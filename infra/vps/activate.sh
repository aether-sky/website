#!/usr/bin/env bash
# Run on a dedicated Debian VPS after installing Caddy's official package.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
bundle=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
cd "$bundle"
for tool in caddy sha256sum find sort cmp install cp ln mv systemctl flock; do command -v "$tool" >/dev/null; done
exec 9>/run/aether-sky-deploy.lock
flock -n 9 || { echo 'Another deployment is running.' >&2; exit 1; }
[[ -z $(find . -type l -print -quit) ]] || { echo 'Symlinks are not allowed in the release.' >&2; exit 1; }
[[ -z $(find . ! -type f ! -type d -print -quit) ]] || exit 1
bash deploy/verify-release.sh "$bundle"
read -r commit < COMMIT
read -r domain < DOMAIN

base=/srv/aether-sky
install -d -m 755 "$base/releases" /etc/caddy /etc/systemd/system/caddy.service.d
if [[ -e /etc/caddy/Caddyfile ]] && ! grep -q 'aether-sky static publication' /etc/caddy/Caddyfile; then
    # Keep the prior package/default configuration before this dedicated-site setup.
    backup=$(mktemp /etc/caddy/Caddyfile.before-aether-sky.XXXXXX)
    cp /etc/caddy/Caddyfile "$backup"
    echo "Saved prior Caddy configuration to $backup"
fi
release=$(mktemp -d "$base/releases/$commit-XXXXXX")
cp -R public deploy COMMIT DOMAIN release.json SHA256SUMS "$release/"
find "$release" -type d -exec chmod 755 {} +
find "$release" -type f -exec chmod 644 {} +
SITE_ADDRESS="$domain" SITE_ROOT="$release/public" caddy validate --config "$release/deploy/Caddyfile" --adapter caddyfile

previous=''
if [[ -L $base/current ]]; then
    previous=$(readlink -f "$base/current")
elif [[ -e $base/current ]]; then
    echo 'The current release path must be a symlink, not a directory.' >&2
    exit 1
fi
if [[ -n $previous ]]; then
    [[ $previous == "$base/releases/"* && -d $previous/public ]] || exit 1
    read -r previous_domain < "$previous/DOMAIN"
    [[ $domain == "$previous_domain" ]] || { echo 'Domain changes require a separate DNS/configuration review.' >&2; exit 1; }
fi
install -m 644 "$release/deploy/Caddyfile" /etc/caddy/Caddyfile
printf 'SITE_ADDRESS=%s\n' "$domain" > /etc/caddy/aether-sky.env
printf '[Service]\nEnvironmentFile=/etc/caddy/aether-sky.env\n' > /etc/systemd/system/caddy.service.d/aether-sky.conf
ln -s "$release" "$base/current.next"
mv -Tf "$base/current.next" "$base/current"
systemctl daemon-reload
systemctl enable caddy
# Restart loads EnvironmentFile on initial setup; subsequent releases also use it.
if ! systemctl restart caddy; then
    if [[ -n $previous ]]; then
        ln -s "$previous" "$base/current.next"
        mv -Tf "$base/current.next" "$base/current"
        install -m 644 "$previous/deploy/Caddyfile" /etc/caddy/Caddyfile
        systemctl restart caddy || true
    fi
    echo 'Caddy failed; inspect journalctl -u caddy.' >&2
    exit 1
fi
if [[ -n $previous ]]; then printf '%s\n' "$previous" > "$base/previous"; fi
echo "Active release: $release"
echo "Check https://$domain/ and https://$domain/blog/ after DNS and TLS are ready."
