import { useEffect, useState } from 'react'
import { getScenarios, runSampleAudit, Scenario, AuditReport } from '../utils/api'
import AuditResult from '../components/AuditResult'
import s from '../components/shared.module.css'

const scenarioBadge = (scenario: string) => {
  if (scenario === 'clean')     return `${s.badge} ${s.badgeGreen}`
  if (scenario === 'violation') return `${s.badge} ${s.badgeAmber}`
  if (scenario === 'duplicate') return `${s.badge} ${s.badgeCoral}`
  return `${s.badge} ${s.badgeGray}`
}

export default function Scenarios() {
  const [scenarios, setScenarios] = useState<Scenario[]>([])
  const [cats,      setCats]      = useState<Record<string,number>>({})
  const [loading,   setLoading]   = useState(true)
  const [running,   setRunning]   = useState(false)
  const [report,    setReport]    = useState<AuditReport | null>(null)
  const [error,     setError]     = useState('')
  const [filter,    setFilter]    = useState('all')

  useEffect(() => {
    getScenarios()
      .then(r => { setScenarios(r.scenarios); setCats(r.categories) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const runAll = async () => {
    setRunning(true); setError(''); setReport(null)
    try { setReport(await runSampleAudit()) }
    catch (e: unknown) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setRunning(false) }
  }

  const visible = filter === 'all' ? scenarios : scenarios.filter(s => s.scenario === filter)

  if (loading) return <div className={s.loading}>Loading scenarios…</div>

  if (report) return (
    <div>
      <button
        className={`${s.btn} ${s.btnSecondary}`}
        style={{ marginBottom: 20 }}
        onClick={() => setReport(null)}
      >
        ← Back to scenarios
      </button>
      <AuditResult report={report} />
    </div>
  )

  return (
    <div>
      <h1 className={s.pageTitle}>Test Scenarios</h1>
      <p className={s.pageSubtitle}>18 synthetic expense scenarios covering every compliance case.</p>

      {error && <div className={s.error}>{error}</div>}

      {/* Stats */}
      <div className={s.statGrid}>
        <div className={s.statCard}>
          <div className={s.statLabel}>Total</div>
          <div className={s.statValue}>{scenarios.length}</div>
        </div>
        <div className={s.statCard}>
          <div className={s.statLabel}>Clean</div>
          <div className={s.statValue} style={{ color: 'var(--green)' }}>{cats.clean ?? 0}</div>
        </div>
        <div className={s.statCard}>
          <div className={s.statLabel}>Violations</div>
          <div className={s.statValue} style={{ color: 'var(--amber)' }}>{cats.violation ?? 0}</div>
        </div>
        <div className={s.statCard}>
          <div className={s.statLabel}>Duplicates</div>
          <div className={s.statValue} style={{ color: 'var(--coral)' }}>{cats.duplicate ?? 0}</div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 16, alignItems: 'center', flexWrap: 'wrap' }}>
        {['all','clean','violation','duplicate'].map(f => (
          <button
            key={f}
            className={`${s.btn} ${filter === f ? '' : s.btnSecondary}`}
            style={{ fontSize: 12, padding: '6px 14px' }}
            onClick={() => setFilter(f)}
          >
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
        <button
          className={s.btn}
          style={{ marginLeft: 'auto' }}
          onClick={runAll}
          disabled={running}
        >
          {running ? 'Running…' : '🚀 Run all 18 scenarios'}
        </button>
      </div>

      <div className={s.card}>
        <table className={s.table}>
          <thead>
            <tr>
              <th>Document ID</th><th>Employee</th><th>Type</th>
              <th>Expected</th><th>Policy</th><th>Note</th>
            </tr>
          </thead>
          <tbody>
            {visible.map(sc => (
              <tr key={sc.id}>
                <td style={{ fontFamily: 'monospace', fontSize: 11, color: 'var(--text)' }}>{sc.id}</td>
                <td>{sc.employee}</td>
                <td><span className={scenarioBadge(sc.scenario)}>{sc.scenario}</span></td>
                <td><span className={`${s.badge} ${s.badgeGray}`} style={{ fontSize: 10 }}>{sc.expected_status}</span></td>
                <td><span className={`${s.badge} ${s.badgeBlue}`}>{sc.policy}</span></td>
                <td style={{ color: 'var(--text2)', fontSize: 12 }}>{sc.note}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
