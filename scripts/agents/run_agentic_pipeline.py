#!/usr/bin/env python3
"""Script principal pour exécuter le pipeline Agentic AI complet."""

import argparse
import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from config.logging_config import logging_config
from src.agents.orchestrator import OrchestratorAgent


def main():
    """Point d'entrée principal pour le pipeline Agentic AI."""
    parser = argparse.ArgumentParser(
        description="Pipeline Agentic AI : Upload FASTQ → Parabricks → Fine-tuning → Prédiction → Rapport"
    )
    
    # Arguments obligatoires
    parser.add_argument(
        "--patient-id",
        required=True,
        help="Identifiant du patient (ex: PATIENT001)",
    )
    parser.add_argument(
        "--fastq-r1",
        required=True,
        help="Chemin vers le fichier FASTQ R1 (local ou S3)",
    )
    parser.add_argument(
        "--fastq-r2",
        help="Chemin vers le fichier FASTQ R2 (pour paired-end)",
    )
    
    # Arguments AWS/EC2
    parser.add_argument(
        "--instance-id",
        required=True,
        help="ID de l'instance EC2 (ex: i-xxxxxxxxxxxxx)",
    )
    parser.add_argument(
        "--ssh-key",
        required=True,
        help="Chemin vers la clé SSH privée (ex: ~/.ssh/key.pem)",
    )
    
    # Options LLM
    parser.add_argument(
        "--train-llm",
        action="store_true",
        help="Fine-tuner le modèle Mistral (défaut: False)",
    )
    parser.add_argument(
        "--model-path",
        help="Chemin vers le modèle fine-tuné existant (pour prédiction)",
    )
    
    # Options de sortie
    parser.add_argument(
        "--output",
        help="Fichier JSON pour sauvegarder les résultats complets",
    )
    parser.add_argument(
        "--skip-report",
        action="store_true",
        help="Ne pas générer le rapport final",
    )

    args = parser.parse_args()

    # Setup logging
    logging_config.setup_logging()

    logger.info("=" * 60)
    logger.info("Pipeline Agentic AI - Détection de Cancer")
    logger.info("=" * 60)
    logger.info(f"Patient ID: {args.patient_id}")
    logger.info(f"FASTQ R1: {args.fastq_r1}")
    if args.fastq_r2:
        logger.info(f"FASTQ R2: {args.fastq_r2}")
    logger.info("=" * 60)

    try:
        # Prepare context
        context = {
            "patient_id": args.patient_id,
            "fastq_r1": args.fastq_r1,
            "fastq_r2": args.fastq_r2,
            "instance_id": args.instance_id,
            "ssh_key": args.ssh_key,
            "train_llm": args.train_llm,
            "model_path": args.model_path,
        }
        
        # Initialize orchestrator
        config = {
            "instance_id": args.instance_id,
            "ssh_key": args.ssh_key,
            "auto_train": args.train_llm,
            "model_path": args.model_path,
        }
        
        orchestrator = OrchestratorAgent(config=config)
        
        # Execute pipeline
        result = orchestrator.run(context)
        
        # Display results
        logger.info("=" * 60)
        logger.info("RÉSULTATS DU PIPELINE")
        logger.info("=" * 60)
        
        if result.success:
            logger.info("✓ Pipeline terminé avec succès!")
            logger.info(f"Temps total: {result.execution_time:.2f} secondes")
            
            # Display prediction results
            if "results" in result.data:
                pred = result.data["results"]
                logger.info(f"\nPrédiction:")
                logger.info(f"  Cancer détecté: {'OUI' if pred.get('cancer_detected') else 'NON'}")
                if pred.get('cancer_detected'):
                    logger.info(f"  Types: {', '.join(pred.get('cancer_types', []))}")
                    logger.info(f"  Risque: {pred.get('risk_level')} ({pred.get('risk_score', 0):.1f}/100)")
            
            # Display report path
            if "report_path" in result.data:
                logger.info(f"\nRapport généré: {result.data.get('report_path')}")
                if "report_s3" in result.data:
                    logger.info(f"Rapport S3: {result.data.get('report_s3')}")
        else:
            logger.error(f"✗ Pipeline échoué: {result.error}")
        
        logger.info("=" * 60)
        
        # Save results to file
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "success": result.success,
                    "status": result.status.value,
                    "execution_time": result.execution_time,
                    "data": result.data,
                    "error": result.error,
                }, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Résultats sauvegardés: {output_path}")
        
        # Exit with appropriate code
        sys.exit(0 if result.success else 1)

    except Exception as e:
        logger.error(f"Erreur fatale: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()

