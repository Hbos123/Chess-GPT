"""
Profile indexing pipeline manager.
Coordinates game fetching, progress tracking, and summary stats used by the UI.
"""

from __future__ import annotations

import asyncio
import json
import io
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Callable, Awaitable
import statistics
import time
import math
from collections import defaultdict, Counter

import chess
import chess.engine

try:
    from game_fetcher import GameFetcher
except ImportError:  # pragma: no cover
    from backend.game_fetcher import GameFetcher


def _utc_now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _utc_from_timestamp(ts: float) -> str:
    return datetime.utcfromtimestamp(ts).isoformat() + "Z"


@dataclass
class ProfileIndexStatus:
    state: str = "idle"  # idle | queued | fetching | complete | error
    message: str = "Not started"
    total_accounts: int = 0
    completed_accounts: int = 0
    total_games_estimate: int = 0
    games_indexed: int = 0
    progress_percent: int = 0
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    last_updated: Optional[str] = None
    last_error: Optional[str] = None
    accounts: List[Dict[str, Any]] = field(default_factory=list)
    target_games: int = 50
    next_poll_at: Optional[str] = None
    background_active: bool = False
    light_analyzed_games: int = 0
    deep_analyzed_games: int = 0

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["progress_percent"] = self.progress_percent
        return payload


PIECE_LABELS = {
    chess.PAWN: "pawn",
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
    chess.KING: "king",
}

ADVANTAGE_BUCKETS = [
    ("losing", -math.inf, -200),
    ("slightly_worse", -200, -80),
    ("balanced", -80, 80),
    ("slightly_better", 80, 200),
    ("winning", 200, math.inf),
]

TIME_BUCKETS = [
    ("<3s", 0, 3),
    ("3-10s", 3, 10),
    ("10-30s", 10, 30),
    ("30s+", 30, math.inf),
]

def _bucket_advantage(value: float) -> str:
    for name, start, end in ADVANTAGE_BUCKETS:
        if start <= value < end:
            return name
    return "balanced"


def _bucket_time(seconds: Optional[float]) -> Optional[str]:
    if seconds is None:
        return None
    for name, start, end in TIME_BUCKETS:
        if start <= seconds < end:
            return name
    return TIME_BUCKETS[-1][0]


def _bucket_rating(player_rating: Optional[int], opponent_rating: Optional[int]) -> str:
    if player_rating is None or opponent_rating is None:
        return "unknown"
    diff = opponent_rating - player_rating
    if diff <= -150:
        return "lower_rated"
    if diff >= 150:
        return "higher_rated"
    return "similar_rating"


def _piece_name_from_move(fen_before: Optional[str], move_uci: Optional[str]) -> str:
    if not fen_before or not move_uci:
        return "unknown"
    try:
        board = chess.Board(fen_before)
        move = chess.Move.from_uci(move_uci)
        piece = board.piece_at(move.from_square)
        if not piece:
            return "unknown"
        return PIECE_LABELS.get(piece.piece_type, "unknown")
    except Exception:
        return "unknown"


def _infer_position_types(board: Optional[chess.Board]) -> List[str]:
    if board is None:
        return []
    types: List[str] = []
    open_files = sum(
        1
        for file_idx in range(8)
        if all(
            board.piece_at(sq) not in (chess.Piece(chess.PAWN, chess.WHITE), chess.Piece(chess.PAWN, chess.BLACK))
            for sq in chess.SquareSet(chess.BB_FILES[file_idx])
        )
    )
    if open_files >= 2:
        types.append("open")
    elif open_files == 1:
        types.append("semi_open")
    else:
        types.append("closed")

    # Detect IQP by checking isolated pawns on files d/e
    for file_name in ["d", "e"]:
        file_idx = chess.FILE_NAMES.index(file_name)
        pawns = [sq for sq in chess.SquareSet(chess.BB_FILES[file_idx]) if board.piece_at(sq) == chess.Piece(chess.PAWN, chess.WHITE)]
        pawns += [sq for sq in chess.SquareSet(chess.BB_FILES[file_idx]) if board.piece_at(sq) == chess.Piece(chess.PAWN, chess.BLACK)]
        if pawns:
            adj_files = []
            if file_idx - 1 >= 0:
                adj_files.append(file_idx - 1)
            if file_idx + 1 < 8:
                adj_files.append(file_idx + 1)
            isolated = True
            for adj in adj_files:
                if any(
                    board.piece_at(sq) == chess.Piece(chess.PAWN, chess.WHITE)
                    or board.piece_at(sq) == chess.Piece(chess.PAWN, chess.BLACK)
                    for sq in chess.SquareSet(chess.BB_FILES[adj])
                ):
                    isolated = False
                    break
            if isolated:
                types.append("iqp")
                break

    # Opposite-side castling
    white_castled = board.king(chess.WHITE) in [chess.G1, chess.C1]
    black_castled = board.king(chess.BLACK) in [chess.G8, chess.C8]
    if white_castled and black_castled:
        if board.king(chess.WHITE) == chess.G1 and board.king(chess.BLACK) == chess.C8:
            types.append("opposite_castle")
        if board.king(chess.WHITE) == chess.C1 and board.king(chess.BLACK) == chess.G8:
            types.append("opposite_castle")

    if len(board.piece_map()) <= 10:
        types.append("endgame_like")

    return types

class ProfileIndexingManager:
    """Centralized manager that orchestrates profile indexing jobs."""

    def __init__(
        self,
        game_fetcher: GameFetcher,
        max_cached_games: int = 200,
        max_games_per_account: int = 40,
        months_back: int = 6,
        supabase_client: Optional[Any] = None,
        review_fn: Optional[Callable[..., Awaitable[Dict[str, Any]]]] = None,
        engine_queue: Optional[Any] = None,
        engine_instance: Optional[Any] = None,
    ) -> None:
        self.game_fetcher = game_fetcher
        self.max_cached_games = max_cached_games
        self.max_games_per_account = max_games_per_account
        self.months_back = months_back
        self.supabase_client = supabase_client
        self.review_fn = review_fn
        self.engine_queue = engine_queue
        self.engine_instance = engine_instance

        self._status: Dict[str, ProfileIndexStatus] = {}
        self._games: Dict[str, List[Dict[str, Any]]] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._analysis_tasks: Dict[str, asyncio.Task] = {}
        self._light_results: Dict[str, Dict[str, Any]] = {}
        self._deep_completed: Dict[str, set] = {}
        self._background_tasks: Dict[str, asyncio.Task] = {}
        self._next_poll_timestamp: Dict[str, float] = {}
        self._last_activity: Dict[str, float] = {}
        self._stats_cache: Dict[str, Dict[str, Any]] = {}
        self._lesson_history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self._lock = asyncio.Lock()

        self.prefs_dir = Path("backend/cache/profile_prefs")
        self.prefs_dir.mkdir(parents=True, exist_ok=True)

        # Background indexing configuration
        self.background_target_games = 50
        self.background_interval_seconds = 20 * 60  # 20 minutes
        self.background_batch_size = max(5, self.max_games_per_account // 3)
        self.light_analysis_depth = 12
        self.deep_analysis_depth = 20

    # ---------------------------------------------------------------------
    # Public getters
    # ---------------------------------------------------------------------
    def get_status(self, user_id: str) -> Dict[str, Any]:
        status = self._status.get(user_id)
        if not status:
            return ProfileIndexStatus().to_dict()
        return status.to_dict()

    def get_games(self, user_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        games = self._games.get(user_id, [])
        if limit is not None:
            return games[:limit]
        return games

    def get_highlights(self, user_id: str) -> List[Dict[str, Any]]:
        games = self._games.get(user_id, [])
        if not games:
            return []

        highlights: List[Dict[str, Any]] = []
        total_games = len(games)
        wins_last_10 = sum(1 for g in games[:10] if g.get("result") == "win")
        highlights.append(
            {
                "label": "Games indexed",
                "value": str(total_games),
                "platform": "All",
            }
        )
        highlights.append(
            {
                "label": "Win rate (last 10)",
                "value": f"{round((wins_last_10 / max(1, min(10, total_games))) * 100)}%",
                "platform": "All",
            }
        )

        latest_by_platform: Dict[str, Dict[str, Any]] = {}
        for game in games:
            platform = game.get("platform")
            if platform and platform not in latest_by_platform:
                latest_by_platform[platform] = game

        for platform, game in latest_by_platform.items():
            rating = game.get("player_rating")
            if rating:
                highlights.append(
                    {
                        "label": "Latest rating",
                        "value": str(rating),
                        "platform": platform.title(),
                    }
                )

        return highlights

    def get_stats(self, user_id: str) -> Dict[str, Any]:
        if user_id not in self._stats_cache:
            games = self._games.get(user_id)
            if games:
                stats = self._compute_stats(games)
                self._stats_cache[user_id] = stats
                if self.supabase_client:
                    self.supabase_client.save_profile_stats(user_id, stats)
            elif self.supabase_client:
                stored = self.supabase_client.get_profile_stats(user_id)
                if stored and stored.get("stats"):
                    self._stats_cache[user_id] = stored["stats"]
                    return stored["stats"]

        return self._stats_cache.get(user_id, {})

    # ---------------------------------------------------------------------
    # Preferences persistence (local fallback)
    # ---------------------------------------------------------------------
    def load_preferences(self, user_id: str) -> Optional[Dict[str, Any]]:
        file_path = self.prefs_dir / f"{user_id}.json"
        if not file_path.exists():
            return None
        try:
            return json.loads(file_path.read_text())
        except Exception:
            return None

    def save_preferences(self, user_id: str, prefs: Dict[str, Any]) -> None:
        file_path = self.prefs_dir / f"{user_id}.json"
        file_path.write_text(json.dumps(prefs, indent=2))
        if self.supabase_client and user_id:
            try:
                updates = {
                    "profile_setup_complete": bool(prefs.get("accounts")),
                    "linked_accounts": prefs.get("accounts", []),
                    "time_controls": prefs.get("time_controls", []),
                }
                self.supabase_client.update_profile(user_id, updates)
            except Exception as exc:
                print(f"⚠️  Supabase profile update failed for {user_id}: {exc}")

    # ---------------------------------------------------------------------
    # Indexing orchestration
    # ---------------------------------------------------------------------
    async def start_indexing(
        self,
        user_id: str,
        accounts: Sequence[Dict[str, str]],
        time_controls: Sequence[str],
    ) -> None:
        """Start (or restart) indexing for a user."""
        normalized_accounts = [
            {
                "platform": acc.get("platform", "chesscom"),
                "username": acc.get("username", "").strip(),
            }
            for acc in accounts
            if acc.get("username")
        ]

        if not normalized_accounts:
            # Nothing to index. Reset status.
            self._status[user_id] = ProfileIndexStatus(
                state="idle",
                message="Add at least one account to index games.",
                accounts=[],
            )
            self._games[user_id] = []
            return

        status = ProfileIndexStatus(
            state="queued",
            message="Queued for fetching…",
            total_accounts=len(normalized_accounts),
            accounts=normalized_accounts,
            total_games_estimate=len(normalized_accounts) * self.max_games_per_account,
            started_at=_utc_now(),
            last_updated=_utc_now(),
        )
        self._status[user_id] = status

        async with self._lock:
            existing_task = self._tasks.get(user_id)
            if existing_task and not existing_task.done():
                existing_task.cancel()
            task = asyncio.create_task(
                self._run_indexing(
                    user_id=user_id,
                    accounts=normalized_accounts,
                    time_controls=[tc.lower() for tc in time_controls],
                )
            )
            self._tasks[user_id] = task

    async def _run_indexing(
        self,
        user_id: str,
        accounts: Sequence[Dict[str, str]],
        time_controls: Sequence[str],
        *,
        max_games_override: Optional[int] = None,
        background: bool = False,
    ) -> None:
        status = self._status[user_id]
        status.target_games = self.background_target_games
        status.games_indexed = 0
        status.completed_accounts = 0
        status.finished_at = None
        status.last_error = None
        status.last_updated = _utc_now()
        status.background_active = background
        if background:
            status.state = "background"
            status.message = "Quietly refreshing games…"
        else:
            status.state = "fetching"
            status.message = "Fetching games…"
            self._games[user_id] = []
        if user_id not in self._games:
            self._games[user_id] = []

        try:
            for account in accounts:
                status.message = f"Fetching {account['username']} ({account['platform']})"
                status.last_updated = _utc_now()

                platform = "chess.com" if account["platform"] == "chesscom" else "lichess"
                try:
                    fetched = await self.game_fetcher.fetch_games(
                        username=account["username"],
                        platform=platform,
                        max_games=max_games_override or self.max_games_per_account,
                        months_back=self.months_back,
                    )
                except Exception as exc:
                    status.state = "error"
                    status.last_error = str(exc)
                    status.message = f"Failed to fetch {account['username']}: {exc}"
                    status.last_updated = _utc_now()
                    return

                filtered = self._filter_games_by_time_control(fetched, time_controls)
                self._games[user_id].extend(filtered)
                status.games_indexed += len(filtered)
                status.completed_accounts += 1
                status.progress_percent = self._compute_progress_percent(status)
                status.last_updated = _utc_now()

            self._games[user_id] = self._dedupe_and_sort_games(self._games[user_id])
            self._games[user_id] = self._games[user_id][: self.max_cached_games]
            current_ids = {
                game.get("game_id") or f"{game.get('platform')}::{game.get('date')}::{game.get('opponent_name')}"
                for game in self._games[user_id]
            }
            if user_id in self._light_results:
                self._light_results[user_id] = {
                    gid: summary
                    for gid, summary in self._light_results[user_id].items()
                    if gid in current_ids
                }
            if user_id in self._deep_completed:
                self._deep_completed[user_id] = {
                    gid for gid in self._deep_completed[user_id] if gid in current_ids
                }
            if status:
                status.light_analyzed_games = len(self._light_results.get(user_id, {}))
                status.deep_analyzed_games = len(self._deep_completed.get(user_id, set()))
            status.state = "complete" if not background else "idle"
            status.background_active = False
            status.message = (
                f"Indexed {status.games_indexed} game(s)."
                if not background
                else "Background refresh complete."
            )
            status.finished_at = _utc_now()
            status.progress_percent = 100 if status.games_indexed else status.progress_percent
            status.last_updated = _utc_now()
            self._refresh_stats(user_id)
            self._schedule_analysis(user_id)

        finally:
            if not background:
                self._tasks.pop(user_id, None)

    @staticmethod
    def _filter_games_by_time_control(
        games: Sequence[Dict[str, Any]],
        allowed_time_controls: Sequence[str],
    ) -> List[Dict[str, Any]]:
        if not allowed_time_controls:
            return list(games)

        allowed = {tc.lower() for tc in allowed_time_controls}
        filtered: List[Dict[str, Any]] = []
        for game in games:
            time_category = str(game.get("time_category", "")).lower()
            if time_category in allowed:
                filtered.append(game)
        return filtered

    @staticmethod
    def _compute_progress_percent(status: ProfileIndexStatus) -> int:
        if status.total_games_estimate:
            return max(
                1,
                min(100, round((status.games_indexed / status.total_games_estimate) * 100)),
            )
        if status.total_accounts:
            return max(
                1,
                min(100, round((status.completed_accounts / status.total_accounts) * 100)),
            )
        return 0

    def _refresh_stats(self, user_id: str) -> None:
        games = self._games.get(user_id, [])
        stats = self._compute_stats(games)
        self._stats_cache[user_id] = stats
        if self.supabase_client:
            self.supabase_client.save_profile_stats(user_id, stats)

    def _compute_stats(self, games: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        total_games = len(games)
        if total_games == 0:
            return {
                "overall": {
                    "total_games": 0,
                    "wins": 0,
                    "losses": 0,
                    "draws": 0,
                    "win_rate": 0,
                    "average_accuracy": None,
                    "blunder_rate": None,
                    "mistake_rate": None,
                },
                "openings": {"top": [], "bottom": []},
                "tags": {"best": [], "worst": []},
                "phases": {"opening": None, "middlegame": None, "endgame": None},
                "personality": {"notes": [], "tendencies": []},
            }

        wins = sum(1 for g in games if g.get("result") == "win")
        draws = sum(1 for g in games if g.get("result") == "draw")
        losses = total_games - wins - draws
        accuracies = [g.get("player_accuracy") for g in games if g.get("player_accuracy") is not None]
        avg_accuracy = round(statistics.mean(accuracies), 1) if accuracies else None

        blunder_counts = [g.get("blunder_count") for g in games if g.get("blunder_count") is not None]
        mistake_counts = [g.get("mistake_count") for g in games if g.get("mistake_count") is not None]
        blunder_rate = round(statistics.mean(blunder_counts), 2) if blunder_counts else None
        mistake_rate = round(statistics.mean(mistake_counts), 2) if mistake_counts else None

        opening_buckets: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"games": 0, "wins": 0, "accuracies": [], "blunders": []})
        tag_buckets: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"games": 0, "wins": 0, "cp_loss": []})
        phase_sums = defaultdict(list)

        for game in games:
            opening_key, opening_label = self._normalize_opening(
                eco=game.get("eco"),
                opening_name=game.get("opening_name") or game.get("opening"),
            )
            bucket = opening_buckets[opening_key]
            bucket.setdefault("label", opening_label)
            bucket["games"] += 1
            if game.get("result") == "win":
                bucket["wins"] += 1
            if game.get("player_accuracy") is not None:
                bucket["accuracies"].append(game["player_accuracy"])
            if game.get("blunder_count") is not None:
                bucket["blunders"].append(game["blunder_count"])

            phase_accuracy = game.get("phase_accuracy") or {}
            for phase in ("opening", "middlegame", "endgame"):
                if phase_accuracy.get(phase) is not None:
                    phase_sums[phase].append(phase_accuracy[phase])

            tags = game.get("tags") or []
            if isinstance(tags, dict):
                tags = tags.keys()
            for tag in tags:
                tag_name = tag if isinstance(tag, str) else tag.get("name", "unknown")
                tag_bucket = tag_buckets[tag_name]
                tag_bucket["games"] += 1
                if game.get("result") == "win":
                    tag_bucket["wins"] += 1
                cp_loss = None
                if isinstance(tag, dict):
                    cp_loss = tag.get("cp_loss")
                if cp_loss is not None:
                    tag_bucket["cp_loss"].append(cp_loss)

        opening_stats = []
        for key, bucket in opening_buckets.items():
            games_played = bucket["games"]
            win_rate = round((bucket["wins"] / games_played) * 100, 1) if games_played else 0
            avg_acc = round(statistics.mean(bucket["accuracies"]), 1) if bucket["accuracies"] else None
            avg_blunders = round(statistics.mean(bucket["blunders"]), 2) if bucket["blunders"] else None
            opening_stats.append(
                {
                    "name": bucket.get("label") or key or "Unknown",
                    "games": games_played,
                    "win_rate": win_rate,
                    "average_accuracy": avg_acc,
                    "blunder_rate": avg_blunders,
                }
            )
        opening_stats.sort(key=lambda o: (o["win_rate"], o["games"]), reverse=True)
        top_openings = opening_stats[:3]
        bottom_openings = list(reversed(opening_stats[-3:])) if opening_stats else []

        tag_stats = []
        for name, bucket in tag_buckets.items():
            games_played = bucket["games"]
            win_rate = round((bucket["wins"] / games_played) * 100, 1) if games_played else 0
            avg_cp = round(statistics.mean(bucket["cp_loss"]), 1) if bucket["cp_loss"] else None
            tag_stats.append(
                {
                    "name": name,
                    "games": games_played,
                    "win_rate": win_rate,
                    "avg_cp_loss": avg_cp,
                }
            )
        tag_stats.sort(key=lambda t: (t["win_rate"], t["games"]), reverse=True)
        best_tags = tag_stats[:3]
        worst_tags = list(reversed(tag_stats[-3:])) if tag_stats else []

        phases = {
            phase: round(statistics.mean(values), 1) if values else None
            for phase, values in phase_sums.items()
        }

        overall_win_rate = round((wins / total_games) * 100, 1)
        opening_profiles = self._build_opening_profiles(
            games,
            overall_win_rate=overall_win_rate,
            phase_baseline=phases,
        )

        personality_notes = self._derive_personality_notes(top_openings, tag_stats, avg_accuracy)
        advanced_summary = self._aggregate_advanced_metrics(games, opening_stats, phases)
        insight_blocks = self._build_insights(advanced_summary, phases)

        return {
            "overall": {
                "total_games": total_games,
                "wins": wins,
                "losses": losses,
                "draws": draws,
                "win_rate": overall_win_rate,
                "average_accuracy": avg_accuracy,
                "blunder_rate": blunder_rate,
                "mistake_rate": mistake_rate,
            },
            "openings": {"top": top_openings, "bottom": bottom_openings},
            "tags": {"best": best_tags, "worst": worst_tags},
            "phases": {
                "opening": phases.get("opening"),
                "middlegame": phases.get("middlegame"),
                "endgame": phases.get("endgame"),
            },
            "personality": personality_notes,
            "advanced": advanced_summary,
            "insights": insight_blocks,
            "opening_profiles": opening_profiles,
        }

    def _build_opening_profiles(
        self,
        games: Sequence[Dict[str, Any]],
        *,
        overall_win_rate: float,
        phase_baseline: Dict[str, Optional[float]],
    ) -> Dict[str, Any]:
        profiles: Dict[str, Dict[str, Any]] = {}
        for game in games:
            opening_key, opening_label = self._normalize_opening(
                game.get("eco"),
                game.get("opening_name") or game.get("opening"),
            )
            side = game.get("player_color", "white")
            profile_key = f"{opening_key}:{side}"
            entry = profiles.setdefault(
                profile_key,
                {
                    "key": profile_key,
                    "eco": game.get("eco"),
                    "name": opening_label,
                    "side": side,
                    "games": 0,
                    "wins": 0,
                    "accuracies": [],
                    "phase_accuracy": {"opening": [], "middlegame": [], "endgame": []},
                    "tag_counts": Counter(),
                    "recent_games": [],
                    "divergence_moves": Counter(),
                },
            )
            entry["games"] += 1
            if game.get("result") == "win":
                entry["wins"] += 1
            if game.get("player_accuracy") is not None:
                entry["accuracies"].append(game["player_accuracy"])
            phase_accuracy = game.get("phase_accuracy") or {}
            for phase in ("opening", "middlegame", "endgame"):
                if phase_accuracy.get(phase) is not None:
                    entry["phase_accuracy"][phase].append(phase_accuracy[phase])

            tags = game.get("tags") or []
            if isinstance(tags, dict):
                tags = tags.keys()
            for tag in tags:
                tag_name = tag if isinstance(tag, str) else tag.get("name", "unknown")
                entry["tag_counts"][tag_name] += 1

            critical = game.get("critical_moves") or []
            if critical:
                first = critical[0]
                san = first.get("san")
                if san:
                    entry["divergence_moves"][san] += 1

            if len(entry["recent_games"]) < 3:
                entry["recent_games"].append(
                    {
                        "game_id": game.get("game_id"),
                        "date": game.get("date"),
                        "result": game.get("result"),
                        "opponent": game.get("opponent_name"),
                        "player_accuracy": game.get("player_accuracy"),
                        "pgn": game.get("pgn"),
                    }
                )

        profile_list: List[Dict[str, Any]] = []
        priority: List[Dict[str, Any]] = []
        baseline_opening_acc = phase_baseline.get("opening")

        for entry in profiles.values():
            games_played = entry["games"]
            win_rate = round((entry["wins"] / games_played) * 100, 1) if games_played else 0.0
            avg_accuracy = round(statistics.mean(entry["accuracies"]), 1) if entry["accuracies"] else None
            opening_acc = (
                round(statistics.mean(entry["phase_accuracy"]["opening"]), 1)
                if entry["phase_accuracy"]["opening"]
                else None
            )
            middlegame_acc = (
                round(statistics.mean(entry["phase_accuracy"]["middlegame"]), 1)
                if entry["phase_accuracy"]["middlegame"]
                else None
            )
            endgame_acc = (
                round(statistics.mean(entry["phase_accuracy"]["endgame"]), 1)
                if entry["phase_accuracy"]["endgame"]
                else None
            )
            common_tags = [tag for tag, _ in entry["tag_counts"].most_common(3)]
            divergence = entry["divergence_moves"].most_common(3)

            profile = {
                "key": entry["key"],
                "eco": entry["eco"],
                "name": entry["name"],
                "side": entry["side"],
                "games": games_played,
                "win_rate": win_rate,
                "average_accuracy": avg_accuracy,
                "opening_accuracy": opening_acc,
                "middlegame_accuracy": middlegame_acc,
                "endgame_accuracy": endgame_acc,
                "common_tags": common_tags,
                "divergence_moves": divergence,
                "recent_games": entry["recent_games"],
            }
            profile_list.append(profile)

            reasons: List[str] = []
            score = 0.0
            if games_played >= 4 and win_rate < overall_win_rate - 10:
                delta = round(overall_win_rate - win_rate, 1)
                reasons.append(f"Win rate {win_rate}% vs overall {overall_win_rate}% (Δ {delta}%)")
                score += delta
            if (
                games_played >= 4
                and opening_acc is not None
                and baseline_opening_acc is not None
                and opening_acc < baseline_opening_acc - 5
            ):
                delta = round(baseline_opening_acc - opening_acc, 1)
                reasons.append(f"Opening accuracy {opening_acc}% vs profile {baseline_opening_acc}% (Δ {delta}%)")
                score += delta
            if divergence:
                reasons.append(f"Frequent off-book move: {divergence[0][0]}")
                score += 2

            if reasons:
                priority.append({**profile, "reasons": reasons, "priority_score": round(score, 2)})

        profile_list.sort(key=lambda p: (p["games"], p["win_rate"]), reverse=True)
        priority.sort(key=lambda p: p["priority_score"], reverse=True)

        return {"list": profile_list, "priority": priority[:5]}

    def _aggregate_advanced_metrics(
        self,
        games: Sequence[Dict[str, Any]],
        opening_stats: List[Dict[str, Any]],
        phase_accuracy: Dict[str, Optional[float]],
    ) -> Dict[str, Any]:
        combined_pieces: Dict[str, Dict[str, float]] = defaultdict(lambda: {"moves": 0, "cp_loss": 0.0, "errors": 0})
        combined_phase_piece: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(lambda: defaultdict(lambda: {"moves": 0, "cp_loss": 0.0, "errors": 0}))
        combined_positions: Dict[str, Dict[str, float]] = defaultdict(lambda: {"moves": 0, "cp_loss": 0.0, "errors": 0})
        combined_advantage: Dict[str, Dict[str, float]] = defaultdict(lambda: {"moves": 0, "cp_loss": 0.0, "errors": 0})
        combined_tactics: Dict[str, Dict[str, float]] = defaultdict(lambda: {"found": 0, "missed": 0, "cp_gain": 0.0, "cp_loss": 0.0})
        combined_tactic_phase: Dict[str, Dict[str, float]] = defaultdict(lambda: {"opportunities": 0, "missed": 0, "found": 0})
        combined_structural: Dict[str, Dict[str, float]] = defaultdict(lambda: {"occurrences": 0, "cp_loss": 0.0, "wins": 0})
        combined_weakness = {"opponent": {"moves": 0, "cp_loss": 0.0}, "self": {"moves": 0, "cp_loss": 0.0}}
        combined_time: Dict[str, Dict[str, float]] = defaultdict(lambda: {"moves": 0, "cp_loss": 0.0, "errors": 0})
        combined_rating: Dict[str, Dict[str, float]] = defaultdict(lambda: {"moves": 0, "cp_loss": 0.0, "errors": 0})
        combined_playstyle = Counter()
        aggregate_conversion = Counter()
        aggregate_resilience = Counter()

        for game in games:
            metrics = game.get("advanced_metrics") or {}
            if not metrics:
                continue
            for piece, data in (metrics.get("pieces") or {}).items():
                combined_pieces[piece]["moves"] += data.get("moves", 0)
                combined_pieces[piece]["cp_loss"] += data.get("cp_loss", 0.0)
                combined_pieces[piece]["errors"] += data.get("errors", 0)
            for phase, phase_map in (metrics.get("phase_piece") or {}).items():
                for piece, data in phase_map.items():
                    combined_phase_piece[phase][piece]["moves"] += data.get("moves", 0)
                    combined_phase_piece[phase][piece]["cp_loss"] += data.get("cp_loss", 0.0)
                    combined_phase_piece[phase][piece]["errors"] += data.get("errors", 0)
            for name, data in (metrics.get("position_types") or {}).items():
                combined_positions[name]["moves"] += data.get("moves", 0)
                combined_positions[name]["cp_loss"] += data.get("cp_loss", 0.0)
                combined_positions[name]["errors"] += data.get("errors", 0)
            for bucket, data in (metrics.get("advantage") or {}).items():
                combined_advantage[bucket]["moves"] += data.get("moves", 0)
                combined_advantage[bucket]["cp_loss"] += data.get("cp_loss", 0.0)
                combined_advantage[bucket]["errors"] += data.get("errors", 0)
            for motif, data in (metrics.get("tactic_motifs") or {}).items():
                combined_tactics[motif]["found"] += data.get("found", 0)
                combined_tactics[motif]["missed"] += data.get("missed", 0)
                combined_tactics[motif]["cp_gain"] += data.get("cp_gain", 0.0)
                combined_tactics[motif]["cp_loss"] += data.get("cp_loss", 0.0)
            for phase, data in (metrics.get("tactic_phases") or {}).items():
                combined_tactic_phase[phase]["opportunities"] += data.get("opportunities", 0)
                combined_tactic_phase[phase]["found"] += data.get("found", 0)
                combined_tactic_phase[phase]["missed"] += data.get("missed", 0)
            for name, data in (metrics.get("structural") or {}).items():
                combined_structural[name]["occurrences"] += data.get("occurrences", 0)
                combined_structural[name]["cp_loss"] += data.get("cp_loss", 0.0)
                combined_structural[name]["wins"] += data.get("wins", 0)
            for key in ("opponent", "self"):
                if metrics.get("weakness", {}).get(key):
                    combined_weakness[key]["moves"] += metrics["weakness"][key].get("moves", 0)
                    combined_weakness[key]["cp_loss"] += metrics["weakness"][key].get("cp_loss", 0.0)
            for bucket, data in (metrics.get("time_buckets") or {}).items():
                combined_time[bucket]["moves"] += data.get("moves", 0)
                combined_time[bucket]["cp_loss"] += data.get("cp_loss", 0.0)
                combined_time[bucket]["errors"] += data.get("errors", 0)
            for bucket, data in (metrics.get("rating_buckets") or {}).items():
                combined_rating[bucket]["moves"] += data.get("moves", 0)
                combined_rating[bucket]["cp_loss"] += data.get("cp_loss", 0.0)
                combined_rating[bucket]["errors"] += data.get("errors", 0)
            for key, value in (metrics.get("playstyle") or {}).items():
                combined_playstyle[key] += value
            for key, value in (metrics.get("conversion") or {}).items():
                aggregate_conversion[key] += value
            for key, value in (metrics.get("resilience") or {}).items():
                aggregate_resilience[key] += value

        def _avg_cp(entry: Dict[str, float]) -> float:
            moves = entry.get("moves", 0)
            return round(entry.get("cp_loss", 0.0) / moves, 1) if moves else 0.0

        accuracy_by_piece = [
            {
                "piece": piece.capitalize(),
                "avg_cp_loss": _avg_cp(data),
                "error_rate": round((data["errors"] / data["moves"]) * 100, 1) if data["moves"] else 0.0,
                "moves": int(data["moves"]),
            }
            for piece, data in combined_pieces.items()
            if data["moves"]
        ]
        accuracy_by_piece.sort(key=lambda row: row["avg_cp_loss"], reverse=True)

        phase_piece_heatmap = {
            phase: {
                piece.capitalize(): _avg_cp(data)
                for piece, data in pieces.items()
                if data["moves"]
            }
            for phase, pieces in combined_phase_piece.items()
        }

        position_rows = [
            {
                "type": name,
                "avg_cp_loss": _avg_cp(data),
                "error_rate": round((data["errors"] / data["moves"]) * 100, 1) if data["moves"] else 0.0,
                "moves": int(data["moves"]),
            }
            for name, data in combined_positions.items()
            if data["moves"]
        ]
        position_rows.sort(key=lambda row: row["avg_cp_loss"], reverse=True)

        advantage_rows = [
            {
                "bucket": bucket,
                "avg_cp_loss": _avg_cp(data),
                "error_rate": round((data["errors"] / data["moves"]) * 100, 1) if data["moves"] else 0.0,
                "moves": int(data["moves"]),
            }
            for bucket, data in combined_advantage.items()
            if data["moves"]
        ]

        tactic_rows = [
            {
                "motif": motif.split(".")[-1].replace("_", " "),
                "found": int(data["found"]),
                "missed": int(data["missed"]),
                "miss_rate": round((data["missed"] / (data["found"] + data["missed"])) * 100, 1)
                if (data["found"] + data["missed"])
                else 0.0,
                "avg_loss": round(data["cp_loss"] / data["missed"], 1) if data["missed"] else 0.0,
            }
            for motif, data in combined_tactics.items()
            if data["found"] or data["missed"]
        ]
        tactic_rows.sort(key=lambda row: row["missed"], reverse=True)

        tactic_phase_rows = [
            {
                "phase": phase,
                "opportunities": int(data["opportunities"]),
                "found": int(data["found"]),
                "missed": int(data["missed"]),
            }
            for phase, data in combined_tactic_phase.items()
            if data["opportunities"]
        ]

        structural_rows = [
            {
                "tag": name,
                "occurrences": int(data["occurrences"]),
                "avg_cp_loss": round(data["cp_loss"] / data["occurrences"], 1) if data["occurrences"] else 0.0,
                "win_rate": round((data["wins"] / data["occurrences"]) * 100, 1) if data["occurrences"] else 0.0,
            }
            for name, data in combined_structural.items()
            if data["occurrences"]
        ]
        structural_rows.sort(key=lambda row: row["occurrences"], reverse=True)

        weakness_summary = {
            key: {
                "moves": stats["moves"],
                "avg_cp_loss": round(stats["cp_loss"] / stats["moves"], 1) if stats["moves"] else 0.0,
            }
            for key, stats in combined_weakness.items()
        }

        time_rows = [
            {
                "bucket": bucket,
                "avg_cp_loss": _avg_cp(data),
                "error_rate": round((data["errors"] / data["moves"]) * 100, 1) if data["moves"] else 0.0,
                "moves": int(data["moves"]),
            }
            for bucket, data in combined_time.items()
            if data["moves"]
        ]

        rating_rows = [
            {
                "bucket": bucket,
                "avg_cp_loss": _avg_cp(data),
                "error_rate": round((data["errors"] / data["moves"]) * 100, 1) if data["moves"] else 0.0,
                "moves": int(data["moves"]),
            }
            for bucket, data in combined_rating.items()
            if data["moves"]
        ]

        aggression_total = combined_playstyle["aggressive_moves"] + combined_playstyle["positional_moves"]
        material_total = combined_playstyle["material_moves"] + combined_playstyle["initiative_moves"]
        simplify_total = combined_playstyle["simplify_moves"] + combined_playstyle["tension_moves"]
        playstyle_summary = {
            "aggression_bias": round((combined_playstyle["aggressive_moves"] / aggression_total) * 100, 1) if aggression_total else None,
            "material_bias": round((combined_playstyle["material_moves"] / material_total) * 100, 1) if material_total else None,
            "simplification_bias": round((combined_playstyle["simplify_moves"] / simplify_total) * 100, 1) if simplify_total else None,
            "king_safety_risk": round((combined_playstyle["king_safety_errors"] / combined_playstyle["king_safety_moves"]) * 100, 1)
            if combined_playstyle["king_safety_moves"]
            else None,
        }

        conversion_summary = {
            "winning_positions": aggregate_conversion.get("winning_positions", 0),
            "converted": aggregate_conversion.get("converted", 0),
            "holds": aggregate_conversion.get("holds", 0),
            "squandered": aggregate_conversion.get("squandered", 0),
            "max_advantage_cp": aggregate_conversion.get("max_advantage_cp", 0),
        }
        if conversion_summary["winning_positions"]:
            conversion_summary["conversion_rate"] = round(
                (conversion_summary["converted"] / conversion_summary["winning_positions"]) * 100,
                1,
            )
        else:
            conversion_summary["conversion_rate"] = None

        resilience_summary = {
            "defensive_positions": aggregate_resilience.get("defensive_positions", 0),
            "swindles": aggregate_resilience.get("swindles", 0),
            "saves": aggregate_resilience.get("saves", 0),
            "collapsed": aggregate_resilience.get("collapsed", 0),
            "max_deficit_cp": aggregate_resilience.get("max_deficit_cp", 0),
        }
        if resilience_summary["defensive_positions"]:
            resilience_summary["save_rate"] = round(
                ((resilience_summary["swindles"] + resilience_summary["saves"]) / resilience_summary["defensive_positions"]) * 100,
                1,
            )
        else:
            resilience_summary["save_rate"] = None

        family_buckets: Dict[str, Dict[str, float]] = defaultdict(lambda: {"games": 0, "win_sum": 0.0})
        for opening in opening_stats:
            name = opening["name"]
            label = name.split("·")[-1].strip() if "·" in name else name
            family = label.split()[0] if label else "Unknown"
            family_bucket = family_buckets[family]
            family_bucket["games"] += opening.get("games", 0)
            family_bucket["win_sum"] += opening.get("win_rate", 0.0) * opening.get("games", 0)
        opening_families = [
            {
                "family": family,
                "games": int(data["games"]),
                "win_rate": round(data["win_sum"] / data["games"], 1) if data["games"] else 0.0,
            }
            for family, data in family_buckets.items()
            if data["games"]
        ]
        opening_families.sort(key=lambda row: row["games"], reverse=True)

        endgame_skills = {
            "opening_accuracy": phase_accuracy.get("opening"),
            "middlegame_accuracy": phase_accuracy.get("middlegame"),
            "endgame_accuracy": phase_accuracy.get("endgame"),
        }

        return {
            "accuracy_by_piece": accuracy_by_piece,
            "phase_piece_heatmap": phase_piece_heatmap,
            "position_types": position_rows,
            "advantage_regimes": advantage_rows,
            "tactic_motifs": tactic_rows,
            "tactic_phases": tactic_phase_rows,
            "structural_tags": structural_rows,
            "weakness": weakness_summary,
            "time_buckets": time_rows,
            "rating_buckets": rating_rows,
            "playstyle": playstyle_summary,
            "conversion": conversion_summary,
            "resilience": resilience_summary,
            "opening_families": opening_families,
            "endgame_skills": endgame_skills,
        }

    def summarize_opening_history(
        self,
        user_id: str,
        eco: Optional[str],
        opening_name: Optional[str],
        max_games: int = 12,
    ) -> Dict[str, Any]:
        """Summaries user games matching an opening for personalization."""
        games = self._games.get(user_id, [])
        matches: List[Dict[str, Any]] = []
        opening_name_lower = opening_name.lower() if opening_name else None

        for game in games:
            match = False
            if eco and game.get("eco") == eco:
                match = True
            elif opening_name_lower and opening_name_lower in (game.get("opening_name", "") or "").lower():
                match = True
            if match:
                matches.append(game)
            if len(matches) >= max_games:
                break

        sequence_counter: Dict[Tuple[str, ...], Dict[str, Any]] = {}
        user_variations: List[Dict[str, Any]] = []
        recent_mistakes: List[Dict[str, Any]] = []

        for game in matches:
            sequence = self._extract_opening_sequence(game.get("pgn") or "", max_moves=14)
            if sequence:
                key = tuple(sequence[:10])
                entry = sequence_counter.setdefault(
                    key,
                    {
                        "moves": sequence[:12],
                        "count": 0,
                        "results": {"win": 0, "loss": 0, "draw": 0},
                    },
                )
                entry["count"] += 1
                result = game.get("result")
                if result in entry["results"]:
                    entry["results"][result] += 1
                user_variations.append(
                    {
                        "moves": sequence[:12],
                        "result": result,
                        "platform": game.get("platform"),
                        "date": game.get("date"),
                        "opponent": game.get("opponent_name"),
                        "hash": hashlib.md5(" ".join(sequence[:12]).encode("utf-8")).hexdigest()[:12],
                    }
                )

            for crit in game.get("critical_moves") or []:
                category = (crit.get("category") or "").lower()
                if category in {"mistake", "blunder"} and crit.get("fen_before") and crit.get("san"):
                    recent_mistakes.append(
                        {
                            "fen": crit["fen_before"],
                            "prompt": f"In your game vs {game.get('opponent_name', 'opponent')} you played {crit['san']} ({category}). Find the correct move now.",
                            "correct_move": crit.get("best_move"),
                            "context": {
                                "game_id": game.get("game_id"),
                                "result": game.get("result"),
                            },
                        }
                    )
                    break  # Only track first critical mistake per game to avoid spam

        top_sequences = [
            {
                "moves": data["moves"],
                "count": data["count"],
                "results": data["results"],
                "hash": hashlib.md5(" ".join(data["moves"]).encode("utf-8")).hexdigest()[:12],
            }
            for _, data in sorted(sequence_counter.items(), key=lambda item: item[1]["count"], reverse=True)
        ][:5]

        return {
            "games_considered": len(matches),
            "top_sequences": top_sequences,
            "recent_mistakes": recent_mistakes[:5],
            "user_variations": user_variations[:6],
            "recent_lessons": list(self._lesson_history.get(user_id, [])),
        }

    def get_opening_profile_snapshot(
        self,
        user_id: str,
        eco: Optional[str],
        opening_name: Optional[str],
        side: str,
    ) -> Optional[Dict[str, Any]]:
        """Return aggregated stats for a specific opening + side."""
        stats = self.get_stats(user_id)
        profiles = (stats.get("opening_profiles") or {}).get("list") or []
        opening_key, _ = self._normalize_opening(eco, opening_name)
        target_key = f"{opening_key}:{side}"
        for profile in profiles:
            if profile.get("key") == target_key:
                return profile
        return None

    def record_opening_lesson_usage(self, user_id: str, metadata: Dict[str, Any]) -> None:
        """Track lesson usage locally for variation rotation."""
        history = self._lesson_history.setdefault(user_id, [])
        history.insert(0, metadata)
        del history[6:]

    @staticmethod
    def _extract_opening_sequence(pgn_text: str, max_moves: int = 12) -> List[str]:
        if not pgn_text:
            return []
        try:
            game = chess.pgn.read_game(io.StringIO(pgn_text))
            if not game:
                return []
            board = game.board()
            moves: List[str] = []
            for move in game.mainline_moves():
                moves.append(board.san(move))
                board.push(move)
                if len(moves) >= max_moves:
                    break
            return moves
        except Exception:
            return []

    def _build_insights(
        self,
        advanced: Dict[str, Any],
        phase_accuracy: Dict[str, Optional[float]],
    ) -> Dict[str, List[str]]:
        insights = {"accuracy": [], "tactics": [], "structure": [], "playstyle": [], "conversion": []}

        pieces = advanced.get("accuracy_by_piece") or []
        if pieces:
            worst = max(pieces, key=lambda row: row["avg_cp_loss"])
            insights["accuracy"].append(
                f"You lose the most CP when moving your {worst['piece'].lower()}s (≈{worst['avg_cp_loss']}cp per move)."
            )
            best = min(pieces, key=lambda row: row["avg_cp_loss"])
            insights["accuracy"].append(
                f"Your {best['piece'].lower()} play is the most reliable (≈{best['avg_cp_loss']}cp per move)."
            )

        positions = advanced.get("position_types") or []
        if positions:
            best_pos = min(positions, key=lambda row: row["avg_cp_loss"])
            worst_pos = max(positions, key=lambda row: row["avg_cp_loss"])
            insights["structure"].append(
                f"Best structure: {best_pos['type']} positions (≈{best_pos['avg_cp_loss']}cp)."
            )
            insights["structure"].append(
                f"Struggle: {worst_pos['type']} positions (≈{worst_pos['avg_cp_loss']}cp)."
            )

        tactics = advanced.get("tactic_motifs") or []
        if tactics:
            worst_tactic = max(tactics, key=lambda row: row["miss_rate"])
            insights["tactics"].append(
                f"Missed tactics: {worst_tactic['motif']} ideas slip {worst_tactic['miss_rate']}% of the time."
            )

        tactic_phases = advanced.get("tactic_phases") or []
        if tactic_phases:
            busiest = max(tactic_phases, key=lambda row: row["opportunities"])
            insights["tactics"].append(
                f"Most tactical chaos happens in the {busiest['phase']} (≈{busiest['opportunities']} chances)."
            )

        playstyle = advanced.get("playstyle") or {}
        aggression_bias = playstyle.get("aggression_bias")
        material_bias = playstyle.get("material_bias")
        if aggression_bias is not None:
            if aggression_bias > 60:
                insights["playstyle"].append(
                    f"In equal positions you choose attacking continuations {aggression_bias:.0f}% of the time."
                )
            elif aggression_bias < 40:
                insights["playstyle"].append(
                    f"You often default to safer, positional moves (attacking choices only {aggression_bias:.0f}% of the time)."
                )
        if material_bias is not None and material_bias > 60:
            insights["playstyle"].append("Material grabs are a recurring theme—consider weighing initiative more often.")

        conversion = advanced.get("conversion") or {}
        if conversion.get("conversion_rate") is not None:
            insights["conversion"].append(
                f"Winning positions converted: {conversion['converted']} of {conversion['winning_positions']} "
                f"({conversion['conversion_rate']}%)."
            )
        resilience = advanced.get("resilience") or {}
        if resilience.get("save_rate") is not None:
            insights["conversion"].append(
                f"Defensive resilience: saved or swindled {resilience['save_rate']}% of bad positions."
            )

        if phase_accuracy.get("endgame") and phase_accuracy.get("middlegame"):
            diff = phase_accuracy["endgame"] - phase_accuracy["middlegame"]
            if diff > 5:
                insights["accuracy"].append("Endgames are a strength relative to middlegames.")
            elif diff < -5:
                insights["accuracy"].append("Endgame accuracy lags behind your middlegame handling.")

        return insights

    def _derive_personality_notes(
        self,
        top_openings: List[Dict[str, Any]],
        tag_stats: List[Dict[str, Any]],
        avg_accuracy: Optional[float],
    ) -> Dict[str, Any]:
        notes: List[str] = []
        tendencies: List[Dict[str, Any]] = []

        if top_openings:
            best = top_openings[0]
            notes.append(
                f"Strong results in {best['name']} lines ({best['win_rate']}% win rate over {best['games']} games)."
            )

        tactical_tags = [t for t in tag_stats if "tactic" in t["name"].lower()]
        if tactical_tags:
            tag = tactical_tags[0]
            notes.append(
                f"Tends to embrace tactical themes like {tag['name']} ({tag['win_rate']}% win rate)."
            )

        if avg_accuracy and avg_accuracy >= 80:
            tendencies.append(
                {"title": "Precision Finisher", "detail": "Average accuracy above 80% indicates consistent conversion.", "confidence": "high"}
            )
        elif avg_accuracy:
            tendencies.append(
                {"title": "Opportunistic", "detail": f"Average accuracy of {avg_accuracy}% leaves room for tighter play in critical moments.", "confidence": "medium"}
            )

        if not notes:
            notes.append("Not enough indexed games to identify strong stylistic trends yet.")

        return {"notes": notes, "tendencies": tendencies}

    @staticmethod
    def _normalize_opening(eco: Optional[str], opening_name: Optional[str]) -> Tuple[str, str]:
        if eco:
            key = eco.upper()
            label = eco.upper()
            if opening_name:
                label = f"{eco.upper()} · {opening_name.split('-')[0].strip()}"
            return key, label

        if opening_name:
            base = opening_name.split('-')[0].strip()
            return base.lower().replace(" ", "_"), base

        return "unknown", "Unknown"

    def _schedule_analysis(self, user_id: str) -> None:
        if not self.review_fn:
            return
        existing = self._analysis_tasks.get(user_id)
        if existing and not existing.done():
            return
        task = asyncio.create_task(self._run_analysis_pipeline(user_id))
        self._analysis_tasks[user_id] = task

    async def _run_analysis_pipeline(self, user_id: str) -> None:
        try:
            await self._run_light_analysis(user_id)
            await self._run_deep_analysis(user_id)
        except Exception as exc:
            print(f"⚠️  Analysis pipeline error for {user_id}: {exc}")

    async def _run_light_analysis(self, user_id: str) -> None:
        if not self.review_fn:
            return
        games = list(self._games.get(user_id, []))
        if not games:
            return
        self._light_results.setdefault(user_id, {})
        status = self._status.get(user_id)
        for game in games:
            game_id = game.get("game_id") or f"{game.get('platform')}::{game.get('date')}::{game.get('opponent_name')}"
            if game_id in self._light_results[user_id]:
                continue
            if not game.get("pgn"):
                continue
            if status:
                status.message = f"Light analysis – {game.get('opponent_name', 'game')}"
                status.last_updated = _utc_now()
            try:
                result = await self.review_fn(
                    game["pgn"],
                    side_focus="both",
                    include_timestamps=False,
                    depth=self.light_analysis_depth,
                    engine_instance=self.engine_instance,
                )
            except Exception as exc:
                print(f"⚠️  Light analysis failed for {game_id}: {exc}")
                continue
            if not result or "ply_records" not in result:
                continue
            summary = self._summarize_light_result(result, game)
            self._light_results[user_id][game_id] = summary
            self._apply_light_summary_to_game(game, summary)
            if status:
                status.light_analyzed_games = len(self._light_results[user_id])
                status.last_updated = _utc_now()
        self._refresh_stats(user_id)

    def _summarize_light_result(self, review_result: Dict[str, Any], game: Dict[str, Any]) -> Dict[str, Any]:
        player_color = game.get("player_color", "white")
        stats = review_result.get("stats", {}).get(player_color, {})
        counts = stats.get("counts", {})
        phase_stats = stats.get("by_phase", {})
        critical_records = [
            {
                "fen_before": rec.get("fen_before"),
                "san": rec.get("san"),
                "category": rec.get("category"),
                "side": rec.get("side_moved"),
            }
            for rec in review_result.get("ply_records", [])
            if rec.get("is_critical")
        ]
        summary = {
            "player_accuracy": stats.get("overall_accuracy"),
            "blunder_count": counts.get("blunder"),
            "mistake_count": counts.get("mistake"),
            "phase_accuracy": {
                phase: data.get("accuracy")
                for phase, data in phase_stats.items()
            },
            "critical": [rec for rec in critical_records if rec.get("fen_before")],
        }
        summary["advanced_metrics"] = self._compute_advanced_metrics(review_result, game, player_color)
        return summary

    def _compute_advanced_metrics(self, review_result: Dict[str, Any], game: Dict[str, Any], player_color: str) -> Dict[str, Any]:
        ply_records = review_result.get("ply_records", [])
        piece_stats: Dict[str, Dict[str, float]] = defaultdict(lambda: {"moves": 0, "cp_loss": 0.0, "errors": 0})
        phase_piece_stats: Dict[str, Dict[str, Dict[str, float]]] = defaultdict(lambda: defaultdict(lambda: {"moves": 0, "cp_loss": 0.0, "errors": 0}))
        position_type_stats: Dict[str, Dict[str, float]] = defaultdict(lambda: {"moves": 0, "cp_loss": 0.0, "errors": 0})
        advantage_stats: Dict[str, Dict[str, float]] = defaultdict(lambda: {"moves": 0, "cp_loss": 0.0, "errors": 0})
        tactic_motifs: Dict[str, Dict[str, float]] = defaultdict(lambda: {"found": 0, "missed": 0, "cp_gain": 0.0, "cp_loss": 0.0})
        tactic_phase: Dict[str, Dict[str, float]] = defaultdict(lambda: {"opportunities": 0, "missed": 0, "found": 0})
        structural_stats: Dict[str, Dict[str, float]] = defaultdict(lambda: {"occurrences": 0, "cp_loss": 0.0, "wins": 0})
        weakness_stats = {
            "opponent": {"moves": 0, "cp_loss": 0.0},
            "self": {"moves": 0, "cp_loss": 0.0},
        }
        time_stats: Dict[str, Dict[str, float]] = defaultdict(lambda: {"moves": 0, "cp_loss": 0.0, "errors": 0})
        rating_bucket = _bucket_rating(game.get("player_rating"), game.get("opponent_rating"))
        rating_stats: Dict[str, Dict[str, float]] = defaultdict(lambda: {"moves": 0, "cp_loss": 0.0, "errors": 0})
        playstyle_stats = {
            "aggressive_moves": 0,
            "aggressive_mistakes": 0,
            "positional_moves": 0,
            "positional_mistakes": 0,
            "material_moves": 0,
            "material_mistakes": 0,
            "initiative_moves": 0,
            "initiative_mistakes": 0,
            "simplify_moves": 0,
            "tension_moves": 0,
            "king_safety_moves": 0,
            "king_safety_errors": 0,
        }
        conversion_tracker = {
            "max_advantage_cp": -math.inf,
            "max_deficit_cp": math.inf,
            "had_winning": False,
            "had_losing": False,
        }
        player_eval_history: List[float] = []

        player_side = "white" if player_color == "white" else "black"
        game_result = game.get("result", "unknown")

        for record in ply_records:
            if record.get("side_moved") != player_color:
                continue
            cp_loss = float(record.get("cp_loss", 0))
            category = record.get("category") or ""
            is_error = category in {"mistake", "blunder"}
            fen_before = record.get("fen_before")
            uci = record.get("uci")
            piece_name = _piece_name_from_move(fen_before, uci)
            piece_stats[piece_name]["moves"] += 1
            piece_stats[piece_name]["cp_loss"] += cp_loss
            if is_error:
                piece_stats[piece_name]["errors"] += 1

            phase = record.get("phase", "middlegame")
            phase_piece_stats[phase][piece_name]["moves"] += 1
            phase_piece_stats[phase][piece_name]["cp_loss"] += cp_loss
            if is_error:
                phase_piece_stats[phase][piece_name]["errors"] += 1

            board = chess.Board(fen_before) if fen_before else None
            for pos_type in _infer_position_types(board):
                position_type_stats[pos_type]["moves"] += 1
                position_type_stats[pos_type]["cp_loss"] += cp_loss
                if is_error:
                    position_type_stats[pos_type]["errors"] += 1

            eval_after = float(record.get("engine", {}).get("played_eval_after_cp", 0))
            player_eval = eval_after if player_color == "white" else -eval_after
            conversion_tracker["max_advantage_cp"] = max(conversion_tracker["max_advantage_cp"], player_eval)
            conversion_tracker["max_deficit_cp"] = min(conversion_tracker["max_deficit_cp"], player_eval)
            if player_eval >= 300:
                conversion_tracker["had_winning"] = True
            if player_eval <= -300:
                conversion_tracker["had_losing"] = True
            player_eval_history.append(player_eval)

            adv_bucket = _bucket_advantage(player_eval)
            advantage_stats[adv_bucket]["moves"] += 1
            advantage_stats[adv_bucket]["cp_loss"] += cp_loss
            if is_error:
                advantage_stats[adv_bucket]["errors"] += 1

            tags = record.get("analyse", {}).get("tags", []) or []
            tag_names = [tag.get("tag_name") for tag in tags if isinstance(tag, dict) and tag.get("tag_name")]
            tactic_tags = [name for name in tag_names if name and name.startswith("tag.tactic.")]
            structural_tags = [name for name in tag_names if name and name.startswith(("tag.file", "tag.center", "tag.pawn", "tag.square", "tag.lever", "tag.color", "tag.local"))]

            for motif in tactic_tags:
                tactic_motifs[motif]["found" if cp_loss < 40 else "missed"] += 1
                if cp_loss < 40:
                    tactic_motifs[motif]["cp_gain"] += max(0, record.get("engine", {}).get("second_best_gap_cp", 0) or 0)
                else:
                    tactic_motifs[motif]["cp_loss"] += cp_loss
                tactic_phase[phase]["opportunities"] += 1
                if cp_loss < 40:
                    tactic_phase[phase]["found"] += 1
                else:
                    tactic_phase[phase]["missed"] += 1

            for struct in structural_tags:
                structural_stats[struct]["occurrences"] += 1
                structural_stats[struct]["cp_loss"] += cp_loss
                if game_result == "win":
                    structural_stats[struct]["wins"] += 1

            for tag in tags:
                tag_name = tag.get("tag_name")
                if not tag_name:
                    continue
                if "weak" in tag_name or "target" in tag_name or "hole" in tag_name:
                    tag_side = tag.get("side")
                    if tag_side and tag_side.lower() != player_side:
                        weakness_stats["opponent"]["moves"] += 1
                        weakness_stats["opponent"]["cp_loss"] += cp_loss
                    else:
                        weakness_stats["self"]["moves"] += 1
                        weakness_stats["self"]["cp_loss"] += cp_loss

            time_bucket = _bucket_time(record.get("time_spent_s"))
            if time_bucket:
                time_stats[time_bucket]["moves"] += 1
                time_stats[time_bucket]["cp_loss"] += cp_loss
                if is_error:
                    time_stats[time_bucket]["errors"] += 1

            rating_stats[rating_bucket]["moves"] += 1
            rating_stats[rating_bucket]["cp_loss"] += cp_loss
            if is_error:
                rating_stats[rating_bucket]["errors"] += 1

            played_san = record.get("san", "")
            is_capture = "x" in played_san
            is_attack = bool(tactic_tags)
            if is_attack:
                playstyle_stats["aggressive_moves"] += 1
                if is_error:
                    playstyle_stats["aggressive_mistakes"] += 1
            else:
                playstyle_stats["positional_moves"] += 1
                if is_error:
                    playstyle_stats["positional_mistakes"] += 1
            if is_capture:
                playstyle_stats["material_moves"] += 1
                if is_error:
                    playstyle_stats["material_mistakes"] += 1
            else:
                playstyle_stats["initiative_moves"] += 1
                if is_error and is_attack:
                    playstyle_stats["initiative_mistakes"] += 1
            if any(name and name.startswith("tag.trades") for name in tag_names):
                playstyle_stats["simplify_moves"] += 1
            else:
                playstyle_stats["tension_moves"] += 1
            if any(name and ("tag.king" in name or "tag.color.hole" in name) for name in tag_names):
                playstyle_stats["king_safety_moves"] += 1
                if is_error:
                    playstyle_stats["king_safety_errors"] += 1

        conversion = {
            "winning_positions": 1 if conversion_tracker["had_winning"] else 0,
            "converted": 1 if conversion_tracker["had_winning"] and game_result == "win" else 0,
            "holds": 1 if conversion_tracker["had_winning"] and game_result == "draw" else 0,
            "squandered": 1 if conversion_tracker["had_winning"] and game_result == "loss" else 0,
            "max_advantage_cp": conversion_tracker["max_advantage_cp"] if conversion_tracker["max_advantage_cp"] != -math.inf else 0,
        }
        resilience = {
            "defensive_positions": 1 if conversion_tracker["had_losing"] else 0,
            "swindles": 1 if conversion_tracker["had_losing"] and game_result == "win" else 0,
            "saves": 1 if conversion_tracker["had_losing"] and game_result == "draw" else 0,
            "collapsed": 1 if conversion_tracker["had_losing"] and game_result == "loss" else 0,
            "max_deficit_cp": conversion_tracker["max_deficit_cp"] if conversion_tracker["max_deficit_cp"] != math.inf else 0,
        }

        pieces_serialized = {
            piece: {
                "moves": data["moves"],
                "cp_loss": data["cp_loss"],
                "errors": data["errors"],
            }
            for piece, data in piece_stats.items()
            if data["moves"]
        }
        phase_piece_serialized = {
            phase: {
                piece: {
                    "moves": pdata["moves"],
                    "cp_loss": pdata["cp_loss"],
                    "errors": pdata["errors"],
                }
                for piece, pdata in pieces.items()
                if pdata["moves"]
            }
            for phase, pieces in phase_piece_stats.items()
        }
        position_serialized = {
            name: {
                "moves": data["moves"],
                "cp_loss": data["cp_loss"],
                "errors": data["errors"],
            }
            for name, data in position_type_stats.items()
            if data["moves"]
        }
        advantage_serialized = {
            bucket: {
                "moves": data["moves"],
                "cp_loss": data["cp_loss"],
                "errors": data["errors"],
            }
            for bucket, data in advantage_stats.items()
            if data["moves"]
        }
        tactic_serialized = {
            motif: data for motif, data in tactic_motifs.items()
            if data["found"] or data["missed"]
        }
        tactic_phase_serialized = {
            phase: data
            for phase, data in tactic_phase.items()
            if data["opportunities"]
        }
        structural_serialized = {
            name: data for name, data in structural_stats.items()
            if data["occurrences"]
        }
        time_serialized = {
            bucket: data for bucket, data in time_stats.items()
            if data["moves"]
        }
        rating_serialized = {
            bucket: data for bucket, data in rating_stats.items()
            if data["moves"]
        }

        return {
            "pieces": pieces_serialized,
            "phase_piece": phase_piece_serialized,
            "position_types": position_serialized,
            "advantage": advantage_serialized,
            "tactic_motifs": tactic_serialized,
            "tactic_phases": tactic_phase_serialized,
            "structural": structural_serialized,
            "weakness": weakness_stats,
            "time_buckets": time_serialized,
            "rating_buckets": rating_serialized,
            "playstyle": playstyle_stats,
            "conversion": conversion,
            "resilience": resilience,
        }

    def _apply_light_summary_to_game(self, game: Dict[str, Any], summary: Dict[str, Any]) -> None:
        if summary.get("player_accuracy") is not None:
            game["player_accuracy"] = summary["player_accuracy"]
        if summary.get("blunder_count") is not None:
            game["blunder_count"] = summary["blunder_count"]
        if summary.get("mistake_count") is not None:
            game["mistake_count"] = summary["mistake_count"]
        if summary.get("phase_accuracy"):
            game["phase_accuracy"] = summary["phase_accuracy"]
        game["critical_moves"] = summary.get("critical", [])
        if summary.get("advanced_metrics"):
            game["advanced_metrics"] = summary["advanced_metrics"]

    async def _run_deep_analysis(self, user_id: str) -> None:
        if not self.engine_queue:
            return
        light_results = self._light_results.get(user_id, {})
        if not light_results:
            return
        completed = self._deep_completed.setdefault(user_id, set())
        status = self._status.get(user_id)
        for game in self._games.get(user_id, []):
            game_id = game.get("game_id") or f"{game.get('platform')}::{game.get('date')}::{game.get('opponent_name')}"
            if game_id in completed:
                continue
            summary = light_results.get(game_id)
            if not summary:
                continue
            critical = summary.get("critical") or []
            if not critical:
                completed.add(game_id)
                continue
            if status:
                status.message = f"Deep analysis – {game.get('opponent_name', 'game')}"
                status.last_updated = _utc_now()
            for record in critical:
                fen = record.get("fen_before")
                if not fen:
                    continue
                await self._reanalyze_critical_move(fen)
            completed.add(game_id)
            if status:
                status.deep_analyzed_games = len(completed)
                status.last_updated = _utc_now()

    async def _reanalyze_critical_move(self, fen: str) -> None:
        if not self.engine_queue:
            return
        try:
            board = chess.Board(fen)
            await self.engine_queue.enqueue(
                self.engine_queue.engine.analyse,
                board,
                chess.engine.Limit(depth=self.deep_analysis_depth),
                multipv=3,
            )
        except Exception as exc:
            print(f"⚠️  Deep analysis failed for fen {fen[:20]}...: {exc}")

    async def ensure_background_index(self, user_id: str) -> None:
        """Called when the user is active to keep background indexing humming."""
        self._last_activity[user_id] = time.monotonic()
        self._schedule_analysis(user_id)
        await self._maybe_schedule_background(user_id)

    async def _maybe_schedule_background(self, user_id: str) -> None:
        total_games = len(self._games.get(user_id, []))
        status = self._status.get(user_id)
        if not status or total_games < self.background_target_games:
            return
        if status.state not in {"idle", "complete"}:
            return
        existing = self._background_tasks.get(user_id)
        if existing and not existing.done():
            return

        now = time.monotonic()
        next_poll = self._next_poll_timestamp.get(user_id)
        if next_poll and now < next_poll:
            return

        next_time = now + self.background_interval_seconds
        self._next_poll_timestamp[user_id] = next_time
        status.next_poll_at = _utc_from_timestamp(time.time() + self.background_interval_seconds)

        task = asyncio.create_task(self._run_background_refresh(user_id))
        self._background_tasks[user_id] = task

    async def _run_background_refresh(self, user_id: str) -> None:
        status = self._status.get(user_id)
        accounts = status.accounts if status else []
        prefs = self.load_preferences(user_id) or {}
        time_controls = prefs.get("time_controls", [])
        if not accounts:
            accounts = prefs.get("accounts", [])
        if not accounts:
            return
        try:
            await self._run_indexing(
                user_id=user_id,
                accounts=accounts,
                time_controls=time_controls,
                max_games_override=self.background_batch_size,
                background=True,
            )
        finally:
            self._background_tasks.pop(user_id, None)
            next_time = time.monotonic() + self.background_interval_seconds
            self._next_poll_timestamp[user_id] = next_time
            status = self._status.get(user_id)
            if status:
                status.next_poll_at = _utc_from_timestamp(time.time() + self.background_interval_seconds)

    @staticmethod
    def _dedupe_and_sort_games(games: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen: Dict[str, Dict[str, Any]] = {}
        for game in games:
            gid = (
                game.get("game_id")
                or f"{game.get('platform')}::{game.get('date')}::{game.get('opponent_name')}"
            )
            if gid not in seen:
                seen[gid] = game
        sorted_games = sorted(
            seen.values(),
            key=lambda game: game.get("date") or "",
            reverse=True,
        )
        return sorted_games

