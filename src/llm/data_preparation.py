"""Training data preparation for LLM fine-tuning."""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from loguru import logger

# Import Variant class if available
try:
    from src.preprocessing.vcf_parser import Variant
    from src.database.cancer_genes_db import get_cancer_genes_db
except ImportError:
    Variant = None


class TrainingDataPreparationError(Exception):
    """Error in training data preparation."""

    pass


class TrainingDataPreparation:
    """Prepare training data for LLM fine-tuning."""

    def __init__(self):
        """Initialize training data preparation."""
        self.logger = logger
        try:
            self.cancer_genes_db = get_cancer_genes_db()
        except Exception:
            self.cancer_genes_db = None

    def prepare_from_vcf_analysis(
        self,
        patient_id: str,
        variants: Union[List[Dict], List[Variant]],
        coverage: float,
        analysis_result: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Prepare training example from VCF analysis.

        Args:
            patient_id: Patient identifier
            variants: List of variant dictionaries or Variant objects
            coverage: Sequencing coverage
            analysis_result: Optional analysis result dictionary

        Returns:
            Training example dictionary in chat format
        """
        from src.llm.prompt_templates import GenomicPromptTemplates

        # Convert Variant objects to enriched dictionaries if needed
        if variants and isinstance(variants[0], Variant):
            variant_dicts = [self._variant_to_dict(v) for v in variants]
        else:
            variant_dicts = variants

        # Calculate patient-level metrics
        patient_metrics = self._calculate_patient_metrics(variant_dicts, coverage)

        # Format user prompt with enriched variant data
        user_prompt = GenomicPromptTemplates.format_user_prompt(
            patient_id=patient_id,
            variants=variant_dicts,
            coverage=coverage,
        )

        # Create system message
        system_message = {
            "role": "system",
            "content": GenomicPromptTemplates.SYSTEM_PROMPT,
        }

        # Create user message
        user_message = {
            "role": "user",
            "content": user_prompt,
        }

        # Create assistant message (from analysis result or default)
        if analysis_result:
            assistant_content = self._format_analysis_result(analysis_result)
        else:
            assistant_content = self._generate_default_analysis(patient_id, variant_dicts)

        assistant_message = {
            "role": "assistant",
            "content": assistant_content,
        }

        # Create training example with enriched metadata
        training_example = {
            "messages": [system_message, user_message, assistant_message],
            "patient_id": patient_id,
            "metadata": patient_metrics,
        }

        return training_example

    def _variant_to_dict(self, variant: Variant) -> Dict[str, Any]:
        """
        Convert Variant object to enriched dictionary with all metrics.

        Args:
            variant: Variant object

        Returns:
            Dictionary with all variant metrics
        """
        # Determine variant type
        variant_type = self._determine_variant_type(variant.ref, variant.alt)
        
        # Calculate impact score
        impact_score = self._calculate_impact_score(variant)
        
        # Check if hotspot
        is_hotspot = self._is_hotspot(variant)
        
        # Check if in cancer gene
        is_cancer_gene = False
        if self.cancer_genes_db and variant.gene:
            is_cancer_gene = self.cancer_genes_db.is_cancer_gene(variant.gene)
        
        # Get allele frequency (AF) - prefer gnomAD, fallback to INFO AF
        af = variant.gnomad_af
        if af is None and variant.info:
            if "AF" in variant.info:
                af_val = variant.info["AF"]
                if isinstance(af_val, (list, tuple)) and len(af_val) > 0:
                    af = float(af_val[0])
                elif isinstance(af_val, (int, float)):
                    af = float(af_val)
        
        # Get VAF (variant allele frequency)
        vaf = variant.vaf
        
        # Get depth
        dp = variant.depth
        
        # Determine if rare (AF < 0.01 or not in population databases)
        is_rare = af is None or af < 0.01
        
        # Determine if high impact
        is_high_impact = impact_score >= 0.7 or variant.is_pathogenic
        
        variant_dict = {
            "chromosome": variant.chromosome,
            "position": variant.position,
            "ref": variant.ref,
            "alt": variant.alt,
            "gene": variant.gene or "Unknown",
            "variant_type": variant_type,
            "consequence": variant.consequence or "Unknown",
            "vaf": round(vaf, 4) if vaf is not None else None,
            "af": round(af, 6) if af is not None else None,
            "dp": dp,
            "quality": variant.quality,
            "clinvar": variant.clinvar or "Not reported",
            "hotspot": is_hotspot,
            "impact_score": round(impact_score, 3),
            "is_pathogenic": variant.is_pathogenic,
            "is_rare": is_rare,
            "is_high_impact": is_high_impact,
            "is_cancer_gene": is_cancer_gene,
        }
        
        return variant_dict

    def _determine_variant_type(self, ref: str, alt: str) -> str:
        """Determine variant type (SNV, INDEL, etc.)."""
        if len(ref) == 1 and len(alt) == 1:
            return "SNV"
        elif len(ref) > len(alt):
            return "Deletion"
        elif len(alt) > len(ref):
            return "Insertion"
        else:
            return "Complex"

    def _calculate_impact_score(self, variant: Variant) -> float:
        """
        Calculate impact score (0-1) based on variant properties.
        
        Higher score = more likely to be pathogenic/high impact.
        """
        score = 0.0
        
        # Pathogenic ClinVar variants get high score
        if variant.is_pathogenic:
            score += 0.5
        
        # High VAF suggests somatic mutation (cancer)
        vaf = variant.vaf
        if vaf is not None:
            if vaf > 0.3:  # High VAF suggests clonal mutation
                score += 0.2
            elif vaf < 0.1:  # Very low VAF might be subclonal
                score += 0.1
        
        # Rare variants (low population frequency) are more likely pathogenic
        if variant.gnomad_af is not None and variant.gnomad_af < 0.001:
            score += 0.2
        elif variant.gnomad_af is None:  # Not in databases
            score += 0.1
        
        # Consequence-based scoring
        if variant.consequence:
            consequence_lower = variant.consequence.lower()
            if "frameshift" in consequence_lower or "stop" in consequence_lower:
                score += 0.3
            elif "missense" in consequence_lower:
                score += 0.1
            elif "synonymous" in consequence_lower:
                score -= 0.2
        
        # Cancer gene variants get bonus
        if self.cancer_genes_db and variant.gene:
            if self.cancer_genes_db.is_cancer_gene(variant.gene):
                score += 0.2
        
        return min(1.0, max(0.0, score))

    def _is_hotspot(self, variant: Variant) -> bool:
        """Check if variant is in a known hotspot region."""
        # Check INFO for hotspot annotation
        if variant.info:
            if "HOTSPOT" in variant.info or "COSMIC" in variant.info:
                return True
            # Some annotations use different field names
            if any("hotspot" in str(k).lower() for k in variant.info.keys()):
                return True
        return False

    def _calculate_patient_metrics(
        self, variants: List[Dict], coverage: float
    ) -> Dict[str, Any]:
        """
        Calculate patient-level metrics from variants.

        Args:
            variants: List of variant dictionaries
            coverage: Sequencing coverage

        Returns:
            Dictionary with patient-level metrics
        """
        if not variants:
            return {
                "coverage": coverage,
                "variant_count": 0,
                "high_impact_count": 0,
                "rare_variant_count": 0,
                "cancer_gene_count": 0,
                "pathogenic_count": 0,
            }
        
        high_impact_count = sum(1 for v in variants if v.get("is_high_impact", False))
        rare_variant_count = sum(1 for v in variants if v.get("is_rare", False))
        cancer_gene_count = sum(1 for v in variants if v.get("is_cancer_gene", False))
        pathogenic_count = sum(1 for v in variants if v.get("is_pathogenic", False))
        
        return {
            "coverage": coverage,
            "variant_count": len(variants),
            "high_impact_count": high_impact_count,
            "rare_variant_count": rare_variant_count,
            "cancer_gene_count": cancer_gene_count,
            "pathogenic_count": pathogenic_count,
        }

    def _format_analysis_result(self, analysis_result: Dict) -> str:
        """
        Format analysis result as assistant message.

        Args:
            analysis_result: Analysis result dictionary

        Returns:
            Formatted analysis text
        """
        parts = []

        if "summary" in analysis_result:
            parts.append(f"## Summary\n{analysis_result['summary']}")

        if "findings" in analysis_result:
            parts.append(f"## Key Findings\n{analysis_result['findings']}")

        if "risk_assessment" in analysis_result:
            parts.append(f"## Risk Assessment\n{analysis_result['risk_assessment']}")

        if "recommendations" in analysis_result:
            parts.append(f"## Recommendations\n{analysis_result['recommendations']}")

        if "urgent_variants" in analysis_result:
            urgent = analysis_result["urgent_variants"]
            if urgent:
                parts.append(f"## Variants Requiring Immediate Attention\n{urgent}")

        return "\n\n".join(parts) if parts else "No significant findings detected."

    def _generate_default_analysis(
        self, patient_id: str, variants: List[Dict]
    ) -> str:
        """
        Generate default analysis text.

        Args:
            patient_id: Patient identifier
            variants: List of variants

        Returns:
            Default analysis text
        """
        if not variants:
            return (
                "## Summary\n"
                "No pathogenic variants detected in this sample.\n\n"
                "## Risk Assessment\n"
                "Based on the current analysis, no elevated cancer risk is indicated.\n\n"
                "## Recommendations\n"
                "Continue with standard screening protocols."
            )

        variant_count = len(variants)
        return (
            f"## Summary\n"
            f"Analysis of patient {patient_id} identified {variant_count} variant(s) "
            f"requiring clinical review.\n\n"
            f"## Key Findings\n"
            f"Multiple variants detected that may have clinical significance.\n\n"
            f"## Risk Assessment\n"
            f"Further evaluation recommended to assess cancer risk.\n\n"
            f"## Recommendations\n"
            f"1. Review variant annotations and clinical significance\n"
            f"2. Consider additional testing if indicated\n"
            f"3. Consult with genetics team for interpretation"
        )

    def load_training_data(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Load training data from JSONL file.

        Args:
            file_path: Path to JSONL file

        Returns:
            List of training examples
        """
        if not file_path.exists():
            self.logger.warning(f"Training data file not found: {file_path}")
            return []

        examples = []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        examples.append(json.loads(line))

            self.logger.info(f"Loaded {len(examples)} training examples from {file_path}")
        except Exception as e:
            error_msg = f"Error loading training data from {file_path}: {str(e)}"
            self.logger.error(error_msg)
            raise TrainingDataPreparationError(error_msg) from e

        return examples

    def save_training_data(
        self, examples: List[Dict[str, Any]], file_path: Path
    ) -> None:
        """
        Save training data to JSONL file.

        Args:
            examples: List of training examples
            file_path: Path to save JSONL file
        """
        file_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                for example in examples:
                    f.write(json.dumps(example, ensure_ascii=False) + "\n")

            self.logger.info(f"Saved {len(examples)} training examples to {file_path}")
        except Exception as e:
            error_msg = f"Error saving training data to {file_path}: {str(e)}"
            self.logger.error(error_msg)
            raise TrainingDataPreparationError(error_msg) from e

