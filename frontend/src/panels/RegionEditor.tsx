// Editor inline de uma regiao. Renderiza campos dependendo do .type
// e (quando aplicavel) botoes "pick" pra preencher coords via click no canvas.

import { useEffect, useState } from 'react'
import type {
  BoxRegion, FaceName, ForceRegion, Region, SphereRegion, Vec3,
} from '../api/types'
import { useRegions, type RegionGroup, type Stored } from '../store/regions'

const FACES: FaceName[] = ['x_min', 'x_max', 'y_min', 'y_max', 'z_min', 'z_max']

interface Props {
  group: RegionGroup
  stored: Stored<Region | ForceRegion>
}

export function RegionEditor({ group, stored }: Props) {
  const update = useRegions((s) => s.update)
  const remove = useRegions((s) => s.remove)
  const startPicking = useRegions((s) => s.startPicking)
  const picking = useRegions((s) => s.picking)

  const r = stored.region
  const isForce = group === 'forces'

  const onTypeChange = (t: Region['type']) => {
    let next: Region
    if (t === 'sphere') next = { type: 'sphere', center: [0, 0, 0], radius: 5 }
    else if (t === 'box') next = { type: 'box', min: [0, 0, 0], max: [10, 10, 10] }
    else next = { type: 'face', name: 'x_min', thickness: 2 }
    update(group, stored.id, next as never)
  }

  const isPickingMe = (field: 'center' | 'min' | 'max') =>
    picking?.id === stored.id && picking.group === group && picking.field === field

  return (
    <div className="region-row">
      <div className="region-row-header">
        <select
          value={r.type}
          onChange={(e) => onTypeChange(e.target.value as Region['type'])}
        >
          <option value="face">face</option>
          <option value="sphere">sphere</option>
          <option value="box">box</option>
        </select>
        <button className="ghost danger" onClick={() => remove(group, stored.id)}>×</button>
      </div>

      {r.type === 'face' && (
        <>
          <label className="row">
            <span>name</span>
            <select
              value={r.name}
              onChange={(e) =>
                update(group, stored.id, { name: e.target.value as FaceName } as never)
              }
            >
              {FACES.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
          </label>
          <label className="row">
            <span>thickness</span>
            <input type="number" min={0.1} step={0.5}
              value={r.thickness ?? ''}
              placeholder="auto"
              onChange={(e) => {
                const v = parseFloat(e.target.value)
                update(group, stored.id, { thickness: Number.isFinite(v) ? v : undefined } as never)
              }} />
          </label>
        </>
      )}

      {r.type === 'sphere' && (
        <>
          <Vec3Field label="center" value={(r as SphereRegion).center}
            picking={isPickingMe('center')}
            onPick={() => startPicking({ group, id: stored.id, field: 'center' })}
            onChange={(v) => update(group, stored.id, { center: v } as never)} />
          <label className="row">
            <span>radius</span>
            <NumInput min={0.1} step={0.5} value={(r as SphereRegion).radius}
              onChange={(n) => update(group, stored.id, { radius: n } as never)} />
          </label>
        </>
      )}

      {r.type === 'box' && (
        <>
          <Vec3Field label="min" value={(r as BoxRegion).min}
            picking={isPickingMe('min')}
            onPick={() => startPicking({ group, id: stored.id, field: 'min' })}
            onChange={(v) => update(group, stored.id, { min: v } as never)} />
          <Vec3Field label="max" value={(r as BoxRegion).max}
            picking={isPickingMe('max')}
            onPick={() => startPicking({ group, id: stored.id, field: 'max' })}
            onChange={(v) => update(group, stored.id, { max: v } as never)} />
        </>
      )}

      {isForce && (
        <Vec3Field label="vector"
          value={(r as ForceRegion).vector}
          onChange={(v) => update(group, stored.id, { vector: v } as never)} />
      )}
    </div>
  )
}

function Vec3Field({
  label, value, onChange, onPick, picking,
}: {
  label: string; value: Vec3; onChange: (v: Vec3) => void
  onPick?: () => void; picking?: boolean
}) {
  const setIdx = (i: number, v: number) => {
    const next = value.slice() as Vec3
    next[i] = v
    onChange(next)
  }
  return (
    <div className="vec3field">
      <div className="vec3-label">
        <span>{label}</span>
        {onPick && (
          <button className={picking ? 'ghost active' : 'ghost'} onClick={onPick}>
            {picking ? '… clique no canvas' : 'pick'}
          </button>
        )}
      </div>
      <div className="vec3-inputs">
        {(['x', 'y', 'z'] as const).map((axis, i) => (
          <label key={axis}>
            <span>{axis}</span>
            <NumInput step={0.5} value={value[i]} onChange={(n) => setIdx(i, n)} />
          </label>
        ))}
      </div>
    </div>
  )
}

// Input numerico controlado por TEXTO local, nao pelo numero puro. Antes, com
// value={value}, apagar o campo deixava parseFloat=NaN -> o onChange nao
// disparava -> o React re-renderizava o numero antigo de volta, impedindo
// limpar o campo. Agora o texto livre fica no estado local; commita so numero
// valido, e ao desfocar vazio/invalido cai pro 0 (default pedido).
function NumInput({
  value, onChange, step, min,
}: {
  value: number
  onChange: (v: number) => void
  step?: number
  min?: number
}) {
  const [text, setText] = useState(String(value))

  // Ressincroniza quando value muda por fora (ex.: pick no canvas, troca de
  // tipo), sem sobrescrever enquanto se digita algo equivalente ao valor atual.
  useEffect(() => {
    if (Number(text) !== value) setText(String(value))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value])

  return (
    <input
      type="number"
      step={step}
      min={min}
      value={text}
      onChange={(e) => {
        const t = e.target.value
        setText(t)
        if (t !== '') {
          const n = Number(t)
          if (Number.isFinite(n)) onChange(n)
        }
      }}
      onBlur={() => {
        if (text === '' || !Number.isFinite(Number(text))) {
          setText('0')
          onChange(0)
        }
      }}
    />
  )
}
