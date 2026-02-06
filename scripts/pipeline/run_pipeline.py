#!/usr/bin/env python3
"""Main script to run the complete genomic pipeline on AWS."""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from config.logging_config import logging_config
from src.pipeline.workflow_orchestrator import WorkflowOrchestrator


def main():
    """Main entry point for pipeline execution."""
    parser = argparse.ArgumentParser(
        description="Run genomic cancer detection pipeline on AWS"
    )
    parser.add_argument(
        "--patient-id",
        required=True,
        help="Patient identifier (e.g., PATIENT001)",
    )
    parser.add_argument(
        "--fastq-r1",
        required=True,
        help="Path to R1 FASTQ file (local or S3)",
    )
    parser.add_argument(
        "--fastq-r2",
        help="Path to R2 FASTQ file (for paired-end, local or S3)",
    )
    parser.add_argument(
        "--instance-id",
        help="Optional EC2 instance ID (will launch new if not provided)",
    )
    parser.add_argument(
        "--ssh-key",
        help="Path to SSH private key for EC2 access",
    )
    parser.add_argument(
        "--keep-instance",
        action="store_true",
        help="Keep EC2 instance running after pipeline (default: stop instance)",
    )

    args = parser.parse_args()

    # Setup logging
    logging_config.setup_logging()

    logger.info("=" * 60)
    logger.info("Genomic Cancer Detection Pipeline - AWS")
    logger.info("=" * 60)
    logger.info(f"Patient ID: {args.patient_id}")
    logger.info(f"FASTQ R1: {args.fastq_r1}")
    if args.fastq_r2:
        logger.info(f"FASTQ R2: {args.fastq_r2}")
    logger.info("=" * 60)

    try:
        # Create orchestrator
        orchestrator = WorkflowOrchestrator(
            patient_id=args.patient_id,
            fastq_r1=args.fastq_r1,
            fastq_r2=args.fastq_r2,
            instance_id=args.instance_id,
            ssh_key_path=args.ssh_key,
        )

        # Run pipeline
        results = orchestrator.run_full_pipeline()

        # Print results
        logger.info("=" * 60)
        logger.info("PIPELINE RESULTS")
        logger.info("=" * 60)
        logger.info(f"Status: {results['status']}")
        logger.info(f"BAM: {results['output_files']['bam']}")
        logger.info(f"VCF: {results['output_files']['vcf']}")
        logger.info(
            f"Pathogenic cancer variants: "
            f"{results['analysis']['pathogenic_cancer_variants']}"
        )

        if results['analysis']['pathogenic_variants']:
            logger.info("\nPathogenic variants found:")
            for variant in results['analysis']['pathogenic_variants']:
                logger.info(
                    f"  - {variant['gene']} {variant['position']} "
                    f"{variant['variant']} ({variant['clinvar']})"
                )

        logger.info("=" * 60)

        # Cleanup
        if not args.keep_instance:
            logger.info("Cleaning up resources...")
            orchestrator.cleanup()
            if orchestrator.instance_id:
                logger.info(f"Stopping instance: {orchestrator.instance_id}")
                from src.aws.ec2_manager import get_ec2_manager
                ec2_manager = get_ec2_manager()
                ec2_manager.stop_instance(orchestrator.instance_id)

        logger.info("Pipeline completed successfully!")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()


