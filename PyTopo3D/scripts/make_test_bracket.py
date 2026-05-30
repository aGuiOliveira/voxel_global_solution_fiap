"""
Gera uma STL simples para testar o caminho --design-space-stl do PyTopo3D.

Tenta uma caixa com furo (precisa de manifold3d ou blender como backend de
booleanas). Se a operação booleana falhar, cai para uma caixa simples — o
pipeline de otimização funciona em qualquer dos dois.

Uso (com env pytopo3d ativo, a partir de PyTopo3D/):
    python scripts/make_test_bracket.py
Saída: ./test_bracket.stl no diretório atual.
"""

import trimesh


def make_bracket() -> trimesh.Trimesh:
    box = trimesh.creation.box(extents=[60, 30, 20])
    hole = trimesh.creation.cylinder(radius=5, height=25)
    try:
        bracket = box.difference(hole)
        if bracket.is_volume:
            return bracket
        print("[warn] difference produziu mesh sem volume; usando caixa pura")
    except Exception as e:
        print(f"[warn] boolean difference falhou ({e}); usando caixa pura")
    return box


if __name__ == "__main__":
    mesh = make_bracket()
    out = "test_bracket.stl"
    mesh.export(out)
    print(f"saved: {out}")
    print(f"watertight: {mesh.is_watertight}")
    print(f"volume (mm^3): {mesh.volume:.2f}")
    print(f"bbox extents (mm): {mesh.bounding_box.extents}")
