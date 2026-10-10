#!/usr/bin/env bash
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
exec 9>/run/aether-sky-deploy.lock
flock -n 9 || exit 1
base=/srv/aether-sky
read -r previous < "$base/previous"
[[ $previous == "$base/releases/"* && -d $previous/public ]] || exit 1
read -r domain < "$previous/DOMAIN"
SITE_ADDRESS="$domain" SITE_ROOT="$previous/public" caddy validate --config "$previous/deploy/Caddyfile" --adapter caddyfile
current=$(readlink -f "$base/current")
ln -s "$previous" "$base/current.next"
mv -Tf "$base/current.next" "$base/current"
install -m 644 "$previous/deploy/Caddyfile" /etc/caddy/Caddyfile
systemctl reload caddy
printf '%s\n' "$current" > "$base/previous"
echo "Restored $previous"
