#!/usr/bin/env python3
"""
Script pour analyser un VCF depuis S3 et préparer les données d'entraînement.
"""

import argparse
import sys
import os
from pathlib import Path

# Add project root to path - resolve to absolute path FIRST
# Script is in scripts/, so project root is parent.parent
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
    from src.agents.vcf_analysis_agent import VCFAnalysisAgent
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
        description="Analyser un VCF depuis S3 et préparer les données d'entraînement"
    )
    
    parser.add_argument(
        "--vcf-s3",
        required=True,
        help="Chemin S3 vers le fichier VCF (ex: s3://bucket/path/variants.vcf.gz)",
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
    logger.info("ANALYSE VCF ET PRÉPARATION DES DONNÉES D'ENTRAÎNEMENT")
    logger.info("=" * 60)
    logger.info(f"Patient ID: {args.patient_id}")
    logger.info(f"VCF S3: {args.vcf_s3}")
    logger.info("=" * 60)
    
    try:
        # Étape 1: Analyser le VCF
        logger.info("Étape 1: Analyse du VCF...")
        vcf_agent = VCFAnalysisAgent()
        
        context = {
            "patient_id": args.patient_id,
            "vcf_s3": args.vcf_s3,
        }
        
        result = vcf_agent.execute(context)
        
        if not result.success:
            logger.error(f"Erreur lors de l'analyse VCF: {result.error}")
            sys.exit(1)
        
        variants = result.data.get("variants", [])
        logger.info(f"✅ {len(variants)} variants pathogènes extraits")
        
        # Afficher un résumé
        logger.info("")
        logger.info("Résumé des variants:")
        logger.info(f"  Total variants: {result.data.get('total_variants', 0)}")
        logger.info(f"  Variants pathogènes: {len(variants)}")
        logger.info(f"  Coverage moyen: {result.data.get('coverage', 0):.2f}x")
        
        # Afficher les 5 premiers variants
        if variants:
            logger.info("")
            logger.info("Exemples de variants (5 premiers):")
            for i, variant in enumerate(variants[:5], 1):
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
            variants=variants,
            coverage=result.data.get("coverage", 30.0),
            analysis_result=result.data,
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
