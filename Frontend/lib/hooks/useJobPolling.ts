'use client';

import useSWR from 'swr';
import { getJobStatus } from '@/lib/api';
import type { JobStatusResponse } from '@/types/api';

const TERMINAL: JobStatusResponse['status'][] = ['completed', 'failed'];

export function useJobPolling(jobId: string | null, pollIntervalMs = 4000) {
  return useSWR<JobStatusResponse>(
    jobId ? ['job', jobId] : null,
    () => getJobStatus(jobId!),
    {
      refreshInterval: (latest) =>
        latest && TERMINAL.includes(latest.status) ? 0 : pollIntervalMs,
      revalidateOnFocus: true,
      dedupingInterval: 1000,
    },
  );
}
