"""
Region helpers: converte dicts JSON-friendly em máscaras 3D na shape do
PyTopo3D `(nely, nelx, nelz)`.

Notas de convenção:

- O usuário pensa em **mm no espaço da peça** (world coords da STL ou da
  bounding box default).
- O trimesh `voxel_grid.matrix` tem shape `(Nx, Ny, Nz)` em ordem de mundo.
- PyTopo3D reinterpreta esse array como `(nely, nelx, nelz)` — portanto
  o axis-0 da máscara corresponde a **X de mundo**, axis-1 a **Y de mundo**,
  axis-2 a **Z de mundo**. Isto está consistente com `design_space_mask`.

Tipos de região suportados (dict):

    {"type": "sphere", "center": [x, y, z], "radius": r}
    {"type": "box",    "min": [x0, y0, z0], "max": [x1, y1, z1]}
    {"type": "face",   "name": "x_min" | "x_max" | "y_min" | ... | "z_max",
                       "thickness": t}     # t em mm; default = 1 voxel

Para `forces`, cada dict tem também `"vector": [Fx, Fy, Fz]`.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np

# (nx_voxels, ny_voxels, nz_voxels), origin (x0, y0, z0) em mm, pitch em mm
GridInfo = Tuple[Tuple[int, int, int], Tuple[float, float, float], float]


def grid_info_from_voxel_grid(voxel_grid) -> GridInfo:
    """Extrai (shape, origin, pitch) de um trimesh VoxelGrid."""
    shape = tuple(int(s) for s in voxel_grid.matrix.shape)
    # transform[:3, 3] é o centro do voxel (0,0,0); subtrai meio pitch p/ canto
    pitch = float(voxel_grid.pitch[0]) if hasattr(voxel_grid.pitch, "__len__") else float(voxel_grid.pitch)
    origin_center = voxel_grid.transform[:3, 3]
    origin_corner = tuple(float(c - 0.5 * pitch) for c in origin_center)
    return shape, origin_corner, pitch


def grid_info_from_box(nelx: int, nely: int, nelz: int, pitch: float) -> GridInfo:
    """Para o caso sem STL: caixa começando em (0,0,0)."""
    # World order: shape (Nx, Ny, Nz) = (nely, nelx, nelz) — ver nota no header.
    # nely é o nº de elementos ao longo do eixo X mundial, nelx ao longo de Y.
    return (nely, nelx, nelz), (0.0, 0.0, 0.0), pitch


def _world_to_index(
    pt_mm: Tuple[float, float, float], origin: Tuple[float, float, float], pitch: float
) -> Tuple[float, float, float]:
    return tuple((p - o) / pitch for p, o in zip(pt_mm, origin))


def _voxel_centers(shape: Tuple[int, int, int], origin: Tuple[float, float, float], pitch: float):
    """Coordenadas (em mm) do centro de cada voxel em arrays meshgrid."""
    Nx, Ny, Nz = shape
    xs = origin[0] + (np.arange(Nx) + 0.5) * pitch
    ys = origin[1] + (np.arange(Ny) + 0.5) * pitch
    zs = origin[2] + (np.arange(Nz) + 0.5) * pitch
    return np.meshgrid(xs, ys, zs, indexing="ij")


_FACE_AXIS = {"x_min": (0, 0), "x_max": (0, 1),
              "y_min": (1, 0), "y_max": (1, 1),
              "z_min": (2, 0), "z_max": (2, 1)}


def region_to_mask(region: dict, grid: GridInfo) -> np.ndarray:
    """Constrói máscara bool 3D na shape do PyTopo3D para uma região."""
    shape, origin, pitch = grid
    rtype = region.get("type")
    if rtype == "sphere":
        center = tuple(float(c) for c in region["center"])
        r = float(region["radius"])
        Xc, Yc, Zc = _voxel_centers(shape, origin, pitch)
        d2 = (Xc - center[0]) ** 2 + (Yc - center[1]) ** 2 + (Zc - center[2]) ** 2
        return d2 <= r * r
    if rtype == "box":
        lo = [float(v) for v in region["min"]]
        hi = [float(v) for v in region["max"]]
        Xc, Yc, Zc = _voxel_centers(shape, origin, pitch)
        return (
            (Xc >= lo[0]) & (Xc <= hi[0])
            & (Yc >= lo[1]) & (Yc <= hi[1])
            & (Zc >= lo[2]) & (Zc <= hi[2])
        )
    if rtype == "face":
        axis, side = _FACE_AXIS[region["name"]]
        thickness_mm = float(region.get("thickness", pitch))
        thickness_vox = max(1, int(round(thickness_mm / pitch)))
        mask = np.zeros(shape, dtype=bool)
        slicer = [slice(None)] * 3
        slicer[axis] = slice(0, thickness_vox) if side == 0 else slice(shape[axis] - thickness_vox, shape[axis])
        mask[tuple(slicer)] = True
        return mask
    raise ValueError(f"region.type desconhecido: {rtype!r}")


def regions_to_mask(regions: Optional[List[dict]], grid: GridInfo) -> np.ndarray:
    """OR de várias regiões. Retorna máscara zerada se regions for None/vazio."""
    shape, _, _ = grid
    if not regions:
        return np.zeros(shape, dtype=bool)
    out = np.zeros(shape, dtype=bool)
    for r in regions:
        out |= region_to_mask(r, grid)
    return out


def force_regions_to_field(
    force_regions: Optional[List[dict]], grid: GridInfo
) -> Optional[np.ndarray]:
    """Constrói o `force_field` (nely, nelx, nelz, 3) somando vetores de cada
    região sobre seus voxels. Retorna None se nada foi pedido (engine usa
    default cantilever)."""
    shape, _, _ = grid
    if not force_regions:
        return None
    field = np.zeros(shape + (3,), dtype=float)
    for r in force_regions:
        mask = region_to_mask(r, grid)
        vec = np.asarray(r["vector"], dtype=float)
        if vec.shape != (3,):
            raise ValueError(f"force.vector deve ter 3 componentes, veio {vec.shape}")
        field[mask] += vec
    return field
