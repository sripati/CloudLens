# Deployment: VPS with a Domain (Live Site)

CloudLens is live at **https://cloudlens.auraaum.com**. It runs the same `docker-compose.yml` as a laptop, on a
Hostinger VPS, with Caddy on the host for HTTPS.

```
Browser ──https :443──▶ Caddy (host) ──http──▶ 127.0.0.1:8080 (frontend nginx) ──▶ backend, Prometheus, ...
```

Caddy is the only service on the public ports 80 and 443. It gets and renews a free Let's Encrypt certificate and
redirects `http://` to `https://`. CloudLens itself listens on localhost only.

## 1. Server

| Item | Live site |
|---|---|
| Provider | Hostinger VPS |
| OS | Ubuntu 24.04 |
| Size | 1 vCPU, 4 GB RAM, plus 2 GB swap |
| Disk | at least 20 GB |

On 1 vCPU the first `docker compose up -d --build` takes noticeably longer than the 5–8 minutes on a t3.small.

## 2. DNS

At the domain's DNS provider (Hostinger hPanel → Domains → DNS records), add an **A** record: name `cloudlens`,
value the VPS IP, TTL 300. Check with `dig +short cloudlens.auraaum.com`.

## 3. Prepare the server

```bash
ssh root@VPS_IP
apt update && apt upgrade -y

# 2 GB swap
fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# firewall (also allow 22/80/443 in the Hostinger firewall if it is enabled)
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw --enable

# Docker and Caddy
curl -fsSL https://get.docker.com | sh
apt install -y caddy
```

## 4. Install CloudLens

```bash
git clone https://github.com/sripati/CloudLens.git /opt/cloudlens
cd /opt/cloudlens
cp .env.example .env
```

Edit `.env`. Generate new secrets with `openssl rand -hex 32`; never reuse the values in `.env.example`.

```
APP_ENV=production
HTTP_PORT=127.0.0.1:8080
CORS_ORIGINS=https://cloudlens.auraaum.com
DASHBOARD_PUBLIC_URL=https://cloudlens.auraaum.com
POSTGRES_PASSWORD=<strong>
JWT_SECRET=<openssl rand -hex 32>
ALERTMANAGER_WEBHOOK_TOKEN=<openssl rand -hex 32>
ADMIN_EMAIL=<admin email>
ADMIN_PASSWORD=<strong>
VIEWER_PASSWORD=<strong>
```

`HTTP_PORT=127.0.0.1:8080` matters: Docker-published ports bypass `ufw`, so binding to localhost is what keeps the
app reachable only through Caddy. The admin and viewer passwords apply only on the first start.

```bash
docker compose up -d --build
docker compose ps                        # all six containers up / healthy
curl http://127.0.0.1:8080/health        # {"status":"ok","database":true,...}
```

## 5. HTTPS with Caddy

`/etc/caddy/Caddyfile`:

```
cloudlens.auraaum.com {
    reverse_proxy 127.0.0.1:8080
}
```

```bash
systemctl reload caddy
journalctl -u caddy -n 50 --no-pager     # "certificate obtained successfully"
```

## 6. After the first sign-in

- **Cloud Accounts:** connect AWS with an access key for the read-only policy in `deploy/aws/iam-policy.json`.
  *EC2 instance role* works only on AWS servers.
- **Settings:** save the Slack and Teams webhook URLs.
- Only one copy should be Live on the same AWS account, or both copies call the paid Cost Explorer API.

## 7. Operate

```bash
cd /opt/cloudlens
docker compose ps
docker compose logs -f backend
git pull && docker compose up -d --build      # update after pushing changes
```

Nightly backup (`crontab -e`); copy the dumps off the server from time to time:

```
0 3 * * * cd /opt/cloudlens && ./scripts/backup_db.sh >> /var/log/cloudlens-backup.log 2>&1
```

Prometheus and Alertmanager are bound to localhost. Reach them through an SSH tunnel:

```bash
ssh -L 9090:localhost:9090 -L 9093:localhost:9093 -L 9000:localhost:9000 root@VPS_IP
# then open http://localhost:9090, http://localhost:9093 and the test inbox at http://localhost:9000
```

## 8. Public-site checklist

- [ ] Consider limiting `/docs`, `/redoc` and `/openapi.json` in `frontend/nginx.conf`. They need no login to read.
- [ ] Change the default passwords if `.env` kept them.
- [ ] Schedule backups and keep a copy off the VPS.

## 9. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Caddy cannot get a certificate | DNS not pointing at the VPS yet, or 80/443 blocked in `ufw` or the Hostinger firewall |
| 502 Bad Gateway | Containers not running: `docker compose ps`, `docker compose logs backend` |
| Login works but API calls fail | `CORS_ORIGINS` / `DASHBOARD_PUBLIC_URL` must be exactly `https://cloudlens.auraaum.com` |
| Very slow first build | Normal on 1 vCPU; check swap with `free -h` |
