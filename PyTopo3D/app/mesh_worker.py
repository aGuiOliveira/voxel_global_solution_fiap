"""Worker thread que extrai mesh (marching cubes) do xPhys a cada N iteracoes
e grava como GLB em runs/{run_id}/iters/{n}.glb, para preview ao vivo no
frontend durante a otimizacao.

Design:
- O optimizer chama `worker.submit(loop, xPhys)` a cada iteracao via
  iter_callback. submit() so guarda uma COPIA do xPhys no slot pendente
  se `loop % frequency == 0`. NAO bloqueia o loop SIMP.
- Uma thread daemon consome o slot, roda marching_cubes + trimesh.export,
  grava GLB, e dispara `on_ready(loop)` para o JobManager atualizar
  job.progress.latest_iter_mesh.
- Slot e' SLOT, nao queue: se um snapshot mais novo chega antes do
  anterior terminar, o anterior e' descartado. Para grids grandes
  (~150k voxels, marching_cubes ~3-5s) o frontend pula iters
  (10 -> 40 -> 70), o que e' desejado.
- stop() encerra a thread limpo e bloqueia ate ela sair.

Custo de performance: o submit() so faz np.ndarray.copy() e set de um lock,
~ms. A extracao roda em paralelo, fora do loop principal. Overhead esperado
na otimizacao: <2%.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable, Optional, Tuple

import numpy as np
import trimesh
from skimage import measure

logger = logging.getLogger("topo3d.api.mesh_worker")


class MeshPreviewWorker:
    def __init__(
        self,
        iters_dir: Path,
        frequency: int = 10,
        on_ready: Optional[Callable[[int], None]] = None,
        level: float = 0.5,
    ) -> None:
        self.iters_dir = iters_dir
        self.frequency = max(1, int(frequency))
        self.on_ready = on_ready
        self.level = level

        self._lock = threading.Lock()
        self._pending: Optional[Tuple[int, np.ndarray]] = None
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread = threading.Thread(
            target=self._loop, name="MeshPreviewWorker", daemon=True
        )
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self.iters_dir.mkdir(parents=True, exist_ok=True)
        self._thread.start()
        self._started = True

    def submit(self, loop_idx: int, xPhys: np.ndarray) -> None:
        if loop_idx % self.frequency != 0:
            return
        snap = np.asarray(xPhys, dtype=np.float32).copy()
        with self._lock:
            self._pending = (loop_idx, snap)
        self._wake.set()

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self._wake.set()
        if self._started:
            self._thread.join(timeout=timeout)

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._wake.wait(timeout=1.0)
            self._wake.clear()
            if self._stop.is_set():
                break
            with self._lock:
                job = self._pending
                self._pending = None
            if job is None:
                continue
            loop_idx, xPhys = job
            try:
                self._extract_and_save(loop_idx, xPhys)
                if self.on_ready is not None:
                    try:
                        self.on_ready(loop_idx)
                    except Exception as cb_err:
                        logger.warning(
                            "on_ready callback raised %s: %s",
                            type(cb_err).__name__, cb_err,
                        )
            except Exception as e:
                logger.warning(
                    "mesh extraction failed at iter %d: %s: %s",
                    loop_idx, type(e).__name__, e,
                )

    def _extract_and_save(self, loop_idx: int, xPhys: np.ndarray) -> None:
        # Pad com zeros para que marching cubes feche as bordas (igual ao
        # padrao de pytopo3d.utils.export.voxel_to_stl com padding=1).
        padded = np.pad(xPhys, 1, mode="constant", constant_values=0.0)

        # marching_cubes pode levantar ValueError se o iso-level nao tem
        # superficie (peca toda vazia ou toda solida na primeira iter).
        try:
            verts, faces, _normals, _ = measure.marching_cubes(padded, level=self.level)
        except (ValueError, RuntimeError):
            return

        # Compensa o padding (1 voxel) — mesma logica de export.py:124
        verts = verts - 1.0

        mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)

        out_path = self.iters_dir / f"{loop_idx}.glb"
        tmp_path = self.iters_dir / f"{loop_idx}.glb.tmp"
        # Grava atomicamente: escreve em .tmp e renomeia, pra que o frontend
        # nunca leia um arquivo parcial.
        mesh.export(tmp_path, file_type="glb")
        tmp_path.replace(out_path)
