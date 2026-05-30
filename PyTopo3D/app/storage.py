"""Paths e helpers de filesystem.

Tudo resolvido a partir da raiz do projeto PyTopo3D (parent deste pacote).
- uploads/<run_id>.stl    : STLs enviadas pelo cliente
- runs/<experiment_name>/ : output do run_optimization (ja criado pelo wrapper)
"""

from __future__ import annotations

import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOADS_DIR = PROJECT_ROOT / "uploads"
RUNS_DIR = PROJECT_ROOT / "runs"


def ensure_dirs() -> None:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    RUNS_DIR.mkdir(parents=True, exist_ok=True)


def upload_path(run_id: str) -> Path:
    return UPLOADS_DIR / f"{run_id}.stl"


def delete_paths(paths: list[Path]) -> None:
    for p in paths:
        if p is None:
            continue
        try:
            if p.is_dir():
                shutil.rmtree(p)
            elif p.exists():
                p.unlink()
        except Exception:
            pass
