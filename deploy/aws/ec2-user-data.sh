#!/bin/bash
# EC2 bootstrap for Amazon Linux 2023 / Ubuntu 22.04+.
# Paste into "User data" when launching the instance (or run once with sudo).
# Installs Docker + Compose plugin, adds 2 GB swap (lets a t3.small build images safely).
set -euxo pipefail

if command -v dnf >/dev/null 2>&1; then
  dnf update -y
  dnf install -y docker git
  mkdir -p /usr/local/lib/docker/cli-plugins
  ARCH=$(uname -m)
  curl -fsSL "https://github.com/docker/compose/releases/download/v2.32.1/docker-compose-linux-${ARCH}" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
  chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
  DEFAULT_USER=ec2-user
else
  apt-get update -y
  apt-get install -y ca-certificates curl git
  curl -fsSL https://get.docker.com | sh
  DEFAULT_USER=ubuntu
fi

systemctl enable --now docker
usermod -aG docker "$DEFAULT_USER"

# swap file (2 GB) - avoids OOM during "docker compose build" on small instances
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

mkdir -p /opt/cloudlens
chown "$DEFAULT_USER":"$DEFAULT_USER" /opt/cloudlens
echo "Bootstrap complete. Copy the project to /opt/cloudlens and run deploy/aws/deploy.sh" > /etc/motd
