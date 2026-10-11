#!/usr/bin/env bash
# One-time admin operation. Review and run on the VPS, never from a CI upload.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
key_file=${1:?Pass a file containing the deployment PUBLIC key}
script_dir=$(cd -- "$(dirname -- "$0")" && pwd)
[[ -L /srv/aether-sky/current && -f /srv/aether-sky/current/public/blog/index.html && -f /etc/caddy/aether-sky.env ]] || {
  echo 'Activate the first static release using docs/vps-deployment.md first.' >&2; exit 1;
}
[[ $(wc -l < "$key_file") -eq 1 ]] || { echo 'Expected one public key line.' >&2; exit 1; }
read -r key_type key_data key_comment < "$key_file"
[[ $key_type == ssh-ed25519 && $key_data =~ ^[A-Za-z0-9+/]+={0,3}$ ]] || exit 1
ssh-keygen -l -f "$key_file" >/dev/null
command -v python3 >/dev/null || { echo 'Install python3 first: apt install python3' >&2; exit 1; }
id site-deploy >/dev/null 2>&1 || useradd --create-home --shell /bin/sh site-deploy
# A shell is required by sshd to launch the forced command, but no shell command is accepted.
install -o root -g root -m 0755 "$script_dir/receive.py" /usr/local/bin/site-receive
install -d -o root -g root -m 0755 /home/site-deploy /home/site-deploy/.ssh
printf 'restrict,command="/usr/local/bin/site-receive" %s %s\n' "$key_type" "$key_data" > /home/site-deploy/.ssh/authorized_keys
chown root:root /home/site-deploy/.ssh/authorized_keys
chmod 0644 /home/site-deploy/.ssh/authorized_keys
# Only the release directories and pointers are writable. No sudo, Caddy config, or blog source access.
chown site-deploy:site-deploy /srv/aether-sky /srv/aether-sky/releases
chmod 0755 /srv/aether-sky /srv/aether-sky/releases
echo 'CI upload account installed. Keep the receiver root-owned and review changes before reinstalling it.'
