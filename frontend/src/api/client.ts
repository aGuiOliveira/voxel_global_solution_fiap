// Wrapper minimo do backend FastAPI. Todas rotas via proxy /api/* do Vite.

import type {
  FileKind, OptimizeRequest, RunResult, RunStatus,
} from './types'

const BASE = '/api'

async function jsonOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text()
    throw new Error(`HTTP ${res.status}: ${body || res.statusText}`)
  }
  return res.json() as Promise<T>
}

export async function healthz(): Promise<boolean> {
  const r = await fetch(`${BASE}/healthz`)
  return r.ok
}

export async function postOptimize(
  params: OptimizeRequest,
  file: File | null,
): Promise<RunStatus> {
  const fd = new FormData()
  fd.append('params', JSON.stringify(params))
  if (file) fd.append('file', file, file.name)
  const r = await fetch(`${BASE}/optimize`, { method: 'POST', body: fd })
  return jsonOrThrow<RunStatus>(r)
}

export async function getRun(runId: string): Promise<RunStatus> {
  const r = await fetch(`${BASE}/runs/${runId}`)
  return jsonOrThrow<RunStatus>(r)
}

export async function getResult(runId: string): Promise<RunResult> {
  const r = await fetch(`${BASE}/runs/${runId}/result`)
  return jsonOrThrow<RunResult>(r)
}

export function fileUrl(runId: string, kind: FileKind): string {
  return `${BASE}/runs/${runId}/files/${kind}`
}

export function iterMeshUrl(runId: string, iterIdx: number): string {
  return `${BASE}/runs/${runId}/files/iter/${iterIdx}`
}

export async function deleteRun(runId: string): Promise<void> {
  const r = await fetch(`${BASE}/runs/${runId}`, { method: 'DELETE' })
  if (!r.ok) throw new Error(`HTTP ${r.status}`)
}

export async function cancelRun(runId: string): Promise<RunStatus> {
  const r = await fetch(`${BASE}/runs/${runId}/cancel`, { method: 'POST' })
  return jsonOrThrow<RunStatus>(r)
}
