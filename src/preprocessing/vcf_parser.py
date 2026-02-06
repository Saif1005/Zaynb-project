"""VCF parser module for parsing and filtering genomic variants."""

import gzip
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from collections import defaultdict
from loguru import logger
try:
    import pyvcf3
except ImportError:
    # PyVCF3 s'importe parfois comme 'vcf'
    import vcf as pyvcf3

from src.utils.validators import validate_vcf_file, ValidationError
from src.database.cancer_genes_db import get_cancer_genes_db


class VCFParseError(Exception):
    """Custom exception for VCF parsing errors."""

    pass


class Variant:
    """Represents a genomic variant from VCF."""

    def __init__(
        self,
        chromosome: str,
        position: int,
        ref: str,
        alt: str,
        quality: Optional[float] = None,
        filter_status: Optional[str] = None,
        info: Optional[Dict] = None,
        format_data: Optional[Dict] = None,
        gene: Optional[str] = None,
        consequence: Optional[str] = None,
        clinvar: Optional[str] = None,
        gnomad_af: Optional[float] = None,
    ):
        """
        Initialize variant.

        Args:
            chromosome: Chromosome
            position: Genomic position (1-based)
            ref: Reference allele
            alt: Alternate allele
            quality: Quality score
            filter_status: FILTER field value
            info: INFO field as dictionary
            format_data: FORMAT field data
            gene: Gene symbol (from annotation)
            consequence: Variant consequence (from annotation)
            clinvar: ClinVar significance
            gnomad_af: gnomAD allele frequency
        """
        self.chromosome = chromosome
        self.position = position
        self.ref = ref
        self.alt = alt
        self.quality = quality
        self.filter_status = filter_status
        self.info = info or {}
        self.format_data = format_data or {}
        self.gene = gene
        self.consequence = consequence
        self.clinvar = clinvar
        self.gnomad_af = gnomad_af

    @property
    def vaf(self) -> Optional[float]:
        """Get variant allele frequency from format data."""
        if "AF" in self.format_data:
            return float(self.format_data["AF"])
        if "AD" in self.format_data:
            # AD is "ref_depth,alt_depth"
            ad = self.format_data["AD"]
            if isinstance(ad, str) and "," in ad:
                ref_dp, alt_dp = map(int, ad.split(","))
                total = ref_dp + alt_dp
                if total > 0:
                    return alt_dp / total
        return None

    @property
    def depth(self) -> Optional[int]:
        """Get read depth from format data."""
        if "DP" in self.format_data:
            return int(self.format_data["DP"])
        if "AD" in self.format_data:
            ad = self.format_data["AD"]
            if isinstance(ad, str) and "," in ad:
                ref_dp, alt_dp = map(int, ad.split(","))
                return ref_dp + alt_dp
        return None

    @property
    def is_pathogenic(self) -> bool:
        """Check if variant is pathogenic based on ClinVar."""
        if not self.clinvar:
            return False
        pathogenic_terms = [
            "pathogenic",
            "likely_pathogenic",
            "pathogenic/likely_pathogenic",
        ]
        return self.clinvar.lower() in pathogenic_terms

    def __repr__(self) -> str:
        """String representation of variant."""
        return (
            f"Variant({self.chromosome}:{self.position} "
            f"{self.ref}>{self.alt}, gene={self.gene}, "
            f"clinvar={self.clinvar})"
        )


class VCFParser:
    """Parser for VCF files with variant filtering and annotation."""

    def __init__(
        self,
        vcf_path: str,
        min_quality: float = 20.0,
        min_vaf: float = 0.05,
        min_depth: int = 10,
        require_pass: bool = True,
    ):
        """
        Initialize VCF parser.

        Args:
            vcf_path: Path to VCF file
            min_quality: Minimum QUAL score
            min_vaf: Minimum variant allele frequency
            min_depth: Minimum read depth
            require_pass: Only include variants with FILTER=PASS
        """
        validate_vcf_file(vcf_path)
        self.vcf_path = Path(vcf_path)
        self.min_quality = min_quality
        self.min_vaf = min_vaf
        self.min_depth = min_depth
        self.require_pass = require_pass
        self.cancer_genes_db = get_cancer_genes_db()

    def parse(self) -> List[Variant]:
        """
        Parse VCF file and return list of variants.

        Returns:
            List of Variant objects

        Raises:
            VCFParseError: If parsing fails
        """
        logger.info(f"Parsing VCF file: {self.vcf_path}")

        variants = []
        try:
            # Open VCF file (handle gzip)
            # pyvcf3 needs the file path directly, it handles gzip internally
            vcf_file_path = str(self.vcf_path)
            
            # For gzip files, pyvcf3 should handle it, but we need to pass the path
            # If it's a Path object, convert to string
            if isinstance(self.vcf_path, Path):
                vcf_file_path = str(self.vcf_path.resolve())
            
            vcf_reader = pyvcf3.Reader(filename=vcf_file_path)

            for record in vcf_reader:
                variant = self._parse_record(record)
                if variant and self._passes_filters(variant):
                    variants.append(variant)

            logger.info(f"Parsed {len(variants)} variants from VCF")
            return variants

        except Exception as e:
            logger.error(f"Failed to parse VCF file: {e}")
            raise VCFParseError(f"VCF parsing failed: {e}") from e

    def _parse_record(self, record) -> Optional[Variant]:
        """
        Parse a single VCF record into Variant object.

        Args:
            record: pyvcf3 Record object

        Returns:
            Variant object or None if parsing fails
        """
        try:
            # Extract basic information
            chromosome = record.CHROM
            position = record.POS
            ref = record.REF
            alt = str(record.ALT[0]) if record.ALT else ""

            # Extract INFO fields
            info_dict = {}
            if hasattr(record, "INFO"):
                for key, value in record.INFO.items():
                    info_dict[key] = value

            # Extract FORMAT fields (from first sample)
            format_dict = {}
            if record.samples:
                sample = record.samples[0]
                for key in record.FORMAT.split(":"):
                    if hasattr(sample, key):
                        format_dict[key] = getattr(sample, key)

            # Extract annotation from INFO (VEP format)
            gene = None
            consequence = None
            clinvar = None
            gnomad_af = None

            # Parse CSQ (VEP consequence) if present
            if "CSQ" in info_dict:
                csq = info_dict["CSQ"]
                if isinstance(csq, str):
                    # CSQ format: Allele|Consequence|Gene|...
                    parts = csq.split("|")
                    if len(parts) > 2:
                        consequence = parts[1] if parts[1] else None
                        gene = parts[2] if parts[2] else None

            # Parse ClinVar if present
            if "CLNSIG" in info_dict:
                clinvar = str(info_dict["CLNSIG"])

            # Parse gnomAD AF if present
            if "gnomAD_AF" in info_dict:
                gnomad_af = float(info_dict["gnomAD_AF"])
            elif "AF" in info_dict:
                af = info_dict["AF"]
                if isinstance(af, (list, tuple)) and len(af) > 0:
                    gnomad_af = float(af[0])
                elif isinstance(af, (int, float)):
                    gnomad_af = float(af)

            variant = Variant(
                chromosome=chromosome,
                position=position,
                ref=ref,
                alt=alt,
                quality=float(record.QUAL) if record.QUAL else None,
                filter_status=record.FILTER if record.FILTER else None,
                info=info_dict,
                format_data=format_dict,
                gene=gene,
                consequence=consequence,
                clinvar=clinvar,
                gnomad_af=gnomad_af,
            )

            return variant

        except Exception as e:
            logger.warning(f"Failed to parse VCF record: {e}")
            return None

    def _passes_filters(self, variant: Variant) -> bool:
        """
        Check if variant passes quality filters.

        Args:
            variant: Variant object

        Returns:
            True if variant passes all filters
        """
        # Filter by PASS status
        if self.require_pass and variant.filter_status != "PASS":
            return False

        # Filter by quality
        if variant.quality is not None and variant.quality < self.min_quality:
            return False

        # Filter by depth
        depth = variant.depth
        if depth is not None and depth < self.min_depth:
            return False

        # Filter by VAF
        vaf = variant.vaf
        if vaf is not None and vaf < self.min_vaf:
            return False

        return True

    def get_pathogenic_variants(
        self, variants: Optional[List[Variant]] = None
    ) -> List[Variant]:
        """
        Filter variants to only pathogenic ones.

        Args:
            variants: Optional list of variants (if None, parses VCF)

        Returns:
            List of pathogenic variants
        """
        if variants is None:
            variants = self.parse()

        pathogenic = [v for v in variants if v.is_pathogenic]
        logger.info(f"Found {len(pathogenic)} pathogenic variants")
        return pathogenic

    def get_cancer_gene_variants(
        self, variants: Optional[List[Variant]] = None
    ) -> List[Variant]:
        """
        Filter variants to only those in cancer genes.

        Args:
            variants: Optional list of variants (if None, parses VCF)

        Returns:
            List of variants in cancer genes
        """
        if variants is None:
            variants = self.parse()

        cancer_genes = set(self.cancer_genes_db.get_all_genes())
        cancer_variants = [
            v for v in variants if v.gene and v.gene.upper() in cancer_genes
        ]

        logger.info(
            f"Found {len(cancer_variants)} variants in cancer genes"
        )
        return cancer_variants

    def get_pathogenic_cancer_variants(
        self, variants: Optional[List[Variant]] = None
    ) -> List[Variant]:
        """
        Get variants that are both pathogenic and in cancer genes.

        Args:
            variants: Optional list of variants (if None, parses VCF)

        Returns:
            List of pathogenic variants in cancer genes
        """
        if variants is None:
            variants = self.parse()

        pathogenic_cancer = [
            v
            for v in variants
            if v.is_pathogenic
            and v.gene
            and self.cancer_genes_db.is_cancer_gene(v.gene)
        ]

        logger.info(
            f"Found {len(pathogenic_cancer)} pathogenic variants in cancer genes"
        )
        return pathogenic_cancer

    def get_variant_summary(
        self, variants: Optional[List[Variant]] = None
    ) -> Dict:
        """
        Generate summary statistics for variants.

        Args:
            variants: Optional list of variants (if None, parses VCF)

        Returns:
            Dictionary with summary statistics
        """
        if variants is None:
            variants = self.parse()

        total = len(variants)
        pathogenic = sum(1 for v in variants if v.is_pathogenic)
        in_cancer_genes = sum(
            1
            for v in variants
            if v.gene and self.cancer_genes_db.is_cancer_gene(v.gene)
        )
        pathogenic_cancer = sum(
            1
            for v in variants
            if v.is_pathogenic
            and v.gene
            and self.cancer_genes_db.is_cancer_gene(v.gene)
        )

        # Count by gene
        gene_counts = defaultdict(int)
        for v in variants:
            if v.gene:
                gene_counts[v.gene] += 1

        # Count by consequence
        consequence_counts = defaultdict(int)
        for v in variants:
            if v.consequence:
                consequence_counts[v.consequence] += 1

        summary = {
            "total_variants": total,
            "pathogenic_variants": pathogenic,
            "variants_in_cancer_genes": in_cancer_genes,
            "pathogenic_cancer_variants": pathogenic_cancer,
            "genes_affected": len(gene_counts),
            "top_genes": dict(
                sorted(gene_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
            "top_consequences": dict(
                sorted(
                    consequence_counts.items(),
                    key=lambda x: x[1],
                    reverse=True,
                )[:10]
            ),
        }

        return summary

