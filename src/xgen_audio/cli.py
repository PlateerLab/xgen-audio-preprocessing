"""Pipe raw PCM via stdin/stdout; optional VAD JSON goes to stderr."""
import argparse
import base64
import binascii
from dataclasses import asdict
import json
import sys

from .stream import AudioPreprocessor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample-rate', type=int, choices=(16000, 48000), default=16000)
    parser.add_argument('--denoise', choices=('none', 'rnnoise'), default='none')
    parser.add_argument('--events', action='store_true')
    parser.add_argument('--no-vad', action='store_true')
    parser.add_argument('--jsonl', action='store_true', help='Bounded request/reply PCM protocol for DEX')
    args = parser.parse_args()
    try:
        with AudioPreprocessor(args.sample_rate, denoise=args.denoise, vad=not args.no_vad) as stream:
            if args.jsonl:
                run_jsonl(stream)
                return
            def emit(result):
                sys.stdout.buffer.write(result.pcm)
                sys.stdout.buffer.flush()
                if args.events:
                    for event in result.events:
                        print(json.dumps(asdict(event)), file=sys.stderr, flush=True)
            if args.events:
                print(json.dumps({'type': 'ready', 'sample_rate': 16000}), file=sys.stderr, flush=True)
            while data := sys.stdin.buffer.read1(4096):
                emit(stream.push(data))
            emit(stream.finish())
    except (ValueError, RuntimeError, OSError) as exc:
        print(f'xgen-audio: {exc}', file=sys.stderr)
        raise SystemExit(1)


def run_jsonl(stream):
    print(json.dumps({'type': 'ready'}), flush=True)
    while True:
        line = sys.stdin.buffer.readline(90000)
        if not line:
            raise ValueError('Unexpected EOF: send finish to drain the stream')
        if not line.endswith(b'\n'):
            raise ValueError('Audio request exceeds limit')
        request = json.loads(line)
        if not isinstance(request, dict):
            raise ValueError('Expected audio request object')
        kind = request.get('type')
        if kind == 'push':
            encoded = request.get('pcm')
            if not isinstance(encoded, str):
                raise ValueError('Expected base64 PCM')
            try:
                pcm = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ValueError('Invalid base64 PCM') from exc
            if len(pcm) > 64000:
                raise ValueError('Audio chunk exceeds 2 seconds')
            result = stream.push(pcm)
        elif kind == 'finish':
            result = stream.finish()
        else:
            raise ValueError('Unknown audio request')
        print(json.dumps({
            'type': 'audio', 'pcm': base64.b64encode(result.pcm).decode('ascii'),
            'events': [asdict(event) for event in result.events],
            'inSpeech': stream.vad.in_speech if stream.vad is not None else False,
        }), flush=True)
        if kind == 'finish':
            return


if __name__ == '__main__':
    main()
