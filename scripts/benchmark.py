"""Deterministic noisy PCM replay -> real denoiser/VAD -> optional local ASR.

This is a small regression experiment, not a COEX field acceptance test.
"""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import platform
import re
import time

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from xgen_audio import AudioPreprocessor


def load(path):
    x, sr = sf.read(path, dtype='float32', always_2d=True)
    x = x.mean(axis=1)
    return resample_poly(x, 16000 // np.gcd(sr, 16000), sr // np.gcd(sr, 16000)).astype('float32') if sr != 16000 else x


def cer(ref, hyp):
    norm = lambda s: re.sub(r'[^\w]', '', s.lower())
    a, b = norm(ref), norm(hyp)
    row = list(range(len(b)+1))
    for i, ca in enumerate(a, 1):
        new = [i]
        for j, cb in enumerate(b, 1):
            new.append(min(new[-1]+1, row[j]+1, row[j-1]+(ca != cb)))
        row = new
    return row[-1] / max(1, len(a))


def replay(x, denoise):
    raw = np.clip(np.rint(x*32768), -32768, 32767).astype('<i2').tobytes()
    stream = AudioPreprocessor(denoise=denoise if isinstance(denoise, str) else "rnnoise" if denoise else "none")
    parts, events, latencies = [], [], []
    first_output_at = None
    start = time.perf_counter()
    for i in range(0, len(raw), 2048):  # DEX's 64 ms microphone callback
        t = time.perf_counter()
        result = stream.push(raw[i:i+2048])
        latencies.append((time.perf_counter()-t)*1000)
        if result.pcm and first_output_at is None:
            first_output_at = min(len(raw), i+2048)/32
        parts.append(result.pcm)
        events.extend(asdict(e) for e in result.events)
    result = stream.finish()
    parts.append(result.pcm)
    events.extend(asdict(e) for e in result.events)
    out = b''.join(parts)
    assert len(out) == len(raw)
    return np.frombuffer(out, dtype='<i2').astype(np.float32)/32768, {
        'rtf': (time.perf_counter()-start)/(len(x)/16000),
        'push_p95_ms': float(np.percentile(latencies, 95)),
        'first_output_after_input_ms': first_output_at,
        'events': events,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('artifacts/benchmark'))
    parser.add_argument('--asr-model', type=Path)
    parser.add_argument('--backend', default='rnnoise', choices=['rnnoise', 'deepfilter'])
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    model = None
    if args.asr_model:
        from faster_whisper import WhisperModel
        model = WhisperModel(str(args.asr_model), device='cpu', compute_type='int8', cpu_threads=4)
    sources = [
        ('korean', args.data/'korean.wav', '안녕하세요. 오늘 날씨가 정말 좋네요.', 'ko'),
        ('english', args.data/'speech.wav', 'And so my fellow Americans ask not what your country can do for you ask what you can do for your country.', 'en'),
    ]
    noises = {name: load(args.data/file) for name, file in [('freesound2530','noise_freesound_2530.wav'),('freesound573577','noise_freesound_573577.wav')]}
    # Competing speakers cannot be expected to disappear with generic denoising.
    interference = load(args.data/'speech.wav')
    noises['competing_speech'] = np.roll(interference, 48000)
    noises['white'] = np.random.default_rng(42).normal(0, 1, 16000*30).astype(np.float32)
    rows = []
    for name, file, reference, language in sources:
        clean = load(file)
        clean = clean/max(np.sqrt(np.mean(clean**2)), 1e-8) * .06
        clean = np.pad(clean, (16000, 16000))
        mask = np.abs(clean) > .005
        cases = [('clean', clean)]
        for noise_name, noise in noises.items():
            noise = np.resize(noise, len(clean))
            for snr in (10, 0):
                scale = np.sqrt(np.mean(clean[mask]**2))/max(np.sqrt(np.mean(noise[mask]**2)), 1e-8)*10**(-snr/20)
                cases.append((f'{noise_name}_{snr}db', clean+noise*scale))
        for case, mixed in cases:
            # Apply one gain to both branches; clipping would invalidate SNR comparisons.
            gain = min(1, .95/max(np.max(np.abs(mixed)), 1e-8))
            for enabled in (False, True):
                output, stats = replay(mixed*gain, args.backend if enabled else "none")
                row = {'source':name, 'case':case, 'denoise':enabled, **stats}
                sf.write(args.output/f'{name}_{case}_{enabled}.wav', output, 16000, subtype='PCM_16')
                if model:
                    segments, _ = model.transcribe(output, language=language, beam_size=1, temperature=0, condition_on_previous_text=False, vad_filter=False)
                    text = ''.join(s.text for s in segments).strip()
                    row.update(text=text, reference=reference, cer=cer(reference,text))
                rows.append(row)
                (args.output/'results.json').write_text(json.dumps({'platform':platform.platform(),'rows':rows}, ensure_ascii=False, indent=2))
                print(json.dumps({k:v for k,v in row.items() if k not in ('events','reference')},ensure_ascii=False),flush=True)
    for name, noise in noises.items():
        x=np.resize(noise,16000*8);x=x/max(np.sqrt(np.mean(x*x)),1e-8)*.03
        for enabled in (False,True):
            output,stats=replay(x,args.backend if enabled else "none")
            # Skip startup while measuring steady-state noise attenuation.
            reduction=20*np.log10(max(np.sqrt(np.mean(x[16000:]**2)),1e-9)/max(np.sqrt(np.mean(output[16000:]**2)),1e-9))
            row={'source':'noise_only','case':name,'denoise':enabled,'attenuation_db':float(reduction),**stats}
            rows.append(row)
            print(json.dumps(row),flush=True)
    (args.output/'results.json').write_text(json.dumps({'platform':platform.platform(),'rows':rows},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
