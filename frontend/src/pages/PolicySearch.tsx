import { useState } from 'react'
import { queryPolicies, PolicyChunk } from '../utils/api'
import s from '../components/shared.module.css'
import styles from './PolicySearch.module.css'

const EXAMPLES = [
  'hotel nightly rate limit NYC',
  'meal per person cap client dinner',
  'spa treatment prohibited',
  'CFO approval threshold amount',
  'late submission deadline days',
  'first class airfare prohibited',
]

export default function PolicySearch() {
  const [query,   setQuery]   = useState('')
  const [topK,    setTopK]    = useState(5)
  const [results, setResults] = useState<PolicyChunk[]>([])
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')
  const [searched,setSearched]= useState(false)

  const run = async (q = query) => {
    if (!q.trim()) return
    setLoading(true); setError(''); setResults([])
    try {
      const r = await queryPolicies(q.trim(), topK)
      setResults(r.results)
      setSearched(true)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1 className={s.pageTitle}>Policy Search</h1>
      <p className={s.pageSubtitle}>
        Semantic search over the 12 corporate policy documents using OpenSearch k-NN.
      </p>

      <div className={s.card}>
        <div style={{ display: 'flex', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
          <input
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="e.g. hotel nightly rate NYC limit"
            style={{ flex: 1, minWidth: 200 }}
            onKeyDown={e => e.key === 'Enter' && run()}
          />
          <select
            value={topK}
            onChange={e => setTopK(+e.target.value)}
            style={{ width: 120 }}
          >
            {[3, 5, 8, 10].map(n => (
              <option key={n} value={n}>Top {n}</option>
            ))}
          </select>
          <button className={s.btn} onClick={() => run()} disabled={loading || !query.trim()}>
            {loading ? 'Searching…' : '🔍 Search'}
          </button>
        </div>

        <div style={{ marginBottom: 4, fontSize: 12, color: 'var(--text2)' }}>
          Try:
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {EXAMPLES.map(ex => (
            <button
              key={ex}
              className={`${s.btn} ${s.btnSecondary}`}
              style={{ fontSize: 11, padding: '4px 10px' }}
              onClick={() => { setQuery(ex); run(ex) }}
            >
              {ex}
            </button>
          ))}
        </div>
      </div>

      {error && <div className={s.error}>{error}</div>}

      {loading && <div className={s.loading}>Searching OpenSearch…</div>}

      {!loading && searched && results.length === 0 && (
        <div className={s.card} style={{ color: 'var(--text2)', textAlign: 'center', padding: 40 }}>
          No results found. Try a different query.
        </div>
      )}

      {results.map((r, i) => (
        <div key={i} className={s.card}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10, flexWrap: 'wrap', gap: 8 }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span className={`${s.badge} ${s.badgeBlue}`}>{r.policy_id}</span>
              <span className={`${s.badge} ${s.badgeGray}`}>{r.source}</span>
            </div>
            <div className={styles.score}>
              Score: <strong>{(r.score * 100).toFixed(1)}%</strong>
            </div>
          </div>
          <p style={{ color: 'var(--text2)', fontSize: 13, lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
            {r.chunk}
          </p>
        </div>
      ))}
    </div>
  )
}
