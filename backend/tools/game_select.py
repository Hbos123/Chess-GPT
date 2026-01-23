"""
Game Selection Engine

Deterministic, testable selection of games from a candidate list.
Designed to support multi-request selection like:
- last game / second last
- a win
- a rapid game / a bullet game
- a game as black

This module is intentionally pure (no network). Tool handlers should fetch
candidate games, then call into this selector.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _as_lower_str(x: Any) -> str:
    try:
        return str(x or "").strip().lower()
    except Exception:
        return ""


def _normalize_time_category(x: Any) -> str:
    """
    Normalize user/tool filter values into our canonical time categories:
    bullet | blitz | rapid | classical | daily
    """
    s = _as_lower_str(x)
    if not s:
        return ""
    # common variants
    if "correspond" in s or "daily" in s:
        return "daily"
    if "bullet" in s:
        return "bullet"
    if "blitz" in s:
        return "blitz"
    if "rapid" in s:
        return "rapid"
    if "classical" in s or "standard" in s:
        return "classical"
    # Sometimes the filter might be like "rapid_game" / "bullet_game"
    if s.endswith("_game"):
        return _normalize_time_category(s[:-5])
    return s


def _infer_time_category_from_time_control(game: Dict[str, Any]) -> str:
    """
    Best-effort inference when time_category is missing:
    interpret game["time_control"] as base seconds (supports int, "600", "600+5", "10|0").
    """
    tc = game.get("time_control")
    try:
        if isinstance(tc, (int, float)) and int(tc) > 0:
            base_seconds = int(tc)
        else:
            s = _as_lower_str(tc).replace("|", "+")
            base = s.split("+")[0]
            base_seconds = int(base) if base.isdigit() else None
        if base_seconds is None:
            return ""
        if base_seconds <= 60:
            return "bullet"
        if base_seconds <= 300:
            return "blitz"
        if base_seconds <= 1500:
            return "rapid"
        return "classical"
    except Exception:
        return ""


def _game_identity_key(game: Dict[str, Any]) -> Tuple[str, str]:
    """
    Stable-ish identity key for deduping across platforms.
    Uses (platform, game_id) when present, otherwise (platform, url).
    """
    platform = _as_lower_str(game.get("platform")) or "unknown"
    gid = str(game.get("game_id") or "").strip()
    if gid:
        return (platform, gid)
    url = str(game.get("url") or "").strip()
    return (platform, url)


def _match_filters(game: Dict[str, Any], username: str, filters: Dict[str, Any]) -> bool:
    """
    Match a game against a small set of generic filters.
    We intentionally support the normalized GameFetcher schema:
      - result: win/loss/draw
      - player_color: white/black
      - time_category: bullet/blitz/rapid/classical/daily
      - eco: e.g. "B50"
      - opponent_name / opponent_rating
      - date: "YYYY-MM-DD" (string compare works for ISO dates)
    """
    # result
    r = _as_lower_str(filters.get("result"))
    if r:
        if _as_lower_str(game.get("result")) != r:
            return False

    # time control category
    tc = _normalize_time_category(filters.get("time_control"))
    if tc:
        gtc = _normalize_time_category(game.get("time_category")) or _normalize_time_category(game.get("time_control_type"))
        # lichess uses "correspondence" in some places; treat as daily
        if gtc == "correspondence":
            gtc = "daily"
        if not gtc:
            gtc = _infer_time_category_from_time_control(game)
        # allow substring-ish matches like "rapid_game" -> "rapid"
        if tc != gtc:
            return False

    # color
    color = _as_lower_str(filters.get("color"))
    if color:
        if _as_lower_str(game.get("player_color")) != color:
            return False

    # opening eco prefix
    eco_prefix = str(filters.get("opening_eco") or "").strip().upper()
    if eco_prefix:
        eco = str(game.get("eco") or game.get("opening_eco") or "").strip().upper()
        if not eco.startswith(eco_prefix):
            return False

    # opponent contains
    opp = _as_lower_str(filters.get("opponent"))
    if opp:
        opp_name = _as_lower_str(game.get("opponent_name"))
        if opp_name and opp not in opp_name:
            return False

    # opponent rating range
    try:
        min_or = filters.get("min_opponent_rating")
        if min_or is not None:
            if (game.get("opponent_rating") is None) or (int(game.get("opponent_rating")) < int(min_or)):
                return False
        max_or = filters.get("max_opponent_rating")
        if max_or is not None:
            if (game.get("opponent_rating") is None) or (int(game.get("opponent_rating")) > int(max_or)):
                return False
    except Exception:
        # If parsing fails, be conservative: don't match.
        return False

    # min moves (best-effort; use cached move count if present; otherwise try to count move numbers from pgn)
    min_moves = filters.get("min_moves")
    if min_moves is not None:
        try:
            mm = int(min_moves)
        except Exception:
            return False
        move_count = game.get("min_moves_estimate")
        if move_count is None:
            pgn = str(game.get("pgn") or "")
            # count full-move numbers like "12."
            import re
            move_nums = re.findall(r"\d+\.", pgn)
            move_count = len(move_nums) if move_nums else None
        if move_count is not None and int(move_count) < mm:
            return False

    # date range (ISO date strings compare lexicographically)
    df = str(filters.get("date_from") or "").strip()
    dt = str(filters.get("date_to") or "").strip()
    if df or dt:
        gd = str(game.get("date") or "").strip()
        if not gd:
            return False
        if df and gd < df:
            return False
        if dt and gd > dt:
            return False

    return True


def select_games_from_candidates(
    *,
    candidates: List[Dict[str, Any]],
    username: str,
    requests: List[Dict[str, Any]],
    global_unique: bool = True,
    global_limit: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Select games to satisfy multiple selection requests.

    Each request may include:
      - name: str (required)
      - count: int (default 1)
      - offset: int (default 0)
      - sort: "date_desc" | "date_asc" (default "date_desc")
      - filters: dict (optional) - same keys as _match_filters
      - require_unique: bool (default True)

    Returns:
      {
        "selected": {name: [game_ref, ...], ...},
        "selected_flat": [game_ref, ...],
        "unmet": [{name, requested_count, found_count, reason}],
        "total_candidates": int,
      }
    """
    used_keys = set()
    used_ref_by_key: Dict[Tuple[str, str], Dict[str, Any]] = {}
    selected: Dict[str, List[Dict[str, Any]]] = {}
    unmet: List[Dict[str, Any]] = []

    def to_ref(g: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "game_id": g.get("game_id"),
            "platform": g.get("platform"),
            "url": g.get("url"),
            "date": g.get("date"),
            "time_category": g.get("time_category"),
            "time_control": g.get("time_control"),
            "player_color": g.get("player_color"),
            "result": g.get("result"),
            "opponent_name": g.get("opponent_name"),
            "opponent_rating": g.get("opponent_rating"),
            "eco": g.get("eco"),
            "opening": g.get("opening"),
        }

    def sort_games(games: List[Dict[str, Any]], sort: str) -> List[Dict[str, Any]]:
        reverse = (sort or "date_desc") != "date_asc"
        return sorted(games, key=lambda g: (str(g.get("date") or ""), str(g.get("url") or "")), reverse=reverse)

    selected_flat: List[Dict[str, Any]] = []

    for req in requests or []:
        name = str(req.get("name") or "").strip()
        if not name:
            continue
        count = int(req.get("count", 1) or 1)
        offset = int(req.get("offset", 0) or 0)
        sort = str(req.get("sort") or "date_desc").strip()
        filters = req.get("filters") or {}
        require_unique = bool(req.get("require_unique", True))
        allow_reuse = bool(req.get("allow_reuse", False))

        # Filter + sort
        pool = [g for g in candidates if _match_filters(g, username, filters)]
        pool = sort_games(pool, sort)

        # Apply uniqueness + offset among eligible matches
        # Offset counts positions in sorted pool, not unused games
        picked: List[Dict[str, Any]] = []
        skipped = 0
        for g in pool:
            key = _game_identity_key(g)
            
            # Apply offset BEFORE checking uniqueness
            # Offset counts positions in sorted pool, not unused games
            if skipped < offset:
                skipped += 1
                # Still mark as used if it's already been used (for tracking)
                if key in used_keys:
                    continue
                # Skip this position for offset purposes
                continue
            
            # Now check uniqueness after offset
            if key in used_keys:
                if allow_reuse:
                    # Reuse existing ref without consuming an additional unique slot.
                    ref = used_ref_by_key.get(key)
                    if isinstance(ref, dict):
                        picked.append(ref)
                        if len(picked) >= count:
                            break
                    continue
                if global_unique or require_unique:
                    continue

            # Enforce global unique cap only when we'd add a *new* unique game.
            # (Reused refs should still be allowed even if the cap is reached.)
            if global_limit is not None and (global_unique or require_unique):
                try:
                    if len(used_keys) >= int(global_limit):
                        break
                except Exception:
                    # If global_limit is malformed, ignore it.
                    pass

            ref = to_ref(g)
            picked.append(ref)
            if global_unique or require_unique:
                used_keys.add(key)
                used_ref_by_key[key] = ref
            # Keep selected_flat unique even if later requests reuse a game.
            selected_flat.append(ref)
            if len(picked) >= count:
                break

        selected[name] = picked
        if len(picked) < count:
            unmet.append(
                {
                    "name": name,
                    "requested_count": count,
                    "found_count": len(picked),
                    "reason": "not_enough_matches",
                }
            )

    return {
        "selected": selected,
        "selected_flat": selected_flat,
        "unmet": unmet,
        "total_candidates": len(candidates or []),
    }


