# Deployment: AWS EC2 (Staging)

The same `docker-compose.yml` that runs locally runs on a single EC2 instance.

## 1. Sizing

| Item | Recommendation | Approx. cost (ap-south-1, on-demand) |
|---|---|---|
| Instance | **t3.small** (2 vCPU, 2 GB) + 2 GB swap | ~USD 15 / month |
| Disk | 20 GB gp3 | ~USD 1.9 / month |
| Public IP | 1 IPv4 | ~USD 3.6 / month |
| Cost Explorer API | ~2 requests / day | ~USD 0.60 / month |
| **Total** | | **≈ USD 21 / month** (≈ ₹1,770) |

Stop the instance outside demo hours to cut compute cost by about 65 %. See [cost-optimization.md](cost-optimization.md).

## 2. Create the instance

### Option A: script (AWS CLI)

```bash
aws configure                                  # once
KEY_NAME=my-keypair AWS_REGION=ap-south-1 ./deploy/aws/create-ec2.sh
```

The script creates:
- Security group `cloudlens-staging-sg`: **SSH 22 from your current IP only**, HTTP 80 from anywhere
- IAM role + instance profile with the read-only `deploy/aws/iam-policy.json` (Cost Explorer, EC2, RDS, CloudWatch)
- A t3.small Amazon Linux 2023 instance with IMDSv2 required, a 20 GB gp3 disk, tags `environment=staging`, `project=cloudlens`
- User data (`deploy/aws/ec2-user-data.sh`) that installs Docker and the Compose plugin and adds swap

### Option B: console

1. EC2 → Launch instance → Amazon Linux 2023, t3.small, your key pair.
2. Security group: inbound 22 (My IP) and 80 (0.0.0.0/0).
3. Advanced → IAM instance profile: a role with `deploy/aws/iam-policy.json`.
4. Advanced → User data: paste `deploy/aws/ec2-user-data.sh`.

## 3. Prepare the staging environment file

```bash
cp .env.example .env.staging
```

Edit `.env.staging`:

```
APP_ENV=staging
HTTP_PORT=80
DASHBOARD_PUBLIC_URL=http://<EC2_PUBLIC_IP>
CORS_ORIGINS=http://<EC2_PUBLIC_IP>
POSTGRES_PASSWORD=<strong>
JWT_SECRET=<openssl rand -hex 32>
ADMIN_PASSWORD=<strong>
ALERTMANAGER_WEBHOOK_TOKEN=<openssl rand -hex 16>
```

## 4. Deploy

```bash
EC2_HOST=<public-ip> SSH_KEY=~/.ssh/my-keypair.pem ./deploy/aws/deploy.sh
```

`deploy.sh` rsyncs the project to `/opt/cloudlens`, uploads `.env.staging` as `.env` (and
runs `docker compose up -d --build`, prunes old images, and waits
for `/health`. The first build takes about 5–8 minutes on a t3.small.

Open `http://<public-ip>/`.

## 5. Operate

```bash
ssh -i key.pem ec2-user@<ip>
cd /opt/cloudlens
docker compose ps
docker compose logs -f backend
./scripts/backup_db.sh                 # database dump into backups/
docker compose pull && docker compose up -d   # update base images
```

Reach Prometheus and Alertmanager (bound to localhost) through an SSH tunnel:

```bash
ssh -i key.pem -L 9090:localhost:9090 -L 9093:localhost:9093 ec2-user@<ip>
# then open http://localhost:9090 and http://localhost:9093
```

## 6. Updating

Re-run `deploy.sh` after code changes; only changed images are rebuilt. Data persists in the Docker
volumes `pgdata`, `promdata` and `amdata`.

## 7. Hardening checklist (before production)

- [ ] Put the instance behind HTTPS: an ALB with an ACM certificate, or Caddy/Certbot in front of nginx
- [ ] Remove the `/mock-inbox/` block from `frontend/nginx.conf` and the `mock-receiver` service
- [ ] Rotate the default passwords and `JWT_SECRET`
- [ ] Enable automated EBS snapshots (Data Lifecycle Manager) or schedule `scripts/backup_db.sh` with cron
- [ ] Restrict port 80/443 to the corporate IP range if the dashboard is internal
- [ ] Set up a CloudWatch alarm on instance status checks

## 8. Staging test checklist

| Check | How | Expected |
|---|---|---|
| Health | `curl http://<ip>/health` | `{"status":"ok","database":true}` |
| Login | Browser | Dashboard loads with data |
| RBAC | Sign in as viewer | No Cloud Accounts / Users menu; no *New rule* |
| Sync | Cloud Accounts → Sync now | New success rows in Sync history |
| Alert | Inject spike → wait 2 min | Message in Slack / Teams / mock inbox |
| Date range | Date button → *Last 6 months*; then type a future *To* date | Data for six months; future date shows an error and Apply stays disabled |
| Restart | `docker compose restart` | Data and rules preserved |

After deploying, connect real accounts on the **Cloud Accounts** screen and choose *EC2 instance role* to use the instance's role, so no keys are stored. Save Slack and Teams webhook URLs in **Settings**. See [live-cloud-setup.md](live-cloud-setup.md).
