// Mirror dos pydantic models do backend (app/models.py).

export type Vec3 = [number, number, number]
export type FaceName = 'x_min' | 'x_max' | 'y_min' | 'y_max' | 'z_min' | 'z_max'

export type SphereRegion = { type: 'sphere'; center: Vec3; radius: number }
export type BoxRegion = { type: 'box'; min: Vec3; max: Vec3 }
export type FaceRegion = { type: 'face'; name: FaceName; thickness?: number }
export type Region = SphereRegion | BoxRegion | FaceRegion

export type ForceRegion = Region & { vector: Vec3 }

export interface OptimizeRequest {
  volfrac?: number
  pitch?: number
  nelx?: number
  nely?: number
  nelz?: number
  penal?: number
  rmin?: number
  disp_thres?: number
  tolx?: number
  maxloop?: number
  stl_level?: number
  smooth_iterations?: number
  create_animation?: boolean
  experiment_name?: string | null
  supports?: Region[]
  forces?: ForceRegion[]
  keep_solid?: Region[]
  auto_solidify_bc?: boolean
}

export type JobStatus = 'queued' | 'running' | 'done' | 'error' | 'cancelled'

export interface RunProgress {
  iter: number
  maxloop: number | null
  compliance: number
  compliance_delta: number
  volume: number
  change: number
  iter_time_s: number
}

export interface RunStatus {
  run_id: string
  status: JobStatus
  created_at: string
  started_at?: string | null
  finished_at?: string | null
  elapsed_s?: number | null
  error?: string | null
  progress?: RunProgress | null
  log_tail?: string[]
  latest_iter_mesh?: number | null
}

export interface RunResult {
  run_id: string
  status: JobStatus
  result?: OptimizationResult | null
  error?: string | null
}

export interface OptimizationResult {
  stl_path: string
  stl_voxel_path: string
  animation_path: string | null
  volume_design_space: number
  volume_solid_forced: number
  volume_free_budget: number
  volume_after: number
  reduction_vs_input_pct: number
  effective_volfrac: number
  watertight: boolean
  n_components_total: number
  n_components_discarded: number
  run_dir: string
  elapsed_s: number
  solver_elapsed_s: number
  nelx: number
  nely: number
  nelz: number
  bounds_mm: {
    x_min: number; x_max: number
    y_min: number; y_max: number
    z_min: number; z_max: number
  }
  supports_voxel_count: number
  force_voxel_count: number
  solid_voxel_count: number
}

export type FileKind =
  | 'input_stl'
  | 'optimized_stl'
  | 'optimized_voxel_stl'
  | 'animation'
  | 'density_npy'
