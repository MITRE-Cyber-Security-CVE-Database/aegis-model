#!/usr/bin/env python3
"""
AEGIS Model Quantization Script
Converts merged PEFT adapter to GGUF format for Ollama deployment.
Requires llama.cpp (convert.py or convert-hf-to-gguf.py)
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path


def find_llama_cpp() -> Path:
    """Find llama.cpp installation."""
    candidates = [
        Path.home() / "llama.cpp",
        Path("/usr/local/src/llama.cpp"),
        Path("./llama.cpp"),
        Path("../llama.cpp"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def quantize_model(
    base_model: str,
    adapter_path: str,
    output_path: str,
    quant_type: str = "Q4_K_M",
) -> str:
    """
    Merge base model + adapter, then quantize to GGUF.
    """
    print(f"[AEGIS] Quantizing to {quant_type}")
    print(f"[AEGIS] Base: {base_model}")
    print(f"[AEGIS] Adapter: {adapter_path}")

    # Step 1: Merge adapter into base model
    print("[AEGIS] Step 1/3: Merging adapter into base model...")
    merge_script = """
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

base = AutoModelForCausalLM.from_pretrained('{base}', torch_dtype=torch.float16, device_map='auto')
tokenizer = AutoTokenizer.from_pretrained('{base}')
model = PeftModel.from_pretrained(base, '{adapter}')
merged = model.merge_and_unload()
merged.save_pretrained('{merged_dir}')
tokenizer.save_pretrained('{merged_dir}')
print('Merged model saved to {merged_dir}')
""".format(base=base_model, adapter=adapter_path, merged_dir="./aegis-merged-f16")

    with open("/tmp/merge_script.py", "w") as f:
        f.write(merge_script)

    result = subprocess.run([sys.executable, "/tmp/merge_script.py"], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(f"[ERROR] Merge failed: {result.stderr}")
        return None

    # Step 2: Convert to GGUF using llama.cpp
    print("[AEGIS] Step 2/3: Converting to GGUF...")
    llama = find_llama_cpp()

    if llama is None:
        print("[AEGIS] llama.cpp not found. Installing...")
        subprocess.run(["git", "clone", "--depth", "1", "https://github.com/ggerganov/llama.cpp.git", str(Path.home() / "llama.cpp")])
        llama = Path.home() / "llama.cpp"

    # Use convert-hf-to-gguf.py (newer format)
    convert_script = llama / "convert_hf_to_gguf.py"
    if not convert_script.exists():
        convert_script = llama / "convert.py"

    if convert_script.exists():
        cmd = [
            sys.executable, str(convert_script),
            "./aegis-merged-f16",
            "--outfile", output_path,
            "--outtype", "f16",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        print(result.stdout)
        if result.returncode != 0:
            print(f"[WARN] Convert output: {result.stderr}")
    else:
        print("[WARN] llama.cpp convert script not found. Trying alternative...")
        # Alternative: use transformers + safetensors directly
        return None

    # Step 3: Quantize if not already at target level
    if quant_type != "F16":
        print(f"[AEGIS] Step 3/3: Quantizing to {quant_type}...")
        quantize_bin = llama / "build" / "bin" / "llama-quantize"
        if not quantize_bin.exists():
            quantize_bin = llama / "llama-quantize"

        if quantize_bin.exists():
            final_output = output_path.replace(".gguf", f"-{quant_type}.gguf")
            cmd = [str(quantize_bin), output_path, final_output, quant_type]
            result = subprocess.run(cmd, capture_output=True, text=True)
            print(result.stdout)
            if result.returncode == 0:
                os.remove(output_path)  # Remove F16 intermediate
                output_path = final_output
        else:
            print(f"[WARN] llama-quantize not found at {quantize_bin}")
            print("[AEGIS] Keeping F16 format. Install llama.cpp for quantization:")
            print("  cd ~/llama.cpp && cmake -B build && cmake --build build --config Release")

    print(f"[AEGIS] Model saved: {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="AEGIS Model Quantization")
    parser.add_argument("--base", default="mistralai/Mistral-7B-Instruct-v0.3", help="Base model")
    parser.add_argument("--adapter", default="./aegis-merged-adapter", help="Adapter path")
    parser.add_argument("--output", default="./aegis-Q4_K_M.gguf", help="Output GGUF file")
    parser.add_argument("--quantization", default="Q4_K_M", choices=["F16", "Q8_0", "Q6_K", "Q5_K_M", "Q4_K_M", "Q4_0"])
    args = parser.parse_args()

    quantize_model(args.base, args.adapter, args.output, args.quantization)


if __name__ == "__main__":
    main()
