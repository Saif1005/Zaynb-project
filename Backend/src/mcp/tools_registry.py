"""Registre MCP — schémas tools pour le pipeline Zaynb."""

from __future__ import annotations

from typing import Any, Dict, List

PIPELINE_MCP_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "data_manager",
        "description": "Valide et upload les FASTQ vers S3. Retourne fastq_r1_s3, fastq_r2_s3.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "fastq_r1": {"type": "string"},
                "fastq_r2": {"type": "string"},
            },
            "required": ["patient_id"],
        },
    },
    {
        "name": "genomic_pipeline",
        "description": (
            "Parabricks GPU (fq2bam + MarkDuplicates + BQSR + HaplotypeCaller). "
            "Fallback CPU si GPU indisponible. Retourne bam_s3, vcf_s3."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "fastq_r1_s3": {"type": "string"},
                "fastq_r2_s3": {"type": "string"},
            },
            "required": ["patient_id", "fastq_r1_s3"],
        },
    },
    {
        "name": "vcf_analysis",
        "description": (
            "Analyse VCF — gènes cancer sein BRCA1, BRCA2, HER2, TP53. "
            "Retourne vcf_metrics, variants."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "vcf_s3": {"type": "string"},
            },
            "required": ["patient_id", "vcf_s3"],
        },
    },
    {
        "name": "llm_training",
        "description": "Préparation LoRA optionnelle (skip si train_llm=false).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
                "train_llm": {"type": "boolean"},
            },
            "required": ["patient_id"],
        },
    },
    {
        "name": "prediction",
        "description": (
            "Inférence clinique BioGPT (microsoft/biogpt) sur variants analysés. "
            "Retourne prediction_results."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
            },
            "required": ["patient_id"],
        },
    },
    {
        "name": "report",
        "description": "Génère rapport PDF/HTML clinique.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string"},
            },
            "required": ["patient_id"],
        },
    },
]


def list_mcp_tools() -> List[Dict[str, Any]]:
    return PIPELINE_MCP_TOOLS


def get_tool_schema(name: str) -> Dict[str, Any]:
    for t in PIPELINE_MCP_TOOLS:
        if t["name"] == name:
            return t
    raise KeyError(f"Tool MCP inconnu: {name}")
