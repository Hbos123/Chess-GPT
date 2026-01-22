import asyncio
import pytest

from backend.profile_indexer import ProfileIndexingManager, ProfileIndexStatus


class DummyFetcher:
    async def fetch_games(self, *args, **kwargs):
        return []


@pytest.mark.asyncio
async def test_compute_stats_basic():
    manager = ProfileIndexingManager(game_fetcher=DummyFetcher())
    games = [
        {
            "result": "win",
            "opening": "Sicilian",
            "player_accuracy": 85,
            "blunder_count": 0,
            "mistake_count": 1,
            "tags": ["attack"],
        },
        {
            "result": "loss",
            "opening": "French",
            "player_accuracy": 72,
            "blunder_count": 1,
            "mistake_count": 2,
            "tags": ["defense"],
        },
        {
            "result": "win",
            "opening": "Sicilian",
            "player_accuracy": 90,
            "blunder_count": 0,
            "mistake_count": 0,
            "tags": ["attack"],
        },
    ]

    stats = manager._compute_stats(games)

    assert stats["overall"]["total_games"] == 3
    assert stats["overall"]["wins"] == 2
    assert stats["overall"]["losses"] == 1
    assert stats["overall"]["win_rate"] == pytest.approx(66.7, rel=1e-2)
    assert stats["openings"]["top"][0]["name"] == "Sicilian"
    assert stats["openings"]["top"][0]["win_rate"] == 100.0
    assert stats["tags"]["best"][0]["name"] == "attack"


def test_opening_profiles_and_priority():
    manager = ProfileIndexingManager(game_fetcher=DummyFetcher())
    games = []
    for _ in range(5):
        games.append(
            {
                "result": "loss",
                "opening_name": "Italian Game",
                "eco": "C50",
                "player_color": "white",
                "player_accuracy": 65,
                "phase_accuracy": {"opening": 60, "middlegame": 55, "endgame": 70},
                "tags": ["tag.structure.open"],
                "critical_moves": [{"san": "h3"}],
            }
        )
    for _ in range(3):
        games.append(
            {
                "result": "win",
                "opening_name": "French Defense",
                "eco": "C01",
                "player_color": "black",
                "player_accuracy": 80,
                "phase_accuracy": {"opening": 78, "middlegame": 75, "endgame": 82},
                "tags": ["tag.structure.closed"],
                "critical_moves": [{"san": "c5"}],
            }
        )

    stats = manager._compute_stats(games)
    opening_profiles = stats["opening_profiles"]["list"]
    assert any(profile["key"] == "C50:white" for profile in opening_profiles)
    priority = stats["opening_profiles"]["priority"]
    assert priority
    first_priority = priority[0]
    assert first_priority["key"] == "C50:white"
    assert first_priority["reasons"]

    user_id = "profile-user"
    manager._stats_cache[user_id] = stats
    snapshot = manager.get_opening_profile_snapshot(user_id, "C50", "Italian Game", "white")
    assert snapshot is not None
    assert snapshot["side"] == "white"


def test_get_stats_computes_when_missing():
    manager = ProfileIndexingManager(game_fetcher=DummyFetcher())
    user_id = "missing-cache"
    manager._games[user_id] = [
        {
            "result": "win",
            "opening_name": "Italian Game",
            "eco": "C50",
            "player_color": "white",
            "player_accuracy": 78,
            "phase_accuracy": {"opening": 75, "middlegame": 70, "endgame": 80},
            "tags": ["tag.structure.open"],
        }
    ]

    stats = manager.get_stats(user_id)
    assert stats["overall"]["total_games"] == 1
    assert "opening_profiles" in stats
    snapshot = manager.get_opening_profile_snapshot(user_id, "C50", "Italian Game", "white")
    assert snapshot is not None


@pytest.mark.asyncio
async def test_background_scheduler_respects_target(monkeypatch):
    manager = ProfileIndexingManager(game_fetcher=DummyFetcher())
    user_id = "user-123"
    status = ProfileIndexStatus(state="complete", total_accounts=1)
    status.accounts = [{"platform": "chesscom", "username": "tester"}]
    manager._status[user_id] = status
    manager._games[user_id] = [{"result": "win"} for _ in range(60)]

    called = asyncio.Event()

    async def fake_refresh(u: str):
        called.set()

    monkeypatch.setattr(manager, "_run_background_refresh", fake_refresh)

    await manager.ensure_background_index(user_id)
    await asyncio.sleep(0)

    assert called.is_set()


@pytest.mark.asyncio
async def test_background_scheduler_skips_when_under_target(monkeypatch):
    manager = ProfileIndexingManager(game_fetcher=DummyFetcher())
    user_id = "user-456"
    status = ProfileIndexStatus(state="complete", total_accounts=1)
    status.accounts = [{"platform": "chesscom", "username": "tester"}]
    manager._status[user_id] = status
    manager._games[user_id] = [{"result": "win"} for _ in range(10)]

    called = asyncio.Event()

    async def fake_refresh(u: str):
        called.set()

    monkeypatch.setattr(manager, "_run_background_refresh", fake_refresh)

    await manager.ensure_background_index(user_id)
    await asyncio.sleep(0)

    assert not called.is_set()


def test_normalize_opening_eats_variations():
    manager = ProfileIndexingManager(game_fetcher=DummyFetcher())
    key, label = manager._normalize_opening("C42", "Petrovs-Defense-Classical-Variation")
    assert key == "C42"
    assert "C42" in label and "Petrovs" in label

    key2, label2 = manager._normalize_opening(None, "Caro-Kann-Defense-Classical-Variation")
    assert key2.startswith("caro")
    assert "Caro" in label2


def test_advanced_metric_aggregation():
    manager = ProfileIndexingManager(game_fetcher=DummyFetcher())
    games = [
        {
            "result": "win",
            "advanced_metrics": {
                "pieces": {"rook": {"moves": 4, "cp_loss": 200, "errors": 2}},
                "phase_piece": {
                    "middlegame": {"rook": {"moves": 3, "cp_loss": 150, "errors": 1}}
                },
                "position_types": {"open": {"moves": 2, "cp_loss": 50, "errors": 0}},
                "advantage": {"winning": {"moves": 2, "cp_loss": 30, "errors": 0}},
                "tactic_motifs": {"tag.tactic.fork": {"found": 1, "missed": 1, "cp_gain": 20, "cp_loss": 120}},
                "tactic_phases": {"middlegame": {"opportunities": 2, "found": 1, "missed": 1}},
                "structural": {"tag.file.open.c": {"occurrences": 2, "cp_loss": 40, "wins": 2}},
                "weakness": {"opponent": {"moves": 2, "cp_loss": 20}, "self": {"moves": 1, "cp_loss": 60}},
                "time_buckets": {"<3s": {"moves": 1, "cp_loss": 80, "errors": 1}},
                "rating_buckets": {"higher_rated": {"moves": 2, "cp_loss": 70, "errors": 1}},
                "playstyle": {
                    "aggressive_moves": 3,
                    "aggressive_mistakes": 1,
                    "positional_moves": 1,
                    "material_moves": 2,
                    "material_mistakes": 1,
                    "initiative_moves": 2,
                    "simplify_moves": 1,
                    "tension_moves": 1,
                    "king_safety_moves": 1,
                    "king_safety_errors": 1,
                },
                "conversion": {"winning_positions": 1, "converted": 1, "holds": 0, "squandered": 0, "max_advantage_cp": 450},
                "resilience": {"defensive_positions": 1, "swindles": 0, "saves": 1, "collapsed": 0, "max_deficit_cp": -320},
            },
        }
    ]
    phase_accuracy = {"opening": 78, "middlegame": 65, "endgame": 82}
    advanced = manager._aggregate_advanced_metrics(games, [{"name": "Sicilian", "games": 2, "win_rate": 60}], phase_accuracy)
    assert advanced["accuracy_by_piece"][0]["piece"] == "Rook"
    assert advanced["tactic_motifs"][0]["motif"] == "fork"
    assert advanced["conversion"]["winning_positions"] == 1
    insights = manager._build_insights(advanced, phase_accuracy)
    assert any("rooks" in line.lower() for line in insights["accuracy"])
    assert "tactics" in insights and insights["tactics"]


def test_summarize_opening_history_extracts_sequences():
    manager = ProfileIndexingManager(game_fetcher=DummyFetcher())
    user_id = "user-open"
    sample_pgn = """[Event "?"]
[Site "?"]
[Date "2023.01.01"]
[Round "-"]
[White "User"]
[Black "Opponent"]
[Result "1-0"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 4. c3 Nf6 5. d4 exd4 6. cxd4 Bb4+ 7. Nc3 Nxe4 8. O-O O-O 1-0
"""
    manager._games[user_id] = [
        {
            "eco": "C50",
            "opening_name": "Italian Game",
            "pgn": sample_pgn,
            "result": "win",
            "platform": "lichess",
            "opponent_name": "Tester",
            "critical_moves": [
                {
                    "category": "mistake",
                    "fen_before": "rnbqkbnr/pppp1ppp/8/4p3/3PP3/5N2/PPP2PPP/RNBQKB1R b KQkq - 0 3",
                    "san": "h6",
                    "best_move": "Nc6",
                }
            ],
        }
    ]

    summary = manager.summarize_opening_history(user_id, "C50", "Italian Game", max_games=3)
    assert summary["games_considered"] == 1
    assert summary["top_sequences"][0]["moves"][0] == "e4"
    assert summary["recent_mistakes"][0]["correct_move"] == "Nc6"

