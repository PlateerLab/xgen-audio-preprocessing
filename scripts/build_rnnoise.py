"""Build pinned upstream RNNoise on macOS/Linux without autotools or Git writes."""
import argparse
import hashlib
from pathlib import Path
import platform
import subprocess
import tarfile
import urllib.request

COMMIT = '70f1d256acd4b34a572f999a05c87bf00b67730d'
SOURCE_HASH = 'f61ee0b3f4c4cd337303e003d333357c5eaf25ef5d75a742109ee59e9a0a3932'
MODEL_HASH = '0a8755f8e2d834eff6a54714ecc7d75f9932e845df35f8b59bc52a7cfe6e8b37'


def download(url, path, digest):
    if not path.exists():
        urllib.request.urlretrieve(url, path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError(f'Checksum mismatch: {path}; remove it and retry')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('.local/rnnoise'))
    args = parser.parse_args()
    if platform.system() not in ('Darwin', 'Linux'):
        parser.error('This build script supports macOS/Linux; Windows needs a separately built RNNoise DLL')
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=True)
    archive = root / 'source.tar.gz'
    download(f'https://codeload.github.com/xiph/rnnoise/tar.gz/{COMMIT}', archive, SOURCE_HASH)
    with tarfile.open(archive) as tar:
        tar.extractall(root, filter='data')
    source = root / f'rnnoise-{COMMIT}'
    weights = root / 'model.tar.gz'
    download(f'https://media.xiph.org/rnnoise/models/rnnoise_data-{MODEL_HASH}.tar.gz', weights, MODEL_HASH)
    with tarfile.open(weights) as tar:
        tar.extractall(source, filter='data')
    library = root / ('librnnoise.dylib' if platform.system() == 'Darwin' else 'librnnoise.so')
    names = 'denoise rnn pitch kiss_fft celt_lpc nnet nnet_default parse_lpcnet_weights rnnoise_data rnnoise_tables'.split()
    subprocess.run(['cc', '-O3', '-shared', '-fPIC', '-Iinclude', '-Isrc', '-o', str(library),
                    *[f'src/{name}.c' for name in names], '-lm'], cwd=source, check=True)
    print(f'XGEN_RNNOISE_LIBRARY={library}')


if __name__ == '__main__':
    main()
