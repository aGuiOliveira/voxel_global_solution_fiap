// Store do job atual + parametros do otimizador + STL carregado.

import { create } from 'zustand'
import type { JobStatus, OptimizationResult, Vec3 } from '../api/types'

export interface BboxMm { min: Vec3; max: Vec3 }

interface JobState {
  // STL de entrada (carregado pelo usuario, ainda nao enviado)
  inputFile: File | null
  inputUrl: string | null  // object URL pro Three carregar
  // BBox da STL em mm, preenchida quando a geometry carrega no InputMesh.
  // Usada pelo ParamsForm pra estimar nx*ny*nz dado o pitch.
  inputBboxMm: BboxMm | null

  // Parametros do POST /optimize
  volfrac: number
  pitch: number
  maxloop: number
  rmin: number
  penal: number
  auto_solidify_bc: boolean

  // Job atual
  runId: string | null
  status: JobStatus | null
  latestIterMesh: number | null
  result: OptimizationResult | null
  showOptimized: boolean
  showOriginal: boolean

  setInput(file: File | null): void
  setInputBbox(b: BboxMm | null): void
  setParam<K extends keyof JobState>(k: K, v: JobState[K]): void
  setRunId(id: string | null): void
  setStatus(s: JobStatus | null): void
  setLatestIterMesh(n: number | null): void
  setResult(r: OptimizationResult | null): void
  setShowOptimized(v: boolean): void
  setShowOriginal(v: boolean): void
  reset(): void
}

export const useJob = create<JobState>((set, get) => ({
  inputFile: null,
  inputUrl: null,
  inputBboxMm: null,

  volfrac: 0.3,
  pitch: 2.0,
  maxloop: 200,
  rmin: 3.0,
  penal: 3.0,
  auto_solidify_bc: true,

  runId: null,
  status: null,
  latestIterMesh: null,
  result: null,
  showOptimized: true,
  showOriginal: true,

  setInput(file) {
    const cur = get().inputUrl
    if (cur) URL.revokeObjectURL(cur)
    const url = file ? URL.createObjectURL(file) : null
    set({
      inputFile: file, inputUrl: url, inputBboxMm: null,
      runId: null, status: null, latestIterMesh: null, result: null,
    })
  },
  setInputBbox(b) {
    set({ inputBboxMm: b })
  },
  setParam(k, v) {
    set({ [k]: v } as never)
  },
  setRunId(id) {
    set({ runId: id, status: null, latestIterMesh: null, result: null })
  },
  setStatus(s) {
    set({ status: s })
  },
  setLatestIterMesh(n) {
    set({ latestIterMesh: n })
  },
  setResult(r) {
    set({ result: r })
  },
  setShowOptimized(v) {
    set({ showOptimized: v })
  },
  setShowOriginal(v) {
    set({ showOriginal: v })
  },
  reset() {
    const cur = get().inputUrl
    if (cur) URL.revokeObjectURL(cur)
    set({
      inputFile: null, inputUrl: null, inputBboxMm: null,
      runId: null, status: null, latestIterMesh: null, result: null,
      showOptimized: true, showOriginal: true,
    })
  },
}))
