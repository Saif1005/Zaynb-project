"""Modèles Pydantic — échanges inter-agents (cancer du sein, BRCA1/BRCA2)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


BREAST_CANCER_TARGET_GENES = frozenset(
    {"BRCA1", "BRCA2", "TP53", "PIK3CA", "PTEN", "ERBB2", "HER2", "MYC"}
)


class PipelineState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AgentStepName(str, Enum):
    DATA_MANAGER = "data_manager"
    PARABRICKS = "parabricks"
    VCF_ANALYSIS = "vcf_analysis"
    LLM_TRAINING = "llm_training"
    PREDICTION = "prediction"
    REPORT = "report"


class FastqInput(BaseModel):
    patient_id: str
    fastq_r1: Optional[str] = None
    fastq_r2: Optional[str] = None
    fastq_r1_s3: Optional[str] = None
    fastq_r2_s3: Optional[str] = None

    @field_validator("patient_id")
    @classmethod
    def patient_id_non_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("patient_id requis")
        return v.strip()


class GenomicPaths(BaseModel):
    bam_s3: Optional[str] = None
    bam_recal_s3: Optional[str] = None
    vcf_s3: Optional[str] = None
    reference_genome_s3: Optional[str] = None


class VariantRecord(BaseModel):
    chromosome: str
    position: int
    ref: str
    alt: str
    gene: Optional[str] = None
    quality: Optional[float] = None
    vaf: Optional[float] = None
    depth: Optional[int] = None
    is_pathogenic: bool = False
    impact_score: float = 0.0
    extra: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class VCFMetrics(BaseModel):
    metadata: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)
    variants: List[VariantRecord] = Field(default_factory=list)
    breast_cancer_variants: List[VariantRecord] = Field(default_factory=list)

    @classmethod
    def from_raw(cls, raw: Dict[str, Any]) -> "VCFMetrics":
        variants = [
            VariantRecord.model_validate(v) if isinstance(v, dict) else v
            for v in raw.get("variants", [])
        ]
        breast = [v for v in variants if v.gene in BREAST_CANCER_TARGET_GENES]
        return cls(
            metadata=raw.get("metadata", {}),
            summary=raw.get("summary", {}),
            variants=variants,
            breast_cancer_variants=breast,
        )


class PredictionResult(BaseModel):
    cancer_detected: bool = False
    cancer_types: List[str] = Field(default_factory=list)
    risk_level: str = "unknown"
    risk_score: float = 0.0
    brca1_detected: bool = False
    brca2_detected: bool = False
    clinical_findings: str = ""
    model_config = {"extra": "allow"}


class AgentStepResult(BaseModel):
    step: AgentStepName
    state: PipelineState
    success: bool
    execution_time: float = 0.0
    error: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)


class PipelineContext(BaseModel):
    """Contexte partagé déterministe entre agents."""

    patient_id: str
    state: PipelineState = PipelineState.PENDING
    fastq_r1: Optional[str] = None
    fastq_r2: Optional[str] = None
    fastq_r1_s3: Optional[str] = None
    fastq_r2_s3: Optional[str] = None
    vcf_s3: Optional[str] = None
    bam_s3: Optional[str] = None
    bam_recal_s3: Optional[str] = None
    instance_id: Optional[str] = None
    ssh_key: Optional[str] = None
    train_llm: bool = False
    model_name: Optional[str] = None
    model_path: Optional[str] = None
    biollm_model: Optional[str] = None
    variants: List[VariantRecord] = Field(default_factory=list)
    vcf_metrics: Optional[VCFMetrics] = None
    vcf_metrics_path: Optional[str] = None
    prediction_results: Optional[PredictionResult] = None
    report_path: Optional[str] = None
    report_s3: Optional[str] = None
    training_data_path: Optional[str] = None
    steps_completed: List[AgentStepName] = Field(default_factory=list)
    pipeline_backend: Optional[str] = None  # "parabricks" | "cpu"
    extra: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}

    def to_agent_dict(self) -> Dict[str, Any]:
        d = self.model_dump(exclude_none=True)
        if self.vcf_metrics:
            d["vcf_metrics"] = self.vcf_metrics.model_dump()
        if self.prediction_results:
            d["prediction_results"] = self.prediction_results.model_dump()
        if self.variants:
            d["variants"] = [v.model_dump() for v in self.variants]
        d.update(self.extra)
        return d

    @classmethod
    def from_agent_dict(cls, data: Dict[str, Any]) -> "PipelineContext":
        raw = dict(data)
        if "vcf_metrics" in raw and isinstance(raw["vcf_metrics"], dict):
            raw["vcf_metrics"] = VCFMetrics.from_raw(raw["vcf_metrics"])
        if "prediction_results" in raw and isinstance(raw["prediction_results"], dict):
            raw["prediction_results"] = PredictionResult.model_validate(
                raw["prediction_results"]
            )
        if "variants" in raw and raw["variants"] and isinstance(raw["variants"][0], dict):
            raw["variants"] = [VariantRecord.model_validate(v) for v in raw["variants"]]
        extra = {k: v for k, v in raw.items() if k not in cls.model_fields}
        known = {k: v for k, v in raw.items() if k in cls.model_fields}
        known["extra"] = extra
        return cls.model_validate(known)

    def merge_agent_result(self, result_data: Dict[str, Any]) -> None:
        ctx = self.from_agent_dict({**self.to_agent_dict(), **result_data})
        for field_name in PipelineContext.model_fields:
            val = getattr(ctx, field_name)
            if val is not None and field_name != "extra":
                setattr(self, field_name, val)
        self.extra.update(ctx.extra)
