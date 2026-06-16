"""Helper utility functions for genomic pipeline."""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger


def ensure_directory(directory_path: str) -> Path:
    """
    Ensure directory exists, create if it doesn't.

    Args:
        directory_path: Path to directory

    Returns:
        Path object to directory
    """
    path = Path(directory_path)
    path.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Directory ensured: {directory_path}")
    return path


def get_file_size_mb(file_path: str) -> float:
    """
    Get file size in megabytes.

    Args:
        file_path: Path to file

    Returns:
        File size in MB
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    size_bytes = os.path.getsize(file_path)
    size_mb = size_bytes / (1024 * 1024)
    return round(size_mb, 2)


def format_genomic_position(chromosome: str, position: int) -> str:
    """
    Format genomic position as chr:pos.

    Args:
        chromosome: Chromosome name (e.g., "chr17" or "17")
        position: Genomic position (1-based)

    Returns:
        Formatted position string (e.g., "chr17:41234470")
    """
    # Ensure chromosome has 'chr' prefix
    if not chromosome.startswith("chr"):
        chromosome = f"chr{chromosome}"

    return f"{chromosome}:{position}"


def parse_genomic_position(position_str: str) -> tuple[str, int]:
    """
    Parse genomic position string into chromosome and position.

    Args:
        position_str: Position string (e.g., "chr17:41234470" or "17:41234470")

    Returns:
        Tuple of (chromosome, position)
    """
    if ":" not in position_str:
        raise ValueError(f"Invalid position format: {position_str}")

    chrom, pos = position_str.split(":", 1)
    return chrom, int(pos)


def get_sample_name_from_path(file_path: str) -> str:
    """
    Extract sample name from file path.

    Args:
        file_path: Path to genomic file

    Returns:
        Sample name extracted from filename
    """
    filename = Path(file_path).stem

    # Remove common extensions
    for ext in [".fastq", ".fq", ".bam", ".vcf", ".gz"]:
        if filename.endswith(ext):
            filename = filename[: -len(ext)]

    # Remove R1/R2 suffixes
    if filename.endswith("_R1") or filename.endswith("_R2"):
        filename = filename[:-3]

    return filename


def create_output_filename(
    base_name: str,
    suffix: str,
    extension: str,
    output_dir: Optional[str] = None,
) -> str:
    """
    Create standardized output filename.

    Args:
        base_name: Base name (e.g., sample ID)
        suffix: Suffix to add (e.g., "aligned", "variants")
        extension: File extension (e.g., "bam", "vcf")
        output_dir: Optional output directory

    Returns:
        Full output file path
    """
    filename = f"{base_name}.{suffix}.{extension}"

    if output_dir:
        ensure_directory(output_dir)
        return str(Path(output_dir) / filename)

    return filename


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string (e.g., "2h 30m 15s")
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")

    return " ".join(parts)


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safely divide two numbers, returning default if denominator is zero.

    Args:
        numerator: Numerator
        denominator: Denominator
        default: Default value if division by zero

    Returns:
        Division result or default
    """
    if denominator == 0:
        return default
    return numerator / denominator










