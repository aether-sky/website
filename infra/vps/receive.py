#!/usr/bin/python3
"""Forced SSH command: bounded static release upload, no shell or sudo access."""
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tarfile
import tempfile

MAX_COMPRESSED = 32 * 1024 * 1024
MAX_EXPANDED = 80 * 1024 * 1024
MAX_FILES = 6000
BASE = Path('/srv/aether-sky')
EXTENSIONS = {'.html', '.css', '.js', '.xml', '.txt', '.json', '.png', '.jpg', '.jpeg',
              '.webp', '.avif', '.gif', '.svg', '.ico', '.woff', '.woff2', '.ttf',
              '.otf', '.pdf', '.mp4', '.webm'}


def unpack(stream):
    compressed = stream.read(MAX_COMPRESSED + 1)
    if len(compressed) > MAX_COMPRESSED:
        raise ValueError('Compressed release too large')
    # Bound expansion before tarfile parses extended headers.
    with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as source:
        raw = source.read(MAX_EXPANDED + 1)
    if len(raw) > MAX_EXPANDED:
        raise ValueError('Expanded release too large')
    files, seen = {}, set()
    with tarfile.open(fileobj=io.BytesIO(raw), mode='r:') as archive:
        for member in archive:
            name = member.name.rstrip('/') if member.isdir() else member.name
            if (len(seen) >= MAX_FILES or name in seen or len(name) > 240
                    or not re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_./-]*', name)
                    or any(p in {'', '.', '..'} or p.startswith('.') for p in name.split('/'))):
                raise ValueError('Invalid or duplicate archive path')
            seen.add(name)
            if not member.isfile() and not member.isdir():
                raise ValueError('Links and special files are forbidden')
            if member.isfile():
                if member.size > MAX_EXPANDED:
                    raise ValueError('File too large')
                files[name] = archive.extractfile(member).read()
    return files


def validate(files, commit, domain):
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        raise ValueError('Invalid commit')
    required = {'COMMIT', 'DOMAIN', 'release.json', 'SHA256SUMS',
                'public/index.html', 'public/blog/index.html'}
    if not required <= files.keys():
        raise ValueError('Missing release files')
    sums = {}
    for line in files['SHA256SUMS'].decode('ascii').splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
        if not match or match[2] in sums:
            raise ValueError('Invalid checksum inventory')
        sums[match[2]] = match[1]
    if set(sums) != files.keys() - {'SHA256SUMS'}:
        raise ValueError('Checksum inventory mismatch')
    if any(hashlib.sha256(files[name]).hexdigest() != digest for name, digest in sums.items()):
        raise ValueError('Checksum mismatch')
    metadata = json.loads(files['release.json'])
    if (files['COMMIT'] != (commit + '\n').encode()
            or files['DOMAIN'] != (domain + '\n').encode()
            or metadata.get('commit') != commit or metadata.get('branch') != 'main'
            or metadata.get('origin') != 'https://' + domain
            or metadata.get('kind') != 'static-blog'):
        raise ValueError('Release provenance mismatch')
    for name in files:
        if name in {'COMMIT', 'DOMAIN', 'release.json', 'SHA256SUMS', 'public/index.html'}:
            continue
        if name in {'deploy/Caddyfile', 'deploy/activate.sh', 'deploy/rollback.sh', 'deploy/verify-release.sh'}:
            continue  # Never installed or executed from an upload.
        if not name.startswith('public/blog/') or Path(name).suffix.lower() not in EXTENSIONS:
            raise ValueError('Unexpected release file')


def current_release(base):
    link = base / 'current'
    if not link.is_symlink():
        raise ValueError('Expected an existing current release symlink')
    target = link.resolve(strict=True)
    if target.parent != (base / 'releases').resolve(strict=True):
        raise ValueError('Current release outside releases directory')
    return target


def switch(base, target):
    pending = base / 'current.next'
    pending.unlink(missing_ok=True)
    pending.symlink_to(target, target_is_directory=True)
    pending.replace(base / 'current')


def publish(files, commit, domain, base=BASE):
    validate(files, commit, domain)
    previous = current_release(base)
    stage = Path(tempfile.mkdtemp(prefix=commit + '-', dir=base / 'releases'))
    try:
        for name, data in files.items():
            if not (name.startswith('public/') or name in {'COMMIT', 'DOMAIN', 'release.json'}):
                continue
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(0o644)
        for directory, _, _ in os.walk(stage):
            Path(directory).chmod(0o755)
        # Save rollback state before the atomic publication step.
        saved = base / 'previous.next'
        saved.write_text(str(previous) + '\n')
        saved.replace(base / 'previous')
        switch(base, stage)
    except Exception:
        if (base / 'current').resolve() != stage:
            shutil.rmtree(stage)
        raise


def rollback(base=BASE):
    previous = Path((base / 'previous').read_text().strip()).resolve(strict=True)
    if previous.parent != (base / 'releases').resolve(strict=True):
        raise ValueError('Previous release outside releases directory')
    if not (previous / 'public/blog/index.html').is_file():
        raise ValueError('Previous release incomplete')
    switch(base, previous)


def main():
    import fcntl
    os.umask(0o022)
    with (BASE / '.upload.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if sys.argv[1:] == ['--rollback'] and not os.environ.get('SSH_ORIGINAL_COMMAND'):
            rollback()
            print('Previous static release restored')
            return
        if sys.argv[1:]:
            raise ValueError('Unexpected arguments')
        command = re.fullmatch(r'deploy ([0-9a-f]{40})', os.environ.get('SSH_ORIGINAL_COMMAND', ''))
        if not command:
            raise ValueError('Only deploy <commit> is allowed')
        config = Path('/etc/caddy/aether-sky.env').read_text()
        domain = re.fullmatch(r'SITE_ADDRESS=([a-z0-9.-]+)\s*', config)
        if not domain:
            raise ValueError('Invalid installed domain configuration')
        publish(unpack(sys.stdin.buffer), command[1], domain[1])
        print('Published static release ' + command[1])


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('Deployment rejected: ' + str(error), file=sys.stderr)
        sys.exit(1)
