// Painel direito: dispara otimizacao, polling, mostra resultado.
//
// Usa React Query soh pro polling. O `runId` vive no store global
// (job.ts) — quando muda, o useQuery troca de key e reinicia o polling.

import { useQuery } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { cancelRun, fileUrl, getResult, getRun, postOptimize } from '../api/client'
import type { OptimizeRequest } from '../api/types'
import { useJob } from '../store/job'
import { useRegions } from '../store/regions'

export function JobPanel() {
  const job = useJob()
  const serialize = useRegions((s) => s.serialize)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  const statusQ = useQuery({
    queryKey: ['run', job.runId],
    queryFn: () => getRun(job.runId!),
    enabled: !!job.runId,
    refetchInterval: (q) => {
      const s = q.state.data?.status
      if (s === 'done' || s === 'error' || s === 'cancelled') return false
      return s === 'running' ? 1000 : 2000
    },
  })

  const [cancelling, setCancelling] = useState(false)
  const onCancel = async () => {
    if (!job.runId) return
    setCancelling(true)
    try {
      await cancelRun(job.runId)
      await statusQ.refetch()
    } catch (e) {
      console.error(e)
    } finally {
      setCancelling(false)
    }
  }

  // Quando o status vira 'done', busca o result e poe no store.
  useEffect(() => {
    if (statusQ.data?.status !== 'done' || !job.runId) return
    if (job.result) return
    getResult(job.runId).then((r) => {
      if (r.result) job.setResult(r.result)
    }).catch(console.error)
  }, [statusQ.data?.status, job.runId, job.result])

  // Espelha status + latest_iter_mesh do polling pro store, pra que o
  // canvas 3D (OptimizedMesh) reaja a cada nova iter pronta.
  useEffect(() => {
    if (!statusQ.data) return
    job.setStatus(statusQ.data.status)
    const n = statusQ.data.latest_iter_mesh ?? null
    if (n !== job.latestIterMesh) job.setLatestIterMesh(n)
  }, [statusQ.data])

  const onOptimize = async () => {
    if (!job.inputFile) {
      setSubmitError('Selecione uma STL primeiro')
      return
    }
    setSubmitting(true)
    setSubmitError(null)
    try {
      const regs = serialize()
      const params: OptimizeRequest = {
        volfrac: job.volfrac,
        pitch: job.pitch,
        rmin: job.rmin,
        penal: job.penal,
        maxloop: job.maxloop,
        auto_solidify_bc: job.auto_solidify_bc,
        ...(regs.supports.length ? { supports: regs.supports } : {}),
        ...(regs.forces.length ? { forces: regs.forces } : {}),
        ...(regs.keep_solid.length ? { keep_solid: regs.keep_solid } : {}),
      }
      const r = await postOptimize(params, job.inputFile)
      job.setRunId(r.run_id)
    } catch (e) {
      setSubmitError(String(e))
    } finally {
      setSubmitting(false)
    }
  }

  const status = statusQ.data?.status
  const elapsed = statusQ.data?.elapsed_s
  const isRunning = status === 'queued' || status === 'running'

  return (
    <aside className="side right">
      <section className="panel-section">
        <h3>3 · Otimização</h3>
        <button
          className="primary big"
          disabled={submitting || isRunning || !job.inputFile}
          onClick={onOptimize}
        >
          {isRunning ? '⏳ rodando…' : submitting ? 'enviando…' : '▶ Otimizar'}
        </button>
        {isRunning && (
          <button
            className="danger big"
            disabled={cancelling}
            onClick={onCancel}
          >
            {cancelling ? 'cancelando…' : '⏹ Cancelar'}
          </button>
        )}
        {submitError && <div className="error">{submitError}</div>}
      </section>

      {job.runId && (
        <>
          <section className="panel-section">
            <h3>Job</h3>
            <Row k="run_id" v={job.runId.slice(0, 12)} />
            <Row k="status" v={
              <span className={`badge badge-${status ?? 'queued'}`}>{status ?? '...'}</span>
            } />
            {elapsed != null && <Row k="elapsed" v={`${elapsed.toFixed(0)}s`} />}
            {statusQ.data?.error && (
              <pre className="error">{statusQ.data.error.slice(0, 600)}</pre>
            )}
          </section>

          {isRunning && <ProgressBlock data={statusQ.data} />}
        </>
      )}

      {job.result && (
        <>
          <section className="panel-section">
            <h3>Resultado</h3>
            <Row k="reduction" v={`${job.result.reduction_vs_input_pct.toFixed(1)}%`} />
            <Row k="effective volfrac" v={job.result.effective_volfrac.toFixed(3)} />
            <Row k="watertight" v={job.result.watertight ? 'sim' : 'não'} />
            <Row k="solver" v={`${job.result.solver_elapsed_s.toFixed(1)}s`} />
            <Row k="grid" v={`${job.result.nelx}×${job.result.nely}×${job.result.nelz}`} />
          </section>

          <section className="panel-section">
            <h3>Visualização</h3>
            <label className="checkrow">
              <input type="checkbox" checked={job.showOriginal}
                onChange={(e) => job.setShowOriginal(e.target.checked)} />
              mostrar STL original
            </label>
            <label className="checkrow">
              <input type="checkbox" checked={job.showOptimized}
                onChange={(e) => job.setShowOptimized(e.target.checked)} />
              mostrar STL otimizada
            </label>
            <a
              className="primary"
              href={fileUrl(job.runId!, 'optimized_stl')}
              download={`optimized_${job.runId}.stl`}
            >
              ⬇ baixar STL
            </a>
          </section>
        </>
      )}
    </aside>
  )
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="kv">
      <span className="k">{k}</span>
      <span className="v">{v}</span>
    </div>
  )
}

function ProgressBlock({ data }: { data: import('../api/types').RunStatus | undefined }) {
  const [showLog, setShowLog] = useState(false)
  const p = data?.progress
  const log = data?.log_tail ?? []
  const pct = p && p.maxloop ? Math.min(100, (p.iter / p.maxloop) * 100) : null

  return (
    <section className="panel-section">
      <h3>Progresso</h3>
      {!p && <div className="meta">Aguardando primeira iteração…</div>}
      {p && (
        <>
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${pct ?? 0}%` }} />
            <span className="progress-label">
              iter {p.iter}{p.maxloop ? ` / ${p.maxloop}` : ''}
              {pct != null && ` · ${pct.toFixed(0)}%`}
            </span>
          </div>
          <Row k="compliance" v={p.compliance.toFixed(3)} />
          <Row k="Δcompliance" v={p.compliance_delta.toFixed(4)} />
          <Row k="volume" v={p.volume.toFixed(3)} />
          <Row k="change" v={p.change.toFixed(4)} />
          <Row k="iter time" v={`${p.iter_time_s.toFixed(2)}s`} />
        </>
      )}
      <button className="ghost" onClick={() => setShowLog((s) => !s)} style={{ marginTop: 4 }}>
        {showLog ? '▾ esconder log' : '▸ mostrar log'} ({log.length})
      </button>
      {showLog && (
        <pre className="log-feed">
          {log.length ? log.join('\n') : '(vazio)'}
        </pre>
      )}
    </section>
  )
}
