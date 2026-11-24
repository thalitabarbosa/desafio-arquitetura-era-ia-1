"""Mede acoplamento (Ca, Ce, I, A, D) dos módulos de app/helpdesk/ e desenha o gráfico A x I.

Uso:
    python3 metrics/coupling.py <pasta app/helpdesk de um checkout> <nome>

Grava metrics/results/<nome>.csv (cabeçalho component,ca,ce,i,a,d) e
metrics/results/<nome>.svg (gráfico A x I com a Main Sequence). Só usa a biblioteca padrão.

Régua (requisito 3 do desafio, fixa para todas as medições):
- componente: cada módulo .py de app/helpdesk/, inclusive em subpastas, identificado pelo caminho
  com pontos (ex.: adapters.gateway); os __init__.py não são componentes;
- dependência: um import, relativo ou absoluto, que resolve para outro componente
  (ex.: from ..ports import Gateway, from helpdesk import config); bibliotecas externas e da
  biblioteca padrão não contam;
- Ca: quantos componentes importam este; Ce: quantos componentes este importa;
- I = Ce / (Ce + Ca), ou 0 quando os dois são zero;
- A = classes abstratas (que herdam de typing.Protocol ou abc.ABC) / total de classes do módulo,
  ou 0 quando o módulo não tem classes;
- D = |A + I - 1|; valores arredondados para 2 casas.
"""
from __future__ import annotations

import ast
import csv
import pathlib
import sys
from html import escape

ROOT_PACKAGE = "helpdesk"
ABSTRACT_BASES = {"Protocol", "typing.Protocol", "ABC", "abc.ABC"}


def discover(source: pathlib.Path) -> dict[str, pathlib.Path]:
    """Mapeia o nome com pontos de cada componente para o arquivo."""
    components = {}
    for path in sorted(source.rglob("*.py")):
        if path.name == "__init__.py" or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(source).with_suffix("")
        components[".".join(relative.parts)] = path
    return components


def package_of(name: str) -> list[str]:
    """Pacote (relativo a helpdesk) que contém o componente: adapters.gateway -> [adapters]."""
    return name.split(".")[:-1]


def resolve(candidate: str, components: dict) -> str | None:
    return candidate if candidate in components else None


def imports_of(name: str, tree: ast.AST, components: dict) -> set[str]:
    """Componentes importados pelo módulo `name` (sem ele mesmo)."""
    found: set[str] = set()
    package = package_of(name)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] != ROOT_PACKAGE:
                    continue
                # import helpdesk.x.y -> tenta o caminho mais longo que for componente
                for size in range(len(parts), 1, -1):
                    target = resolve(".".join(parts[1:size]), components)
                    if target:
                        found.add(target)
                        break
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                parts = (node.module or "").split(".")
                if parts[0] != ROOT_PACKAGE:
                    continue
                base = parts[1:]
            else:
                if node.level - 1 > len(package):
                    continue  # sobe além de helpdesk: não resolve para componente
                base = package[: len(package) - (node.level - 1)]
                if node.module:
                    base = base + node.module.split(".")
            module_target = resolve(".".join(base), components) if base else None
            if module_target:
                # from .schemas import X  /  from helpdesk.adapters.gateway import Y
                found.add(module_target)
                continue
            for alias in node.names:
                # from . import config, llm  /  from helpdesk.adapters import gateway
                target = resolve(".".join(base + [alias.name]), components)
                if target:
                    found.add(target)
    found.discard(name)
    return found


def base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Subscript):  # Protocol[T]
        node = node.value
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{base_name(node.value)}.{node.attr}"
    return ""


def abstractness(tree: ast.AST) -> float:
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    if not classes:
        return 0.0
    abstract = [c for c in classes if any(base_name(b) in ABSTRACT_BASES for b in c.bases)]
    return len(abstract) / len(classes)


def measure(source: pathlib.Path) -> list[dict]:
    components = discover(source)
    trees = {name: ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
             for name, path in components.items()}
    efferent = {name: imports_of(name, tree, components) for name, tree in trees.items()}
    afferent = {name: {other for other, deps in efferent.items() if name in deps} for name in components}
    rows = []
    for name in components:
        ca, ce = len(afferent[name]), len(efferent[name])
        instability = ce / (ce + ca) if (ce + ca) else 0.0
        abstract = abstractness(trees[name])
        distance = abs(abstract + instability - 1)
        rows.append({"component": name, "ca": ca, "ce": ce, "i": round(instability, 2),
                     "a": round(abstract, 2), "d": round(distance, 2)})
    return rows


def in_pain_zone(row: dict) -> bool:
    return row["a"] < 0.5 and row["i"] < 0.5 and row["d"] >= 0.5


def write_csv(rows: list[dict], path: pathlib.Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(["component", "ca", "ce", "i", "a", "d"])
        for r in rows:
            writer.writerow([r["component"], r["ca"], r["ce"], f"{r['i']:.2f}", f"{r['a']:.2f}", f"{r['d']:.2f}"])


def write_svg(rows: list[dict], title: str, path: pathlib.Path) -> None:
    size, margin = 520, 70
    width, height = size + 2 * margin + 220, size + 2 * margin

    def x(i: float) -> float:
        return margin + i * size

    def y(a: float) -> float:
        return margin + (1 - a) * size

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="Helvetica, Arial, sans-serif" font-size="12">',
        f'<rect width="{width}" height="{height}" fill="white"/>',
        f'<text x="{margin}" y="30" font-size="16" font-weight="bold">{escape(title)}: A x I</text>',
        # zona de dor (A<0,5, I<0,5, abaixo da linha D=0,5) e zona de inutilidade
        f'<polygon points="{x(0)},{y(0)} {x(0)},{y(0.5)} {x(0.5)},{y(0)}" fill="#f8d7d3"/>',
        f'<polygon points="{x(1)},{y(1)} {x(1)},{y(0.5)} {x(0.5)},{y(1)}" fill="#e3e3f3"/>',
        f'<text x="{x(0.03)}" y="{y(0.42)}" fill="#a33">zona de dor</text>',
        f'<text x="{x(0.78)}" y="{y(0.95)}" fill="#447">zona de inutilidade</text>',
        f'<rect x="{x(0)}" y="{y(1)}" width="{size}" height="{size}" fill="none" stroke="#333"/>',
        f'<line x1="{x(0)}" y1="{y(1)}" x2="{x(1)}" y2="{y(0)}" stroke="#2a7" stroke-width="2"/>',
        f'<text x="{x(0.55)}" y="{y(0.47)}" fill="#2a7" transform="rotate(45 {x(0.55)} {y(0.47)})">'
        'Main Sequence (A + I = 1)</text>',
    ]
    for t in (0, 0.25, 0.5, 0.75, 1):
        parts.append(f'<text x="{x(t)}" y="{y(0) + 18}" text-anchor="middle">{t:g}</text>')
        parts.append(f'<text x="{x(0) - 8}" y="{y(t) + 4}" text-anchor="end">{t:g}</text>')
    parts.append(f'<text x="{x(0.5)}" y="{y(0) + 40}" text-anchor="middle">I (instabilidade)</text>')
    parts.append(f'<text x="{x(0) - 45}" y="{y(0.5)}" text-anchor="middle" '
                 f'transform="rotate(-90 {x(0) - 45} {y(0.5)})">A (abstração)</text>')

    groups: dict[tuple, list[str]] = {}
    for r in rows:
        groups.setdefault((r["i"], r["a"]), []).append(r["component"])
    placed: list[tuple[float, float]] = []  # (x, y) dos rótulos já desenhados
    for (i, a), names in sorted(groups.items(), key=lambda g: (g[0][1], g[0][0])):
        color = "#c0392b" if in_pain_zone({"i": i, "a": a, "d": abs(a + i - 1)}) else "#1f5fa8"
        parts.append(f'<circle cx="{x(i)}" cy="{y(a)}" r="5" fill="{color}"/>')
        # empilha rótulos de pontos próximos para não se sobreporem, com uma linha guia
        label_y = y(a) - 14
        while any(abs(label_y - py) < 15 and abs(x(i) - px) < 230 for px, py in placed):
            label_y -= 16
        placed.append((x(i), label_y))
        anchor = "end" if i > 0.9 else "start"
        label_x = x(i) - 4 if anchor == "end" else x(i) + 4
        parts.append(f'<line x1="{x(i)}" y1="{y(a)}" x2="{label_x}" y2="{label_y + 3}" '
                     f'stroke="{color}" stroke-width="0.6"/>')
        parts.append(f'<text x="{label_x}" y="{label_y}" text-anchor="{anchor}" fill="{color}">'
                     f'{escape(", ".join(names))}</text>')

    legend_x, legend_y = x(1) + 20, y(1) + 10
    parts.append(f'<text x="{legend_x}" y="{legend_y}" font-weight="bold">component: ca ce i a d</text>')
    for n, r in enumerate(rows):
        color = "#c0392b" if in_pain_zone(r) else "#333"
        parts.append(f'<text x="{legend_x}" y="{legend_y + 18 * (n + 1)}" fill="{color}">'
                     f'{escape(r["component"])}: {r["ca"]} {r["ce"]} {r["i"]:.2f} {r["a"]:.2f} {r["d"]:.2f}</text>')
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    source = pathlib.Path(argv[1]).resolve()
    if not source.is_dir():
        print(f"pasta não encontrada: {source}")
        return 2
    name = argv[2]
    results = pathlib.Path(__file__).resolve().parent / "results"
    results.mkdir(exist_ok=True)
    rows = measure(source)
    write_csv(rows, results / f"{name}.csv")
    write_svg(rows, name, results / f"{name}.svg")
    print("component,ca,ce,i,a,d")
    for r in rows:
        flag = "  <- zona de dor" if in_pain_zone(r) else ""
        print(f"{r['component']},{r['ca']},{r['ce']},{r['i']:.2f},{r['a']:.2f},{r['d']:.2f}{flag}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
