/** Diagramme Mermaid — architecture multi-agents du projet Zaynb */
export const ARCHITECTURE_MERMAID = `
flowchart TB
    classDef client fill:#881337,stroke:#f43f5e,color:#fff,stroke-width:2px
    classDef host fill:#4c1d95,stroke:#7c3aed,color:#fff,stroke-width:2px
    classDef agent fill:#0c4a6e,stroke:#0ea5e9,color:#e0f2fe,stroke-width:2px
    classDef pipe fill:#1e293b,stroke:#64748b,color:#f1f5f9,stroke-width:2px

    subgraph HARNESS["Harness — OrchestratorAgent · LangChain"]
        direction TB
        CLIENT["Entrée UI<br/>run_agentic_pipeline"]:::client
        MASTER["OrchestratorAgent<br/>contexte partagé"]:::host
        subgraph AGENTS["Agents src/agents/"]
            direction LR
            AG1["DataManagerAgent"]:::agent
            AG2["ParabricksAgent<br/>BWA·GATK"]:::agent
            AG3["VCFAnalysisAgent"]:::agent
            AG4["LLMTrainingAgent<br/>LoRA"]:::agent
            AG5["PredictionAgent<br/>Mistral"]:::agent
            AG6["ReportGeneratorAgent"]:::agent
        end
    end

    subgraph PIPELINE["Pipeline bio-informatique — S3"]
        direction LR
        S1["FASTQ"]:::pipe
        S2["BAM"]:::pipe
        S3["VCF"]:::pipe
        S4["JSONL"]:::pipe
        S5["LoRA"]:::pipe
        S6["Rapport"]:::pipe
    end

    CLIENT ==> MASTER
    MASTER ==> AG1 ==> AG2 ==> AG3 ==> AG4 ==> AG5 ==> AG6 ==> CLIENT
    S1 --> S2 --> S3 --> S4 --> S5 --> S6
`.trim();

export type EdgePair = [from: string, to: string];

export type WorkflowStep = {
  id: string;
  tag: string;
  title: string;
  description: string;
  dataLabel: string;
  transport: string;
  highlight: EdgePair[];
};

export const WORKFLOW_STEPS: WorkflowStep[] = [
  {
    id: 'client',
    tag: 'Entrée',
    title: 'Requête utilisateur',
    description: 'Lancement via run_agentic_pipeline.py avec patient_id et chemins FASTQ/VCF S3.',
    dataLabel: 'patient_id · contexte',
    transport: 'Requête',
    highlight: [['CLIENT', 'MASTER']],
  },
  {
    id: 'master',
    tag: 'OrchestratorAgent',
    title: 'Planification Harness',
    description: 'Validation des entrées et délégation séquentielle aux agents métier.',
    dataLabel: 'Contexte partagé',
    transport: 'Contexte',
    highlight: [['MASTER', 'AG1']],
  },
  {
    id: 'ag1',
    tag: 'DataManagerAgent',
    title: 'Validation FASTQ',
    description: 'Upload et validation R1/R2 sur S3 (patients/<ID>/).',
    dataLabel: 'FASTQ R1/R2',
    transport: 'FASTQ',
    highlight: [['AG1', 'AG2']],
  },
  {
    id: 'ag2',
    tag: 'ParabricksAgent',
    title: 'BWA-MEM + GATK HaplotypeCaller',
    description: 'ParabricksRunner (GPU) ou CPURunner (EC2) : FASTQ → BAM → VCF.',
    dataLabel: 'variants.vcf.gz',
    transport: 'VCF',
    highlight: [['AG2', 'AG3']],
  },
  {
    id: 'ag3',
    tag: 'VCFAnalysisAgent',
    title: 'Analyse variants',
    description: 'VCFParser, cancer_genes_db, TMB → vcf_metrics pour le bioLLM.',
    dataLabel: 'Variants pathogènes',
    transport: 'Variants',
    highlight: [['AG3', 'AG4']],
  },
  {
    id: 'ag4',
    tag: 'LLMTrainingAgent',
    title: 'Fine-tuning LoRA',
    description: 'TrainingDataPreparation + LLMFineTuner (Mistral/BioGPT, optionnel).',
    dataLabel: 'JSONL · adapters PEFT',
    transport: 'JSONL',
    highlight: [['AG4', 'AG5']],
  },
  {
    id: 'ag5',
    tag: 'PredictionAgent',
    title: 'Inférence clinique',
    description: 'CancerDetectionInference — score et diagnostic structuré.',
    dataLabel: 'Score cancer',
    transport: 'Score',
    highlight: [['AG5', 'AG6']],
  },
  {
    id: 'ag6',
    tag: 'ReportGeneratorAgent',
    title: 'Rapport final',
    description: 'Synthèse pipeline + prédiction, diffusion vers le client.',
    dataLabel: 'Rapport clinique',
    transport: 'Rapport',
    highlight: [['AG6', 'CLIENT']],
  },
];
