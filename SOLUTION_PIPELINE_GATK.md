# 🔧 Solution: Pipeline GATK pour 50 Patients

## ❌ Problème Identifié

Le script `run_gatk_batch_50_patients.py` échoue à cause de:
1. **Erreur d'import** : `CPURunner` manquant (✅ CORRIGÉ)
2. **Problème de connectivité DNS** : Impossible de se connecter à AWS EC2 depuis WSL

## ✅ Solution Recommandée

Utiliser le script **`batch_process_patients.py`** qui est déjà conçu pour gérer ces problèmes et qui utilise `CPURunner` directement.

## 🚀 Utilisation

### Étape 1: Préparer la liste des patients avec FASTQ

```bash
cd /mnt/c/Users/saifa/projet_zaynb

# Créer un fichier JSON avec les 50 patients qui ont des FASTQ
python3 << 'EOF'
import json
import subprocess
from pathlib import Path

patients_file = Path('data/patients_list.json')
with open(patients_file) as f:
    patients = json.load(f)

bucket = 'genomic-cancer-pipeline-input-dev-622994489865'
patients_with_fastq = []

for patient in patients[:60]:
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
        print(f'✅ {patient_id}')
        if len(patients_with_fastq) >= 50:
            break

# Sauvegarder
output_file = Path('data/patients_with_fastq_50.json')
with open(output_file, 'w') as f:
    json.dump(patients_with_fastq, f, indent=2)

print(f'\n✅ {len(patients_with_fastq)} patients sauvegardés dans {output_file}')
EOF
```

### Étape 2: Lancer le pipeline batch

```bash
python scripts/pipeline/batch_process_patients.py \
    --instance-id i-0822e345e78731721 \
    --ssh-key ~/.ssh/saif-pipeline-complet \
    --patients-file data/patients_with_fastq_50.json \
    --max-workers 1 \
    --output-dir ./data/batch_gatk_50_results
```

## 📋 Ce que fait le script batch_process_patients.py

Pour chaque patient, il exécute:
1. **Alignement** : FASTQ → BAM (via BWA-MEM sur CPU)
2. **Variant Calling** : BAM → VCF (via GATK HaplotypeCaller)
3. **Analyse VCF** : Analyse des variants détectés
4. **Préparation données d'entraînement** : Format JSON pour LLM

## ⚙️ Options du Script

- `--instance-id`: ID de l'instance EC2 (défaut: i-0822e345e78731721)
- `--ssh-key`: Chemin vers la clé SSH
- `--patients-file`: Fichier JSON avec la liste des patients
- `--max-workers`: Nombre de patients en parallèle (recommandé: 1)
- `--output-dir`: Répertoire pour sauvegarder les résultats
- `--resume`: Reprendre là où on s'est arrêté (défaut: True)

## 📊 Suivi du Progrès

Le script crée automatiquement:
- `progress.json`: Patients traités et échoués
- `results.json`: Résultats détaillés
- `errors.json`: Erreurs détaillées

### Vérifier le progrès

```bash
# Voir les patients traités
cat data/batch_gatk_50_results/progress.json | jq

# Voir les résultats
cat data/batch_gatk_50_results/results.json | jq '.[] | select(.status == "success") | .patient_id'

# Voir les erreurs
cat data/batch_gatk_50_results/errors.json | jq '.[] | {patient_id, error}'
```

## 🔄 Reprendre après Interruption

Le script reprend automatiquement. Pour forcer une reprise:

```bash
python scripts/pipeline/batch_process_patients.py \
    --instance-id i-0822e345e78731721 \
    --ssh-key ~/.ssh/saif-pipeline-complet \
    --patients-file data/patients_with_fastq_50.json \
    --max-workers 1 \
    --output-dir ./data/batch_gatk_50_results \
    --resume
```

## ⏱️ Temps Estimé

- **Par patient**: ~2-4 heures (selon la taille des FASTQ)
- **50 patients séquentiels**: ~100-200 heures (~4-8 jours)

## 🐛 Résolution de Problèmes

### Problème: Erreur SSH

```bash
# Tester la connexion SSH
ssh -i ~/.ssh/saif-pipeline-complet ubuntu@15.188.127.194 "echo 'Connection OK'"
```

### Problème: Instance Arrêtée

```bash
# Redémarrer l'instance
aws ec2 start-instances --instance-ids i-0822e345e78731721 --region eu-west-3

# Attendre qu'elle soit prête
aws ec2 wait instance-running --instance-ids i-0822e345e78731721 --region eu-west-3
```

### Problème: Espace Disque

```bash
# Vérifier l'espace sur l'instance
ssh -i ~/.ssh/saif-pipeline-complet ubuntu@15.188.127.194 "df -h"
```

## 📝 Notes Importantes

1. **Le script utilise CPURunner** : Il fait l'alignement et le variant calling sur CPU (pas Parabricks/GPU)
2. **Traitement séquentiel recommandé** : Utiliser `--max-workers 1` pour éviter la saturation
3. **Reprise automatique** : Le script reprend automatiquement après interruption
4. **Résultats sur S3** : Les BAM et VCF sont sauvegardés sur S3 automatiquement

---

**Dernière mise à jour**: 26 janvier 2026
**Statut**: Prêt à l'utilisation
