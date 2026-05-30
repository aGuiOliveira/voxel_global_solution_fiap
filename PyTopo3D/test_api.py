"""Smoke test da Fase 1 da API FastAPI.

Pre-condicoes:
  - uvicorn rodando em http://127.0.0.1:8000 (`uvicorn app.main:app --port 8000`)
  - env conda pytopo3d ativo
  - test_bracket.stl presente em PyTopo3D/

Fluxo:
  1. healthz
  2. POST /optimize com STL + cantilever (supports x_min, force x_max -Z)
  3. polling em GET /runs/{id} ate status=done (ou error)
  4. GET /runs/{id}/result + GET /runs/{id}/files/optimized_stl
  5. valida watertight do mesh baixado

Roda com:  python test_api.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx
import trimesh

BASE_URL = "http://127.0.0.1:8000"
STL_PATH = Path(__file__).parent / "test_bracket.stl"
POLL_INTERVAL_S = 5
POLL_TIMEOUT_S = 60 * 30  # 30 min: peca pequena com pitch=2 leva poucos min


def main() -> int:
    if not STL_PATH.exists():
        print(f"ERRO: STL nao encontrada: {STL_PATH}", file=sys.stderr)
        return 1

    client = httpx.Client(base_url=BASE_URL, timeout=60.0)

    # 1. healthz
    r = client.get("/healthz")
    r.raise_for_status()
    assert r.json() == {"ok": True}, r.json()
    print("healthz OK")

    # 2. POST /optimize
    params = {
        "volfrac": 0.3,
        "pitch": 2.0,
        "create_animation": False,
        "supports": [{"type": "face", "name": "x_min", "thickness": 4.0}],
        "forces": [{"type": "face", "name": "x_max", "thickness": 4.0,
                    "vector": [0, 0, -1.0]}],
    }
    with STL_PATH.open("rb") as fp:
        r = client.post(
            "/optimize",
            data={"params": json.dumps(params)},
            files={"file": (STL_PATH.name, fp, "model/stl")},
        )
    r.raise_for_status()
    status = r.json()
    run_id = status["run_id"]
    print(f"job enfileirado: run_id={run_id}, status={status['status']}")

    # 3. polling
    t_start = time.time()
    final_status = None
    while time.time() - t_start < POLL_TIMEOUT_S:
        r = client.get(f"/runs/{run_id}")
        r.raise_for_status()
        s = r.json()
        elapsed = s.get("elapsed_s")
        print(f"  [{int(time.time()-t_start):4d}s] status={s['status']} "
              f"job_elapsed={elapsed and round(elapsed,1)}")
        if s["status"] in ("done", "error"):
            final_status = s
            break
        time.sleep(POLL_INTERVAL_S)

    if final_status is None:
        print(f"TIMEOUT apos {POLL_TIMEOUT_S}s", file=sys.stderr)
        return 2
    if final_status["status"] == "error":
        print(f"JOB FALHOU: {final_status.get('error')}", file=sys.stderr)
        return 3

    # 4. result + download
    r = client.get(f"/runs/{run_id}/result")
    r.raise_for_status()
    result = r.json()["result"]
    print(f"effective_volfrac={result['effective_volfrac']:.3f} "
          f"reduction={result['reduction_vs_input_pct']:.1f}% "
          f"watertight={result['watertight']}")

    out_path = Path(__file__).parent / f"_smoke_{run_id}.stl"
    with client.stream("GET", f"/runs/{run_id}/files/optimized_stl") as resp:
        resp.raise_for_status()
        with out_path.open("wb") as fp:
            for chunk in resp.iter_bytes():
                fp.write(chunk)
    print(f"STL baixada: {out_path} ({out_path.stat().st_size} bytes)")

    # 5. valida mesh
    mesh = trimesh.load(out_path, force="mesh")
    assert mesh.is_watertight, "mesh baixada nao e watertight"
    print(f"mesh watertight, bounds={mesh.bounds.tolist()}")

    print("END_OF_TEST: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
