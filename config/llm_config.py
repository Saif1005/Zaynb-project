"""LLM configuration module."""

import os
from typing import Optional
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


@dataclass
class LLMConfig:
    """Configuration for Large Language Model (fine-tuning and inference)."""

    model_name: str
    model_path: str
    device: str
    max_length: int
    temperature: float
    top_p: float
    use_anthropic_api: bool = False
    anthropic_api_key: Optional[str] = None

    # Training parameters
    training_data_path: str = "./data/training/genomic_training_data.jsonl"
    training_output_dir: str = "./models/checkpoints"
    training_epochs: int = 3
    training_batch_size: int = 4
    training_learning_rate: float = 2e-4
    training_logging_steps: int = 10
    training_save_steps: int = 100

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Create LLMConfig from environment variables."""
        return cls(
            model_name=os.getenv(
                "LLM_MODEL_NAME",
                "mistralai/Mistral-7B-Instruct-v0.2",
            ),
            model_path=os.getenv("LLM_MODEL_PATH", "./models/mistral-genomic-ft"),
            device=os.getenv("LLM_DEVICE", "cuda"),
            max_length=int(os.getenv("LLM_MAX_LENGTH", "2048")),
            temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
            top_p=float(os.getenv("LLM_TOP_P", "0.9")),
            use_anthropic_api=os.getenv("USE_ANTHROPIC_API", "false").lower() == "true",
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            training_data_path=os.getenv(
                "TRAINING_DATA_PATH",
                "./data/training/genomic_training_data.jsonl",
            ),
            training_output_dir=os.getenv(
                "TRAINING_OUTPUT_DIR",
                "./models/checkpoints",
            ),
            training_epochs=int(os.getenv("TRAINING_EPOCHS", "3")),
            training_batch_size=int(os.getenv("TRAINING_BATCH_SIZE", "4")),
            training_learning_rate=float(os.getenv("TRAINING_LEARNING_RATE", "2e-4")),
            training_logging_steps=int(os.getenv("TRAINING_LOGGING_STEPS", "10")),
            training_save_steps=int(os.getenv("TRAINING_SAVE_STEPS", "100")),
        )

    def get_model_path(self) -> Path:
        """Get Path object for model directory."""
        return Path(self.model_path)

    def get_training_data_path(self) -> Path:
        """Get Path object for training data."""
        return Path(self.training_data_path)

    def get_training_output_dir(self) -> Path:
        """Get Path object for training output directory."""
        return Path(self.training_output_dir)


# Global instance
llm_config = LLMConfig.from_env()
