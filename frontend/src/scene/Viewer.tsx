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
        // up=Z: STL/CAD usa Z-up, mas o three.js e' Y-up por padrao. Sem isso a
        // peca aparece "deitada" (o eixo de altura Z fica na horizontal). Mudamos
        // so a convencao de camera — nenhuma geometria/coordenada e' tocada, entao
        // picking, overlays e bbox seguem no espaco nativo da STL.
        camera={{ up: [0, 0, 1], position: [80, -80, 60], fov: 45, near: 0.1, far: 5000 }}
        onPointerMissed={() => picking && cancelPicking()}
      >
        <color attach="background" args={["#1b1f24"]} />
        <ambientLight intensity={0.5} />
        <directionalLight position={[60, -60, 100]} intensity={1.0} castShadow />
        <directionalLight position={[-60, 80, -40]} intensity={0.3} />

        <axesHelper args={[20]} />
        <Grid
          args={[200, 200]}
          cellSize={5} sectionSize={20}
          cellColor="#3a4250" sectionColor="#5a6478"
          fadeDistance={300} infiniteGrid
          // Grid do drei nasce no plano XZ (chao Y-up). Com Z-up o chao e' o
          // plano XY — rotaciona 90deg em X pra a peca ficar "em pe" sobre ele.
          rotation={[Math.PI / 2, 0, 0]}
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
