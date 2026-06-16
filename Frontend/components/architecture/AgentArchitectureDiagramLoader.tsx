'use client';

import dynamic from 'next/dynamic';

/** Wrapper SSR-safe : Mermaid ne s'exécute jamais côté serveur (Vercel) */
const AgentArchitectureDiagram = dynamic(
  () => import('./AgentArchitectureDiagram'),
  {
    ssr: false,
    loading: () => (
      <div
        style={{
          padding: '2rem',
          textAlign: 'center',
          color: '#94a3b8',
          background: 'rgba(15,23,42,0.85)',
          borderRadius: '1.25rem',
          border: '1px solid rgba(255,255,255,0.08)',
        }}
      >
        Chargement du diagramme architecture…
      </div>
    ),
  }
);

export default AgentArchitectureDiagram;
