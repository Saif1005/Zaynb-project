#!/usr/bin/env python3
"""
Script pour vérifier l'état du traitement batch et identifier les problèmes.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

def check_batch_status(output_dir: str = "./data/batch_processing"):
    """Vérifier l'état du traitement batch."""
    output_path = Path(output_dir)
    
    print("=" * 60)
    print("📊 ÉTAT DU TRAITEMENT BATCH")
    print("=" * 60)
    print()
    
    # Charger le progrès
    progress_file = output_path / "progress.json"
    if not progress_file.exists():
        print("❌ Fichier de progrès introuvable")
        return
    
    with open(progress_file, "r") as f:
        progress = json.load(f)
    
    processed = progress.get("processed", [])
    failed = progress.get("failed", [])
    total = progress.get("total", 0)
    
    print(f"Total patients: {total}")
    print(f"✅ Traités avec succès: {len(processed)}")
    print(f"❌ Échoués: {len(failed)}")
    print(f"⏳ En attente: {total - len(processed) - len(failed)}")
    print()
    
    # Charger les résultats
    results_file = output_path / "results.json"
    if results_file.exists():
        with open(results_file, "r") as f:
            results = json.load(f)
        
        if results:
            print("Derniers résultats:")
            for result in results[-5:]:
                patient_id = result.get("patient_id", "Unknown")
                status = result.get("status", "unknown")
                processing_time = result.get("processing_time", 0)
                variants_count = result.get("variants_count", 0)
                
                print(f"  {patient_id}: {status} ({processing_time/60:.1f} min, {variants_count} variants)")
            print()
    
    # Charger les erreurs
    errors_file = output_path / "errors.json"
    if errors_file.exists():
        with open(errors_file, "r") as f:
            errors = json.load(f)
        
        if errors:
            print("Erreurs récentes:")
            error_types = {}
            for error in errors[-10:]:
                error_msg = error.get("error", "Unknown error")
                # Catégoriser les erreurs
                if "NoSuchKey" in error_msg or "not found" in error_msg.lower():
                    error_type = "Fichier FASTQ manquant"
                elif "SSH" in error_msg or "Connection" in error_msg:
                    error_type = "Erreur SSH"
                elif "timeout" in error_msg.lower():
                    error_type = "Timeout"
                else:
                    error_type = "Autre"
                
                error_types[error_type] = error_types.get(error_type, 0) + 1
            
            for error_type, count in error_types.items():
                print(f"  {error_type}: {count} occurrences")
            print()
            
            print("Exemples d'erreurs:")
            for error in errors[-3:]:
                print(f"  {error.get('patient_id', 'Unknown')}: {error.get('error', 'Unknown')[:100]}")
            print()
    
    # Recommandations
    print("=" * 60)
    print("💡 RECOMMANDATIONS")
    print("=" * 60)
    
    if len(failed) > len(processed):
        print("⚠️  Beaucoup d'échecs détectés!")
        print()
        print("Causes possibles:")
        print("  1. Fichiers FASTQ manquants sur S3")
        print("  2. Erreurs SSH (saturation)")
        print("  3. Timeouts")
        print()
        print("Solutions:")
        print("  1. Vérifier les fichiers FASTQ:")
        print("     bash scripts/verify_fastq_files.sh")
        print()
        print("  2. Si fichiers manquants, uploader:")
        print("     bash scripts/upload_fastq_via_ec2.sh --patient-id PATIENT001 ...")
        print()
        print("  3. Ou utiliser des VCF existants (skip_alignment):")
        print("     Modifier patients_list.json pour ajouter 'skip_alignment': true")
        print()
        print("  4. Réduire le nombre de workers:")
        print("     --max-workers 1")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Vérifier l'état du traitement batch")
    parser.add_argument(
        "--output-dir",
        default="./data/batch_processing",
        help="Répertoire de sortie du batch processing",
    )
    
    args = parser.parse_args()
    check_batch_status(args.output_dir)
