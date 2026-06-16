export type JobStatus = 'queued' | 'running' | 'completed' | 'failed';

export interface AnalyzeRequest {
  patient_id: string;
  s3_uri_r1: string;
  s3_uri_r2: string;
}

export interface AnalyzeResponse {
  job_id: string;
  status: JobStatus;
  patient_id: string;
  message: string;
}

export interface GATKMetrics {
  QUAL?: number | null;
  DP?: number | null;
  VAF?: number | null;
}

export interface PathogenicVariant {
  gene: string;
  chromosome: string;
  position: number;
  mutation: string;
  gatk_metrics: GATKMetrics;
  pathogenicity?: string;
  inheritance?: string | null;
}

export interface GenomicFindings {
  breast_cancer_panel_analyzed?: string[];
  pathogenic_variants_detected: PathogenicVariant[];
  breast_cancer_risk_detected?: boolean;
  identified_pathogenic_genes?: string[];
}

export interface SystemMetrics {
  execution_time_seconds: number;
  pipeline_engine: string;
  hardware: string;
  steps_completed: string[];
}

export interface ClinicalPrediction {
  model: string;
  risk_level: string;
  diagnostic_conclusion: string;
  clinical_summary: string;
  legal_disclaimer: string;
  status: string;
}

export interface ClinicalReport {
  report_id: string;
  patient_id: string;
  generated_at: string;
  system_metrics: SystemMetrics;
  genomic_findings: GenomicFindings;
  clinical_prediction: ClinicalPrediction;
  report_s3?: string | null;
}

export interface JobStatusResponse {
  job_id: string;
  status: JobStatus;
  patient_id: string;
  created_at: string;
  updated_at: string;
  mode?: string | null;
  vcf_s3?: string | null;
  current_step?: string | null;
  progress_message?: string | null;
  steps_completed: string[];
  error?: string | null;
  result?: ClinicalReport | null;
}

export interface HealthResponse {
  status: string;
  service: string;
  orchestrator?: string;
  use_orchestrator?: boolean;
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface AssistantChatRequest {
  message: string;
  history?: ChatMessage[];
  context?: Record<string, unknown>;
}

export interface AssistantChatResponse {
  reply: string;
  intent: string;
  action_taken?: string | null;
  job_id?: string | null;
  patient_id?: string | null;
  missing_fields: string[];
  parsed: Record<string, unknown>;
}

export interface UploadFastqParams {
  patient_id: string;
  fastq_r1: File;
  fastq_r2: File;
}

export type PipelineStepId =
  | 'data_manager'
  | 'parabricks'
  | 'genomic_pipeline'
  | 'vcf_analysis'
  | 'prediction'
  | 'report';

export interface PipelineStep {
  id: PipelineStepId;
  label: string;
  description: string;
}
