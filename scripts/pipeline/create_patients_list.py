#!/usr/bin/env python3
"""
Script pour créer une liste de 200 patients à partir de fichiers FASTQ disponibles.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict

def create_patients_list(
    fastq_dir: str,
    output_file: str,
    num_patients: int = 200,
    patient_prefix: str = "PATIENT",
) -> List[Dict]:
    """
    Créer une liste de patients à partir de fichiers FASTQ.
    
    Args:
        fastq_dir: Répertoire contenant les fichiers FASTQ (ou S3 prefix)
        output_file: Fichier de sortie JSON
        num_patients: Nombre de patients à créer
        patient_prefix: Préfixe pour les IDs de patients
        
    Returns:
        Liste de dictionnaires patients
    """
    patients = []
    
    # Option 1: Depuis un répertoire local avec fichiers FASTQ
    fastq_path = Path(fastq_dir)
    if fastq_path.exists() and fastq_path.is_dir():
        # Chercher les fichiers FASTQ
        fastq_files = sorted(list(fastq_path.glob("*.fastq.gz")) + 
                            list(fastq_path.glob("*.fq.gz")))
        
        # Grouper par patient (R1 et R2)
        patient_files = {}
        for fq_file in fastq_files:
            name = fq_file.stem.replace(".gz", "").replace(".fastq", "").replace(".fq", "")
            # Détecter R1/R2
            if "_R1" in name or "_1" in name or name.endswith("1"):
                patient_id = name.replace("_R1", "").replace("_1", "").replace("1", "")
                if patient_id not in patient_files:
                    patient_files[patient_id] = {}
                patient_files[patient_id]["r1"] = str(fq_file)
            elif "_R2" in name or "_2" in name or name.endswith("2"):
                patient_id = name.replace("_R2", "").replace("_2", "").replace("2", "")
                if patient_id not in patient_files:
                    patient_files[patient_id] = {}
                patient_files[patient_id]["r2"] = str(fq_file)
        
        # Créer la liste de patients
        for i, (patient_id, files) in enumerate(list(patient_files.items())[:num_patients]):
            if "r1" in files and "r2" in files:
                patients.append({
                    "patient_id": f"{patient_prefix}{i+1:03d}",
                    "fastq_r1_local": files["r1"],
                    "fastq_r2_local": files["r2"],
                    "fastq_r1_s3": None,  # À uploader
                    "fastq_r2_s3": None,  # À uploader
                })
    
    # Option 2: Template pour création manuelle
    else:
        print(f"Création d'un template de liste de {num_patients} patients...")
        
        for i in range(num_patients):
            patient_id = f"{patient_prefix}{i+1:03d}"
            patients.append({
                "patient_id": patient_id,
                "fastq_r1_s3": f"s3://genomic-cancer-pipeline-input-dev-622994489865/patients/{patient_id}/R1.fastq.gz",
                "fastq_r2_s3": f"s3://genomic-cancer-pipeline-input-dev-622994489865/patients/{patient_id}/R2.fastq.gz",
                "skip_alignment": False,
            })
    
    # Sauvegarder
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w") as f:
        json.dump(patients, f, indent=2)
    
    print(f"✅ Liste de {len(patients)} patients créée: {output_path}")
    print(f"\nExemple de patient:")
    if patients:
        print(json.dumps(patients[0], indent=2))
    
    return patients


def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Créer une liste de patients pour le traitement batch"
    )
    
    parser.add_argument(
        "--fastq-dir",
        default="s3://genomic-cancer-pipeline-input-dev-622994489865/patients/",
        help="Répertoire local avec FASTQ ou préfixe S3",
    )
    parser.add_argument(
        "--output-file",
        default="./data/patients_list.json",
        help="Fichier de sortie JSON",
    )
    parser.add_argument(
        "--num-patients",
        type=int,
        default=200,
        help="Nombre de patients à créer (défaut: 200)",
    )
    parser.add_argument(
        "--patient-prefix",
        default="PATIENT",
        help="Préfixe pour les IDs de patients (défaut: PATIENT)",
    )
    
    args = parser.parse_args()
    
    create_patients_list(
        fastq_dir=args.fastq_dir,
        output_file=args.output_file,
        num_patients=args.num_patients,
        patient_prefix=args.patient_prefix,
    )


if __name__ == "__main__":
    main()
