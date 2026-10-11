"""Exercise the SSH receiver with valid releases and hostile archive payloads."""
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('receive', Path(__file__).parents[2] / 'infra/vps/receive.py')
receive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(receive)
COMMIT = 'a' * 40
DOMAIN = 'aether-sky.cloud'


def fixture():
    files = {
        'COMMIT': (COMMIT + '\n').encode(), 'DOMAIN': (DOMAIN + '\n').encode(),
        'release.json': json.dumps(dict(branch='main', commit=COMMIT,
                                       origin='https://' + DOMAIN, kind='static-blog')).encode(),
        'public/index.html': b'redirect', 'public/blog/index.html': b'<h1>Blog</h1>',
        'public/blog/assets/main.css': b'body { color: black }',
        'deploy/activate.sh': b'UNTRUSTED SCRIPT MUST NEVER EXECUTE',
    }
    return checksums(files)


def checksums(files):
    files['SHA256SUMS'] = ''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\n'
                                for name, data in files.items() if name != 'SHA256SUMS').encode()
    return files


def archive(files, extra=None):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode='w:gz') as tar:
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            tar.addfile(member, io.BytesIO(data))
        if extra:
            tar.addfile(extra)
    return io.BytesIO(out.getvalue())


class ReceiverTests(unittest.TestCase):
    def test_valid_roundtrip(self):
        files = receive.unpack(archive(fixture()))
        receive.validate(files, COMMIT, DOMAIN)

    def test_corruption_inventory_and_provenance(self):
        for mutation in ('corrupt', 'extra', 'missing', 'duplicate_hash', 'dev', 'ci-check', 'domain', 'commit', 'kind'):
            with self.subTest(mutation=mutation):
                files = fixture()
                if mutation == 'corrupt':
                    files['public/blog/index.html'] += b'changed'
                elif mutation == 'extra':
                    files['secret.txt'] = b'private'
                elif mutation == 'missing':
                    del files['public/blog/index.html']
                elif mutation == 'duplicate_hash':
                    files['SHA256SUMS'] += files['SHA256SUMS'].splitlines(keepends=True)[0]
                elif mutation == 'domain':
                    files['DOMAIN'] = b'other.example\n'
                    checksums(files)
                else:
                    metadata = json.loads(files['release.json'])
                    metadata['branch' if mutation in {'dev', 'ci-check'} else mutation] = mutation
                    files['release.json'] = json.dumps(metadata).encode()
                    checksums(files)
                with self.assertRaises(ValueError):
                    receive.validate(files, COMMIT, DOMAIN)

    def test_invalid_paths_and_member_types(self):
        for name in ('../escape', '/etc/passwd', 'public/.env', 'public//file', 'public/./file', 'public/back\\slash'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                receive.unpack(archive({name: b'bad'}))
        for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE, tarfile.BLKTYPE):
            member = tarfile.TarInfo('public/link')
            member.type = kind
            member.linkname = '/etc/passwd'
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                receive.unpack(archive({}, member))
        with self.assertRaises(ValueError):
            receive.unpack(archive({'COMMIT': b'a'}, tarfile.TarInfo('COMMIT')))

    def test_resource_limits(self):
        with patch.object(receive, 'MAX_COMPRESSED', 8), self.assertRaises(ValueError):
            receive.unpack(archive(fixture()))
        with patch.object(receive, 'MAX_EXPANDED', 128), self.assertRaises(ValueError):
            receive.unpack(io.BytesIO(gzip.compress(b'x' * 129)))
        with patch.object(receive, 'MAX_FILES', 1), self.assertRaises(ValueError):
            receive.unpack(archive(fixture()))

    def test_extra_public_app_or_source_rejected_even_with_valid_hashes(self):
        for name in ('public/home/index.html', 'public/blog/server.py', 'deploy/evil.sh'):
            files = fixture()
            files[name] = b'bad'
            with self.subTest(name=name), self.assertRaises(ValueError):
                receive.validate(checksums(files), COMMIT, DOMAIN)

    @unittest.skipIf(os.name == 'nt', 'Publication symlinks exercised on Linux')
    def test_atomic_publish_rollback_and_rejected_release_preserves_current(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            previous = base / 'releases/old'
            (previous / 'public/blog').mkdir(parents=True)
            (previous / 'public/blog/index.html').write_text('old')
            (base / 'current').symlink_to(previous)
            bad = fixture()
            bad['COMMIT'] = b'wrong'
            with self.assertRaises(ValueError):
                receive.publish(bad, COMMIT, DOMAIN, base)
            self.assertEqual((base / 'current').resolve(), previous)
            receive.publish(fixture(), COMMIT, DOMAIN, base)
            current = (base / 'current').resolve()
            self.assertEqual((current / 'public/blog/index.html').read_bytes(), b'<h1>Blog</h1>')
            self.assertFalse((current / 'deploy').exists())
            self.assertEqual(current.stat().st_mode & 0o777, 0o755)
            receive.rollback(base)
            self.assertEqual((base / 'current').resolve(), previous)


if __name__ == '__main__':
    unittest.main()
