#!/usr/bin/env python3
"""
Script pour consolider toutes les données d'entraînement des patients traités
et créer une base de données enrichie avec métriques.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict
from collections import defaultdict
import statistics

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
project_root_str = str(project_root)
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)
import os
os.chdir(project_root)

from loguru import logger
from config.logging_config import logging_config
from src.llm.data_preparation import TrainingDataPreparation


class TrainingDataConsolidator:
    """Consolidateur de données d'entraînement."""
    
    def __init__(self, batch_output_dir: str):
        """
        Initialiser le consolidateur.
        
        Args:
            batch_output_dir: Répertoire contenant les résultats du batch processing
        """
        self.batch_dir = Path(batch_output_dir)
        self.training_data_dir = self.batch_dir / "training_data"
        self.results_file = self.batch_dir / "results.json"
        
    def load_all_training_examples(self) -> List[Dict]:
        """Charger tous les exemples d'entraînement."""
        examples = []
        
        # Charger depuis les fichiers individuels
        if self.training_data_dir.exists():
            for patient_file in self.training_data_dir.glob("*.json"):
                try:
                    with open(patient_file, "r") as f:
                        example = json.load(f)
                        examples.append(example)
                except Exception as e:
                    logger.warning(f"Erreur lors du chargement de {patient_file}: {e}")
        
        logger.info(f"Chargé {len(examples)} exemples d'entraînement")
        return examples
    
    def calculate_metrics(self, examples: List[Dict]) -> Dict:
        """
        Calculer des métriques sur la base de données.
        
        Args:
            examples: Liste d'exemples d'entraînement
            
        Returns:
            Dictionnaire avec les métriques
        """
        metrics = {
            "total_patients": len(examples),
            "total_variants": 0,
            "patients_with_variants": 0,
            "patients_without_variants": 0,
            "variant_counts": [],
            "coverage_values": [],
            "high_impact_counts": [],
            "rare_variant_counts": [],
            "cancer_gene_counts": [],
            "pathogenic_counts": [],
            "genes_distribution": defaultdict(int),
            "consequence_distribution": defaultdict(int),
            "variant_types": defaultdict(int),
        }
        
        for example in examples:
            metadata = example.get("metadata", {})
            
            variant_count = metadata.get("variant_count", 0)
            metrics["total_variants"] += variant_count
            metrics["variant_counts"].append(variant_count)
            
            if variant_count > 0:
                metrics["patients_with_variants"] += 1
            else:
                metrics["patients_without_variants"] += 1
            
            metrics["coverage_values"].append(metadata.get("coverage", 0))
            metrics["high_impact_counts"].append(metadata.get("high_impact_count", 0))
            metrics["rare_variant_counts"].append(metadata.get("rare_variant_count", 0))
            metrics["cancer_gene_counts"].append(metadata.get("cancer_gene_count", 0))
            metrics["pathogenic_counts"].append(metadata.get("pathogenic_count", 0))
            
            # Analyser les variants dans les messages
            messages = example.get("messages", [])
            for msg in messages:
                if msg.get("role") == "user":
                    content = msg.get("content", "")
                    # Extraire les gènes mentionnés
                    # (simplifié, pourrait être amélioré)
                    if "Gene:" in content:
                        for line in content.split("\n"):
                            if "Gene:" in line:
                                gene = line.split("Gene:")[1].split(",")[0].strip()
                                if gene:
                                    metrics["genes_distribution"][gene] += 1
        
        # Calculer les statistiques
        if metrics["variant_counts"]:
            metrics["stats"] = {
                "variant_count": {
                    "mean": statistics.mean(metrics["variant_counts"]),
                    "median": statistics.median(metrics["variant_counts"]),
                    "min": min(metrics["variant_counts"]),
                    "max": max(metrics["variant_counts"]),
                },
                "coverage": {
                    "mean": statistics.mean(metrics["coverage_values"]),
                    "median": statistics.median(metrics["coverage_values"]),
                    "min": min(metrics["coverage_values"]),
                    "max": max(metrics["coverage_values"]),
                },
                "high_impact": {
                    "mean": statistics.mean(metrics["high_impact_counts"]),
                    "median": statistics.median(metrics["high_impact_counts"]),
                },
                "rare_variants": {
                    "mean": statistics.mean(metrics["rare_variant_counts"]),
                    "median": statistics.median(metrics["rare_variant_counts"]),
                },
            }
        
        # Top 10 gènes
        metrics["top_genes"] = sorted(
            metrics["genes_distribution"].items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        return metrics
    
    def consolidate(
        self,
        output_file: str = "./data/training/genomic_training_data.jsonl",
        min_variants: int = 0,
    ) -> Dict:
        """
        Consolider toutes les données d'entraînement.
        
        Args:
            output_file: Fichier de sortie JSONL
            min_variants: Nombre minimum de variants pour inclure un patient
            
        Returns:
            Statistiques de consolidation
        """
        logger.info("=" * 60)
        logger.info("CONSOLIDATION DES DONNÉES D'ENTRAÎNEMENT")
        logger.info("=" * 60)
        
        # Charger tous les exemples
        examples = self.load_all_training_examples()
        
        if not examples:
            logger.error("Aucun exemple d'entraînement trouvé")
            return {}
        
        # Filtrer par nombre minimum de variants
        if min_variants > 0:
            filtered_examples = []
            for example in examples:
                variant_count = example.get("metadata", {}).get("variant_count", 0)
                if variant_count >= min_variants:
                    filtered_examples.append(example)
            examples = filtered_examples
            logger.info(f"Filtré à {len(examples)} exemples avec ≥{min_variants} variants")
        
        # Calculer les métriques
        metrics = self.calculate_metrics(examples)
        
        # Sauvegarder le fichier consolidé
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        data_prep = TrainingDataPreparation()
        data_prep.save_training_data(examples, output_path)
        
        # Sauvegarder les métriques
        metrics_file = output_path.parent / "training_metrics.json"
        with open(metrics_file, "w") as f:
            json.dump(metrics, f, indent=2)
        
        logger.info("=" * 60)
        logger.info("✅ CONSOLIDATION TERMINÉE")
        logger.info("=" * 60)
        logger.info(f"Total patients: {metrics['total_patients']}")
        logger.info(f"Patients avec variants: {metrics['patients_with_variants']}")
        logger.info(f"Patients sans variants: {metrics['patients_without_variants']}")
        logger.info(f"Total variants: {metrics['total_variants']}")
        logger.info(f"Moyenne variants/patient: {metrics['stats']['variant_count']['mean']:.2f}")
        logger.info(f"Moyenne coverage: {metrics['stats']['coverage']['mean']:.2f}x")
        logger.info(f"\nTop 10 gènes:")
        for gene, count in metrics["top_genes"]:
            logger.info(f"  {gene}: {count} patients")
        logger.info(f"\nFichiers générés:")
        logger.info(f"  - {output_path}")
        logger.info(f"  - {metrics_file}")
        
        return metrics


def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Consolider les données d'entraînement de tous les patients traités"
    )
    
    parser.add_argument(
        "--batch-output-dir",
        required=True,
        help="Répertoire contenant les résultats du batch processing",
    )
    parser.add_argument(
        "--output-file",
        default="./data/training/genomic_training_data.jsonl",
        help="Fichier de sortie JSONL consolidé",
    )
    parser.add_argument(
        "--min-variants",
        type=int,
        default=0,
        help="Nombre minimum de variants pour inclure un patient (défaut: 0)",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logging_config.setup_logging()
    
    # Créer le consolidateur
    consolidator = TrainingDataConsolidator(args.batch_output_dir)
    
    # Consolider
    metrics = consolidator.consolidate(
        output_file=args.output_file,
        min_variants=args.min_variants,
    )


if __name__ == "__main__":
    main()
