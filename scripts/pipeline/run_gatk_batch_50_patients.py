#!/usr/bin/env python3
"""
Script pour lancer le pipeline GATK complet sur les 50 patients avec FASTQ.

Workflow pour chaque patient:
1. Parabricks fq2bam (FASTQ → BAM)
2. Parabricks HaplotypeCaller (BAM → VCF)
3. Analyse VCF
4. Préparation données d'entraînement
5. Fine-tuning (optionnel)
6. Détection cancer
"""

import argparse
import sys
import os
import json
import subprocess
import time
from pathlib import Path
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)

from loguru import logger
from config.logging_config import logging_config
from config.aws_config import aws_config


def check_fastq_exists(patient_id: str) -> bool:
    """Vérifier si les fichiers FASTQ existent sur S3."""
    # Utiliser le bucket réel où les fichiers sont stockés
    bucket = "genomic-cancer-pipeline-input-dev-622994489865"
    r1_path = f"s3://{bucket}/patients/{patient_id}/R1.fastq.gz"
    r2_path = f"s3://{bucket}/patients/{patient_id}/R2.fastq.gz"
    
    try:
        # Essayer sans région d'abord (fonctionne parfois mieux)
        result_r1 = subprocess.run(
            ["aws", "s3", "ls", r1_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        result_r2 = subprocess.run(
            ["aws", "s3", "ls", r2_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        
        # Vérifier si les fichiers existent (returncode == 0 et pas d'erreur dans stderr)
        r1_exists = result_r1.returncode == 0 and "NoSuchKey" not in result_r1.stderr
        r2_exists = result_r2.returncode == 0 and "NoSuchKey" not in result_r2.stderr
        
        return r1_exists and r2_exists
    except subprocess.TimeoutExpired:
        return False
    except Exception as e:
        # En cas d'erreur, considérer comme non existant
        return False


def get_patients_with_fastq(patients_file: Path, limit: int = 50) -> List[Dict]:
    """Obtenir la liste des patients avec fichiers FASTQ sur S3."""
    # Utiliser le bucket réel où les fichiers sont stockés
    bucket = "genomic-cancer-pipeline-input-dev-622994489865"
    
    with open(patients_file, "r") as f:
        patients = json.load(f)
    
    patients_with_fastq = []
    logger.info(f"Vérification de {len(patients)} patients...")
    
    for i, patient in enumerate(patients):
        patient_id = patient.get("patient_id", "")
        if i % 10 == 0:
            logger.info(f"Vérification en cours: {i}/{len(patients)} patients vérifiés, {len(patients_with_fastq)} trouvés...")
        
        if check_fastq_exists(patient_id):
            fastq_r1 = f"s3://{bucket}/patients/{patient_id}/R1.fastq.gz"
            fastq_r2 = f"s3://{bucket}/patients/{patient_id}/R2.fastq.gz"
            patients_with_fastq.append({
                "patient_id": patient_id,
                "fastq_r1": fastq_r1,
                "fastq_r2": fastq_r2,
            })
            logger.info(f"✅ {patient_id} trouvé ({len(patients_with_fastq)}/{limit})")
            if len(patients_with_fastq) >= limit:
                break
    
    return patients_with_fastq


def run_pipeline_for_patient(
    patient_id: str,
    fastq_r1: str,
    fastq_r2: str,
    instance_id: str,
    ssh_key: str,
    skip_parabricks_pull: bool = True,
    skip_fine_tuning: bool = True,
) -> Dict:
    """Lancer le pipeline complet pour un patient."""
    result = {
        "patient_id": patient_id,
        "status": "failed",
        "error": None,
        "start_time": datetime.now().isoformat(),
    }
    
    try:
        logger.info(f"[{patient_id}] Démarrage du pipeline GATK...")
        
        # Construire la commande
        cmd = [
            "python", "scripts/pipeline/run_complete_workflow.py",
            "--instance-id", instance_id,
            "--ssh-key", ssh_key,
            "--fastq-r1", fastq_r1,
            "--fastq-r2", fastq_r2,
            "--patient-id", patient_id,
        ]
        
        if skip_parabricks_pull:
            cmd.append("--skip-parabricks-pull")
        
        if skip_fine_tuning:
            cmd.append("--skip-fine-tuning")
        
        # Exécuter la commande
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=14400,  # 4 heures max par patient
        )
        
        if process.returncode == 0:
            result["status"] = "success"
            result["end_time"] = datetime.now().isoformat()
            logger.info(f"[{patient_id}] ✅ Pipeline terminé avec succès")
        else:
            # Capturer les erreurs complètes
            error_msg = ""
            if process.stderr:
                error_msg = process.stderr
            if process.stdout and "ERROR" in process.stdout:
                error_msg += "\n" + process.stdout
            
            # Extraire la vraie erreur (ignorer les warnings)
            error_lines = error_msg.split("\n")
            real_errors = [line for line in error_lines 
                          if "ERROR" in line or "Error" in line or "Exception" in line 
                          or "Traceback" in line or "Failed" in line]
            
            if real_errors:
                result["error"] = "\n".join(real_errors[:10])  # Limiter à 10 lignes
            else:
                result["error"] = error_msg[:1000] if error_msg else "Erreur inconnue"
            
            logger.error(f"[{patient_id}] ❌ Erreur: {result['error'][:200]}")
    
    except subprocess.TimeoutExpired:
        result["error"] = "Timeout (4 heures dépassées)"
        logger.error(f"[{patient_id}] ❌ Timeout")
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"[{patient_id}] ❌ Exception: {e}")
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Lancer le pipeline GATK complet sur les 50 patients avec FASTQ"
    )
    
    parser.add_argument(
        "--instance-id",
        default="i-0822e345e78731721",
        help="ID de l'instance EC2 (défaut: i-0822e345e78731721)",
    )
    parser.add_argument(
        "--ssh-key",
        default="~/.ssh/saif-pipeline-complet",
        help="Chemin vers la clé SSH (défaut: ~/.ssh/saif-pipeline-complet)",
    )
    parser.add_argument(
        "--patients-file",
        default="./data/patients_list.json",
        help="Fichier JSON avec la liste des patients",
    )
    parser.add_argument(
        "--max-patients",
        type=int,
        default=50,
        help="Nombre maximum de patients à traiter (défaut: 50)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=1,
        help="Nombre de patients à traiter en parallèle (défaut: 1, recommandé: 1 pour éviter saturation)",
    )
    parser.add_argument(
        "--skip-parabricks-pull",
        action="store_true",
        default=True,
        help="Ne pas puller le container Parabricks (déjà présent)",
    )
    parser.add_argument(
        "--skip-fine-tuning",
        action="store_true",
        default=True,
        help="Ne pas faire le fine-tuning (utiliser modèle existant)",
    )
    parser.add_argument(
        "--output-dir",
        default="./data/batch_gatk_results",
        help="Répertoire pour sauvegarder les résultats",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logging_config.setup_logging()
    
    logger.info("=" * 60)
    logger.info("PIPELINE GATK BATCH - 50 PATIENTS")
    logger.info("=" * 60)
    logger.info(f"Instance ID: {args.instance_id}")
    logger.info(f"SSH Key: {args.ssh_key}")
    logger.info(f"Max patients: {args.max_patients}")
    logger.info(f"Max workers: {args.max_workers}")
    logger.info("=" * 60)
    
    # Créer le répertoire de sortie
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Fichiers de suivi
    progress_file = output_dir / "progress.json"
    results_file = output_dir / "results.json"
    
    # Charger le progrès existant
    if progress_file.exists():
        with open(progress_file, "r") as f:
            progress = json.load(f)
        processed_ids = set(progress.get("processed", []))
    else:
        progress = {"processed": [], "failed": []}
        processed_ids = set()
    
    # Obtenir les patients avec FASTQ
    patients_file = Path(args.patients_file)
    if not patients_file.exists():
        logger.error(f"Fichier patients introuvable: {patients_file}")
        sys.exit(1)
    
    logger.info("Recherche des patients avec fichiers FASTQ sur S3...")
    patients = get_patients_with_fastq(patients_file, limit=args.max_patients)
    logger.info(f"✅ {len(patients)} patients trouvés avec fichiers FASTQ")
    
    # Filtrer les patients déjà traités
    patients_to_process = [p for p in patients if p["patient_id"] not in processed_ids]
    logger.info(f"📋 {len(patients_to_process)} patients à traiter (déjà traités: {len(patients) - len(patients_to_process)})")
    
    if len(patients_to_process) == 0:
        logger.info("✅ Tous les patients ont déjà été traités!")
        return
    
    # Charger les résultats existants
    if results_file.exists():
        with open(results_file, "r") as f:
            results = json.load(f)
    else:
        results = []
    
    # Traiter les patients
    stats = {
        "total": len(patients_to_process),
        "success": 0,
        "failed": 0,
        "start_time": datetime.now().isoformat(),
    }
    
    logger.info(f"Traitement de {len(patients_to_process)} patients avec {args.max_workers} worker(s)...")
    
    ssh_key_expanded = os.path.expanduser(args.ssh_key)
    
    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {}
        
        for i, patient in enumerate(patients_to_process):
            # Délai entre les soumissions pour éviter la saturation
            if i > 0:
                time.sleep(2)
            
            future = executor.submit(
                run_pipeline_for_patient,
                patient_id=patient["patient_id"],
                fastq_r1=patient["fastq_r1"],
                fastq_r2=patient["fastq_r2"],
                instance_id=args.instance_id,
                ssh_key=ssh_key_expanded,
                skip_parabricks_pull=args.skip_parabricks_pull,
                skip_fine_tuning=args.skip_fine_tuning,
            )
            futures[future] = patient
        
        for future in as_completed(futures):
            patient = futures[future]
            patient_id = patient["patient_id"]
            
            try:
                result = future.result()
                results.append(result)
                
                if result["status"] == "success":
                    progress["processed"].append(patient_id)
                    stats["success"] += 1
                    logger.info(f"✅ [{patient_id}] Succès ({stats['success']}/{stats['total']})")
                else:
                    progress["failed"].append(patient_id)
                    stats["failed"] += 1
                    logger.error(f"❌ [{patient_id}] Échec: {result.get('error', 'Unknown')}")
                
                # Sauvegarder périodiquement
                with open(progress_file, "w") as f:
                    json.dump(progress, f, indent=2)
                with open(results_file, "w") as f:
                    json.dump(results, f, indent=2)
            
            except Exception as e:
                logger.error(f"❌ [{patient_id}] Exception: {e}")
                progress["failed"].append(patient_id)
                stats["failed"] += 1
    
    stats["end_time"] = datetime.now().isoformat()
    stats["success_rate"] = stats["success"] / stats["total"] if stats["total"] > 0 else 0
    
    # Résumé final
    logger.info("")
    logger.info("=" * 60)
    logger.info("RÉSUMÉ FINAL")
    logger.info("=" * 60)
    logger.info(f"Total patients: {stats['total']}")
    logger.info(f"Succès: {stats['success']}")
    logger.info(f"Échecs: {stats['failed']}")
    logger.info(f"Taux de succès: {stats['success_rate']:.2%}")
    logger.info("=" * 60)
    
    # Sauvegarder les statistiques
    stats_file = output_dir / "stats.json"
    with open(stats_file, "w") as f:
        json.dump(stats, f, indent=2)
    
    logger.info(f" Résultats sauvegardés dans: {output_dir}")


if __name__ == "__main__":
    main()
