// Canvas R3F: input + optimized + overlays + axes + grid.

import { Bounds, Grid, OrbitControls } from '@react-three/drei'
import { Canvas } from '@react-three/fiber'
import { InputMesh } from './InputMesh'
import { OptimizedMesh } from './OptimizedMesh'
import { RegionOverlays } from './RegionOverlays'
import { useJob } from '../store/job'
import { useRegions } from '../store/regions'

export function Viewer() {
  const inputUrl = useJob((s) => s.inputUrl)
  const picking = useRegions((s) => s.picking)
  const cancelPicking = useRegions((s) => s.cancelPicking)

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <Canvas
        shadows
        camera={{ position: [80, 80, 80], fov: 45, near: 0.1, far: 5000 }}
        onPointerMissed={() => picking && cancelPicking()}
      >
        <color attach="background" args={["#1b1f24"]} />
        <ambientLight intensity={0.5} />
        <directionalLight position={[60, 100, 60]} intensity={1.0} castShadow />
        <directionalLight position={[-60, -40, -80]} intensity={0.3} />

        <axesHelper args={[20]} />
        <Grid
          args={[200, 200]}
          cellSize={5} sectionSize={20}
          cellColor="#3a4250" sectionColor="#5a6478"
          fadeDistance={300} infiniteGrid
        />

        <Bounds fit clip observe margin={1.2} key={inputUrl ?? 'empty'}>
          <InputMesh />
          <OptimizedMesh />
        </Bounds>
        <RegionOverlays />

        <OrbitControls makeDefault enableDamping dampingFactor={0.1} />
      </Canvas>

      {picking && (
        <div className="picking-banner">
          Clique na peça para definir {picking.field} — Esc/clique no vazio cancela
        </div>
      )}
    </div>
  )
}
