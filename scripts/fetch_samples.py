"""Download small public test fixtures; never package these in the runtime wheel."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('artifacts/samples'))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    base = 'https://raw.githubusercontent.com/Rikorose/DeepFilterNet/d375b2d8309e0935d165700c91da9de862a99c31/assets/'
    sources = [
        ('noise_freesound_2530.wav', base+'noise_freesound_2530.wav', 'CC BY 3.0; Freesound sound 2530, see upstream assets/README.md'),
        ('noise_freesound_573577.wav', base+'noise_freesound_573577.wav', 'CC0 1.0; Freesound sound 573577'),
        ('speech.wav', 'https://raw.githubusercontent.com/ggml-org/whisper.cpp/master/samples/jfk.wav', 'JFK public address sample from whisper.cpp; test only'),
    ]
    manifest = []
    for name, url, license in sources:
        path = args.output / name
        if not path.exists():
            urllib.request.urlretrieve(url, path)
        manifest.append(dict(file=name, url=url, license=license, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    fixture = Path(__file__).resolve().parents[1]/'tests/fixtures/speech.wav'
    (args.output/'korean.wav').write_bytes(fixture.read_bytes())
    manifest.append(dict(file='korean.wav',source='existing XGEN synthesized Korean VAD fixture; local test only',sha256=hashlib.sha256(fixture.read_bytes()).hexdigest()))
    (args.output/'sources.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
