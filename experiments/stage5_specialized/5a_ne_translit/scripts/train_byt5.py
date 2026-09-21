"""Experiment 5A - ByT5-small fine-tuning (RTX 4060, bf16, full FT).

Trains google/byt5-small on the ParaNames PER split (train/dev/test in
results/pn_per_split.json). Logs VRAM peak and epoch time. Saves checkpoint
in models/byt5-small-pn-per/.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[2]
os.environ.setdefault("HF_HOME", str(HERE.parent / ".cache" / "hf"))
print("HF_HOME:", os.environ["HF_HOME"], flush=True)

import torch  # noqa: E402
from torch.utils.data import Dataset  # noqa: E402
from transformers import (AutoModelForSeq2SeqLM, AutoTokenizer,  # noqa: E402
                          DataCollatorForSeq2Seq, Seq2SeqTrainer, Seq2SeqTrainingArguments)

MODEL_NAME = "google/byt5-small"
OUT_DIR = HERE / "models" / "byt5-small-pn-per"
EPOCHS = 3
BATCH = 32
LR = 1e-3
MAX_LEN = 64


class PairDS(Dataset):
    def __init__(self, pairs, tok):
        self.pairs = pairs
        self.tok = tok

    def __len__(self):
        return len(self.pairs)

    def __getitem__(self, i):
        p = self.pairs[i]
        model_in = self.tok(p["eng"], truncation=True, max_length=MAX_LEN)
        labels = self.tok(p["ru"], truncation=True, max_length=MAX_LEN)
        return {"input_ids": model_in["input_ids"],
                "attention_mask": model_in["attention_mask"],
                "labels": labels["input_ids"]}


def main():
    split = json.loads((HERE / "results" / "pn_per_split.json").read_text(encoding="utf-8"))
    tok = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModelForSeq2SeqLM.from_pretrained(MODEL_NAME, dtype=torch.bfloat16).cuda()
    tds = PairDS(split["train"], tok)
    vds = PairDS(split["dev"], tok)
    targs = Seq2SeqTrainingArguments(
        output_dir=str(OUT_DIR),
        per_device_train_batch_size=BATCH,
        per_device_eval_batch_size=BATCH,
        learning_rate=LR,
        num_train_epochs=EPOCHS,
        eval_strategy="epoch",
        save_strategy="steps", save_steps=1000,
        logging_steps=500,
        bf16=True,
        gradient_checkpointing=True,
        save_total_limit=1,
        report_to=[],
        seed=42,
        dataloader_num_workers=0,
        disable_tqdm=True,
    )
    trainer = Seq2SeqTrainer(model=model, args=targs, train_dataset=tds, eval_dataset=vds,
                             data_collator=DataCollatorForSeq2Seq(tok, model=model))
    t0 = time.time()
    trainer = Seq2SeqTrainer(model=model, args=targs, train_dataset=tds, eval_dataset=vds,
                             data_collator=DataCollatorForSeq2Seq(tok, model=model))
    trainer.train()
    train_s = round(time.time() - t0, 1)
    peak = torch.cuda.max_memory_allocated() / 2 ** 20
    print(f"train done in {train_s}s, peak VRAM {peak:.0f} MiB", flush=True)
    # save final model
    model.save_pretrained(str(OUT_DIR))
    tok.save_pretrained(str(OUT_DIR))
    (HERE / "results" / "train_meta.json").write_text(json.dumps({
        "model": MODEL_NAME, "epochs": EPOCHS, "batch": BATCH, "lr": LR,
        "bf16": True, "gradient_checkpointing": True,
        "train_time_s": train_s, "peak_vram_mib": round(peak, 0),
        "train_size": len(tds), "device": torch.cuda.get_device_name(0),
    }, ensure_ascii=False, indent=1))
    print("saved model + meta")


if __name__ == "__main__":
    main()
