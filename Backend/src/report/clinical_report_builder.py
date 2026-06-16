"""Assemblage du rapport clinique JSON structuré."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.database.cancer_genes_db import get_cancer_genes_db
from src.schemas.clinical_report import (
    ClinicalPrediction,
    ClinicalReport,
    GATKMetrics,
    GenomicFindings,
    LEGAL_DISCLAIMER,
    PathogenicVariantFinding,
    SystemMetrics,
)

_GENE_DISPLAY = {"ERBB2": "HER2"}

CLINICAL_MIN_QUAL = float(os.getenv("CLINICAL_MIN_QUAL", "20"))
CLINICAL_MIN_DP = int(os.getenv("CLINICAL_MIN_DP", "10"))
CLINICAL_MIN_VAF = float(os.getenv("CLINICAL_MIN_VAF", "0.05"))


def _display_gene(symbol: str) -> str:
    u = symbol.upper()
    return _GENE_DISPLAY.get(u, u)


def _panel_symbols_from_db() -> List[str]:
    db = get_cancer_genes_db()
    seen: set[str] = set()
    symbols: List[str] = []
    for gene_key in db.get_all_genes():
        info = db.get_gene_info(gene_key)
        if not info:
            continue
        types = info.get("cancer_types", [])
        if not any("breast" in str(t).lower() for t in types):
            continue
        sym = _display_gene(str(info.get("symbol", gene_key)))
        if sym not in seen:
            seen.add(sym)
            symbols.append(sym)
    return sorted(symbols)


def variant_dict_to_finding(v: Dict[str, Any]) -> PathogenicVariantFinding:
    gene_raw = str(v.get("gene", "Unknown")).upper()
    gene = _display_gene(gene_raw)
    db = get_cancer_genes_db()
    gene_info = db.get_gene_info(gene_raw) or db.get_gene_info(gene) or {}
    ref = v.get("ref", "")
    alt = v.get("alt", "")
    chrom = str(v.get("chromosome", ""))
    if chrom and not chrom.startswith("chr"):
        chrom = f"chr{chrom.lstrip('chr')}"

    return PathogenicVariantFinding(
        gene=gene,
        chromosome=chrom,
        position=int(v.get("position", 0)),
        mutation=f"{ref}>{alt}" if ref and alt else v.get("mutation", "N/A"),
        gatk_metrics=GATKMetrics(
            QUAL=round(float(v["quality"]), 1) if v.get("quality") is not None else None,
            DP=int(v.get("dp") or v.get("depth") or 0) or None,
            VAF=round(float(v["vaf"]), 3) if v.get("vaf") is not None else None,
        ),
        pathogenicity=str(
            gene_info.get("pathogenicity", v.get("pathogenicity", "pathogenic"))
        ),
        inheritance=gene_info.get("inheritance"),
    )


def build_genomic_findings(context: Dict[str, Any]) -> GenomicFindings:
    panel = _panel_symbols_from_db()
    variants_raw = context.get("breast_cancer_variants") or context.get("variants") or []
    findings = [variant_dict_to_finding(v) for v in variants_raw if isinstance(v, dict)]

    risk = context.get("breast_cancer_risk_detected", False)
    genes = context.get("identified_pathogenic_genes") or []
    if not genes and findings:
        genes = sorted({f.gene for f in findings})
    if findings:
        risk = True

    return GenomicFindings(
        breast_cancer_panel_analyzed=panel,
        pathogenic_variants_detected=findings,
        breast_cancer_risk_detected=bool(risk),
        identified_pathogenic_genes=genes,
    )


def _risk_from_findings(findings: GenomicFindings) -> str:
    if not findings.pathogenic_variants_detected:
        return "LOW"
    high_genes = {"BRCA1", "BRCA2", "TP53"}
    detected = {f.gene for f in findings.pathogenic_variants_detected}
    if detected & high_genes:
        return "HIGH"
    return "MODERATE"


def _diagnostic_conclusion(risk_level: str) -> str:
    mapping = {
        "HIGH": "Risque génétique de cancer du sein : ÉLEVÉ",
        "MODERATE": "Risque génétique de cancer du sein : MODÉRÉ",
        "LOW": "Risque génétique de cancer du sein : FAIBLE",
    }
    return mapping.get(risk_level.upper(), mapping["LOW"])


def _build_clinical_summary(
    findings: GenomicFindings,
    prediction_raw: Optional[Dict[str, Any]] = None,
) -> str:
    if prediction_raw and prediction_raw.get("clinical_summary"):
        return prediction_raw["clinical_summary"]

    if not findings.pathogenic_variants_detected:
        return (
            "Aucun variant pathogène du panel cancer du sein (BRCA1, BRCA2, TP53, PIK3CA, "
            "PTEN, MYC, HER2) n'a été détecté après filtrage GATK (QUAL, DP, VAF). "
            "Le profil génétique analysé ne présente pas d'altération connue à haut risque "
            "pour le cancer du sein sur les gènes ciblés."
        )

    paragraphs: List[str] = []
    for v in findings.pathogenic_variants_detected:
        m = v.gatk_metrics
        inh = v.inheritance or "non documentée"
        paragraphs.append(
            f"Variant pathogène confirmé sur {v.gene} ({v.chromosome}:{v.position}, "
            f"mutation {v.mutation}). Les métriques GATK (QUAL={m.QUAL}, DP={m.DP}, "
            f"VAF={m.VAF}) supportent la présence de l'altération. "
            f"Le gène {v.gene} est associé à un mode de transmission {inh.replace('_', ' ')} "
            f"et à un risque accru de carcinome mammaire selon cancer_genes_db."
        )
    return " ".join(paragraphs)


def build_clinical_prediction(
    findings: GenomicFindings,
    prediction_raw: Optional[Dict[str, Any]] = None,
    model_name: str = "BioGPT",
) -> ClinicalPrediction:
    raw = prediction_raw or {}
    risk = raw.get("risk_level", _risk_from_findings(findings)).upper()
    if risk not in ("HIGH", "MODERATE", "LOW"):
        risk = _risk_from_findings(findings)

    return ClinicalPrediction(
        model=model_name,
        risk_level=risk,
        diagnostic_conclusion=raw.get(
            "diagnostic_conclusion", _diagnostic_conclusion(risk)
        ),
        clinical_summary=_build_clinical_summary(findings, raw),
        legal_disclaimer=raw.get("legal_disclaimer", LEGAL_DISCLAIMER),
        status="AWAITING_MEDICAL_VALIDATION",
    )


def build_clinical_report(
    context: Dict[str, Any],
    execution_time_seconds: float = 0.0,
    steps_completed: Optional[List[str]] = None,
) -> ClinicalReport:
    patient_id = context.get("patient_id", "UNKNOWN")
    date_str = datetime.utcnow().strftime("%Y%m%d")
    report_id = f"REP-{patient_id}-{date_str}"

    genomic = build_genomic_findings(context)
    prediction_raw = context.get("prediction_results") or context.get("clinical_prediction")
    model_name = context.get("model_name") or "microsoft/biogpt"
    if prediction_raw and prediction_raw.get("model_name"):
        model_name = prediction_raw["model_name"]
    display_model = (
        "BioGPT"
        if "biogpt" in str(model_name).lower()
        else model_name
    )

    parabricks_ver = os.getenv(
        "PARABRICKS_IMAGE", "nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1"
    ).split(":")[-1]

    return ClinicalReport(
        report_id=report_id,
        patient_id=patient_id,
        system_metrics=SystemMetrics(
            execution_time_seconds=round(execution_time_seconds, 1),
            pipeline_engine=f"NVIDIA Clara Parabricks {parabricks_ver}",
            hardware=os.getenv("PIPELINE_HARDWARE", "AWS g4dn.xlarge"),
            steps_completed=steps_completed or [],
        ),
        genomic_findings=genomic,
        clinical_prediction=build_clinical_prediction(
            genomic, prediction_raw, display_model
        ),
        report_s3=context.get("report_s3"),
    )
