"""FastAPI app para o engine PyTopo3D.

Endpoints minimos da Fase 1:
    POST   /optimize                  multipart: STL (opcional) + params JSON
    GET    /runs/{id}                 status do job
    GET    /runs/{id}/result          dict completo de run_optimization
    GET    /runs/{id}/files/{kind}    download de artefatos
    DELETE /runs/{id}                 remove run_dir e job da memoria
    GET    /healthz                   ping

Single-process, in-memory, sem auth. Subir com:
    uvicorn app.main:app --reload --port 8000
(cwd = pasta PyTopo3D, env conda pytopo3d ativo)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import ValidationError

from .jobs import JobManager
from .models import OptimizeRequest, RunResult, RunStatus
from .storage import RUNS_DIR, delete_paths, ensure_dirs, upload_path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
)

app = FastAPI(title="PyTopo3D API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs = JobManager()
ensure_dirs()


FileKind = Literal[
    "input_stl",
    "optimized_stl",
    "optimized_voxel_stl",
    "animation",
    "density_npy",
]


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.post("/optimize", response_model=RunStatus)
async def optimize(
    params: str = Form(default="{}"),
    file: Optional[UploadFile] = File(default=None),
) -> RunStatus:
    """Cria um job de otimizacao.

    - `params`: string JSON com os campos de OptimizeRequest.
    - `file`: STL do design space (opcional; sem file, roda em caixa nelx/y/z).
    """
    try:
        params_dict = json.loads(params) if params else {}
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"params nao e JSON valido: {e}")
    try:
        req = OptimizeRequest.model_validate(params_dict)
    except ValidationError as e:
        raise HTTPException(422, e.errors())

    kwargs = req.model_dump(exclude_none=True)

    input_stl: Optional[Path] = None
    if file is not None:
        # Precisamos do run_id antes do submit pra nomear o arquivo. Como o
        # JobManager gera o id internamente, escrevemos com um nome temporario
        # e renomeamos depois — mas mais simples: usar o nome do upload e
        # apontar para esse caminho. O JobManager gera o run_id e nao precisa
        # casar com o nome do upload.
        from uuid import uuid4

        upload_id = uuid4().hex[:12]
        input_stl = upload_path(upload_id)
        with input_stl.open("wb") as fp:
            while chunk := await file.read(1 << 20):
                fp.write(chunk)

    job = jobs.submit(kwargs, input_stl)
    return _job_to_status(job)


@app.get("/runs/{run_id}", response_model=RunStatus)
def get_run(run_id: str) -> RunStatus:
    job = jobs.get(run_id)
    if job is None:
        raise HTTPException(404, "run nao encontrado")
    return _job_to_status(job)


@app.get("/runs", response_model=list[RunStatus])
def list_runs() -> list[RunStatus]:
    return [_job_to_status(j) for j in jobs.list()]


@app.get("/runs/{run_id}/result", response_model=RunResult)
def get_result(run_id: str) -> RunResult:
    job = jobs.get(run_id)
    if job is None:
        raise HTTPException(404, "run nao encontrado")
    return RunResult(
        run_id=job.run_id,
        status=job.status,
        result=job.result,
        error=job.error,
    )


@app.get("/runs/{run_id}/files/{kind}")
def get_file(run_id: str, kind: FileKind) -> FileResponse:
    job = jobs.get(run_id)
    if job is None:
        raise HTTPException(404, "run nao encontrado")
    if job.status != "done" or not job.result:
        raise HTTPException(409, f"run nao concluido (status={job.status})")

    path = _resolve_file(job.result, job.input_stl_path, kind)
    if path is None:
        raise HTTPException(404, f"artefato '{kind}' nao existe pra esse run")
    if not path.exists():
        raise HTTPException(404, f"arquivo sumiu do disco: {path}")

    media = "model/stl" if path.suffix.lower() == ".stl" else "application/octet-stream"
    return FileResponse(path, media_type=media, filename=path.name)


@app.get("/runs/{run_id}/files/iter/{iter_idx}")
def get_iter_mesh(run_id: str, iter_idx: int) -> FileResponse:
    """GLB do mesh de preview daquela iteracao (gerado pelo MeshPreviewWorker)."""
    job = jobs.get(run_id)
    if job is None:
        raise HTTPException(404, "run nao encontrado")
    iters_dir = RUNS_DIR / run_id / "iters"
    path = iters_dir / f"{iter_idx}.glb"
    if not path.exists():
        raise HTTPException(404, f"mesh da iter {iter_idx} nao existe (ainda)")
    return FileResponse(path, media_type="model/gltf-binary", filename=path.name)


@app.post("/runs/{run_id}/cancel", response_model=RunStatus)
def cancel_run(run_id: str) -> RunStatus:
    job = jobs.cancel(run_id)
    if job is None:
        raise HTTPException(404, "run nao encontrado")
    return _job_to_status(job)


@app.delete("/runs/{run_id}")
def delete_run(run_id: str) -> dict:
    job = jobs.delete(run_id)
    if job is None:
        raise HTTPException(404, "run nao encontrado")
    paths_to_remove: list[Path] = []
    if job.input_stl_path:
        paths_to_remove.append(job.input_stl_path)
    if job.result and job.result.get("run_dir"):
        paths_to_remove.append(Path(job.result["run_dir"]))
    delete_paths(paths_to_remove)
    return {"deleted": run_id}


def _job_to_status(job) -> RunStatus:
    return RunStatus(
        run_id=job.run_id,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        elapsed_s=job.elapsed_s,
        error=job.error,
        progress=job.progress,
        log_tail=job.log_tail[-20:] if job.log_tail else [],
        latest_iter_mesh=job.latest_iter_mesh,
    )


def _resolve_file(result: dict, input_stl: Optional[Path], kind: FileKind) -> Optional[Path]:
    if kind == "input_stl":
        return input_stl
    if kind == "optimized_stl":
        p = result.get("stl_path")
        return Path(p) if p else None
    if kind == "optimized_voxel_stl":
        p = result.get("stl_voxel_path")
        return Path(p) if p else None
    if kind == "animation":
        p = result.get("animation_path")
        return Path(p) if p else None
    if kind == "density_npy":
        run_dir = result.get("run_dir")
        if not run_dir:
            return None
        return Path(run_dir) / "optimized_design.npy"
    return None
