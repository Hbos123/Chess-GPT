/* eslint-disable no-restricted-globals */
// Simple web worker wrapper around stockfish.wasm

import STOCKFISH from 'stockfish.wasm';

let engine: any = null;

async function ensureEngine() {
  if (!engine) {
    engine = await (STOCKFISH as any)();
    engine.onmessage = (line: any) => {
      const text = typeof line === 'string' ? line : (line?.data || String(line));
      (self as any).postMessage({ type: 'sf', data: text });
    };
  }
}

self.onmessage = async (ev: MessageEvent) => {
  const msg = ev.data;
  if (msg?.cmd === 'init') {
    try {
      await ensureEngine();
      (self as any).postMessage({ type: 'ready' });
    } catch (error) {
      console.error('[Stockfish Worker] Init failed:', error);
      (self as any).postMessage({ type: 'error', error: String(error) });
    }
    return;
  }
  if (msg?.cmd === 'send') {
    try {
      await ensureEngine();
      if (engine && engine.postMessage) {
        engine.postMessage(msg.data);
      }
    } catch (error) {
      console.error('[Stockfish Worker] Send failed:', error);
    }
  }
};

export {}; // keep TS happy


