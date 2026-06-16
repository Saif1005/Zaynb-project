"""LangChain Tools — wrappers MCP pour agents Zaynb."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from src.mcp.bridge import MCPToolBridge


class PatientInput(BaseModel):
    patient_id: str = Field(description="Identifiant patient")


class DataManagerInput(PatientInput):
    fastq_r1: Optional[str] = None
    fastq_r2: Optional[str] = None


class GenomicPipelineInput(PatientInput):
    fastq_r1_s3: Optional[str] = None
    fastq_r2_s3: Optional[str] = None


class VcfAnalysisInput(PatientInput):
    vcf_s3: Optional[str] = None


class LlmTrainingInput(PatientInput):
    train_llm: bool = False


def build_langchain_tools(bridge: MCPToolBridge) -> List[StructuredTool]:
    """Construit les StructuredTool LangChain branchés sur le pont MCP."""

    def _wrap(name: str, args: Dict[str, Any]) -> str:
        return bridge.call_tool(name, args)

    return [
        StructuredTool.from_function(
            func=lambda patient_id, fastq_r1=None, fastq_r2=None: _wrap(
                "data_manager",
                {"patient_id": patient_id, "fastq_r1": fastq_r1, "fastq_r2": fastq_r2},
            ),
            name="data_manager",
            description="Valide et upload FASTQ vers S3",
            args_schema=DataManagerInput,
        ),
        StructuredTool.from_function(
            func=lambda patient_id, fastq_r1_s3=None, fastq_r2_s3=None: _wrap(
                "genomic_pipeline",
                {"patient_id": patient_id, "fastq_r1_s3": fastq_r1_s3, "fastq_r2_s3": fastq_r2_s3},
            ),
            name="genomic_pipeline",
            description="Parabricks GPU + BQSR + HaplotypeCaller",
            args_schema=GenomicPipelineInput,
        ),
        StructuredTool.from_function(
            func=lambda patient_id, vcf_s3=None: _wrap(
                "vcf_analysis",
                {"patient_id": patient_id, "vcf_s3": vcf_s3},
            ),
            name="vcf_analysis",
            description="Analyse VCF gènes cancer sein",
            args_schema=VcfAnalysisInput,
        ),
        StructuredTool.from_function(
            func=lambda patient_id, train_llm=False: _wrap(
                "llm_training",
                {"patient_id": patient_id, "train_llm": train_llm},
            ),
            name="llm_training",
            description="Préparation LoRA optionnelle",
            args_schema=LlmTrainingInput,
        ),
        StructuredTool.from_function(
            func=lambda patient_id: _wrap("prediction", {"patient_id": patient_id}),
            name="prediction",
            description="Inférence BioGPT (microsoft/biogpt)",
            args_schema=PatientInput,
        ),
        StructuredTool.from_function(
            func=lambda patient_id: _wrap("report", {"patient_id": patient_id}),
            name="report",
            description="Génère rapport clinique",
            args_schema=PatientInput,
        ),
    ]


def context_summary(bridge: MCPToolBridge) -> str:
    ctx = bridge.get_context_dict()
    keys = ["patient_id", "vcf_s3", "bam_s3", "fastq_r1_s3", "steps_completed", "prediction_results"]
    summary = {k: ctx.get(k) for k in keys if ctx.get(k) is not None}
    return json.dumps(summary, default=str)[:2000]
