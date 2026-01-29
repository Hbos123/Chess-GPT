/* eslint-disable no-restricted-globals */
// Simple web worker wrapper around stockfish.wasm
// Uses stockfish from public folder to avoid Next.js module resolution issues

let stockfishWorker: Worker | null = null;
let engineReady = false;
let readyQueue: string[] = [];

function initStockfish() {
  if (stockfishWorker) return;
  
  try {
    // Use stockfish-lite.js from public folder (same as StockfishAnalysis component)
    stockfishWorker = new Worker('/stockfish-lite.js', { type: 'classic' });
    
    stockfishWorker.onmessage = (e: MessageEvent) => {
      const text = typeof e.data === 'string' ? e.data : String(e.data || '');
      if (!text || text.trim() === '') return;
      
      // Handle ready response
      if (text.trim() === 'readyok') {
        engineReady = true;
        // Process queued messages
        readyQueue.forEach(msg => {
          if (stockfishWorker) stockfishWorker.postMessage(msg);
        });
        readyQueue = [];
        (self as any).postMessage({ type: 'ready' });
        return;
      }
      
      // Forward Stockfish output to parent
      (self as any).postMessage({ type: 'sf', data: text });
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
    initStockfish();
    return;
  }
  if (msg?.cmd === 'send') {
    if (!stockfishWorker) {
      initStockfish();
    }
    if (!engineReady) {
      readyQueue.push(msg.data);
    } else if (stockfishWorker) {
      stockfishWorker.postMessage(msg.data);
    }
  }
};

export {}; // keep TS happy


