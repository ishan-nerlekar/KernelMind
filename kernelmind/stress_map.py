"""Map each inspect_evals eval to the scorers it uses, by reading its source (no imports).

Two outputs:
- exposure: evals that call an inspect_ai built-in scorer a probe covers, so they inherit
  that probe's findings (e.g. every `match(numeric=True)` caller inherits #6536/#6537);
- audit queue: evals with their own @scorer functions that parse free text (regex or JSON
  on a model or judge reply), ranked by how much parsing they do. These need a probe.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

BUILTINS = {"match", "includes", "exact", "choice", "pattern", "answer", "f1", "model_graded_qa",
            "model_graded_fact", "math"}
PARSERS = {("re", "search"), ("re", "findall"), ("re", "match"), ("re", "fullmatch"), ("re", "finditer"), ("json", "loads")}


@dataclass
class EvalScorers:
    name: str
    builtins: list[str] = field(default_factory=list)  # e.g. "match(numeric=True)"
    custom: list[str] = field(default_factory=list)  # @scorer function names
    parse_calls: int = 0  # re.*/json.loads calls in modules that define a @scorer


def _call_name(node: ast.Call) -> str | None:
    f = node.func
    return f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)


def _is_parse(node: ast.AST) -> bool:
    """re.search(...), json.loads(...) and friends; a compiled pattern's .search() also counts."""
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
        return False
    owner = node.func.value
    if isinstance(owner, ast.Name) and (owner.id, node.func.attr) in PARSERS:
        return True
    return node.func.attr in ("search", "findall", "fullmatch", "finditer") and isinstance(owner, ast.Name) and owner.id.isupper()


def _render(node: ast.Call, name: str) -> str:
    kws = []
    for k in node.keywords:
        if k.arg and isinstance(k.value, ast.Constant) and k.arg in ("numeric", "location", "grade_pattern", "partial_credit"):
            kws.append(f"{k.arg}={k.value.value!r}")
        elif k.arg in ("grade_pattern", "pattern", "template", "instructions"):
            kws.append(f"{k.arg}=<custom>")
    if name == "pattern" and node.args:
        kws.insert(0, "<regex>")
    return f"{name}({', '.join(kws)})"


def _scorer_imports(tree: ast.Module) -> set[str]:
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("inspect_ai.scorer"):
            names |= {a.asname or a.name for a in n.names if a.name in BUILTINS}
    return names


def _defines_scorer(tree: ast.Module) -> list[str]:
    out = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in n.decorator_list:
                d = d.func if isinstance(d, ast.Call) else d
                if (isinstance(d, ast.Name) and d.id == "scorer") or (isinstance(d, ast.Attribute) and d.attr == "scorer"):
                    out.append(n.name)
    return out


def scan(src: Path) -> list[EvalScorers]:
    """`src` is inspect_evals' src/inspect_evals directory."""
    results = []
    for d in sorted(p for p in src.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))):
        if d.name in ("utils", "metadata"):
            continue
        e = EvalScorers(d.name)
        for f in sorted(d.rglob("*.py")):
            if "test" in f.parts:
                continue
            try:
                tree = ast.parse(f.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            imported = _scorer_imports(tree)
            for n in ast.walk(tree):
                if isinstance(n, ast.Call) and (name := _call_name(n)) in imported:
                    e.builtins.append(_render(n, name))
            scorers = _defines_scorer(tree)
            if scorers:
                e.custom += scorers
                e.parse_calls += sum(1 for n in ast.walk(tree) if _is_parse(n))
        e.builtins = sorted(set(e.builtins))
        e.custom = sorted(set(e.custom))
        if e.builtins or e.custom:
            results.append(e)
    return results


# which probe findings a built-in call inherits
EXPOSURE = {
    "match(numeric=True)": "inspect.match_numeric, inspect.match_numeric_large (#6536, #6537)",
    "choice()": "inspect.choice when paired with multiple_choice() (#6534, #6535)",
    "pattern(<regex>)": "first match wins and string comparison (macbench, #2918)",
}


def exposure(results: list[EvalScorers]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {k: [] for k in EXPOSURE}
    for e in results:
        for b in e.builtins:
            key = b if b in EXPOSURE else ("pattern(<regex>)" if b.startswith("pattern(") else None)
            if key and e.name not in out[key]:
                out[key].append(e.name)
    return out


def markdown(results: list[EvalScorers], covered: set[str]) -> str:
    exp = exposure(results)
    lines = [f"{len(results)} evals with scorers.\n", "## Exposure to built-in findings\n",
             "| Built-in call | Inherits | Evals |", "|---|---|---|"]
    for k, evals in exp.items():
        lines.append(f"| `{k}` | {EXPOSURE[k]} | {len(evals)}: {', '.join(evals)} |")
    queue = sorted((e for e in results if e.custom and e.name not in covered), key=lambda e: -e.parse_calls)
    lines += ["", "## Audit queue: custom scorers that parse free text, no probe yet\n",
              "| Eval | Custom scorers | Parse calls | Built-ins |", "|---|---|---|---|"]
    for e in queue:
        if e.parse_calls:
            names = ', '.join(e.custom[:4]) + (f' (+{len(e.custom) - 4} more)' if len(e.custom) > 4 else '')
            lines.append(f"| {e.name} | {names} | {e.parse_calls} | {', '.join(e.builtins) or '-'} |")
    return "\n".join(lines) + "\n"
