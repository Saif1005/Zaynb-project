#!/usr/bin/env python3
"""
Script pour télécharger les fichiers FASTQ manquants depuis SRA
pour les patients listés dans patients_list.json.
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


def check_fastq_exists(patient_id: str) -> bool:
    """Vérifier si les fichiers FASTQ existent déjà sur S3."""
    bucket = aws_config.s3_input_bucket
    r1_path = f"s3://{bucket}/patients/{patient_id}/R1.fastq.gz"
    r2_path = f"s3://{bucket}/patients/{patient_id}/R2.fastq.gz"
    
    try:
        result_r1 = subprocess.run(
            ["aws", "s3", "ls", r1_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        result_r2 = subprocess.run(
            ["aws", "s3", "ls", r2_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result_r1.returncode == 0 and result_r2.returncode == 0
    except Exception:
        return False


def download_sra_fastq(sra_id: str, output_dir: Path) -> Optional[Dict[str, str]]:
    """Télécharger les fichiers FASTQ depuis SRA."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"[{sra_id}] Téléchargement depuis SRA...")
    
    # Vérifier si sra-toolkit est installé
    try:
        subprocess.run(["prefetch", "--version"], capture_output=True, check=True, timeout=10)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        logger.error("sra-toolkit n'est pas installé. Installez-le avec: sudo apt-get install sra-toolkit")
        return None
    
    # Vérifier si un processus prefetch est déjà actif pour ce SRA ID
    try:
        check_process = subprocess.run(
            ["pgrep", "-f", f"prefetch.*{sra_id}"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if check_process.returncode == 0:
            logger.warning(f"[{sra_id}] Un processus prefetch est déjà actif. Attente de la fin...")
            # Attendre jusqu'à 10 minutes que le processus se termine
            for _ in range(60):
                time.sleep(10)
                check_process = subprocess.run(
                    ["pgrep", "-f", f"prefetch.*{sra_id}"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if check_process.returncode != 0:
                    logger.info(f"[{sra_id}] Processus prefetch terminé")
                    break
            else:
                logger.warning(f"[{sra_id}] Timeout: le processus prefetch est toujours actif après 10 minutes")
                return None
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        # pgrep peut ne pas être disponible, continuer
        pass
    
    # Nettoyer les fichiers lock orphelins avant de télécharger
    lock_file = output_dir / f"{sra_id}.sra.lock"
    if lock_file.exists():
        # Vérifier si le lock file est utilisé par un processus actif
        try:
            lsof_check = subprocess.run(
                ["lsof", str(lock_file)],
                capture_output=True,
                text=True,
                timeout=5
            )
            if lsof_check.returncode == 0:
                logger.warning(f"[{sra_id}] Lock file utilisé par un processus actif, attente...")
                time.sleep(30)  # Attendre 30 secondes
            else:
                logger.warning(f"[{sra_id}] Suppression du fichier lock orphelin: {lock_file}")
                try:
                    lock_file.unlink()
                except Exception as e:
                    logger.warning(f"[{sra_id}] Impossible de supprimer le lock file: {e}")
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            # lsof peut ne pas être disponible, supprimer le lock file
            logger.warning(f"[{sra_id}] Suppression du fichier lock: {lock_file}")
            try:
                lock_file.unlink()
            except Exception as e:
                logger.warning(f"[{sra_id}] Impossible de supprimer le lock file: {e}")
    
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


def upload_fastq_via_ec2(patient_id: str, fastq_r1: str, fastq_r2: str, ssh_key: str) -> bool:
    """Uploader les fichiers FASTQ vers S3 via l'instance EC2."""
    logger.info(f"[{patient_id}] Upload vers S3 via EC2...")
    
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


def process_patient(patient_id: str, sra_id: str, download_dir: Path, ssh_key: str) -> Dict:
    """Traiter un patient : télécharger et uploader."""
    result = {
        "patient_id": patient_id,
        "sra_id": sra_id,
        "status": "failed",
        "error": None,
    }
    
    try:
        # Vérifier si déjà présent
        if check_fastq_exists(patient_id):
            logger.info(f"[{patient_id}] ✅ Déjà présent sur S3, skip")
            result["status"] = "skipped"
            result["fastq_r1_s3"] = f"s3://{aws_config.s3_input_bucket}/patients/{patient_id}/R1.fastq.gz"
            result["fastq_r2_s3"] = f"s3://{aws_config.s3_input_bucket}/patients/{patient_id}/R2.fastq.gz"
            return result
        
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
        description="Télécharger les fichiers FASTQ manquants pour les patients dans patients_list.json"
    )
    
    parser.add_argument(
        "--patients-file",
        type=str,
        default="./data/patients_list.json",
        help="Fichier JSON avec la liste des patients",
    )
    
    parser.add_argument(
        "--sra-ids-file",
        type=str,
        help="Fichier texte avec une liste d'IDs SRA (un par ligne). Si non fourni, réutilise les IDs disponibles.",
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
    
    args = parser.parse_args()
    
    # Setup logging
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO",
    )
    
    logger.info("=" * 60)
    logger.info("TÉLÉCHARGEMENT DES FICHIERS FASTQ MANQUANTS")
    logger.info("=" * 60)
    
    # Charger la liste des patients
    patients_file = Path(args.patients_file)
    if not patients_file.exists():
        logger.error(f"Fichier patients introuvable: {patients_file}")
        sys.exit(1)
    
    with open(patients_file, "r") as f:
        patients = json.load(f)
    
    logger.info(f"✅ {len(patients)} patients chargés depuis {patients_file}")
    
    # Vérifier quels patients ont déjà leurs fichiers
    missing_patients = []
    existing_patients = []
    
    logger.info("Vérification des fichiers existants sur S3...")
    for patient in patients[:10]:  # Vérifier les 10 premiers pour avoir une idée
        patient_id = patient.get("patient_id", "")
        if check_fastq_exists(patient_id):
            existing_patients.append(patient_id)
        else:
            missing_patients.append(patient_id)
    
    logger.info(f"Exemple: {len(existing_patients)} patients avec fichiers, {len(missing_patients)} patients sans fichiers")
    
    # Charger les IDs SRA
    if args.sra_ids_file and Path(args.sra_ids_file).exists():
        with open(args.sra_ids_file, "r") as f:
            sra_ids = [line.strip() for line in f if line.strip()]
        logger.info(f"✅ {len(sra_ids)} IDs SRA chargés depuis {args.sra_ids_file}")
    else:
        # Utiliser une liste par défaut et la répéter
        default_sra_ids = ["SRR1770413", "SRR390728", "ERR034533"]
        sra_ids = (default_sra_ids * (len(patients) // len(default_sra_ids) + 1))[:len(patients)]
        logger.warning(f"Utilisation de {len(default_sra_ids)} IDs SRA par défaut (réutilisés)")
    
    # Filtrer les patients qui n'ont pas de fichiers
    patients_to_process = []
    for patient in patients:
        patient_id = patient.get("patient_id", "")
        if not check_fastq_exists(patient_id):
            patients_to_process.append(patient)
    
    logger.info(f"📋 {len(patients_to_process)} patients nécessitent un téléchargement")
    
    if len(patients_to_process) == 0:
        logger.info("✅ Tous les patients ont déjà leurs fichiers FASTQ sur S3!")
        return
    
    # Créer les répertoires
    download_dir = Path(args.download_dir)
    download_dir.mkdir(parents=True, exist_ok=True)
    
    # Traiter les patients
    results = []
    failed = []
    
    logger.info(f"Traitement de {len(patients_to_process)} patients avec {args.max_workers} workers...")
    
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {}
        
        for i, patient in enumerate(patients_to_process):
            patient_id = patient.get("patient_id", "")
            sra_id = sra_ids[i % len(sra_ids)]  # Réutiliser les IDs SRA si nécessaire
            
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
                elif result["status"] == "skipped":
                    logger.info(f"⏭️  [{patient_id}] Déjà présent")
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
    
    # Résumé
    logger.info("")
    logger.info("=" * 60)
    logger.info("RÉSUMÉ")
    logger.info("=" * 60)
    logger.info(f"Total patients à traiter: {len(patients_to_process)}")
    logger.info(f"Succès: {sum(1 for r in results if r['status'] == 'success')}")
    logger.info(f"Déjà présents: {sum(1 for r in results if r['status'] == 'skipped')}")
    logger.info(f"Échecs: {len(failed)}")
    
    if failed:
        logger.warning("")
        logger.warning("Patients en échec:")
        for f in failed[:10]:  # Afficher les 10 premiers
            logger.warning(f"  - {f['patient_id']}: {f.get('error', 'Unknown')}")


if __name__ == "__main__":
    main()
