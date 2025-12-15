import { Chess } from 'chess.js';

let worker: Worker | null = null;
let readyPromise: Promise<void> | null = null;

function initWorker(): Promise<void> {
  if (readyPromise) return readyPromise;
  readyPromise = new Promise((resolve) => {
    // @ts-ignore - bundlers handle worker paths
    worker = new Worker(new URL('../workers/stockfishWorker.ts', import.meta.url), { type: 'module' });
    worker!.onmessage = (e: MessageEvent) => {
      if (e.data?.type === 'ready') resolve();
    };
    worker!.postMessage({ cmd: 'init' });
  });
  return readyPromise;
}

type Info = { depth?: number; multipv?: number; score?: { cp?: number; mate?: number }; pv?: string[] };

export async function analyzePositionWasm(fen: string, lines: number = 3, depth: number = 16) {
  await initWorker();
  const infos: Info[] = [];
  let bestEval = 0;
  let bestPv: string[] = [];

  const listeners: ((msg: string) => void)[] = [];
  const onMessage = (ev: MessageEvent) => {
    const text: string = ev.data?.data || '';
    if (!text) return;
    if (text.startsWith('info')) {
      // Parse UCI info
      const tokens = text.split(/\s+/);
      const obj: Info = {};
      for (let i = 0; i < tokens.length; i++) {
        const t = tokens[i];
        if (t === 'depth') obj.depth = parseInt(tokens[++i], 10);
        if (t === 'multipv') obj.multipv = parseInt(tokens[++i], 10);
        if (t === 'score') {
          const type = tokens[++i];
          const val = parseInt(tokens[++i], 10);
          obj.score = type === 'cp' ? { cp: val } : { mate: val };
        }
        if (t === 'pv') {
          obj.pv = tokens.slice(i + 1);
          break;
        }
      }
      if (obj.multipv && obj.pv && (obj.score?.cp !== undefined || obj.score?.mate !== undefined)) {
        infos[obj.multipv - 1] = obj;
        if (obj.multipv === 1) {
          bestEval = obj.score?.cp !== undefined ? obj.score!.cp! : (obj.score?.mate! > 0 ? 10000 : -10000);
          bestPv = obj.pv || [];
        }
      }
    }
  };
  worker!.addEventListener('message', onMessage as any);
  // Send position and go
  worker!.postMessage({ cmd: 'send', data: `ucinewgame` });
  worker!.postMessage({ cmd: 'send', data: `isready` });
  worker!.postMessage({ cmd: 'send', data: `setoption name MultiPV value ${lines}` });
  worker!.postMessage({ cmd: 'send', data: `position fen ${fen}` });
  worker!.postMessage({ cmd: 'send', data: `go depth ${depth}` });

  // Wait a bit longer than needed – poll for best pv conclusion using a timeout
  await new Promise((resolve) => setTimeout(resolve, Math.max(800, depth * 80)));
  worker!.removeEventListener('message', onMessage as any);
  worker!.postMessage({ cmd: 'send', data: 'stop' });

  // Convert PV UCIs to SAN
  const toSAN = (uciPv: string[]) => {
    const board = new Chess(fen);
    const moves: string[] = [];
    for (const u of uciPv) {
      try {
        const from = u.substring(0, 2);
        const to = u.substring(2, 4);
        const promo = u.length > 4 ? u.substring(4, 5) : undefined;
        const move = board.move({ from, to, promotion: promo as any });
        if (!move) break;
        moves.push(move.san);
      } catch {
        break;
      }
    }
    return moves.join(' ');
  };

  const candidates = infos
    .filter(Boolean)
    .slice(0, lines)
    .map((obj, idx) => {
      const cp = obj.score?.cp !== undefined ? obj.score!.cp! : (obj.score?.mate! > 0 ? 10000 : -10000);
      const pvSan = toSAN(obj.pv || []);
      const uciFirst = obj.pv?.[0] || '';
      return {
        move: uciFirst ? new Chess(fen).move({ from: uciFirst.substring(0, 2), to: uciFirst.substring(2, 4), promotion: uciFirst[4] as any })?.san || uciFirst : '',
        uci: uciFirst,
        eval_cp: cp,
        pv_san: pvSan,
        depth,
      };
    });

  const bestMove = candidates[0]?.move || '';
  return {
    fen,
    eval_cp: bestEval,
    best_move: bestMove,
    candidate_moves: candidates,
    phase: 'unknown',
    white_analysis: {},
    black_analysis: {},
  } as any;
}


