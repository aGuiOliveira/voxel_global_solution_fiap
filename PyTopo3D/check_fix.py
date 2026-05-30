"""Re-aplica _scale_stl_to_mm no output anterior pra validar origin offset."""
from optimize import _scale_stl_to_mm

src = "runs/stl_20260526_230124_vf0.3_p3.0_r3.0/optimized_design.stl"
dst = "runs/stl_20260526_230124_vf0.3_p3.0_r3.0/optimized_mm_aligned.stl"
# origin do bracket = (-31, -17, -11) (do bounds_mm do run anterior)
m = _scale_stl_to_mm(src, dst, pitch=2.0, origin=(-31.0, -17.0, -11.0))
print("after origin fix:")
print("  watertight:", m.is_watertight)
print("  bounds:", m.bounds.tolist())
print("  esperado: x in [-31, 31], y in [-17, 17], z in [-11, 11]")
