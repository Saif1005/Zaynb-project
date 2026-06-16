import axios from 'axios';
import type {
  AnalyzeRequest,
  AnalyzeResponse,
  AssistantChatRequest,
  AssistantChatResponse,
  HealthResponse,
  JobStatusResponse,
  UploadFastqParams,
} from '@/types/api';

const baseURL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL,
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
});

export const uploadClient = axios.create({
  baseURL,
  timeout: 3_600_000,
});

export async function checkHealth(): Promise<HealthResponse> {
  const { data } = await apiClient.get<HealthResponse>('/health');
  return data;
}

export async function startAnalysis(
  payload: AnalyzeRequest,
): Promise<AnalyzeResponse> {
  const { data } = await apiClient.post<AnalyzeResponse>(
    '/api/v1/analyze',
    payload,
  );
  return data;
}

export async function getJobStatus(jobId: string): Promise<JobStatusResponse> {
  const { data } = await apiClient.get<JobStatusResponse>(
    `/api/v1/jobs/${jobId}`,
  );
  return data;
}

export async function getClinicalReport(jobId: string) {
  const { data } = await apiClient.get(`/api/v1/jobs/${jobId}/report`);
  return data;
}

export async function sendAssistantMessage(
  payload: AssistantChatRequest,
): Promise<AssistantChatResponse> {
  const { data } = await apiClient.post<AssistantChatResponse>(
    '/api/v1/assistant/chat',
    payload,
  );
  return data;
}

export function formatApiError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const status = err.response?.status;
    const detail = err.response?.data;
    if (status === 404) {
      return 'Endpoint assistant introuvable — redéployez l\'API (bash scripts/deployment/restart_api_ec2.sh).';
    }
    if (status === 0 || err.code === 'ERR_NETWORK') {
      return `Réseau/CORS : impossible de joindre ${baseURL}. Vérifiez CORS_ORIGINS sur l'API.`;
    }
    if (typeof detail === 'string') return detail;
    if (detail && typeof detail === 'object' && 'detail' in detail) {
      return String((detail as { detail: unknown }).detail);
    }
    return err.message || 'Erreur API';
  }
  return 'Erreur inattendue';
}

export async function uploadAndAnalyze(
  params: UploadFastqParams,
  onUploadProgress?: (pct: number) => void,
): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append('patient_id', params.patient_id.trim());
  form.append('fastq_r1', params.fastq_r1);
  form.append('fastq_r2', params.fastq_r2);

  const { data } = await uploadClient.post<AnalyzeResponse>(
    '/api/v1/analyze/upload',
    form,
    {
      onUploadProgress: (e) => {
        if (onUploadProgress && e.total) {
          onUploadProgress(Math.round((e.loaded / e.total) * 100));
        }
      },
    },
  );
  return data;
}

export const FASTQ_EXTENSIONS = ['.fastq.gz', '.fq.gz', '.fastq', '.fq'];

export function isFastqFile(file: File): boolean {
  const name = file.name.toLowerCase();
  return FASTQ_EXTENSIONS.some((ext) => name.endsWith(ext));
}

export const S3_URI_PATTERN = /^s3:\/\/[a-z0-9.\-]+\/.+/i;
export const PATIENT_ID_PATTERN = /^[A-Za-z0-9_\-]+$/;

export function validateAnalyzeForm(values: AnalyzeRequest): string | null {
  if (!values.patient_id.trim()) {
    return 'Le Patient ID est obligatoire.';
  }
  if (!PATIENT_ID_PATTERN.test(values.patient_id.trim())) {
    return 'Patient ID invalide (lettres, chiffres, _ et - uniquement).';
  }
  if (!values.s3_uri_r1.trim()) {
    return 'Le chemin S3 FASTQ R1 est obligatoire.';
  }
  if (!values.s3_uri_r2.trim()) {
    return 'Le chemin S3 FASTQ R2 est obligatoire.';
  }
  if (!S3_URI_PATTERN.test(values.s3_uri_r1.trim())) {
    return 'URI S3 R1 invalide (format attendu : s3://bucket/chemin).';
  }
  if (!S3_URI_PATTERN.test(values.s3_uri_r2.trim())) {
    return 'URI S3 R2 invalide (format attendu : s3://bucket/chemin).';
  }
  if (values.s3_uri_r1.trim() === values.s3_uri_r2.trim()) {
    return 'Les chemins FASTQ R1 et R2 doivent être distincts.';
  }
  return null;
}
