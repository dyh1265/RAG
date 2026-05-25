# Deploy DocuMind as a public demo (always-on)

Paths for an always-on URL without your laptop:

| Path | Best for | Monthly cost |
|------|----------|--------------|
| **[B. Split cloud](#b-split-cloud-qdrant--upstash--fly--vercel)** | **Oracle full / no VM** | $0–5 (+ OpenAI) |
| **[C. Cloudflare Tunnel](#c-cloudflare-tunnel-local-docker)** | Quick demo, PC stays on | $0 (+ OpenAI) |
| **[D. Trial VM credits](#d-trial-vm-credits-gcp--azure)** | Full `docker compose`, 90 days | $0 trial (+ OpenAI) |
| **[A. Oracle Always Free VM](#a-oracle-always-free-vm)** | Full stack when capacity exists | $0 (+ OpenAI) |

All paths run **CPU / text-only** (`USE_COLPALI=false`). GPU ColPali is not on free tiers.

---

## Oracle out of capacity?

Ampere A1 instances (`VM.Standard.A1.Flex`) are often **“Out of host capacity”** in popular regions. That is normal.

**Do this instead (in order):**

1. **[Split cloud (B)](#b-split-cloud-qdrant--upstash--fly--vercel)** — most reliable $0 path today; `deploy/fly.toml` included.
2. **[Cloudflare Tunnel (C)](#c-cloudflare-tunnel-local-docker)** — run Docker on your PC; share a stable URL (5 min setup).
3. **[GCP / Azure trial VM (D)](#d-trial-vm-credits-gcp--azure)** — full stack for ~90 days.
4. **Oracle retries** — different region (e.g. `sa-saopaulo-1`, `ap-tokyo-1`) or off-peak hours (often 2–6 AM local); AMD `E2.1.Micro` (1 GB) is **too small** for this stack.
5. **Cheap VPS** — [Hetzner CX22](https://www.hetzner.com/cloud) ~€4/mo; then use [`bootstrap-oracle.sh`](bootstrap-oracle.sh) on any Ubuntu VM.

---

## B. Split cloud (Qdrant + Upstash + Fly + Vercel)

**Use this when Oracle is occupied.** Managed DB/cache + hosted API + static frontend.

### Architecture

```
Browser → Vercel (React) → Fly.io (rag-api) → Qdrant Cloud + Upstash Redis
```

### 1. Qdrant Cloud (free ~1 GB)

1. [cloud.qdrant.io](https://cloud.qdrant.io/) → create free cluster.
2. Copy cluster **URL** and **API key**.

### 2. Upstash Redis (free)

1. [upstash.com](https://upstash.com/) → create Redis database.
2. Copy the **TLS** URL (`rediss://…`).

### 3. Fly.io — rag-api

Install [flyctl](https://fly.io/docs/hands-on/install-flyctl/), sign up, then from **repo root**:

```bash
fly auth login
fly apps create documind-rag-api   # or pick another name; edit deploy/fly.toml
fly secrets set \
  OPENAI_API_KEY=sk-... \
  QDRANT_URL=https://YOUR.cluster.cloud.qdrant.io \
  QDRANT_API_KEY=... \
  REDIS_URL=rediss://default:...@....upstash.io:6379 \
  CELERY_BROKER_URL=rediss://default:...@....upstash.io:6379
fly deploy --config deploy/fly.toml
```

Note the app URL: `https://documind-rag-api.fly.dev`

**Memory:** PyTorch + embeddings need **≥ 2 GB**. Fly’s free allowance may not cover that; expect **~$3–5/mo** for a 2 GB machine. Set billing alerts in Fly.

**Ephemeral disk:** uploaded PDFs live on the Fly VM disk until the machine is replaced — fine for a short demo.

### 4. Vercel — frontend

1. Import the repo at [vercel.com](https://vercel.com).
2. Set **Root Directory** to `frontend`.
3. Environment variable:

| Variable | Value |
|----------|--------|
| `VITE_RAG_API_URL` | `https://documind-rag-api.fly.dev` |

4. Deploy. Open the Vercel URL → upload PDF → chat.

CORS on the API is already `allow_origins=["*"]`.

### Split-cloud checklist

- [ ] Qdrant cluster up; URL + API key in Fly secrets
- [ ] Upstash `rediss://` URL in both `REDIS_URL` and `CELERY_BROKER_URL`
- [ ] Fly deploy succeeds; `https://YOUR.app.fly.dev/health` returns OK
- [ ] Vercel `VITE_RAG_API_URL` matches Fly URL (redeploy after changing)
- [ ] End-to-end: upload PDF → query → citations

---

## C. Cloudflare Tunnel (local Docker)

**Fastest free demo** if your Windows machine can stay on during the demo.

```powershell
# Terminal 1 — start stack locally (UI + /api on http://localhost)
cd docker
docker compose --profile production up -d --build
```

Install [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/), then run from a new terminal:

```
"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel --url http://localhost:80
```

Cloudflare prints a public `https://….trycloudflare.com` URL. Share that link.

**Pros:** no cloud signup beyond Cloudflare, full stack works.  
**Cons:** demo dies when your PC sleeps or Docker stops.

---

## D. Trial VM credits (GCP / Azure)

If you want full `docker compose` without Oracle:

| Provider | Offer | VM suggestion |
|----------|-------|---------------|
| [Google Cloud](https://cloud.google.com/free) | $300 / 90 days for new accounts | `e2-medium` (2 vCPU, 4 GB) |
| [Azure](https://azure.microsoft.com/free) | $200 credit / 30 days | `B2s` (2 vCPU, 4 GB) |

Create Ubuntu 22.04, open ports 22 + 80, then run the same steps as Oracle:

```bash
bash deploy/bootstrap-oracle.sh
```

Works on any Ubuntu VM — the script is not Oracle-specific.

---

## A. Oracle Always Free VM

Runs the same stack as local production: **Qdrant + Redis + rag-api + DocuMind Web**, with only port **80** public.

### 1. Create the VM

1. Sign up at [Oracle Cloud](https://www.oracle.com/cloud/free/) (credit card for verification; Always Free resources stay $0).
2. **Compute → Instances → Create instance**
   - **Shape:** Ampere `VM.Standard.A1.Flex` — **4 OCPUs, 24 GB RAM** (Always Free cap)
   - **Image:** Ubuntu 22.04 or 24.04 (aarch64)
   - **Boot volume:** 50–100 GB
   - **SSH key:** add your public key
3. **Networking → Security list → Ingress rules** — add:
   - `0.0.0.0/0` → **TCP 22** (SSH; restrict to your IP if possible)
   - `0.0.0.0/0` → **TCP 80** (demo UI)
   - Optional later: **TCP 443** for HTTPS
4. Note the instance **public IP**.

Also open the **Ubuntu firewall** if enabled:

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo netfilter-persistent save 2>/dev/null || true
```

### 2. Clone and configure

SSH in:

```bash
ssh ubuntu@YOUR_PUBLIC_IP
```

```bash
sudo apt-get update && sudo apt-get install -y git
git clone https://github.com/dyh1265/RAG.git ~/RAG   # or scp your local copy
cd ~/RAG
cp deploy/.env.demo.example .env
nano .env   # set OPENAI_API_KEY=sk-...
```

### 3. Start the demo stack

```bash
bash deploy/bootstrap-oracle.sh
```

Or manually:

```bash
cd ~/RAG/docker
docker compose --profile production up -d --build
```

**First start:** Docker builds the API image and downloads embedding models (~15–30 min on ARM). The API warms models on boot (`API_WARMUP_MODELS=true`).

### 4. Verify

| Check | URL |
|-------|-----|
| Web UI | `http://YOUR_PUBLIC_IP/` |
| API health (SSH tunnel only) | `http://127.0.0.1:8002/health` |
| Qdrant dashboard (SSH tunnel only) | `http://127.0.0.1:6333/dashboard` |

Upload a PDF in the UI, wait for ingest, then chat.

### 5. Optional: HTTPS with a domain

Point `demo.yourdomain.com` A-record → VM public IP, then add Caddy in front:

```bash
# Example: install Caddy on the host and reverse-proxy to localhost:80
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy
```

`/etc/caddy/Caddyfile`:

```
demo.yourdomain.com {
    reverse_proxy localhost:80
}
```

Override the `documind-web` port mapping so Caddy can bind `:443` itself. The compose file reads `DOCUMIND_WEB_PORT`, default `80:80`:

```bash
DOCUMIND_WEB_PORT=127.0.0.1:8080:80 docker compose --profile production up -d
```

Persist that override by exporting `DOCUMIND_WEB_PORT` in your shell profile or putting it in `.env` (compose reads `.env` automatically).

### 6. Operations

```bash
cd ~/RAG/docker

# Logs
docker compose logs -f rag-api documind-web

# Restart after .env change
docker compose --profile production up -d --build rag-api

# Stop demo
docker compose --profile production down
```

### Security notes (public demo)

- `docker/docker-compose.yml` binds Qdrant, Redis, and rag-api to **127.0.0.1** by default.
- Only the `documind-web` container is exposed publicly (port 80 → SPA + `/api` proxy).
- Do **not** open ports 6333, 6379, or 8002 in Oracle ingress.
- Rotate `OPENAI_API_KEY` if the demo is abused; set Oracle billing alerts.
- PII redaction is on by default in production compose.

### 7. Teardown / cleanup

**Cloudflare Tunnel (Windows):**

```powershell
# Stop the tunnel: Ctrl-C in the cloudflared window, or
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process

# Stop Docker stack but keep volumes (Qdrant data, model cache survive)
cd C:\path\to\RAG\docker
docker compose --profile production --profile dev down

# Drop legacy/orphan services from previous compose versions (e.g. rag_nginx)
docker compose --profile production --profile dev down --remove-orphans

# Full reset — wipes ingested chunks, embeddings, model cache, dashboards
docker compose --profile production --profile dev down -v --remove-orphans
```

**Oracle / VM:**

```bash
cd ~/RAG/docker

docker compose --profile production down                    # stop demo, keep data
docker compose --profile production down --remove-orphans   # drop legacy services
docker compose --profile production down -v --remove-orphans  # full reset

# Reclaim disk on small VMs (build cache, dangling images)
docker system prune -f
docker builder prune -f
```

**Split cloud (Fly + Qdrant Cloud + Upstash + Vercel):**

```bash
# Tear down the Fly app (stops billing on rag-api machine)
fly apps destroy documind-rag-api

# Optional: Vercel project, Qdrant cluster, Upstash DB — delete from each console.
```

**Free the host:**

- **Cloudflared service** (if installed): `cloudflared service uninstall` (Linux/macOS) or use the Windows installer.
- **Caddy + TLS certificates** (Oracle path 5): `sudo systemctl stop caddy && sudo apt remove caddy`. Issued certs live under `/var/lib/caddy/.local/share/caddy/`.
- **Oracle VM:** terminate the instance from the Oracle Cloud console; the boot volume goes with it (Always Free → no charge).

| Volume | Holds | Wiped by `down -v`? |
|---|---|---|
| `qdrant_data` | All ingested chunks + embeddings | yes |
| `redis_data` | Embedding cache + Celery queue | yes |
| `huggingface_cache` | Embedding/reranker models (~3 GB) | yes (re-downloads next start) |
| `prometheus_data`, `grafana_data` | Metrics + dashboards | yes |

---

## Which path should you pick?

| | Split cloud | Cloudflare Tunnel | Trial VM | Oracle VM |
|---|-------------|-------------------|----------|-----------|
| Oracle full? | **Works** | **Works** | **Works** | Often blocked |
| Always-on | Yes (if Fly paid ~$5) | Only while PC runs | Yes (trial period) | Yes |
| Setup time | ~1–2 h | ~10 min | ~1 h | ~1 h |
| Full local parity | Partial | **Yes** | **Yes** | **Yes** |

**Today:** use **split cloud (B)** or **Cloudflare Tunnel (C)**.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| UI loads, API errors | `docker logs rag_api`; check `OPENAI_API_KEY` |
| Oracle “Out of host capacity” | Use [split cloud (B)](#b-split-cloud-qdrant--upstash--fly--vercel) or [Cloudflare Tunnel (C)](#c-cloudflare-tunnel-local-docker) |
| OOM during build | Ensure 4 GB swap (`bootstrap-oracle.sh` adds it) |
| Ingest very slow | Expected on CPU; use small PDFs for demo |
| `ready` never true | First model download; wait or check disk space |

See also the **Quickstart** section in [`../README.md`](../README.md) — the same `docker compose --profile production up -d --build` command is used for local, Cloudflare Tunnel, and VM deployments.
