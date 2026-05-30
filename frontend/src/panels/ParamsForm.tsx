import { useJob } from '../store/job'

// Limites empiricos (Pardiso, ~8 GB RAM):
//   < 50k voxels  -> rapido (<1 min)
//   50-150k       -> ok (~3-15 min)
//   150-250k      -> lento, beira o limite de RAM
//   > 250k        -> provavelmente OOM no Pardiso
const VOXEL_FAST = 50_000
const VOXEL_OK = 150_000
const VOXEL_SLOW = 250_000

export function ParamsForm() {
  const job = useJob()
  return (
    <section className="panel-section">
      <h3>2 · Parâmetros</h3>
      <NumField label="volfrac" value={job.volfrac} step={0.05} min={0.05} max={0.95}
        onChange={(v) => job.setParam('volfrac', v)} help="Fração de volume alvo" />
      <NumField label="pitch (mm)" value={job.pitch} step={0.5} min={0.1}
        onChange={(v) => job.setParam('pitch', v)} help="Tamanho do voxel" />
      <NumField label="rmin" value={job.rmin} step={0.5} min={1}
        onChange={(v) => job.setParam('rmin', v)} help="Raio do filtro" />
      <NumField label="penal" value={job.penal} step={0.5} min={1}
        onChange={(v) => job.setParam('penal', v)} help="Penalidade SIMP" />
      <NumField label="maxloop" value={job.maxloop} step={50} min={10} int
        onChange={(v) => job.setParam('maxloop', v)} help="Max iterações" />
      <label className="checkrow">
        <input
          type="checkbox"
          checked={job.auto_solidify_bc}
          onChange={(e) => job.setParam('auto_solidify_bc', e.target.checked)}
        />
        auto_solidify_bc
      </label>
      <GridEstimator />
    </section>
  )
}

function GridEstimator() {
  const bbox = useJob((s) => s.inputBboxMm)
  const pitch = useJob((s) => s.pitch)

  if (!bbox) {
    return (
      <div className="grid-est neutral">
        <small>Sobe uma STL pra estimar o tamanho do grid.</small>
      </div>
    )
  }
  if (!pitch || pitch <= 0) {
    return (
      <div className="grid-est warn">
        <small>Pitch inválido.</small>
      </div>
    )
  }

  const dx = bbox.max[0] - bbox.min[0]
  const dy = bbox.max[1] - bbox.min[1]
  const dz = bbox.max[2] - bbox.min[2]
  const nx = Math.max(1, Math.ceil(dx / pitch))
  const ny = Math.max(1, Math.ceil(dy / pitch))
  const nz = Math.max(1, Math.ceil(dz / pitch))
  const total = nx * ny * nz

  // Voxels totais da bbox; o efetivo depois da voxelizacao e' menor (~30-70%
  // da bbox dependendo da peca), entao tratamos esses limites como upper-bound.
  let level: 'fast' | 'ok' | 'slow' | 'oom' = 'fast'
  let label = ''
  if (total < VOXEL_FAST) {
    level = 'fast'
    label = 'rápido (< 1 min)'
  } else if (total < VOXEL_OK) {
    level = 'ok'
    label = 'ok (~ 3–15 min)'
  } else if (total < VOXEL_SLOW) {
    level = 'slow'
    label = 'lento, beira limite de RAM'
  } else {
    level = 'oom'
    label = '⚠ pode estourar RAM (Pardiso error -2)'
  }

  return (
    <div className={`grid-est ${level}`}>
      <div className="grid-est-line">
        <strong>Grid estimado:</strong>{' '}
        {nx}×{ny}×{nz} = {formatCount(total)} voxels
      </div>
      <small>
        bbox {dx.toFixed(1)}×{dy.toFixed(1)}×{dz.toFixed(1)} mm — {label}
        {level === 'oom' && (
          <>
            <br />Aumente o <code>pitch</code> pra reduzir o grid (pitch ×2 → voxels ÷8).
          </>
        )}
      </small>
    </div>
  )
}

function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}k`
  return String(n)
}

function NumField({
  label, value, onChange, step, min, max, int, help,
}: {
  label: string; value: number; onChange: (v: number) => void
  step?: number; min?: number; max?: number; int?: boolean; help?: string
}) {
  return (
    <label className="numfield">
      <span>{label}</span>
      <input
        type="number"
        value={value}
        step={step ?? 1}
        min={min}
        max={max}
        onChange={(e) => {
          const v = int ? parseInt(e.target.value, 10) : parseFloat(e.target.value)
          if (Number.isFinite(v)) onChange(v)
        }}
      />
      {help && <small>{help}</small>}
    </label>
  )
}
