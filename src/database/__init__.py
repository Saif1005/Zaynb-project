"""Database modules for cancer genes and clinical data."""

from src.database.cancer_genes_db import (
    CancerGenesDB,
    get_cancer_genes_db,
)

__all__ = [
    "CancerGenesDB",
    "get_cancer_genes_db",
]

