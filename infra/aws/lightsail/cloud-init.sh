#!/bin/sh
set -eu

install -d -m 700 -o ubuntu -g ubuntu /home/ubuntu/.ssh
touch /home/ubuntu/.ssh/authorized_keys
if ! grep -qxF '${admin_ssh_public_key}' /home/ubuntu/.ssh/authorized_keys; then
  printf '%s\n' '${admin_ssh_public_key}' >> /home/ubuntu/.ssh/authorized_keys
fi
chown ubuntu:ubuntu /home/ubuntu/.ssh/authorized_keys
chmod 600 /home/ubuntu/.ssh/authorized_keys

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y ca-certificates curl docker.io docker-compose-v2 openssl unattended-upgrades
systemctl enable --now docker
usermod -aG docker ubuntu

if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

install -d -o ubuntu -g ubuntu /opt/alpha-poker/releases /opt/alpha-poker/shared
touch /var/lib/cloud/instance/alpha-poker-ready
