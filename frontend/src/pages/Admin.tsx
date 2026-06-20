import { useState } from 'react'
import { seedPolicies, generateData } from '../utils/api'
import s from '../components/shared.module.css'
import styles from './Admin.module.css'

interface Task {
  id:      string
  label:   string
  desc:    string
  icon:    string
  fn:      () => Promise<unknown>
  order:   number
}

export default function Admin() {
  const [statuses, setStatuses] = useState<Record<string, 'idle'|'running'|'done'|'error'>>({})
  const [messages, setMessages] = useState<Record<string, string>>({})

  const run = async (task: Task) => {
    setStatuses(p => ({ ...p, [task.id]: 'running' }))
    setMessages(p => ({ ...p, [task.id]: '' }))
    try {
      const result = await task.fn() as Record<string, unknown>
      setStatuses(p  => ({ ...p, [task.id]: 'done' }))
      setMessages(p  => ({ ...p, [task.id]: JSON.stringify(result, null, 2) }))
    } catch (e: unknown) {
      setStatuses(p  => ({ ...p, [task.id]: 'error' }))
      setMessages(p  => ({ ...p, [task.id]: e instanceof Error ? e.message : String(e) }))
    }
  }

  const tasks: Task[] = [
    {
      id:    'generate-data',
      label: 'Generate synthetic data',
      desc:  'Write 14 invoice PDFs/JSONs, 4 form PDFs/JSONs, and 18 OCR stubs to the data/ directory. Run once after first deployment.',
      icon:  '📂',
      fn:    generateData,
      order: 1,
    },
    {
      id:    'seed-policies',
      label: 'Seed policies into OpenSearch',
      desc:  'Write 12 policy .txt files, chunk them (300-word windows), embed via Bedrock Titan, and upsert into the OpenSearch k-NN index. Run once after deployment, and again when policies change.',
      icon:  '🔍',
      fn:    seedPolicies,
      order: 2,
    },
  ]

  const statusColor = { idle:'var(--text2)', running:'var(--amber)', done:'var(--green)', error:'var(--coral)' }
  const statusLabel = { idle:'Ready', running:'Running…', done:'✓ Done', error:'✗ Error' }

  return (
    <div>
      <h1 className={s.pageTitle}>Admin</h1>
      <p className={s.pageSubtitle}>
        First-time setup tasks. Run these in order after deployment.
      </p>

      <div className={s.card} style={{ background: 'var(--amber-dim)', borderColor: 'var(--amber)', marginBottom: 20 }}>
        <div style={{ color: 'var(--amber)', fontWeight: 600, marginBottom: 6 }}>⚠️ First-time setup</div>
        <p style={{ color: 'var(--text2)', fontSize: 13 }}>
          Run these two tasks in order after your first CDK deployment.
          Step 1 generates the test dataset. Step 2 loads the policy knowledge base into OpenSearch.
          Without Step 2, the validation agent will fall back to rule-based checks only.
        </p>
      </div>

      {tasks.sort((a,b) => a.order - b.order).map(task => {
        const st = statuses[task.id] ?? 'idle'
        const msg = messages[task.id]
        return (
          <div key={task.id} className={s.card}>
            <div className={styles.taskHeader}>
              <div className={styles.taskIcon}>{task.icon}</div>
              <div style={{ flex: 1 }}>
                <div className={styles.taskLabel}>
                  Step {task.order} — {task.label}
                </div>
                <div className={styles.taskDesc}>{task.desc}</div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div className={styles.taskStatus} style={{ color: statusColor[st] }}>
                  {statusLabel[st]}
                </div>
                <button
                  className={s.btn}
                  style={{ marginTop: 8 }}
                  onClick={() => run(task)}
                  disabled={st === 'running'}
                >
                  {st === 'running' ? 'Running…' : st === 'done' ? 'Re-run' : 'Run'}
                </button>
              </div>
            </div>

            {msg && (
              <pre className={`${styles.output} ${st === 'error' ? styles.outputError : styles.outputSuccess}`}>
                {msg}
              </pre>
            )}
          </div>
        )
      })}
    </div>
  )
}
