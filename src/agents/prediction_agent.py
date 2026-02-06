"""Prediction Agent - Predicts cancer using fine-tuned LLM."""

from typing import Dict, Any, Optional
from loguru import logger

from src.agents.base_agent import BaseAgent, AgentResult, AgentStatus
from src.llm.inference_engine import CancerDetectionInference


class PredictionAgent(BaseAgent):
    """Agent for predicting cancer using fine-tuned LLM."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Prediction Agent."""
        super().__init__("Prediction", config)
        self.inference_engine: Optional[CancerDetectionInference] = None

    def validate_input(self, context: Dict[str, Any]) -> bool:
        """Validate input context."""
        if "variants" not in context:
            self.logger.error("Missing variants in context")
            return False
        return True

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        """
        Predict cancer using fine-tuned LLM.

        Args:
            context: Context with variants and patient info

        Returns:
            AgentResult with prediction results
        """
        patient_id = context.get("patient_id")
        variants = context.get("variants", [])
        coverage = context.get("coverage", 30.0)
        model_path = context.get("model_path") or self.config.get("model_path")
        
        try:
            # Initialize inference engine
            self.logger.info("Loading fine-tuned model...")
            self.inference_engine = CancerDetectionInference(model_path=model_path)
            
            # Make prediction
            self.logger.info("Generating cancer prediction...")
            prediction = self.inference_engine.analyze_patient(
                patient_id=patient_id,
                variants=variants,
                coverage=coverage,
            )
            
            self.logger.info(f"✓ Prediction completed")
            self.logger.info(f"  Cancer detected: {prediction.get('cancer_detected')}")
            if prediction.get('cancer_detected'):
                self.logger.info(f"  Cancer types: {prediction.get('cancer_types')}")
                self.logger.info(f"  Risk level: {prediction.get('risk_level')}")
                self.logger.info(f"  Risk score: {prediction.get('risk_score')}")
            
            return AgentResult(
                success=True,
                status=AgentStatus.COMPLETED,
                data={
                    "prediction_results": prediction,
                    "patient_id": patient_id,
                }
            )

        except Exception as e:
            error_msg = f"Prediction failed: {e}"
            self.logger.error(error_msg)
            # Try to provide basic analysis if LLM fails
            return AgentResult(
                success=False,
                status=AgentStatus.FAILED,
                error=error_msg,
                data={
                    "prediction_results": {
                        "cancer_detected": len(variants) > 0,
                        "variants_count": len(variants),
                        "error": "LLM prediction failed, using basic analysis"
                    }
                }
            )








