import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { getHealth, listReports, ReportMeta } from '../utils/api'
import s from '../components/shared.module.css'
import styles from './Dashboard.module.css'

export default function Dashboard() {
  const [health, setHealth]   = useState<{ status: string } | null>(null)
  const [reports, setReports] = useState<ReportMeta[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')

  useEffect(() => {
    Promise.all([getHealth(), listReports()])
      .then(([h, r]) => {
        setHealth(h)
        setReports(r.reports.slice(0, 5))
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className={s.loading}>Loading dashboard…</div>

  return (
    <div>
      <h1 className={s.pageTitle}>Expense Audit Dashboard</h1>
      <p className={s.pageSubtitle}>AI-powered corporate expense compliance platform — RetailCorp Inc.</p>

      {error && <div className={s.error}>{error}</div>}

      {/* Service health */}
      <div className={s.statGrid}>
        <div className={s.statCard}>
          <div className={s.statLabel}>Service status</div>
          <div className={s.statValue} style={{ fontSize: 18, color: health?.status === 'ok' ? 'var(--green)' : 'var(--coral)' }}>
            {health?.status === 'ok' ? '● Online' : '● Offline'}
          </div>
          <div className={s.statSub}>FastAPI backend</div>
        </div>
        <div className={s.statCard}>
          <div className={s.statLabel}>Total reports</div>
          <div className={s.statValue}>{reports.length}</div>
          <div className={s.statSub}>Stored in S3</div>
        </div>
        <div className={s.statCard}>
          <div className={s.statLabel}>Audit pipeline</div>
          <div className={s.statValue} style={{ fontSize: 18, color: 'var(--teal)' }}>4 agents</div>
          <div className={s.statSub}>OCR → Validate → Dup → Audit</div>
        </div>
        <div className={s.statCard}>
          <div className={s.statLabel}>Policy docs</div>
          <div className={s.statValue}>12</div>
          <div className={s.statSub}>In OpenSearch k-NN</div>
        </div>
      </div>

      {/* Quick actions */}
      <div className={s.card}>
        <div className={s.cardTitle}>Quick actions</div>
        <div className={styles.actionGrid}>
          <Link to="/upload" className={styles.action}>
            <div className={styles.actionIcon}>📤</div>
            <div className={styles.actionLabel}>Upload &amp; Audit</div>
            <div className={styles.actionSub}>Upload PDF or JSON expense files</div>
          </Link>
          <Link to="/reports" className={styles.action}>
            <div className={styles.actionIcon}>📋</div>
            <div className={styles.actionLabel}>View Reports</div>
            <div className={styles.actionSub}>Browse all stored audit reports</div>
          </Link>
          <Link to="/validate" className={styles.action}>
            <div className={styles.actionIcon}>✅</div>
            <div className={styles.actionLabel}>Validate Expense</div>
            <div className={styles.actionSub}>Check a single expense instantly</div>
          </Link>
          <Link to="/scenarios" className={styles.action}>
            <div className={styles.actionIcon}>🧪</div>
            <div className={styles.actionLabel}>Run Sample Audit</div>
            <div className={styles.actionSub}>Test with 18 synthetic scenarios</div>
          </Link>
        </div>
      </div>

      {/* Recent reports */}
      {reports.length > 0 && (
        <div className={s.card}>
          <div className={s.cardTitle}>Recent reports</div>
          <table className={s.table}>
            <thead>
              <tr>
                <th>Report ID</th>
                <th>Last modified</th>
                <th>Size</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {reports.map(r => (
                <tr key={r.report_id}>
                  <td style={{ color: 'var(--text)', fontFamily: 'monospace', fontSize: 12 }}>
                    {r.report_id}
                  </td>
                  <td>{new Date(r.last_modified).toLocaleString()}</td>
                  <td>{(r.size_bytes / 1024).toFixed(1)} KB</td>
                  <td>
                    <Link to={`/reports/${r.report_id}`} style={{ color: 'var(--blue)', fontSize: 12 }}>
                      View →
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ marginTop: 12 }}>
            <Link to="/reports" style={{ fontSize: 13, color: 'var(--blue)' }}>
              View all reports →
            </Link>
          </div>
        </div>
      )}

      {/* Architecture note */}
      <div className={s.card}>
        <div className={s.cardTitle}>Architecture</div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', fontSize: 12 }}>
          {['FastAPI', 'AWS Textract', 'Amazon Bedrock (Claude)', 'Titan Embed v2',
            'OpenSearch k-NN', 'Amazon S3', 'ECS Fargate', 'CDK v2'].map(t => (
            <span key={t} className={s.badge + ' ' + s.badgeGray}>{t}</span>
          ))}
        </div>
      </div>
    </div>
  )
}
