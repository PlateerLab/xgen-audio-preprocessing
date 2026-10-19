"""Install a dedicated DEX audio runtime; never modify an existing environment."""
import argparse
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import venv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', required=True, type=Path, help='new runtime directory (must not exist)')
    args = parser.parse_args()
    if sys.version_info[:2] not in ((3, 11), (3, 12)) or sys.version_info < (3, 11, 8):
        parser.error('Use Python 3.11.8+ or 3.12 (with venv/ensurepip).')
    if platform.system() not in ('Darwin', 'Linux'):
        parser.error('This installer supports macOS/Linux; Windows is not implemented.')
    if not shutil.which('cc'):
        parser.error('C compiler missing: macOS needs Xcode Command Line Tools; Linux needs a C toolchain.')
    target = args.target.expanduser().absolute()
    if target.exists() or target.is_symlink():
        parser.error(f'Target already exists, refusing to overwrite: {target}')
    source = Path(__file__).resolve().parents[1]
    if not (source / 'pyproject.toml').is_file():
        parser.error('Run this script from the extracted source bundle, not a standalone copy.')
    target.mkdir(parents=True)
    python = target / '.venv/bin/python'
    library = target / '.local/rnnoise' / ('librnnoise.dylib' if platform.system() == 'Darwin' else 'librnnoise.so')
    env = os.environ.copy()
    for key in ('PYTHONPATH', 'PYTHONHOME', 'XGEN_RNNOISE_LIBRARY'):
        env.pop(key, None)
    env['PYTHONNOUSERSITE'] = '1'

    def run(*command):
        subprocess.run([str(c) for c in command], cwd=target, env=env, check=True)

    try:
        print(f'Creating isolated runtime: {target}', flush=True)
        venv.EnvBuilder(with_pip=True, symlinks=True).create(target / '.venv')
        # Non-editable install: the runtime must work without this source checkout.
        run(python, '-m', 'pip', '--isolated', '--no-cache-dir', 'install', source)
        run(python, source / 'scripts/build_rnnoise.py', '--output', library.parent)
        run(python, '-m', 'pip', 'check')
        env['XGEN_RNNOISE_LIBRARY'] = str(library)
        run(python, '-I', '-c', '''
import sys
from pathlib import Path
import xgen_audio
from xgen_audio import AudioPreprocessor
assert Path(xgen_audio.__file__).is_relative_to(Path(sys.prefix)), xgen_audio.__file__
raw = bytes(32000)
for noise in ('none', 'rnnoise'):
    for vad in (False, True):
        with AudioPreprocessor(denoise=noise, vad=vad) as stream:
            chunks = [stream.push(raw[i:i+2048]) for i in range(0, len(raw), 2048)]
            chunks.append(stream.finish())
            assert sum(len(c.pcm) for c in chunks) == len(raw)
            assert not any(c.events for c in chunks), 'silence triggered VAD'
        print(f'Runtime check passed: noise={noise}, vad={vad}')
''')
        freeze = subprocess.check_output([str(python), '-m', 'pip', 'freeze'], cwd=target, env=env, text=True)
        (target / 'installed-requirements.txt').write_text(freeze)
        settings = {'DEX_AUDIO_ROOT': str(target), 'DEX_AUDIO_PYTHON': str(python), 'XGEN_RNNOISE_LIBRARY': str(library)}
        (target / 'env.sh').write_text(''.join(f'export {key}={shlex.quote(value)}\n' for key, value in settings.items()))
        (target / 'install-info.json').write_text(json.dumps({
            'python': sys.version, 'platform': platform.platform(), 'machine': platform.machine(),
            'source': str(source), **settings,
        }, indent=2) + '\n')
        print(f'Installation verified. In the terminal that launches DEX:\nsource {shlex.quote(str(target / "env.sh"))}')
    except (subprocess.CalledProcessError, OSError) as error:
        print(f'Installation failed: {error}\nIncomplete files remain at {target}; use a new target for retry.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
