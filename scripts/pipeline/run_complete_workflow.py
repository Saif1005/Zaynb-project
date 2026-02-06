#!/usr/bin/env python3
"""
Script complet pour orchestrer le workflow :
Parabricks → Fine-tuning Mistral → Détection Cancer

Workflow:
1. Pull container Parabricks NVIDIA
2. Exécuter Parabricks (FASTQ → BAM → VCF)
3. Analyser les variants VCF
4. Préparer les données d'entraînement
5. Fine-tuner Mistral sur les variants
6. Utiliser le modèle pour détecter le cancer
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from config.logging_config import logging_config
from config.aws_config import aws_config
from src.agents.orchestrator import OrchestratorAgent
from src.pipeline.parabricks_runner import ParabricksRunner
from src.llm.data_preparation import TrainingDataPreparation
from src.llm.fine_tuner import LLMFineTuner
from src.llm.inference_engine import CancerDetectionInference


def setup_logging():
    """Setup logging configuration."""
    logging_config.setup_logging()


def pull_parabricks_container(instance_id: str, ssh_key: str) -> bool:
    """
    Puller le container Parabricks sur l'instance EC2.
    
    Args:
        instance_id: ID de l'instance EC2
        ssh_key: Chemin vers la clé SSH
        
    Returns:
        True si succès, False sinon
    """
    logger.info("=" * 60)
    logger.info("ÉTAPE 0: Pull du Container Parabricks")
    logger.info("=" * 60)
    
    runner = ParabricksRunner(instance_id=instance_id, ssh_key_path=ssh_key)
    
    try:
        # Vérifier si le container existe déjà
        check_cmd = "docker images | grep clara-parabricks || echo 'not found'"
        exit_code, stdout, stderr = runner._execute_remote_command(check_cmd, timeout=30)
        
        if "clara-parabricks" in stdout:
            logger.info("✓ Container Parabricks déjà présent")
            return True
        
        # Puller le container
        logger.info("Pulling container Parabricks (cela peut prendre plusieurs minutes)...")
        pull_cmd = "docker pull nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1"
        exit_code, stdout, stderr = runner._execute_remote_command(pull_cmd, timeout=1800)  # 30 min
        
        if exit_code == 0:
            logger.info("✓ Container Parabricks pullé avec succès")
            return True
        else:
            logger.error(f"Erreur lors du pull: {stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Erreur lors du pull du container: {e}")
        return False
    finally:
        runner.cleanup()


def run_parabricks_pipeline(
    instance_id: str,
    ssh_key: str,
    fastq_r1: str,
    fastq_r2: str,
    patient_id: str,
) -> dict:
    """
    Exécuter le pipeline Parabricks complet.
    
    Args:
        instance_id: ID de l'instance EC2
        ssh_key: Chemin vers la clé SSH
        fastq_r1: Chemin S3 vers FASTQ R1
        fastq_r2: Chemin S3 vers FASTQ R2
        patient_id: ID du patient
        
    Returns:
        Dictionnaire avec les chemins BAM et VCF
    """
    logger.info("=" * 60)
    logger.info("ÉTAPE 1: Pipeline Parabricks (FASTQ → VCF)")
    logger.info("=" * 60)
    
    runner = ParabricksRunner(instance_id=instance_id, ssh_key_path=ssh_key)
    
    try:
        # Chemins de sortie
        output_bam = f"s3://{aws_config.s3_output_bucket}/patients/{patient_id}/aligned.bam"
        output_vcf = f"s3://{aws_config.s3_output_bucket}/patients/{patient_id}/variants.vcf.gz"
        reference_genome = aws_config.reference_genome_s3
        
        # Étape 1.1: fq2bam
        logger.info("Exécution de Parabricks fq2bam...")
        bam_output = runner.run_fq2bam(
            fastq_r1=fastq_r1,
            fastq_r2=fastq_r2,
            output_bam=output_bam,
            reference_genome=reference_genome,
        )
        logger.info(f"✓ BAM généré: {bam_output}")
        
        # Étape 1.2: HaplotypeCaller
        logger.info("Exécution de Parabricks HaplotypeCaller...")
        vcf_output = runner.run_haplotypecaller(
            input_bam=bam_output,
            output_vcf=output_vcf,
            reference_genome=reference_genome,
        )
        logger.info(f"✓ VCF généré: {vcf_output}")
        
        return {
            "bam_path": bam_output,
            "vcf_path": vcf_output,
            "patient_id": patient_id,
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de l'exécution de Parabricks: {e}")
        raise
    finally:
        runner.cleanup()


def prepare_training_data(vcf_path: str, patient_id: str) -> str:
    """
    Préparer les données d'entraînement depuis le VCF.
    
    Args:
        vcf_path: Chemin S3 vers le VCF
        patient_id: ID du patient
        
    Returns:
        Chemin vers le fichier de données d'entraînement
    """
    logger.info("=" * 60)
    logger.info("ÉTAPE 2: Préparation des Données d'Entraînement")
    logger.info("=" * 60)
    
    from src.agents.vcf_analysis_agent import VCFAnalysisAgent
    
    # Analyser le VCF pour extraire les variants
    vcf_agent = VCFAnalysisAgent()
    
    # Télécharger et analyser le VCF
    context = {
        "patient_id": patient_id,
        "vcf_s3": vcf_path,  # vcf_path is actually an S3 URI
    }
    
    result = vcf_agent.execute(context)
    
    if not result.success:
        raise Exception(f"Erreur lors de l'analyse VCF: {result.error}")
    
    variants = result.data.get("variants", [])
    logger.info(f"✓ {len(variants)} variants pathogènes extraits")
    
    # Préparer les données d'entraînement
    data_prep = TrainingDataPreparation()
    
    training_example = data_prep.prepare_from_vcf_analysis(
        patient_id=patient_id,
        variants=variants,
        coverage=result.data.get("coverage", 30.0),
        analysis_result=result.data,
    )
    
    # Sauvegarder
    training_data_path = Path(f"./data/training/genomic_training_data.jsonl")
    training_data_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Charger les données existantes
    existing_data = data_prep.load_training_data(training_data_path)
    existing_data.append(training_example)
    
    data_prep.save_training_data(existing_data, training_data_path)
    logger.info(f"✓ Données d'entraînement sauvegardées: {training_data_path} ({len(existing_data)} exemples)")
    
    return str(training_data_path)


def fine_tune_mistral(
    instance_id: str,
    ssh_key: str,
    training_data_path: str,
    patient_id: str,
) -> str:
    """
    Fine-tuner le modèle Mistral sur les variants.
    
    Args:
        instance_id: ID de l'instance EC2
        ssh_key: Chemin vers la clé SSH
        training_data_path: Chemin vers les données d'entraînement
        patient_id: ID du patient
        
    Returns:
        Chemin vers le modèle fine-tuné
    """
    logger.info("=" * 60)
    logger.info("ÉTAPE 3: Fine-tuning Mistral")
    logger.info("=" * 60)
    
    fine_tuner = LLMFineTuner(
        instance_id=instance_id,
        ssh_key_path=ssh_key,
    )
    
    try:
        # Setup environnement d'entraînement
        logger.info("Configuration de l'environnement d'entraînement...")
        fine_tuner.setup_training_environment()
        
        # Uploader les données d'entraînement
        logger.info("Upload des données d'entraînement...")
        remote_data_path = fine_tuner.upload_training_data(Path(training_data_path))
        
        # Exécuter le fine-tuning
        logger.info("Démarrage du fine-tuning (cela peut prendre plusieurs heures)...")
        output_dir = f"~/llm-training/outputs/mistral-genomic-ft-{patient_id}"
        
        model_path = fine_tuner.run_fine_tuning(
            training_data_path=remote_data_path,
            output_dir=output_dir,
        )
        
        logger.info(f"✓ Fine-tuning terminé: {model_path}")
        return model_path
        
    except Exception as e:
        logger.error(f"Erreur lors du fine-tuning: {e}")
        raise
    finally:
        fine_tuner.cleanup()


def detect_cancer_with_model(
    vcf_path: str,
    patient_id: str,
    model_path: str,
) -> dict:
    """
    Utiliser le modèle fine-tuné pour détecter le cancer.
    
    Args:
        vcf_path: Chemin vers le VCF à analyser
        patient_id: ID du patient
        model_path: Chemin vers le modèle fine-tuné
        
    Returns:
        Résultats de détection
    """
    logger.info("=" * 60)
    logger.info("ÉTAPE 4: Détection de Cancer avec Modèle Fine-tuné")
    logger.info("=" * 60)
    
    from src.agents.vcf_analysis_agent import VCFAnalysisAgent
    
    # Analyser le VCF
    vcf_agent = VCFAnalysisAgent()
    context = {
        "patient_id": patient_id,
        "vcf_path": vcf_path,
    }
    
    result = vcf_agent.execute(context)
    variants = result.data.get("pathogenic_cancer_variants", [])
    
    # Utiliser le modèle fine-tuné pour l'inférence
    inference = CancerDetectionInference()
    inference.model_path = model_path
    inference.load_model()
    
    detection_results = inference.analyze_patient(
        patient_id=patient_id,
        variants=variants,
        coverage=result.data.get("coverage", 30.0),
        tmb=result.data.get("tmb"),
        quality_metrics=result.data.get("quality_metrics"),
    )
    
    logger.info(f"✓ Détection terminée pour patient {patient_id}")
    logger.info(f"  Résultats: {detection_results}")
    
    return detection_results


def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Workflow complet: Parabricks → Fine-tuning Mistral → Détection Cancer"
    )
    
    parser.add_argument(
        "--instance-id",
        required=True,
        help="ID de l'instance EC2 (ex: i-xxxxxxxxxxxxx)",
    )
    parser.add_argument(
        "--ssh-key",
        required=True,
        help="Chemin vers la clé SSH privée",
    )
    parser.add_argument(
        "--fastq-r1",
        required=True,
        help="Chemin S3 vers le fichier FASTQ R1",
    )
    parser.add_argument(
        "--fastq-r2",
        required=True,
        help="Chemin S3 vers le fichier FASTQ R2",
    )
    parser.add_argument(
        "--patient-id",
        required=True,
        help="ID du patient",
    )
    parser.add_argument(
        "--skip-parabricks-pull",
        action="store_true",
        help="Ne pas puller le container Parabricks (déjà présent)",
    )
    parser.add_argument(
        "--skip-fine-tuning",
        action="store_true",
        help="Ne pas faire le fine-tuning (utiliser modèle existant)",
    )
    parser.add_argument(
        "--model-path",
        help="Chemin vers un modèle fine-tuné existant (si skip-fine-tuning)",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    
    logger.info("=" * 60)
    logger.info("WORKFLOW COMPLET: Parabricks → Fine-tuning → Détection")
    logger.info("=" * 60)
    logger.info(f"Patient ID: {args.patient_id}")
    logger.info(f"Instance ID: {args.instance_id}")
    logger.info(f"FASTQ R1: {args.fastq_r1}")
    logger.info(f"FASTQ R2: {args.fastq_r2}")
    logger.info("=" * 60)
    
    try:
        # Étape 0: Puller Parabricks (si nécessaire)
        if not args.skip_parabricks_pull:
            if not pull_parabricks_container(args.instance_id, args.ssh_key):
                logger.error("Échec du pull du container Parabricks")
                sys.exit(1)
        
        # Étape 1: Exécuter Parabricks
        parabricks_results = run_parabricks_pipeline(
            instance_id=args.instance_id,
            ssh_key=args.ssh_key,
            fastq_r1=args.fastq_r1,
            fastq_r2=args.fastq_r2,
            patient_id=args.patient_id,
        )
        
        vcf_path = parabricks_results["vcf_path"]
        logger.info(f"✓ VCF généré: {vcf_path}")
        
        # Étape 2: Préparer les données d'entraînement
        training_data_path = prepare_training_data(vcf_path, args.patient_id)
        
        # Étape 3: Fine-tuning (si activé)
        model_path = args.model_path
        if not args.skip_fine_tuning:
            model_path = fine_tune_mistral(
                instance_id=args.instance_id,
                ssh_key=args.ssh_key,
                training_data_path=training_data_path,
                patient_id=args.patient_id,
            )
        elif not model_path:
            logger.warning("⚠️  Aucun modèle spécifié et fine-tuning désactivé")
            logger.info("Utilisation du modèle par défaut")
            model_path = None
        
        # Étape 4: Détection de cancer
        detection_results = detect_cancer_with_model(
            vcf_path=vcf_path,
            patient_id=args.patient_id,
            model_path=model_path,
        )
        
        # Résumé final
        logger.info("=" * 60)
        logger.info("✅ WORKFLOW TERMINÉ AVEC SUCCÈS!")
        logger.info("=" * 60)
        logger.info(f"Patient ID: {args.patient_id}")
        logger.info(f"VCF: {vcf_path}")
        logger.info(f"Modèle: {model_path or 'Par défaut'}")
        logger.info(f"Résultats de détection: {detection_results}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Erreur dans le workflow: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()



