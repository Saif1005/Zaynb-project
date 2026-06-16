"""Schéma JSON clinique — output API Zaynb."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class GATKMetrics(BaseModel):
    QUAL: Optional[float] = None
    DP: Optional[int] = None
    VAF: Optional[float] = None


class PathogenicVariantFinding(BaseModel):
    gene: str
    chromosome: str
    position: int
    mutation: str
    gatk_metrics: GATKMetrics
    pathogenicity: str = "pathogenic"
    inheritance: Optional[str] = None


class GenomicFindings(BaseModel):
    breast_cancer_panel_analyzed: List[str] = Field(default_factory=list)
    pathogenic_variants_detected: List[PathogenicVariantFinding] = Field(
        default_factory=list
    )
    breast_cancer_risk_detected: bool = False
    identified_pathogenic_genes: List[str] = Field(default_factory=list)


class SystemMetrics(BaseModel):
    execution_time_seconds: float = 0.0
    pipeline_engine: str = "NVIDIA Clara Parabricks 4.6.0-1"
    hardware: str = "AWS g4dn.xlarge"
    steps_completed: List[str] = Field(default_factory=list)


LEGAL_DISCLAIMER = (
    "Ce rapport est généré par un système d'intelligence artificielle à des fins "
    "d'aide à la décision. Il ne constitue pas un diagnostic médical et doit être "
    "validé par un oncologue ou un généticien clinique avant toute prise de décision thérapeutique."
)


class ClinicalPrediction(BaseModel):
    model: str = "BioGPT"
    risk_level: str = "LOW"
    diagnostic_conclusion: str = "Risque génétique de cancer du sein : FAIBLE"
    clinical_summary: str = ""
    legal_disclaimer: str = LEGAL_DISCLAIMER
    status: str = "AWAITING_MEDICAL_VALIDATION"


class ClinicalReport(BaseModel):
    report_id: str
    patient_id: str
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"))
    system_metrics: SystemMetrics = Field(default_factory=SystemMetrics)
    genomic_findings: GenomicFindings = Field(default_factory=GenomicFindings)
    clinical_prediction: ClinicalPrediction = Field(default_factory=ClinicalPrediction)
    report_s3: Optional[str] = None

    def to_api_dict(self) -> dict:
        return self.model_dump(exclude_none=True)
