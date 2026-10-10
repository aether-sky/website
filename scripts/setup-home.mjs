import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';
const root = fileURLToPath(new URL('../', import.meta.url));
const venv = join(root, 'services/home/.venv');
const python = join(venv, process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const requirements = join(root, 'services/home/requirements.txt');

function fail(message) {
  console.error(message);
  process.exit(1);
}
function supported(command) {
  const result = spawnSync(command, ['-c', 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'], { encoding: 'utf8' });
  return !result.error && result.status === 0;
}
function run(command, args) {
  const result = spawnSync(command, args, { cwd: root, stdio: 'inherit' });
  if (result.error || result.status !== 0) {
    fail('Homepage dependency setup failed. Stop any running homepage server before changing dependencies, then retry. Python 3.12+ is required.');
  }
}

// Re-running `python -m venv` can rewrite pyvenv.cfg before Windows rejects
// replacing an in-use python.exe. Never recreate an existing environment here.
if (!existsSync(python)) {
  if (existsSync(venv)) fail('The homepage virtual environment is incomplete. Stop the homepage server and repair services/home/.venv with Python 3.12+ before retrying.');
  const base = process.env.PYTHON || 'python';
  if (!supported(base)) fail('Python 3.12+ is required. Set PYTHON to its executable path, then retry. No virtual environment was changed.');
  run(base, ['-m', 'venv', venv]);
} else if (!supported(python)) {
  fail('The existing homepage environment is unavailable or uses Python older than 3.12. Stop the homepage server and repair services/home/.venv with Python 3.12+. No virtual environment was changed.');
}

// Avoid pip/network work when the pinned dependencies are already usable.
const check = String.raw`
import importlib.metadata as metadata
import pathlib, sys
for line in pathlib.Path(sys.argv[1]).read_text(encoding='utf-8').splitlines():
    line = line.strip()
    if not line or line.startswith('#'):
        continue
    name, expected = line.split('==', 1)
    try:
        if metadata.version(name) != expected:
            sys.exit(1)
    except metadata.PackageNotFoundError:
        sys.exit(1)
import httpx, html5lib, tinycss2, jwt, hypothesis
from cryptography.hazmat.primitives.asymmetric import rsa
`;
const result = spawnSync(python, ['-c', check, requirements], { encoding: 'utf8' });
if (!result.error && result.status === 0) {
  console.log('Homepage Python environment and dependencies are ready.');
} else {
  run(python, ['-m', 'pip', 'install', '--disable-pip-version-check', '-r', requirements]);
  const verify = spawnSync(python, ['-c', check, requirements], { encoding: 'utf8' });
  if (verify.error || verify.status !== 0) fail('Homepage dependencies could not be verified. Stop the homepage server and repair its virtual environment before retrying.');
}
