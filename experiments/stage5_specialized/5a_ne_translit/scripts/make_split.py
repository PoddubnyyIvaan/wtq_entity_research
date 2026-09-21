"""Experiment 5A - fine-tune ByT5-small for EN->RU personal-name transliteration.

Data: ParaNames PER pairs (eng canonical -> ru label), entity-level split
(one QID only in one of train/dev/test). Subsampled to a fixed budget
(seed 42) to fit the 3-5 epoch budget on RTX 4060.
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]

SEED = 42
N_TRAIN = 200_000
N_DEV = 3_000
N_TEST = 3_000


def load_pairs():
    seen = set()
    pairs = []
    for line in (ROOT / "experiments" / "paranames" / "cache" / "paranames_en_ru.jsonl").open():
        o = json.loads(line)
        for c in o["cands"]:
            if c["type"] != "PER":
                continue
            qid = c["qid"]
            if qid in seen:
                continue
            seen.add(qid)
            pairs.append({"eng": c["eng_canonical"], "ru": c["ru"], "qid": qid})
    return pairs


def main():
    pairs = load_pairs()
    print("PER entities with RU:", len(pairs), flush=True)
    rng = random.Random(SEED)
    rng.shuffle(pairs)
    # prefer names that exist (all have RU by construction)
    train = pairs[:N_TRAIN]
    dev = pairs[N_TRAIN:N_TRAIN + N_DEV]
    test = pairs[N_TRAIN + N_DEV:N_TRAIN + N_DEV + N_TEST]
    out = {"train": train, "dev": dev, "test": test,
           "counts": {"train": len(train), "dev": len(dev), "test": len(test)},
           "seed": SEED, "split_note": "entity-level (unique QID per split)"}
    (HERE / "results" / "pn_per_split.json").write_text(json.dumps(out, ensure_ascii=False))
    print("saved split:", out["counts"])


if __name__ == "__main__":
    main()
