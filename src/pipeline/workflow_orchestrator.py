"""Workflow orchestrator for end-to-end genomic pipeline execution on AWS."""

from pathlib import Path
from typing import Optional, Dict, List
from loguru import logger

from config.aws_config import aws_config
from src.aws.s3_manager import get_s3_manager
from src.aws.ec2_manager import get_ec2_manager
from src.pipeline.parabricks_runner import ParabricksRunner
from src.preprocessing.vcf_parser import VCFParser
from src.utils.validators import validate_fastq_files, validate_patient_id


class WorkflowOrchestratorError(Exception):
    """Custom exception for workflow orchestration errors."""

    pass


class WorkflowOrchestrator:
    """Orchestrates the complete genomic pipeline on AWS."""

    def __init__(
        self,
        patient_id: str,
        fastq_r1: str,
        fastq_r2: Optional[str] = None,
        instance_id: Optional[str] = None,
        ssh_key_path: Optional[str] = None,
    ):
        """
        Initialize workflow orchestrator.

        Args:
            patient_id: Patient identifier
            fastq_r1: Path to R1 FASTQ (local or S3)
            fastq_r2: Optional path to R2 FASTQ (for paired-end)
            instance_id: Optional EC2 instance ID (will launch if not provided)
            ssh_key_path: Path to SSH private key for EC2 access
        """
        validate_patient_id(patient_id)
        self.patient_id = patient_id
        self.fastq_r1 = fastq_r1
        self.fastq_r2 = fastq_r2
        self.instance_id = instance_id
        self.ssh_key_path = ssh_key_path

        self.s3_manager = get_s3_manager()
        self.ec2_manager = get_ec2_manager()
        self.parabricks_runner = ParabricksRunner(
            instance_id=instance_id, ssh_key_path=ssh_key_path
        )

        # S3 paths for intermediate and final results
        self.s3_input_prefix = f"patients/{patient_id}/input"
        self.s3_output_prefix = f"patients/{patient_id}/output"
        self.s3_work_prefix = f"patients/{patient_id}/work"

    def run_full_pipeline(self) -> Dict:
        """
        Execute the complete genomic pipeline.

        Pipeline steps:
        1. Upload FASTQ files to S3 (if local)
        2. Run Parabricks fq2bam (FASTQ → BAM)
        3. Run Parabricks HaplotypeCaller (BAM → VCF)
        4. Download VCF from S3
        5. Parse and analyze VCF
        6. Generate summary

        Returns:
            Dictionary with pipeline results and paths

        Raises:
            WorkflowOrchestratorError: If pipeline fails
        """
        logger.info(f"Starting full pipeline for patient: {self.patient_id}")

        try:
            # Step 1: Prepare input files on S3
            fastq_r1_s3, fastq_r2_s3 = self._prepare_input_files()

            # Step 2: Run fq2bam
            bam_s3 = self._run_fq2bam(fastq_r1_s3, fastq_r2_s3)

            # Step 3: Run HaplotypeCaller
            vcf_s3 = self._run_haplotypecaller(bam_s3)

            # Step 4: Download and parse VCF
            vcf_local = self._download_vcf(vcf_s3)

            # Step 5: Analyze variants
            analysis_results = self._analyze_variants(vcf_local)

            # Step 6: Generate summary
            summary = self._generate_summary(
                fastq_r1_s3=fastq_r1_s3,
                fastq_r2_s3=fastq_r2_s3,
                bam_s3=bam_s3,
                vcf_s3=vcf_s3,
                analysis=analysis_results,
            )

            logger.info(f"Pipeline completed successfully for patient: {self.patient_id}")
            return summary

        except Exception as e:
            logger.error(f"Pipeline failed for patient {self.patient_id}: {e}")
            raise WorkflowOrchestratorError(f"Pipeline execution failed: {e}") from e

    def _prepare_input_files(self) -> tuple[str, Optional[str]]:
        """
        Upload FASTQ files to S3 if they are local.

        Returns:
            Tuple of (R1 S3 path, R2 S3 path)
        """
        logger.info("Preparing input files on S3")

        # Upload R1 if local
        if not self.fastq_r1.startswith("s3://"):
            fastq_r1_name = Path(self.fastq_r1).name
            s3_key_r1 = f"{self.s3_input_prefix}/{fastq_r1_name}"
            self.s3_manager.upload_file(
                self.fastq_r1, s3_key_r1, bucket_name=aws_config.s3_input_bucket
            )
            fastq_r1_s3 = f"s3://{aws_config.s3_input_bucket}/{s3_key_r1}"
            logger.info(f"Uploaded R1 to {fastq_r1_s3}")
        else:
            fastq_r1_s3 = self.fastq_r1

        # Upload R2 if provided and local
        fastq_r2_s3 = None
        if self.fastq_r2:
            if not self.fastq_r2.startswith("s3://"):
                fastq_r2_name = Path(self.fastq_r2).name
                s3_key_r2 = f"{self.s3_input_prefix}/{fastq_r2_name}"
                self.s3_manager.upload_file(
                    self.fastq_r2, s3_key_r2, bucket_name=aws_config.s3_input_bucket
                )
                fastq_r2_s3 = f"s3://{aws_config.s3_input_bucket}/{s3_key_r2}"
                logger.info(f"Uploaded R2 to {fastq_r2_s3}")
            else:
                fastq_r2_s3 = self.fastq_r2

        return fastq_r1_s3, fastq_r2_s3

    def _run_fq2bam(
        self, fastq_r1_s3: str, fastq_r2_s3: Optional[str]
    ) -> str:
        """
        Run Parabricks fq2bam pipeline.

        Args:
            fastq_r1_s3: S3 path to R1 FASTQ
            fastq_r2_s3: Optional S3 path to R2 FASTQ

        Returns:
            S3 path to output BAM
        """
        logger.info("Running Parabricks fq2bam pipeline")

        bam_name = f"{self.patient_id}.aligned.bam"
        bam_s3 = f"s3://{aws_config.s3_output_bucket}/{self.s3_output_prefix}/{bam_name}"

        # Run fq2bam (Parabricks handles S3 URIs directly)
        if fastq_r2_s3:
            self.parabricks_runner.run_fq2bam(
                fastq_r1=fastq_r1_s3,
                fastq_r2=fastq_r2_s3,
                output_bam=bam_s3,
                reference_genome=aws_config.reference_genome_s3,
            )
        else:
            # Single-end (only R1)
            raise WorkflowOrchestratorError(
                "Single-end FASTQ not yet supported"
            )

        logger.info(f"fq2bam completed: {bam_s3}")
        return bam_s3

    def _run_haplotypecaller(self, bam_s3: str) -> str:
        """
        Run Parabricks HaplotypeCaller.

        Args:
            bam_s3: S3 path to input BAM

        Returns:
            S3 path to output VCF
        """
        logger.info("Running Parabricks HaplotypeCaller")

        vcf_name = f"{self.patient_id}.variants.vcf.gz"
        vcf_s3 = f"s3://{aws_config.s3_output_bucket}/{self.s3_output_prefix}/{vcf_name}"

        # Run HaplotypeCaller
        self.parabricks_runner.run_haplotypecaller(
            input_bam=bam_s3,
            output_vcf=vcf_s3,
            reference_genome=aws_config.reference_genome_s3,
        )

        logger.info(f"HaplotypeCaller completed: {vcf_s3}")
        return vcf_s3

    def _download_vcf(self, vcf_s3: str) -> str:
        """
        Download VCF from S3 to local.

        Args:
            vcf_s3: S3 path to VCF

        Returns:
            Local path to VCF
        """
        logger.info(f"Downloading VCF from {vcf_s3}")

        vcf_local = f"./work/{self.patient_id}/variants.vcf.gz"
        Path(vcf_local).parent.mkdir(parents=True, exist_ok=True)

        # Extract S3 bucket and key
        s3_path = vcf_s3.replace("s3://", "")
        parts = s3_path.split("/", 1)
        bucket = parts[0]
        key = parts[1] if len(parts) > 1 else ""

        self.s3_manager.download_file(
            s3_key=key, local_path=vcf_local, bucket_name=bucket
        )

        logger.info(f"VCF downloaded to {vcf_local}")
        return vcf_local

    def _analyze_variants(self, vcf_local: str) -> Dict:
        """
        Parse and analyze VCF file.

        Args:
            vcf_local: Local path to VCF

        Returns:
            Dictionary with analysis results
        """
        logger.info("Analyzing variants from VCF")

        parser = VCFParser(vcf_local)
        variants = parser.parse()

        # Get pathogenic cancer variants
        pathogenic_cancer = parser.get_pathogenic_cancer_variants(variants)

        # Get summary
        summary = parser.get_variant_summary(variants)

        analysis = {
            "total_variants": len(variants),
            "pathogenic_cancer_variants": len(pathogenic_cancer),
            "pathogenic_variants": [
                {
                    "gene": v.gene,
                    "position": f"{v.chromosome}:{v.position}",
                    "variant": f"{v.ref}>{v.alt}",
                    "clinvar": v.clinvar,
                    "consequence": v.consequence,
                }
                for v in pathogenic_cancer
            ],
            "summary": summary,
        }

        logger.info(
            f"Analysis complete: {len(pathogenic_cancer)} pathogenic "
            f"cancer variants found"
        )
        return analysis

    def _generate_summary(
        self,
        fastq_r1_s3: str,
        fastq_r2_s3: Optional[str],
        bam_s3: str,
        vcf_s3: str,
        analysis: Dict,
    ) -> Dict:
        """
        Generate pipeline summary.

        Args:
            fastq_r1_s3: S3 path to R1 FASTQ
            fastq_r2_s3: S3 path to R2 FASTQ
            bam_s3: S3 path to BAM
            vcf_s3: S3 path to VCF
            analysis: Analysis results

        Returns:
            Complete pipeline summary
        """
        summary = {
            "patient_id": self.patient_id,
            "status": "completed",
            "input_files": {
                "fastq_r1": fastq_r1_s3,
                "fastq_r2": fastq_r2_s3,
            },
            "output_files": {
                "bam": bam_s3,
                "vcf": vcf_s3,
            },
            "analysis": analysis,
            "instance_id": self.instance_id,
        }

        return summary

    def cleanup(self) -> None:
        """Cleanup resources (close SSH, optionally stop instance)."""
        self.parabricks_runner.cleanup()
        logger.info("Workflow orchestrator cleanup completed")

