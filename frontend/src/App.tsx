import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { JobPanel } from './panels/JobPanel'
import { ParamsForm } from './panels/ParamsForm'
import { RegionList } from './panels/RegionList'
import { StlUploader } from './panels/StlUploader'
import { Viewer } from './scene/Viewer'
import './App.css'

const qc = new QueryClient()

function App() {
  return (
    <QueryClientProvider client={qc}>
      <div className="layout">
        <aside className="side left">
          <header className="brand">
            <h1>PyTopo3D</h1>
            <p className="meta">topology optimization</p>
          </header>
          <StlUploader />
          <ParamsForm />
          <RegionList title="Apoios (supports)"   group="supports"   color="#3a86ff" />
          <RegionList title="Forças (forces)"     group="forces"     color="#ff3a3a" />
          <RegionList title="Sólidas (keep_solid)" group="keep_solid" color="#3fdc6c" />
        </aside>

        <main className="canvas-wrap">
          <Viewer />
        </main>

        <JobPanel />
      </div>
    </QueryClientProvider>
  )
}

export default App
