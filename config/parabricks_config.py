"""Parabricks configuration module."""

import os
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ParabricksConfig:
    """Configuration for NVIDIA Parabricks GPU-accelerated genomics pipeline."""

    image: str
    license_key: Optional[str] = None
    gpu_count: int = 1
    memory_gb: int = 64

    @classmethod
    def from_env(cls) -> "ParabricksConfig":
        """Create ParabricksConfig from environment variables."""
        return cls(
            image=os.getenv(
                "PARABRICKS_IMAGE",
                "nvcr.io/nvidia/clara/clara-parabricks:4.6.0-1",
            ),
            license_key=os.getenv("PARABRICKS_LICENSE_KEY"),
            gpu_count=int(os.getenv("PARABRICKS_GPU_COUNT", "1")),
            memory_gb=int(os.getenv("PARABRICKS_MEMORY_GB", "64")),
        )

    def get_docker_command(
        self,
        command: str,
        input_files: list[str],
        output_file: str,
        reference_genome: str,
        use_gpu: Optional[bool] = None,
        **kwargs: str,
    ) -> list[str]:
        """
        Generate Docker command for Parabricks execution.
        
        Parabricks supports direct S3 URIs (s3://bucket/key) without
        needing to download files first. See:
        https://docs.nvidia.com/clara/parabricks/latest/tutorials/fq2bam_tutorial.html

        Args:
            command: Parabricks command (fq2bam, haplotypecaller, etc.)
            input_files: List of input file paths (can be S3 URIs)
            output_file: Output file path (can be S3 URI)
            reference_genome: Path to reference genome FASTA (can be S3 URI)
            use_gpu: Whether to use GPU (None = auto-detect, True = force GPU, False = CPU only)
            **kwargs: Additional command-line arguments

        Returns:
            List of command arguments for subprocess
        """
        cmd = [
            "docker",
            "run",
            "--rm",
        ]
        
        # Add GPU support only if explicitly requested
        # Note: GPU detection is done in parabricks_runner before calling this method
        if use_gpu:
            cmd.extend(["--gpus", "all"])
        
        cmd.extend([
            self.image,
            "pbrun",
            command,  # Command comes immediately after pbrun
        ])
        
        # Note: --cpu flag is not a global pbrun flag
        # CPU mode is automatically used when no GPU is available
        # Some Parabricks commands may support --cpu as a command-specific flag
        
        cmd.extend([
            "--ref",
            reference_genome,
        ])

        # Add input files (Parabricks handles S3 URIs directly)
        if command == "fq2bam":
            cmd.extend(["--in-fq"] + input_files)
        elif command == "haplotypecaller":
            cmd.extend(["--in-bam"] + input_files)

        # Add output (Parabricks can write directly to S3)
        if command == "fq2bam":
            cmd.extend(["--out-bam", output_file])
        elif command == "haplotypecaller":
            cmd.extend(["--out-variants", output_file])

        # Add additional kwargs
        for key, value in kwargs.items():
            cmd.extend([f"--{key.replace('_', '-')}", str(value)])

        return cmd


# Global instance
parabricks_config = ParabricksConfig.from_env()

