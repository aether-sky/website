#!/usr/bin/env bash
# Read-only integrity check; does not install, configure, or start anything.
set -euo pipefail
cd -- "${1:?Pass the extracted release directory}"
[[ -f SHA256SUMS && -f COMMIT && -f DOMAIN && -f release.json ]] || exit 1
[[ -z $(find . -type l -print -quit) ]] || { echo 'Symlinks are not allowed in the release.' >&2; exit 1; }
[[ -z $(find . ! -type f ! -type d -print -quit) ]] || exit 1
while IFS= read -r line; do
    [[ $line =~ ^[0-9a-f]{64}\ \ [A-Za-z0-9_./-]+$ ]] || exit 1
    name=${line:66}
    [[ $name != /* && $name != *..* && $name != .* ]] || exit 1
done < SHA256SUMS
cmp <(find . -type f ! -path './SHA256SUMS' -printf '%P\n' | LC_ALL=C sort) <(cut -c67- SHA256SUMS | LC_ALL=C sort)
sha256sum --check --strict SHA256SUMS >/dev/null
read -r commit < COMMIT
read -r domain < DOMAIN
[[ $commit =~ ^[0-9a-f]{40}$ ]] || exit 1
[[ $domain =~ ^[a-z0-9]([a-z0-9.-]*[a-z0-9])?\.[a-z]{2,63}$ ]] || exit 1
[[ -f public/blog/index.html && -f public/index.html ]] || exit 1
[[ $(find public -mindepth 1 -maxdepth 1 ! -name blog ! -name index.html | wc -l) -eq 0 ]] || exit 1
echo 'Release inventory and checksums verified.'
