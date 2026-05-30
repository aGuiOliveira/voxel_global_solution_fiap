"""
Wrapper importável do engine PyTopo3D para o backend FastAPI.

Expõe `run_optimization(...)`: roda o pipeline completo (carregar STL como
design space, aplicar apoios/forças/regiões sólidas, otimizar via SIMP,
exportar STL otimizada em mm, validar watertight) e devolve um dict com
paths e métricas.

Reusa as funções de `pytopo3d.runners.experiment` em vez de re-implementar
a malha de chamadas que vive em `main.py`.

API de regiões (dicts JSON-friendly, em mm no espaço da STL):
    {"type": "sphere", "center": [x,y,z], "radius": r}
    {"type": "box",    "min": [x0,y0,z0], "max": [x1,y1,z1]}
    {"type": "face",   "name": "x_min" | "x_max" | "y_min" | ... | "z_max",
                       "thickness": t_mm}     # default: 1 voxel

Para `forces` adiciona `"vector": [Fx, Fy, Fz]`.
"""

from __future__ import annotations

import os
import time
from datetime import datetime
from typing import Callable, List, Optional

import numpy as np
import trimesh
from trimesh.voxel import creation as voxel_creation

from pytopo3d.runners.experiment import execute_optimization, export_result_to_stl, setup_experiment
from pytopo3d.utils.regions import (
    GridInfo,
    force_regions_to_field,
    grid_info_from_box,
    grid_info_from_voxel_grid,
    regions_to_mask,
)
from pytopo3d.visualization.visualizer import create_optimization_animation


def _scale_stl_to_mm(
    src_stl: str,
    dst_stl: str,
    pitch: float,
    origin_corner: tuple = (0.0, 0.0, 0.0),
    keep_largest_component: bool = True,
):
    """Carrega a STL gerada por voxel_to_stl (coords em voxels), escala pra
    mm e alinha ao espaço da peça original.

    Convenção do alinhamento: vértices saem do marching_cubes em coord de
    voxel; voxel_to_stl já compensou o padding (-1 voxel). Após escalar por
    `pitch`, o mesh fica centrado em voxel-coord 0 = canto inferior da
    bbox da voxelização. Para que a STL de saída fique sobreposta à STL
    de entrada, transladamos para `origin_corner + 0.5*pitch` (centro do
    voxel 0, que é o canto da peça original). O mesh ainda pode sobrar
    ±0.5*pitch nas bordas — é overhang inerente ao marching cubes.

    - Sempre roda fix_normals (marching cubes pode emitir normais invertidas).
    - Por padrão descarta componentes desconectados pequenos (topology
      optimization frequentemente gera "ilhas" flutuantes que não imprimem).

    Returns
    -------
    mesh, n_components_total, n_components_discarded
    """
    mesh = trimesh.load(src_stl, force="mesh")
    mesh.apply_scale(pitch)
    # +0.5*pitch para alinhar mesh ao centro do voxel 0 (= canto da peça)
    aligned_origin = tuple(o + 0.5 * pitch for o in origin_corner)
    mesh.apply_translation(aligned_origin)

    n_total, n_discarded = 1, 0
    if keep_largest_component:
        parts = mesh.split(only_watertight=False)
        n_total = len(parts)
        if n_total > 1:
            def _score(p):
                try:
                    v = abs(p.volume)
                    if v > 0:
                        return v
                except Exception:
                    pass
                return p.area
            parts = sorted(parts, key=_score, reverse=True)
            mesh = parts[0]
            n_discarded = n_total - 1

    if not mesh.is_watertight:
        trimesh.repair.fill_holes(mesh)
    trimesh.repair.fix_normals(mesh)
    mesh.export(dst_stl)
    return mesh, n_total, n_discarded


def _voxelize_stl(stl_path: str, pitch: float):
    """Voxeliza a STL e devolve (mask 3D bool, GridInfo). Replica a lógica
    de pytopo3d.utils.import_design_space.voxelize_mesh mas captura o
    VoxelGrid (que tem o transform world↔index)."""
    mesh = trimesh.load(stl_path, force="mesh")
    vg = voxel_creation.voxelize(mesh=mesh, pitch=pitch, method="subdivide")
    vg.fill()
    return vg.matrix.astype(bool), grid_info_from_voxel_grid(vg)


def run_optimization(
    input_stl_path: Optional[str] = None,
    volfrac: float = 0.3,
    pitch: float = 1.0,
    nelx: int = 32,
    nely: int = 16,
    nelz: int = 16,
    penal: float = 3.0,
    rmin: float = 3.0,
    disp_thres: float = 0.5,
    tolx: float = 0.01,
    maxloop: int = 2000,
    stl_level: float = 0.5,
    smooth_iterations: int = 5,
    create_animation: bool = False,
    animation_frequency: int = 10,
    animation_frames: int = 50,
    animation_fps: int = 5,
    base_dir: str = "runs",
    experiment_name: Optional[str] = None,
    use_gpu: bool = False,
    # ---------------- boundary conditions ----------------
    supports: Optional[List[dict]] = None,
    forces: Optional[List[dict]] = None,
    keep_solid: Optional[List[dict]] = None,
    auto_solidify_bc: bool = True,
    iter_callback: Optional[Callable[[int, np.ndarray], None]] = None,
) -> dict:
    """Roda otimização topológica do começo ao fim.

    Parameters de fronteira
    -----------------------
    supports :
        Lista de regiões (dicts) onde a peça é fixa (DOFs do FEM = 0).
        Default (None): face inteira em x=0 (cantilever clássico).
    forces :
        Lista de regiões com `vector: [Fx, Fy, Fz]`. Default: aresta
        x=xmax, y=0 em -Z (default do PyTopo3D).
    keep_solid :
        Lista de regiões onde o material **nunca pode ser removido**
        (xPhys forçado em 1 a cada iteração). Resolve o problema da
        peça "boiando longe do apoio".
    auto_solidify_bc :
        Se True (default), regiões de supports e forces também são
        adicionadas a keep_solid — garante que o material existe onde a
        peça é fixada/carregada, que é quase sempre o que se quer.

    Returns dict com:
        stl_path, stl_voxel_path, animation_path,
        volume_before, volume_after, reduction_pct, run_dir,
        watertight, elapsed_s, solver_elapsed_s,
        nelx, nely, nelz, bounds_mm
    """
    t0 = time.time()

    if experiment_name is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        tag = "stl" if input_stl_path else "box"
        experiment_name = f"{tag}_{ts}_vf{volfrac}_p{penal}_r{rmin}"

    # 1. Voxelização + grid info
    if input_stl_path is not None:
        design_space_mask, grid = _voxelize_stl(input_stl_path, pitch)
        shape = design_space_mask.shape  # (Nx_world, Ny_world, Nz_world) interpretado como (nely, nelx, nelz)
        nely_eff, nelx_eff, nelz_eff = shape
        combined_obstacle_mask = ~design_space_mask
    else:
        grid = grid_info_from_box(nelx, nely, nelz, pitch)
        shape = grid[0]
        nely_eff, nelx_eff, nelz_eff = shape
        design_space_mask = np.ones(shape, dtype=bool)
        combined_obstacle_mask = np.zeros(shape, dtype=bool)

    # 2. Boundary condition masks a partir das regiões
    support_mask = regions_to_mask(supports, grid) if supports else None
    force_field = force_regions_to_field(forces, grid)

    solid_regions: List[dict] = list(keep_solid or [])
    if auto_solidify_bc:
        if supports:
            solid_regions.extend(supports)
        if forces:
            # Para forças, replica só a geometria (sem o vetor)
            for r in forces:
                solid_regions.append({k: v for k, v in r.items() if k != "vector"})
    solid_mask = regions_to_mask(solid_regions, grid) if solid_regions else None

    # 3. Logger + results_mgr
    logger, results_mgr = setup_experiment(
        verbose=False, quiet=False, log_level="INFO",
        experiment_name=experiment_name,
        nelx=nelx_eff, nely=nely_eff, nelz=nelz_eff,
        volfrac=volfrac, penal=penal, rmin=rmin,
    )
    if base_dir != "results":
        from pytopo3d.utils.results_manager import ResultsManager
        results_mgr = ResultsManager(base_dir=base_dir, experiment_name=experiment_name)
        # Reapontar o logger não é necessário; results_mgr novo aponta para outro dir.

    if input_stl_path is not None:
        results_mgr.copy_file(input_stl_path, "design_space.stl")

    # 4. Salvar máscaras pra debug visual
    np.save(os.path.join(results_mgr.experiment_dir, "design_space_mask.npy"), design_space_mask)
    if support_mask is not None:
        np.save(os.path.join(results_mgr.experiment_dir, "support_mask.npy"), support_mask)
    if solid_mask is not None:
        np.save(os.path.join(results_mgr.experiment_dir, "solid_mask.npy"), solid_mask)
    if force_field is not None:
        np.save(os.path.join(results_mgr.experiment_dir, "force_field.npy"), force_field)

    # 5. Otimização
    xPhys, history, run_time = execute_optimization(
        nelx=nelx_eff, nely=nely_eff, nelz=nelz_eff,
        volfrac=volfrac, penal=penal, rmin=rmin,
        disp_thres=disp_thres,
        force_field=force_field,
        support_mask=support_mask,
        solid_mask=solid_mask,
        tolx=tolx, maxloop=maxloop,
        create_animation=create_animation,
        animation_frequency=animation_frequency,
        logger=logger,
        combined_obstacle_mask=combined_obstacle_mask,
        use_gpu=use_gpu,
        iter_callback=iter_callback,
    )

    result_path = results_mgr.save_result(xPhys, "optimized_design.npy")

    export_result_to_stl(
        export_stl=True, stl_level=stl_level,
        smooth_stl=True, smooth_iterations=smooth_iterations,
        logger=logger, results_mgr=results_mgr, result_path=result_path,
    )
    stl_voxel_path = os.path.join(results_mgr.experiment_dir, "optimized_design.stl")
    stl_mm_path = os.path.join(results_mgr.experiment_dir, "optimized_mm.stl")
    mesh_mm, n_components_total, n_components_discarded = _scale_stl_to_mm(
        stl_voxel_path, stl_mm_path, pitch=pitch, origin_corner=grid[1]
    )

    animation_path = None
    if create_animation and history:
        try:
            animation_path = create_optimization_animation(
                nelx=nelx_eff, nely=nely_eff, nelz=nelz_eff,
                experiment_name=experiment_name,
                disp_thres=disp_thres,
                animation_frames=animation_frames,
                animation_fps=animation_fps,
                logger=logger,
                results_mgr=results_mgr,
                history=history,
                combined_obstacle_mask=combined_obstacle_mask,
                loads_array=None, constraints_array=None,
            )
        except Exception as e:
            logger.warning(f"Animation generation failed (continuing): {e}")

    # Volumes em mm^3. Calculamos vários "denominadores" pra deixar claro
    # o que o número significa — o app pode escolher qual mostrar.
    voxel_vol = pitch ** 3
    design_voxels = int(np.count_nonzero(design_space_mask))
    solid_voxels = int(solid_mask.sum()) if solid_mask is not None else 0
    free_voxels = design_voxels - solid_voxels    # onde o otimizador escolhe

    volume_design_space = design_voxels * voxel_vol  # peça original voxelizada
    volume_solid_forced = solid_voxels * voxel_vol   # forçado por keep_solid
    volume_free_budget = free_voxels * voxel_vol * volfrac  # alvo do SIMP

    try:
        # |mesh.volume| (Gauss divergence) funciona mesmo quando watertight=False
        volume_after = abs(float(mesh_mm.volume))
        if not np.isfinite(volume_after) or volume_after == 0.0:
            raise ValueError("volume nulo/inválido")
    except Exception:
        volume_after = float(mesh_mm.bounding_box.volume)

    # Reduções "honestas":
    # - reduction_vs_input: redução vs STL de entrada (o que o usuário vê)
    # - effective_volfrac: fração total que sobrou (inclui solid forçado)
    reduction_vs_input_pct = (
        (1.0 - volume_after / volume_design_space) * 100.0
        if volume_design_space > 0 else 0.0
    )
    effective_volfrac = (
        volume_after / volume_design_space if volume_design_space > 0 else 0.0
    )

    # Bounds da bbox da peça em mm pra UI saber onde clicar
    origin = grid[1]
    extents_mm = (shape[0] * pitch, shape[1] * pitch, shape[2] * pitch)
    bounds_mm = {
        "x_min": origin[0], "x_max": origin[0] + extents_mm[0],
        "y_min": origin[1], "y_max": origin[1] + extents_mm[1],
        "z_min": origin[2], "z_max": origin[2] + extents_mm[2],
    }

    return {
        "stl_path": stl_mm_path,
        "stl_voxel_path": stl_voxel_path,
        "animation_path": animation_path,
        # --- volumes (mm^3) ---
        "volume_design_space": volume_design_space,    # peça original
        "volume_solid_forced": volume_solid_forced,    # forçado por keep_solid
        "volume_free_budget": volume_free_budget,      # alvo SIMP (free * volfrac)
        "volume_after": volume_after,                  # mesh final medido
        # --- métricas derivadas ---
        "reduction_vs_input_pct": reduction_vs_input_pct,
        "effective_volfrac": effective_volfrac,        # volume_after / volume_design_space
        # --- diagnóstico ---
        "watertight": bool(mesh_mm.is_watertight),
        "n_components_total": n_components_total,      # antes de descartar
        "n_components_discarded": n_components_discarded,  # ilhas removidas
        "run_dir": results_mgr.experiment_dir,
        "elapsed_s": time.time() - t0,
        "solver_elapsed_s": run_time,
        "nelx": nelx_eff, "nely": nely_eff, "nelz": nelz_eff,
        "bounds_mm": bounds_mm,
        "supports_voxel_count": int(support_mask.sum()) if support_mask is not None else 0,
        "force_voxel_count": int(np.any(force_field, axis=-1).sum()) if force_field is not None else 0,
        "solid_voxel_count": int(solid_mask.sum()) if solid_mask is not None else 0,
    }


if __name__ == "__main__":
    import json
    r = run_optimization(input_stl_path=None, volfrac=0.3,
                         nelx=32, nely=16, nelz=16, create_animation=False)
    print(json.dumps({k: v for k, v in r.items() if k != "animation_path"},
                     indent=2, default=str))
