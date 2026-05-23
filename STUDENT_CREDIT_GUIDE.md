# Student Credit Activation Guide — Project AEGIS
**Target:** Johnny Watters (johnny.watters@email.phoenix.edu)  
**Goal:** Unlock $500+ in free cloud credits for military-grade AI training

---

## Step 1: GitHub Student Developer Pack (Gateway to Everything)

**URL:** https://education.github.com/pack  
**Eligibility:** Enrolled student with `.edu` email  
**Value:** $10,000+ in free tools and credits

### Activation Checklist

- [ ] Go to https://education.github.com/pack
- [ ] Click "Get your pack"
- [ ] Sign in with GitHub account: `gulfofamerica`
- [ ] Verify student status using: `johnny.watters@email.phoenix.edu`
- [ ] Upload student ID or enrollment verification (if prompted)
- [ ] Wait for approval (usually instant for .edu emails)

### What You Unlock

| Benefit | Value | How to Use for AEGIS |
|---------|-------|---------------------|
| **GitHub Copilot** | Free | AI-assisted security code review |
| **Azure for Students** | $100 credit + free services | GPU VM training (33 hours V100) |
| **AWS Educate** | $30-50/month | Deployment + S3 model storage |
| **DigitalOcean** | $200 credit | Kubernetes clusters |
| **Namecheap** | Free .me domain | `cyberviser.me` |
| **JetBrains** | Free IDEs | PyCharm Professional |
| **Datadog** | Free Pro tier | Security monitoring |
| **Sentry** | Free | Error tracking |
| **Travis CI** | Free private builds | CI/CD backup |
| **Heroku** | Free dyno hours | Quick web app deployment |

---

## Step 2: Azure for Students ($100 Credit)

**URL:** https://azure.microsoft.com/en-us/free/students/  
**Prerequisite:** GitHub Student Pack activated  
**Credit:** $100 valid for 12 months  
**GPU Access:** Yes, NC-series VMs available

### Activation

```bash
# Sign up at the URL above
# Use GitHub login (already verified as student)
# No credit card required for student tier!
```

### GPU VM Pricing (Student Budget Math)

| VM Type | GPU | Cost/Hour | Hours on $100 |
|---------|-----|-----------|---------------|
| NC6s_v3 | 1x V100 | ~$3.00 | **33 hours** |
| NC12s_v3 | 2x V100 | ~$6.00 | 16 hours |
| NC24s_v3 | 4x V100 | ~$12.00 | 8 hours |
| NV6 | 1x M60 | ~$1.80 | 55 hours |
| NV12 | 2x M60 | ~$3.60 | 27 hours |

**Recommendation:** Start with `NV6` (M60) for longer training runs, then use `NC6s_v3` (V100) for final fine-tuning.

### Deploy AEGIS Training VM

```bash
# Clone the repo
git clone https://github.com/gulfofamerica/aegis-model.git
cd aegis-model/deploy

# Generate SSH key
ssh-keygen -t ed25519 -f ~/.ssh/aegis-azure -C "aegis-training"

# Deploy GPU VM via Bicep
az login  # Sign in with Azure student account
az group create --name aegis-training --location eastus
az deployment group create \
  --resource-group aegis-training \
  --template-file azure-gpu.bicep \
  --parameters adminSshKey="$(cat ~/.ssh/aegis-azure.pub)"

# Connect
ssh -i ~/.ssh/aegis-azure cyberviser@<IP_FROM_OUTPUT>
```

**Budget Protection Built-In:**
- Auto-shutdown at 22:00 UTC daily
- $100 budget alarm at 80% and 100%

---

## Step 3: AWS Educate ($30-50/Month)

**URL:** https://aws.amazon.com/education/awseducate/  
**Prerequisite:** GitHub Student Pack or .edu email  
**Credit:** $30-50/month recurring  
**Duration:** While enrolled

### Activation

```bash
# Sign up at URL above
# Use: johnny.watters@email.phoenix.edu
# Complete AWS Educate starter courses (optional but recommended)
```

### GPU Pricing (Educate Credits)

| Instance | GPU | On-Demand | Spot (70% off) |
|----------|-----|-----------|----------------|
| g4dn.xlarge | 1x T4 | $0.526/hr | ~$0.16/hr |
| g4dn.2xlarge | 1x T4 | $0.752/hr | ~$0.23/hr |
| p3.2xlarge | 1x V100 | $3.06/hr | ~$0.92/hr |

**Budget Math:** $30/month = 187 hours of spot g4dn.xlarge training!

### Deploy AEGIS on AWS

```bash
cd aegis-model/deploy

# Install Terraform
# https://developer.hashicorp.com/terraform/install

# Set up AWS credentials
aws configure  # Use AWS Educate access keys

# Deploy
terraform init
terraform plan
terraform apply

# Output shows SSH command and Jupyter URL
```

---

## Step 4: DigitalOcean ($200 Credit)

**URL:** Via GitHub Student Pack  
**Credit:** $200 for 12 months  
**Best For:** Kubernetes clusters, load balancers

### Use Case for AEGIS

Deploy a K8s cluster to serve the AEGIS model API:

```bash
# Create cluster
doctl kubernetes cluster create aegis-k8s \
  --region nyc1 \
  --version 1.29 \
  --node-pool "name=gpu-pool;size=g-4vcpu-16gb;count=2"

# Deploy Ollama + AEGIS model
kubectl apply -f deploy/k8s-aegis.yaml
```

---

## Step 5: GitHub Actions (Unlimited Public Repo CI/CD)

**Cost:** FREE for public repositories  
**Limit:** Unlimited minutes for public repos  
**Limit:** 2000 minutes/month for private repos

### Strategy

1. **Make `aegis-model` repo PUBLIC** on GitHub
2. Push code to trigger automated builds
3. GitHub Actions auto-merges adapters, quantizes, evaluates
4. Releases published as GitHub Releases with artifacts
5. Zero cost, unlimited builds

```bash
cd /home/x/aegis-model
git init
git remote add origin https://github.com/gulfofamerica/aegis-model.git
git add .
git commit -m "Initial AEGIS model v0.1.0"
git push -u origin main
```

### What CI/CD Does (Free)

- Merge Hancock + Sauron adapters
- Quantize to GGUF (Q4_K_M, Q8_0, F16)
- Evaluate against security benchmarks
- Publish model artifacts to GitHub Releases
- Comment benchmark results on PRs

---

## Credit Maximization Strategy

| Week | Resource | Action | Cost |
|------|----------|--------|------|
| 1 | GitHub + Azure | Set up, test merge, small training | $0-20 |
| 2 | AWS Spot | Main training run (g4dn spot) | $0-30 |
| 3 | Azure NC | Final fine-tuning on V100 | $50-80 |
| 4 | DigitalOcean | Deploy K8s serving cluster | $20-40 |
| Ongoing | GitHub Actions | CI/CD, evaluation | $0 |

**Total Burn:** ~$100-170/month across all platforms  
**Total Value:** $300+ in compute resources  
**Savings:** 60-70% via spot instances + student credits

---

## Free Tier Perpetual Resources (No Credits Needed)

| Service | Free Tier | Use for AEGIS |
|---------|-----------|---------------|
| GitHub | Unlimited public repos | Code, CI/CD, releases |
| Hugging Face | Unlimited public models | Model hosting |
| Ollama | Local inference | Desktop deployment |
| Docker Hub | Unlimited public pulls | Container distribution |
| Cloudflare Pages | Unlimited static sites | Documentation |
| Vercel | Hobby tier | Web dashboard |
| Supabase | 500MB database | KB storage |
| Neon | 3GB Postgres | Alternative to Supabase |

---

## Troubleshooting

### "Azure says I need a credit card"
- Make sure you're using **Azure for Students** (not regular free tier)
- Verify GitHub Student Pack first
- Contact Azure support with student ID if stuck

### "AWS Educate says I'm not eligible"
- Try the GitHub Student Pack route first
- If that fails, email AWS Educate support with enrollment verification
- Alternative: AWS Free Tier (no credits, but 750 hours t2.micro/month)

### "GPU instances not available in my region"
- Azure: Use `eastus`, `westus2`, or `southcentralus`
- AWS: Use `us-east-1`, `us-west-2`, or `eu-west-1`
- Check GPU quota: Azure Portal → Subscriptions → Quotas

### "I ran out of credits mid-training"
- The scripts have auto-save checkpoints every 500 steps
- Resume from checkpoint: `--resume_from_checkpoint`
- Switch to cheaper instance type and continue

---

## Next Steps After Credit Activation

1. ✅ Activate GitHub Student Pack
2. ✅ Sign up for Azure + AWS Educate
3. ✅ Fork/clone aegis-model repo to GitHub
4. ✅ Deploy first GPU VM (Azure or AWS)
5. ✅ Run: `python src/merge_adapters.py`
6. ✅ Evaluate baseline: `python eval/evaluate.py --model mistral`
7. 🎯 Train AEGIS v1.0 and beat Mythos Preview's 83.1% CyberGym

---

**AEGIS: Built by students. For the defenders. Against the glasswing.**
