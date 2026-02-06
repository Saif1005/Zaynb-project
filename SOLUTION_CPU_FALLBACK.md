# ✅ Solution : Fallback CPU pour Instances sans GPU

## 🎯 Problème

Parabricks nécessite absolument un GPU NVIDIA pour fonctionner. Sur une instance sans GPU, Parabricks échoue avec l'erreur :
```
[Parabricks Options Error]: Could not find accessible GPUs. Please make sure the container options enable GPUs
```

## ✅ Solution Implémentée

J'ai créé un système de **fallback automatique** qui utilise des outils CPU-native (BWA-MEM + GATK) quand Parabricks ne peut pas fonctionner.

### Architecture

1. **ParabricksRunner** tente d'abord d'utiliser Parabricks (si GPU disponible)
2. Si Parabricks échoue à cause de l'absence de GPU, **automatiquement bascule vers CPURunner**
3. **CPURunner** utilise :
   - **BWA-MEM** pour l'alignement FASTQ → BAM (au lieu de Parabricks fq2bam)
   - **GATK HaplotypeCaller** pour l'appel de variants BAM → VCF (au lieu de Parabricks haplotypecaller)

### Fichiers Créés/Modifiés

1. **`src/pipeline/cpu_runner.py`** (nouveau) :
   - Implémente `CPURunner` avec les mêmes méthodes que `ParabricksRunner`
   - Utilise BWA-MEM et GATK via Docker ou installation locale
   - Télécharge/upload les fichiers depuis/vers S3 automatiquement

2. **`src/pipeline/parabricks_runner.py`** (modifié) :
   - Détecte automatiquement les erreurs liées à l'absence de GPU
   - Bascule automatiquement vers `CPURunner` en cas d'échec GPU

## 🚀 Utilisation

**Aucun changement nécessaire !** Le workflow fonctionne automatiquement :

```bash
python scripts/pipeline/run_complete_workflow.py \
  --instance-id i-0822e345e78731721 \
  --ssh-key ~/.ssh/saif-pipeline-complet \
  --fastq-r1 s3://genomic-cancer-pipeline-input-dev-622994489865/patients/PATIENT001/R1.fastq.gz \
  --fastq-r2 s3://genomic-cancer-pipeline-input-dev-622994489865/patients/PATIENT001/R2.fastq.gz \
  --patient-id PATIENT001
```

### Comportement

1. **Avec GPU** : Utilise Parabricks (rapide, optimisé GPU)
2. **Sans GPU** : Bascule automatiquement vers BWA-MEM + GATK (plus lent mais fonctionnel)

## ⚠️ Différences de Performance

| Aspect | Parabricks (GPU) | BWA-MEM + GATK (CPU) |
|--------|------------------|----------------------|
| **Vitesse** | ⚡ Très rapide (minutes) | 🐌 Plus lent (heures) |
| **Précision** | ✅ Excellente | ✅ Excellente |
| **Coût** | 💰 Plus cher (instance GPU) | 💰 Moins cher (instance CPU) |
| **Disponibilité** | 🎯 Nécessite GPU NVIDIA | ✅ Fonctionne partout |

## 📋 Prérequis pour le Mode CPU

Le `CPURunner` installe automatiquement les outils nécessaires, mais vous pouvez aussi les installer manuellement :

```bash
# Sur l'instance EC2
sudo apt-get update
sudo apt-get install -y bwa samtools

# GATK via Docker (recommandé)
docker pull broadinstitute/gatk:latest
```

## 🔍 Logs

Quand le fallback CPU est activé, vous verrez :

```
⚠ Parabricks requires GPU. Falling back to CPU-native pipeline (BWA-MEM)...
This will be slower but will work on instances without GPU
Starting CPU-native BWA-MEM alignment pipeline
...
✓ CPU-native pipeline completed successfully: s3://...
```

## 🎯 Avantages

1. **✅ Compatible avec toutes les instances** : GPU ou CPU
2. **✅ Automatique** : Aucune configuration supplémentaire
3. **✅ Même interface** : Le workflow reste identique
4. **✅ Même résultats** : BWA-MEM et GATK sont des outils standards de référence

## 📝 Notes

- Le mode CPU est **beaucoup plus lent** (peut prendre plusieurs heures au lieu de minutes)
- Pour la production, il est recommandé d'utiliser une instance GPU si possible
- Le fallback CPU est utile pour :
  - Tests et développement
  - Budget limité
  - Instances temporaires sans GPU

---

**💡 Le workflow fonctionne maintenant sur toutes les instances, avec ou sans GPU !**


