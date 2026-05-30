import type { ForceRegion, Region } from '../api/types'
import { useRegions, type RegionGroup } from '../store/regions'
import { RegionEditor } from './RegionEditor'

const DEFAULTS: Record<RegionGroup, () => Region | ForceRegion> = {
  supports: () => ({ type: 'face', name: 'x_min', thickness: 2 }),
  keep_solid: () => ({ type: 'face', name: 'x_min', thickness: 2 }),
  forces: () => ({ type: 'face', name: 'x_max', thickness: 2, vector: [0, 0, -1] }),
}

export function RegionList({
  title, group, color,
}: {
  title: string; group: RegionGroup; color: string
}) {
  const items = useRegions((s) => s[group])
  const add = useRegions((s) => s.add)

  return (
    <section className="panel-section">
      <h3 style={{ color }}>{title}</h3>
      {items.length === 0 && <p className="meta">Nenhuma região.</p>}
      {items.map((it) => (
        <RegionEditor key={it.id} group={group} stored={it} />
      ))}
      <button className="ghost" onClick={() => add(group, DEFAULTS[group]())}>
        + adicionar
      </button>
    </section>
  )
}
