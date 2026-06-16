'use client';

import dynamic from 'next/dynamic';

/**
 * Import SSR-safe pour Vercel : évite `window is not defined` au build/prerender.
 */
const AnimatedArchitecture = dynamic(() => import('./AnimatedArchitecture'), {
  ssr: false,
  loading: () => (
    <div
      style={{
        padding: '2rem',
        textAlign: 'center',
        color: '#94a3b8',
        background: 'rgba(15,23,42,0.9)',
        borderRadius: '1.25rem',
        border: '1px solid rgba(255,255,255,0.08)',
      }}
    >
      Chargement du diagramme animé…
    </div>
  ),
});

export default AnimatedArchitecture;
