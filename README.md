# Project AEGIS
**Advanced Endpoint & Global Intelligence Shield**

A military-grade defensive cybersecurity model to surpass Anthropic's Glasswing/Mythos Preview.
Built by CyberViser (Johnny Watters) using free student resources, open-source tooling, and existing HF adapters.

---

## Why AEGIS > Mythos

| Feature | Anthropic Mythos | Project AEGIS |
|---------|-----------------|---------------|
| Cost | $25-125/M tokens | **$0** (local Ollama) |
| Architecture | Closed, API-only | **Open, containerized** |
| Deployment | Cloud-restricted | **Air-gapped capable** |
| Compliance | Anthropic-controlled | **CyberViser-controlled** |
| Customization | Black-box | **Fully fine-tuned + merged** |
| Student Access | $100M partner-only | **Built by students, for students** |

---

## Quick Start

```bash
cd /home/x/aegis-model

# 1. Merge existing adapters into AEGIS base
python src/merge_adapters.py

# 2. Create Ollama model
ollama create aegis -f deploy/Modelfile

# 3. Deploy locally
ollama run aegis

# 4. Evaluate against security benchmarks
python eval/evaluate.py --model aegis --benchmarks all
```

---

## Resource Strategy: Zero-Cost Military Grade

### Phase 1: GitHub Student Pack Activation (johnny.watters@email.phoenix.edu)

Activate at: https://education.github.com/pack

| Resource | Free Credit | Purpose |
|----------|-------------|---------|
| **GitHub Copilot** | Free | AI-assisted security code review |
| **Azure for Students** | $100 + free services | GPU VM training |
| **AWS Educate** | $30-50/month | Deployment & S3 storage |
| **DigitalOcean** | $200 | K8s clusters |
| **JetBrains** | Free IDEs | Development |
| **Namecheap** | Free .me domain | `cyberviser.me` |
| **Datadog** | Free Pro | Security monitoring |
| **Sentry** | Free | Error tracking |

### Phase 2: Azure GPU Training ($100 Student Credit)

```bash
# Deploy NC6s_v3 (Tesla V100) via Bicep
az deployment group create \
  --resource-group aegis-training \
  --template-file deploy/azure-gpu.bicep \
  --parameters adminUsername=cyberviser
```

**Training time:** ~$3/hour = **33 hours of V100 training** on $100 credit.

### Phase 3: AWS Free Tier Deployment

```bash
# Deploy inference endpoint on AWS
cd deploy && terraform apply
```

Uses AWS Free Tier (750 hours/month t2.micro) + Educate credits for GPU inference.

### Phase 4: GitHub Actions CI/CD (Unlimited Public Repo)

```yaml
# .github/workflows/build-model.yml
# Triggers: push to main, weekly schedule
# Actions: merge adapters -> quantize -> evaluate -> release
```

---

## Model Architecture

```
Base: mistralai/Mistral-7B-Instruct-v0.3
    |
    +-- Hancock Pentest Adapter (hancock-pentest-v1)
    +-- Sauron Security Adapter (sauron-v3)
    +-- CyberViser Custom Corpus (CVE, exploits, patches)
    |
    = AEGIS-v1.0 (merged + quantized)
```

### Quantization Targets

| Format | Size | Use Case |
|--------|------|----------|
| Q4_K_M | ~4.4 GB | Desktop/laptop inference |
| Q8_0 | ~7.6 GB | Server inference |
| F16 | ~14 GB | Training/fine-tuning |

---

## Security Benchmarks

| Benchmark | Mythos Preview | AEGIS Target |
|-----------|---------------|--------------|
| CyberGym | 83.1% | **85%+** |
| SWE-bench Verified | 93.9% | **90%+** |
| CVEFixes | N/A | **80%+** |
| Devign | N/A | **75%+** |
| CWE-Top-25 | N/A | **90%+** |

---

## Directory Structure

```
aegis-model/
├── .github/workflows/      # CI/CD pipelines
├── deploy/                 # Infrastructure as Code
│   ├── azure-gpu.bicep     # Azure GPU VM
│   ├── aws-gpu.tf          # AWS Terraform
│   ├── aws-gpu.yml         # AWS CloudFormation
│   └── Modelfile           # Ollama model definition
├── src/                    # Source code
│   ├── merge_adapters.py   # Adapter merging
│   ├── train.py            # Fine-tuning script
│   └── quantize.py         # GGUF quantization
├── eval/                   # Evaluation
│   ├── evaluate.py         # Benchmark runner
│   └── metrics.py          # Scoring
├── benchmarks/             # Test datasets
├── corpus/                 # Training data
└── README.md
```

---

## Student Credit Activation Checklist

- [ ] **GitHub Student Pack**: https://education.github.com/pack (use johnny.watters@email.phoenix.edu)
- [ ] **Azure for Students**: https://azure.microsoft.com/en-us/free/students/
- [ ] **AWS Educate**: https://aws.amazon.com/education/awseducate/
- [ ] **DigitalOcean**: Via GitHub Student Pack
- [ ] **Namecheap Domain**: Free .me domain via GitHub Student Pack
- [ ] **JetBrains**: Free IDEs via GitHub Student Pack

---

## Legal & Ethical

**AEGIS is a DEFENSIVE tool.**
- All training data is publicly available (CVE, NVD, open-source patches)
- Model weights will be released under Apache 2.0
- Compliance enforcer (from GlasseyeOS-AI) ensures safe harbor
- Human-in-the-loop required for exploitation actions

---

**Built by CyberViser. For the defenders.**
