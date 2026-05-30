"""Captura progresso do otimizador via logging handler.

PyTopo3D loga cada iteracao no logger "pytopo3d.core.optimizer" como:
    Iter  123: Obj=  45.6789, ΔObj=  -0.1234, Vol= 0.345, change= 0.012, time= 0.45s

Este handler intercepta esses logs, parseia, atualiza job.progress + job.log_tail,
e tambem serve como ponto de cancelamento: se job.cancel_event estiver setado,
levanta CancelledError que propaga pra cima do logger.info(...) no engine e
encerra o loop de otimizacao limpo (Handler.handle nao envolve emit em
try/except, so try/finally — entao excecoes propagam).

Anexado no logger ROOT (e nao em 'pytopo3d') porque setup_logger() do PyTopo3D
limpa os handlers do logger 'pytopo3d' dentro de setup_experiment. Filtramos por
record.name pra so capturar logs do engine.
"""

from __future__ import annotations

import logging
import re
import threading
from collections import deque
from typing import TYPE_CHECKING, Deque

if TYPE_CHECKING:
    from .jobs import Job


class CancelledError(Exception):
    """Levantada de dentro do handler pra interromper o otimizador."""


_ITER_RE = re.compile(
    r"Iter\s+(\d+):\s*"
    r"Obj=\s*([-+]?\d+\.?\d*)\s*,\s*"
    r"[^=]*=\s*([-+]?\d+\.?\d*)\s*,\s*"
    r"Vol=\s*([-+]?\d+\.?\d*)\s*,\s*"
    r"change=\s*([-+]?\d+\.?\d*)\s*,\s*"
    r"time=\s*([-+]?\d+\.?\d*)",
)

LOG_TAIL_MAX = 60


class JobProgressHandler(logging.Handler):
    def __init__(self, job: "Job"):
        super().__init__(level=logging.INFO)
        self.job = job
        self._lock = threading.Lock()
        self._tail: Deque[str] = deque(maxlen=LOG_TAIL_MAX)

    def emit(self, record: logging.LogRecord) -> None:
        if not record.name.startswith("pytopo3d"):
            return
        try:
            msg = record.getMessage()
        except Exception:
            return

        with self._lock:
            self._tail.append(msg)
            self.job.log_tail = list(self._tail)

            m = _ITER_RE.search(msg)
            if m:
                try:
                    self.job.progress = {
                        "iter": int(m.group(1)),
                        "maxloop": int(self.job.params.get("maxloop", 0)) or None,
                        "compliance": float(m.group(2)),
                        "compliance_delta": float(m.group(3)),
                        "volume": float(m.group(4)),
                        "change": float(m.group(5)),
                        "iter_time_s": float(m.group(6)),
                    }
                except ValueError:
                    pass

        # Checkpoint de cancelamento — apos persistir progress, levanta se pedido
        if self.job.cancel_event.is_set():
            raise CancelledError("cancelado pelo usuario")


def attach(job: "Job") -> JobProgressHandler:
    handler = JobProgressHandler(job)
    logging.getLogger().addHandler(handler)
    return handler


def detach(handler: JobProgressHandler) -> None:
    logging.getLogger().removeHandler(handler)
