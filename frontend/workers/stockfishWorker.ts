/* eslint-disable no-restricted-globals */
// Simple web worker wrapper around stockfish.wasm

import STOCKFISH from 'stockfish.wasm';

let engine: any = null;

async function ensureEngine() {
  if (!engine) {
    engine = await (STOCKFISH as any)();
    engine.onmessage = (line: any) => {
      const text = typeof line === 'string' ? line : line?.data;
      (self as any).postMessage({ type: 'sf', data: text });
    };
  }
}

self.onmessage = async (ev: MessageEvent) => {
  const msg = ev.data;
  if (msg?.cmd === 'init') {
    await ensureEngine();
    (self as any).postMessage({ type: 'ready' });
    return;
  }
  if (msg?.cmd === 'send') {
    await ensureEngine();
    engine.postMessage(msg.data);
  }
};

export {}; // keep TS happy


