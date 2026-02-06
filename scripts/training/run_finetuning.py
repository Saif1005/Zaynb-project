#!/usr/bin/env python3
"""
Script pour lancer le fine-tuning de Mistral sur les données génomiques.

Usage:
    python scripts/training/run_finetuning.py \
        --instance-id i-0822e345e78731721 \
        --ssh-key ~/.ssh/saif-pipeline-complet \
        --training-data ./data/training/genomic_training_data.jsonl
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from config.logging_config import logging_config
from src.llm.fine_tuner import LLMFineTuner


def main():
    """Point d'entrée principal pour le fine-tuning."""
    parser = argparse.ArgumentParser(
        description="Fine-tuner le modèle Mistral sur les données génomiques"
    )
    
    parser.add_argument(
        "--instance-id",
        required=True,
        help="ID de l'instance EC2 (ex: i-0822e345e78731721)",
    )
    parser.add_argument(
        "--ssh-key",
        required=True,
        help="Chemin vers la clé SSH privée (ex: ~/.ssh/saif-pipeline-complet)",
    )
    parser.add_argument(
        "--training-data",
        required=True,
        help="Chemin vers le fichier de données d'entraînement JSONL",
    )
    parser.add_argument(
        "--output-dir",
        help="Répertoire de sortie pour le modèle (défaut: ~/llm-training/outputs/mistral-genomic-ft)",
    )
    parser.add_argument(
        "--model-name",
        default="mistralai/Mistral-7B-Instruct-v0.2",
        help="Nom du modèle de base (défaut: mistralai/Mistral-7B-Instruct-v0.2)",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logging_config.setup_logging()
    
    logger.info("=" * 60)
    logger.info("FINE-TUNING MISTRAL POUR DÉTECTION DE CANCER")
    logger.info("=" * 60)
    logger.info(f"Instance ID: {args.instance_id}")
    logger.info(f"Training Data: {args.training_data}")
    logger.info(f"Model: {args.model_name}")
    logger.info("=" * 60)
    
    # Vérifier que le fichier de données existe
    training_data_path = Path(args.training_data)
    if not training_data_path.exists():
        logger.error(f"Fichier de données d'entraînement introuvable: {training_data_path}")
        sys.exit(1)
    
    # Compter le nombre d'exemples
    try:
        with open(training_data_path, 'r', encoding='utf-8') as f:
            num_examples = sum(1 for line in f if line.strip())
        logger.info(f"✓ {num_examples} exemples d'entraînement trouvés")
        
        if num_examples < 10:
            logger.warning(f"⚠ Seulement {num_examples} exemples. Recommandé: 20+ pour une bonne précision")
            response = input("Continuer quand même? (y/N): ")
            if response.lower() != 'y':
                logger.info("Fine-tuning annulé")
                sys.exit(0)
    except Exception as e:
        logger.error(f"Erreur lors de la lecture du fichier: {e}")
        sys.exit(1)
    
    # Initialiser le fine-tuner
    try:
        fine_tuner = LLMFineTuner(
            instance_id=args.instance_id,
            ssh_key_path=args.ssh_key,
        )
        
        # Définir le répertoire de sortie
        if args.output_dir:
            output_dir = args.output_dir
        else:
            output_dir = f"~/llm-training/outputs/mistral-genomic-ft"
        
        logger.info("=" * 60)
        logger.info("DÉMARRAGE DU FINE-TUNING")
        logger.info("=" * 60)
        logger.info("⏱️  Temps estimé: 6-24 heures (selon l'instance)")
        logger.info("📊 Vous pouvez surveiller les logs via SSH")
        logger.info("=" * 60)
        
        # Lancer le fine-tuning
        model_path = fine_tuner.run_fine_tuning(
            training_data_path=training_data_path,
            output_dir=output_dir,
        )
        
        logger.info("=" * 60)
        logger.info("✅ FINE-TUNING TERMINÉ AVEC SUCCÈS!")
        logger.info("=" * 60)
        logger.info(f"📍 Modèle sauvegardé: {model_path}")
        logger.info("")
        logger.info("💡 Pour utiliser ce modèle, utilisez:")
        logger.info(f"   --model-path {model_path}")
        logger.info("")
        
        # Nettoyer
        fine_tuner.cleanup()
        
    except KeyboardInterrupt:
        logger.warning("Fine-tuning interrompu par l'utilisateur")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Erreur lors du fine-tuning: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

