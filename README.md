# Voxel — Otimização Topológica 3D com UI Web

** Projeto destinado a entrega da Global Solution 2026 da FIAP.

Aplicação web pra otimização topológica 3D via SIMP. O usuário sobe uma STL,
define apoios/forças/regiões sólidas direto numa visualização 3D, dispara a
otimização e acompanha o resultado evoluindo ao vivo.

Engine: [PyTopo3D](./PyTopo3D/) (SIMP em Python). Backend:
FastAPI. Frontend: React + Vite + React Three Fiber.

## Features

- Upload de STL como design space
- Definição de boundary conditions via UI 3D:
  - **Apoios** (DOFs fixos) por face / esfera / box
  - **Forças** com vetor (Fx, Fy, Fz) por face / esfera / box
  - **Regiões keep_solid** (material que nunca pode ser removido)
- Otimização SIMP via PyTopo3D com solver Pardiso (multi-core CPU)
- **Live preview** durante o run: peça atualiza no canvas 3D a cada 10 iter
  via marching cubes em thread separada (overhead ≈ 0% na otimização)
- Métricas ao vivo (compliance, change, volume) + log feed
- Cancelamento polite no meio do run
- Download da STL otimizada em mm (alinhada ao espaço da entrada)
- Estimador de tamanho do grid no painel de parâmetros, com aviso quando
  vai estourar a RAM (Pardiso error -2)

## Arquitetura

```
gs_back/
├── PyTopo3D/                  ← backend + engine
│   ├── pytopo3d/              ← engine SIMP (upstream + 3 patches locais)
│   ├── app/                   ← FastAPI
│   │   ├── main.py            ← endpoints HTTP
│   │   ├── jobs.py            ← JobManager (ThreadPoolExecutor max_workers=1)
│   │   ├── progress.py        ← captura "Iter X: ..." do logger pra UI
│   │   ├── mesh_worker.py     ← thread que gera GLB do live preview
│   │   ├── models.py          ← pydantic v2
│   │   └── storage.py         ← paths (uploads/, runs/)
│   ├── optimize.py            ← wrapper run_optimization()
│   ├── environment.yml        ← conda env "pytopo3d"
│   ├── test_api.py            ← smoke test da API
│   ├── test_bracket.stl       ← STL de teste (~5 MB, ~30k voxels @ pitch=2)
│   └── satellite_bracket.stl  ← STL maior (peça do TCC)
└── frontend/                  ← React + Vite + TS
    ├── vite.config.ts         ← proxy /api/* → 127.0.0.1:8000
    └── src/
        ├── api/               ← fetch wrappers + tipos
        ├── store/             ← Zustand (regions, job)
        ├── scene/             ← R3F: Viewer, InputMesh, OptimizedMesh, ...
        └── panels/            ← StlUploader, ParamsForm, RegionList, JobPanel
```

## Pré-requisitos

- **Conda** (Anaconda ou Miniconda)
- **Node.js** 18+
- **Windows / Linux / macOS** — testado em Windows 11
- ~8 GB de RAM livre pra peças médias (~150k voxels). Pardiso é solver direto
  (fatoração LU) e consome muita memória; o estimador no UI avisa quando
  o grid configurado vai provavelmente estourar.

## Setup

### 1. Clonar

```bash
git clone <url> gs_back
cd gs_back
```

### 2. Backend — env conda

```bash
cd PyTopo3D
conda env create -f environment.yml
conda activate pytopo3d
pip install fastapi 'uvicorn[standard]' python-multipart httpx
```

> Os pacotes da API (FastAPI etc) não estão no `environment.yml` porque ele é
> do upstream PyTopo3D. Vão à parte com `pip install`.

### 3. Frontend

```bash
cd ../frontend
npm install
```

## Como rodar

Em dois terminais separados:

**Terminal 1 — backend:**

```bash
conda activate pytopo3d
cd PyTopo3D
uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info
```

**Terminal 2 — frontend:**

```bash
cd frontend
npm run dev
```

Abre o navegador em **http://localhost:5173**.

### Smoke test backend (opcional)

Com o uvicorn no ar:

```bash
conda activate pytopo3d
cd PyTopo3D
python test_api.py
```

Sobe `test_bracket.stl`, polla até `done`, baixa a STL otimizada e valida
watertight. Leva ~3 min em CPU.

## Endpoints

| Método  | Rota                                  | Função                                   |
| ------- | ------------------------------------- | ---------------------------------------- |
| GET     | `/healthz`                            | Ping                                     |
| POST    | `/optimize`                           | Multipart: params (JSON) + STL → cria job|
| GET     | `/runs/{id}`                          | Status + progress + log_tail + latest_iter_mesh |
| GET     | `/runs/{id}/result`                   | Dict completo de `run_optimization`      |
| GET     | `/runs/{id}/files/{kind}`             | Download: input_stl / optimized_stl / animation / density_npy |
| GET     | `/runs/{id}/files/iter/{n}`           | GLB do preview da iter `n` (live)        |
| POST    | `/runs/{id}/cancel`                   | Cancela job                              |
| DELETE  | `/runs/{id}`                          | Remove run_dir + job da memória          |

## ⚠ Notas importantes

### Patches locais no PyTopo3D

O diretório `PyTopo3D/pytopo3d/` é um **fork modificado** do upstream
[PyTopo3D](https://github.com/aamir-1/PyTopo3D), com correções e extensões
locais. **Não dar `git pull` cego no upstream** — vai sobrescrever:

- `pytopo3d/utils/oc_update.py` — fix de NameError quando rodando CPU-only
  (referência a `cp` mesmo sem CuPy importado)
- `pytopo3d/utils/filter.py` — mesma classe de bug
- `pytopo3d/core/optimizer.py` — adicionado `iter_callback` opcional pro
  live preview
- `pytopo3d/runners/experiment.py` — propaga `iter_callback`
- `pytopo3d/utils/export.py` — trocado Laplacian por Taubin no smoothing
  do `voxel_to_stl`. Laplacian distorcia vertices da fronteira (face do
  apoio em keep_solid) gerando triângulos longos visualmente esquisitos.
  Taubin preserva volume/fronteira.

### Estado in-memory

O `JobManager` guarda jobs em RAM. Reiniciar o uvicorn perde a lista de jobs
ativos (mas os arquivos em `runs/<id>/` persistem em disco).

### CPU-only

Engine roda em CPU via PyPardiso. Suporte GPU (CuPy) foi avaliado e
descartado: a placa-alvo do projeto (MX-series, 2 GB VRAM) é pequena demais
pra grids reais e memory-bound. Pra reabilitar GPU no futuro: descomentar
`cupy-cuda12x` no `environment.yml` e passar `use_gpu=True` no
`run_optimization()`.

## Stack resumida

**Backend:** Python 3.10 · FastAPI · Pydantic v2 · NumPy · SciPy · scikit-image · trimesh · PyPardiso (Intel MKL)

**Frontend:** TypeScript · React 19 · Vite · React Three Fiber · drei · Three.js · Zustand · TanStack Query
