import { useState, useRef, DragEvent } from 'react'
import { uploadAudit, runSampleAudit, AuditReport } from '../utils/api'
import AuditResult from '../components/AuditResult'
import s from '../components/shared.module.css'
import styles from './Upload.module.css'

export default function Upload() {
  const [files,   setFiles]   = useState<File[]>([])
  const [report,  setReport]  = useState<AuditReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')
  const [dragging,setDragging]= useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const dropped = Array.from(e.dataTransfer.files).filter(
      f => f.name.endsWith('.pdf') || f.name.endsWith('.json')
    )
    setFiles(prev => [...prev, ...dropped])
  }

  const onFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) setFiles(prev => [...prev, ...Array.from(e.target.files!)])
  }

  const removeFile = (i: number) => setFiles(prev => prev.filter((_, idx) => idx !== i))

  const runUpload = async () => {
    if (!files.length) return
    setLoading(true); setError(''); setReport(null)
    try {
      const r = await uploadAudit(files)
      setReport(r)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  const runSample = async () => {
    setLoading(true); setError(''); setReport(null)
    try {
      const r = await runSampleAudit()
      setReport(r)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1 className={s.pageTitle}>Upload &amp; Audit</h1>
      <p className={s.pageSubtitle}>Upload expense documents (PDF or JSON) or run the built-in sample audit.</p>

      {!report && (
        <>
          {/* Drop zone */}
          <div
            className={`${styles.dropZone} ${dragging ? styles.dragging : ''}`}
            onDragOver={e => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
          >
            <div className={styles.dropIcon}>📂</div>
            <div className={styles.dropText}>
              Drag &amp; drop PDF or JSON files here
            </div>
            <div className={styles.dropSub}>or click to browse</div>
            <input
              ref={inputRef}
              type="file"
              multiple
              accept=".pdf,.json"
              style={{ display: 'none' }}
              onChange={onFileInput}
            />
          </div>

          {/* File list */}
          {files.length > 0 && (
            <div className={s.card} style={{ marginTop: 12 }}>
              <div className={s.cardTitle}>Selected files ({files.length})</div>
              {files.map((f, i) => (
                <div key={i} className={styles.fileRow}>
                  <span className={styles.fileIcon}>
                    {f.name.endsWith('.pdf') ? '📄' : '{}'}
                  </span>
                  <span className={styles.fileName}>{f.name}</span>
                  <span className={styles.fileSize}>
                    {(f.size / 1024).toFixed(1)} KB
                  </span>
                  <button
                    className={`${s.btn} ${s.btnDanger}`}
                    style={{ padding: '3px 10px', fontSize: 11 }}
                    onClick={() => removeFile(i)}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}

          {error && <div className={s.error}>{error}</div>}

          {/* Actions */}
          <div className={styles.actions}>
            <button
              className={s.btn}
              onClick={runUpload}
              disabled={loading || !files.length}
            >
              {loading ? 'Auditing…' : '🚀 Run Audit'}
            </button>
            <span className={styles.orSep}>or</span>
            <button
              className={`${s.btn} ${s.btnSecondary}`}
              onClick={runSample}
              disabled={loading}
            >
              {loading ? 'Running…' : '🧪 Run Sample Audit (18 scenarios)'}
            </button>
          </div>
        </>
      )}

      {loading && (
        <div className={s.loading}>
          <div className={styles.spinner} />
          <div style={{ marginTop: 16 }}>Running audit pipeline…</div>
          <div style={{ color: 'var(--text3)', marginTop: 6, fontSize: 12 }}>
            OCR → Validation → Duplicate detection → Report generation
          </div>
        </div>
      )}

      {report && !loading && (
        <>
          <button
            className={`${s.btn} ${s.btnSecondary}`}
            style={{ marginBottom: 20 }}
            onClick={() => { setReport(null); setFiles([]) }}
          >
            ← Run another audit
          </button>
          <AuditResult report={report} />
        </>
      )}
    </div>
  )
}
