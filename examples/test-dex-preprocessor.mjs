import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { openPreprocessor } from './dex-preprocessor.mjs';

const python = process.env.XGEN_AUDIO_PYTHON;
assert(python, 'Set XGEN_AUDIO_PYTHON');
const raw = readFileSync(process.argv[2]); // PCM16LE extracted from benchmark WAV
const expected = spawnSync(python, ['-m', 'xgen_audio.cli', '--denoise', 'rnnoise'], { input: raw, maxBuffer: 16 * 1024 * 1024 });
assert.equal(expected.status, 0, expected.stderr?.toString());
const chunks = [], events = [], errors = [];
const worker = openPreprocessor({ python, denoise: 'rnnoise', onPcm: (p) => chunks.push(p), onEvent: (e) => events.push(e), onError: (e) => errors.push(String(e)) });
for (let i = 0; i < raw.length; i += 2048) await worker.push(raw.subarray(i, i + 2048));
await worker.finish(); await worker.finish();
const processed = Buffer.concat(chunks);
assert.deepEqual(processed, expected.stdout);
assert.equal(processed.length, raw.length);
assert.equal(errors.length, 0);
assert(events.some(e => e.type === 'speech_start'));
assert(events.some(e => e.type === 'speech_end'));
// VoiceSession sends 640-byte frames; flush its short tail BEFORE sending stop.
const packets = [];
for (let i = 0; i < processed.length; i += 640) packets.push(processed.subarray(i, i + 640));
assert.deepEqual(Buffer.concat(packets), processed);
if (process.argv[3]) writeFileSync(process.argv[3], processed);
console.log(JSON.stringify({ inputBytes: raw.length, outputBytes: processed.length, packets: packets.length, events, errors }));
