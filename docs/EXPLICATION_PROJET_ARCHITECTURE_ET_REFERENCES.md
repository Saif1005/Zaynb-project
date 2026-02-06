# Explication détaillée du projet : Pipeline génomique, GATK, fine-tuning et workflow agentique

Ce document décrit le projet dans son ensemble : le pipeline complet (FASTQ → VCF), GATK en détail, le fine-tuning du modèle LLM, l’intégration dans un workflow agentique, les étapes déjà développées vs à faire, et des références scientifiques pour valider l’approche.

---

## 1. Vue d’ensemble du projet

**Objectif** : Automatiser la détection de variants cancérigènes à partir de séquençage (FASTQ) jusqu’à une prédiction clinique, en combinant :

- Un **pipeline génomique** (alignement + appel de variants) conforme aux bonnes pratiques (BWA-MEM + GATK HaplotypeCaller).
- Une **analyse des variants** (VCF → gènes cancérigènes, TMB, etc.).
- Un **modèle de langage fine-tuné** (Mistral) pour interpréter les variants et prédire un risque cancer.
- Une **orchestration agentique** (multi-agents) pour exécuter tout le workflow de manière automatique.

---

## 2. Pipeline génomique complet (détail des étapes)

Le pipeline va des reads bruts au VCF, puis à l’analyse et à la prédiction.

### 2.1 Chaîne de traitement globale

```
FASTQ (R1, R2)  →  Alignement  →  BAM  →  Appel de variants  →  VCF  →  Analyse  →  Données LLM  →  Fine-tuning / Inférence  →  Rapport
```

### 2.2 Étape 1 : Données d’entrée (FASTQ)

- **Entrée** : paires de fichiers FASTQ (R1, R2) par patient, souvent issus de SRA ou uploadés vers S3.
- **Stockage** : S3 (`genomic-cancer-pipeline-input-*`) avec structure `patients/<PATIENT_ID>/R1.fastq.gz`, `R2.fastq.gz`.
- **Rôle** : Les agents **Data Manager** et les scripts batch gèrent l’upload, la validation et la liste des patients prêts pour le pipeline.

### 2.3 Étape 2 : Alignement (FASTQ → BAM)

- **Outil** : **BWA-MEM** (référence hg38).
- **Sortie** : BAM aligné (coordonnées sur le génome de référence).
- **Implémentation** :
  - **CPU** : `CPURunner` (`src/pipeline/cpu_runner.py`) — SSH vers une EC2, télécharge FASTQ + référence depuis S3, lance BWA-MEM, upload du BAM (et index .bai recréé localement pour éviter « Invalid GZIP header »).
  - **GPU (optionnel)** : Parabricks `fq2bam` via `ParabricksRunner` si une instance avec GPU NVIDIA est utilisée.
- **Référence** : Génome hg38 sur S3 (`genomic-references-*/hg38/hg38.fa`). Index .fai créé côté serveur si absent.

### 2.4 Étape 3 : Appel de variants (BAM → VCF)

- **Outil** : **GATK HaplotypeCaller** (Broad Institute).
- **Entrée** : BAM indexé + référence FASTA (avec .fai).
- **Sortie** : VCF compressé (`variants.vcf.gz`) contenant SNPs/indels.
- **Implémentation** :
  - **CPU** : `CPURunner.run_haplotypecaller` — télécharge BAM + référence, supprime tout .bai existant, recrée l’index BAM avec `samtools index`, crée l’index référence avec `samtools faidx` si besoin, lance GATK en Docker (`broadinstitute/gatk:4.2.6.1`), upload du VCF vers S3.
  - **GPU** : Parabricks HaplotypeCaller via `ParabricksRunner` si disponible.

### 2.5 Étape 4 : Analyse des variants (VCF → variants pathogènes)

- **Module** : `VCFParser` + **VCF Analysis Agent**.
- **Actions** : Téléchargement du VCF depuis S3, parsing avec seuils (QUAL, DP, VAF, `require_pass=False` pour GATK), croisement avec une base de gènes du cancer (`cancer_genes_db`), calcul de métriques (TMB, couverture, résumé des variants).
- **Sortie** : Liste de variants pathogènes/cancer, métadonnées patient, prêtes pour le LLM.

### 2.6 Étape 5 : Données d’entraînement (pour le fine-tuning)

- **Module** : `TrainingDataPreparation` (`src/llm/data_preparation.py`).
- **Entrée** : Résultat de l’analyse VCF (variants, couverture, etc.).
- **Sortie** : Exemples au format conversation (system + user) pour fine-tuning (p.ex. JSONL).
- **Usage** : Alimentation du **LLM Training Agent** et du script `run_finetuning.py` (ou équivalent sur EC2 GPU).

### 2.7 Étape 6 : Fine-tuning du modèle (optionnel)

- **Modèle de base** : Mistral (ou configurable).
- **Méthode** : LoRA/QLoRA (PEFT) pour adapter le modèle au domaine génomique (interprétation de variants, risque cancer).
- **Infra** : EC2 GPU (p3.2xlarge ou similaire), environnement d’entraînement installé via SSH, données uploadées depuis S3 ou local.
- **Module** : `LLMFineTuner` (`src/llm/fine_tuner.py`).

### 2.8 Étape 7 : Prédiction (inférence)

- **Module** : `CancerDetectionInference` + **Prediction Agent**.
- **Entrée** : Variants (et métriques) du patient + modèle fine-tuné (ou modèle de base).
- **Sortie** : Prédiction structurée (cancer détecté ou non, types, niveau de risque, score).

### 2.9 Étape 8 : Rapport

- **Module** : **Report Generator Agent**.
- **Sortie** : Rapport final (texte/HTML/PDF selon implémentation) et éventuellement upload S3.

---

## 3. GATK en détail (alignement + HaplotypeCaller)

### 3.1 Bonnes pratiques GATK (référence scientifique)

Le workflow utilisé s’appuie sur les **GATK Best Practices** décrits dans :

- **Van der Auwera G.A. et al.**, *“From FastQ data to high confidence variant calls: the Genome Analysis Toolkit best practices pipeline”*, **Current Protocols in Bioinformatics**, 2013 (PMC4243306).  
  Ce protocole décrit : prétraitement des reads (alignement, BQSR, etc.), puis découverte de variants avec HaplotypeCaller.

Dans notre projet :

- **Prétraitement** : alignement BWA-MEM → BAM (optionnellement déduplication/ BQSR selon les scripts).
- **Variant calling** : GATK HaplotypeCaller uniquement (germline); pas de MuTect2/somatique dans la version actuelle.

### 3.2 BWA-MEM

- **Rôle** : Aligner les reads FASTQ sur le génome de référence (hg38).
- **Référence** : Algorithme décrit par Li (2013), *“Aligning sequence reads, clone sequences and assembly contigs with BWA-MEM”* (arXiv:1303.3997).
- **Choix** : BWA-MEM est recommandé pour reads ≥ 70 bp (GDC, NVIDIA Parabricks, GATK pipelines). Le projet utilise bien BWA-MEM côté CPU (`CPURunner`) ou Parabricks côté GPU.

### 3.3 GATK HaplotypeCaller

- **Principe** : Assemblage local des reads dans les régions actives, puis appel de variants (SNPs/indels) à partir des haplotypes.
- **Avantages** : Mieux que les callers position-dépendants pour les indels et régions difficiles (documentation GATK + article Van der Auwera ci-dessus).
- **Version utilisée** : GATK 4.2.6.1 (Docker `broadinstitute/gatk:4.2.6.1`).
- **Points techniques dans le code** :
  - Référence : `.fa` + `.fai` (création automatique si .fai manquant sur S3).
  - BAM : index `.bai` **toujours recréé** après téléchargement pour éviter un index obsolète et l’erreur « Invalid GZIP header » dans GATK.

### 3.4 Références pipelines cancer (alignement + variant calling)

- **GDC (NCI)** : *“DNA-Seq: Whole Genome Sequencing Variant Calling”* et *“DNA-Seq: Whole Exome and Targeted Sequencing”* — BWA-MEM pour l’alignement, puis variant callers (somatique/germline). Notre pipeline en est inspiré pour la partie alignement + appel germline.
- **NVIDIA Clara Parabricks** : *“Whole-Genome Small Variant Calling”* — fq2bam + HaplotypeCaller, équivalent accéléré GPU de notre chaîne CPU.

---

## 4. Fine-tuning du modèle et intégration

### 4.1 Données d’entraînement

- **Source** : Sortie du pipeline (VCF analysé) → variants pathogènes, couverture, TMB, etc.
- **Format** : Paires (prompt utilisateur, réponse attendue) ou format chat (system + user + assistant), sauvegardées en JSONL.
- **Rôle** : Enseigner au LLM à interpréter des listes de variants et à produire une décision/texte de type « cancer détecté / types / niveau de risque ».

### 4.2 Modèle et méthode

- **Modèle** : Mistral (ou autre modèle causal configurable dans `llm_config`).
- **Méthode** : Fine-tuning avec **LoRA/QLoRA** (PEFT) pour limiter le coût et la taille des paramètres entraînés.
- **Infrastructure** : EC2 GPU (ex. p3.2xlarge), SSH, environnement Python (PyTorch, Transformers, PEFT). Le fine-tuning peut être lancé via `LLMFineTuner` ou les scripts dans `scripts/training/`.

### 4.3 Intégration dans le workflow

- **Option 1 – Pipeline agentique** : L’**LLM Training Agent** prépare les données (à partir du contexte VCF) et lance le fine-tuning si `auto_train` (ou équivalent) est activé ; le **Prediction Agent** charge ensuite le modèle (fine-tuné ou de base) et fait l’inférence.
- **Option 2 – Batch** : `batch_process_patients.py` fait FASTQ → BAM → VCF → analyse → préparation des données d’entraînement (JSONL par patient ou consolidé) ; le fine-tuning peut être lancé séparément sur ces JSONL.
- **Option 3 – Workflow manuel** : `run_complete_workflow.py` enchaîne Parabricks (ou CPU) → préparation données → fine-tuning Mistral → détection cancer, sans passer par les agents.

### 4.4 Références scientifiques (LLM + génomique / cancer)

- **Benchmarking LLM pour variants cancéreux** : *“Benchmarking large language models GPT-4o, Llama 3.1, and Qwen 2.5 for cancer genetic variant classification”* (Nature, 2025) — évalue les LLM sur la classification de variants (OncoKB, CIViC, rapports réels). Montre que le fine-tuning et le prompt engineering améliorent les performances.
- **RAG + fine-tuning en génomique** : *“Boosting GPT models for genomics analysis: generating trusted genetic variant annotations and interpretations through RAG and Fine-tuning”* (PMC11842050) — combinaison RAG + fine-tuning pour l’annotation et l’interprétation de variants.
- **Intégration LLM + bases de variants cancer** : *“CIViC MCP: Integrating Large Language Models with the Clinical Interpretations of Variants in Cancer”* (PMC12632937) — utilisation de LLM avec des bases cliniques (CIViC, etc.), cohérent avec l’usage de `cancer_genes_db` et de l’analyse VCF dans ce projet.

---

## 5. Workflow agentique (orchestration automatique)

### 5.1 Architecture multi-agents

Le workflow « tout automatique » est piloté par un **Orchestrator** qui enchaîne des agents spécialisés :

| Agent | Rôle |
|-------|------|
| **OrchestratorAgent** | Coordonne les étapes, valide les entrées, gère les échecs et le contexte partagé. |
| **DataManagerAgent** | Upload/validation des FASTQ, préparation des chemins S3, mise à jour du contexte. |
| **ParabricksAgent** | Exécute le pipeline génomique (fq2bam + HaplotypeCaller) ; utilise **ParabricksRunner** (GPU). Pas encore de bascule automatique vers **CPURunner** dans cet agent. |
| **VCFAnalysisAgent** | Télécharge le VCF depuis S3, parse, filtre, croise avec les gènes cancer, calcule TMB/couverture, produit les variants pour le LLM. |
| **LLMTrainingAgent** | Prépare les données d’entraînement et lance le fine-tuning si demandé (optionnel). |
| **PredictionAgent** | Charge le modèle (fine-tuné ou base) et appelle `CancerDetectionInference` pour la prédiction cancer. |
| **ReportGeneratorAgent** | Génère le rapport final (et optionnellement l’upload S3). |

### 5.2 Flux d’exécution (agentic)

```
run_agentic_pipeline.py
    → OrchestratorAgent.run(context)
        → 1. DataManagerAgent   (upload / validation FASTQ)
        → 2. ParabricksAgent   (fq2bam + HaplotypeCaller)  [actuellement Parabricks uniquement]
        → 3. VCFAnalysisAgent  (parse VCF, variants pathogènes)
        → 4. LLMTrainingAgent   (préparation + fine-tuning optionnel)
        → 5. PredictionAgent   (inférence LLM)
        → 6. ReportGeneratorAgent (rapport)
```

### 5.3 Références (orchestration / agentic AI)

- **AWS** : *“Workflow orchestration agents”* et *“Workflow for orchestration”* (Prescriptive Guidance) — orchestration hiérarchique, un agent coordinateur délègue à des agents spécialisés, état et événements.
- **AgentOrchestra** : *“AgentOrchestra: A Hierarchical Multi-Agent Framework for General-Purpose Task Solving”* (arXiv) — modèle hiérarchique (planning agent + workers), analogue à notre Orchestrator + agents métier.

---

## 6. Ce qui est développé vs ce qui reste à faire

### 6.1 Développé (implémenté et utilisé)

| Composant | Détail |
|-----------|--------|
| **Pipeline CPU (BWA + GATK)** | `CPURunner` : SSH, S3, BWA-MEM, GATK HaplotypeCaller, gestion index BAM/FASTA. |
| **Pipeline GPU (Parabricks)** | `ParabricksRunner` : fq2bam + HaplotypeCaller sur GPU. |
| **Batch patients** | `batch_process_patients.py` : traitement par lots avec **CPURunner**, suivi (progress, errors, results). |
| **Analyse VCF** | `VCFParser`, seuils configurables, gènes cancer, TMB ; **VCF Analysis Agent**. |
| **Préparation données LLM** | `TrainingDataPreparation`, format chat, export JSONL. |
| **Fine-tuning** | `LLMFineTuner` : env GPU EC2, upload données, lancement entraînement LoRA/QLoRA. |
| **Inférence** | `CancerDetectionInference` : chargement Mistral + adapters PEFT, `analyze_patient`. |
| **Agents** | Tous les agents listés ci-dessus + base (`BaseAgent`, `AgentResult`, etc.). |
| **Orchestrateur** | `OrchestratorAgent` : enchaînement des 6 étapes, gestion erreurs, contexte. |
| **Scripts d’entrée** | `run_agentic_pipeline.py` (1 patient, agentic), `run_complete_workflow.py` (workflow manuel), `batch_process_patients.py` (batch CPU). |
| **Infrastructure** | Terraform (S3, IAM, API, batch, Step Functions), config AWS, EC2, S3. |

### 6.2 Partiellement fait ou à renforcer

| Composant | État |
|-----------|------|
| **Bascule CPU/GPU dans l’agent** | ParabricksAgent utilise uniquement ParabricksRunner ; pas de fallback automatique vers CPURunner si pas de GPU (fallback CPU existe dans le batch, pas dans l’orchestrator agentique). |
| **BQSR / déduplication** | Pas de MarkDuplicates ni BQSR dans le pipeline actuel ; possible à ajouter pour se rapprocher à 100 % des GATK Best Practices. |
| **Appel somatique** | HaplotypeCaller germline uniquement ; pas de MuTect2 (tumeur/normal) pour variants somatiques. |
| **RAG** | Pas d’intégration RAG (bases type CIViC/OncoKB) dans l’inférence ; uniquement fine-tuning + prompt. |
| **Rapport** | ReportGeneratorAgent présent ; contenu et format (HTML/PDF) à préciser ou étendre. |
| **API / Step Functions** | Routes et modules existent ; liaison complète « upload → Step Functions → agents » à finaliser selon la cible déploiement. |

### 6.3 À faire (recommandations)

1. **Agentic** : Dans `ParabricksAgent`, détecter l’absence de GPU ou l’échec Parabricks et basculer automatiquement sur `CPURunner` (comme en batch).
2. **Pipeline** : Ajouter MarkDuplicates + BQSR (GATK) avant HaplotypeCaller pour coller aux best practices.
3. **Somatique** : Si besoin clinique, ajouter une branche tumeur/normal avec MuTect2 (ou autre caller somatique).
4. **LLM** : Enrichir avec RAG (CIViC, OncoKB) pour améliorer l’interprétation des variants (références PMC11842050, PMC12632937).
5. **Rapport** : Finaliser template et sortie (PDF/HTML) du Report Generator.
6. **Tests** : Tests d’intégration sur un patient de bout en bout (agentic + batch) et validation des sorties VCF/LLM.

---

## 7. Schéma d’architecture (texte)

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                     UTILISATEUR / SYSTÈME                         │
                    │  run_agentic_pipeline.py | batch_process_patients.py | API         │
                    └───────────────────────────────┬─────────────────────────────────┘
                                                    │
                    ┌───────────────────────────────▼───────────────────────────────┐
                    │              OrchestratorAgent (orchestration)                 │
                    │  Valide entrée, enchaîne les agents, gère erreurs et contexte   │
                    └───┬─────┬─────┬─────┬─────┬─────┬───────────────────────────────┘
                        │     │     │     │     │     │
        ┌────────────────┘     │     │     │     │     └────────────────┐
        │                      │     │     │     │                      │
        ▼                      ▼     ▼     ▼     ▼                      ▼
┌───────────────┐    ┌───────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ DataManager   │    │ Parabricks    │  │ VCF Analysis │  │ LLM Training │  │ Prediction   │  │ Report       │
│ Agent         │───▶│ Agent         │──▶│ Agent        │──▶│ Agent         │──▶│ Agent        │──▶│ Generator    │
│ Upload/valid  │    │ (ou CPU*)     │  │ Parse VCF   │  │ Fine-tune    │  │ Inférence    │  │ Agent        │
└───────────────┘    └───────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────────────┘  └──────────────┘
                             │                 │                 │
                    ┌────────▼────────┐  ┌──────▼───────┐  ┌──────▼───────┐
                    │ Parabricks     │  │ VCFParser    │  │ LLMFineTuner │
                    │ Runner (GPU)   │  │ cancer_genes │  │ PEFT/LoRA    │
                    │ ou CPURunner   │  │ TMB, etc.   │  │              │
                    │ (BWA+GATK)     │  └──────────────┘  └──────────────┘
                    └────────┬──────┘
                             │
                    ┌────────▼────────┐
                    │ S3 (FASTQ,      │
                    │ BAM, VCF, ref)  │
                    │ EC2 (SSH)       │
                    └─────────────────┘

* Aujourd’hui le batch utilise CPURunner ; l’agent Parabricks n’utilise que ParabricksRunner.
```

---

## 8. Références scientifiques (résumé pour validation du projet)

| Domaine | Référence | Lien avec le projet |
|---------|-----------|----------------------|
| **Pipeline GATK** | Van der Auwera et al., *Current Protocols in Bioinformatics*, 2013 (PMC4243306) | Bonnes pratiques FASTQ → variants ; BWA + GATK HaplotypeCaller. |
| **Alignement** | Li (2013), BWA-MEM (arXiv:1303.3997) ; GDC DNA-Seq pipelines | BWA-MEM pour reads courts/longs, cohérent avec notre alignement. |
| **Variants cancer** | GDC DNA-Seq WGS/WES ; NVIDIA Parabricks WGS small variant | Même logique alignement + appel de variants (germline/small variant). |
| **LLM + variants** | Nature 2025, benchmarking GPT-4o, Llama 3.1, Qwen 2.5 pour variants cancer | Justifie l’usage de LLM + fine-tuning pour la classification de variants. |
| **RAG + fine-tuning** | PMC11842050, “Boosting GPT models for genomics analysis” | RAG + fine-tuning pour annotations/interprétation ; extension possible du projet. |
| **CIViC / clinique** | PMC12632937, CIViC MCP + LLM | Alignement avec l’usage de bases gènes cancer et interprétation clinique. |
| **Orchestration** | AWS Workflow orchestration agents ; AgentOrchestra (arXiv) | Modèle hiérarchique orchestrator + agents spécialisés, comme dans ce projet. |

---

## 9. Conclusion

- Le **pipeline** (FASTQ → BAM → VCF) est implémenté avec **BWA-MEM** et **GATK HaplotypeCaller**, avec une chaîne CPU opérationnelle (`CPURunner`) et une option GPU (Parabricks).  
- Le **fine-tuning** (Mistral, LoRA/QLoRA) et l’**inférence** sont branchés sur les sorties VCF analysées et s’appuient sur des pratiques validées par la littérature (LLM pour variants, RAG/fine-tuning).  
- L’**orchestration agentique** (Orchestrator + 6 agents) permet d’exécuter le workflow de manière automatique ; le maillon encore « manquant » côté agentic est le fallback automatique GPU → CPU dans ParabricksAgent.  
- Les **étapes restantes** concernent surtout : renforcement des bonnes pratiques (BQSR, déduplication), option somatique (MuTect2), RAG, et finalisation rapport / déploiement API–Step Functions.

Ce document et les références citées permettent de justifier la validité scientifique et technique du projet (alignement, GATK, LLM, orchestration) dans un rapport ou une thèse.
