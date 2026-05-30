// Renderiza overlays semitransparentes de cada regiao (supports/forces/keep_solid).
// Forces ganham uma seta indicando a direcao do vetor.

import { useMemo } from 'react'
import * as THREE from 'three'
import type {
  BoxRegion, FaceName, ForceRegion, Region, SphereRegion, FaceRegion, Vec3,
} from '../api/types'
import { useJob } from '../store/job'
import { useRegions, type Stored } from '../store/regions'
import { useStlGeometry } from './useStlMesh'

const COLOR_SUPPORT = '#3a86ff'
const COLOR_FORCE = '#ff3a3a'
const COLOR_KEEP = '#3fdc6c'

export function RegionOverlays() {
  const inputUrl = useJob((s) => s.inputUrl)
  const pitch = useJob((s) => s.pitch)
  const geom = useStlGeometry(inputUrl)

  const supports = useRegions((s) => s.supports)
  const forces = useRegions((s) => s.forces)
  const keepSolid = useRegions((s) => s.keep_solid)

  const bounds = useMemo<MeshBounds | null>(() => {
    if (!geom) return null
    geom.computeBoundingBox()
    const b = geom.boundingBox
    if (!b) return null
    return {
      min: [b.min.x, b.min.y, b.min.z],
      max: [b.max.x, b.max.y, b.max.z],
    }
  }, [geom])

  if (!bounds) return null

  return (
    <group>
      {supports.map((r) => (
        <RegionShape key={r.id} stored={r} color={COLOR_SUPPORT} bounds={bounds} pitch={pitch} />
      ))}
      {keepSolid.map((r) => (
        <RegionShape key={r.id} stored={r} color={COLOR_KEEP} bounds={bounds} pitch={pitch} />
      ))}
      {forces.map((r) => (
        <ForceShape key={r.id} stored={r} bounds={bounds} pitch={pitch} />
      ))}
    </group>
  )
}

interface MeshBounds { min: Vec3; max: Vec3 }

interface ShapeProps {
  stored: Stored<Region>
  color: string
  bounds: MeshBounds
  pitch: number
}

function RegionShape({ stored, color, bounds, pitch }: ShapeProps) {
  const r = stored.region
  if (r.type === 'sphere') return <SphereOverlay r={r} color={color} />
  if (r.type === 'box') return <BoxOverlay r={r} color={color} />
  return <FaceOverlay r={r} color={color} bounds={bounds} pitch={pitch} />
}

function SphereOverlay({ r, color }: { r: SphereRegion; color: string }) {
  return (
    <mesh position={r.center}>
      <sphereGeometry args={[r.radius, 24, 16]} />
      <meshStandardMaterial color={color} transparent opacity={0.35} depthWrite={false} />
    </mesh>
  )
}

function BoxOverlay({ r, color }: { r: BoxRegion; color: string }) {
  const size: Vec3 = [r.max[0] - r.min[0], r.max[1] - r.min[1], r.max[2] - r.min[2]]
  const center: Vec3 = [
    (r.min[0] + r.max[0]) / 2,
    (r.min[1] + r.max[1]) / 2,
    (r.min[2] + r.max[2]) / 2,
  ]
  return (
    <mesh position={center}>
      <boxGeometry args={size} />
      <meshStandardMaterial color={color} transparent opacity={0.3} depthWrite={false} />
    </mesh>
  )
}

function FaceOverlay({
  r, color, bounds, pitch,
}: {
  r: FaceRegion; color: string; bounds: MeshBounds; pitch: number
}) {
  const thickness = r.thickness ?? pitch
  const { center, size } = faceSlab(r.name, bounds, thickness)
  return (
    <mesh position={center}>
      <boxGeometry args={size} />
      <meshStandardMaterial color={color} transparent opacity={0.35} depthWrite={false} />
    </mesh>
  )
}

function faceSlab(
  face: FaceName,
  b: MeshBounds,
  thickness: number,
): { center: Vec3; size: Vec3 } {
  const dx = b.max[0] - b.min[0]
  const dy = b.max[1] - b.min[1]
  const dz = b.max[2] - b.min[2]
  const cx = (b.min[0] + b.max[0]) / 2
  const cy = (b.min[1] + b.max[1]) / 2
  const cz = (b.min[2] + b.max[2]) / 2
  switch (face) {
    case 'x_min': return { center: [b.min[0] + thickness / 2, cy, cz], size: [thickness, dy, dz] }
    case 'x_max': return { center: [b.max[0] - thickness / 2, cy, cz], size: [thickness, dy, dz] }
    case 'y_min': return { center: [cx, b.min[1] + thickness / 2, cz], size: [dx, thickness, dz] }
    case 'y_max': return { center: [cx, b.max[1] - thickness / 2, cz], size: [dx, thickness, dz] }
    case 'z_min': return { center: [cx, cy, b.min[2] + thickness / 2], size: [dx, dy, thickness] }
    case 'z_max': return { center: [cx, cy, b.max[2] - thickness / 2], size: [dx, dy, thickness] }
  }
}

function ForceShape({
  stored, bounds, pitch,
}: {
  stored: Stored<ForceRegion>; bounds: MeshBounds; pitch: number
}) {
  const r = stored.region
  // Determina o centro geometrico da regiao pra plantar a seta
  let origin: Vec3
  if (r.type === 'sphere') {
    origin = r.center
  } else if (r.type === 'box') {
    origin = [
      (r.min[0] + r.max[0]) / 2,
      (r.min[1] + r.max[1]) / 2,
      (r.min[2] + r.max[2]) / 2,
    ]
  } else {
    origin = faceSlab(r.name, bounds, r.thickness ?? pitch).center
  }

  return (
    <group>
      <RegionShape stored={stored as never} color={COLOR_FORCE} bounds={bounds} pitch={pitch} />
      <ForceArrow origin={origin} vector={r.vector} sceneExtent={Math.max(
        bounds.max[0]-bounds.min[0], bounds.max[1]-bounds.min[1], bounds.max[2]-bounds.min[2],
      )} />
    </group>
  )
}

function ForceArrow({ origin, vector, sceneExtent }: { origin: Vec3; vector: Vec3; sceneExtent: number }) {
  // Seta com tamanho proporcional ao bbox da peca (vetor normalizado * 30%)
  const v = new THREE.Vector3(...vector)
  const length = v.length()
  if (length === 0) return null
  const dir = v.clone().normalize()
  const len = sceneExtent * 0.3
  return (
    <arrowHelper args={[dir, new THREE.Vector3(...origin), len, 0xff3a3a, len * 0.2, len * 0.12]} />
  )
}
