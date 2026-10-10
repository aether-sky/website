# Publish main on a Linode Debian VPS

This deployment serves the static blog only. Caddy redirects `/` to `/blog/`, serves the built blog, and obtains/renews HTTPS certificates. There is no Python service, Node runtime, database, chat API, or LLM key on the VPS. `dev` remains local.

## 1. Create the server and DNS

Create a **Linode Shared CPU / 2 GB / $12 per month** instance (1 vCPU, 50 GB SSD) with **Debian 13 (Trixie)**, in a region near your visitors. Add your SSH public key during creation. Do not choose a Docker or application marketplace image.

Attach an Akamai Cloud Firewall: allow inbound TCP **22 from your own IP**, TCP **80 and 443 from everyone**, and optionally UDP **443** for HTTP/3. Keep outbound traffic allowed for DNS, package updates, and certificate issuance. Do not expose ports 8000, 4324, 4325, or Caddy's admin port 2019. Set the default inbound policy to Drop and outbound to Accept. Check both IPv4 and IPv6 rules.

Point your domain's A record to the VPS's IPv4 address. Add an AAAA record only if you configure IPv6 to the same VPS. Keep existing email/MX records. This setup serves the exact domain you build for; it does not assume a `www` alias. If using a CDN, start with DNS-only routing while validating the origin.

Paid VPS backups are optional for this static release: the source and configuration can recreate it. Back up the Git repository somewhere other than your development computer, and retain a release archive. Server backups become important when a future release adds server-only data such as the review queue. HTTPS certificate state can be reissued; avoid unnecessary repeated rebuilds that might hit issuance limits.

The setup uses ordinary Debian and Caddy, so it also works on another VPS provider. Current references: [Linode plans](https://www.akamai.com/cloud/pricing/cpu), [Debian stable](https://www.debian.org/releases/), and [Caddy installation](https://caddyserver.com/docs/install#debian-ubuntu-raspbian).

## 2. Install Caddy once

SSH to the new server using its IP. Use your configured sudo account, or the initial `root` login for bootstrap. If logged in as root and `sudo` is absent, omit `sudo` from these commands. On the **VPS**, install the official stable package:

```sh
sudo apt update
sudo apt upgrade -y
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl gnupg
curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo chmod o+r /usr/share/keyrings/caddy-stable-archive-keyring.gpg /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy
```

These follow [Caddy's official Debian installation](https://caddyserver.com/docs/install#debian-ubuntu-raspbian). Its package supplies the unprivileged `caddy` user and systemd service. Install security updates regularly; reboot if the OS requests it.

## 3. Build and package locally

On your **development computer**, stop the dev preview, switch to `main`, and commit blog and deployment changes. The hostname below follows your supplied email domain; substitute it if the website uses a different domain:

```powershell
git switch main
pnpm install --frozen-lockfile
pnpm release:site https://aether-sky.cloud
```

The command builds the blog through Turborepo with `BLOG_BASE=/blog` and the supplied `SITE_URL`. It refuses non-`main` or detached checkouts and uncommitted blog/deployment inputs, including new untracked inputs. Unrelated documentation or reference-artwork work can remain uncommitted because it is not packaged. The command writes `.release/site-<commit>.tar.gz` and prints its SHA-256. Only files deliberately emitted into the blog's build artifact are published; private/unknown file extensions and symlinks inside that artifact are rejected. Review any new files added to `apps/blog/public` before publishing.

The archive contains `public/blog/`, a root redirect fallback, Caddy configuration, activation/rollback scripts, provenance, and checksums. Only `public/` is served. Local OAuth credentials, the repo, dependencies, and ignored chat build files are not included. SHA-256 detects accidental corruption; it does not prove an archive is from a trusted author. Transfer your own archive using SSH.

`pnpm build:site https://aether-sky.cloud` also builds a preview while tracked changes are uncommitted, but does not produce a deployable archive. Staging directories accumulate under ignored `.release/`; remove old ones when no longer needed.

## 4. Upload and activate

Replace the commit filename, SSH user, and IP with your actual values. These commands only upload the selected release:

```powershell
scp .release/site-<commit>.tar.gz <user>@<server-ip>:/tmp/site-release.tar.gz
ssh <user>@<server-ip>
```

Then, on the **VPS**:

```sh
release_dir=$(mktemp -d /tmp/aether-sky-release.XXXXXX)
tar -xzf /tmp/site-release.tar.gz -C "$release_dir"
sudo bash "$release_dir/deploy/activate.sh"
```

Activation is intended for a **dedicated website VPS**: it installs this site's Caddy configuration, preserving any previous configuration in `/etc/caddy/Caddyfile.before-aether-sky.*`. It checks the complete file inventory and hashes, rejects symlinks, copies a new version under `/srv/aether-sky/releases`, validates Caddy configuration, switches the `current` symlink, and restarts Caddy. The server serves root-owned read-only files as the `caddy` user. Old versions remain for rollback; a brief service restart occurs on activation.

Check:

```sh
curl -I https://aether-sky.cloud/
curl -I https://aether-sky.cloud/blog/
curl -I https://aether-sky.cloud/api/chat
sudo systemctl status caddy --no-pager
```

Expect **302 to `/blog/`**, **200**, and **404**, respectively. The root redirect is intentionally temporary and uncached so a later deliberate homepage release can replace it. Check an article, its embedded animation, RSS, and the appearance controls in a browser. Caddy requires correct public DNS and reachable ports 80/443 for [automatic HTTPS](https://caddyserver.com/docs/automatic-https).

## Updates, rollback, and recovery

For updates, commit on `main`, rerun `pnpm release:site`, upload the new archive, and run its activation script. Neither Git nor Node is needed on the server. Keep the website's source in a backed-up repository; only `main` should ever be wired to future publication automation.

To restore the previous activated release:

```sh
sudo bash /srv/aether-sky/current/deploy/rollback.sh
```

Rollback validates the previous configuration and switches back to it. It is available after at least two successful activations. It restores static content, not DNS or OS changes. If Caddy fails, inspect `sudo journalctl -u caddy -n 100 --no-pager`. If the VPS is lost, create a replacement, update DNS, install Caddy, and activate a retained archive. Keep old release directories until the new release is verified; periodically remove older versions manually to bound disk use.

## Verification

Local verification on 2026-10-10: the production `/blog` build passed; all 6 deployment checks passed using Caddy 2.11.7 and Bash; all 80 existing blog browser/accessibility tests passed in Microsoft Edge. The Caddy test checked root and `/blog` redirects, public links/assets, RSS origin, and inaccessible chat/settings/private paths. Integrity tests rejected modified files, extra files, and an absolute-path checksum entry. Activation and rollback scripts passed Bash syntax checks; their root/systemd behavior has not yet been exercised on a VPS. No server was purchased, DNS changed, or site published.

`pnpm test:release` runs artifact-boundary checks through Turborepo. To include a real Caddy HTTP smoke test, install/download Caddy and set `CADDY_BIN` to its executable path, then run `pnpm build:site https://your-domain` and `pnpm test:release`. Set `DEPLOY_BASH` to Bash's path to also test the actual server-side checksum verifier against valid, corrupted, extra-file, and invalid-path bundles. Without those executables, the respective integration tests are explicitly skipped. Blog UI coverage remains `pnpm test:a11y`; see the existing audit for manual limits. None of these local tests verifies your VPS's DNS, TLS issuance, firewall, or systemd setup; verify those after activation.
