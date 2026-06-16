'use client';

import useSWR from 'swr';
import {
  Activity,
  Dna,
  Server,
  Wifi,
  WifiOff,
} from 'lucide-react';
import ThemeToggle from '@/components/layout/ThemeToggle';
import { checkHealth } from '@/lib/api';

interface MainLayoutProps {
  children: React.ReactNode;
}

export default function MainLayout({ children }: MainLayoutProps) {
  const { data: health, error, isLoading } = useSWR('health', checkHealth, {
    refreshInterval: 15_000,
    revalidateOnFocus: true,
  });

  const connected = !error && health?.status === 'ok';

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 transition-colors dark:bg-slate-950 dark:text-slate-100">
      <div
        className="pointer-events-none fixed inset-0 opacity-[0.35] dark:opacity-[0.12]"
        style={{
          backgroundImage:
            'radial-gradient(circle at 20% 20%, rgba(6,182,212,0.15) 0%, transparent 50%), radial-gradient(circle at 80% 0%, rgba(14,165,233,0.12) 0%, transparent 40%)',
        }}
      />

      <header className="sticky top-0 z-50 border-b border-slate-200/80 bg-white/80 backdrop-blur-md dark:border-slate-800/80 dark:bg-slate-950/80">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-dna-500 to-sky-600 text-white shadow-lg shadow-dna-500/25">
              <Dna className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-dna-600 dark:text-dna-400">
                Zaynb Project
              </p>
              <h1 className="text-sm font-bold leading-tight sm:text-base">
                Plateforme génomique clinique
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div
              className={`hidden items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium sm:flex ${
                connected
                  ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400'
                  : 'border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-400'
              }`}
            >
              {connected ? (
                <Wifi className="h-3.5 w-3.5" />
              ) : (
                <WifiOff className="h-3.5 w-3.5" />
              )}
              <span>
                {isLoading
                  ? 'Connexion…'
                  : connected
                    ? 'API connectée'
                    : 'API hors ligne'}
              </span>
            </div>

            {health?.orchestrator && (
              <div className="hidden items-center gap-1.5 rounded-full border border-slate-200 bg-slate-100 px-3 py-1.5 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 lg:flex">
                <Server className="h-3.5 w-3.5 text-dna-500" />
                <span className="max-w-[180px] truncate">{health.orchestrator}</span>
              </div>
            )}

            <div className="flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-100 px-3 py-1.5 text-xs text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300 sm:flex">
              <Activity className="h-3.5 w-3.5 text-dna-500" />
              <span>MLOps</span>
            </div>

            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="relative mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-10">
        {children}
      </main>

      <footer className="relative border-t border-slate-200 py-4 text-center text-xs text-slate-500 dark:border-slate-800 dark:text-slate-500">
        Zaynb · Pipeline GATK Parabricks · BioGPT · Usage recherche clinique uniquement
      </footer>
    </div>
  );
}
