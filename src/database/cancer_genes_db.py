"""Cancer genes database module for accessing cancer gene information."""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Set
from loguru import logger
from config.aws_config import aws_config


class CancerGenesDB:
    """Database for cancer gene information and clinical significance."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize cancer genes database.

        Args:
            db_path: Optional path to cancer genes JSON file.
                    Defaults to data/cancer_genes/cancer_genes_db.json
        """
        if db_path is None:
            # Default path relative to project root
            default_path = os.getenv(
                "CANCER_GENES_DB_PATH",
                "./data/cancer_genes/cancer_genes_db.json",
            )
            db_path = default_path

        self.db_path = Path(db_path)
        self._genes: Dict[str, Dict] = {}
        self._load_database()

    def _load_database(self) -> None:
        """Load cancer genes database from JSON file."""
        if not self.db_path.exists():
            raise FileNotFoundError(
                f"Cancer genes database not found: {self.db_path}"
            )

        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                self._genes = json.load(f)
            logger.info(
                f"Loaded {len(self._genes)} cancer genes from {self.db_path}"
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse cancer genes database: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load cancer genes database: {e}")
            raise

    def get_gene_info(self, gene_symbol: str) -> Optional[Dict]:
        """
        Get information for a specific gene.

        Args:
            gene_symbol: Gene symbol (e.g., "BRCA1", "TP53")

        Returns:
            Dictionary with gene information or None if not found
        """
        gene_info = self._genes.get(gene_symbol.upper())
        if gene_info:
            logger.debug(f"Retrieved info for gene: {gene_symbol}")
        else:
            logger.warning(f"Gene not found in database: {gene_symbol}")
        return gene_info

    def is_cancer_gene(self, gene_symbol: str) -> bool:
        """
        Check if a gene is in the cancer genes database.

        Args:
            gene_symbol: Gene symbol to check

        Returns:
            True if gene is in database, False otherwise
        """
        return gene_symbol.upper() in self._genes

    def get_cancer_types(self, gene_symbol: str) -> List[str]:
        """
        Get list of cancer types associated with a gene.

        Args:
            gene_symbol: Gene symbol

        Returns:
            List of cancer types (empty list if gene not found)
        """
        gene_info = self.get_gene_info(gene_symbol)
        if gene_info:
            return gene_info.get("cancer_types", [])
        return []

    def get_genes_by_cancer_type(self, cancer_type: str) -> List[str]:
        """
        Get all genes associated with a specific cancer type.

        Args:
            cancer_type: Cancer type (e.g., "breast", "ovarian")

        Returns:
            List of gene symbols
        """
        cancer_type_lower = cancer_type.lower()
        matching_genes = []

        for gene_symbol, gene_info in self._genes.items():
            cancer_types = [
                ct.lower() for ct in gene_info.get("cancer_types", [])
            ]
            if cancer_type_lower in cancer_types:
                matching_genes.append(gene_symbol)

        logger.debug(
            f"Found {len(matching_genes)} genes for cancer type: {cancer_type}"
        )
        return matching_genes

    def get_high_risk_genes(self) -> List[str]:
        """
        Get all high/very high clinical significance genes.

        Returns:
            List of gene symbols with high clinical significance
        """
        high_risk_genes = []

        for gene_symbol, gene_info in self._genes.items():
            significance = gene_info.get("clinical_significance", "").lower()
            if significance in ("high", "very_high"):
                high_risk_genes.append(gene_symbol)

        return high_risk_genes

    def get_all_genes(self) -> List[str]:
        """
        Get all gene symbols in the database.

        Returns:
            List of all gene symbols
        """
        return list(self._genes.keys())

    def get_penetrance(self, gene_symbol: str) -> Optional[float]:
        """
        Get penetrance value for a gene.

        Args:
            gene_symbol: Gene symbol

        Returns:
            Penetrance value (0.0-1.0) or None if gene not found
        """
        gene_info = self.get_gene_info(gene_symbol)
        if gene_info:
            return gene_info.get("penetrance")
        return None

    def get_screening_recommendations(
        self, gene_symbol: str
    ) -> List[str]:
        """
        Get screening recommendations for a gene.

        Args:
            gene_symbol: Gene symbol

        Returns:
            List of screening recommendations
        """
        gene_info = self.get_gene_info(gene_symbol)
        if gene_info:
            return gene_info.get("screening_recommendations", [])
        return []

    def get_chromosomal_location(self, gene_symbol: str) -> Optional[Dict]:
        """
        Get chromosomal location for a gene.

        Args:
            gene_symbol: Gene symbol

        Returns:
            Dictionary with chromosome, start, end or None
        """
        gene_info = self.get_gene_info(gene_symbol)
        if gene_info:
            return {
                "chromosome": gene_info.get("chromosome"),
                "start": gene_info.get("start_position"),
                "end": gene_info.get("end_position"),
            }
        return None

    def get_genes_in_region(
        self, chromosome: str, start: int, end: int
    ) -> List[str]:
        """
        Get all cancer genes in a genomic region.

        Args:
            chromosome: Chromosome (e.g., "chr17")
            end: End position (1-based)
            start: Start position (1-based)

        Returns:
            List of gene symbols overlapping the region
        """
        matching_genes = []
        chrom_normalized = chromosome if chromosome.startswith("chr") else f"chr{chromosome}"

        for gene_symbol, gene_info in self._genes.items():
            gene_chrom = gene_info.get("chromosome", "")
            gene_start = gene_info.get("start_position")
            gene_end = gene_info.get("end_position")

            if (
                gene_chrom == chrom_normalized
                and gene_start is not None
                and gene_end is not None
            ):
                # Check for overlap
                if not (end < gene_start or start > gene_end):
                    matching_genes.append(gene_symbol)

        logger.debug(
            f"Found {len(matching_genes)} genes in region "
            f"{chrom_normalized}:{start}-{end}"
        )
        return matching_genes


# Global instance
_cancer_genes_db: Optional[CancerGenesDB] = None


def get_cancer_genes_db() -> CancerGenesDB:
    """
    Get global cancer genes database instance.

    Returns:
        CancerGenesDB instance
    """
    global _cancer_genes_db
    if _cancer_genes_db is None:
        _cancer_genes_db = CancerGenesDB()
    return _cancer_genes_db

