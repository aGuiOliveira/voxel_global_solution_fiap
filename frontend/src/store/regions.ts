// Store das regioes (supports / forces / keep_solid) + estado de picking.
//
// "Picking" e o modo em que o proximo click no canvas vai preencher
// coordenadas de uma regiao em edicao (sphere center, box corners).

import { create } from 'zustand'
import type { ForceRegion, Region, Vec3 } from '../api/types'

export type RegionGroup = 'supports' | 'forces' | 'keep_solid'

export interface Stored<R> {
  id: string
  region: R
}

type PickingTarget = {
  group: RegionGroup
  id: string
  field: 'center' | 'min' | 'max'
}

interface RegionsState {
  supports: Stored<Region>[]
  forces: Stored<ForceRegion>[]
  keep_solid: Stored<Region>[]

  picking: PickingTarget | null

  add(group: RegionGroup, region: Region | ForceRegion): string
  update(group: RegionGroup, id: string, patch: Partial<Region & { vector: Vec3 }>): void
  remove(group: RegionGroup, id: string): void
  clear(): void

  startPicking(t: PickingTarget): void
  cancelPicking(): void
  applyPick(point: Vec3): void

  serialize(): {
    supports: Region[]
    forces: ForceRegion[]
    keep_solid: Region[]
  }
}

let nextId = 1
const newId = () => `r${nextId++}`

export const useRegions = create<RegionsState>((set, get) => ({
  supports: [],
  forces: [],
  keep_solid: [],
  picking: null,

  add(group, region) {
    const id = newId()
    set((s) => ({ ...s, [group]: [...s[group], { id, region }] }))
    return id
  },

  update(group, id, patch) {
    set((s) => ({
      ...s,
      [group]: s[group].map((it) =>
        it.id === id ? { ...it, region: { ...it.region, ...patch } as never } : it,
      ),
    }))
  },

  remove(group, id) {
    set((s) => ({ ...s, [group]: s[group].filter((it) => it.id !== id) }))
  },

  clear() {
    set({ supports: [], forces: [], keep_solid: [], picking: null })
  },

  startPicking(t) {
    set({ picking: t })
  },
  cancelPicking() {
    set({ picking: null })
  },
  applyPick(point) {
    const p = get().picking
    if (!p) return
    get().update(p.group, p.id, { [p.field]: point } as never)
    set({ picking: null })
  },

  serialize() {
    const s = get()
    return {
      supports: s.supports.map((r) => r.region),
      forces: s.forces.map((r) => r.region),
      keep_solid: s.keep_solid.map((r) => r.region),
    }
  },
}))
