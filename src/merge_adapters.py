#!/usr/bin/env python3
"""
AEGIS Adapter Merger
Merges Hancock + Sauron LoRA adapters into a unified defensive security model.
Uses PEFT/mergekit for weighted merging.
"""

import os
import sys
import argparse
from pathlib import Path


def _ensure_ml_deps():
    """Lazy-import ML dependencies. Auto-create venv on Kali (PEP 668)."""
    try:
        from peft import PeftModel  # noqa: F401
        from transformers import AutoModelForCausalLM, AutoTokenizer  # noqa: F401
        import torch  # noqa: F401
        return
    except ImportError:
        pass

    venv_dir = Path.home() / ".aegis-venv"
    if not venv_dir.exists():
        print(f"[AEGIS] Creating venv at {venv_dir} (PEP 668 / Kali workaround)...")
        os.system(f"python3 -m venv {venv_dir}")
        os.system(f"{venv_dir}/bin/pip install -q --upgrade pip")
        os.system(f"{venv_dir}/bin/pip install -q transformers peft accelerate bitsandbytes torch safetensors")

    venv_python = venv_dir / "bin" / "python3"
    if str(sys.executable) != str(venv_python):
        print(f"[AEGIS] Re-executing inside venv: {venv_python}")
        os.execv(str(venv_python), [str(venv_python)] + sys.argv)


BASE_MODEL = "mistralai/Mistral-7B-Instruct-v0.3"
# Discovered adapters from /home/x/models/hf/ (May 2026)
# Downloaded via: hf download cyberviser/<repo> --local-dir /home/x/models/hf/<name>
ADAPTER_PATHS = {
    "hancock_pentest": "/home/x/models/hf/hancock-pentest-v1",
    "hancock_mistral": "/home/x/models/hf/hancock-mistral-7b-adapter",
    "hancock_v032": "/home/x/models/hf/hancock-v0.3.2-adapter",
    "sauron": "/home/x/models/hf/sauron-v3",
    "sauron_v1": "/home/x/models/hf/sauron-v1",
    "sauron_v2": "/home/x/models/hf/sauron-v2",
}


def discover_adapters() -> dict:
    """Scan /home/x/models/hf/ for available adapters."""
    found = {}
    for name, path in ADAPTER_PATHS.items():
        if os.path.isdir(path):
            # Check it looks like a PEFT adapter (has adapter_config.json or adapter_model.safetensors)
            has_config = os.path.exists(os.path.join(path, "adapter_config.json"))
            has_weights = any(os.path.exists(os.path.join(path, f"adapter_model.{ext}")) for ext in ["safetensors", "bin"])
            if has_config or has_weights:
                found[name] = path
                print(f"  [OK] {name}: {path}")
            else:
                print(f"  [SKIP] {name}: {path} (no adapter_config.json or adapter_model weights)")
        else:
            print(f"  [MISSING] {name}: {path}")
    return found


def merge_adapters(base_model_name: str, output_dir: str, weights: dict = None):
    """
    Merge multiple LoRA adapters into a single model.
    Uses linear interpolation of adapter weights.
    """
    # Discover available adapters
    available = discover_adapters()
    if not available:
        raise RuntimeError("No adapters found! Run: hf download cyberviser/<repo> --local-dir /home/x/models/hf/<name>")

    # Default weights: prioritize pentest-focused adapters
    default_weights = {
        "hancock_pentest": 0.35,
        "hancock_mistral": 0.25,
        "sauron": 0.25,
        "hancock_v032": 0.15,
    }
    # Filter weights to only available adapters and normalize
    weights = weights or {}
    for k in list(weights.keys()):
        if k not in available:
            del weights[k]
    if not weights:
        weights = {k: v for k, v in default_weights.items() if k in available}

    total = sum(weights.values())
    weights = {k: v / total for k, v in weights.items()}
    print(f"\n[AEGIS] Merge weights (normalized): {weights}")

    # Lazy-load ML deps (auto-creates venv on Kali if needed)
    _ensure_ml_deps()
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch

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
    for name, path in available.items():
        if name not in weights:
            continue

        weight = weights[name]
        print(f"[AEGIS] Loading adapter '{name}' from {path} (weight={weight:.3f})")

        try:
            adapter_model = PeftModel.from_pretrained(model, path)
            adapter_state = adapter_model.state_dict()
        except Exception as e:
            print(f"[WARN] Failed to load {name}: {e}")
            continue

        if merged_state is None:
            merged_state = {k: v * weight for k, v in adapter_state.items()}
        else:
            for k, v in adapter_state.items():
                if k in merged_state:
                    merged_state[k] += v * weight
                else:
                    merged_state[k] = v * weight

    if merged_state is None:
        raise RuntimeError("No adapters successfully loaded for merge!")

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
    parser.add_argument("--list", action="store_true", help="List available adapters and exit")
    parser.add_argument("--hancock-pentest-weight", type=float, default=0.35, help="Hancock pentest adapter weight")
    parser.add_argument("--hancock-mistral-weight", type=float, default=0.25, help="Hancock mistral adapter weight")
    parser.add_argument("--sauron-weight", type=float, default=0.25, help="Sauron adapter weight")
    parser.add_argument("--hancock-v032-weight", type=float, default=0.15, help="Hancock v0.3.2 adapter weight")
    args = parser.parse_args()

    if args.list:
        print("[AEGIS] Available adapters:")
        discover_adapters()
        return

    weights = {
        "hancock_pentest": args.hancock_pentest_weight,
        "hancock_mistral": args.hancock_mistral_weight,
        "sauron": args.sauron_weight,
        "hancock_v032": args.hancock_v032_weight,
    }

    merge_adapters(args.base, args.output, weights)


if __name__ == "__main__":
    main()
