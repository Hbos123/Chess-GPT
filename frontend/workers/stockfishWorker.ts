/* eslint-disable no-restricted-globals */
// Simple web worker wrapper around stockfish.wasm
// NOTE: Client-side Stockfish is currently disabled. All analysis uses backend Stockfish.
// To re-enable, uncomment the import and engine initialization.

// import STOCKFISH from 'stockfish.wasm';

let engine: any = null;

async function ensureEngine() {
  // Client-side Stockfish disabled - using backend analysis instead
  console.warn('[Stockfish Worker] Client-side Stockfish is disabled. All analysis uses backend.');
  return;
  
  // if (!engine) {
  //   engine = await (STOCKFISH as any)();
  //   engine.onmessage = (line: any) => {
  //     const text = typeof line === 'string' ? line : line?.data;
  //     (self as any).postMessage({ type: 'sf', data: text });
  //   };
  // }
}

self.onmessage = async (ev: MessageEvent) => {
  const msg = ev.data;
  if (msg?.cmd === 'init') {
    console.log('[Stockfish Worker] Init request received - client-side engine disabled');
    (self as any).postMessage({ type: 'ready' });
    return;
  }
  // Client-side engine disabled - no-op
  console.warn('[Stockfish Worker] Command ignored - client-side engine disabled:', msg);
};

export {}; // keep TS happy


