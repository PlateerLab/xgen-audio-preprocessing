/** Electron main-process seam: one subprocess per microphone capture, no shell. */
import { spawn } from 'node:child_process';
import { once } from 'node:events';

export function openPreprocessor({ python, denoise = 'none', onPcm, onEvent = () => {}, onError = () => {} }) {
  const child = spawn(python, ['-m', 'xgen_audio.cli', '--events', '--denoise', denoise], {
    stdio: ['pipe', 'pipe', 'pipe'], env: process.env,
  });
  let stderr = '';
  let ended = false;
  // Attach immediately so a spawn failure cannot become an unhandled rejection.
  const done = new Promise((resolve, reject) => {
    child.once('error', reject);
    child.once('close', (code) => code === 0 ? resolve() : reject(new Error(`Audio worker exited: ${code}`)));
  });
  done.catch(onError);
  child.stdin.on('error', onError);
  child.stdout.on('data', onPcm);
  child.stderr.on('data', (chunk) => {
    stderr += chunk.toString();
    for (;;) {
      const newline = stderr.indexOf('\n');
      if (newline < 0) break;
      const line = stderr.slice(0, newline); stderr = stderr.slice(newline + 1);
      try { onEvent(JSON.parse(line)); } catch { /* native runtime diagnostics are not VAD events */ }
    }
    if (stderr.length > 8192) stderr = stderr.slice(-8192);
  });
  return {
    async push(pcm) {
      if (ended) throw new Error('Audio worker is closed');
      if (!child.stdin.write(pcm)) await once(child.stdin, 'drain');
    },
    async finish() {
      if (!ended) { ended = true; child.stdin.end(); }
      const timer = setTimeout(() => child.kill(), 10_000);
      try { await done; } finally { clearTimeout(timer); }
    },
    cancel() { ended = true; child.kill(); },
  };
}
