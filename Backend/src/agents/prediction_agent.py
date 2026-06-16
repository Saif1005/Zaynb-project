"""Prediction Agent — inférence clinique BioGPT (Microsoft)."""

import os
from typing import Dict, Any, Optional

from src.agents.base_agent import BaseAgent, AgentResult, AgentStatus
from src.llm.inference_engine import CancerDetectionInference
from src.report.clinical_report_builder import (
    build_clinical_prediction,
    build_genomic_findings,
    LEGAL_DISCLAIMER,
)
from config.llm_config import llm_config, get_biollm_model_and_path


class PredictionAgent(BaseAgent):
    """Agent prédiction cancer du sein via microsoft/biogpt (+ LoRA optionnel)."""

    DEFAULT_MODEL = "microsoft/biogpt"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__("Prediction", config)
        self.inference_engine: Optional[CancerDetectionInference] = None

    def validate_input(self, context: Dict[str, Any]) -> bool:
        if "variants" in context:
            return True
        if "vcf_metrics" in context and context["vcf_metrics"].get("variants") is not None:
            return True
        if context.get("genomic_findings"):
            return True
        self.logger.error("Missing variants or vcf_metrics in context")
        return False

    def _rule_based_prediction(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Secours uniquement si BioGPT indisponible (ALLOW_RULE_BASED_FALLBACK=true)."""
        genomic = build_genomic_findings(context)
        clinical = build_clinical_prediction(
            genomic, model_name="rule-based-fallback"
        )
        return {
            "cancer_detected": genomic.breast_cancer_risk_detected,
            "cancer_types": ["breast"] if genomic.breast_cancer_risk_detected else [],
            "risk_level": clinical.risk_level,
            "risk_score": {"HIGH": 85.0, "MODERATE": 55.0, "LOW": 15.0}.get(
                clinical.risk_level, 15.0
            ),
            "diagnostic_conclusion": clinical.diagnostic_conclusion,
            "clinical_summary": clinical.clinical_summary,
            "legal_disclaimer": clinical.legal_disclaimer,
            "status": clinical.status,
            "prediction_mode": "rule_based_fallback",
        }

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        patient_id = context.get("patient_id")
        variants = context.get("variants")
        coverage = context.get("coverage", 30.0)
        if variants is None and context.get("vcf_metrics"):
            vcf_metrics = context["vcf_metrics"]
            variants = vcf_metrics.get("variants", [])
            meta = vcf_metrics.get("metadata", {})
            coverage = meta.get("coverage", coverage)
            if not patient_id:
                patient_id = meta.get("patient_id", "unknown")
        variants = variants or []

        skip_biogpt = os.getenv("SKIP_BIOGPT", "false").lower() in ("1", "true", "yes")
        allow_fallback = os.getenv("ALLOW_RULE_BASED_FALLBACK", "false").lower() in (
            "1",
            "true",
            "yes",
        )

        if skip_biogpt:
            self.logger.warning(
                "SKIP_BIOGPT=true — prédiction rule-based (désactiver pour thèse / prod BioGPT)"
            )
            prediction = self._rule_based_prediction(context)
            return AgentResult(
                success=True,
                status=AgentStatus.COMPLETED,
                data={
                    "prediction_results": prediction,
                    "patient_id": patient_id,
                    "model_name": "rule-based",
                },
            )

        preset_name, preset_path = get_biollm_model_and_path()
        model_path = context.get("model_path") or self.config.get("model_path") or preset_path
        base_model = (
            context.get("model_name")
            or self.config.get("model_name")
            or llm_config.prediction_model
            or preset_name
            or self.DEFAULT_MODEL
        )

        try:
            self.logger.info(f"Chargement BioGPT: {base_model} (1ère inférence: 2-5 min)")
            self.inference_engine = CancerDetectionInference(
                model_path=model_path,
                base_model=base_model,
            )
            self.inference_engine.load_model()

            self.logger.info("Inférence clinique BioGPT...")
            prediction = self.inference_engine.analyze_patient(
                patient_id=patient_id,
                variants=variants,
                coverage=coverage,
            )
            prediction.setdefault("legal_disclaimer", LEGAL_DISCLAIMER)
            prediction.setdefault("status", "AWAITING_MEDICAL_VALIDATION")
            prediction.setdefault("prediction_mode", "biogpt")

            self.logger.info(
                f"✓ BioGPT prediction — risk={prediction.get('risk_level')}"
            )

            return AgentResult(
                success=True,
                status=AgentStatus.COMPLETED,
                data={
                    "prediction_results": prediction,
                    "patient_id": patient_id,
                    "model_name": base_model,
                },
            )

        except Exception as e:
            self.logger.error(f"BioGPT failed: {e}")
            if not allow_fallback:
                return AgentResult(
                    success=False,
                    status=AgentStatus.FAILED,
                    error=f"BioGPT inference failed (ALLOW_RULE_BASED_FALLBACK=false): {e}",
                )
            self.logger.warning("ALLOW_RULE_BASED_FALLBACK=true — secours rule-based")
            prediction = self._rule_based_prediction(context)
            prediction["biogpt_error"] = str(e)
            return AgentResult(
                success=True,
                status=AgentStatus.COMPLETED,
                data={
                    "prediction_results": prediction,
                    "patient_id": patient_id,
                    "model_name": "rule-based-fallback",
                },
            )
        finally:
            if self.inference_engine:
                self.inference_engine.unload_model()
