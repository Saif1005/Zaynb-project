"""VCF parser module for parsing and filtering genomic variants.

Métriques alignées sur docs/METRIQUES_DETECTION_CANCER_SEIN.md pour la détection
du cancer du sein à partir de fichiers VCF.
"""

import gzip
import json
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from collections import defaultdict
from loguru import logger
try:
    import pyvcf3
except ImportError:
    # PyVCF3 s'importe parfois comme 'vcf'
    import vcf as pyvcf3

from src.utils.validators import validate_vcf_file, ValidationError
from src.database.cancer_genes_db import get_cancer_genes_db

# ---------------------------------------------------------------------------
# Constantes des métriques (docs/METRIQUES_DETECTION_CANCER_SEIN.md)
# ---------------------------------------------------------------------------

# Seuils qualité standard (production)
MIN_QUALITY_STANDARD = 20.0
MIN_VAF_STANDARD = 0.05
MIN_DEPTH_STANDARD = 10

# Seuils sensibles (analyse subclonale / variants rares)
MIN_QUALITY_SENSITIVE = 10.0
MIN_VAF_SENSITIVE = 0.01
MIN_DEPTH_SENSITIVE = 2

# Fréquence allélique population (AF)
AF_RARE_THRESHOLD = 0.01       # AF < 1% = rare
AF_VERY_RARE_THRESHOLD = 0.001  # AF < 0.1% = très rare

# Score d'impact
IMPACT_HIGH_THRESHOLD = 0.7    # >= 0.7 = impact élevé
IMPACT_MODERATE_THRESHOLD = 0.4  # >= 0.4 = impact modéré

# VAF interprétation (mutation clonale / subclonale)
VAF_CLONAL_MIN = 0.30   # VAF 30-50% = clonal
VAF_CLONAL_MAX = 0.50
VAF_SUBCLONAL_MAX = 0.10  # VAF < 10% = subclonal
VAF_GERMLINE_HET_MIN = 0.45  # Hétérozygote germinal ~50%
VAF_GERMLINE_HET_MAX = 0.55

# Gènes associés au cancer du sein (doc section 1 & 6) — alias ERBB2 = HER2
BREAST_CANCER_GENES = frozenset({"BRCA1", "BRCA2", "TP53", "PIK3CA", "PTEN", "ERBB2", "HER2", "MYC"})

_REQUIRED_GENE_DB_FIELDS = ("symbol", "name", "cancer_types", "pathogenicity")

# Hotspots PIK3CA connus (positions approximatives, doc section 6.2)
PIK3CA_HOTSPOT_POSITIONS = {179218294, 179218311}


class VCFParseError(Exception):
    """Custom exception for VCF parsing errors."""

    pass


def _info_scalar(value: Any) -> str:
    """Extrait une valeur scalaire depuis INFO pyvcf (souvent list/tuple)."""
    if isinstance(value, (list, tuple)) and value:
        return str(value[0])
    return str(value)


def _format_scalar(value: Any) -> Any:
    """Extrait une valeur scalaire depuis FORMAT pyvcf."""
    if isinstance(value, (list, tuple)) and len(value) == 1:
        return value[0]
    return value


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
            af = _format_scalar(self.format_data["AF"])
            if isinstance(af, (list, tuple)) and af:
                af = af[0]
            return float(af)
        if "AD" in self.format_data:
            ad = _format_scalar(self.format_data["AD"])
            if isinstance(ad, str) and "," in ad:
                ref_dp, alt_dp = map(int, ad.split(","))
                total = ref_dp + alt_dp
                if total > 0:
                    return alt_dp / total
            if isinstance(ad, (list, tuple)) and len(ad) >= 2:
                ref_dp, alt_dp = int(ad[0]), int(ad[1])
                total = ref_dp + alt_dp
                if total > 0:
                    return alt_dp / total
        return None

    @property
    def depth(self) -> Optional[int]:
        """Get read depth from format data."""
        if "DP" in self.format_data:
            dp = _format_scalar(self.format_data["DP"])
            return int(dp)
        if "AD" in self.format_data:
            ad = _format_scalar(self.format_data["AD"])
            if isinstance(ad, str) and "," in ad:
                ref_dp, alt_dp = map(int, ad.split(","))
                return ref_dp + alt_dp
            if isinstance(ad, (list, tuple)) and len(ad) >= 2:
                return int(ad[0]) + int(ad[1])
        return None

    @property
    def is_pathogenic(self) -> bool:
        """Pathogène selon ClinVar (CLNSIG) — section 5.1 METRIQUES."""
        if not self.clinvar:
            return False
        c = str(self.clinvar).lower().replace(" ", "_")
        if "benign" in c or "conflicting" in c:
            return False
        return (
            "pathogenic" in c
            or "likely_pathogenic" in c
            or c in ("pathogenic/likely_pathogenic",)
        )

    def get_population_af(self) -> Optional[float]:
        """Fréquence allélique population: gnomAD prioritaire, sinon INFO AF (doc section 3.2)."""
        if self.gnomad_af is not None:
            return self.gnomad_af
        if self.info and "AF" in self.info:
            af = self.info["AF"]
            if isinstance(af, (list, tuple)) and len(af) > 0:
                return float(af[0])
            if isinstance(af, (int, float)):
                return float(af)
        return None

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
        self._validate_cancer_genes_db()
        self._breast_panel_cache: Optional[Dict[str, Dict[str, Any]]] = None

    def _validate_cancer_genes_db(self) -> None:
        """Charge et valide la structure de cancer_genes_db.json à l'initialisation."""
        db_path = self.cancer_genes_db.db_path
        if not db_path.exists():
            raise VCFParseError(f"Cancer genes database not found: {db_path}")
        try:
            with open(db_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except json.JSONDecodeError as e:
            raise VCFParseError(f"Invalid cancer_genes_db.json: {e}") from e
        if not isinstance(raw, dict) or not raw:
            raise VCFParseError("cancer_genes_db.json must be a non-empty object")
        for gene_key, info in raw.items():
            if not isinstance(info, dict):
                raise VCFParseError(f"Gene entry '{gene_key}' must be an object")
            for field in _REQUIRED_GENE_DB_FIELDS:
                if field not in info:
                    raise VCFParseError(
                        f"Gene '{gene_key}' missing required field '{field}'"
                    )
            if not isinstance(info["cancer_types"], list):
                raise VCFParseError(
                    f"Gene '{gene_key}': cancer_types must be a list"
                )
            if not isinstance(info["pathogenicity"], str):
                raise VCFParseError(
                    f"Gene '{gene_key}': pathogenicity must be a string"
                )
        logger.info(
            f"cancer_genes_db validated: {len(raw)} genes from {db_path}"
        )

    def get_breast_cancer_panel(self) -> Dict[str, Dict[str, Any]]:
        """
        Retourne les gènes du panel cancer du sein depuis cancer_genes_db.json.
        Critère : la chaîne 'breast' présente dans cancer_types.
        """
        if self._breast_panel_cache is not None:
            return self._breast_panel_cache
        panel: Dict[str, Dict[str, Any]] = {}
        for gene_key in self.cancer_genes_db.get_all_genes():
            info = self.cancer_genes_db.get_gene_info(gene_key)
            if not info:
                continue
            cancer_types = info.get("cancer_types", [])
            if not any("breast" in str(ct).lower() for ct in cancer_types):
                continue
            panel[gene_key.upper()] = info
            symbol = str(info.get("symbol", gene_key)).upper()
            panel[symbol] = info
        self._breast_panel_cache = panel
        logger.info(
            f"Breast cancer panel: {sorted({info['symbol'] for info in panel.values()})}"
        )
        return panel

    def _resolve_panel_gene(self, gene: Optional[str]) -> Optional[str]:
        """Mappe un symbole VCF (ex. ERBB2) vers une entrée du panel."""
        if not gene:
            return None
        panel = self.get_breast_cancer_panel()
        upper = gene.upper()
        if upper in panel:
            return str(panel[upper].get("symbol", upper)).upper()
        return None

    def _infer_gene_from_coordinates(self, chromosome: str, position: int) -> Optional[str]:
        """Attribue un gène du panel si la position tombe dans l'intervalle du JSON."""
        chrom = str(chromosome)
        if not chrom.startswith("chr"):
            chrom = f"chr{chrom.lstrip('chr')}"
        for gene_key in self.cancer_genes_db.get_all_genes():
            info = self.cancer_genes_db.get_gene_info(gene_key)
            if not info:
                continue
            gchrom = str(info.get("chromosome", ""))
            if not gchrom.startswith("chr"):
                gchrom = f"chr{gchrom.lstrip('chr')}"
            if gchrom != chrom:
                continue
            start = info.get("start_position")
            end = info.get("end_position")
            if start is None or end is None:
                continue
            if int(start) <= position <= int(end):
                return str(info.get("symbol", gene_key)).upper()
        return None

    def intersect_breast_panel_pathogenic_variants(
        self, variants: Optional[List[Variant]] = None
    ) -> Tuple[List[Variant], List[str]]:
        """
        Variants pathogènes (ClinVar CLNSIG) intersectés avec le panel cancer du sein.
        Gène : annotation VCF (GENE/CSQ) ou position dans cancer_genes_db.json.
        """
        if variants is None:
            variants = self.parse()
        panel = self.get_breast_cancer_panel()

        matched: List[Variant] = []
        identified: Set[str] = set()
        for variant in variants:
            if not variant.is_pathogenic:
                continue
            gene = variant.gene
            if not gene:
                gene = self._infer_gene_from_coordinates(
                    variant.chromosome, variant.position
                )
                if gene:
                    variant.gene = gene
            resolved = self._resolve_panel_gene(gene)
            if resolved is None:
                continue
            gene_info = panel.get(resolved) or panel.get(resolved.upper())
            if not gene_info:
                continue
            matched.append(variant)
            identified.add(resolved)
        genes_sorted = sorted(identified)
        logger.info(
            f"Breast panel pathogenic intersection: {len(matched)} variants, "
            f"genes={genes_sorted}"
        )
        return matched, genes_sorted

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
                csq = _info_scalar(info_dict["CSQ"])
                if isinstance(csq, str):
                    parts = csq.split("|")
                    if len(parts) > 2:
                        consequence = parts[1] if parts[1] else None
                        gene = parts[2] if parts[2] else None

            # Parse GENE direct (VCF simplifié / test)
            if not gene and "GENE" in info_dict:
                gene = _info_scalar(info_dict["GENE"]).split(",")[0].strip()

            # Parse ClinVar if present
            if "CLNSIG" in info_dict:
                clinvar = _info_scalar(info_dict["CLNSIG"])

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

            if not variant.gene:
                inferred = self._infer_gene_from_coordinates(chromosome, position)
                if inferred:
                    variant.gene = inferred

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

    def _is_rare(self, variant: Variant) -> bool:
        """Variant rare si AF < 1% ou non présent en base (doc section 3.2)."""
        af = variant.get_population_af()
        return af is None or af < AF_RARE_THRESHOLD

    def _is_hotspot(self, variant: Variant) -> bool:
        """Hotspot COSMIC / région récurrente (doc section 5.3)."""
        if not variant.info:
            return False
        if "HOTSPOT" in variant.info or "COSMIC" in variant.info:
            return True
        if any("hotspot" in str(k).lower() for k in variant.info.keys()):
            return True
        # PIK3CA positions connues
        if variant.gene and variant.gene.upper() == "PIK3CA" and variant.position in PIK3CA_HOTSPOT_POSITIONS:
            return True
        return False

    def _calculate_impact_score(self, variant: Variant) -> float:
        """
        Score d'impact 0.0–1.0 selon doc section 4.1.
        Plus le score est élevé, plus le variant est susceptible d'être pathogène.
        """
        score = 0.0
        if variant.is_pathogenic:
            score += 0.5
        vaf = variant.vaf
        if vaf is not None:
            if vaf > 0.3:
                score += 0.2
            elif vaf < 0.1:
                score += 0.1
        af = variant.get_population_af()
        if af is not None and af < AF_VERY_RARE_THRESHOLD:
            score += 0.2
        elif af is None:
            score += 0.1
        if variant.consequence:
            c = variant.consequence.lower()
            if "frameshift" in c or "stop" in c:
                score += 0.3
            elif "missense" in c:
                score += 0.1
            elif "synonymous" in c:
                score -= 0.2
        if variant.gene and self.cancer_genes_db and self.cancer_genes_db.is_cancer_gene(variant.gene):
            score += 0.2
        return min(1.0, max(0.0, score))

    def _is_breast_cancer_gene(self, gene: Optional[str]) -> bool:
        """Indique si le gène appartient au panel cancer du sein (cancer_genes_db)."""
        return self._resolve_panel_gene(gene) is not None

    def _calculate_breast_cancer_score(self, variant: Variant) -> float:
        """
        Score de risque cancer du sein 0.0–1.0 (doc section 6.3).
        """
        score = 0.0
        gene = (variant.gene or "").upper()
        vaf = variant.vaf
        if gene in ("BRCA1", "BRCA2") and variant.is_pathogenic:
            score += 0.6
        elif gene == "TP53" and variant.is_pathogenic:
            score += 0.4
        elif gene == "PIK3CA" and vaf is not None and 0.1 < vaf < 0.6:
            score += 0.3
        elif gene in ("PTEN", "ERBB2", "MYC") and variant.is_pathogenic:
            score += 0.2
        return min(1.0, score)

    def get_enriched_variant_metrics(self, variant: Variant) -> Dict[str, Any]:
        """
        Retourne un dictionnaire des métriques par variant (aligné doc sections 4–7).
        Utilisable pour rapports et entraînement LLM.
        """
        impact_score = self._calculate_impact_score(variant)
        af = variant.get_population_af()
        is_rare = af is None or af < AF_RARE_THRESHOLD
        is_high_impact = impact_score >= IMPACT_HIGH_THRESHOLD or variant.is_pathogenic
        is_cancer_gene = variant.gene is not None and self.cancer_genes_db.is_cancer_gene(variant.gene)
        breast_cancer_score = self._calculate_breast_cancer_score(variant)
        return {
            "chromosome": variant.chromosome,
            "position": variant.position,
            "ref": variant.ref,
            "alt": variant.alt,
            "gene": variant.gene,
            "consequence": variant.consequence,
            "vaf": round(variant.vaf, 4) if variant.vaf is not None else None,
            "af": round(af, 6) if af is not None else None,
            "depth": variant.depth,
            "quality": variant.quality,
            "clinvar": variant.clinvar,
            "is_pathogenic": variant.is_pathogenic,
            "is_rare": is_rare,
            "is_high_impact": is_high_impact,
            "is_hotspot": self._is_hotspot(variant),
            "is_cancer_gene": is_cancer_gene,
            "is_breast_cancer_gene": self._is_breast_cancer_gene(variant.gene),
            "impact_score": round(impact_score, 3),
            "breast_cancer_score": round(breast_cancer_score, 3),
        }

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

    def get_breast_cancer_variants(
        self, variants: Optional[List[Variant]] = None
    ) -> List[Variant]:
        """Variants patient intersectés avec le panel sein (pathogenicity JSON)."""
        matched, _ = self.intersect_breast_panel_pathogenic_variants(variants)
        return matched

    def is_breast_cancer_detected(
        self, variants: Optional[List[Variant]] = None
    ) -> bool:
        """True si au moins un gène pathogène du panel sein est altéré."""
        _, genes = self.intersect_breast_panel_pathogenic_variants(variants)
        return len(genes) > 0

    def get_variant_summary(
        self, variants: Optional[List[Variant]] = None
    ) -> Dict[str, Any]:
        """
        Statistiques agrégées (doc section 7.1).
        Inclut les compteurs pour détection cancer du sein.
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

        # Métriques doc section 7.1
        high_impact_count = sum(
            1
            for v in variants
            if self._calculate_impact_score(v) >= IMPACT_HIGH_THRESHOLD or v.is_pathogenic
        )
        rare_variant_count = sum(1 for v in variants if self._is_rare(v))
        cancer_gene_count = in_cancer_genes
        pathogenic_count = pathogenic
        breast_cancer_variants = self.get_breast_cancer_variants(variants)
        _, identified_breast_genes = self.intersect_breast_panel_pathogenic_variants(
            variants
        )
        breast_cancer_detected = len(identified_breast_genes) > 0

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
            "high_impact_count": high_impact_count,
            "rare_variant_count": rare_variant_count,
            "cancer_gene_count": cancer_gene_count,
            "pathogenic_count": pathogenic_count,
            "breast_cancer_variant_count": len(breast_cancer_variants),
            "breast_cancer_detected": breast_cancer_detected,
            "identified_pathogenic_genes": identified_breast_genes,
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

    def export_metrics_json(
        self,
        variants: Optional[List[Variant]] = None,
        coverage: Optional[float] = None,
        patient_id: Optional[str] = None,
        output_path: Optional[str] = None,
        include_all_variants: bool = False,
    ) -> Dict[str, Any]:
        """
        Export des métriques VCF au format JSON pour le bioLLM (entraînement + prédiction).        Conforme à docs/METRIQUES_DETECTION_CANCER_SEIN.md. Ce JSON est l'output canonique
        du pipeline GATK/VCF : métadonnées patient, résumé, liste de variants avec métriques
        (impact_score, breast_cancer_score, etc.). Consommé par l'orchestrateur et le modèle bioLLM.

        Args:
            variants: Liste de variants (si None, parse le VCF).
            coverage: Profondeur moyenne (si None, calculée depuis les variants).
            patient_id: Identifiant patient.
            output_path: Si fourni, écrit le JSON dans ce fichier.
            include_all_variants: Si False, n'inclut que les variants pathogènes/cancer.
                Si True, inclut tous les variants parsés (avec métriques).

        Returns:
            Dictionnaire avec metadata (section 7), summary, variants (enriched metrics).
        """
        if variants is None:
            variants = self.parse()
        if coverage is None and variants:
            depths = [v.depth for v in variants if v.depth is not None]
            coverage = sum(depths) / len(depths) if depths else 30.0
        elif coverage is None:
            coverage = 30.0

        summary = self.get_variant_summary(variants)
        metadata = {
            "patient_id": patient_id,
            "coverage": round(float(coverage), 2),
            "variant_count": summary["total_variants"],
            "high_impact_count": summary["high_impact_count"],
            "rare_variant_count": summary["rare_variant_count"],
            "cancer_gene_count": summary["cancer_gene_count"],
            "pathogenic_count": summary["pathogenic_count"],
            "breast_cancer_detected": summary["breast_cancer_detected"],
        }

        if include_all_variants:
            variants_to_export = variants
        else:
            variants_to_export, _ = self.intersect_breast_panel_pathogenic_variants(
                variants
            )
            if not variants_to_export:
                variants_to_export = self.get_pathogenic_cancer_variants(variants)[:100]
        variants_json = [
            self.get_enriched_variant_metrics(v)
            for v in variants_to_export
        ]

        payload = {
            "metadata": metadata,
            "summary": summary,
            "variants": variants_json,
        }

        if output_path:
            import json
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"Metrics JSON written: {output_path}")

        return payload