"""LLM configuration module."""

import os
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


# Choix de modèles BioLLM (pré-entraînés biomédicaux ou généraux pour la génomique)
# Variable d'environnement : BIOLLM_MODEL = mistral | biogpt | biogpt-large | llama3 | custom
BIOLLM_MODELS: Dict[str, Dict[str, str]] = {
    "mistral": {
        "model_name": "mistralai/Mistral-7B-Instruct-v0.2",
        "model_path": "./models/mistral-genomic-ft",
        "description": "Mistral 7B Instruct (général, bon pour fine-tuning génomique)",
    },
    "biogpt": {
        "model_name": "microsoft/biogpt",
        "model_path": "./models/biogpt-genomic-ft",
        "description": "BioGPT (Microsoft) - pré-entraîné sur PubMed, ~1.5B params",
    },
    "biogpt-large": {
        "model_name": "microsoft/BioGPT-Large",
        "model_path": "./models/biogpt-large-genomic-ft",
        "description": "BioGPT-Large (Microsoft) - pré-entraîné biomédical, plus grand",
    },
    "llama3": {
        "model_name": "meta-llama/Meta-Llama-3-8B-Instruct",
        "model_path": "./models/llama3-genomic-ft",
        "description": "Llama 3 8B Instruct (nécessite accord Meta pour accès)",
    },
    "custom": {
        "model_name": "",  # lu depuis LLM_MODEL_NAME
        "model_path": "",  # lu depuis LLM_MODEL_PATH
        "description": "Modèle personnalisé (LLM_MODEL_NAME + LLM_MODEL_PATH)",
    },
}


def get_biollm_model_and_path() -> Tuple[str, str]:
    """
    Retourne (model_name, model_path) selon BIOLLM_MODEL et LLM_MODEL_NAME / LLM_MODEL_PATH.
    """
    choice = (os.getenv("BIOLLM_MODEL") or "mistral").strip().lower()
    if choice not in BIOLLM_MODELS:
        choice = "mistral"
    preset = BIOLLM_MODELS[choice]
    model_name = preset["model_name"] or os.getenv("LLM_MODEL_NAME", "mistralai/Mistral-7B-Instruct-v0.2")
    model_path = preset["model_path"] or os.getenv("LLM_MODEL_PATH", "./models/mistral-genomic-ft")
    if choice == "custom":
        model_name = os.getenv("LLM_MODEL_NAME", model_name)
        model_path = os.getenv("LLM_MODEL_PATH", model_path)
    return model_name, model_path


@dataclass
class LLMConfig:
    """Configuration for Large Language Model (fine-tuning and inference)."""

    model_name: str
    model_path: str
    biollm_model: str
    prediction_model: str
    orchestrator_model: str
    ollama_host: str
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
        biollm_choice = (os.getenv("BIOLLM_MODEL") or "mistral").strip().lower()
        if biollm_choice not in BIOLLM_MODELS:
            biollm_choice = "mistral"
        model_name, model_path = get_biollm_model_and_path()

        return cls(
            model_name=model_name,
            model_path=model_path,
            biollm_model=biollm_choice,
            prediction_model=os.getenv("PREDICTION_MODEL", "microsoft/biogpt"),
            orchestrator_model=os.getenv("ORCHESTRATOR_LLM_MODEL", "mistral:v0.3"),
            ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
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

    @staticmethod
    def get_available_biollm_models() -> Dict[str, Dict[str, Any]]:
        """Liste des modèles BioLLM disponibles (pour CLI / UI)."""
        return dict(BIOLLM_MODELS)

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
