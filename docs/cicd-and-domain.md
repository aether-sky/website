# Domain and automatic publication

Repository: <https://github.com/aether-sky/website>. Debian VPS: `162.216.16.250`.
Public domain: <https://aether-sky.cloud>. Only `main` publishes. `dev` stays experimental.

## Porkbun DNS

In Porkbun, open **Domain Management → aether-sky.cloud → DNS**. Replace the existing
apex web records (currently resolving to `207.207.210.107` and `207.207.210.229`)
with this record:

| Type | Host | Answer | TTL |
| --- | --- | --- | --- |
| A | leave blank | 162.216.16.250 | 600 or default |

Remove conflicting apex ALIAS/CNAME/A records pointing elsewhere, and any stale apex
AAAA record pointing to a different server. Preserve MX/TXT and other email records.
Keep the existing Porkbun nameservers. This configuration serves the apex only;
`www` needs an explicit Caddy alias before adding a DNS record for it.

Allow inbound TCP 80/443 through the Linode firewall. Caddy obtains HTTPS once DNS
resolves to this server and those ports are reachable. Check from PowerShell:

```powershell
Resolve-DnsName aether-sky.cloud -Type A
curl.exe -I https://aether-sky.cloud/
curl.exe -I https://aether-sky.cloud/blog/
```

Expect the Linode IP, a 302 redirect to `/blog/`, and a 200 response. If the server
only shows the Caddy welcome page, complete the first static release activation in
[vps-deployment.md](vps-deployment.md) before enabling automatic uploads.

References: [Porkbun A records](https://kb.porkbun.com/article/54-how-to-use-a-records-to-point-your-domain-at-a-web-host),
[Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https).

## One-time deployment account

Generate a separate deployment key on your development computer. Use an empty
passphrase because GitHub Actions must use this key without interaction. The
`work` directory is ignored by Git; do not commit or share the private file.

```powershell
New-Item -ItemType Directory -Force work/deploy-keys
ssh-keygen -t ed25519 -C website-github-deploy -f work/deploy-keys/site-deploy
```

Copy the public key and reviewed setup files using your existing admin login
(substitute your SSH username if it is not `root`):

```powershell
scp infra/vps/receive.py infra/vps/setup-ci.sh work/deploy-keys/site-deploy.pub root@162.216.16.250:/tmp/
ssh root@162.216.16.250
```

On the **VPS**, after the first manual release is active:

```sh
sudo apt install -y python3
sudo bash /tmp/setup-ci.sh /tmp/site-deploy.pub
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

If logged in as root, omit `sudo`. The last command prints the server fingerprint.
Verify it through your already trusted SSH connection or Linode's LISH console.
Then on your development computer collect the matching host key:

```powershell
ssh-keyscan -t ed25519 162.216.16.250 2>$null | Set-Content -Encoding ascii work/deploy-keys/known_hosts
ssh-keygen -lf work/deploy-keys/known_hosts
```

The fingerprints must match. `ssh-keyscan` alone does not authenticate a server.
Keep strict host checking enabled.

The `site-deploy` account accepts only `deploy <40-character-commit>` through a forced
SSH command. It cannot open an interactive shell, forward ports, run uploaded scripts,
change Caddy configuration, or use sudo. The root-owned receiver bounds archive size,
rejects links and unsafe paths, verifies the complete checksum inventory and expected
commit/domain/main provenance, and publishes only static files. Checksums detect
corruption; SSH credentials and repository access establish who may publish. A person
who can push to `main` can still publish arbitrary browser HTML/JS, so protect that branch.

The server needs Python's standard library for this upload utility. It does not run a
Python web service or coding agent. Caddy continues serving static files.

## GitHub configuration

In **Settings → Environments**, create `production`. Restrict deployment branches to
**Selected branches and tags → main**. Add these environment secrets:

| Secret | Value |
| --- | --- |
| DEPLOY_SSH_KEY | Entire contents of `work/deploy-keys/site-deploy` (private key) |
| DEPLOY_KNOWN_HOSTS | Entire verified `work/deploy-keys/known_hosts` file |

Using the authenticated GitHub CLI avoids copying the private key into chat:

```powershell
Get-Content -Raw work/deploy-keys/site-deploy | gh secret set DEPLOY_SSH_KEY --env production --repo aether-sky/website
Get-Content -Raw work/deploy-keys/known_hosts | gh secret set DEPLOY_KNOWN_HOSTS --env production --repo aether-sky/website
```

**Firewall:** hosted GitHub runners use changing source IPs. An SSH rule allowing only
your personal IP blocks deployment. For this simple setup, permit TCP 22 for the hosted
runner connections using public-key authentication and the restricted upload key.
Before widening access, verify your admin public-key login works, then disable SSH
password and keyboard-interactive authentication, validate with `sudo sshd -t`, and reload
SSH while keeping your existing session open. Inspect effective settings using
`sudo sshd -T`; distribution snippets and Match blocks can override configuration.
Alternatively retain the narrow firewall and add a VPN or runner with a fixed IP;
that requires additional workflow/network setup. Do not copy GitHub's entire changing IP
range into a permanent firewall rule.

References: [GitHub environments](https://docs.github.com/en/actions/concepts/workflows-and-actions/deployment-environments),
[GitHub runner IP addresses](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).

Once DNS, the upload account, secrets, and SSH reachability are ready:

```powershell
git remote add origin https://github.com/aether-sky/website.git
git push -u origin main
git push -u origin dev
```

If `origin` is already configured, omit `git remote add`. Set the repository default
branch to `main`. The workflow checks pull requests targeting `main`, checks pushes
to `main`, and deploys only successful `main` pushes or manual runs on `main`.
Neither pull requests nor `dev` pushes receive deployment secrets or publish.
Manual dispatch is under **Actions → Check and publish static site → Run workflow**.
Older queued commits are skipped when `main` has advanced.

Checks include the release boundary/Caddy tests, hostile receiver payloads, and the
blog's existing accessibility/browser suite. Actions are pinned by commit SHA.
After publication, the workflow verifies the root redirect, blog response, and
inaccessible chat route. Use a GitHub ruleset to require the `checks` job before
merging into `main`; use reviewed pull requests from `dev` for blog changes, taking
care not to merge the experimental homepage into the publication branch.

## Rollback and maintenance

On the VPS, restore the previous static release with:

```sh
sudo -u site-deploy /usr/local/bin/site-receive --rollback
```

Then revert the problematic Git commit before the next publication. Automatic uploads
do not install deployment scripts or Caddy changes. Review and install receiver changes
manually with `setup-ci.sh`; apply Caddy changes as an admin. After CI is enabled, use
the receiver's rollback command, not the older release-bundled rollback script.
Do not run manual activation concurrently with an automatic upload. Old releases are
retained; periodically remove older ones after checking that they are neither `current`
nor `previous`. The receiver limits each upload, not total disk usage.

Local verification: seven deployment tests passed with Caddy/Bash/Python, including
six Python test groups (hostile archive/provenance cases and Linux publication/rollback).
Live server account setup, GitHub execution, firewall connectivity, and TLS issuance
still require end-to-end verification after the configuration above.
