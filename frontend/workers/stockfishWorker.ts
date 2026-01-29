/* eslint-disable no-restricted-globals */
// Simple web worker wrapper around stockfish.wasm
// Uses stockfish from public folder to avoid Next.js module resolution issues

let engine: any = null;
let engineReady = false;

async function ensureEngine() {
  if (engine && engineReady) return;
  
  try {
    // Use stockfish from public folder - load as a Worker
    // The stockfish.js file in public/stockfish/ handles WASM loading
    const stockfishWorker = new Worker('/stockfish/stockfish.js', { type: 'classic' });
    
    engine = {
      postMessage: (msg: string) => {
        stockfishWorker.postMessage(msg);
      },
      onmessage: null as ((line: any) => void) | null,
      terminate: () => {
        stockfishWorker.terminate();
      }
    };
    
    stockfishWorker.onmessage = (e: MessageEvent) => {
      const text = typeof e.data === 'string' ? e.data : String(e.data || '');
      if (text.trim() === 'readyok') {
        engineReady = true;
        (self as any).postMessage({ type: 'ready' });
      } else if (engine.onmessage) {
        engine.onmessage({ data: text });
      }
    };
    
    stockfishWorker.onerror = (e: ErrorEvent) => {
      console.error('[Stockfish Worker] Error:', e);
      (self as any).postMessage({ type: 'error', error: String(e.error || e.message) });
    };
    
    // Initialize Stockfish
    stockfishWorker.postMessage('uci');
    stockfishWorker.postMessage('isready');
  } catch (error) {
    console.error('[Stockfish Worker] Init failed:', error);
    (self as any).postMessage({ type: 'error', error: String(error) });
  }
}

self.onmessage = async (ev: MessageEvent) => {
  const msg = ev.data;
  if (msg?.cmd === 'init') {
    await ensureEngine();
    return;
  }
  if (msg?.cmd === 'send') {
    if (!engine || !engineReady) {
      await ensureEngine();
    }
    if (engine && engine.postMessage) {
      engine.postMessage(msg.data);
    }
  }
};

export {}; // keep TS happy


