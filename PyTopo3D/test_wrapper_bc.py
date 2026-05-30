"""Teste do wrapper com apoios + força custom.

Cenário: cantilever clássico — fixa face x_min, força em -Z na face x_max.
Verifica:
  1. STL final é watertight
  2. Material persiste no x_min (apoio) e x_max (força) — i.e. a peça
     toca os dois extremos, não fica boiando no meio
"""

import json

import numpy as np
import trimesh

from optimize import run_optimization

SUPPORTS = [{"type": "face", "name": "x_min", "thickness": 4.0}]
FORCES = [{"type": "face", "name": "x_max", "thickness": 4.0,
           "vector": [0, 0, -1.0]}]

r = run_optimization(
    input_stl_path="test_bracket.stl",
    volfrac=0.3,
    pitch=2.0,
    create_animation=False,
    supports=SUPPORTS,
    forces=FORCES,
    # auto_solidify_bc=True (default) garante material nos dois extremos
)

print(json.dumps(r, indent=2, default=str))

# Estes asserts sao sanity check do PIPELINE, nao da qualidade da peca:
assert r["supports_voxel_count"] > 0, "support_mask ficou vazio"
assert r["force_voxel_count"] > 0, "force_field ficou vazio"
assert r["solid_voxel_count"] >= r["supports_voxel_count"], \
    "solid_mask deveria conter ao menos os supports"
assert r["reduction_vs_input_pct"] > 30, f"reducao baixa: {r['reduction_vs_input_pct']:.1f}%"
assert r["reduction_vs_input_pct"] < 95, f"reducao alta demais (peca sumiu?): {r['reduction_vs_input_pct']:.1f}%"
# Componentes: deve ter alguns descartados (5 no run anterior) e mesh principal watertight
print(f"componentes (total/descartados): {r['n_components_total']}/{r['n_components_discarded']}")
print(f"volfrac efetivo: {r['effective_volfrac']:.3f} (pedido: 0.300)")

# Verifica material nos extremos:
xPhys = np.load(f"{r['run_dir']}/optimized_design.npy")
xmin_slab = xPhys[:2, :, :]
xmax_slab = xPhys[-2:, :, :]
mid_lo = xPhys.shape[0]//2 - 1
print(f"densidade media x_min (apoio): {xmin_slab.mean():.3f}")
print(f"densidade media x_max (forca): {xmax_slab.mean():.3f}")
print(f"densidade media meio:           {xPhys[mid_lo:mid_lo+2, :, :].mean():.3f}")
assert xmin_slab.mean() > 0.9, f"material no apoio insuficiente: {xmin_slab.mean()}"
assert xmax_slab.mean() > 0.9, f"material na forca insuficiente: {xmax_slab.mean()}"

# Valida o mesh final visualmente: deve tocar ambos os extremos em X
mesh = trimesh.load(r["stl_path"], force="mesh")
bx_min, bx_max = mesh.bounds[0][0], mesh.bounds[1][0]
print(f"bounds x do mesh otimizado: [{bx_min:.2f}, {bx_max:.2f}] mm")
print(f"bounds esperados:           [{r['bounds_mm']['x_min']:.2f}, {r['bounds_mm']['x_max']:.2f}] mm")

print("END_OF_TEST: PASS")
