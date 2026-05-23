#!/usr/bin/env bash
# AEGIS Asset Recon — defensive inventory of local + LAN + cloud assets.
# Non-destructive. Skips OS fingerprint (-O) if not root.
#
# Usage:
#   bash scan_assets.sh [output_dir]
#
# Output: {output_dir}/<timestamp>/{system,filesystem,services,software,
#                                    network_passive,network_active,cloud,
#                                    secrets,summary}.{json,md,txt}
set -uo pipefail

OUT_BASE="${1:-/home/x/aegis-model/recon/inventory}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$OUT_BASE/$TS"
mkdir -p "$OUT"

LOG() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$OUT/scan.log"; }
SECTION() { echo; LOG "=== $* ==="; }

LOG "AEGIS recon starting → $OUT"
LOG "Host: $(hostname)  User: $(whoami)  PID: $$"

# ----------------------------------------------------------------------------
SECTION "1. SYSTEM"
{
  echo "{"
  echo "  \"hostname\": \"$(hostname)\","
  echo "  \"fqdn\": \"$(hostname -f 2>/dev/null || hostname)\","
  echo "  \"kernel\": \"$(uname -srm)\","
  echo "  \"distro\": \"$(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME")\","
  echo "  \"uptime\": \"$(uptime -p 2>/dev/null || uptime)\","
  echo "  \"boot_time\": \"$(uptime -s 2>/dev/null || echo unknown)\","
  echo "  \"load_avg\": \"$(cut -d' ' -f1-3 /proc/loadavg 2>/dev/null)\","
  echo "  \"cpu_model\": \"$(grep -m1 'model name' /proc/cpuinfo 2>/dev/null | cut -d: -f2- | sed 's/^ //')\","
  echo "  \"cpu_cores\": $(nproc 2>/dev/null || echo 0),"
  mem_total=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}')
  mem_free=$(grep MemAvailable /proc/meminfo 2>/dev/null | awk '{print $2}')
  echo "  \"memory_kb\": {\"total\": ${mem_total:-0}, \"available\": ${mem_free:-0}},"
  echo "  \"swap_kb\": {\"total\": $(grep SwapTotal /proc/meminfo 2>/dev/null | awk '{print $2}'), \"free\": $(grep SwapFree /proc/meminfo 2>/dev/null | awk '{print $2}')},"
  echo "  \"users_logged_in\": $(who | wc -l),"
  echo "  \"current_user\": \"$(whoami)\","
  echo "  \"is_root\": $([ $(id -u) = 0 ] && echo true || echo false),"
  echo "  \"shells_in_use\": $(ps -eo comm | grep -E '^(zsh|bash|fish|sh)$' | sort -u | wc -l)"
  echo "}"
} > "$OUT/system.json"
LOG "  → system.json"

lsblk -J 2>/dev/null > "$OUT/disks.json" || lsblk > "$OUT/disks.txt"
df -h --output=source,fstype,size,used,avail,pcent,target 2>/dev/null > "$OUT/disk_usage.txt"
LOG "  → disks.json, disk_usage.txt"

# ----------------------------------------------------------------------------
SECTION "2. FILESYSTEM (top-level home dirs by size)"
{
  echo "# Top 40 largest dirs in /home/x (depth ≤2)"
  du -sh /home/x/*/ 2>/dev/null | sort -rh | head -40
  echo
  echo "# Project dirs (look like git repos)"
  find /home/x -maxdepth 3 -type d -name .git 2>/dev/null | xargs -I{} dirname {} 2>/dev/null | head -50
  echo
  echo "# Notable file types"
  find /home/x -maxdepth 3 -type f \( -name '*.tf' -o -name 'docker-compose*.y*ml' \
       -o -name 'Dockerfile' -o -name 'azure-pipelines*.y*ml' -o -name '.github' \
       -o -name '*.bicep' -o -name 'requirements.txt' -o -name 'package.json' \
       -o -name 'pyproject.toml' -o -name 'Cargo.toml' -o -name 'go.mod' \) \
       2>/dev/null | head -80
} > "$OUT/filesystem.txt"
LOG "  → filesystem.txt"

# ----------------------------------------------------------------------------
SECTION "3. SERVICES & LISTENING SOCKETS"
{
  echo "# systemd services (running)"
  systemctl list-units --type=service --state=running --no-pager --no-legend 2>/dev/null | awk '{print $1}'
  echo
  echo "# Listening sockets (TCP)"
  ss -tlnp 2>/dev/null
  echo
  echo "# Listening sockets (UDP)"
  ss -ulnp 2>/dev/null
} > "$OUT/services.txt"
LOG "  → services.txt"

# ----------------------------------------------------------------------------
SECTION "4. SOFTWARE INVENTORY"
{
  echo "# Ollama models"
  ollama list 2>/dev/null
  echo
  echo "# Docker containers (all states)"
  docker ps -a --format 'table {{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}\t{{.Names}}' 2>/dev/null
  echo
  echo "# Docker images"
  docker images --format 'table {{.Repository}}:{{.Tag}}\t{{.Size}}\t{{.CreatedSince}}' 2>/dev/null | head -40
  echo
  echo "# Docker volumes"
  docker volume ls 2>/dev/null
  echo
  echo "# Docker networks"
  docker network ls 2>/dev/null
  echo
  echo "# Kubectl contexts"
  kubectl config get-contexts 2>/dev/null
  echo
  echo "# Kubectl current cluster nodes"
  kubectl get nodes -o wide 2>/dev/null
  echo
  echo "# Python (system) top packages"
  pip3 list --break-system-packages 2>/dev/null | head -40
  echo
  echo "# APT installed (count + top categories)"
  apt list --installed 2>/dev/null | wc -l
  echo
  echo "# /opt contents"
  ls -la /opt/ 2>/dev/null
  echo
  echo "# /usr/local/bin custom binaries"
  ls /usr/local/bin/ 2>/dev/null | head -40
} > "$OUT/software.txt"
LOG "  → software.txt"

# ----------------------------------------------------------------------------
SECTION "5. NETWORK (passive)"
{
  echo "# Interfaces"
  ip -br -c addr 2>/dev/null
  echo
  echo "# Routing table"
  ip -4 route 2>/dev/null
  echo
  echo "# IPv6 routes"
  ip -6 route 2>/dev/null | head -20
  echo
  echo "# ARP / neighbor cache (already-known LAN devices)"
  ip neigh 2>/dev/null
  echo
  echo "# DNS resolvers"
  resolvectl status 2>/dev/null | grep -E 'DNS Servers|Current DNS' | head -10
  cat /etc/resolv.conf 2>/dev/null | grep -v '^#' | grep -v '^$'
  echo
  echo "# /etc/hosts custom entries"
  grep -v '^#' /etc/hosts 2>/dev/null | grep -v '^$'
  echo
  echo "# Active connections (top 30)"
  ss -tnp state established 2>/dev/null | head -30
} > "$OUT/network_passive.txt"
LOG "  → network_passive.txt"

# ----------------------------------------------------------------------------
SECTION "6. LAN DEEP SCAN (nmap)"
LAN="192.168.0.0/24"
LOG "  Target LAN: $LAN"

# Stage 1: ping sweep (cheap)
LOG "  Stage 1/3: ICMP ping sweep..."
nmap -sn -n -T4 --max-retries 1 "$LAN" -oG "$OUT/nmap_ping.gnmap" \
     -oN "$OUT/nmap_ping.txt" 2>&1 | tail -5 | tee -a "$OUT/scan.log"

LIVE_HOSTS=$(grep -oP 'Host: \K[\d.]+' "$OUT/nmap_ping.gnmap" 2>/dev/null | sort -u | head -50)
HOST_COUNT=$(echo "$LIVE_HOSTS" | wc -l)
LOG "  Found $HOST_COUNT live host(s)"
echo "$LIVE_HOSTS" > "$OUT/live_hosts.txt"

# Stage 2: top-100 TCP ports + service version detection (no -O since not root)
if [ -n "$LIVE_HOSTS" ]; then
  LOG "  Stage 2/3: nmap top-100 TCP + service version (this takes a few min)..."
  echo "$LIVE_HOSTS" | xargs nmap -sV --version-light -F -T4 \
       --max-retries 2 --host-timeout 60s \
       -oN "$OUT/nmap_services.txt" -oX "$OUT/nmap_services.xml" \
       -oG "$OUT/nmap_services.gnmap" 2>&1 | tail -10 | tee -a "$OUT/scan.log"

  # Stage 3: light vuln-script scan on the most common ports (NSE 'safe' category)
  LOG "  Stage 3/3: NSE safe scripts on common ports..."
  echo "$LIVE_HOSTS" | xargs nmap -sV --script "default,safe and not intrusive" \
       -p 22,80,443,3389,445,139,8080,8443,3000,3030,5432,6379,11434 \
       -T4 --max-retries 1 --host-timeout 90s \
       -oN "$OUT/nmap_safe_scripts.txt" 2>&1 | tail -10 | tee -a "$OUT/scan.log"
else
  LOG "  No live hosts → skipping deep scan"
fi
LOG "  → nmap_*.txt"

# ----------------------------------------------------------------------------
SECTION "7. CLOUD INVENTORY"
mkdir -p "$OUT/cloud"

# AWS
if aws sts get-caller-identity >/dev/null 2>&1; then
  LOG "  AWS: authenticated, enumerating..."
  aws sts get-caller-identity > "$OUT/cloud/aws_identity.json" 2>&1
  aws ec2 describe-regions --query 'Regions[].RegionName' --output text 2>/dev/null > "$OUT/cloud/aws_regions.txt"
  REGION=$(aws configure get region 2>/dev/null || echo us-east-1)
  LOG "    primary region: $REGION"
  aws ec2 describe-instances --region "$REGION" \
      --query 'Reservations[].Instances[].{Id:InstanceId,Type:InstanceType,State:State.Name,Public:PublicIpAddress,Private:PrivateIpAddress,Tags:Tags}' \
      --output json > "$OUT/cloud/aws_ec2.json" 2>&1
  aws s3api list-buckets --query 'Buckets[].Name' --output json > "$OUT/cloud/aws_s3.json" 2>&1
  aws iam list-users --query 'Users[].UserName' --output json > "$OUT/cloud/aws_iam_users.json" 2>&1
  aws lambda list-functions --region "$REGION" --query 'Functions[].FunctionName' --output json > "$OUT/cloud/aws_lambda.json" 2>&1
  aws rds describe-db-instances --region "$REGION" --query 'DBInstances[].DBInstanceIdentifier' --output json > "$OUT/cloud/aws_rds.json" 2>&1
  LOG "    → cloud/aws_*.json"
else
  echo "not authenticated" > "$OUT/cloud/aws_status.txt"
fi

# Azure
if az account show >/dev/null 2>&1; then
  LOG "  Azure: authenticated, enumerating..."
  az account show > "$OUT/cloud/azure_account.json" 2>&1
  az resource list --query '[].{name:name, type:type, rg:resourceGroup, loc:location}' -o json > "$OUT/cloud/azure_resources.json" 2>&1
  az group list --query '[].{name:name, loc:location}' -o json > "$OUT/cloud/azure_rgs.json" 2>&1
else
  echo "not authenticated" > "$OUT/cloud/azure_status.txt"
fi

# GCP (gcloud not installed here — record absence)
echo "gcloud not installed" > "$OUT/cloud/gcp_status.txt"

# ----------------------------------------------------------------------------
SECTION "8. SECRETS / SENSITIVE FILES (light)"
{
  echo "# .env / .envrc / .env.* files in home (top 50)"
  find /home/x -maxdepth 4 -type f \( -name '.env' -o -name '.envrc' -o -name '.env.*' \) 2>/dev/null | head -50
  echo
  echo "# SSH private keys with permissions"
  find /home/x/.ssh ~/.ssh -maxdepth 2 -type f 2>/dev/null \
       -exec stat -c '%a %n' {} \; 2>/dev/null | head -30
  echo
  echo "# Cloud credentials"
  ls -la /home/x/.aws/credentials /home/x/.aws/config 2>/dev/null
  ls -la /home/x/.azure 2>/dev/null | head
  ls -la /home/x/.kube/config 2>/dev/null
  echo
  echo "# Files named *secret*, *token*, *credential* (top 30)"
  find /home/x -maxdepth 4 -type f \
       \( -iname '*secret*' -o -iname '*token*' -o -iname '*credential*' \
          -o -iname '*api_key*' -o -iname '*api-key*' \) 2>/dev/null | head -30
  echo
  echo "# World-readable files containing 'PRIVATE KEY' (top 10)"
  find /home/x -maxdepth 5 -type f -perm -004 2>/dev/null \
       -exec grep -l 'PRIVATE KEY' {} \; 2>/dev/null | head -10
} > "$OUT/secrets_audit.txt"
LOG "  → secrets_audit.txt"

# ----------------------------------------------------------------------------
SECTION "9. SUMMARY"
SUMMARY="$OUT/summary.md"
{
  echo "# AEGIS Asset Recon  ($TS)"
  echo
  echo "Host: \`$(hostname)\`  User: \`$(whoami)\`  Mode: **Deep**"
  echo "Output dir: \`$OUT\`"
  echo
  echo "## Quick stats"
  echo
  echo "| Metric | Value |"
  echo "|---|---|"
  echo "| Distro | $(. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME") |"
  echo "| Kernel | $(uname -r) |"
  echo "| CPU cores | $(nproc) |"
  echo "| Memory total | $(grep MemTotal /proc/meminfo | awk '{printf "%.1f GB",$2/1024/1024}') |"
  echo "| Disk free (/) | $(df -h / | tail -1 | awk '{print $4" / "$2}') |"
  echo "| Listening TCP ports | $(ss -tln 2>/dev/null | tail -n +2 | wc -l) |"
  echo "| Running services | $(systemctl list-units --type=service --state=running --no-legend --no-pager 2>/dev/null | wc -l) |"
  echo "| Docker containers (running) | $(docker ps -q 2>/dev/null | wc -l) |"
  echo "| Docker images | $(docker images -q 2>/dev/null | wc -l) |"
  echo "| Ollama models | $(ollama list 2>/dev/null | tail -n +2 | wc -l) |"
  echo "| Git repos in /home/x | $(find /home/x -maxdepth 3 -type d -name .git 2>/dev/null | wc -l) |"
  echo "| Live LAN hosts ($LAN) | $HOST_COUNT |"
  echo
  echo "## Network exposure (this host's listening ports)"
  echo
  echo '```'
  ss -tln 2>/dev/null | tail -n +2 | awk '{print $4}' | sort -u
  echo '```'
  echo
  echo "## Live LAN hosts"
  echo
  if [ -s "$OUT/live_hosts.txt" ]; then
    echo '```'
    cat "$OUT/live_hosts.txt"
    echo '```'
    echo
    if [ -f "$OUT/nmap_services.gnmap" ]; then
      echo "### Discovered services"
      echo
      echo '```'
      grep -oP 'Host: \K\S+ \(\S*\).*Ports: \K.*?(?=\tIgnored)' "$OUT/nmap_services.gnmap" 2>/dev/null \
        | head -20 || echo "(see nmap_services.txt for full output)"
      echo '```'
    fi
  fi
  echo
  echo "## Cloud accounts"
  echo
  echo "- **AWS:** $([ -f "$OUT/cloud/aws_identity.json" ] && jq -r '.Account // "unknown"' < "$OUT/cloud/aws_identity.json" 2>/dev/null || echo "not authenticated")"
  echo "- **Azure:** $([ -f "$OUT/cloud/azure_account.json" ] && jq -r '.id // "unknown"' < "$OUT/cloud/azure_account.json" 2>/dev/null || echo "not authenticated")"
  echo "- **GCP:** gcloud not installed"
  echo
  echo "## Files in this report"
  echo
  ls -la "$OUT" | tail -n +2 | awk '{print "- `"$NF"`  ("$5" bytes)"}' | grep -v '^- `\.`' | grep -v '^- `\.\.`'
} > "$SUMMARY"

LOG "DONE → $SUMMARY"
echo
cat "$SUMMARY"
