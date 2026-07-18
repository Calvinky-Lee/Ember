// P4 owns — spec 07, tasks P4-M1..M5. Views: Race | Result | Methodology | Report.
// Mocks (src/mocks/) are the frozen spec-06 contract; VITE_USE_MOCKS=1 by default
// until the h14 integration (see specs/tasks/P4-dashboard-demo.md).
import React, { useState } from 'react'
import mockRun from './mocks/run.json'

const VIEWS = ['Race', 'Result', 'Methodology', 'Report']

export default function App() {
  const [view, setView] = useState('Race')
  return (
    <div style={{ maxWidth: 960, margin: '0 auto', padding: '2rem 1rem' }}>
      <header style={{ display: 'flex', gap: '1rem', alignItems: 'baseline' }}>
        <h1 style={{ color: 'var(--ember)' }}>Ember</h1>
        <nav style={{ display: 'flex', gap: '0.75rem' }}>
          {VIEWS.map(v => (
            <button key={v} onClick={() => setView(v)}
              style={{ fontWeight: v === view ? 700 : 400 }}>{v}</button>
          ))}
        </nav>
      </header>
      {/* P4-M1: replace with RaceView etc. Mock event stream: */}
      <pre style={{ background: 'var(--panel)', padding: '1rem', overflowX: 'auto' }}>
        {JSON.stringify(mockRun, null, 2).slice(0, 1200)}
      </pre>
    </div>
  )
}
