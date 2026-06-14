import { AuditReport } from '../utils/api'
import s from './shared.module.css'
import styles from './AuditResult.module.css'

interface Props { report: AuditReport }

function statusBadge(status: string) {
  const map: Record<string, string> = {
    COMPLIANT:        s.badgeGreen,
    APPROVED:         s.badgeGreen,
    VIOLATION:        s.badgeAmber,
    PARTIALLY_APPROVED: s.badgeAmber,
    CRITICAL:         s.badgeCoral,
    REJECTED:         s.badgeCoral,
    ESCALATED:        s.badgeCoral,
    PENDING_REVIEW:   s.badgeBlue,
    EXACT_DUPLICATE:  s.badgeCoral,
    NEAR_DUPLICATE:   s.badgeAmber,
  }
  return `${s.badge} ${map[status] ?? s.badgeGray}`
}

function riskBadge(risk: string) {
  const map: Record<string, string> = {
    LOW: s.badgeGreen, MEDIUM: s.badgeAmber,
    HIGH: s.badgeCoral, CRITICAL: s.badgeCoral,
  }
  return `${s.badge} ${map[risk] ?? s.badgeGray}`
}

function $$(n: number) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n)
}

function pct(n: number) { return `${(n * 100).toFixed(0)}%` }

export default function AuditResult({ report }: Props) {
  const fb = report.financial_breakdown
  const ac = report.approval_chain

  const verdictColor = {
    APPROVED:            'var(--green)',
    PARTIALLY_APPROVED:  'var(--amber)',
    ESCALATED:           'var(--coral)',
    REJECTED:            'var(--coral)',
  }[report.overall_verdict] ?? 'var(--text)'

  return (
    <div>
      {/* Header row */}
      <div className={styles.header}>
        <div>
          <div className={styles.reportId}>
            Report: <span style={{ fontFamily: 'monospace' }}>{report.audit_report_id}</span>
          </div>
          <div style={{ color: 'var(--text2)', fontSize: 12, marginTop: 2 }}>
            Generated {new Date(report.generated_at).toLocaleString()}
          </div>
        </div>
        <div className={styles.verdict} style={{ color: verdictColor }}>
          {report.overall_verdict}
        </div>
      </div>

      {/* KPI row */}
      <div className={s.statGrid}>
        <div className={s.statCard}>
          <div className={s.statLabel}>Compliance score</div>
          <div className={s.statValue} style={{ color: report.compliance_score >= 80 ? 'var(--green)' : report.compliance_score >= 60 ? 'var(--amber)' : 'var(--coral)' }}>
            {report.compliance_score}<span style={{ fontSize: 14 }}>/100</span>
          </div>
        </div>
        <div className={s.statCard}>
          <div className={s.statLabel}>Confidence</div>
          <div className={s.statValue}>{pct(report.aggregate_confidence)}</div>
        </div>
        <div className={s.statCard}>
          <div className={s.statLabel}>Total claimed</div>
          <div className={s.statValue} style={{ fontSize: 20 }}>{$$(fb.total_claimed)}</div>
        </div>
        <div className={s.statCard}>
          <div className={s.statLabel}>Approved</div>
          <div className={s.statValue} style={{ fontSize: 20, color: 'var(--green)' }}>{$$(fb.amount_approved)}</div>
        </div>
        <div className={s.statCard}>
          <div className={s.statLabel}>Rejected</div>
          <div className={s.statValue} style={{ fontSize: 20, color: 'var(--coral)' }}>{$$(fb.amount_rejected)}</div>
        </div>
        <div className={s.statCard}>
          <div className={s.statLabel}>Pending review</div>
          <div className={s.statValue} style={{ fontSize: 20, color: 'var(--amber)' }}>{$$(fb.amount_pending_review)}</div>
        </div>
      </div>

      {/* Executive summary */}
      <div className={s.card}>
        <div className={s.cardTitle}>Executive summary</div>
        <p style={{ color: 'var(--text2)', lineHeight: 1.7, fontSize: 13 }}>
          {report.executive_summary}
        </p>
      </div>

      {/* Approval chain */}
      {(ac.manager_approval_required || ac.vp_approval_required || ac.cfo_approval_required) && (
        <div className={s.card}>
          <div className={s.cardTitle}>Approval required</div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {ac.manager_approval_required && <span className={`${s.badge} ${s.badgeAmber}`}>Manager approval</span>}
            {ac.vp_approval_required       && <span className={`${s.badge} ${s.badgeCoral}`}>VP approval</span>}
            {ac.cfo_approval_required      && <span className={`${s.badge} ${s.badgeCoral}`}>CFO approval</span>}
          </div>
        </div>
      )}

      {/* Key findings */}
      {report.key_findings.length > 0 && (
        <div className={s.card}>
          <div className={s.cardTitle}>Policy findings ({report.key_findings.length})</div>
          <table className={s.table}>
            <thead>
              <tr>
                <th>ID</th><th>Policy</th><th>Severity</th>
                <th>Description</th><th>Amount</th><th>Confidence</th>
              </tr>
            </thead>
            <tbody>
              {report.key_findings.map(f => (
                <tr key={f.finding_id}>
                  <td style={{ fontFamily: 'monospace', fontSize: 11 }}>{f.finding_id}</td>
                  <td><span className={`${s.badge} ${s.badgeBlue}`}>{f.policy_reference}</span></td>
                  <td><span className={statusBadge(f.severity)}>{f.severity}</span></td>
                  <td style={{ color: 'var(--text)' }}>{f.description}</td>
                  <td>{$$(f.amount_impact)}</td>
                  <td>{pct(f.confidence_score)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Duplicates */}
      {report.duplicate_findings.length > 0 && (
        <div className={s.card}>
          <div className={s.cardTitle}>Duplicate findings ({report.duplicate_findings.length})</div>
          <table className={s.table}>
            <thead>
              <tr><th>Type</th><th>Expense IDs</th><th>Amount at risk</th><th>Confidence</th><th>Recommendation</th></tr>
            </thead>
            <tbody>
              {report.duplicate_findings.map((d, i) => (
                <tr key={i}>
                  <td><span className={statusBadge(d.type)}>{d.type.replace('_', ' ')}</span></td>
                  <td style={{ fontFamily: 'monospace', fontSize: 11 }}>{d.expense_ids.join(' ↔ ')}</td>
                  <td style={{ color: 'var(--coral)' }}>{$$(d.amount_at_risk)}</td>
                  <td>{pct(d.confidence_score)}</td>
                  <td>{d.recommendation}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Expense details */}
      <div className={s.card}>
        <div className={s.cardTitle}>Expense details ({report.expense_details.length})</div>
        <div style={{ overflowX: 'auto' }}>
          <table className={s.table}>
            <thead>
              <tr>
                <th>Document ID</th><th>Vendor</th><th>Category</th>
                <th>Amount</th><th>Date</th><th>Status</th>
                <th>Risk</th><th>Approval</th><th>Dup?</th>
              </tr>
            </thead>
            <tbody>
              {report.expense_details.map(e => (
                <tr key={e.document_id}>
                  <td style={{ fontFamily: 'monospace', fontSize: 11 }}>{e.document_id}</td>
                  <td style={{ color: 'var(--text)' }}>{e.vendor}</td>
                  <td>{e.category}</td>
                  <td>{$$(e.amount)}</td>
                  <td style={{ whiteSpace: 'nowrap' }}>{e.date}</td>
                  <td><span className={statusBadge(e.compliance_status)}>{e.compliance_status}</span></td>
                  <td><span className={riskBadge(e.risk_level)}>{e.risk_level}</span></td>
                  <td><span className={`${s.badge} ${s.badgeGray}`}>{e.requires_approval}</span></td>
                  <td>{e.is_duplicate ? '⚠️' : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Action items */}
      {report.action_items.length > 0 && (
        <div className={s.card}>
          <div className={s.cardTitle}>Action items ({report.action_items.length})</div>
          <table className={s.table}>
            <thead>
              <tr><th>ID</th><th>Priority</th><th>Assignee</th><th>Action</th><th>Deadline</th></tr>
            </thead>
            <tbody>
              {report.action_items.map(a => (
                <tr key={a.action_id}>
                  <td style={{ fontFamily: 'monospace', fontSize: 11 }}>{a.action_id}</td>
                  <td><span className={a.priority === 'HIGH' ? `${s.badge} ${s.badgeCoral}` : `${s.badge} ${s.badgeAmber}`}>{a.priority}</span></td>
                  <td><span className={`${s.badge} ${s.badgeBlue}`}>{a.assignee}</span></td>
                  <td style={{ color: 'var(--text)' }}>{a.action}</td>
                  <td style={{ whiteSpace: 'nowrap' }}>{a.deadline}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
