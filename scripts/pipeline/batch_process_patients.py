#!/usr/bin/env python3
"""
Script pour traiter un batch de patients (ex: 200 patients).
Orchestre le workflow complet : FASTQ → BAM → VCF → Analyse → Données d'entraînement
"""

import argparse
import sys
import os
import json
import time
from pathlib import Path
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
project_root_str = str(project_root)
if project_root_str not in sys.path:
    sys.path.insert(0, project_root_str)
os.chdir(project_root)

from loguru import logger
from config.logging_config import logging_config
from config.aws_config import aws_config
from src.pipeline.cpu_runner import CPURunner
from src.agents.vcf_analysis_agent import VCFAnalysisAgent
from src.llm.data_preparation import TrainingDataPreparation


class BatchPatientProcessor:
    """Processeur pour traiter un batch de patients."""
    
    def __init__(
        self,
        instance_id: str,
        ssh_key: str,
        max_workers: int = 4,
        output_dir: str = "./data/batch_processing",
    ):
        """
        Initialiser le processeur de batch.
        
        Args:
            instance_id: ID de l'instance EC2
            ssh_key: Chemin vers la clé SSH
            max_workers: Nombre de patients à traiter en parallèle
            output_dir: Répertoire de sortie
        """
        self.instance_id = instance_id
        # Expanser le chemin SSH (résoudre ~)
        self.ssh_key = os.path.expanduser(ssh_key)
        # Limiter le nombre de workers pour éviter la saturation SSH
        self.max_workers = min(max_workers, 2)  # Max 2 workers pour SSH
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Fichiers de suivi
        self.progress_file = self.output_dir / "progress.json"
        self.results_file = self.output_dir / "results.json"
        self.errors_file = self.output_dir / "errors.json"
        
        # Charger le progrès existant
        self.progress = self._load_progress()
        self.results = self._load_results()
        self.errors = self._load_errors()
    
    def _load_progress(self) -> Dict:
        """Charger le progrès depuis le fichier."""
        if self.progress_file.exists():
            with open(self.progress_file, "r") as f:
                return json.load(f)
        return {"processed": [], "failed": [], "total": 0}
    
    def _save_progress(self):
        """Sauvegarder le progrès."""
        with open(self.progress_file, "w") as f:
            json.dump(self.progress, f, indent=2)
    
    def _load_results(self) -> List[Dict]:
        """Charger les résultats."""
        if self.results_file.exists():
            with open(self.results_file, "r") as f:
                return json.load(f)
        return []
    
    def _save_results(self):
        """Sauvegarder les résultats."""
        with open(self.results_file, "w") as f:
            json.dump(self.results, f, indent=2)
    
    def _load_errors(self) -> List[Dict]:
        """Charger les erreurs."""
        if self.errors_file.exists():
            with open(self.errors_file, "r") as f:
                return json.load(f)
        return []
    
    def _save_errors(self):
        """Sauvegarder les erreurs."""
        with open(self.errors_file, "w") as f:
            json.dump(self.errors, f, indent=2)
    
    def process_patient(
        self,
        patient_id: str,
        fastq_r1_s3: Optional[str] = None,
        fastq_r2_s3: Optional[str] = None,
        skip_alignment: bool = False,
    ) -> Dict:
        """
        Traiter un patient complet.
        
        Args:
            patient_id: ID du patient
            fastq_r1_s3: Chemin S3 vers FASTQ R1 (optionnel si skip_alignment)
            fastq_r2_s3: Chemin S3 vers FASTQ R2 (optionnel si skip_alignment)
            skip_alignment: Si True, saute l'alignement et utilise un VCF existant
            
        Returns:
            Dictionnaire avec les résultats
        """
        start_time = time.time()
        result = {
            "patient_id": patient_id,
            "status": "processing",
            "start_time": datetime.now().isoformat(),
            "steps": {},
        }
        
        try:
            # Étape 1: Alignement (FASTQ → BAM)
            if not skip_alignment and fastq_r1_s3 and fastq_r2_s3:
                logger.info(f"[{patient_id}] Étape 1: Alignement FASTQ → BAM...")
                runner = CPURunner(
                    instance_id=self.instance_id,
                    ssh_key_path=self.ssh_key,
                )
                
                bam_s3 = f"s3://{aws_config.s3_output_bucket}/patients/{patient_id}/aligned.bam"
                reference_genome = aws_config.reference_genome_s3
                
                bam_output = runner.run_fq2bam(
                    fastq_r1=fastq_r1_s3,
                    fastq_r2=fastq_r2_s3,
                    output_bam=bam_s3,
                    reference_genome=reference_genome,
                )
                result["steps"]["alignment"] = {"status": "success", "bam_s3": bam_output}
                runner.cleanup()
            else:
                result["steps"]["alignment"] = {"status": "skipped"}
            
            # Étape 2: Variant Calling (BAM → VCF)
            if not skip_alignment:
                logger.info(f"[{patient_id}] Étape 2: Variant Calling BAM → VCF...")
                runner = CPURunner(
                    instance_id=self.instance_id,
                    ssh_key_path=self.ssh_key,
                )
                
                vcf_s3 = f"s3://{aws_config.s3_output_bucket}/patients/{patient_id}/variants.vcf.gz"
                bam_s3 = result["steps"]["alignment"]["bam_s3"]
                reference_genome = aws_config.reference_genome_s3
                
                vcf_output = runner.run_haplotypecaller(
                    input_bam=bam_s3,
                    output_vcf=vcf_s3,
                    reference_genome=reference_genome,
                )
                result["steps"]["variant_calling"] = {"status": "success", "vcf_s3": vcf_output}
                runner.cleanup()
            else:
                # Utiliser un VCF existant
                vcf_s3 = f"s3://{aws_config.s3_output_bucket}/patients/{patient_id}/variants.vcf.gz"
                result["steps"]["variant_calling"] = {"status": "skipped", "vcf_s3": vcf_s3}
            
            # Étape 3: Analyse VCF
            logger.info(f"[{patient_id}] Étape 3: Analyse VCF...")
            vcf_agent = VCFAnalysisAgent()
            context = {
                "patient_id": patient_id,
                "vcf_s3": result["steps"]["variant_calling"]["vcf_s3"],
            }
            
            analysis_result = vcf_agent.execute(context)
            if not analysis_result.success:
                raise Exception(f"VCF Analysis failed: {analysis_result.error}")
            
            variants = analysis_result.data.get("variants", [])
            result["steps"]["vcf_analysis"] = {
                "status": "success",
                "total_variants": analysis_result.data.get("total_variants", 0),
                "pathogenic_variants": len(variants),
                "coverage": analysis_result.data.get("coverage", 0),
            }
            
            # Étape 4: Préparation des données d'entraînement
            logger.info(f"[{patient_id}] Étape 4: Préparation des données d'entraînement...")
            data_prep = TrainingDataPreparation()
            
            training_example = data_prep.prepare_from_vcf_analysis(
                patient_id=patient_id,
                variants=variants,
                coverage=analysis_result.data.get("coverage", 30.0),
                analysis_result=analysis_result.data,
            )
            
            # Sauvegarder l'exemple individuel
            patient_data_file = self.output_dir / "training_data" / f"{patient_id}.json"
            patient_data_file.parent.mkdir(parents=True, exist_ok=True)
            with open(patient_data_file, "w") as f:
                json.dump(training_example, f, indent=2)
            
            result["steps"]["training_prep"] = {
                "status": "success",
                "training_file": str(patient_data_file),
            }
            
            result["status"] = "success"
            result["variants_count"] = len(variants)
            result["processing_time"] = time.time() - start_time
            
            logger.info(f"[{patient_id}] ✅ Traitement terminé avec succès ({len(variants)} variants)")
            
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
            result["processing_time"] = time.time() - start_time
            logger.error(f"[{patient_id}] ❌ Erreur: {e}")
            raise
        
        return result
    
    def process_batch(
        self,
        patients: List[Dict],
        resume: bool = True,
    ) -> Dict:
        """
        Traiter un batch de patients.
        
        Args:
            patients: Liste de dictionnaires avec patient_id, fastq_r1_s3, fastq_r2_s3
            resume: Si True, reprend là où on s'est arrêté
            
        Returns:
            Statistiques du traitement
        """
        logger.info("=" * 60)
        logger.info(f"TRAITEMENT BATCH DE {len(patients)} PATIENTS")
        logger.info("=" * 60)
        
        # Filtrer les patients déjà traités si resume
        if resume:
            processed_ids = set(self.progress.get("processed", []))
            patients = [p for p in patients if p["patient_id"] not in processed_ids]
            logger.info(f"Reprise: {len(patients)} patients restants à traiter")
        
        self.progress["total"] = len(patients) + len(self.progress.get("processed", []))
        self._save_progress()
        
        stats = {
            "total": len(patients),
            "success": 0,
            "failed": 0,
            "start_time": datetime.now().isoformat(),
        }
        
        # Traiter en parallèle avec délai pour éviter saturation SSH
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for i, patient in enumerate(patients):
                # Ajouter un petit délai entre les soumissions pour éviter la saturation SSH
                if i > 0:
                    time.sleep(1)  # 1 seconde entre chaque soumission
                
                future = executor.submit(
                    self.process_patient,
                    patient["patient_id"],
                    patient.get("fastq_r1_s3"),
                    patient.get("fastq_r2_s3"),
                    patient.get("skip_alignment", False),
                )
                futures[future] = patient
            
            for future in as_completed(futures):
                patient = futures[future]
                patient_id = patient["patient_id"]
                
                try:
                    result = future.result()
                    self.results.append(result)
                    self.progress["processed"].append(patient_id)
                    stats["success"] += 1
                    logger.info(f"✅ {patient_id} terminé ({stats['success']}/{stats['total']})")
                except Exception as e:
                    error_info = {
                        "patient_id": patient_id,
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                    }
                    self.errors.append(error_info)
                    self.progress["failed"].append(patient_id)
                    stats["failed"] += 1
                    logger.error(f"❌ {patient_id} échoué: {e}")
                
                # Sauvegarder périodiquement
                self._save_progress()
                self._save_results()
                self._save_errors()
        
        stats["end_time"] = datetime.now().isoformat()
        stats["success_rate"] = stats["success"] / stats["total"] if stats["total"] > 0 else 0
        
        logger.info("=" * 60)
        logger.info("TRAITEMENT BATCH TERMINÉ")
        logger.info("=" * 60)
        logger.info(f"Total: {stats['total']}")
        logger.info(f"Succès: {stats['success']}")
        logger.info(f"Échecs: {stats['failed']}")
        logger.info(f"Taux de succès: {stats['success_rate']:.2%}")
        
        return stats


def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Traiter un batch de patients pour générer une base de données d'entraînement"
    )
    
    parser.add_argument(
        "--instance-id",
        required=True,
        help="ID de l'instance EC2",
    )
    parser.add_argument(
        "--ssh-key",
        required=True,
        help="Chemin vers la clé SSH",
    )
    parser.add_argument(
        "--patients-file",
        required=True,
        help="Fichier JSON avec la liste des patients",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=2,
        help="Nombre de patients à traiter en parallèle (défaut: 2, max recommandé: 2 pour éviter saturation SSH)",
    )
    parser.add_argument(
        "--output-dir",
        default="./data/batch_processing",
        help="Répertoire de sortie",
    )
    parser.add_argument(
        "--no-resume",
        action="store_true",
        help="Ne pas reprendre le traitement précédent",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logging_config.setup_logging()
    
    # Charger la liste des patients
    patients_file = Path(args.patients_file)
    if not patients_file.exists():
        logger.error(f"Fichier patients introuvable: {patients_file}")
        sys.exit(1)
    
    with open(patients_file, "r") as f:
        patients = json.load(f)
    
    if not isinstance(patients, list):
        logger.error("Le fichier patients doit contenir une liste JSON")
        sys.exit(1)
    
    # Créer le processeur
    processor = BatchPatientProcessor(
        instance_id=args.instance_id,
        ssh_key=args.ssh_key,
        max_workers=args.max_workers,
        output_dir=args.output_dir,
    )
    
    # Traiter le batch
    stats = processor.process_batch(patients, resume=not args.no_resume)
    
    logger.info(f"Résultats sauvegardés dans: {args.output_dir}")
    logger.info(f"Fichiers générés:")
    logger.info(f"  - {processor.progress_file}")
    logger.info(f"  - {processor.results_file}")
    logger.info(f"  - {processor.errors_file}")


if __name__ == "__main__":
    main()
