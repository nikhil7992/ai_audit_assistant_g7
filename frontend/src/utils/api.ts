/**
 * src/utils/api.ts
 * All API calls to the FastAPI backend.
 *
 * PLACEHOLDER: Set VITE_API_URL in your .env file to point at your ALB.
 * Example: VITE_API_URL=http://expense-audit-alb-dev-xxx.us-east-1.elb.amazonaws.com
 *
 * In local dev, vite.config.ts proxies /api → http://localhost:8000
 * In production (S3/CloudFront), VITE_API_URL must be the full ALB URL.
 */

// BASE is empty — all API calls use relative URLs (e.g. /validate, /audit/sample)
// nginx proxies them to the FastAPI gateway service at runtime via BACKEND_URL env var.
// This means the same Docker image works in any environment without rebuilding.
const BASE = ''

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  isFormData = false,
): Promise<T> {
  const headers: Record<string, string> = {}
  if (!isFormData && body) headers['Content-Type'] = 'application/json'

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: isFormData ? (body as FormData) : body ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

// ── Health ────────────────────────────────────────────────────────────────────
export const getHealth = () =>
  request<{ status: string; service: string; version: string }>('GET', '/health')

// ── Audit ─────────────────────────────────────────────────────────────────────
export const runSampleAudit = () =>
  request<AuditReport>('POST', '/audit/sample')

export const uploadAudit = (files: File[]) => {
  const fd = new FormData()
  files.forEach(f => fd.append('files', f))
  return request<AuditReport>('POST', '/audit/upload', fd, true)
}

export const getScenarios = () =>
  request<{ total: number; scenarios: Scenario[]; categories: Record<string,number> }>(
    'GET', '/audit/scenarios'
  )

// ── Validate ──────────────────────────────────────────────────────────────────
export const validateExpense = (expense: Record<string, unknown>) =>
  request<ValidationResult>('POST', '/validate', expense)

// ── Reports ───────────────────────────────────────────────────────────────────
export const listReports = () =>
  request<{ reports: ReportMeta[]; total: number }>('GET', '/reports')

export const getReport = (id: string) =>
  request<AuditReport>('GET', `/reports/${id}`)

// ── Policies ──────────────────────────────────────────────────────────────────
export const queryPolicies = (query: string, top_k = 5) =>
  request<{ query: string; results: PolicyChunk[] }>('POST', '/policies/query', { query, top_k })

// ── Admin ─────────────────────────────────────────────────────────────────────
export const seedPolicies = () =>
  request<{ status: string; policy_files: number; indexed: number }>(
    'POST', '/admin/seed-policies'
  )

export const generateData = () =>
  request<{ status: string; invoices_generated: number; forms_generated: number }>(
    'POST', '/admin/generate-data'
  )

// ── Types ─────────────────────────────────────────────────────────────────────
export interface AuditReport {
  audit_report_id:      string
  audit_date:           string
  overall_verdict:      'APPROVED' | 'PARTIALLY_APPROVED' | 'ESCALATED' | 'REJECTED'
  compliance_score:     number
  aggregate_confidence: number
  executive_summary:    string
  financial_breakdown: {
    total_claimed:          number
    amount_approved:        number
    amount_rejected:        number
    amount_pending_review:  number
  }
  key_findings:    Finding[]
  duplicate_findings: DupFinding[]
  action_items:    ActionItem[]
  approval_chain: {
    manager_approval_required: boolean
    vp_approval_required:      boolean
    cfo_approval_required:     boolean
  }
  expense_details: ExpenseDetail[]
  generated_at:    string
}

export interface Finding {
  finding_id:        string
  severity:          string
  policy_reference:  string
  description:       string
  amount_impact:     number
  affected_expense:  string
  confidence_score:  number
}

export interface DupFinding {
  type:             string
  expense_ids:      string[]
  amount_at_risk:   number
  confidence_score: number
  recommendation:   string
}

export interface ActionItem {
  action_id: string
  assignee:  string
  priority:  string
  action:    string
  deadline:  string
}

export interface ExpenseDetail {
  document_id:        string
  vendor:             string
  amount:             number
  category:           string
  date:               string
  compliance_status:  string
  risk_level:         string
  confidence_score:   number
  requires_approval:  string
  is_duplicate:       boolean
}

export interface ReportMeta {
  report_id:     string
  last_modified: string
  size_bytes:    number
}

export interface ValidationResult {
  document_id:            string
  compliance_status:      string
  risk_level:             string
  confidence_score:       number
  violations:             { policy_ref: string; description: string; severity: string }[]
  recommendations:        string[]
  requires_approval_from: string
  reasoning:              string
  validation_method:      string
}

export interface Scenario {
  id:              string
  employee:        string
  scenario:        string
  expected_status: string
  policy:          string
  note:            string
}

export interface PolicyChunk {
  chunk:     string
  source:    string
  policy_id: string
  score:     number
}
