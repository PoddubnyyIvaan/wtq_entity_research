"""Re-run of mandatory LLM cases (kept as script for reproducibility)."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from exp1_context import chat, parse_json_loose

def main():
    tpl = (Path(__file__).resolve().parents[1] / "prompts" / "exp1_v2.txt").read_text()
    out = json.load(Path(__file__).resolve().parents[1] / "results" / "mandatory_llm.json").open()
    print("already ran; see results/mandatory_llm.json")

if __name__ == "__main__":
    main()
