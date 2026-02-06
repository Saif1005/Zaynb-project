#!/usr/bin/env python3
"""
Script pour télécharger les données FASTQ de 100 patients depuis SRA
et les uploader vers S3 via l'instance EC2.
"""

import argparse
import subprocess
import json
import time
import os
from pathlib import Path
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from loguru import logger
from config.aws_config import aws_config


# Liste d'IDs SRA publics accessibles pour tests
# Note: Pour 100 patients, vous devrez trouver plus d'IDs SRA ou réutiliser certains IDs
DEFAULT_SRA_IDS = [
    "SRR1770413", "SRR390728", "ERR034533",
    # Ajoutez plus d'IDs SRA ici ou utilisez une liste externe
]

# Si vous avez un fichier avec des IDs SRA
SRA_IDS_FILE = "data/sra_ids_list.txt"


def load_sra_ids(file_path: Optional[str] = None) -> List[str]:
    """Charger une liste d'IDs SRA depuis un fichier ou utiliser la liste par défaut."""
    if file_path and Path(file_path).exists():
        with open(file_path, "r") as f:
            ids = [line.strip() for line in f if line.strip()]
            logger.info(f"Chargé {len(ids)} IDs SRA depuis {file_path}")
            return ids
    
    # Utiliser la liste par défaut et la répéter pour avoir 100 patients
    ids = DEFAULT_SRA_IDS * (100 // len(DEFAULT_SRA_IDS) + 1)
    return ids[:100]


def download_sra_fastq(sra_id: str, output_dir: Path) -> Optional[Dict[str, str]]:
    """
    Télécharger les fichiers FASTQ depuis SRA.
    
    Args:
        sra_id: ID SRA
        output_dir: Répertoire de sortie
        
    Returns:
        Dictionnaire avec les chemins des fichiers R1 et R2, ou None si échec
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"[{sra_id}] Téléchargement depuis SRA...")
    
    # Vérifier si sra-toolkit est installé
    try:
        subprocess.run(["prefetch", "--version"], capture_output=True, check=True, timeout=10)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        logger.error("sra-toolkit n'est pas installé. Installez-le avec: sudo apt-get install sra-toolkit")
        return None
    
    # Télécharger avec prefetch
    prefetch_cmd = ["prefetch", sra_id]
    result = subprocess.run(prefetch_cmd, cwd=str(output_dir), capture_output=True, text=True, timeout=3600)
    
    if result.returncode != 0:
        logger.warning(f"[{sra_id}] Erreur prefetch: {result.stderr}")
        return None
    
    # Convertir en FASTQ
    fastq_dump_cmd = ["fastq-dump", "--split-files", sra_id]
    result = subprocess.run(fastq_dump_cmd, cwd=str(output_dir), capture_output=True, text=True, timeout=3600)
    
    if result.returncode != 0:
        logger.warning(f"[{sra_id}] Erreur fastq-dump: {result.stderr}")
        return None
    
    # Compresser
    r1_path = output_dir / f"{sra_id}_1.fastq"
    r2_path = output_dir / f"{sra_id}_2.fastq"
    
    if r1_path.exists():
        subprocess.run(["gzip", "-f", str(r1_path)], check=True, timeout=600)
        r1_path = output_dir / f"{sra_id}_1.fastq.gz"
    
    if r2_path.exists():
        subprocess.run(["gzip", "-f", str(r2_path)], check=True, timeout=600)
        r2_path = output_dir / f"{sra_id}_2.fastq.gz"
    
    if not r1_path.exists() or not r2_path.exists():
        logger.warning(f"[{sra_id}] Fichiers FASTQ non trouvés après conversion")
        return None
    
    logger.info(f"[{sra_id}] ✅ Téléchargement terminé")
    return {
        "r1": str(r1_path),
        "r2": str(r2_path),
    }


def upload_fastq_via_ec2(patient_id: str, fastq_r1: str, fastq_r2: str, 
                         ssh_key: str) -> bool:
    """
    Uploader les fichiers FASTQ vers S3 via l'instance EC2.
    
    Args:
        patient_id: ID du patient
        fastq_r1: Chemin vers R1
        fastq_r2: Chemin vers R2
        ssh_key: Chemin vers la clé SSH
        
    Returns:
        True si succès
    """
    logger.info(f"[{patient_id}] Upload vers S3 via EC2...")
    
    # Utiliser le script existant upload_fastq_via_ec2.sh
    upload_script = project_root / "scripts" / "upload_fastq_via_ec2.sh"
    
    if not upload_script.exists():
        logger.error(f"Script upload non trouvé: {upload_script}")
        return False
    
    cmd = [
        "bash", str(upload_script),
        "--patient-id", patient_id,
        "--fastq-r1", fastq_r1,
        "--fastq-r2", fastq_r2,
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    
    if result.returncode != 0:
        logger.error(f"[{patient_id}] Erreur upload: {result.stderr}")
        return False
    
    logger.info(f"[{patient_id}] ✅ Upload terminé")
    return True


def process_patient(patient_id: str, sra_id: str, download_dir: Path, 
                   ssh_key: str) -> Dict:
    """
    Traiter un patient : télécharger et uploader.
    
    Args:
        patient_id: ID du patient (ex: PATIENT001)
        sra_id: ID SRA à télécharger
        download_dir: Répertoire pour les téléchargements
        ssh_key: Chemin vers la clé SSH
        
    Returns:
        Dictionnaire avec le résultat
    """
    result = {
        "patient_id": patient_id,
        "sra_id": sra_id,
        "status": "failed",
        "error": None,
    }
    
    try:
        # Télécharger
        fastq_files = download_sra_fastq(sra_id, download_dir)
        
        if not fastq_files:
            result["error"] = "Échec du téléchargement SRA"
            return result
        
        # Uploader
        success = upload_fastq_via_ec2(
            patient_id=patient_id,
            fastq_r1=fastq_files["r1"],
            fastq_r2=fastq_files["r2"],
            ssh_key=ssh_key,
        )
        
        if success:
            result["status"] = "success"
            result["fastq_r1_s3"] = f"s3://{aws_config.s3_input_bucket}/patients/{patient_id}/R1.fastq.gz"
            result["fastq_r2_s3"] = f"s3://{aws_config.s3_input_bucket}/patients/{patient_id}/R2.fastq.gz"
        else:
            result["error"] = "Échec de l'upload"
        
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"[{patient_id}] Erreur: {e}")
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Télécharger les données FASTQ de 100 patients depuis SRA"
    )
    
    parser.add_argument(
        "--sra-ids-file",
        type=str,
        help="Fichier texte avec une liste d'IDs SRA (un par ligne)",
    )
    
    parser.add_argument(
        "--download-dir",
        type=str,
        default="./data/fastq_downloads",
        help="Répertoire pour télécharger les fichiers FASTQ",
    )
    
    parser.add_argument(
        "--ssh-key",
        type=str,
        default="~/.ssh/saif-pipeline-complet",
        help="Chemin vers la clé SSH",
    )
    
    parser.add_argument(
        "--max-workers",
        type=int,
        default=2,
        help="Nombre de téléchargements en parallèle (défaut: 2)",
    )
    
    parser.add_argument(
        "--output-file",
        type=str,
        default="./data/patients_list_100.json",
        help="Fichier JSON de sortie avec la liste des patients",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
    )
    
    logger.info("=" * 60)
    logger.info("TÉLÉCHARGEMENT DE 100 PATIENTS FASTQ")
    logger.info("=" * 60)
    
    # Charger les IDs SRA
    sra_ids = load_sra_ids(args.sra_ids_file)
    
    if len(sra_ids) < 100:
        logger.warning(f"Seulement {len(sra_ids)} IDs SRA disponibles. Certains IDs seront réutilisés.")
        # Répéter les IDs pour avoir 100 patients
        sra_ids = (sra_ids * (100 // len(sra_ids) + 1))[:100]
    
    logger.info(f"✅ {len(sra_ids)} IDs SRA chargés")
    
    # Créer les répertoires
    download_dir = Path(args.download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)
    
    # Générer les IDs de patients
    patient_ids = [f"PATIENT{i:03d}" for i in range(1, 101)]
    
    # Traiter les patients
    results = []
    failed = []
    
    logger.info(f"Traitement de {len(patient_ids)} patients avec {args.max_workers} workers...")
    
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {}
        
        for patient_id, sra_id in zip(patient_ids, sra_ids):
            future = executor.submit(
                process_patient,
                patient_id=patient_id,
                sra_id=sra_id,
                download_dir=download_dir,
                ssh_key=os.path.expanduser(args.ssh_key),
            )
            futures[future] = (patient_id, sra_id)
            time.sleep(1)  # Délai pour éviter la saturation
        
        for future in as_completed(futures):
            patient_id, sra_id = futures[future]
            try:
                result = future.result()
                results.append(result)
                
                if result["status"] == "success":
                    logger.info(f"✅ [{patient_id}] Succès")
                else:
                    logger.error(f"❌ [{patient_id}] Échec: {result.get('error', 'Unknown')}")
                    failed.append(result)
            except Exception as e:
                logger.error(f"❌ [{patient_id}] Exception: {e}")
                failed.append({
                    "patient_id": patient_id,
                    "sra_id": sra_id,
                    "status": "failed",
                    "error": str(e),
                })
    
    # Créer le fichier patients_list.json
    patients_list = []
    for result in results:
        if result["status"] == "success":
            patients_list.append({
                "patient_id": result["patient_id"],
                "fastq_r1_s3": result["fastq_r1_s3"],
                "fastq_r2_s3": result["fastq_r2_s3"],
                "skip_alignment": False,
            })
    
    output_file = Path(args.output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w") as f:
        json.dump(patients_list, f, indent=2)
    
    # Résumé
    logger.info("")
    logger.info("=" * 60)
    logger.info("RÉSUMÉ")
    logger.info("=" * 60)
    logger.info(f"Total patients: {len(patient_ids)}")
    logger.info(f"Succès: {len(patients_list)}")
    logger.info(f"Échecs: {len(failed)}")
    logger.info(f"Fichier créé: {output_file}")
    logger.info("")
    logger.info("Prochaines étapes:")
    logger.info(f"  python scripts/pipeline/batch_process_patients.py \\")
    logger.info(f"      --instance-id <INSTANCE_ID> \\")
    logger.info(f"      --ssh-key {args.ssh_key} \\")
    logger.info(f"      --patients-file {output_file} \\")
    logger.info(f"      --max-workers 2")


if __name__ == "__main__":
    main()
