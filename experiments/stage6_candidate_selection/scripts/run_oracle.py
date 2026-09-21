"""Stage 6 — oracle LLM reruns (both models, mode D)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / "scripts"))
import run_llm_selection as R  # noqa: E402


def main():
    R.run_tag("qwen2.5:7b", "D", "oracle", oracle=True)
    R.run_tag("qwen2.5:3b", "D", "oracle", oracle=True)


if __name__ == "__main__":
    main()
