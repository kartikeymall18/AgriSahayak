/* Records a spoken question as a 16 kHz mono WAV (no ffmpeg needed on the laptop). Stops by itself when you stop talking. */
const VoiceCap = (() => {
  function toWav(f32, rate) {
    const target = 16000;
    if (rate !== target) {                                        // simple resample, enough for speech
      const ratio = rate / target, n = Math.floor(f32.length / ratio), o = new Float32Array(n);
      for (let i = 0; i < n; i++) { const p = i * ratio, a = Math.floor(p), b = Math.min(a + 1, f32.length - 1); o[i] = f32[a] + (f32[b] - f32[a]) * (p - a); }
      f32 = o;
    }
    const buf = new ArrayBuffer(44 + f32.length * 2), v = new DataView(buf);
    const w = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
    w(0, 'RIFF'); v.setUint32(4, 36 + f32.length * 2, true); w(8, 'WAVE'); w(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
    v.setUint32(24, target, true); v.setUint32(28, target * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); w(36, 'data'); v.setUint32(40, f32.length * 2, true);
    for (let i = 0; i < f32.length; i++) { const s = Math.max(-1, Math.min(1, f32[i])); v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true); }
    return new Blob([buf], { type: 'audio/wav' });
  }

  /** start({maxSec, silenceMs, startTimeoutMs, onLevel}) -> { promise, stop }.  promise resolves {blob, heard, reason, seconds}. */
  function start(opts = {}) {
    const maxSec = opts.maxSec || 12, silenceMs = opts.silenceMs || 1300, startTimeoutMs = opts.startTimeoutMs || 7000;
    let stopFn = () => {};
    const promise = (async () => {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
      const AC = window.AudioContext || window.webkitAudioContext;
      let ctx; try { ctx = new AC({ sampleRate: 16000 }); } catch (e) { ctx = new AC(); }
      const src = ctx.createMediaStreamSource(stream), proc = ctx.createScriptProcessor(4096, 1, 1);
      const chunks = []; let heard = false, done = false, noise = 0, nCal = 0, thr = 0.02;
      const t0 = performance.now(); let lastVoice = t0;
      return new Promise(resolve => {
        const finish = reason => {
          if (done) return; done = true;
          try { proc.disconnect(); src.disconnect(); } catch (e) {} stream.getTracks().forEach(t => t.stop());
          const rate = ctx.sampleRate; try { ctx.close(); } catch (e) {}
          let len = 0; chunks.forEach(c => len += c.length); const pcm = new Float32Array(len); let o = 0; chunks.forEach(c => { pcm.set(c, o); o += c.length; });
          resolve({ blob: toWav(pcm, rate), heard, reason, seconds: len / rate });
        };
        stopFn = () => finish('stopped');
        proc.onaudioprocess = e => {
          const d = e.inputBuffer.getChannelData(0); chunks.push(new Float32Array(d));
          let sum = 0; for (let i = 0; i < d.length; i++) sum += d[i] * d[i]; const rms = Math.sqrt(sum / d.length);
          if (opts.onLevel) opts.onLevel(rms);
          const now = performance.now();
          if (nCal < 3) { noise += rms; nCal++; if (nCal === 3) thr = Math.max(0.012, (noise / 3) * 2.5 + 0.004); }
          else if (rms > thr) { heard = true; lastVoice = now; }
          if (heard && now - lastVoice > silenceMs) finish('silence');
          else if (!heard && now - t0 > startTimeoutMs) finish('no_speech');
          else if (now - t0 > maxSec * 1000) finish('max');
        };
        src.connect(proc); proc.connect(ctx.destination);
      });
    })();
    return { promise, stop: () => stopFn() };
  }
  return { start };
})();
