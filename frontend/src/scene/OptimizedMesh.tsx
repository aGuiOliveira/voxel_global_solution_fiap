// Mostra ou (a) preview ao vivo durante a otimizacao — GLB da ultima iter
// pronta servida por /api/runs/{id}/files/iter/{n} — ou (b) a STL final
// otimizada apos status='done'.
//
// As coords do GLB sao em VOXEL (output direto do marching cubes em xPhys).
// Como a STL final tambem volta em mm via outro pipeline, escalamos o GLB
// pelo pitch pra ficar aproximadamente no mesmo espaco visual da peca de
// entrada. A geometria muda a cada iter, mas o transform do mesh fica fixo.

import { DoubleSide } from 'three'
import { fileUrl, iterMeshUrl } from '../api/client'
import { useJob } from '../store/job'
import { useGlbGeometry, useStlGeometry } from './useStlMesh'

export function OptimizedMesh() {
  const runId = useJob((s) => s.runId)
  const status = useJob((s) => s.status)
  const latestIter = useJob((s) => s.latestIterMesh)
  const result = useJob((s) => s.result)
  const show = useJob((s) => s.showOptimized)
  const pitch = useJob((s) => s.pitch)

  const isRunning = status === 'queued' || status === 'running'
  const liveUrl = runId && isRunning && latestIter != null
    ? iterMeshUrl(runId, latestIter)
    : null
  const finalUrl = runId && result ? fileUrl(runId, 'optimized_stl') : null

  const liveGeom = useGlbGeometry(liveUrl)
  const finalGeom = useStlGeometry(finalUrl)

  if (!show) return null

  // Prioriza a STL final quando existe (status=done).
  if (finalGeom) {
    return (
      <mesh geometry={finalGeom} castShadow receiveShadow>
        <meshStandardMaterial color="#ff9a3d" metalness={0.1} roughness={0.6} />
      </mesh>
    )
  }

  if (liveGeom) {
    // side=DoubleSide pra que faces com winding invertido (marching_cubes
    // sem fix_normals) renderizem dos dois lados em vez de sumir. Custa
    // ~zero pra grids pequenos do preview e evita visual "folha de papel".
    return (
      <mesh
        geometry={liveGeom}
        scale={[pitch, pitch, pitch]}
        castShadow
        receiveShadow
      >
        <meshStandardMaterial
          color="#ffb56b"
          metalness={0.1}
          roughness={0.7}
          side={DoubleSide}
        />
      </mesh>
    )
  }

  return null
}
