"""Inference engine for fine-tuned LLM cancer detection."""

import json
from pathlib import Path
from typing import Dict, List, Optional
from loguru import logger

try:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
    from peft import PeftModel
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False
    torch = None
    AutoModelForCausalLM = None
    AutoTokenizer = None
    PeftModel = None

from config.llm_config import llm_config
from src.llm.prompt_templates import GenomicPromptTemplates


class InferenceError(Exception):
    """Custom exception for inference errors."""

    pass


class CancerDetectionInference:
    """Inference engine for cancer detection using fine-tuned LLM."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        base_model: Optional[str] = None,
        device: Optional[str] = None,
    ):
        """
        Initialize inference engine.

        Args:
            model_path: Path to fine-tuned model (LoRA adapters)
            base_model: Base model name (defaults to config)
            device: Device to use (defaults to config)
        """
        self.model_path = model_path or llm_config.model_path
        self.base_model = base_model or llm_config.model_name
        self.device = device or llm_config.device

        self.model = None
        self.tokenizer = None
        self.prompt_templates = GenomicPromptTemplates()

    def load_model(self) -> None:
        """Load fine-tuned model and tokenizer."""
        if not HAS_TORCH:
            raise InferenceError("PyTorch and transformers are required for inference. Install with: pip install torch transformers peft")
        
        if self.model is not None:
            return

        logger.info(f"Loading model from {self.model_path}")
        logger.info(f"Base model: {self.base_model}")

        try:
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.base_model)
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token

            # Load base model
            self.model = AutoModelForCausalLM.from_pretrained(
                self.base_model,
                device_map="auto",
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
            )

            # Load LoRA adapters if fine-tuned model exists
            model_path = Path(self.model_path)
            if model_path.exists():
                logger.info(f"Loading LoRA adapters from {model_path}")
                self.model = PeftModel.from_pretrained(self.model, str(model_path))
                self.model = self.model.merge_and_unload()  # Merge adapters

            self.model.eval()
            logger.info("Model loaded successfully")

        except Exception as e:
            error_msg = f"Failed to load model: {e}"
            logger.error(error_msg)
            raise InferenceError(error_msg) from e

    def analyze_patient(
        self,
        patient_id: str,
        variants: List[Dict],
        coverage: float,
        tmb: Optional[float] = None,
        quality_metrics: Optional[Dict] = None,
    ) -> Dict:
        """
        Analyze patient genomic data for cancer detection.

        Args:
            patient_id: Patient identifier
            variants: List of pathogenic variants
            coverage: Sequencing coverage
            tmb: Tumor mutational burden (optional)
            quality_metrics: Quality metrics (optional)

        Returns:
            Dictionary with analysis results
        """
        if self.model is None:
            self.load_model()

        # Format prompt
        user_prompt = self.prompt_templates.format_user_prompt(
            patient_id=patient_id,
            variants=variants,
            coverage=coverage,
            tmb=tmb,
            quality_metrics=quality_metrics,
        )

        # Create messages
        messages = [
            {"role": "system", "content": GenomicPromptTemplates.SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # Tokenize
        text = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer(text, return_tensors="pt").to(self.device)

        # Generate
        logger.info("Generating response from LLM...")
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=llm_config.temperature,
                top_p=llm_config.top_p,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        # Decode response
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        assistant_response = response.split("assistant\n")[-1].strip()

        # Parse response
        results = self._parse_response(assistant_response)

        logger.info(f"Analysis completed for patient {patient_id}")
        return results

    def _parse_response(self, response: str) -> Dict:
        """
        Parse LLM response into structured format.

        Args:
            response: LLM response text

        Returns:
            Structured results dictionary
        """
        results = {
            "cancer_detected": False,
            "cancer_types": [],
            "risk_level": "LOW",
            "risk_score": 0.0,
            "recommendations": [],
            "raw_response": response,
        }

        # Parse response
        lines = response.split("\n")
        for line in lines:
            line = line.strip()

            if line.startswith("RÉSULTAT:"):
                result = line.split(":")[-1].strip()
                results["cancer_detected"] = result.upper() == "POSITIF"

            elif line.startswith("Types de cancer"):
                types_str = line.split(":")[-1].strip()
                results["cancer_types"] = [
                    t.strip() for t in types_str.split(",") if t.strip()
                ]

            elif line.startswith("Niveau de risque"):
                level = line.split(":")[-1].strip()
                results["risk_level"] = level.upper()

            elif line.startswith("Score de risque"):
                score_str = line.split(":")[-1].strip().split("/")[0]
                try:
                    results["risk_score"] = float(score_str)
                except ValueError:
                    pass

            elif line and line[0].isdigit() and "." in line:
                # Recommendation line
                rec = line.split(".", 1)[-1].strip()
                if rec:
                    results["recommendations"].append(rec)

        return results

    def batch_analyze(
        self, patients_data: List[Dict]
    ) -> List[Dict]:
        """
        Analyze multiple patients in batch.

        Args:
            patients_data: List of patient data dictionaries

        Returns:
            List of analysis results
        """
        results = []
        for patient_data in patients_data:
            try:
                result = self.analyze_patient(**patient_data)
                result["patient_id"] = patient_data.get("patient_id")
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to analyze patient {patient_data.get('patient_id')}: {e}")
                results.append({
                    "patient_id": patient_data.get("patient_id"),
                    "error": str(e),
                })

        return results



