"""VCF Analysis Agent - Analyzes variants from VCF file."""

from typing import Dict, Any, Optional
from pathlib import Path
from loguru import logger

from src.agents.base_agent import BaseAgent, AgentResult, AgentStatus
from src.preprocessing.vcf_parser import VCFParser
from src.aws.s3_manager import get_s3_manager
from config.aws_config import aws_config


class VCFAnalysisAgent(BaseAgent):
    """Agent for analyzing VCF files and extracting variants."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize VCF Analysis Agent."""
        super().__init__("VCFAnalysis", config)
        self.s3_manager = get_s3_manager()

    def validate_input(self, context: Dict[str, Any]) -> bool:
        """Validate input context."""
        if "vcf_s3" not in context:
            self.logger.error("Missing vcf_s3 in context")
            return False
        return True

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        """
        Analyze VCF file and extract pathogenic cancer variants.

        Args:
            context: Context with VCF S3 path

        Returns:
            AgentResult with analyzed variants
        """
        patient_id = context.get("patient_id")
        vcf_s3 = context.get("vcf_s3")
        
        try:
            # Download VCF from S3
            self.logger.info(f"Downloading VCF from {vcf_s3}...")
            vcf_local = f"./work/{patient_id}/variants.vcf.gz"
            Path(vcf_local).parent.mkdir(parents=True, exist_ok=True)
            
            s3_path = vcf_s3.replace("s3://", "")
            parts = s3_path.split("/", 1)
            bucket = parts[0]
            key = parts[1] if len(parts) > 1 else ""
            
            self.s3_manager.download_file(
                s3_key=key,
                local_path=vcf_local,
                bucket_name=bucket,
            )
            self.logger.info(f"✓ VCF downloaded: {vcf_local}")
            
            # Parse VCF
            self.logger.info("Parsing VCF file...")
            # Relâcher les filtres pour accepter plus de variants (comme dans analyze_vcf_local.py)
            # Les variants GATK ont souvent FILTER=. (pas PASS) et DP faible
            vcf_parser = VCFParser(
                vcf_local,
                min_quality=10.0,      # Au lieu de 20.0 (QUAL)
                min_vaf=0.01,         # Au lieu de 0.05 (1% au lieu de 5%)
                min_depth=2,          # Au lieu de 10 (accepter DP=2,3,4)
                require_pass=False,   # Accepter aussi FILTER=. (pas seulement PASS)
            )
            variants = vcf_parser.parse()
            self.logger.info(f"Total variants found: {len(variants)}")
            
            # Get pathogenic cancer variants
            pathogenic_cancer = vcf_parser.get_pathogenic_cancer_variants(variants)
            self.logger.info(f"Pathogenic cancer variants: {len(pathogenic_cancer)}")
            
            # Get variant summary
            summary = vcf_parser.get_variant_summary(variants)
            
            # Convert to enriched dict format with all metrics
            variants_dict = []
            for variant in pathogenic_cancer:
                # Determine variant type
                variant_type = "SNV" if len(variant.ref) == 1 and len(variant.alt) == 1 else \
                              "Deletion" if len(variant.ref) > len(variant.alt) else \
                              "Insertion" if len(variant.alt) > len(variant.ref) else "Complex"
                
                # Get allele frequency
                af = variant.gnomad_af
                if af is None and variant.info and "AF" in variant.info:
                    af_val = variant.info["AF"]
                    if isinstance(af_val, (list, tuple)) and len(af_val) > 0:
                        af = float(af_val[0])
                    elif isinstance(af_val, (int, float)):
                        af = float(af_val)
                
                # Check if rare
                is_rare = af is None or af < 0.01
                
                # Check if in cancer gene
                is_cancer_gene = variant.gene and vcf_parser.cancer_genes_db.is_cancer_gene(variant.gene)
                
                # Check if hotspot
                is_hotspot = False
                if variant.info:
                    is_hotspot = "HOTSPOT" in variant.info or "COSMIC" in variant.info or \
                                 any("hotspot" in str(k).lower() for k in variant.info.keys())
                
                # Calculate impact score (simplified)
                impact_score = 0.0
                if variant.is_pathogenic:
                    impact_score += 0.5
                if variant.vaf and variant.vaf > 0.3:
                    impact_score += 0.2
                if is_rare:
                    impact_score += 0.2
                if variant.consequence:
                    cons_lower = variant.consequence.lower()
                    if "frameshift" in cons_lower or "stop" in cons_lower:
                        impact_score += 0.3
                    elif "missense" in cons_lower:
                        impact_score += 0.1
                if is_cancer_gene:
                    impact_score += 0.2
                impact_score = min(1.0, impact_score)
                
                is_high_impact = impact_score >= 0.7 or variant.is_pathogenic
                
                variants_dict.append({
                    "gene": variant.gene or "Unknown",
                    "ref": variant.ref,
                    "alt": variant.alt,
                    "chromosome": variant.chromosome,
                    "position": variant.position,
                    "consequence": variant.consequence or "Unknown",
                    "clinvar": variant.clinvar or "Not reported",
                    "vaf": round(variant.vaf, 4) if variant.vaf is not None else None,
                    "af": round(af, 6) if af is not None else None,
                    "dp": variant.depth,
                    "quality": variant.quality,
                    "variant_type": variant_type,
                    "hotspot": is_hotspot,
                    "impact_score": round(impact_score, 3),
                    "is_pathogenic": variant.is_pathogenic,
                    "is_rare": is_rare,
                    "is_high_impact": is_high_impact,
                    "is_cancer_gene": is_cancer_gene,
                })
            
            # Calculate average coverage
            coverage = sum(v.depth for v in variants if v.depth) / len(variants) if variants else 30.0
            
            return AgentResult(
                success=True,
                status=AgentStatus.COMPLETED,
                data={
                    "vcf_local_path": vcf_local,
                    "total_variants": len(variants),
                    "pathogenic_cancer_variants": len(pathogenic_cancer),
                    "variants": variants_dict,
                    "summary": summary,
                    "coverage": coverage,
                    "patient_id": patient_id,
                }
            )

        except Exception as e:
            error_msg = f"VCF Analysis failed: {e}"
            self.logger.error(error_msg)
            return AgentResult(
                success=False,
                status=AgentStatus.FAILED,
                error=error_msg
            )



