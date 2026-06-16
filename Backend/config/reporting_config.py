"""Reporting configuration module."""

import os
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ReportingConfig:
    """Configuration for clinical report generation."""

    output_dir: str
    format: str  # pdf, html, json
    include_visualizations: bool = True
    include_recommendations: bool = True
    language: str = "fr"  # fr, en

    @classmethod
    def from_env(cls) -> "ReportingConfig":
        """Create ReportingConfig from environment variables."""
        return cls(
            output_dir=os.getenv("REPORT_OUTPUT_DIR", "./reports"),
            format=os.getenv("REPORT_FORMAT", "pdf").lower(),
            include_visualizations=os.getenv(
                "REPORT_INCLUDE_VISUALIZATIONS", "true"
            ).lower() == "true",
            include_recommendations=os.getenv(
                "REPORT_INCLUDE_RECOMMENDATIONS", "true"
            ).lower() == "true",
            language=os.getenv("REPORT_LANGUAGE", "fr").lower(),
        )

    def get_output_dir(self) -> Path:
        """Get Path object for report output directory."""
        path = Path(self.output_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_patient_report_path(self, patient_id: str) -> Path:
        """Get report path for a specific patient."""
        output_dir = self.get_output_dir()
        extension = self.format
        return output_dir / f"{patient_id}_report.{extension}"

    def is_pdf(self) -> bool:
        """Check if report format is PDF."""
        return self.format == "pdf"

    def is_html(self) -> bool:
        """Check if report format is HTML."""
        return self.format == "html"

    def is_json(self) -> bool:
        """Check if report format is JSON."""
        return self.format == "json"


# Global instance
reporting_config = ReportingConfig.from_env()


