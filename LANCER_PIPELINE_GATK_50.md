# 🚀 Lancer le Pipeline GATK pour 50 Patients

## ✅ Problème Résolu

Le fichier `cpu_runner.py` manquant a été créé. Le script `batch_process_patients.py` est maintenant prêt à être utilisé.

## 📋 Étapes pour Lancer le Pipeline

### Étape 1: Créer la liste des 50 patients avec FASTQ

```bash
cd /mnt/c/Users/saifa/projet_zaynb

python3 << 'EOF'
import json
import subprocess
from pathlib import Path

patients_file = Path('data/patients_list.json')
with open(patients_file) as f:
    patients = json.load(f)

bucket = 'genomic-cancer-pipeline-input-dev-622994489865'
patients_with_fastq = []

print("Recherche des patients avec fichiers FASTQ...")
for i, patient in enumerate(patients[:60]):
    patient_id = patient.get('patient_id', '')
    r1_path = f's3://{bucket}/patients/{patient_id}/R1.fastq.gz'
    r2_path = f's3://{bucket}/patients/{patient_id}/R2.fastq.gz'
    
    result_r1 = subprocess.run(['aws', 's3', 'ls', r1_path, '--region', 'eu-west-3'], 
                              capture_output=True, timeout=10)
    result_r2 = subprocess.run(['aws', 's3', 'ls', r2_path, '--region', 'eu-west-3'], 
                              capture_output=True, timeout=10)
    
    if result_r1.returncode == 0 and result_r2.returncode == 0:
        patients_with_fastq.append({
            'patient_id': patient_id,
            'fastq_r1_s3': r1_path,
            'fastq_r2_s3': r2_path,
            'skip_alignment': False
        })
        print(f'✅ {patient_id} ({len(patients_with_fastq)}/50)')
        if len(patients_with_fastq) >= 50:
            break

# Sauvegarder
output_file = Path('data/patients_with_fastq_50.json')
with open(output_file, 'w') as f:
    json.dump(patients_with_fastq, f, indent=2)

print(f'\n✅ {len(patients_with_fastq)} patients sauvegardés dans {output_file}')
EOF
```

### Étape 2: Lancer le Pipeline Batch

```bash
python scripts/pipeline/batch_process_patients.py \
    --instance-id i-0822e345e78731721 \
    --ssh-key ~/.ssh/saif-pipeline-complet \
    --patients-file data/patients_with_fastq_50.json \
    --max-workers 1 \
    --output-dir ./data/batch_gatk_50_results
```

## 📊 Ce que fait le Script

Pour chaque patient, le script exécute automatiquement:

1. **Alignement BWA-MEM** : FASTQ → BAM (avec Read Groups)
2. **GATK HaplotypeCaller** : BAM → VCF (variant calling)
3. **Analyse VCF** : Analyse des variants détectés
4. **Préparation données d'entraînement** : Format JSON pour LLM

## ⏱️ Temps Estimé

- **Par patient**: ~2-4 heures
- **50 patients séquentiels**: ~100-200 heures (~4-8 jours)

## 📁 Fichiers de Suivi

Le script crée automatiquement dans `./data/batch_gatk_50_results/`:

- `progress.json` : Patients traités et échoués
- `results.json` : Résultats détaillés pour chaque patient
- `errors.json` : Erreurs détaillées

## 🔄 Reprendre après Interruption

Le script reprend automatiquement là où il s'est arrêté. Les patients déjà traités sont automatiquement skippés.

## 🔍 Vérifier le Progrès

```bash
# Voir les patients traités
cat data/batch_gatk_50_results/progress.json | jq

# Voir les résultats
cat data/batch_gatk_50_results/results.json | jq '.[] | select(.status == "success") | .patient_id'

# Voir les erreurs
cat data/batch_gatk_50_results/errors.json | jq '.[] | {patient_id, error}'
```

## ✅ Prêt à Lancer !

Tous les fichiers nécessaires sont maintenant en place. Vous pouvez lancer le pipeline avec les commandes ci-dessus.

---

**Dernière mise à jour**: 26 janvier 2026
**Statut**: ✅ Prêt
