"""JobManager: enfileira/executa otimizacoes em um worker unico.

- 1 job de cada vez (ThreadPoolExecutor max_workers=1): cada run usa todos
  os cores do CPU. Demais requests ficam em status="queued".
- Estado in-memory (dict). Persistencia real e o filesystem (runs/<exp>/).
- Cada Job guarda o dict completo retornado por run_optimization quando
  concluir.
"""

from __future__ import annotations

import logging
import threading
import time
import traceback
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from optimize import run_optimization

from . import progress as progress_mod
from .mesh_worker import MeshPreviewWorker
from .storage import RUNS_DIR

LIVE_PREVIEW_FREQUENCY = 10

logger = logging.getLogger("topo3d.api.jobs")


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class Job:
    run_id: str
    params: dict
    input_stl_path: Optional[Path]
    status: str = "queued"
    created_at: str = field(default_factory=_now_iso)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    future: Optional[Future] = None
    progress: Optional[dict] = None
    log_tail: list[str] = field(default_factory=list)
    cancel_event: threading.Event = field(default_factory=threading.Event)
    latest_iter_mesh: Optional[int] = None

    @property
    def elapsed_s(self) -> Optional[float]:
        if self.started_at is None:
            return None
        end = self.finished_at or _now_iso()
        try:
            t0 = datetime.fromisoformat(self.started_at).timestamp()
            t1 = datetime.fromisoformat(end).timestamp()
            return t1 - t0
        except Exception:
            return None


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1)

    def submit(self, params: dict, input_stl_path: Optional[Path]) -> Job:
        run_id = uuid.uuid4().hex[:12]
        job = Job(run_id=run_id, params=params, input_stl_path=input_stl_path)
        with self._lock:
            self._jobs[run_id] = job
        job.future = self._executor.submit(self._run, run_id)
        return job

    def _run(self, run_id: str) -> None:
        job = self._jobs[run_id]
        # Se ja cancelado antes mesmo de comecar (na fila)
        if job.cancel_event.is_set():
            job.status = "cancelled"
            job.finished_at = _now_iso()
            return
        job.status = "running"
        job.started_at = _now_iso()
        t0 = time.time()
        handler = progress_mod.attach(job)
        # Fixa experiment_name = run_id pra que run_dir = RUNS_DIR/run_id seja
        # previsivel ja agora — o worker precisa do path antes da otimizacao
        # comecar, e o endpoint /runs/{id}/files/iter/{n} casa direto.
        kwargs = dict(job.params)
        if job.input_stl_path is not None:
            kwargs["input_stl_path"] = str(job.input_stl_path)
        kwargs.setdefault("base_dir", str(RUNS_DIR))
        kwargs["use_gpu"] = False  # Fase 0/1: CPU-only
        kwargs.setdefault("experiment_name", run_id)

        run_dir = RUNS_DIR / kwargs["experiment_name"]

        def _on_mesh_ready(loop_idx: int) -> None:
            job.latest_iter_mesh = loop_idx

        mesh_worker = MeshPreviewWorker(
            iters_dir=run_dir / "iters",
            frequency=LIVE_PREVIEW_FREQUENCY,
            on_ready=_on_mesh_ready,
        )
        mesh_worker.start()
        kwargs["iter_callback"] = mesh_worker.submit

        try:
            logger.info("Job %s iniciado: %s", run_id, kwargs.get("experiment_name"))
            result = run_optimization(**kwargs)
            job.result = _jsonable(result)
            job.status = "done"
            logger.info("Job %s done em %.1fs", run_id, time.time() - t0)
        except progress_mod.CancelledError:
            job.status = "cancelled"
            logger.info("Job %s cancelado em %.1fs", run_id, time.time() - t0)
        except Exception as e:
            job.error = f"{type(e).__name__}: {e}\n{traceback.format_exc()}"
            job.status = "error"
            logger.exception("Job %s falhou", run_id)
        finally:
            progress_mod.detach(handler)
            mesh_worker.stop()
            job.finished_at = _now_iso()

    def cancel(self, run_id: str) -> Optional[Job]:
        job = self._jobs.get(run_id)
        if job is None:
            return None
        if job.status in ("done", "error", "cancelled"):
            return job  # nada a cancelar
        job.cancel_event.set()
        # Se ainda esta na fila (queued), tenta tirar do executor
        if job.future is not None and not job.future.running():
            job.future.cancel()
            if job.status == "queued":
                job.status = "cancelled"
                job.finished_at = _now_iso()
        return job

    def get(self, run_id: str) -> Optional[Job]:
        return self._jobs.get(run_id)

    def list(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())

    def delete(self, run_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.pop(run_id, None)


def _jsonable(d: dict) -> dict:
    """run_optimization retorna paths em str, mas alguns valores podem ser
    numpy scalars. Faz conversao defensiva pra dict serializavel."""
    import numpy as np

    out = {}
    for k, v in d.items():
        if isinstance(v, (np.integer,)):
            out[k] = int(v)
        elif isinstance(v, (np.floating,)):
            out[k] = float(v)
        elif isinstance(v, np.ndarray):
            out[k] = v.tolist()
        elif isinstance(v, Path):
            out[k] = str(v)
        else:
            out[k] = v
    return out
