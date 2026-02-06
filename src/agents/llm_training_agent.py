"""LLM Training Agent - Manages LLM fine-tuning and data preparation."""

from typing import Dict, Any, Optional
from pathlib import Path
from loguru import logger

from src.agents.base_agent import BaseAgent, AgentResult, AgentStatus
from src.llm.data_preparation import TrainingDataPreparation
from src.llm.fine_tuner import LLMFineTuner
from config.llm_config import llm_config


class LLMTrainingAgent(BaseAgent):
    """Agent for managing LLM training data and fine-tuning."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize LLM Training Agent."""
        super().__init__("LLMTraining", config)
        self.data_prep = TrainingDataPreparation()

    def validate_input(self, context: Dict[str, Any]) -> bool:
        """Validate input context."""
        if "variants" not in context and "pathogenic_cancer_variants" not in context:
            self.logger.warning("No variants in context, skipping LLM training")
            return False
        return True

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        """
        Prepare training data and optionally fine-tune the model.

        Args:
            context: Context with variants and patient info

        Returns:
            AgentResult with training data path and model info
        """
        patient_id = context.get("patient_id")
        variants = context.get("variants", [])
        coverage = context.get("coverage", 30.0)
        
        # Check if fine-tuning is requested
        should_train = context.get("train_llm", False) or self.config.get("auto_train", False)
        
        try:
            # Prepare training data
            self.logger.info("Preparing training data...")
            training_example = self.data_prep.prepare_from_vcf_analysis(
                patient_id=patient_id,
                variants=variants,
                coverage=coverage,
            )
            
            # Save training data
            training_data_path = Path(self.config.get(
                "training_data_path",
                f"./data/training/genomic_training_data.jsonl"
            ))
            training_data_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Load existing data if file exists
            existing_data = []
            if training_data_path.exists():
                existing_data = self.data_prep.load_training_data(training_data_path)
                self.logger.info(f"Loaded {len(existing_data)} existing examples")
            
            # Add new example
            existing_data.append(training_example)
            self.data_prep.save_training_data(existing_data, training_data_path)
            self.logger.info(f"✓ Training data saved: {training_data_path} ({len(existing_data)} examples)")
            
            result_data = {
                "training_data_path": str(training_data_path),
                "total_examples": len(existing_data),
                "patient_id": patient_id,
            }
            
            # Fine-tune if requested
            if should_train:
                self.logger.info("Starting LLM fine-tuning...")
                instance_id = context.get("instance_id") or self.config.get("instance_id")
                ssh_key = context.get("ssh_key") or self.config.get("ssh_key")
                
                if not instance_id or not ssh_key:
                    self.logger.warning("Missing instance_id or ssh_key, skipping fine-tuning")
                else:
                    fine_tuner = LLMFineTuner(
                        instance_id=instance_id,
                        ssh_key_path=ssh_key,
                    )
                    
                    # Setup environment
                    fine_tuner.setup_training_environment()
                    
                    # Upload training data
                    remote_data_path = fine_tuner.upload_training_data(training_data_path)
                    
                    # Run fine-tuning
                    output_dir = self.config.get(
                        "model_output_dir",
                        f"~/llm-training/outputs/mistral-genomic-ft-{patient_id}"
                    )
                    
                    model_path = fine_tuner.run_fine_tuning(
                        training_data_path=training_data_path,
                        output_dir=output_dir,
                    )
                    
                    result_data["model_path"] = model_path
                    result_data["model_trained"] = True
                    
                    fine_tuner.cleanup()
                    self.logger.info(f"✓ Model fine-tuned: {model_path}")
            else:
                result_data["model_trained"] = False
                self.logger.info("Fine-tuning skipped (use --train-llm to enable)")
            
            return AgentResult(
                success=True,
                status=AgentStatus.COMPLETED,
                data=result_data
            )

        except Exception as e:
            error_msg = f"LLM Training failed: {e}"
            self.logger.error(error_msg)
            # Don't fail the pipeline if training fails
            return AgentResult(
                success=False,
                status=AgentStatus.FAILED,
                error=error_msg,
                data={"training_data_path": str(training_data_path) if 'training_data_path' in locals() else None}
            )








