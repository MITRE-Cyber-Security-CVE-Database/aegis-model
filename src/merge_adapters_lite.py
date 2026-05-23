#!/usr/bin/env python3
"""
AEGIS Lite Adapter Merger
=========================
Merges multiple LoRA adapter safetensors files via weighted linear interpolation
WITHOUT requiring torch / peft / transformers.

Only deps: numpy + safetensors (~10MB).

Why this exists:
  The full merge_adapters.py path needs ~5GB venv (torch + peft + transformers)
  + 14GB Mistral-7B base model. We don't have that disk budget.
  This script merges only the adapter deltas (the LoRA matrices A and B), which
  is sufficient when the adapters share the same base model + same target
  modules. Each output tensor is:
      W_merged[name] = sum_i (w_i * W_i[name])  for shared keys
      W_merged[name] = W_i[name]                for unique keys (preserved as-is)

Usage:
  python3 merge_adapters_lite.py \\
      --output /home/x/models/hf/aegis-v1-adapter \\
      --weights hancock_pentest=0.40,hancock_v032=0.20,sauron=0.40
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from safetensors import safe_open
from safetensors.numpy import save_file


ADAPTER_PATHS = {
    "hancock_pentest": "/home/x/models/hf/hancock-pentest-v1",
    "hancock_mistral": "/home/x/models/hf/hancock-mistral-7b-adapter",
    "hancock_v032":    "/home/x/models/hf/hancock-v0.3.2-adapter",
    "sauron":          "/home/x/models/hf/sauron-v3",
    "sauron_v1":       "/home/x/models/hf/sauron-v1",
    "sauron_v2":       "/home/x/models/hf/sauron-v2",
}


def load_adapter_tensors(path: Path) -> dict[str, np.ndarray]:
    """Load all tensors from adapter_model.safetensors as numpy arrays."""
    f = path / "adapter_model.safetensors"
    if not f.exists():
        raise FileNotFoundError(f"Missing {f}")
    out = {}
    with safe_open(str(f), framework="numpy") as fh:
        for k in fh.keys():
            out[k] = fh.get_tensor(k)
    return out


def parse_weights(spec: str) -> dict[str, float]:
    """Parse 'name=0.4,other=0.6' into {'name': 0.4, 'other': 0.6}."""
    out = {}
    for tok in spec.split(","):
        tok = tok.strip()
        if not tok:
            continue
        name, _, val = tok.partition("=")
        out[name.strip()] = float(val.strip())
    return out


def merge(weights: dict[str, float], output: Path, force: bool = False):
    output = Path(output)
    if output.exists() and not force:
        print(f"[!] Output {output} already exists. Use --force to overwrite.")
        return

    # 1. Validate paths + load
    paths = {}
    for name in weights:
        if name not in ADAPTER_PATHS:
            print(f"[!] Unknown adapter '{name}'. Choose from: {list(ADAPTER_PATHS)}")
            sys.exit(2)
        p = Path(ADAPTER_PATHS[name])
        if not p.exists():
            print(f"[!] Adapter dir missing: {p}")
            sys.exit(2)
        paths[name] = p

    total_w = sum(weights.values())
    if abs(total_w - 1.0) > 1e-3:
        print(f"[*] Normalizing weights (sum was {total_w:.3f})")
        weights = {k: v / total_w for k, v in weights.items()}
    print(f"[*] Effective weights: {weights}")

    # 2. Load all adapter tensors
    loaded: dict[str, dict[str, np.ndarray]] = {}
    for name, p in paths.items():
        print(f"[*] Loading {name} from {p}")
        loaded[name] = load_adapter_tensors(p)
        print(f"    {len(loaded[name])} tensors")

    # 3. Compute the union of tensor keys
    all_keys: set[str] = set()
    for t in loaded.values():
        all_keys |= set(t.keys())

    # 4. Merge tensor-by-tensor
    print(f"[*] Merging {len(all_keys)} unique tensor keys...")
    merged: dict[str, np.ndarray] = {}
    skipped_shape = 0

    for k in sorted(all_keys):
        contributors = [(name, loaded[name][k]) for name in weights if k in loaded[name]]
        if not contributors:
            continue
        # Resolve dtype + shape: use the first contributor's shape as target
        ref_shape = contributors[0][1].shape
        ref_dtype = contributors[0][1].dtype

        # Filter contributors with matching shape
        compat = [(n, t) for n, t in contributors if t.shape == ref_shape]
        if len(compat) < len(contributors):
            skipped_shape += len(contributors) - len(compat)

        # Renormalize weights across the present + shape-compatible contributors
        present_w = {n: weights[n] for n, _ in compat}
        s = sum(present_w.values()) or 1.0
        present_w = {n: w / s for n, w in present_w.items()}

        acc = np.zeros(ref_shape, dtype=np.float32)
        for n, t in compat:
            acc += present_w[n] * t.astype(np.float32)
        merged[k] = acc.astype(ref_dtype)

    print(f"[*] Merged {len(merged)} tensors  (shape mismatches dropped: {skipped_shape})")

    # 5. Write output
    output.mkdir(parents=True, exist_ok=True)
    out_file = output / "adapter_model.safetensors"
    save_file(merged, str(out_file))
    print(f"[+] Wrote {out_file}  ({out_file.stat().st_size / 1e6:.1f} MB)")

    # 6. Copy config from the largest contributor (adapter_config.json + tokenizer)
    largest = max(weights, key=weights.get)
    src = paths[largest]
    for fname in ("adapter_config.json", "tokenizer_config.json", "tokenizer.json",
                  "tokenizer.model", "chat_template.jinja"):
        s = src / fname
        if s.exists():
            shutil.copy2(s, output / fname)
            print(f"    copied {fname}  (from {largest})")

    # 7. Write provenance
    (output / "AEGIS_MERGE.json").write_text(json.dumps({
        "merge_type": "linear_lora_average",
        "weights": weights,
        "source_adapters": {n: str(p) for n, p in paths.items()},
        "tensor_count": len(merged),
        "shape_mismatches_dropped": skipped_shape,
    }, indent=2))
    print(f"[+] Wrote {output/'AEGIS_MERGE.json'}")
    print()
    print(f"Done. Output: {output}")


def main():
    p = argparse.ArgumentParser(description="Lite LoRA adapter merger (numpy + safetensors only)")
    p.add_argument("--output", default="/home/x/models/hf/aegis-v1-adapter")
    p.add_argument("--weights", default="hancock_pentest=0.40,hancock_v032=0.20,sauron=0.40",
                   help="Comma-separated name=weight pairs (will be normalized to sum=1.0)")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()

    weights = parse_weights(args.weights)
    merge(weights, Path(args.output), force=args.force)


if __name__ == "__main__":
    main()
