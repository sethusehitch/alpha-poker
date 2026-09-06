#!/bin/bash
set -euo pipefail

project_dir=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
terraform_dir="$project_dir/infra/aws/lightsail"
aws_profile=${AWS_PROFILE:-default}
aws_region=${AWS_REGION:-us-west-2}
ssh_key_file=${ALPHA_POKER_SSH_KEY_FILE:-$HOME/.ssh/alpha-poker-lightsail}
instance_name=$(terraform -chdir="$terraform_dir" output -raw instance_name)
public_ip=$(terraform -chdir="$terraform_dir" output -raw public_ip)
site_url=$(terraform -chdir="$terraform_dir" output -raw site_url)
primary_hostname=$(terraform -chdir="$terraform_dir" output -raw primary_hostname)
www_hostname=$(terraform -chdir="$terraform_dir" output -raw www_hostname)
temporary_hostname=$(terraform -chdir="$terraform_dir" output -raw temporary_hostname)
temporary_site_url="https://$temporary_hostname"
release_id=$(date -u +%Y%m%d%H%M%S)
temporary_dir=$(mktemp -d)
archive_file="$temporary_dir/alpha-poker-release.tgz"
known_hosts_file="$temporary_dir/known_hosts"
trap 'rm -rf "$temporary_dir"' EXIT HUP INT TERM
umask 077

if [ ! -f "$ssh_key_file" ]; then
  echo "SSH key not found at $ssh_key_file. Run ops/aws/apply-infra.sh first." >&2
  exit 1
fi

COPYFILE_DISABLE=1 tar -C "$project_dir" -czf "$archive_file" \
  --exclude=.git \
  --exclude=.env \
  --exclude=.next \
  --exclude=.terraform \
  --exclude=.venv \
  --exclude=.vinext \
  --exclude=.wrangler \
  --exclude='*.tfplan' \
  --exclude='*.tfstate*' \
  --exclude='__pycache__' \
  --exclude=data \
  --exclude=dist \
  --exclude=node_modules \
  .

ssh_options=(
  -i "$ssh_key_file"
  -o IdentitiesOnly=yes
  -o "UserKnownHostsFile=$known_hosts_file"
  -o StrictHostKeyChecking=accept-new
  -o ConnectTimeout=10
)

for attempt in {1..60}; do
  if ssh "${ssh_options[@]}" "ubuntu@$public_ip" true; then
    break
  fi
  printf 'Waiting for SSH access (%s/60)\n' "$attempt"
  sleep 5
done
ssh "${ssh_options[@]}" "ubuntu@$public_ip" \
  "cloud-init status --wait || test -f /var/lib/cloud/instance/alpha-poker-ready"
scp "${ssh_options[@]}" "$archive_file" "ubuntu@$public_ip:/tmp/alpha-poker-release.tgz"

ssh "${ssh_options[@]}" "ubuntu@$public_ip" \
  "sudo bash -s -- '$release_id' '$primary_hostname' '$www_hostname' '$temporary_hostname'" <<'REMOTE_SCRIPT'
set -euo pipefail
release_id=$1
primary_hostname=$2
www_hostname=$3
temporary_hostname=$4
app_root=/opt/alpha-poker
release_dir="$app_root/releases/$release_id"

install -d -o ubuntu -g ubuntu "$release_dir" "$app_root/shared"
tar --warning=no-unknown-keyword -xzf /tmp/alpha-poker-release.tgz -C "$release_dir"
rm -f /tmp/alpha-poker-release.tgz

if [ ! -f "$app_root/shared/.env" ]; then
  invite_code=$(openssl rand -hex 16)
  operator_token=$(openssl rand -hex 32)
  umask 077
  {
    printf 'ALPHA_POKER_PRIMARY_HOSTNAME=%s\n' "$primary_hostname"
    printf 'ALPHA_POKER_WWW_HOSTNAME=%s\n' "$www_hostname"
    printf 'ALPHA_POKER_TEMPORARY_HOSTNAME=%s\n' "$temporary_hostname"
    printf 'ALPHA_POKER_AUTO_RUN=true\n'
    printf 'ALPHA_POKER_AUTO_RUN_HANDS=200\n'
    printf 'ALPHA_POKER_RETAINED_HAND_RUNS=2\n'
    printf 'ALPHA_POKER_RETAINED_ARTIFACT_RUNS=30\n'
    printf 'ALPHA_POKER_INVITE_CODE=%s\n' "$invite_code"
    printf 'ALPHA_POKER_OPERATOR_TOKEN=%s\n' "$operator_token"
    printf 'LOG_LEVEL=info\n'
  } > "$app_root/shared/.env"
  chown ubuntu:ubuntu "$app_root/shared/.env"
  chmod 600 "$app_root/shared/.env"
else
  sed -i '/^ALPHA_POKER_HOSTNAME=/d;/^ALPHA_POKER_PRIMARY_HOSTNAME=/d;/^ALPHA_POKER_WWW_HOSTNAME=/d;/^ALPHA_POKER_TEMPORARY_HOSTNAME=/d' "$app_root/shared/.env"
  {
    printf 'ALPHA_POKER_PRIMARY_HOSTNAME=%s\n' "$primary_hostname"
    printf 'ALPHA_POKER_WWW_HOSTNAME=%s\n' "$www_hostname"
    printf 'ALPHA_POKER_TEMPORARY_HOSTNAME=%s\n' "$temporary_hostname"
  } >> "$app_root/shared/.env"
fi

ln -s "$app_root/shared/.env" "$release_dir/.env"
chown -R ubuntu:ubuntu "$release_dir"

# Take a transactionally consistent SQLite backup from the running API before
# switching releases. The backup lives with the persistent data volume and is
# bounded to the ten newest pre-deploy snapshots.
if [ -f "$app_root/current/compose.aws.yaml" ]; then
  cd "$app_root/current"
  if docker compose -f compose.aws.yaml --env-file "$app_root/shared/.env" ps --status running -q api | grep -q .; then
    docker compose -f compose.aws.yaml --env-file "$app_root/shared/.env" exec -T \
      -e "ALPHA_POKER_BACKUP_ID=$release_id" api python -c '
import os
import sqlite3
from pathlib import Path

backup_dir = Path("/data/backups")
backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
backup_id = os.environ["ALPHA_POKER_BACKUP_ID"]
destination = backup_dir / f"pre-deploy-{backup_id}.sqlite3"
with sqlite3.connect("/data/alpha-poker.sqlite3") as source, sqlite3.connect(destination) as target:
    source.backup(target)
destination.chmod(0o600)
backups = sorted(backup_dir.glob("pre-deploy-*.sqlite3"), key=lambda item: item.stat().st_mtime, reverse=True)
for expired in backups[10:]:
    expired.unlink()
'
  fi
fi

ln -sfn "$release_dir" "$app_root/current.next"
mv -Tf "$app_root/current.next" "$app_root/current"

cd "$app_root/current"
# Release directories are immutable and `current` is a symlink. Recreate every
# service so bind mounts such as Caddyfile.aws follow the new release rather
# than remaining attached to the previous symlink target.
docker compose -f compose.aws.yaml --env-file "$app_root/shared/.env" up --build --detach --wait --force-recreate

mapfile -t old_releases < <(find "$app_root/releases" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' | sort -rn | tail -n +4 | cut -d' ' -f2-)
for old_release in "${old_releases[@]}"; do
  case "$old_release" in
    "$app_root/releases/"*) rm -rf -- "$old_release" ;;
  esac
done
REMOTE_SCRIPT

invite_code=$(ssh "${ssh_options[@]}" "ubuntu@$public_ip" \
  "sudo awk -F= '/^ALPHA_POKER_INVITE_CODE=/{print \$2}' /opt/alpha-poker/shared/.env")
for attempt in {1..60}; do
  if curl --fail --silent --show-error --max-time 10 "$temporary_site_url/ops/healthz" >/dev/null; then
    break
  fi
  if [ "$attempt" -eq 60 ]; then
    echo "Timed out waiting for HTTPS at $temporary_site_url" >&2
    exit 1
  fi
  printf 'Waiting for HTTPS (%s/60)\n' "$attempt"
  sleep 5
done
ALPHA_POKER_INVITE_CODE="$invite_code" ALPHA_POKER_BASE_URL="$temporary_site_url" "$project_dir/ops/smoke.sh"
if curl --fail --silent --show-error --max-time 10 "$site_url/ops/healthz" >/dev/null 2>&1; then
  ALPHA_POKER_INVITE_CODE="$invite_code" ALPHA_POKER_BASE_URL="$site_url" "$project_dir/ops/smoke.sh"
  printf 'Alpha Poker deployed to %s\n' "$site_url"
else
  printf 'Alpha Poker deployed at %s; %s is waiting for DNS delegation and HTTPS.\n' "$temporary_site_url" "$site_url"
fi
