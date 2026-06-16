'use client';

import { useCallback, useEffect, useId, useRef, useState } from 'react';
import {
  ANIMATED_ARCHITECTURE_MERMAID,
  ARCH_WORKFLOW,
  type ArchWorkflowStep,
} from '@/lib/mermaid/animatedArchitectureDiagram';
import {
  prepareDiagram,
  runWorkflowSession,
  setupFlowAnimation,
  stopFlowAnimation,
} from '@/lib/mermaid/flowAnimation';
import { runAndExportSession } from '@/lib/export/captureSession';
import styles from './AnimatedArchitecture.module.css';

const INJECTED_FLOW_STYLES = `
  path.data-flow-path.flow-active {
    stroke: #0ea5e9 !important;
    stroke-width: 2.5px !important;
    stroke-dasharray: 8 4 !important;
  }
  path.data-tool-path.flow-active {
    stroke: #10b981 !important;
    stroke-width: 3px !important;
    stroke-dasharray: 6 3 !important;
  }
  path.data-one-shot-path.flow-active {
    stroke: #a78bfa !important;
    stroke-width: 3.5px !important;
    stroke-dasharray: 10 6 !important;
  }
  path.data-validation-path.flow-active {
    stroke: #f59e0b !important;
    stroke-width: 3.5px !important;
    stroke-dasharray: 6 4 !important;
  }
`;

export default function AnimatedArchitecture() {
  const rootRef = useRef<HTMLElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const cleanupRef = useRef<(() => void) | null>(null);
  const reactId = useId().replace(/:/g, '');

  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [playing, setPlaying] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportStatus, setExportStatus] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState<ArchWorkflowStep | null>(null);
  const [stepIndex, setStepIndex] = useState(-1);

  useEffect(() => {
    let cancelled = false;

    const renderDiagram = async () => {
      if (!containerRef.current) return;

      try {
        const mermaid = (await import('mermaid')).default;
        if (cancelled) return;

        mermaid.initialize({
          startOnLoad: false,
          theme: 'dark',
          securityLevel: 'loose',
          themeVariables: {
            primaryColor: '#0c4a6e',
            primaryTextColor: '#e0f2fe',
            primaryBorderColor: '#0ea5e9',
            lineColor: '#334155',
            secondaryColor: '#1e293b',
            tertiaryColor: '#020617',
            clusterBkg: '#0f172a',
            clusterBorder: '#334155',
            titleColor: '#94a3b8',
            edgeLabelBackground: '#1e293b',
          },
          flowchart: { curve: 'basis', htmlLabels: true, padding: 20 },
        });

        const { svg } = await mermaid.render(
          `animated-architecture-${reactId}`,
          ANIMATED_ARCHITECTURE_MERMAID
        );

        if (cancelled || !containerRef.current) return;

        containerRef.current.innerHTML = svg;
        cleanupRef.current?.();
        cleanupRef.current = setupFlowAnimation(containerRef.current);
        setStatus('ready');
      } catch (err) {
        if (!cancelled) {
          setStatus('error');
          setErrorMessage(
            err instanceof Error ? err.message : 'Échec du rendu Mermaid'
          );
        }
      }
    };

    renderDiagram();

    return () => {
      cancelled = true;
      cleanupRef.current?.();
      cleanupRef.current = null;
      if (containerRef.current) containerRef.current.innerHTML = '';
    };
  }, [reactId]);

  const runSession = useCallback(async () => {
    if (!containerRef.current || playing || status !== 'ready') return;

    setPlaying(true);
    setStepIndex(-1);
    setCurrentStep(null);
    stopFlowAnimation();
    prepareDiagram(containerRef.current);

    await runWorkflowSession(
      containerRef.current,
      ARCH_WORKFLOW,
      (step, index) => {
        setCurrentStep(step);
        setStepIndex(index);
      },
      2200
    );

    setPlaying(false);
  }, [playing, status]);

  const reset = useCallback(() => {
    if (!containerRef.current) return;
    stopFlowAnimation();
    prepareDiagram(containerRef.current);
    setCurrentStep(null);
    setStepIndex(-1);
    setPlaying(false);
    setExportStatus(null);
  }, []);

  const exportSession = useCallback(
    async (format: 'webm' | 'gif') => {
      if (!rootRef.current || !containerRef.current || exporting || status !== 'ready') {
        return;
      }

      setExporting(true);
      setExportStatus('Démarrage de l’export…');
      setPlaying(true);
      setStepIndex(-1);
      setCurrentStep(null);
      stopFlowAnimation();

      try {
        await runAndExportSession({
          format,
          fps: 10,
          stepMs: 2200,
          captureTarget: rootRef.current,
          diagramContainer: containerRef.current,
          steps: ARCH_WORKFLOW,
          onStep: (step, index) => {
            setCurrentStep(step);
            setStepIndex(index);
          },
          onProgress: setExportStatus,
        });
      } catch (err) {
        setExportStatus(
          err instanceof Error ? err.message : 'Échec de l’export'
        );
      } finally {
        setExporting(false);
        setPlaying(false);
      }
    },
    [exporting, status]
  );

  return (
    <section ref={rootRef} className={styles.root}>
      <header className={styles.header}>
        <div className={styles.headerRow}>
          <div>
            <h2 className={styles.title}>
              Architecture Harness — Raisonnement ReAct &amp; flux de données
            </h2>
            <p className={styles.subtitle}>
              Bleu = délégation · Vert = tool · Violet = one-shot · Ambre = validation orchestrateur
            </p>
          </div>
          <div className={styles.controls}>
            <button
              type="button"
              className={styles.btn}
              disabled={status !== 'ready' || playing || exporting}
              onClick={runSession}
            >
              ▶ Démarrer la session
            </button>
            <button
              type="button"
              className={`${styles.btn} ${styles.btnExport}`}
              disabled={status !== 'ready' || playing || exporting}
              onClick={() => exportSession('webm')}
              title="Enregistre les 8 étapes et télécharge un fichier .webm"
            >
              ⬇ WebM
            </button>
            <button
              type="button"
              className={`${styles.btn} ${styles.btnExport}`}
              disabled={status !== 'ready' || playing || exporting}
              onClick={() => exportSession('gif')}
              title="Enregistre les 8 étapes et télécharge un fichier .gif"
            >
              ⬇ GIF
            </button>
            <button
              type="button"
              className={`${styles.btn} ${styles.btnSecondary}`}
              disabled={status !== 'ready' || playing || exporting}
              onClick={reset}
            >
              Réinitialiser
            </button>
          </div>
        </div>
      </header>

      {status === 'loading' && (
        <p className={styles.loading}>Rendu Mermaid côté client…</p>
      )}
      {status === 'error' && (
        <p className={styles.error}>Erreur : {errorMessage}</p>
      )}
      {exportStatus && (
        <p className={styles.exportStatus}>{exportStatus}</p>
      )}

      {currentStep && (
        <div
          className={`${styles.banner} ${
            currentStep.orchestratorValidation
              ? styles.bannerValidation
              : currentStep.oneShot
                ? styles.bannerOneShot
                : currentStep.tool
                  ? styles.bannerTool
                  : styles.bannerDelegation
          }`}
        >
          <span className={styles.bannerStep}>
            Étape {stepIndex + 1}/{ARCH_WORKFLOW.length}
          </span>
          <strong>{currentStep.agent}</strong> — {currentStep.title}
          {currentStep.oneShot && (
            <span className={styles.oneShotBadge}>
              1× ONE SHOT — cet agent s&apos;exécute une seule fois dans le pipeline
            </span>
          )}
          {currentStep.orchestratorValidation && (
            <span className={styles.validationBadge}>
              ✓ VALIDATION — l&apos;orchestrateur valide le rapport avant livraison au client
            </span>
          )}
          {currentStep.tool && currentStep.toolName && (
            <span className={styles.toolBadge}>
              {currentStep.oneShot ? '1×' : '⚙'} Exécution tool externe :{' '}
              <em>{currentStep.toolName}</em>
            </span>
          )}
          <span className={styles.payload}>Flux : {currentStep.payload}</span>
        </div>
      )}

      {!currentStep && status === 'ready' && !playing && (
        <div className={styles.bannerIdle}>
          Cliquez sur « Démarrer la session » pour voir la délégation (bleu) et
          l&apos;exécution des tools externes (vert)
        </div>
      )}

      <div className={styles.diagramWrapper}>
        <style dangerouslySetInnerHTML={{ __html: INJECTED_FLOW_STYLES }} />
        <div
          ref={containerRef}
          className={styles.diagramHost}
          aria-label="Diagramme architecture multi-agents animé"
        />
      </div>

      {status === 'ready' && (
        <div className={styles.legend}>
          <div className={styles.legendItem}>
            <span className={styles.legendSwatchDelegation} />
            Délégation agent → agent (bleu)
          </div>
          <div className={styles.legendItem}>
            <span className={styles.legendSwatchTool} />
            Exécution tool externe (vert)
          </div>
          <div className={styles.legendItem}>
            <span className={styles.legendSwatchOneShot} />
            Exécution unique one-shot (violet, 1 passage)
          </div>
          <div className={styles.legendItem}>
            <span className={styles.legendSwatchValidation} />
            Validation orchestrateur (ambre)
          </div>
        </div>
      )}
    </section>
  );
}
