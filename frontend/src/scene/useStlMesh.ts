// Hooks util: carrega uma STL ou GLB de uma URL e retorna a BufferGeometry.
// STLLoader e GLTFLoader vivem em three/examples — drei nao expoe.

import { useEffect, useState } from 'react'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import type { BufferGeometry, Mesh } from 'three'

export function useStlGeometry(url: string | null): BufferGeometry | null {
  const [geom, setGeom] = useState<BufferGeometry | null>(null)

  useEffect(() => {
    if (!url) {
      setGeom(null)
      return
    }
    let cancelled = false
    const loader = new STLLoader()
    loader.load(
      url,
      (g) => {
        if (cancelled) return
        g.computeVertexNormals()
        setGeom(g)
      },
      undefined,
      (err) => {
        console.error('STL load failed', err)
      },
    )
    return () => {
      cancelled = true
    }
  }, [url])

  return geom
}

// Extrai a primeira BufferGeometry de um GLB. 404 e' silencioso (a iter
// pode nao estar pronta ainda); demais erros vao pro console.
export function useGlbGeometry(url: string | null): BufferGeometry | null {
  const [geom, setGeom] = useState<BufferGeometry | null>(null)

  useEffect(() => {
    if (!url) {
      setGeom(null)
      return
    }
    let cancelled = false
    const loader = new GLTFLoader()
    loader.load(
      url,
      (gltf) => {
        if (cancelled) return
        let found: BufferGeometry | null = null
        gltf.scene.traverse((obj) => {
          if (!found && (obj as Mesh).isMesh) {
            const m = obj as Mesh
            found = m.geometry as BufferGeometry
          }
        })
        if (found) {
          (found as BufferGeometry).computeVertexNormals()
          setGeom(found)
        }
      },
      undefined,
      (err) => {
        // 404 e' esperado quando o frontend chega antes do GLB ser escrito;
        // silenciamos via reduce de log.
        const msg = (err as { message?: string })?.message ?? String(err)
        if (!/404/.test(msg)) console.error('GLB load failed', err)
      },
    )
    return () => {
      cancelled = true
    }
  }, [url])

  return geom
}
