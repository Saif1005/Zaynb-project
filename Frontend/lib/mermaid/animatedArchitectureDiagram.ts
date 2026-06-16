/** Diagramme Harness — chemins de raisonnement + charge utile par flèche */
export const ANIMATED_ARCHITECTURE_MERMAID = `
flowchart TB
    classDef client fill:#881337,stroke:#f43f5e,color:#fff
    classDef host fill:#4c1d95,stroke:#7c3aed,color:#fff
    classDef agent fill:#0c4a6e,stroke:#0ea5e9,color:#e0f2fe
    classDef tool fill:#064e3b,stroke:#10b981,color:#d1fae5
    classDef pipe fill:#1e293b,stroke:#64748b,color:#f1f5f9

    subgraph HARNESS["Architecture Harness — Système multi-agents AGI"]
        direction TB

        subgraph CLIENT["① Couche Client"]
            UI["Interface utilisateur / API"]:::client
        end

        subgraph HOST["② Couche Host"]
            MASTER["OrchestratorAgent<br/>(LangChain ReAct)"]:::host
        end

        subgraph AGENTS["③ Couche Agents"]
            direction LR
            AG1["DataManager"]:::agent
            AG2["Parabricks"]:::agent
            AG3["VCF Analysis"]:::agent
            AG4["LLM Training<br/>1× one-shot"]:::agent
            AG5["Prediction"]:::agent
            AG6["Report Generator"]:::agent
        end

        subgraph TOOLS["④ Couche Tools"]
            direction TB
            T1["S3 / EC2"]:::tool
            T2["BWA-MEM / GATK"]:::tool
            T3["VCFParser"]:::tool
            T4["PEFT / LoRA"]:::tool
            T5["Inférence LLM"]:::tool
            T6["Génération PDF"]:::tool
        end
    end

    UI -->|"1. [Intention: Lancer analyse patient]<br/>Flux: {patient_id, fastq_R1, fastq_R2}"| MASTER
    MASTER -->|"2. [Planification: Préparer infra S3]<br/>Flux: {task: 'upload_validate'}"| AG1
    AG1 -->|"3. [Raisonnement: FASTQ prêts, alignement]<br/>Flux: {s3_fastq_paths, ref: 'hg38'}"| AG2
    AG2 -->|"4. [Raisonnement: Variants trouvés, extraire]<br/>Flux: {vcf_file: 'variants.vcf.gz'}"| AG3
    AG3 -->|"5. [Raisonnement: Gènes identifiés, préparer LLM]<br/>Flux: {cancer_genes_list, tmb_score}"| AG4
    AG4 -->|"6. [Raisonnement: Modèle adapté, prédire]<br/>Flux: {lora_weights_path, variant_context}"| AG5
    AG5 -->|"7. [Raisonnement: Diagnostic fait, synthétiser]<br/>Flux: {cancer_risk: 'High', details}"| AG6
    AG6 -.->|"8. [Validation orchestrateur + clôture]<br/>Flux: {report_url, orchestrator_validated: true}"| MASTER

    AG1 --> T1
    AG2 --> T2
    AG3 --> T3
    AG4 --> T4
    AG5 --> T5
    AG6 --> T6
`.trim();

export type NodePair = [from: string, to: string];

export type ArchWorkflowStep = {
  id: number;
  agent: string;
  title: string;
  payload: string;
  delegation: NodePair;
  tool?: NodePair;
  toolName?: string;
  /** Agent exécuté une seule fois (fine-tuning LoRA optionnel) */
  oneShot?: boolean;
  oneShotNode?: string;
  /** Retour rapport validé par l'orchestrateur avant livraison client */
  orchestratorValidation?: boolean;
  validationNode?: string;
};

/** Étapes du workflow — délégation + exécution tool externe */
export const ARCH_WORKFLOW: ArchWorkflowStep[] = [
  {
    id: 1,
    agent: 'Client UI',
    title: 'Intention — lancer analyse patient',
    payload: '{patient_id, fastq_R1, fastq_R2}',
    delegation: ['UI', 'MASTER'],
  },
  {
    id: 2,
    agent: 'DataManager',
    title: 'Planification — validation infra S3',
    payload: "{task: 'upload_validate'}",
    delegation: ['MASTER', 'AG1'],
    tool: ['AG1', 'T1'],
    toolName: 'S3 / EC2',
  },
  {
    id: 3,
    agent: 'Parabricks',
    title: 'Alignement FASTQ → BAM (hg38)',
    payload: "{s3_fastq_paths, ref: 'hg38'}",
    delegation: ['AG1', 'AG2'],
    tool: ['AG2', 'T2'],
    toolName: 'BWA-MEM / GATK',
  },
  {
    id: 4,
    agent: 'VCF Analysis',
    title: 'Extraction variants pathogènes',
    payload: "{vcf_file: 'variants.vcf.gz'}",
    delegation: ['AG2', 'AG3'],
    tool: ['AG3', 'T3'],
    toolName: 'VCFParser',
  },
  {
    id: 5,
    agent: 'LLM Training',
    title: 'Fine-tuning LoRA — exécution unique (one-shot)',
    payload: '{cancer_genes_list, tmb_score}',
    delegation: ['AG3', 'AG4'],
    tool: ['AG4', 'T4'],
    toolName: 'PEFT / LoRA',
    oneShot: true,
    oneShotNode: 'AG4',
  },
  {
    id: 6,
    agent: 'Prediction',
    title: 'Inférence risque cancer',
    payload: '{lora_weights_path, variant_context}',
    delegation: ['AG4', 'AG5'],
    tool: ['AG5', 'T5'],
    toolName: 'Inférence LLM',
  },
  {
    id: 7,
    agent: 'Report Generator',
    title: 'Synthèse rapport clinique',
    payload: "{cancer_risk: 'High', details}",
    delegation: ['AG5', 'AG6'],
    tool: ['AG6', 'T6'],
    toolName: 'Génération PDF',
  },
  {
    id: 8,
    agent: 'OrchestratorAgent',
    title: 'Validation du rapport — clôture et retour client',
    payload: "{report_url, orchestrator_validated: true, status: 'success'}",
    delegation: ['AG6', 'MASTER'],
    orchestratorValidation: true,
    validationNode: 'MASTER',
  },
];
