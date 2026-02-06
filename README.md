# 🧬 Genomic Cancer Detection Pipeline - Agentic AI

Pipeline automatique de détection de cancer utilisant l'analyse génomique et l'IA générative.

## 🎯 Vue d'Ensemble

Ce projet implémente un système **Agentic AI** qui automatise complètement le processus de détection de cancer :

1. **Upload** de séquences d'ADN brutes (FASTQ)
2. **Pipeline Parabricks** (alignement et appel de variants)
3. **Analyse des variants** pathogènes
4. **Fine-tuning** du modèle Mistral (optionnel)
5. **Prédiction** de cancer avec LLM
6. **Génération** de rapport complet

## 🏗️ Architecture

### Agents Spécialisés

- **Orchestrator** : Coordonne tous les agents
- **Data Manager** : Gestion upload et validation
- **Parabricks** : Pipeline génomique (fq2bam + HaplotypeCaller)
- **VCF Analysis** : Analyse des variants
- **LLM Training** : Fine-tuning Mistral
- **Prediction** : Prédiction cancer
- **Report Generator** : Génération rapports

### Infrastructure AWS

- **ECS Fargate** : API Server
- **Step Functions** : Orchestration
- **Lambda** : Agents légers
- **EC2 GPU** : Parabricks + LLM Training
- **S3** : Stockage fichiers
- **DynamoDB** : État des exécutions

## 🚀 Démarrage Rapide

### Prérequis

- Python 3.12+
- AWS CLI configuré
- Instance EC2 configurée
- Buckets S3 créés

### Installation

```bash
# Cloner le projet
git clone <repository>
cd projet_zaynb

# Créer environnement virtuel
python -m venv genomic-env
source genomic-env/bin/activate  # Linux/Mac
# ou
genomic-env\Scripts\activate  # Windows

# Installer dépendances
pip install -r requirements.txt
```

### Configuration

```bash
# Copier le template
cp .env.example .env

# Éditer .env avec vos valeurs AWS
nano .env
```

### Utilisation

#### Option 1 : Ligne de Commande

```bash
python scripts/agents/run_agentic_pipeline.py \
    --patient-id PATIENT001 \
    --fastq-r1 ./data/sample_R1.fastq.gz \
    --fastq-r2 ./data/sample_R2.fastq.gz \
    --instance-id i-xxxxxxxxxxxxx \
    --ssh-key ~/.ssh/genomic-pipeline \
    --train-llm
```

#### Option 2 : API REST

```bash
# Démarrer l'API
python scripts/api/start_api.py

# Upload via curl
curl -X POST "http://localhost:8000/api/v1/pipeline/upload" \
  -F "patient_id=PATIENT001" \
  -F "fastq_r1=@sample_R1.fastq.gz" \
  -F "fastq_r2=@sample_R2.fastq.gz"
```

#### Option 3 : Interface Web

```bash
streamlit run scripts/web/start_web_ui.py
```

## 📚 Documentation

### Guides Principaux
- **[GUIDE_COMPLET.md](GUIDE_COMPLET.md)** : Guide complet (déploiement, entraînement, utilisation)
- **[QUICK_START_AWS.md](QUICK_START_AWS.md)** : Démarrage rapide AWS
- **[README_AWS.md](README_AWS.md)** : Vue d'ensemble AWS

### Documentation Détaillée
- **[Architecture](docs/ARCHITECTURE.md)** : Architecture complète du système
- **[Déploiement](docs/DEPLOYMENT.md)** : Guide de déploiement sur AWS
- **[Utilisation](docs/USAGE.md)** : Guide d'utilisation détaillé

## 🧪 Tests

```bash
# Lancer tous les tests
pytest tests/

# Tests spécifiques
pytest tests/test_agents.py
pytest tests/test_api.py
```

## 🚀 Déploiement sur AWS

```bash
# Déploiement automatique
bash scripts/deployment/deploy_to_aws.sh

# Ou manuel avec Terraform
cd terraform/environments/dev
terraform init
terraform apply
```

## 📁 Structure du Projet

```
projet_zaynb/
├── src/              # Code source
├── scripts/          # Scripts d'exécution
├── tests/            # Tests
├── terraform/        # Infrastructure AWS
├── docker/           # Dockerfiles
└── docs/             # Documentation
```

## 🤝 Contribution

1. Fork le projet
2. Créer une branche (`git checkout -b feature/AmazingFeature`)
3. Commit (`git commit -m 'Add AmazingFeature'`)
4. Push (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

## 📝 License

Ce projet est sous licence MIT.

## 📞 Support

Pour toute question, ouvrir une issue sur GitHub.

---**Pipeline Agentic AI pour la détection de cancer - Prêt pour la production ! 🎉**