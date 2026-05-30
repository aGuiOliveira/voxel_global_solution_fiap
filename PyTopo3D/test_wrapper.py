"""Smoke test do wrapper run_optimization."""
import json

from optimize import run_optimization

r = run_optimization(
    input_stl_path="test_bracket.stl",
    volfrac=0.3,
    pitch=2.0,
    create_animation=False,
)
print(json.dumps(r, indent=2, default=str))
assert r["watertight"], "STL final NAO eh watertight"
assert r["reduction_vs_input_pct"] > 50, "reducao baixa: %.2f" % r["reduction_vs_input_pct"]
print("END_OF_TEST: PASS")
