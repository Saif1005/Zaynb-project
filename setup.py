"""Setup script for genomic-cancer-detection-aws package."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="genomic-cancer-detection-aws",
    version="0.1.0",
    author="Genomic AI Team",
    description="Pipeline d'analyse génomique avec détection de cancer assistée par IA sur AWS",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/genomic-cancer-detection-aws",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Healthcare Industry",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.10",
    install_requires=requirements,
    extras_require={
        "dev": [
            "black",
            "flake8",
            "mypy",
            "pytest",
            "pytest-cov",
            "pytest-mock",
        ],
    },
    entry_points={
        "console_scripts": [
            "genomic-pipeline=scripts.pipeline.run_pipeline:main",
            "genomic-train=scripts.training.train_llm:main",
        ],
    },
)

