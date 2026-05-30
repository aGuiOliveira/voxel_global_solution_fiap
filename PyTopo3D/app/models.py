"""Pydantic v2 models para a API.

Espelha o formato de regioes definido em pytopo3d.utils.regions: cada regiao
e um dict com `type` discriminado e os campos correspondentes (em mm).
Forces sao regioes com campo extra `vector: [Fx, Fy, Fz]`.
"""

from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field

Vec3 = tuple[float, float, float]
FaceName = Literal["x_min", "x_max", "y_min", "y_max", "z_min", "z_max"]


class SphereRegion(BaseModel):
    type: Literal["sphere"]
    center: Vec3
    radius: float = Field(gt=0)


class BoxRegion(BaseModel):
    type: Literal["box"]
    min: Vec3
    max: Vec3


class FaceRegion(BaseModel):
    type: Literal["face"]
    name: FaceName
    thickness: Optional[float] = Field(default=None, gt=0)


Region = Annotated[
    Union[SphereRegion, BoxRegion, FaceRegion],
    Field(discriminator="type"),
]


class ForceSphereRegion(SphereRegion):
    vector: Vec3


class ForceBoxRegion(BoxRegion):
    vector: Vec3


class ForceFaceRegion(FaceRegion):
    vector: Vec3


ForceRegion = Annotated[
    Union[ForceSphereRegion, ForceBoxRegion, ForceFaceRegion],
    Field(discriminator="type"),
]


class OptimizeRequest(BaseModel):
    """Parametros do run_optimization. STL vai separado como multipart file."""

    volfrac: float = Field(default=0.3, gt=0, lt=1)
    pitch: float = Field(default=1.0, gt=0)
    # Usado apenas se nao houver STL (modo caixa)
    nelx: int = Field(default=32, gt=0)
    nely: int = Field(default=16, gt=0)
    nelz: int = Field(default=16, gt=0)
    penal: float = Field(default=3.0, gt=0)
    rmin: float = Field(default=3.0, gt=0)
    disp_thres: float = Field(default=0.5, gt=0, lt=1)
    tolx: float = Field(default=0.01, gt=0)
    maxloop: int = Field(default=2000, gt=0)
    stl_level: float = Field(default=0.5, gt=0, lt=1)
    smooth_iterations: int = Field(default=5, ge=0)
    create_animation: bool = False
    animation_frequency: int = 10
    animation_frames: int = 50
    animation_fps: int = 5
    experiment_name: Optional[str] = None
    supports: Optional[list[Region]] = None
    forces: Optional[list[ForceRegion]] = None
    keep_solid: Optional[list[Region]] = None
    auto_solidify_bc: bool = True


JobStatus = Literal["queued", "running", "done", "error", "cancelled"]


class RunProgress(BaseModel):
    iter: int
    maxloop: Optional[int] = None
    compliance: float
    compliance_delta: float
    volume: float
    change: float
    iter_time_s: float


class RunStatus(BaseModel):
    run_id: str
    status: JobStatus
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    elapsed_s: Optional[float] = None
    error: Optional[str] = None
    progress: Optional[RunProgress] = None
    log_tail: list[str] = []
    # Ultima iteracao que tem mesh GLB de preview pronto em runs/{id}/iters/.
    # Frontend usa pra recarregar o mesh ao vivo enquanto a otimizacao roda.
    latest_iter_mesh: Optional[int] = None


class RunResult(BaseModel):
    run_id: str
    status: JobStatus
    result: Optional[dict] = None
    error: Optional[str] = None
