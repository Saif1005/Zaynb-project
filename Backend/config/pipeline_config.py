"""Pipeline configuration module."""

import os
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class PipelineConfig:
    """Configuration for genomic pipeline execution."""

    work_dir: str
    max_workers: int
    timeout_hours: int
    keep_intermediate_files: bool = False

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        """Create PipelineConfig from environment variables."""
        return cls(
            work_dir=os.getenv("PIPELINE_WORK_DIR", "./work"),
            max_workers=int(os.getenv("PIPELINE_MAX_WORKERS", "4")),
            timeout_hours=int(os.getenv("PIPELINE_TIMEOUT_HOURS", "72")),
            keep_intermediate_files=os.getenv(
                "PIPELINE_KEEP_INTERMEDIATE", "false"
            ).lower() == "true",
        )

    def get_work_dir(self) -> Path:
        """Get Path object for work directory."""
        path = Path(self.work_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_patient_work_dir(self, patient_id: str) -> Path:
        """Get work directory for a specific patient."""
        patient_dir = self.get_work_dir() / patient_id
        patient_dir.mkdir(parents=True, exist_ok=True)
        return patient_dir

    @property
    def timeout_seconds(self) -> int:
        """Get timeout in seconds."""
        return self.timeout_hours * 3600


# Global instance
pipeline_config = PipelineConfig.from_env()


