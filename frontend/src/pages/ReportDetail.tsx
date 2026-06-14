import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getReport, AuditReport } from '../utils/api'
import AuditResult from '../components/AuditResult'
import s from '../components/shared.module.css'

export default function ReportDetail() {
  const { id } = useParams<{ id: string }>()
  const [report,  setReport]  = useState<AuditReport | null>(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState('')

  useEffect(() => {
    if (!id) return
    getReport(id)
      .then(setReport)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className={s.loading}>Loading report…</div>
  if (error)   return <div className={s.error}>{error}</div>
  if (!report) return null

  return (
    <div>
      <div style={{ marginBottom: 20 }}>
        <Link to="/reports" style={{ color: 'var(--blue)', fontSize: 13 }}>
          ← All reports
        </Link>
      </div>
      <AuditResult report={report} />
    </div>
  )
}
