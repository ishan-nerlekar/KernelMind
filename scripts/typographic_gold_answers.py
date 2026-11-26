# /// script
# dependencies = ["datasets>=2.19"]
# ///
"""How many QA gold answers contain typographic punctuation that an ASCII-only normaliser keeps?

SQuAD-style answer normalisation removes `string.punctuation`, which is ASCII only. A gold answer such as
"1914–1918" (en dash) or "Schindler’s List" (curly apostrophe) keeps that character after normalisation, so a
model that writes the ASCII form ("1914-1918") gets exact match 0. This counts the dev-set questions where that can
happen.

  uv run scripts/typographic_gold_answers.py            # writes results/typographic_gold_answers.json

"affected_all": every gold answer of the question has such a character, so an ASCII-writing model cannot match any
of them. "affected_any": at least one gold answer has one.
"""

import json
import string
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ASCII = set(string.punctuation)


def typographic(s: str) -> list[str]:
    """Punctuation characters an ASCII-only normaliser leaves in place."""
    return [c for c in s if c not in ASCII and unicodedata.category(c).startswith("P")]


def summarise(name: str, golds_per_question) -> dict:
    n = all_ = any_ = 0
    chars: Counter = Counter()
    examples = []
    for golds in golds_per_question:
        golds = [g for g in golds if g and g.strip()]
        if not golds:
            continue  # unanswerable (SQuAD v2) or empty
        n += 1
        hits = [typographic(g) for g in golds]
        if any(hits):
            any_ += 1
            for h in hits:
                chars.update(h)
        if all(hits):
            all_ += 1
            if len(examples) < 8:
                examples.append(golds[0])
    return {
        "dataset": name,
        "questions": n,
        "affected_all": all_,
        "affected_all_pct": round(100 * all_ / n, 2) if n else 0.0,
        "affected_any": any_,
        "affected_any_pct": round(100 * any_ / n, 2) if n else 0.0,
        "characters": {f"U+{ord(c):04X} {unicodedata.name(c, '?')}": k for c, k in chars.most_common(10)},
        "examples": examples,
    }


DATASETS = [
    # (label, path, config, split, gold answers of one row)
    ("SQuAD v2 dev (inspect_evals squad)", "rajpurkar/squad_v2", None, "validation", lambda r: r["answers"]["text"]),
    ("SQuAD v1.1 dev", "rajpurkar/squad", None, "validation", lambda r: r["answers"]["text"]),
    ("Natural Questions open dev (Search-R1 nq)", "google-research-datasets/nq_open", None, "validation",
     lambda r: r["answer"]),
    ("TriviaQA rc.nocontext dev", "mandarjoshi/trivia_qa", "rc.nocontext", "validation",
     lambda r: [r["answer"]["value"], *r["answer"]["aliases"]]),
    ("HotpotQA distractor dev", "hotpotqa/hotpot_qa", "distractor", "validation", lambda r: [r["answer"]]),
    ("DROP dev (inspect_evals drop)", "ucinlp/drop", None, "validation", lambda r: r["answers_spans"]["spans"]),
]


def main() -> int:
    from datasets import load_dataset

    out = []
    for label, path, config, split, golds in DATASETS:
        try:
            ds = load_dataset(path, config, split=split)
        except Exception as e:  # keep going: one unavailable dataset should not lose the others
            print(f"skip {label}: {type(e).__name__}: {e}", file=sys.stderr)
            continue
        r = summarise(label, (golds(row) for row in ds))
        out.append(r)
        print(f"{label}: {r['affected_all']}/{r['questions']} ({r['affected_all_pct']}%) all gold answers affected; "
              f"{r['affected_any']} ({r['affected_any_pct']}%) any. Top: {list(r['characters'])[:3]}")
    dest = Path("results/typographic_gold_answers.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        r = summarise("t", [["1914–1918"], ["Paris"], ["O’Neill", "O'Neill"], [""], ["“Hamlet”"]])
        assert (r["questions"], r["affected_all"], r["affected_any"]) == (4, 2, 3), r
        assert not typographic("U.S. $5 (a-b)") and typographic("1914–1918") == ["–"]
        print("ok")
        sys.exit(0)
    sys.exit(main())
