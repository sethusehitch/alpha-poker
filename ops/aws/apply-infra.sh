#!/bin/bash
set -euo pipefail
umask 077

project_dir=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
terraform_dir="$project_dir/infra/aws/lightsail"
aws_profile=${AWS_PROFILE:-hitch-personal}
aws_region=${AWS_REGION:-us-west-2}
ssh_key_file=${ALPHA_POKER_SSH_KEY_FILE:-$HOME/.ssh/alpha-poker-lightsail}

install -d -m 700 "$(dirname "$ssh_key_file")"
if [ ! -f "$ssh_key_file" ]; then
  ssh-keygen -q -t ed25519 -N '' -C alpha-poker-lightsail -f "$ssh_key_file"
fi
if [ ! -f "$ssh_key_file.pub" ]; then
  ssh-keygen -y -f "$ssh_key_file" > "$ssh_key_file.pub"
fi
chmod 600 "$ssh_key_file"
chmod 644 "$ssh_key_file.pub"
ssh_public_key=$(tr -d '\r\n' < "$ssh_key_file.pub")

public_ip=$(curl --fail --silent --show-error --max-time 10 https://checkip.amazonaws.com | tr -d '[:space:]')
if [[ ! $public_ip =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "Could not determine a valid public IPv4 address for restricted SSH access." >&2
  exit 1
fi

terraform -chdir="$terraform_dir" init
terraform -chdir="$terraform_dir" validate
terraform -chdir="$terraform_dir" plan \
  -out=alpha-poker.tfplan \
  -var="aws_profile=$aws_profile" \
  -var="aws_region=$aws_region" \
  -var="admin_cidr=$public_ip/32" \
  -var="admin_ssh_public_key=$ssh_public_key"
terraform -chdir="$terraform_dir" apply alpha-poker.tfplan

terraform -chdir="$terraform_dir" output
