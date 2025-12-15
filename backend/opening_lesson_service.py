"""
Opening lesson orchestration service.
Combines Lichess explorer data with user history to build personalized lessons.
"""

import hashlib
import time
from typing import Any, Dict, List, Optional, Tuple

import chess
import chess.pgn

from fen_analyzer import analyze_fen
from opening_builder import build_opening_lesson


def _color_from_turn(fen: str) -> str:
    try:
        return "white" if chess.Board(fen).turn else "black"
    except Exception:
        return "white"


def _build_move_descriptor(board: chess.Board, san: str, source: str) -> Optional[Dict[str, Any]]:
    try:
        move = board.parse_san(san)
        uci = move.uci()
        return {
            "san": san,
            "uci": uci,
            "from": uci[:2],
            "to": uci[2:4],
            "promotion": uci[4:] if len(uci) > 4 else None,
            "source": source,
        }
    except Exception:
        return None


def _derive_user_alternates(history: List[str], opening_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Surface up to three user-played alternates with basic stats."""
    history_len = len(history)
    candidate_stats: Dict[str, Dict[str, Any]] = {}

    for variation in opening_summary.get("user_variations", []):
        moves = variation.get("moves", [])
        if len(moves) <= history_len or moves[:history_len] != history:
            continue

        candidate = moves[history_len]
        record = candidate_stats.setdefault(
            candidate,
            {
                "san": candidate,
                "games": 0,
                "wins": 0,
                "losses": 0,
                "draws": 0,
                "platform": None,
                "last_played": None,
            },
        )
        record["games"] += 1
        result = (variation.get("result") or "").lower()
        if result == "win":
            record["wins"] += 1
        elif result == "loss":
            record["losses"] += 1
        elif result == "draw":
            record["draws"] += 1

        occurred_on = variation.get("date")
        if occurred_on and (
            not record["last_played"]
            or str(occurred_on) > str(record["last_played"])
        ):
            record["last_played"] = occurred_on
            record["platform"] = variation.get("platform")

    sorted_candidates = sorted(
        candidate_stats.values(), key=lambda entry: entry["games"], reverse=True
    )[:3]

    formatted: List[Dict[str, Any]] = []
    for entry in sorted_candidates:
        formatted.append(
            {
                "san": entry["san"],
                "personal_record": {
                    "games": entry["games"],
                    "wins": entry["wins"],
                    "losses": entry["losses"],
                    "draws": entry["draws"],
                },
                "platform": entry.get("platform"),
                "last_played": entry.get("last_played"),
            }
        )

    return formatted


async def _extract_tags_for_nodes(nodes: List[Dict[str, Any]], engine_queue, max_nodes: int = 6) -> None:
    if not engine_queue:
        return
    sampled = nodes[:max_nodes]
    for node in sampled:
        fen = node.get("fen")
        if not fen:
            continue
        try:
            analysis = await analyze_fen(fen, engine_queue, depth=12)
            tags = analysis.get("tags", [])
            white_tags = sorted({t.get("tag_name") for t in tags if t.get("side") == "white" and t.get("tag_name")})[:6]
            black_tags = sorted({t.get("tag_name") for t in tags if t.get("side") == "black" and t.get("tag_name")})[:6]
            highlight_squares = []
            for tag in tags:
                highlight_squares.extend(tag.get("squares", []))
            node["tags"] = {
                "white": white_tags,
                "black": black_tags,
            }
            if highlight_squares:
                node["tag_highlights"] = sorted(set(highlight_squares))
        except Exception as exc:
            print(f"⚠️ Tag extraction failed for lesson node: {exc}")


def _append_ai_responses(lesson_nodes: List[Dict[str, Any]]) -> None:
    for idx, node in enumerate(lesson_nodes):
        next_node = lesson_nodes[idx + 1] if idx + 1 < len(lesson_nodes) else None
        ai_responses: List[Dict[str, Any]] = []
        if next_node and next_node.get("recommended_source") == "mainline":
            ai_move = next_node.get("incoming_ai_move")
            if ai_move:
                ai_responses.append(ai_move)
        node["ai_responses"] = ai_responses


def _attach_next_ids(nodes: List[Dict[str, Any]]) -> None:
    for idx, node in enumerate(nodes):
        node["next_node_id"] = nodes[idx + 1]["id"] if idx + 1 < len(nodes) else None


def _build_personal_overview(
    profile_snapshot: Optional[Dict[str, Any]],
    opening_summary: Dict[str, Any],
    opening_name: str,
) -> Dict[str, Any]:
    if not profile_snapshot:
        return {
            "title": f"{opening_name} snapshot",
            "games_played": opening_summary.get("games_considered", 0),
            "win_rate": None,
            "opening_accuracy": None,
            "strengths": ["Limited data indexed for this opening so far."],
            "issues": [],
            "common_tags": [],
        }

    strengths: List[str] = []
    issues: List[str] = []

    win_rate = profile_snapshot.get("win_rate")
    opening_acc = profile_snapshot.get("opening_accuracy")
    middlegame_acc = profile_snapshot.get("middlegame_accuracy")
    best_tag = profile_snapshot.get("common_tags", [None])[0]

    if win_rate is not None:
        if win_rate >= 55:
            strengths.append(f"Solid results: {win_rate}% win rate in this line.")
        else:
            issues.append(f"Win rate is {win_rate}%, below the desired 55%+ threshold.")

    if opening_acc is not None:
        if opening_acc >= 75:
            strengths.append(f"Opening accuracy averages {opening_acc}%.")
        else:
            issues.append(f"Opening accuracy dips to {opening_acc}%. Focus on the first 10 moves.")

    if middlegame_acc is not None and opening_acc is not None:
        if middlegame_acc < opening_acc - 5:
            issues.append("Positions are reached successfully but middlegame conversion lags.")

    if best_tag:
        strengths.append(f"Comfortable with {best_tag} structures in this line.")

    if not strengths:
        strengths.append("Flexible understanding of the structure—build on it with concrete plans.")
    if not issues:
        issues.append("Continue practicing critical moments to turn small edges into wins.")

    return {
        "title": f"{profile_snapshot.get('name', opening_name)} ({profile_snapshot.get('side', 'white').title()})",
        "games_played": profile_snapshot.get("games", 0),
        "win_rate": win_rate,
        "opening_accuracy": opening_acc,
        "strengths": strengths,
        "issues": issues,
        "common_tags": profile_snapshot.get("common_tags", []),
    }


def _build_model_line_sections(lesson_plan: Dict[str, Any]) -> Dict[str, Any]:
    overview = next((section for section in lesson_plan.get("sections", []) if section.get("type") == "overview"), None)
    alternates_section = next(
        (section for section in lesson_plan.get("sections", []) if section.get("type") == "alternates"),
        {},
    )
    main_line = {
        "name": lesson_plan.get("title"),
        "moves": lesson_plan.get("main_line_moves", []),
        "key_ideas": overview.get("key_ideas") if overview else [],
    }
    alternates: List[Dict[str, Any]] = []
    for branch in alternates_section.get("branches", []) or []:
        alternates.append(
            {
                "name": branch.get("name"),
                "checkpoints": branch.get("checkpoints", []),
            }
        )
    return {"main_line": main_line, "alternates": alternates}


def _build_user_game_walkthroughs(opening_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    walkthroughs: List[Dict[str, Any]] = []
    for variation in opening_summary.get("user_variations", [])[:3]:
        walkthroughs.append(
            {
                "moves": variation.get("moves", []),
                "result": variation.get("result"),
                "opponent": variation.get("opponent"),
                "date": variation.get("date"),
                "platform": variation.get("platform"),
            }
        )
    for mistake in opening_summary.get("recent_mistakes", [])[:3]:
        walkthroughs.append(
            {
                "fen": mistake.get("fen"),
                "prompt": mistake.get("prompt"),
                "correct_move": mistake.get("correct_move"),
            }
        )
    return walkthroughs


def _build_problem_patterns(
    profile_snapshot: Optional[Dict[str, Any]],
    opening_summary: Dict[str, Any],
) -> Dict[str, Any]:
    patterns: List[Dict[str, Any]] = []
    if profile_snapshot and profile_snapshot.get("common_tags"):
        for tag in profile_snapshot["common_tags"]:
            patterns.append(
                {
                    "label": tag,
                    "detail": f"Recurring motif in your games—review theory ideas when {tag} appears.",
                }
            )
    for mistake in opening_summary.get("recent_mistakes", [])[:2]:
        patterns.append(
            {
                "label": "Critical moment",
                "detail": mistake.get("prompt"),
            }
        )
    if not patterns:
        patterns.append({"label": "Explore deeper", "detail": "Play a few more games here to surface themes."})
    return {"patterns": patterns}


def _build_drill_package(
    opening_summary: Dict[str, Any],
    practice_positions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    drills: List[Dict[str, Any]] = []
    for mistake in opening_summary.get("recent_mistakes", [])[:5]:
        drills.append(
            {
                "fen": mistake.get("fen"),
                "prompt": mistake.get("prompt"),
                "correct_move": mistake.get("correct_move"),
            }
        )
    return {
        "tactics": drills,
        "practice_positions": practice_positions,
    }


def _build_summary_block(personal_overview: Dict[str, Any], problem_patterns: Dict[str, Any]) -> Dict[str, Any]:
    key_points = []
    if personal_overview.get("issues"):
        key_points.extend(personal_overview["issues"][:2])
    if problem_patterns.get("patterns"):
        key_points.extend(pattern["detail"] for pattern in problem_patterns["patterns"][:2])
    if not key_points:
        key_points.append("Keep reinforcing the main line until it feels automatic.")
    return {"takeaways": key_points[:4]}


def _collect_primary_fens(lesson_plan: Dict[str, Any]) -> List[str]:
    fens: List[str] = []
    for section in lesson_plan.get("sections", []):
        if section.get("type") in {"walkthrough", "overview"}:
            for checkpoint in section.get("checkpoints", []) or []:
                fen = checkpoint.get("fen")
                if fen:
                    fens.append(fen)
        if section.get("branches"):
            for branch in section["branches"]:
                for checkpoint in branch.get("checkpoints", []) or []:
                    fen = checkpoint.get("fen")
                    if fen:
                        fens.append(fen)
    return fens


def _mistake_positions_from_summary(opening_summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    positions: List[Dict[str, Any]] = []
    for mistake in opening_summary.get("recent_mistakes", [])[:5]:
        fen = mistake.get("fen")
        if not fen:
            continue
        try:
            board = chess.Board(fen)
            side = "white" if board.turn else "black"
        except Exception:
            side = "white"
        prompt = mistake.get("prompt") or "Find the best continuation from your game"
        positions.append(
            {
                "fen": fen,
                "objective": prompt,
                "hints": [
                    "This position comes directly from one of your games.",
                    f"Correct move: {mistake.get('correct_move') or 'See solution'}",
                ],
                "candidates": [],
                "side": side,
                "difficulty": "advanced",
                "themes": ["user_game", "mistake"],
            }
        )
    return positions


async def _build_master_references(
    fens: List[str],
    explorer_client,
    orientation: str,
) -> List[Dict[str, Any]]:
    references: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for fen in fens:
        key = fen.split(" ")[0]
        if key in seen:
            continue
        seen.add(key)
        try:
            masters_data = await explorer_client.query_position(
                fen,
                db="masters",
                speeds=["classical", "rapid"],
                ratings=[2200, 2800],
            )
        except Exception:
            continue
        top_games = masters_data.get("topGames") or []
        opening_meta = masters_data.get("opening") or {}
        for game in top_games[:2]:
            references.append(
                {
                    "fen": fen,
                    "white": game.get("white"),
                    "black": game.get("black"),
                    "winner": game.get("winner"),
                    "year": game.get("year"),
                    "moves": game.get("moves", [])[:12],
                    "orientation": orientation,
                    "eco": opening_meta.get("eco"),
                    "opening_name": opening_meta.get("name"),
                }
            )
        if len(references) >= 4:
            break
    return references


def _sequence_to_query(moves: List[str]) -> str:
    """Convert a SAN move list into a PGN-style query string."""
    if not moves:
        return ""
    parts: List[str] = []
    move_number = 1
    for idx, san in enumerate(moves):
        if idx % 2 == 0:
            parts.append(f"{move_number}. {san}")
        else:
            parts.append(f"{san}")
            move_number += 1
    # Ensure trailing space between move pairs
    return " ".join(parts)


def _hash_sequence(moves: List[str]) -> str:
    """Stable hash for a move sequence."""
    joined = " ".join(moves)
    return hashlib.md5(joined.encode("utf-8")).hexdigest()[:12]


def _build_lesson_positions_from_checkpoints(checkpoints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    positions: List[Dict[str, Any]] = []
    for idx, cp in enumerate(checkpoints):
        history = cp.get("moves_san", [])
        positions.append(
            {
                "id": cp.get("id") or f"checkpoint-{idx}",
                "fen": cp.get("fen"),
                "objective": cp.get("objective") or "Find the best continuation",
                "hints": [
                    f"Moves so far: {' '.join(history[:10])}",
                ],
                "candidates": [move.get("san") for move in cp.get("popular_replies", [])],
                "side": _color_from_turn(cp.get("fen", "")),
                "difficulty": "intermediate",
                "themes": ["opening", "continuation"],
                "history": history,
                "popular_replies": cp.get("popular_replies", []),
            }
        )
    return positions


def _build_positions_from_lesson(lesson: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten lesson sections into draggable lesson positions."""
    positions: List[Dict[str, Any]] = []
    for section in lesson.get("sections", []):
        if section.get("checkpoints"):
            positions.extend(_build_lesson_positions_from_checkpoints(section["checkpoints"]))
        if section.get("branches"):
            for branch in section["branches"]:
                positions.extend(_build_lesson_positions_from_checkpoints(branch.get("checkpoints", [])))
        if section.get("fens"):
            for fen in section["fens"]:
                positions.append(
                    {
                        "id": f"drill-{len(positions)}",
                        "fen": fen,
                        "objective": "Practice the resulting position",
                        "hints": [],
                        "candidates": [],
                        "side": _color_from_turn(fen),
                        "difficulty": "intermediate",
                        "themes": ["opening", "drill"],
                        "history": [],
                        "popular_replies": [],
                    }
                )
    return positions


def _filter_positions_for_orientation(positions: List[Dict[str, Any]], orientation: str) -> List[Dict[str, Any]]:
    orientation = orientation or "white"
    filtered = []
    for pos in positions:
        if pos.get("side") == orientation:
            filtered.append(pos)
    if filtered:
        return filtered
    return positions


def _build_lesson_tree(
    positions: List[Dict[str, Any]],
    main_line_moves: List[str],
    opening_summary: Dict[str, Any],
    orientation: str,
) -> List[Dict[str, Any]]:
    nodes: List[Dict[str, Any]] = []
    for idx, pos in enumerate(positions):
        fen = pos.get("fen")
        if not fen:
            continue
        history = pos.get("history", [])
        board = chess.Board(fen)
        options: List[Dict[str, Any]] = []
        user_alternates = _derive_user_alternates(history, opening_summary)
        for i, reply in enumerate(pos.get("popular_replies", [])[:4]):
            descriptor = _build_move_descriptor(board, reply.get("san"), "mainline" if i == 0 else "lichess")
            if descriptor:
                descriptor["popularity"] = (
                    reply.get("popularity")
                    or reply.get("pop")
                )
                descriptor["win_rate"] = reply.get("score")
                options.append(descriptor)
        for alt in user_alternates:
            if isinstance(alt, str):
                descriptor = _build_move_descriptor(board, alt, "user_history")
            else:
                descriptor = _build_move_descriptor(board, alt.get("san"), "user_history")
            if descriptor:
                if isinstance(alt, dict):
                    descriptor["personal_record"] = alt.get("personal_record")
                    descriptor["last_played"] = alt.get("last_played")
                    descriptor["platform"] = alt.get("platform")
                options.append(descriptor)
        main_move = options[0] if options else None
        # Determine AI follow-up from main line
        next_ai_move = None
        if main_move:
            try:
                line_index = len(history)
                if line_index + 1 < len(main_line_moves):
                    temp_board = chess.Board(fen)
                    temp_board.push(temp_board.parse_san(main_line_moves[line_index]))
                    ai_san = main_line_moves[line_index + 1]
                    temp_board.push(temp_board.parse_san(ai_san))
                    next_ai_move = _build_move_descriptor(
                        chess.Board(fen),
                        ai_san,
                        "mainline_response",
                    )
            except Exception:
                next_ai_move = None
        node = {
            "id": pos.get("id") or f"lesson-node-{idx}",
            "fen": fen,
            "side": pos.get("side"),
            "objective": pos.get("objective"),
            "hints": pos.get("hints", []),
            "main_move": main_move,
            "alternate_moves": options[1:],
            "history": history,
            "tag_highlights": [],
            "tags": {"white": [], "black": []},
            "recommended_source": main_move.get("source") if main_move else None,
            "incoming_ai_move": next_ai_move,
        }
        nodes.append(node)
    _attach_next_ids(nodes)
    _append_ai_responses(nodes)
    return nodes


async def create_opening_lesson_payload(
    request_data: Dict[str, Any],
    explorer_client,
    profile_indexer,
    supabase_client,
    engine_queue=None,
) -> Dict[str, Any]:
    """
    Generate a personalized opening lesson payload.

    Args:
        request_data: Dict matching OpeningLessonRequest fields
        explorer_client: Lichess explorer client
        profile_indexer: ProfileIndexingManager instance
        supabase_client: Supabase client (optional)

    Returns:
        Dict with lesson plan, personalization, metadata, and quiz prompts
    """
    user_id: str = request_data.get("user_id")
    chat_id: Optional[str] = request_data.get("chat_id")
    opening_query: Optional[str] = request_data.get("opening_query")
    fen: Optional[str] = request_data.get("fen")
    eco: Optional[str] = request_data.get("eco")
    orientation: str = request_data.get("orientation") or "white"
    variation_hint: Optional[str] = request_data.get("variation_hint")

    inferred_opening_name = opening_query
    resolved_fen = fen

    # If no explicit query provided, infer from FEN
    if not opening_query and fen:
        explorer_data = await explorer_client.query_position(fen)
        opening_info = explorer_data.get("opening", {})
        inferred_opening_name = opening_info.get("name", "Current opening")
        eco = eco or opening_info.get("eco")
    elif opening_query and not fen:
        # Try to resolve query to FEN so we can pass to explorer
        resolved = await explorer_client.parse_san_to_fen(opening_query.split())
        resolved_fen = resolved

    if not inferred_opening_name:
        inferred_opening_name = "Current opening"

    # Summarize user history for personalization + variation selection
    opening_summary = profile_indexer.summarize_opening_history(
        user_id=user_id,
        eco=eco,
        opening_name=inferred_opening_name,
        max_games=12,
    )
    opening_profile_snapshot = None
    if profile_indexer:
        opening_profile_snapshot = profile_indexer.get_opening_profile_snapshot(
            user_id=user_id,
            eco=eco,
            opening_name=inferred_opening_name,
            side=orientation,
        )

    sequence_choice: Optional[Dict[str, Any]] = None
    recent_variation_hashes: List[str] = []

    # Pull previous lessons from Supabase for variation rotation
    recent_lessons: List[Dict[str, Any]] = []
    if supabase_client:
        recent_lessons = supabase_client.get_recent_opening_lessons(
            user_id=user_id,
            opening_key=eco or inferred_opening_name,
            limit=5,
        )
        recent_variation_hashes = [lesson.get("variation_hash") for lesson in recent_lessons if lesson.get("variation_hash")]

    for candidate in opening_summary.get("top_sequences", []):
        if candidate.get("hash") not in recent_variation_hashes:
            sequence_choice = candidate
            break

    if not sequence_choice and opening_summary.get("top_sequences"):
        sequence_choice = opening_summary["top_sequences"][0]

    seed_query = opening_query or inferred_opening_name
    if sequence_choice:
        seed_query = _sequence_to_query(sequence_choice.get("moves", [])) or seed_query

    if variation_hint:
        seed_query = variation_hint

    # Build base lesson with explorer data
    lesson_plan = await build_opening_lesson(
        opening_query=seed_query,
        explorer=explorer_client,
    )

    lesson_meta = lesson_plan.get("meta", {})
    lesson_plan["personalized_variations"] = opening_summary.get("user_variations", [])

    # Build quiz prompts from recent mistakes
    quiz_prompts: List[Dict[str, Any]] = []
    for mistake in opening_summary.get("recent_mistakes", []):
        quiz_prompts.append(
            {
                "fen": mistake.get("fen"),
                "prompt": mistake.get("prompt"),
                "expected": mistake.get("correct_move"),
                "context": mistake.get("context"),
            }
        )

    lesson_plan["quizzes"] = quiz_prompts

    # Compose metadata and history record
    variation_hash = sequence_choice.get("hash") if sequence_choice else _hash_sequence(lesson_plan.get("main_line_moves", [])[:6])
    metadata = {
        "lesson_id": lesson_plan.get("lesson_id"),
        "opening_name": lesson_plan.get("title"),
        "eco": lesson_meta.get("eco") or eco,
        "orientation": lesson_meta.get("orientation") or orientation,
        "seed_query": seed_query,
        "variation_hash": variation_hash,
        "difficulty": "intermediate",
        "timestamp": time.time(),
    }

    profile_indexer.record_opening_lesson_usage(user_id, metadata)

    if supabase_client:
        supabase_client.save_opening_lesson(
            user_id=user_id,
            lesson_data={
                "lesson_id": metadata["lesson_id"],
                "opening_name": metadata["opening_name"],
                "eco": metadata["eco"],
                "variation_hash": variation_hash,
                "orientation": metadata["orientation"],
                "seed_query": seed_query,
                "chat_id": chat_id,
                "difficulty": metadata["difficulty"],
                "metadata": metadata,
            },
        )

    practice_positions = _build_positions_from_lesson(lesson_plan)
    mistake_positions = _mistake_positions_from_summary(opening_summary)
    practice_positions.extend(mistake_positions)
    personal_overview = _build_personal_overview(
        opening_profile_snapshot,
        opening_summary,
        inferred_opening_name,
    )
    model_lines = _build_model_line_sections(lesson_plan)
    user_games = _build_user_game_walkthroughs(opening_summary)
    problem_patterns = _build_problem_patterns(opening_profile_snapshot, opening_summary)
    drills = _build_drill_package(opening_summary, practice_positions)
    summary_block = _build_summary_block(personal_overview, problem_patterns)
    master_refs = await _build_master_references(
        _collect_primary_fens(lesson_plan),
        explorer_client,
        orientation,
    )

    lesson_sections = [
        {"type": "personal_overview", "title": "Your Baseline"},
        {"type": "model_lines", "title": "Model Lines"},
        {"type": "user_games", "title": "Your Games"},
        {"type": "problem_patterns", "title": "Problem Patterns"},
        {"type": "masters", "title": "Model Games"},
        {"type": "drills", "title": "Drills & Practice"},
        {"type": "summary", "title": "Summary"},
    ]

    lesson_blueprint = {
        "lesson_id": metadata["lesson_id"],
        "title": metadata["opening_name"],
        "sections": lesson_sections,
    }

    orientation_color = request_data.get("orientation") or lesson_meta.get("orientation") or "white"
    orientation_color = orientation_color.lower()
    filtered_positions = _filter_positions_for_orientation(practice_positions, orientation_color)
    lesson_tree = _build_lesson_tree(
        filtered_positions,
        lesson_plan.get("main_line_moves", []),
        opening_summary,
        orientation_color,
    )
    await _extract_tags_for_nodes(lesson_tree, engine_queue)

    response = {
        "lesson": lesson_blueprint,
        "personal_overview": personal_overview,
        "model_lines": model_lines,
        "user_games": user_games,
        "problem_patterns": problem_patterns,
        "master_refs": master_refs,
        "drills": drills,
        "summary": summary_block,
        "personalization": opening_summary,
        "metadata": metadata,
        "recent_lessons": recent_lessons,
        "practice_positions": practice_positions,
        "positions": practice_positions,
        "canonical_plan": lesson_plan,
        "lesson_tree": lesson_tree,
    }

    return response

