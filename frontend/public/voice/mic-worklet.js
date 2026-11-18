// Microphone -> 16 kHz, 16-bit mono PCM, in 40 ms chunks, for the shop's voice assistant.
// Runs on the browser's audio thread. The page sends each chunk over the WebSocket.

const TARGET_RATE = 16000;
const CHUNK_SAMPLES = 640; // 40 ms at 16 kHz

class MicProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / TARGET_RATE;
    this.position = 0; // fractional read position into the incoming stream
    this.chunk = new Int16Array(CHUNK_SAMPLES);
    this.filled = 0;
    this.sumSquares = 0;
  }

  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (!channel) return true;

    // Linear-interpolation resampling from the device rate to 16 kHz.
    while (this.position < channel.length - 1) {
      const index = Math.floor(this.position);
      const frac = this.position - index;
      const sample = channel[index] * (1 - frac) + channel[index + 1] * frac;
      const clamped = Math.max(-1, Math.min(1, sample));
      this.chunk[this.filled++] = clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff;
      this.sumSquares += clamped * clamped;

      if (this.filled === CHUNK_SAMPLES) {
        const level = Math.sqrt(this.sumSquares / CHUNK_SAMPLES);
        this.port.postMessage({ pcm: this.chunk.buffer, level }, [this.chunk.buffer]);
        this.chunk = new Int16Array(CHUNK_SAMPLES);
        this.filled = 0;
        this.sumSquares = 0;
      }
      this.position += this.ratio;
    }
    this.position -= channel.length;
    return true;
  }
}

registerProcessor("nexus-mic", MicProcessor);
