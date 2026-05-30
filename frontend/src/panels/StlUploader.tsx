import { useRef } from 'react'
import { useJob } from '../store/job'
import { useRegions } from '../store/regions'

export function StlUploader() {
  const inputRef = useRef<HTMLInputElement>(null)
  const inputFile = useJob((s) => s.inputFile)
  const setInput = useJob((s) => s.setInput)
  const clearRegions = useRegions((s) => s.clear)

  const onPick = () => inputRef.current?.click()
  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null
    setInput(f)
    clearRegions()
  }

  return (
    <section className="panel-section">
      <h3>1 · STL de entrada</h3>
      <input
        ref={inputRef}
        type="file"
        accept=".stl"
        style={{ display: 'none' }}
        onChange={onFile}
      />
      <button className="primary" onClick={onPick}>
        {inputFile ? 'Trocar STL…' : 'Selecionar STL…'}
      </button>
      {inputFile && (
        <div className="meta">
          {inputFile.name} · {(inputFile.size / 1024).toFixed(1)} KB
        </div>
      )}
    </section>
  )
}
