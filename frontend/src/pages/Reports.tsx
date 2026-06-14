import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { listReports, ReportMeta } from '../utils/api'
import s from '../components/shared.module.css'

export default function Reports() {
  const [reports, setReports] = useState<ReportMeta[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')

  useEffect(() => {
    listReports()
      .then(r => setReports(r.reports))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className={s.loading}>Loading reports…</div>

  return (
    <div>
      <h1 className={s.pageTitle}>Audit Reports</h1>
      <p className={s.pageSubtitle}>All reports stored in Amazon S3.</p>

      {error && <div className={s.error}>{error}</div>}

      {reports.length === 0 ? (
        <div className={s.card} style={{ textAlign: 'center', color: 'var(--text2)', padding: 48 }}>
          <div style={{ fontSize: 36, marginBottom: 12 }}>📭</div>
          No reports yet. Run an audit from the{' '}
          <Link to="/upload">Upload page</Link>.
        </div>
      ) : (
        <div className={s.card}>
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
                  <td style={{ fontFamily: 'monospace', fontSize: 12, color: 'var(--text)' }}>
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
        </div>
      )}
    </div>
  )
}
