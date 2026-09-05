#!/bin/bash
set -euo pipefail

project_dir=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
terraform_dir="$project_dir/infra/aws/lightsail"
ssh_key_file=${ALPHA_POKER_SSH_KEY_FILE:-$HOME/.ssh/alpha-poker-lightsail}
public_ip=$(terraform -chdir="$terraform_dir" output -raw public_ip)
ssh -i "$ssh_key_file" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new "ubuntu@$public_ip" \
  "sudo awk -F= '/^(ALPHA_POKER_INVITE_CODE|ALPHA_POKER_OPERATOR_TOKEN)=/{print}' /opt/alpha-poker/shared/.env"
