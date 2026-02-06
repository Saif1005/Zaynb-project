#!/usr/bin/env python3
"""Script simplifié pour exécuter le pipeline Parabricks sur une instance EC2 existante."""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from config.logging_config import logging_config
from config.aws_config import aws_config
from src.pipeline.parabricks_runner import ParabricksRunner


def main():
    """Point d'entrée principal pour exécuter Parabricks."""
    parser = argparse.ArgumentParser(
        description="Exécuter le pipeline Parabricks sur une instance EC2 existante"
    )
    parser.add_argument(
        "--instance-id",
        required=True,
        help="ID de l'instance EC2 (ex: i-0822e345e78731721)",
    )
    parser.add_argument(
        "--ssh-key",
        required=True,
        help="Chemin vers la clé SSH privée (ex: ~/.ssh/key.pem)",
    )
    parser.add_argument(
        "--fastq-r1",
        required=True,
        help="Chemin S3 vers le fichier FASTQ R1 (ex: s3://bucket/input/R1.fastq.gz)",
    )
    parser.add_argument(
        "--fastq-r2",
        required=True,
        help="Chemin S3 vers le fichier FASTQ R2 (ex: s3://bucket/input/R2.fastq.gz)",
    )
    parser.add_argument(
        "--output-bam",
        help="Chemin S3 pour le BAM de sortie (défaut: s3://output-bucket/patient_id/aligned.bam)",
    )
    parser.add_argument(
        "--output-vcf",
        help="Chemin S3 pour le VCF de sortie (défaut: s3://output-bucket/patient_id/variants.vcf.gz)",
    )
    parser.add_argument(
        "--reference-genome",
        help=f"Chemin S3 vers le génome de référence (défaut: {aws_config.reference_genome_s3})",
    )
    parser.add_argument(
        "--skip-haplotypecaller",
        action="store_true",
        help="Ne pas exécuter HaplotypeCaller (seulement fq2bam)",
    )

    args = parser.parse_args()

    # Setup logging
    logging_config.setup_logging()

    logger.info("=" * 60)
    logger.info("Pipeline Parabricks - Exécution sur instance EC2")
    logger.info("=" * 60)
    logger.info(f"Instance ID: {args.instance_id}")
    logger.info(f"FASTQ R1: {args.fastq_r1}")
    logger.info(f"FASTQ R2: {args.fastq_r2}")
    logger.info("=" * 60)

    # Définir les chemins de sortie par défaut
    if not args.output_bam:
        # Extraire le nom du patient depuis le chemin FASTQ
        patient_id = Path(args.fastq_r1).stem.split("_")[0] if "_" in Path(args.fastq_r1).name else "patient"
        args.output_bam = f"s3://{aws_config.s3_output_bucket}/patients/{patient_id}/aligned.bam"
    
    if not args.output_vcf:
        patient_id = Path(args.fastq_r1).stem.split("_")[0] if "_" in Path(args.fastq_r1).name else "patient"
        args.output_vcf = f"s3://{aws_config.s3_output_bucket}/patients/{patient_id}/variants.vcf.gz"

    reference_genome = args.reference_genome or aws_config.reference_genome_s3

    runner = None
    try:
        # Créer le runner Parabricks
        runner = ParabricksRunner(
            instance_id=args.instance_id,
            ssh_key_path=args.ssh_key,
        )

        # Vérifier que l'instance est en cours d'exécution
        logger.info(f"Vérification de l'instance {args.instance_id}...")
        instance_info = runner.ec2_manager.get_instance_info(args.instance_id)
        if instance_info["state"] != "running":
            logger.warning(f"L'instance est en état: {instance_info['state']}")
            logger.info("Démarrage de l'instance...")
            runner.ec2_manager.ec2_client.start_instances(InstanceIds=[args.instance_id])
            runner.ec2_manager.wait_for_instance(args.instance_id, "running")
            logger.info("Instance démarrée avec succès")

        # Vérifier que Docker et Parabricks sont disponibles
        logger.info("Vérification de Docker et Parabricks...")
        check_cmd = "docker --version && docker run --rm --gpus all nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1 pbrun --version 2>&1 | head -5"
        exit_code, stdout, stderr = runner._execute_remote_command(check_cmd, timeout=300)
        if exit_code == 0:
            logger.info("✓ Docker et Parabricks sont disponibles")
            logger.debug(f"Docker/Parabricks info: {stdout}")
        else:
            logger.warning(f"Docker/Parabricks check: {stderr}")
            logger.info("Tentative de continuation...")

        # Étape 1: Exécuter fq2bam (FASTQ → BAM)
        logger.info("=" * 60)
        logger.info("ÉTAPE 1: Exécution de Parabricks fq2bam")
        logger.info("=" * 60)
        bam_output = runner.run_fq2bam(
            fastq_r1=args.fastq_r1,
            fastq_r2=args.fastq_r2,
            output_bam=args.output_bam,
            reference_genome=reference_genome,
        )
        logger.info(f"✓ fq2bam terminé: {bam_output}")

        # Étape 2: Exécuter HaplotypeCaller (BAM → VCF)
        if not args.skip_haplotypecaller:
            logger.info("=" * 60)
            logger.info("ÉTAPE 2: Exécution de Parabricks HaplotypeCaller")
            logger.info("=" * 60)
            vcf_output = runner.run_haplotypecaller(
                input_bam=bam_output,
                output_vcf=args.output_vcf,
                reference_genome=reference_genome,
            )
            logger.info(f"✓ HaplotypeCaller terminé: {vcf_output}")

        logger.info("=" * 60)
        logger.info("Pipeline Parabricks terminé avec succès!")
        logger.info("=" * 60)
        logger.info(f"BAM: {bam_output}")
        if not args.skip_haplotypecaller:
            logger.info(f"VCF: {args.output_vcf}")

    except Exception as e:
        logger.error(f"Erreur lors de l'exécution du pipeline: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)
    finally:
        if runner:
            runner.cleanup()


if __name__ == "__main__":
    main()

