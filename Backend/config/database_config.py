"""Database configuration module."""

import os
from typing import Optional
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class DatabaseConfig:
    """Configuration for database paths and access."""

    cancer_genes_db_path: str
    clinvar_db_path: Optional[str] = None
    gnomad_db_path: Optional[str] = None
    dbsnp_db_path: Optional[str] = None

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Create DatabaseConfig from environment variables."""
        return cls(
            cancer_genes_db_path=os.getenv(
                "CANCER_GENES_DB_PATH",
                "./data/cancer_genes/cancer_genes_db.json",
            ),
            clinvar_db_path=os.getenv("CLINVAR_DB_PATH"),
            gnomad_db_path=os.getenv("GNOMAD_DB_PATH"),
            dbsnp_db_path=os.getenv("DBSNP_DB_PATH"),
        )

    def get_cancer_genes_db_path(self) -> Path:
        """Get Path object for cancer genes database."""
        return Path(self.cancer_genes_db_path)

    def get_clinvar_db_path(self) -> Optional[Path]:
        """Get Path object for ClinVar database."""
        if self.clinvar_db_path:
            return Path(self.clinvar_db_path)
        return None

    def get_gnomad_db_path(self) -> Optional[Path]:
        """Get Path object for gnomAD database."""
        if self.gnomad_db_path:
            return Path(self.gnomad_db_path)
        return None

    def get_dbsnp_db_path(self) -> Optional[Path]:
        """Get Path object for dbSNP database."""
        if self.dbsnp_db_path:
            return Path(self.dbsnp_db_path)
        return None


# Global instance
database_config = DatabaseConfig.from_env()

