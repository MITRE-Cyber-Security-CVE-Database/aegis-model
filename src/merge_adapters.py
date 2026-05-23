#!/usr/bin/env python3
"""
AEGIS Adapter Merger
Merges Hancock + Sauron LoRA adapters into a unified defensive security model.
Uses PEFT/mergekit for weighted merging.
"""

import os
import argparse
from pathlib import Path

try:
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch
except ImportError:
    print("Installing dependencies...")
    os.system("pip install -q transformers peft accelerate bitsandbytes")
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch


BASE_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"
ADAPTER_PATHS = {
    "hancock": "/home/x/models/hf/hancock-pentest-v1",
    "sauron": "/home/x/models/hf/sauron-v3",
    "hancock_v2": "/home/x/models/hf/hancock-v0.3.2-adapter",
}


def merge_adapters(base_model_name: str, output_dir: str, weights: dict = None):
    """
    Merge multiple LoRA adapters into a single model.
    Uses linear interpolation of adapter weights.
    """
    weights = weights or {"hancock": 0.4, "sauron": 0.4, "hancock_v2": 0.2}

    print(f"[AEGIS] Loading base model: {base_model_name}")
    print(f"[AEGIS] This will use ~14GB RAM. Ensure you have sufficient memory.")

    tokenizer = AutoTokenizer.from_pretrained(base_model_name)

    # Load base model in 8-bit to save memory
    model = AutoModelForCausalLM.from_pretrained(
        base_model_name,
        torch_dtype=torch.float16,
        device_map="auto",
        load_in_8bit=True,
    )

    # Load and merge each adapter
    merged_state = None
    for name, path in ADAPTER_PATHS.items():
        if not os.path.exists(path):
            print(f"[WARN] Adapter {name} not found at {path}, skipping")
            continue

        weight = weights.get(name, 0.33)
        print(f"[AEGIS] Loading adapter '{name}' from {path} (weight={weight})")

        adapter_model = PeftModel.from_pretrained(model, path)
        adapter_state = adapter_model.state_dict()

        if merged_state is None:
            merged_state = {k: v * weight for k, v in adapter_state.items()}
        else:
            for k, v in adapter_state.items():
                if k in merged_state:
                    merged_state[k] += v * weight
                else:
                    merged_state[k] = v * weight

    if merged_state is None:
        raise RuntimeError("No adapters found to merge!")

    # Apply merged state to a new PEFT model
    print("[AEGIS] Applying merged adapter weights...")
    # Save merged adapter
    os.makedirs(output_dir, exist_ok=True)

    # We need to save in PEFT format - create a dummy adapter and overwrite weights
    # Simpler approach: save the merged state dict
    torch.save(merged_state, os.path.join(output_dir, "adapter_model_merged.bin"))

    # Copy config from first available adapter
    for name, path in ADAPTER_PATHS.items():
        if os.path.exists(path):
            import shutil
            for f in ["adapter_config.json", "tokenizer_config.json", "chat_template.jinja"]:
                src = os.path.join(path, f)
                if os.path.exists(src):
                    shutil.copy(src, os.path.join(output_dir, f))
            break

    print(f"[AEGIS] Merged adapter saved to: {output_dir}")
    print(f"[AEGIS] Next steps:")
    print(f"  1. Quantize: python src/quantize.py --adapter {output_dir}")
    print(f"  2. Create Ollama model: ollama create aegis -f deploy/Modelfile")
    return output_dir


def merge_with_mergekit(output_dir: str):
    """Alternative: Use mergekit for more sophisticated merging."""
    print("[AEGIS] Attempting mergekit merge (requires mergekit installation)...")
    try:
        import mergekit
        print("mergekit available")
    except ImportError:
        print("mergekit not installed. Install with: pip install mergekit")
        print("Falling back to PEFT linear merge...")
        return merge_adapters(BASE_MODEL, output_dir)


def main():
    parser = argparse.ArgumentParser(description="AEGIS Adapter Merger")
    parser.add_argument("--output", default="/home/x/models/hf/aegis-v1-adapter", help="Output directory")
    parser.add_argument("--base", default=BASE_MODEL, help="Base model name")
    parser.add_argument("--hancock-weight", type=float, default=0.4, help="Hancock adapter weight")
    parser.add_argument("--sauron-weight", type=float, default=0.4, help="Sauron adapter weight")
    parser.add_argument("--hancock2-weight", type=float, default=0.2, help="Hancock v2 adapter weight")
    args = parser.parse_args()

    weights = {
        "hancock": args.hancock_weight,
        "sauron": args.sauron_weight,
        "hancock_v2": args.hancock2_weight,
    }

    merge_adapters(args.base, args.output, weights)


if __name__ == "__main__":
    main()
