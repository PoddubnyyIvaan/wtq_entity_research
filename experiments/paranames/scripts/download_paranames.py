"""Records the official download (idempotent).

URL: https://github.com/bltlab/paranames/releases/download/v2024.05.07.0/paranames.tsv.gz
Asset also referenced from: https://github.com/bltlab/paranames/releases/tag/v2024.05.07.0
Local path: ../raw/paranames.tsv.gz (git-cached, not copied into outputs).
"""
import subprocess
import sys
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "raw" / "paranames.tsv.gz"

def main():
    if RAW.exists() and RAW.stat().st_size == 999401108:
        print("already downloaded")
        return
    subprocess.run(["curl", "-fSL", "-o", str(RAW),
                    "https://github.com/bltlab/paranames/releases/download/v2024.05.07.0/paranames.tsv.gz"],
                   check=True)

if __name__ == "__main__":
    main()
