import { useState } from 'react'
import { validateExpense, ValidationResult } from '../utils/api'
import s from '../components/shared.module.css'
import styles from './Validate.module.css'

const DEFAULT = JSON.stringify({
  document_id:   "TEST-001",
  vendor:        "Marriott Hotels",
  category:      "accommodation",
  amount:        450.00,
  date:          "2026-06-13",
  description:   "Hotel 2 nights NYC",
  employee_name: "Alice Johnson",
  department:    "Sales"
}, null, 2)

export default function Validate() {
  const [json,    setJson]    = useState(DEFAULT)
  const [result,  setResult]  = useState<ValidationResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')
  const [jsonErr, setJsonErr] = useState('')

  const run = async () => {
    setJsonErr('')
    let parsed: Record<string, unknown>
    try { parsed = JSON.parse(json) }
    catch { setJsonErr('Invalid JSON — please fix before running.'); return }

    setLoading(true); setError(''); setResult(null)
    try {
      setResult(await validateExpense(parsed))
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const statusColor: Record<string, string> = {
    COMPLIANT:     'var(--green)',
    VIOLATION:     'var(--amber)',
    CRITICAL:      'var(--coral)',
    PENDING_REVIEW:'var(--blue)',
  }

  return (
    <div>
      <h1 className={s.pageTitle}>Validate Expense</h1>
      <p className={s.pageSubtitle}>
        Enter a single expense as JSON and check it against company policy instantly.
      </p>

      <div className={styles.layout}>
        {/* Input */}
        <div>
          <div className={s.card}>
            <div className={s.cardTitle}>Expense JSON</div>
            <textarea
              value={json}
              onChange={e => setJson(e.target.value)}
              rows={18}
              style={{ fontFamily: 'monospace', fontSize: 12, resize: 'vertical' }}
            />
            {jsonErr && <div className={s.error} style={{ marginTop: 8 }}>{jsonErr}</div>}
            {error   && <div className={s.error} style={{ marginTop: 8 }}>{error}</div>}
            <button
              className={s.btn}
              style={{ marginTop: 12 }}
              onClick={run}
              disabled={loading}
            >
              {loading ? 'Validating…' : '✅ Validate'}
            </button>
          </div>

          {/* Quick examples */}
          <div className={s.card}>
            <div className={s.cardTitle}>Quick examples</div>
            {[
              { label: 'Hotel over limit', obj: { document_id:'T1', vendor:'Ritz-Carlton NYC', category:'accommodation', amount:650, date:'2026-06-13', description:'Hotel 2 nights' } },
              { label: 'Spa (prohibited)', obj: { document_id:'T2', vendor:'Four Seasons Spa', category:'wellness', amount:320, date:'2026-06-13', description:'Spa treatment' } },
              { label: 'Compliant flight',  obj: { document_id:'T3', vendor:'Delta Air Lines', category:'travel', amount:380, date:'2026-06-13', description:'Economy ORD-JFK' } },
              { label: 'High value (CFO)',  obj: { document_id:'T4', vendor:'Apple Store', category:'technology', amount:6499, date:'2026-06-13', description:'MacBook Pro' } },
            ].map(ex => (
              <button
                key={ex.label}
                className={`${s.btn} ${s.btnSecondary}`}
                style={{ marginRight: 8, marginBottom: 8, fontSize: 12 }}
                onClick={() => setJson(JSON.stringify(ex.obj, null, 2))}
              >
                {ex.label}
              </button>
            ))}
          </div>
        </div>

        {/* Result */}
        {result && (
          <div className={s.card}>
            <div className={s.cardTitle}>Validation result</div>

            <div className={styles.resultStatus}
              style={{ color: statusColor[result.compliance_status] ?? 'var(--text)' }}>
              {result.compliance_status}
            </div>

            <div className={styles.resultGrid}>
              <div className={styles.resultItem}>
                <div className={styles.resultLabel}>Risk level</div>
                <div className={styles.resultVal}>{result.risk_level}</div>
              </div>
              <div className={styles.resultItem}>
                <div className={styles.resultLabel}>Confidence</div>
                <div className={styles.resultVal}>{(result.confidence_score * 100).toFixed(0)}%</div>
              </div>
              <div className={styles.resultItem}>
                <div className={styles.resultLabel}>Approval required</div>
                <div className={styles.resultVal}>{result.requires_approval_from}</div>
              </div>
              <div className={styles.resultItem}>
                <div className={styles.resultLabel}>Method</div>
                <div className={styles.resultVal}>{result.validation_method}</div>
              </div>
            </div>

            {result.violations.length > 0 && (
              <>
                <div className={s.cardTitle} style={{ marginTop: 16 }}>
                  Violations ({result.violations.length})
                </div>
                {result.violations.map((v, i) => (
                  <div key={i} className={styles.violation}>
                    <span className={`${s.badge} ${s.badgeBlue}`}>{v.policy_ref}</span>
                    <span className={`${s.badge} ${s.badgeCoral}`} style={{ marginLeft: 8 }}>{v.severity}</span>
                    <div style={{ marginTop: 6, color: 'var(--text)', fontSize: 13 }}>{v.description}</div>
                  </div>
                ))}
              </>
            )}

            {result.recommendations.length > 0 && (
              <>
                <div className={s.cardTitle} style={{ marginTop: 16 }}>Recommendations</div>
                <ul style={{ paddingLeft: 18, color: 'var(--text2)', fontSize: 13 }}>
                  {result.recommendations.map((r, i) => <li key={i} style={{ marginBottom: 4 }}>{r}</li>)}
                </ul>
              </>
            )}

            <div className={s.cardTitle} style={{ marginTop: 16 }}>Reasoning</div>
            <p style={{ color: 'var(--text2)', fontSize: 13, lineHeight: 1.6 }}>{result.reasoning}</p>
          </div>
        )}
      </div>
    </div>
  )
}
