#!/usr/bin/env python3
"""
Script pour analyser un VCF local et préparer les données d'entraînement.
Alternative au script S3 pour les environnements avec problèmes de connectivité.
"""

import argparse
import sys
import os
from pathlib import Path

# Add project root to path - resolve to absolute path FIRST
project_root = Path(__file__).resolve().parent.parent
project_root_str = str(project_root)

# Ensure project root is in Python path
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)

# Also set PYTHONPATH environment variable
os.environ['PYTHONPATH'] = project_root_str + os.pathsep + os.environ.get('PYTHONPATH', '')

# Change to project root directory
os.chdir(project_root)

# NOW import project modules
from loguru import logger

# Try to import logging_config, but make it optional
try:
    from config.logging_config import logging_config
    USE_LOGGING_CONFIG = True
except ImportError as e:
    USE_LOGGING_CONFIG = False
    # Configure basic logging with loguru
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
        colorize=True,
    )
    logger.warning(f"Could not import logging_config: {e}. Using basic logging.")

try:
    from src.preprocessing.vcf_parser import VCFParser
    from src.llm.data_preparation import TrainingDataPreparation
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    logger.error(f"Project root: {project_root}")
    logger.error(f"Python path: {sys.path[:3]}")
    logger.error(f"Current directory: {os.getcwd()}")
    sys.exit(1)


def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Analyser un VCF local et préparer les données d'entraînement"
    )
    
    parser.add_argument(
        "--vcf-file",
        required=True,
        help="Chemin vers le fichier VCF local (ex: ./work/PATIENT001/variants.vcf.gz)",
    )
    parser.add_argument(
        "--patient-id",
        required=True,
        help="ID du patient",
    )
    parser.add_argument(
        "--output-dir",
        default="./data/training",
        help="Répertoire de sortie pour les données d'entraînement",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    if USE_LOGGING_CONFIG:
        logging_config.setup_logging()
    
    logger.info("=" * 60)
    logger.info("ANALYSE VCF LOCAL ET PRÉPARATION DES DONNÉES D'ENTRAÎNEMENT")
    logger.info("=" * 60)
    logger.info(f"Patient ID: {args.patient_id}")
    logger.info(f"VCF File: {args.vcf_file}")
    logger.info("=" * 60)
    
    # Vérifier que le fichier existe
    vcf_path = Path(args.vcf_file)
    if not vcf_path.exists():
        logger.error(f"Fichier VCF introuvable: {args.vcf_file}")
        sys.exit(1)
    
    try:
        # Étape 1: Parser le VCF
        logger.info("Étape 1: Parsing du VCF...")
        # Relâcher les filtres pour accepter plus de variants
        # Les variants GATK ont souvent FILTER=. (pas PASS) et DP faible
        vcf_parser = VCFParser(
            str(vcf_path),
            min_quality=10.0,      # Au lieu de 20.0 (QUAL)
            min_vaf=0.01,         # Au lieu de 0.05 (1% au lieu de 5%)
            min_depth=2,          # Au lieu de 10 (accepter DP=2,3,4)
            require_pass=False,   # Accepter aussi FILTER=. (pas seulement PASS)
        )
        variants = vcf_parser.parse()
        logger.info(f"✅ {len(variants)} variants trouvés au total")
        
        # Pour le fine-tuning, utiliser TOUS les variants (pas seulement les pathogènes)
        # Le modèle doit apprendre à distinguer les variants importants des variants bénins
        # Get pathogenic cancer variants for summary
        pathogenic_cancer = vcf_parser.get_pathogenic_cancer_variants(variants)
        logger.info(f"✅ {len(pathogenic_cancer)} variants pathogènes extraits (pour référence)")
        
        # Convert to enriched dict format with all metrics - utiliser TOUS les variants
        variants_dict = []
        for variant in variants:  # Utiliser tous les variants, pas seulement pathogenic_cancer
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
            
            # Calculate impact score
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
        
        # Afficher un résumé
        logger.info("")
        logger.info("Résumé des variants:")
        logger.info(f"  Total variants: {len(variants)}")
        logger.info(f"  Variants enrichis: {len(variants_dict)}")
        logger.info(f"  Variants pathogènes (référence): {len(pathogenic_cancer)}")
        logger.info(f"  Coverage moyen: {coverage:.2f}x")
        
        # Afficher les 5 premiers variants
        if variants_dict:
            logger.info("")
            logger.info("Exemples de variants (5 premiers):")
            for i, variant in enumerate(variants_dict[:5], 1):
                logger.info(f"  {i}. {variant.get('gene', 'Unknown')} - "
                          f"{variant.get('chromosome', '?')}:{variant.get('position', '?')} - "
                          f"VAF={variant.get('vaf', 'N/A')}, "
                          f"Impact={variant.get('impact_score', 0):.2f}")
        
        # Étape 2: Préparer les données d'entraînement
        logger.info("")
        logger.info("Étape 2: Préparation des données d'entraînement...")
        data_prep = TrainingDataPreparation()
        
        training_example = data_prep.prepare_from_vcf_analysis(
            patient_id=args.patient_id,
            variants=variants_dict,
            coverage=coverage,
            analysis_result={
                "total_variants": len(variants),
                "enriched_variants": len(variants_dict),
                "pathogenic_cancer_variants": len(pathogenic_cancer),
                "variants": variants_dict,
                "coverage": coverage,
                "patient_id": args.patient_id,
            },
        )
        
        # Sauvegarder
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        training_data_path = output_dir / "genomic_training_data.jsonl"
        
        # Charger les données existantes
        existing_data = data_prep.load_training_data(training_data_path)
        existing_data.append(training_example)
        
        data_prep.save_training_data(existing_data, training_data_path)
        
        logger.info("")
        logger.info("=" * 60)
        logger.info("✅ SUCCÈS!")
        logger.info("=" * 60)
        logger.info(f"Données d'entraînement sauvegardées: {training_data_path}")
        logger.info(f"Total d'exemples: {len(existing_data)}")
        logger.info("")
        logger.info("Prochaines étapes:")
        logger.info("1. Vérifier les données: cat " + str(training_data_path))
        logger.info("2. Lancer le fine-tuning:")
        logger.info(f"   python scripts/training/run_finetuning.py \\")
        logger.info(f"       --instance-id <INSTANCE_ID> \\")
        logger.info(f"       --ssh-key <SSH_KEY> \\")
        logger.info(f"       --training-data {training_data_path}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Erreur: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
