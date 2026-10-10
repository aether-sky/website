import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
// Set PYTHON to an absolute executable path when Python is not on PATH.
const local = fileURLToPath(new URL(`../services/home/.venv/${process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python'}`, import.meta.url));
const process_ = spawn(existsSync(local) ? local : process.env.PYTHON || 'python', process.argv.slice(2), { stdio: 'inherit', env: process.env });
process_.on('error', error => { console.error(`Could not start Python. Install Python 3.12+ or set PYTHON. ${error.message}`); process.exitCode = 1; });
process_.on('exit', code => { process.exitCode = code ?? 1; });
