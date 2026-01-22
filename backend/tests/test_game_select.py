from tools.game_select import select_games_from_candidates


def _mk(
    *,
    game_id: str,
    date: str,
    time_category: str,
    player_color: str,
    result: str,
    opponent_name: str,
    eco: str = "",
    platform: str = "chess.com",
):
    return {
        "game_id": game_id,
        "platform": platform,
        "url": f"https://example/{platform}/{game_id}",
        "date": date,
        "time_category": time_category,
        "time_control": time_category,
        "player_color": player_color,
        "result": result,
        "opponent_name": opponent_name,
        "opponent_rating": 1500,
        "eco": eco,
        "opening": "",
        "pgn": "1. e4 e5 2. Nf3 Nc6 *",
    }


def test_select_games_supports_aliasing_and_uniqueness_budget():
    # Most recent first by date
    candidates = [
        _mk(game_id="g1", date="2026-01-01", time_category="bullet", player_color="black", result="loss", opponent_name="OppA"),
        _mk(game_id="g2", date="2025-12-31", time_category="rapid", player_color="white", result="win", opponent_name="OppB"),
        _mk(game_id="g3", date="2025-12-30", time_category="blitz", player_color="black", result="draw", opponent_name="OppC"),
        _mk(game_id="g4", date="2025-12-29", time_category="rapid", player_color="black", result="win", opponent_name="OppD"),
        _mk(game_id="g5", date="2025-12-28", time_category="bullet", player_color="white", result="win", opponent_name="OppE"),
    ]

    requests = [
        {"name": "last_game", "count": 1, "offset": 0, "sort": "date_desc", "require_unique": True},
        {"name": "second_last", "count": 1, "offset": 1, "sort": "date_desc", "require_unique": True},
        {"name": "a_win", "count": 1, "filters": {"result": "win"}, "require_unique": True},
        # These can reuse previously selected games to keep the total unique set small.
        {"name": "a_rapid", "count": 1, "filters": {"time_control": "rapid"}, "allow_reuse": True},
        {"name": "a_bullet", "count": 1, "filters": {"time_control": "bullet"}, "allow_reuse": True},
        {"name": "as_black", "count": 1, "filters": {"color": "black"}, "allow_reuse": True},
    ]

    out = select_games_from_candidates(
        candidates=candidates,
        username="me",
        requests=requests,
        global_unique=True,
        global_limit=5,
    )

    assert out["unmet"] == []
    sel = out["selected"]
    assert sel["last_game"][0]["game_id"] == "g1"
    assert sel["second_last"][0]["game_id"] == "g2"
    # a_win must be a win distinct from g2 if uniqueness prevents reusing g2 for this label
    assert sel["a_win"][0]["result"] == "win"
    assert sel["a_rapid"][0]["time_category"] == "rapid"
    assert sel["a_bullet"][0]["time_category"] == "bullet"
    assert sel["as_black"][0]["player_color"] == "black"

    # Unique list should not exceed budget and should not contain duplicates
    flat = out["selected_flat"]
    assert len(flat) <= 5
    keys = {(g.get("platform"), g.get("game_id")) for g in flat}
    assert len(keys) == len(flat)


