#!/usr/bin/env python3

import sys
import os
import io
import asyncio
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional

script_dir = Path(__file__).parent
backend_dir = script_dir.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")

import chess
import chess.pgn
import chess.engine


def get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    
    if not supabase_url or not supabase_key:
        print("❌ Missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY")
        return None
    
    from supabase_client import SupabaseClient
    print(f"📦 Using Supabase: {supabase_url}")
    return SupabaseClient(supabase_url, supabase_key)


def get_stockfish_path() -> Optional[str]:
    possible_paths = [
        os.path.join(backend_dir, "stockfish"),
        os.path.join(backend_dir, "stockfish.exe"),
        "/usr/local/bin/stockfish",
        "/usr/bin/stockfish",
        "stockfish",
    ]
    
    for path in possible_paths:
        if os.path.exists(path) and os.access(path, os.X_OK):
            return path
        if os.path.exists(path) and not path.endswith(".exe"):
            try:
                os.chmod(path, os.stat(path).st_mode | 0o111)
                if os.access(path, os.X_OK):
                    return path
            except:
                pass
    
    import shutil
    stockfish_cmd = shutil.which("stockfish")
    if stockfish_cmd:
        return stockfish_cmd
    
    print("⚠️  Stockfish not found")
    return None


async def initialize_engine(stockfish_path: str) -> Optional[chess.engine.SimpleEngine]:
    try:
        transport, engine = await chess.engine.popen_uci(stockfish_path)
        await engine.configure({"Threads": 1, "Hash": 32})
        print(f"✅ Stockfish initialized")
        return engine
    except Exception as e:
        print(f"❌ Failed to initialize Stockfish: {e}")
        return None


async def best_move_for_fen(engine: chess.engine.SimpleEngine, fen: str, depth: int) -> tuple[str, str, float]:
    board = chess.Board(fen)
    info = await engine.analyse(board, chess.engine.Limit(depth=depth), multipv=1)
    pv = info["pv"]
    move = pv[0]
    best_san = board.san(move)
    best_uci = move.uci()
    score = info["score"].white()
    eval_cp = score.score(mate_score=10000) if not score.is_mate() else (10000 if score.mate() > 0 else -10000)
    return best_san, best_uci, float(eval_cp)


def infer_category(rec: Dict) -> str:
    cat = str(rec.get("category") or "").strip().lower()
    if cat in ("blunder", "mistake", "inaccuracy"):
        return cat
    if rec.get("is_blunder"):
        return "blunder"
    if rec.get("is_mistake"):
        return "mistake"
    if rec.get("is_inaccuracy"):
        return "inaccuracy"
    analyse = rec.get("analyse") if isinstance(rec.get("analyse"), dict) else {}
    tags = analyse.get("tags", []) if isinstance(analyse.get("tags"), list) else []
    tags_norm = set()
    for t in tags:
        if isinstance(t, str):
            tags_norm.add(t.strip().lower())
        elif isinstance(t, dict):
            nm = t.get("tag_name") or t.get("name") or t.get("tag")
            if isinstance(nm, str):
                tags_norm.add(nm.strip().lower())
    if "blunder" in tags_norm:
        return "blunder"
    if "mistake" in tags_norm:
        return "mistake"
    if "inaccuracy" in tags_norm:
        return "inaccuracy"
    return ""


def extract_tag_names(tags) -> List[str]:
    out = []
    for t in (tags or []):
        if isinstance(t, str) and t.strip():
            out.append(t.strip())
        elif isinstance(t, dict):
            nm = t.get("tag_name") or t.get("name") or t.get("tag")
            if isinstance(nm, str) and nm.strip():
                out.append(nm.strip())
    return out


async def backfill_user_positions_from_pgn(
    user_id: str,
    supabase_client,
    engine: chess.engine.SimpleEngine,
    max_games: int = 200,
    max_positions_per_game: int = 30,
    min_cp_loss: float = 100,
    verify_depth: int = 14
) -> Dict[str, Any]:
    print(f"\n🔄 Processing user: {user_id}")
    
    try:
        def fetch_games():
            q = (
                supabase_client.client.table("games")
                .select("id,user_id,game_date,opening_name,user_color,pgn,game_review,review_type,analyzed_at,archived_at,compressed_at")
                .eq("user_id", user_id)
                .not_.is_("analyzed_at", "null")
                .is_("archived_at", "null")
                .order("game_date", desc=True)
                .limit(max_games)
            )
            try:
                q = q.is_("compressed_at", "null")
            except Exception:
                pass
            return q.execute().data or []
        
        games = await asyncio.to_thread(fetch_games)
        if not games:
            return {"status": "ok", "user_id": user_id, "games": 0, "positions_saved": 0, "note": "No analyzed games found"}
        
        print(f"   📚 Found {len(games)} games")
        
        saved_total = 0
        games_processed = 0
        games_with_positions = 0
        
        for idx, g in enumerate(games, 1):
            games_processed += 1
            game_id = g.get("id")
            pgn = g.get("pgn")
            game_review = g.get("game_review") or {}
            
            if not isinstance(game_review, dict):
                continue
            
            ply_records = game_review.get("ply_records", [])
            if not isinstance(ply_records, list) or not ply_records:
                continue
            
            if not isinstance(pgn, str) or not pgn.strip():
                continue
            
            try:
                game_obj = chess.pgn.read_game(io.StringIO(pgn))
                if not game_obj:
                    continue
                
                board = game_obj.board()
                fen_befores: List[str] = []
                uci_moves: List[str] = []
                san_moves: List[str] = []
                side_moveds: List[str] = []
                
                ply_no = 0
                for mv in game_obj.mainline_moves():
                    ply_no += 1
                    fen_befores.append(board.fen())
                    uci_moves.append(mv.uci())
                    san_moves.append(board.san(mv))
                    side_moveds.append("white" if board.turn else "black")
                    board.push(mv)
            except Exception as e:
                print(f"   ⚠️ Error parsing PGN for game {game_id}: {e}")
                continue
            
            meta = game_review.get("metadata", {}) if isinstance(game_review.get("metadata"), dict) else {}
            player_color = (meta.get("player_color") or g.get("user_color") or "white")
            player_color = "black" if str(player_color).lower().strip() == "black" else "white"
            
            positions_to_save = []
            
            for rec_idx, rec in enumerate(ply_records):
                if not isinstance(rec, dict):
                    continue
                
                ply = rec.get("ply")
                try:
                    ply_i = int(ply) if ply is not None else (rec_idx + 1)
                except Exception:
                    ply_i = rec_idx + 1
                
                if ply_i <= 0 or ply_i > len(fen_befores):
                    continue
                
                category = infer_category(rec)
                if category not in ("blunder", "mistake"):
                    continue
                
                cp_loss = rec.get("cp_loss")
                try:
                    cp_loss_f = float(cp_loss or 0)
                except Exception:
                    cp_loss_f = 0.0
                
                if cp_loss_f < min_cp_loss:
                    continue
                
                side_moved = rec.get("side_moved") or side_moveds[ply_i - 1]
                error_side = "player" if side_moved == player_color else "opponent"
                
                fen_before = rec.get("fen_before") or fen_befores[ply_i - 1]
                move_san = rec.get("san") or rec.get("move_san") or san_moves[ply_i - 1]
                move_uci = rec.get("uci") or uci_moves[ply_i - 1]
                
                raw_before = rec.get("raw_before", {}) if isinstance(rec.get("raw_before"), dict) else {}
                raw_after = rec.get("raw_after", {}) if isinstance(rec.get("raw_after"), dict) else {}
                analyse = rec.get("analyse", {}) if isinstance(rec.get("analyse"), dict) else {}
                
                tags_start = extract_tag_names(raw_before.get("tags")) if raw_before else []
                tags_after_played = extract_tag_names(raw_after.get("tags")) if raw_after else extract_tag_names(analyse.get("tags"))
                tags_gained = list(set(tags_after_played) - set(tags_start))
                tags_lost = list(set(tags_start) - set(tags_after_played))
                
                try:
                    best_san, best_uci, eval_cp = await best_move_for_fen(engine, fen_before, verify_depth)
                except Exception as e:
                    print(f"   ⚠️ Error computing best move for game {game_id} ply {ply_i}: {e}")
                    continue
                
                fen_parts = fen_before.split()
                side_to_move = "white" if len(fen_parts) > 1 and fen_parts[1] == "w" else "black"
                
                positions_to_save.append({
                    "fen": fen_before,
                    "side_to_move": side_to_move,
                    "from_game_id": game_id,
                    "source_ply": ply_i,
                    "move_san": move_san,
                    "move_uci": move_uci,
                    "best_move_san": best_san,
                    "best_move_uci": best_uci,
                    "eval_cp": eval_cp,
                    "cp_loss": cp_loss_f,
                    "phase": rec.get("phase"),
                    "opening_name": g.get("opening_name") or None,
                    "is_critical": cp_loss_f >= 200,
                    "is_error": True,
                    "error_category": category,
                    "error_side": error_side,
                    "error_note": f"{category.capitalize()}: {move_san} (cp_loss: {round(cp_loss_f, 1)})",
                    "tags_start": tags_start,
                    "tags_after_played": tags_after_played,
                    "tags_after_best": [],
                    "tags_gained": tags_gained,
                    "tags_lost": tags_lost,
                    "time_spent_s": rec.get("time_spent_s"),
                    "piece_blundered": rec.get("piece_blundered"),
                    "piece_best_move": rec.get("piece_best_move"),
                })
                
                if max_positions_per_game and len(positions_to_save) >= max_positions_per_game:
                    break
            
            if not positions_to_save:
                continue
            
            games_with_positions += 1
            
            saved_count = await asyncio.to_thread(
                supabase_client.batch_upsert_positions,
                user_id,
                positions_to_save,
                game_id
            )
            saved_total += int(saved_count or 0)
            
            if idx % 10 == 0:
                print(f"   📊 Processed {idx}/{len(games)} games, {games_with_positions} with positions, {saved_total} positions saved")
        
        print(f"   ✅ Processed {games_processed} games")
        print(f"   ✅ {games_with_positions} games had positions")
        print(f"   ✅ {saved_total} positions saved")
        
        return {
            "status": "ok",
            "user_id": user_id,
            "games": len(games),
            "games_processed": games_processed,
            "games_with_positions": games_with_positions,
            "positions_saved": saved_total,
        }
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "user_id": user_id, "error": str(e)}


async def main_async(args):
    supabase_client = get_supabase_client()
    if not supabase_client:
        return
    
    print("✅ Connected to database")
    
    stockfish_path = get_stockfish_path()
    if not stockfish_path:
        return
    
    engine = await initialize_engine(stockfish_path)
    if not engine:
        return
    
    try:
        print("🔍 Finding all users with analyzed games...")
        if hasattr(supabase_client, 'client'):
            result = supabase_client.client.table("games")\
                .select("user_id")\
                .not_.is_("game_review", "null")\
                .execute()
            user_ids = list(set([g.get("user_id") for g in (result.data or []) if g.get("user_id")]))
        else:
            result = supabase_client._execute_query(
                "SELECT DISTINCT user_id FROM public.games WHERE game_review IS NOT NULL",
                ()
            )
            user_ids = [row["user_id"] for row in result if row.get("user_id")]
        
        print(f"📊 Found {len(user_ids)} users")
        
        total_saved = 0
        for i, user_id in enumerate(user_ids, 1):
            print(f"\n[{i}/{len(user_ids)}] Processing user {user_id[:8]}...")
            result = await backfill_user_positions_from_pgn(
                user_id,
                supabase_client,
                engine,
                max_games=args.max_games,
                max_positions_per_game=args.max_positions_per_game,
                min_cp_loss=args.min_cp_loss,
                verify_depth=args.verify_depth
            )
            total_saved += result.get("positions_saved", 0)
        
        print(f"\n✅ Backfill complete: {total_saved} positions saved across {len(user_ids)} users")
    finally:
        if engine:
            try:
                await engine.quit()
            except:
                pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", type=str, help="Specific user ID (optional)")
    parser.add_argument("--max-games", type=int, default=200)
    parser.add_argument("--max-positions-per-game", type=int, default=30)
    parser.add_argument("--min-cp-loss", type=float, default=100.0)
    parser.add_argument("--verify-depth", type=int, default=14)
    
    args = parser.parse_args()
    
    if args.user_id:
        async def run_single():
            supabase_client = get_supabase_client()
            if not supabase_client:
                return
            stockfish_path = get_stockfish_path()
            if not stockfish_path:
                return
            engine = await initialize_engine(stockfish_path)
            if not engine:
                return
            try:
                result = await backfill_user_positions_from_pgn(
                    args.user_id, supabase_client, engine,
                    args.max_games, args.max_positions_per_game,
                    args.min_cp_loss, args.verify_depth
                )
                print(f"\n✅ Complete: {result.get('positions_saved', 0)} positions saved")
            finally:
                if engine:
                    try:
                        await engine.quit()
                    except:
                        pass
        asyncio.run(run_single())
    else:
        asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
