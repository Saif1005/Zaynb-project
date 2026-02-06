"""Parabricks Agent - Executes Parabricks genomic pipeline."""

from typing import Dict, Any, Optional
from loguru import logger

from src.agents.base_agent import BaseAgent, AgentResult, AgentStatus
from src.pipeline.parabricks_runner import ParabricksRunner
from config.aws_config import aws_config


class ParabricksAgent(BaseAgent):
    """Agent for executing Parabricks pipeline."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize Parabricks Agent."""
        super().__init__("Parabricks", config)
        self.runner: Optional[ParabricksRunner] = None

    def validate_input(self, context: Dict[str, Any]) -> bool:
        """Validate input context."""
        required = ["patient_id", "fastq_r1_s3", "fastq_r2_s3"]
        for field in required:
            if field not in context:
                self.logger.error(f"Missing required field: {field}")
                return False
        return True

    def execute(self, context: Dict[str, Any]) -> AgentResult:
        """
        Execute Parabricks pipeline (fq2bam + HaplotypeCaller).

        Args:
            context: Context with FASTQ S3 paths

        Returns:
            AgentResult with BAM and VCF S3 paths
        """
        patient_id = context.get("patient_id")
        fastq_r1_s3 = context.get("fastq_r1_s3")
        fastq_r2_s3 = context.get("fastq_r2_s3")
        
        instance_id = context.get("instance_id") or self.config.get("instance_id")
        ssh_key = context.get("ssh_key") or self.config.get("ssh_key")
        
        if not instance_id or not ssh_key:
            return AgentResult(
                success=False,
                status=AgentStatus.FAILED,
                error="Missing instance_id or ssh_key in context or config"
            )
        
        try:
            # Initialize runner
            self.runner = ParabricksRunner(
                instance_id=instance_id,
                ssh_key_path=ssh_key,
            )
            
            # Define output paths
            bam_s3 = f"s3://{aws_config.s3_output_bucket}/patients/{patient_id}/aligned.bam"
            vcf_s3 = f"s3://{aws_config.s3_output_bucket}/patients/{patient_id}/variants.vcf.gz"
            
            # Run fq2bam
            self.logger.info("Executing Parabricks fq2bam...")
            bam_output = self.runner.run_fq2bam(
                fastq_r1=fastq_r1_s3,
                fastq_r2=fastq_r2_s3,
                output_bam=bam_s3,
                reference_genome=aws_config.reference_genome_s3,
            )
            self.logger.info(f"✓ fq2bam completed: {bam_output}")
            
            # Run HaplotypeCaller
            self.logger.info("Executing Parabricks HaplotypeCaller...")
            vcf_output = self.runner.run_haplotypecaller(
                input_bam=bam_output,
                output_vcf=vcf_s3,
                reference_genome=aws_config.reference_genome_s3,
            )
            self.logger.info(f"✓ HaplotypeCaller completed: {vcf_output}")
            
            return AgentResult(
                success=True,
                status=AgentStatus.COMPLETED,
                data={
                    "bam_s3": bam_output,
                    "vcf_s3": vcf_output,
                    "patient_id": patient_id,
                }
            )

        except Exception as e:
            error_msg = f"Parabricks execution failed: {e}"
            self.logger.error(error_msg)
            return AgentResult(
                success=False,
                status=AgentStatus.FAILED,
                error=error_msg
            )
        finally:
            if self.runner:
                self.runner.cleanup()








