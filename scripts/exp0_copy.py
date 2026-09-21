"""Experiment 0 - Copy/identity baseline: source -> source.

The baseline never changes the surface form, so identity preservation is 100%
by construction. Its purpose is to quantify what would be *left untranslated*
if copying were used, i.e. how much of the sample consists of Latin-script
translatable strings.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import jload, jdumpl, norm_key

def main():
    items = [json.loads(l) for l in (Path(__file__).resolve().parents[1] / "samples" / "sample200.jsonl").open()]
    results = []
    for it in items:
        results.append({
            "example_id": it["example_id"],
            "candidate_type": it["candidate_type"],
            "source": it["cell_value"],
            "translation": it["cell_value"],
            "method": "copy",
            "confidence": 1.0,
            "needs_review": False,
        })
    n_latin = sum(1 for it in items if all(ord(c) < 0x250 or c in "éèêëáàâäíìîïóòôöúùûüçñåøæœšžý" for c in it["cell_value"] if c.isalpha()))
    stats = {
        "n": len(results),
        "identity_preserved": 1.0,
        "ru_form_provided": 0.0,
        "latin_script_source_cells": n_latin,
        "latin_share": n_latin / len(items),
        "note": ("copy leaves 100% identity but provides no Russian surface form; "
                 "for a RU dataset every cell would remain English"),
    }
    out = Path(__file__).resolve().parents[1] / "results"
    jdumpl(out / "exp0_copy.jsonl", results)
    (out / "exp0_copy_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1))
    print(json.dumps(stats, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
