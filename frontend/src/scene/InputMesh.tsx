// Mesh da STL de entrada. Click no mesh dispara applyPick quando ha
// modo de picking ativo.

import type { ThreeEvent } from '@react-three/fiber'
import { useEffect } from 'react'
import { useJob } from '../store/job'
import { useRegions } from '../store/regions'
import { useStlGeometry } from './useStlMesh'

export function InputMesh() {
  const url = useJob((s) => s.inputUrl)
  const show = useJob((s) => s.showOriginal)
  const setInputBbox = useJob((s) => s.setInputBbox)
  const result = useJob((s) => s.result)
  const status = useJob((s) => s.status)
  const latestIterMesh = useJob((s) => s.latestIterMesh)
  const picking = useRegions((s) => s.picking)
  const applyPick = useRegions((s) => s.applyPick)

  const geom = useStlGeometry(url)

  // Publica a bbox no store quando a geometry chega. ParamsForm consome isso
  // pra estimar nx*ny*nz dado o pitch.
  useEffect(() => {
    if (!geom) {
      setInputBbox(null)
      return
    }
    if (!geom.boundingBox) geom.computeBoundingBox()
    const bb = geom.boundingBox
    if (!bb) return
    setInputBbox({
      min: [bb.min.x, bb.min.y, bb.min.z],
      max: [bb.max.x, bb.max.y, bb.max.z],
    })
  }, [geom, setInputBbox])

  // Durante o run com preview ao vivo, esconde o original — opacidade baixa em
  // mesh STL nao funciona bem (triangulos sobrepostos somam alpha e a peca
  // ainda parece solida). Some completo enquanto roda; volta fantasma quando
  // o resultado final chega, pra dar contexto sem atrapalhar a visualizacao.
  const isRunning = status === 'queued' || status === 'running'
  const hideForLivePreview = isRunning && latestIterMesh != null
  if (!geom || !show || hideForLivePreview) return null

  const handleClick = (e: ThreeEvent<MouseEvent>) => {
    if (!picking) return
    e.stopPropagation()
    const p = e.point
    applyPick([p.x, p.y, p.z])
  }

  // Apos done (com result), fica fantasma pra dar contexto sem atrapalhar.
  // (Durante running ja saiu via return null acima.)
  const hasOverlay = !!result
  return (
    <mesh
      geometry={geom}
      onClick={handleClick}
      castShadow
      receiveShadow
    >
      <meshStandardMaterial
        color="#a8b3c2"
        metalness={0.05}
        roughness={0.8}
        transparent={hasOverlay}
        opacity={hasOverlay ? 0.18 : 1.0}
      />
    </mesh>
  )
}
