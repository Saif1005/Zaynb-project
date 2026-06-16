"""Quality control configuration module."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class QualityControlConfig:
    """Configuration for quality control thresholds."""

    min_coverage: int
    min_vaf: float
    min_quality_score: float
    min_mapping_quality: int = 20
    min_base_quality: int = 20

    @classmethod
    def from_env(cls) -> "QualityControlConfig":
        """Create QualityControlConfig from environment variables."""
        return cls(
            min_coverage=int(os.getenv("MIN_COVERAGE", "30")),
            min_vaf=float(os.getenv("MIN_VAF", "0.05")),
            min_quality_score=float(os.getenv("MIN_QUALITY_SCORE", "20.0")),
            min_mapping_quality=int(os.getenv("MIN_MAPPING_QUALITY", "20")),
            min_base_quality=int(os.getenv("MIN_BASE_QUALITY", "20")),
        )

    def validate_coverage(self, coverage: float) -> bool:
        """Check if coverage meets minimum threshold."""
        return coverage >= self.min_coverage

    def validate_vaf(self, vaf: float) -> bool:
        """Check if VAF meets minimum threshold."""
        return vaf >= self.min_vaf

    def validate_quality(self, quality: float) -> bool:
        """Check if quality score meets minimum threshold."""
        return quality >= self.min_quality_score


# Global instance
quality_control_config = QualityControlConfig.from_env()

