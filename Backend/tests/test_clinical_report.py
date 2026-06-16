"""Tests rapport clinique JSON."""

from src.report.clinical_report_builder import build_clinical_report


def test_clinical_report_structure():
    context = {
        "patient_id": "PT_001",
        "breast_cancer_risk_detected": True,
        "identified_pathogenic_genes": ["BRCA1"],
        "breast_cancer_variants": [
            {
                "gene": "BRCA1",
                "chromosome": "chr17",
                "position": 43044295,
                "ref": "C",
                "alt": "T",
                "quality": 950.5,
                "dp": 45,
                "vaf": 0.48,
            }
        ],
        "prediction_results": {
            "risk_level": "HIGH",
            "diagnostic_conclusion": "Risque génétique de cancer du sein : ÉLEVÉ",
            "clinical_summary": (
                "Présence confirmée d'un variant pathogène hétérozygote sur BRCA1."
            ),
        },
        "model_name": "microsoft/biogpt",
    }
    report = build_clinical_report(context, execution_time_seconds=1245.0, steps_completed=[
        "data_manager", "parabricks", "vcf_analysis", "prediction", "report"
    ])
    data = report.to_api_dict()

    assert data["patient_id"] == "PT_001"
    assert "report_id" in data
    assert data["system_metrics"]["execution_time_seconds"] == 1245.0
    assert "BRCA1" in data["genomic_findings"]["breast_cancer_panel_analyzed"]
    assert len(data["genomic_findings"]["pathogenic_variants_detected"]) == 1
    v = data["genomic_findings"]["pathogenic_variants_detected"][0]
    assert v["gene"] == "BRCA1"
    assert v["mutation"] == "C>T"
    assert v["gatk_metrics"]["QUAL"] == 950.5
    assert v["gatk_metrics"]["DP"] == 45
    assert v["gatk_metrics"]["VAF"] == 0.48
    assert data["clinical_prediction"]["risk_level"] == "HIGH"
    assert data["clinical_prediction"]["status"] == "AWAITING_MEDICAL_VALIDATION"
    assert "oncologue" in data["clinical_prediction"]["legal_disclaimer"].lower()
