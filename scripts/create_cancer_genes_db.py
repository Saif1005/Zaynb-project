#!/usr/bin/env python3
"""
Script pour créer une base de données minimale des gènes cancéreux.
"""

import json
from pathlib import Path

# Liste des gènes cancéreux les plus importants avec leurs informations
CANCER_GENES = {
    "TP53": {
        "symbol": "TP53",
        "name": "Tumor protein p53",
        "chromosome": "chr17",
        "start_position": 7668402,
        "end_position": 7687550,
        "cancer_types": ["breast", "ovarian", "colorectal", "lung", "pancreatic"],
        "pathogenicity": "pathogenic",
        "inheritance": "autosomal_dominant",
    },
    "BRCA1": {
        "symbol": "BRCA1",
        "name": "BRCA1 DNA repair associated",
        "chromosome": "chr17",
        "start_position": 43044295,
        "end_position": 43125483,
        "cancer_types": ["breast", "ovarian"],
        "pathogenicity": "pathogenic",
        "inheritance": "autosomal_dominant",
    },
    "BRCA2": {
        "symbol": "BRCA2",
        "name": "BRCA2 DNA repair associated",
        "chromosome": "chr13",
        "start_position": 32315474,
        "end_position": 32400266,
        "cancer_types": ["breast", "ovarian", "pancreatic"],
        "pathogenicity": "pathogenic",
        "inheritance": "autosomal_dominant",
    },
    "KRAS": {
        "symbol": "KRAS",
        "name": "KRAS proto-oncogene, GTPase",
        "chromosome": "chr12",
        "start_position": 25205246,
        "end_position": 25250929,
        "cancer_types": ["colorectal", "pancreatic", "lung"],
        "pathogenicity": "pathogenic",
        "inheritance": "somatic",
    },
    "EGFR": {
        "symbol": "EGFR",
        "name": "Epidermal growth factor receptor",
        "chromosome": "chr7",
        "start_position": 55019017,
        "end_position": 55211628,
        "cancer_types": ["lung", "colorectal", "brain"],
        "pathogenicity": "pathogenic",
        "inheritance": "somatic",
    },
    "PIK3CA": {
        "symbol": "PIK3CA",
        "name": "Phosphatidylinositol-4,5-bisphosphate 3-kinase catalytic subunit alpha",
        "chromosome": "chr3",
        "start_position": 179148114,
        "end_position": 179240093,
        "cancer_types": ["breast", "colorectal", "endometrial"],
        "pathogenicity": "pathogenic",
        "inheritance": "somatic",
    },
    "PTEN": {
        "symbol": "PTEN",
        "name": "Phosphatase and tensin homolog",
        "chromosome": "chr10",
        "start_position": 87863247,
        "end_position": 87971930,
        "cancer_types": ["breast", "endometrial", "prostate", "brain"],
        "pathogenicity": "pathogenic",
        "inheritance": "autosomal_dominant",
    },
    "APC": {
        "symbol": "APC",
        "name": "APC regulator of WNT signaling pathway",
        "chromosome": "chr5",
        "start_position": 112707498,
        "end_position": 112846239,
        "cancer_types": ["colorectal"],
        "pathogenicity": "pathogenic",
        "inheritance": "autosomal_dominant",
    },
    "RB1": {
        "symbol": "RB1",
        "name": "RB transcriptional corepressor 1",
        "chromosome": "chr13",
        "start_position": 48303751,
        "end_position": 48481526,
        "cancer_types": ["retinoblastoma", "osteosarcoma", "lung"],
        "pathogenicity": "pathogenic",
        "inheritance": "autosomal_dominant",
    },
    "VHL": {
        "symbol": "VHL",
        "name": "Von Hippel-Lindau tumor suppressor",
        "chromosome": "chr3",
        "start_position": 10183314,
        "end_position": 10194194,
        "cancer_types": ["renal", "pheochromocytoma"],
        "pathogenicity": "pathogenic",
        "inheritance": "autosomal_dominant",
    },
    "CDKN2A": {
        "symbol": "CDKN2A",
        "name": "Cyclin dependent kinase inhibitor 2A",
        "chromosome": "chr9",
        "start_position": 21967752,
        "end_position": 21995300,
        "cancer_types": ["melanoma", "pancreatic"],
        "pathogenicity": "pathogenic",
        "inheritance": "autosomal_dominant",
    },
    "MLH1": {
        "symbol": "MLH1",
        "name": "MutL homolog 1",
        "chromosome": "chr3",
        "start_position": 37034841,
        "end_position": 37092337,
        "cancer_types": ["colorectal", "endometrial"],
        "pathogenicity": "pathogenic",
        "inheritance": "autosomal_dominant",
    },
    "MSH2": {
        "symbol": "MSH2",
        "name": "MutS homolog 2",
        "chromosome": "chr2",
        "start_position": 47467569,
        "end_position": 47665050,
        "cancer_types": ["colorectal", "endometrial"],
        "pathogenicity": "pathogenic",
        "inheritance": "autosomal_dominant",
    },
    "BRAF": {
        "symbol": "BRAF",
        "name": "B-Raf proto-oncogene, serine/threonine kinase",
        "chromosome": "chr7",
        "start_position": 140719327,
        "end_position": 140924928,
        "cancer_types": ["melanoma", "colorectal", "thyroid"],
        "pathogenicity": "pathogenic",
        "inheritance": "somatic",
    },
    "MYC": {
        "symbol": "MYC",
        "name": "MYC proto-oncogene, bHLH transcription factor",
        "chromosome": "chr8",
        "start_position": 127735434,
        "end_position": 127742951,
        "cancer_types": ["lymphoma", "leukemia", "breast"],
        "pathogenicity": "pathogenic",
        "inheritance": "somatic",
    },
    "HER2": {
        "symbol": "ERBB2",
        "name": "Erb-b2 receptor tyrosine kinase 2",
        "chromosome": "chr17",
        "start_position": 39688094,
        "end_position": 39728660,
        "cancer_types": ["breast", "gastric"],
        "pathogenicity": "pathogenic",
        "inheritance": "somatic",
    },
}


def main():
    """Créer la base de données des gènes cancéreux."""
    # Créer le répertoire
    db_dir = Path("./data/cancer_genes")
    db_dir.mkdir(parents=True, exist_ok=True)
    
    db_path = db_dir / "cancer_genes_db.json"
    
    # Sauvegarder la base de données
    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(CANCER_GENES, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Base de données créée: {db_path}")
    print(f"   {len(CANCER_GENES)} gènes cancéreux ajoutés")
    print("\nGènes inclus:")
    for gene in sorted(CANCER_GENES.keys()):
        print(f"  - {gene}: {CANCER_GENES[gene]['name']}")


if __name__ == "__main__":
    main()
