"""
Investigator - Chess Intelligence Engine
Purpose: Execute chess analysis and return structured conclusions.
FORBIDDEN: English sentences, coaching tone, speculation, explanation.
All outputs are structured data or enums.
"""

import chess
import chess.engine
import chess.pgn
import io
import re
from typing import Dict, Any, List, Optional, Callable, Tuple
from dataclasses import dataclass, field
from light_raw_analyzer import LightRawAnalysis, compute_light_raw_analysis
from evidence_semantic_story import build_semantic_story


@dataclass
class EvidenceLine:
    """
    Structured evidence line extracted from analysis output.
    Generic, position-agnostic.
    """
    moves: List[str]  # SAN moves (2-4 plies max)
    source: str  # "pv" | "pgn" | "threat" | "validated"
    context: Optional[str] = None  # Optional context (e.g., "before_move", "after_move", "refutation")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "moves": self.moves,
            "source": self.source,
            "context": self.context
        }


@dataclass
class InvestigationResult:
    """Structured facts only - NO prose"""
    # Position facts
    eval_before: Optional[float] = None  # In pawns
    eval_after: Optional[float] = None  # In pawns
    eval_drop: Optional[float] = None  # In pawns
    
    # Move facts
    player_move: Optional[str] = None  # SAN notation
    best_move: Optional[str] = None  # UCI notation
    missed_move: Optional[str] = None  # SAN notation
    
    # NEW: Move classification flags
    user_proposed_move: bool = False  # True only if user explicitly named the move
    candidate_move: bool = False  # True if move is natural solution to user's goal
    is_awkward_development: bool = False  # True if move is awkward but natural
    
    # Classification (enums, not prose)
    intent_mismatch: Optional[bool] = None
    game_phase: Optional[str] = None  # "opening", "middlegame", "endgame"
    urgency: Optional[str] = None  # "critical", "high", "normal"
    
    # Multi-branched PGN
    pgn_branches: Dict[str, str] = field(default_factory=dict)  # branch_name -> PGN string
    
    # Tactical facts
    tactics_found: List[Dict[str, Any]] = field(default_factory=list)
    
    # Threat facts
    threats: List[Dict[str, Any]] = field(default_factory=list)
    
    # Delta facts
    material_change: Optional[float] = None  # In pawns
    positional_change: Optional[float] = None  # In centipawns
    theme_changes: Dict[str, float] = field(default_factory=dict)
    
    # Additional structured data
    candidate_moves: List[Dict[str, Any]] = field(default_factory=list)  # [{move: str, eval: float}, ...]
    pv_after_move: List[str] = field(default_factory=list)  # Principal variation after move
    
    # NEW: Light raw analysis (themes + tags)
    light_raw_analysis: Optional[LightRawAnalysis] = None
    
    # NEW: Dual-depth analysis
    eval_d16: Optional[float] = None  # D16 evaluation (ground truth)
    # NOTE: For dual-depth analysis, we standardize these as SAN for UI/display.
    # The UCI best move is available via best_move (and internal analysis dicts).
    best_move_d16: Optional[str] = None  # D16 best move (SAN)
    best_move_d16_eval_cp: Optional[int] = None  # D16 best move eval in centipawns
    second_best_move_d16: Optional[str] = None  # D16 second best move (SAN)
    second_best_move_d16_eval_cp: Optional[int] = None  # D16 second best move eval in centipawns
    is_critical: Optional[bool] = None  # True if cp loss > 50 between best and second best
    is_winning: Optional[bool] = None  # True if best and second best have different signs
    eval_d2: Optional[float] = None  # D2 evaluation (shallow)
    top_moves_d2: List[Dict[str, Any]] = field(default_factory=list)  # D2 top moves list
    overestimated_moves: List[str] = field(default_factory=list)  # Moves overestimated by D2
    
    # NEW: Multi-branched exploration
    exploration_tree: Dict[str, Any] = field(default_factory=dict)  # Tree structure of all branches
    pgn_exploration: str = ""  # Massive PGN with all branches, themes, tactics, commentary
    themes_identified: List[str] = field(default_factory=list)  # Themes found in exploration
    commentary: Dict[str, str] = field(default_factory=dict)  # Move-by-move commentary
    
    # NEW: Goal search results (for investigate_target)
    goal_search_results: Dict[str, Any] = field(default_factory=dict)  # goal_status, witness_line_san, witnesses, best_progress_reached, limits
    
    # NEW: Structured evidence index (deterministically extracted from analysis)
    evidence_index: List[EvidenceLine] = field(default_factory=list)  # Evidence lines available for Claims

    # NEW: Structured deltas for the main evidence line (avoid downstream PGN regex parsing)
    # These are intended to be the single source of truth for tags/roles deltas + net changes shown to the user.
    evidence_starting_fen: Optional[str] = None  # Position before the player's move (if available)
    evidence_pgn_line: Optional[str] = None  # Canonical short line used for evidence/net changes (SAN, 2-4 plies)
    evidence_main_line_moves: List[str] = field(default_factory=list)  # Parsed SAN moves for evidence_pgn_line
    evidence_per_move_deltas: List[Dict[str, Any]] = field(default_factory=list)  # [{move, tags_gained, tags_lost, roles_gained, roles_lost}]
    # NEW: Per-move state series for the evidence line (so LLM can name pieces correctly from FEN)
    # Each entry includes: ply, move_san, fen_before, fen_after, eval/material/positional before/after.
    evidence_per_move_stats: List[Dict[str, Any]] = field(default_factory=list)
    evidence_tags_gained_net: List[str] = field(default_factory=list)
    evidence_tags_lost_net: List[str] = field(default_factory=list)
    # NEW: Preserve full/raw net tags (including clutter like diagonal/key) for deep/raw analysis.
    evidence_tags_gained_net_raw: List[str] = field(default_factory=list)
    evidence_tags_lost_net_raw: List[str] = field(default_factory=list)
    # NEW: Structured net tag instances (preserve squares/pieces/details so tags can be linked to pieces)
    evidence_tags_gained_net_structured: List[Dict[str, Any]] = field(default_factory=list)
    evidence_tags_lost_net_structured: List[Dict[str, Any]] = field(default_factory=list)
    evidence_roles_gained_net: List[str] = field(default_factory=list)
    evidence_roles_lost_net: List[str] = field(default_factory=list)

    # NEW: Evidence-line eval decomposition (all values in pawns, normalized + for White, - for Black)
    # This is the core quantitative justification for whether the evidence line favors White or Black.
    evidence_end_fen: Optional[str] = None
    evidence_eval_start: Optional[float] = None
    evidence_eval_end: Optional[float] = None
    evidence_eval_delta: Optional[float] = None
    evidence_material_start: Optional[float] = None
    evidence_material_end: Optional[float] = None
    evidence_positional_start: Optional[float] = None
    evidence_positional_end: Optional[float] = None
    
    def to_dict(self, include_semantic_story: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for serialization.

        NOTE: semantic_story is expensive to build and should be opt-in; default is False.
        """
        payload = {
            "eval_before": self.eval_before,
            "eval_after": self.eval_after,
            "eval_drop": self.eval_drop,
            "player_move": self.player_move,
            "best_move": self.best_move,
            "missed_move": self.missed_move,
            "intent_mismatch": self.intent_mismatch,
            "game_phase": self.game_phase,
            "urgency": self.urgency,
            "pgn_branches": self.pgn_branches,
            "tactics_found": self.tactics_found,
            "threats": self.threats,
            "material_change": self.material_change,
            "positional_change": self.positional_change,
            "theme_changes": self.theme_changes,
            "candidate_moves": self.candidate_moves,
            "pv_after_move": self.pv_after_move,
            "user_proposed_move": self.user_proposed_move,
            "candidate_move": self.candidate_move,
            "is_awkward_development": self.is_awkward_development,
            "light_raw_analysis": self.light_raw_analysis.to_dict() if self.light_raw_analysis else None,
            "eval_d16": self.eval_d16,
            "best_move_d16": self.best_move_d16,
            "best_move_d16_eval_cp": self.best_move_d16_eval_cp,
            "second_best_move_d16": self.second_best_move_d16,
            "second_best_move_d16_eval_cp": self.second_best_move_d16_eval_cp,
            "is_critical": self.is_critical,
            "is_winning": self.is_winning,
            "eval_d2": self.eval_d2,
            "top_moves_d2": self.top_moves_d2,
            "overestimated_moves": self.overestimated_moves,
            "exploration_tree": self.exploration_tree,
            "pgn_exploration": self.pgn_exploration,
            "themes_identified": self.themes_identified,
            "commentary": self.commentary,
            # NEW: Deterministic evidence lines (2-4 plies each) for claim binding / frontend UI
            "evidence_index": [e.to_dict() for e in self.evidence_index] if self.evidence_index else [],

            # NEW: Structured deltas + net changes for evidence line (single source of truth)
            "evidence_starting_fen": self.evidence_starting_fen,
            "evidence_pgn_line": self.evidence_pgn_line,
            "evidence_main_line_moves": self.evidence_main_line_moves,
            "evidence_per_move_deltas": self.evidence_per_move_deltas,
            "evidence_per_move_stats": self.evidence_per_move_stats,
            "evidence_tags_gained_net": self.evidence_tags_gained_net,
            "evidence_tags_lost_net": self.evidence_tags_lost_net,
            "evidence_tags_gained_net_raw": self.evidence_tags_gained_net_raw,
            "evidence_tags_lost_net_raw": self.evidence_tags_lost_net_raw,
            "evidence_tags_gained_net_structured": self.evidence_tags_gained_net_structured,
            "evidence_tags_lost_net_structured": self.evidence_tags_lost_net_structured,
            "evidence_roles_gained_net": self.evidence_roles_gained_net,
            "evidence_roles_lost_net": self.evidence_roles_lost_net,

            # NEW: Evidence-line eval decomposition
            "evidence_end_fen": self.evidence_end_fen,
            "evidence_eval_start": self.evidence_eval_start,
            "evidence_eval_end": self.evidence_eval_end,
            "evidence_eval_delta": self.evidence_eval_delta,
            "evidence_material_start": self.evidence_material_start,
            "evidence_material_end": self.evidence_material_end,
            "evidence_positional_start": self.evidence_positional_start,
            "evidence_positional_end": self.evidence_positional_end,
            
            # NEW: Goal search results
            "goal_search_results": self.goal_search_results,
        }

        # Deterministic semantic story (grounded explanation scaffold for tags/roles deltas)
        # Keep this opt-in to avoid heavy work during caching and routine serialization.
        if include_semantic_story:
            try:
                if self.evidence_per_move_deltas:
                    payload["semantic_story"] = build_semantic_story(
                        investigation_result=self,
                        evidence_eval={
                            "pgn_line": self.evidence_pgn_line,
                            "eval_start": self.evidence_eval_start,
                            "eval_end": self.evidence_eval_end,
                            "eval_delta": self.evidence_eval_delta,
                            "material_start": self.evidence_material_start,
                            "material_end": self.evidence_material_end,
                            "positional_start": self.evidence_positional_start,
                            "positional_end": self.evidence_positional_end,
                        },
                    )
                else:
                    payload["semantic_story"] = None
            except Exception:
                payload["semantic_story"] = None

        return payload


class Investigator:
    """
    Chess Intelligence Engine - Completely non-linguistic.
    Has its own chess board and can play out moves.
    """
    
    def __init__(self, engine_queue=None, engine_pool=None):
        """
        Initialize Investigator with engine queue or engine pool.
        
        Args:
            engine_queue: StockfishQueue instance for engine analysis (legacy, for compatibility)
            engine_pool: EnginePool instance for parallel analysis (preferred)
        """
        if engine_pool:
            self.engine_pool = engine_pool
            self.engine_queue = None
            self.use_pool = True
        elif engine_queue:
            self.engine_queue = engine_queue
            self.engine_pool = None
            self.use_pool = False
        else:
            raise ValueError("Must provide either engine_pool or engine_queue")
        self.board = chess.Board()
        # Debug logging is extremely verbose; keep it off by default for speed + readable logs.
        # Enable with INVESTIGATOR_DEBUG=1.
        try:
            import os
            self.debug = str(os.getenv("INVESTIGATOR_DEBUG", "0")).lower() in ("1", "true", "yes", "on")
        except Exception:
            self.debug = False
        # Simple per-instance caches (bounded by manual pruning)
        self._analysis_cache: Dict[Tuple[str, int], Dict[str, Any]] = {}
        self._light_raw_cache: Dict[str, LightRawAnalysis] = {}

    def _cached_light_raw(self, fen: str) -> LightRawAnalysis:
        lr = self._light_raw_cache.get(fen)
        if lr is not None:
            return lr
        lr = compute_light_raw_analysis(fen)
        # Best-effort size bound
        if len(self._light_raw_cache) > 512:
            try:
                self._light_raw_cache.pop(next(iter(self._light_raw_cache)))
            except Exception:
                self._light_raw_cache = {}
        self._light_raw_cache[fen] = lr
        return lr

    async def _cached_analyze_depth(self, fen: str, depth: int, get_top_2: bool = False) -> Dict[str, Any]:
        # Cache only the common get_top_2=False case
        if get_top_2:
            return await self._analyze_depth(fen, depth=depth, get_top_2=get_top_2)
        key = (fen, int(depth))
        cached = self._analysis_cache.get(key)
        if cached is not None:
            return cached
        res = await self._analyze_depth(fen, depth=depth, get_top_2=False)
        if len(self._analysis_cache) > 1024:
            try:
                self._analysis_cache.pop(next(iter(self._analysis_cache)))
            except Exception:
                self._analysis_cache = {}
        self._analysis_cache[key] = res
        return res

    def _humanize_tag(self, tag_name: str) -> Optional[str]:
        """Convert structured tag identifiers into human-readable phrases."""
        if not tag_name:
            return None
        cleaned = tag_name.replace("tag.", "").replace(".", " ").replace("_", " ").strip()
        if not cleaned:
            return None
        return " ".join(part for part in cleaned.split() if part)
    
    def _extract_tag_labels(self, tags: List[Dict[str, Any]], limit: int = 3) -> List[str]:
        labels: List[str] = []
        for tag in tags:
            tag_name = tag.get("tag") or tag.get("name")
            friendly = self._humanize_tag(tag_name)
            if friendly and friendly not in labels:
                labels.append(friendly)
            if len(labels) >= limit:
                break
        return labels
    
    async def _summarize_opponent_threats(self, fen_after: str, pv_moves: List[str]) -> List[Dict[str, Any]]:
        """
        Analyze the resulting position (opponent to move) to capture best reply threats.
        Records best reply SAN, cp gap between best/second-best replies, and tag labels.
        """
        try:
            reply_analysis = await self._analyze_depth(fen_after, depth=10, get_top_2=True)
        except Exception:
            return []
        
        best_reply = reply_analysis.get("best_move_san")
        best_eval_cp = reply_analysis.get("best_move_eval_cp")
        second_eval_cp = reply_analysis.get("second_best_move_eval_cp")
        cp_gap = None
        if best_eval_cp is not None and second_eval_cp is not None:
            cp_gap = abs(best_eval_cp - second_eval_cp)
        
        threat_tags = []
        try:
            light_raw = self._cached_light_raw(fen_after)
            threat_tags = self._extract_tag_labels(light_raw.tags)
        except Exception:
            pass
        
        if not best_reply and not threat_tags:
            return []
        
        return [{
            "best_reply": best_reply,
            "cp_gap": cp_gap,
            "tag_labels": threat_tags,
            "pv_hint": pv_moves[:2] if pv_moves else []
        }]
    
    def _log_turn_switch(self, fen_before: str, fen_after: str, context: str = ""):
        """Log when the turn switches, which affects eval normalization."""
        if not getattr(self, "debug", False):
            return
        board_before = chess.Board(fen_before)
        board_after = chess.Board(fen_after)
        turn_switched = board_before.turn != board_after.turn
        
        if turn_switched:
            print(f"   ⚠️ [EVAL_NORM] TURN SWITCH DETECTED {context}:", flush=True)
            print(f"      - Before: {'WHITE' if board_before.turn == chess.WHITE else 'BLACK'} to move", flush=True)
            print(f"      - After: {'WHITE' if board_after.turn == chess.WHITE else 'BLACK'} to move", flush=True)
            print(f"      - ⚠️ CRITICAL: Stockfish eval will be from different side's perspective!", flush=True)
            print(f"      - ⚠️ CRITICAL: _score_to_white_cp MUST flip sign correctly!", flush=True)
        else:
            print(f"   ✅ [EVAL_NORM] No turn switch {context}", flush=True)
    
    def _score_to_white_cp(self, score: Optional[chess.engine.PovScore], fen: Optional[str] = None) -> Optional[int]:
        """
        Normalize engine evaluations so +cp always favors White.
        
        Uses score.white() which already handles perspective conversion correctly.
        """
        if getattr(self, "debug", False):
            print(f"      🔍 [SCORE_TO_WHITE_CP] Input score: {score}, type: {type(score)}")
        if score is None:
            if getattr(self, "debug", False):
                print(f"      ⚠️ [SCORE_TO_WHITE_CP] Score is None, returning None")
            return None
        
        # Log side to move for debugging
        if fen:
            try:
                board_check = chess.Board(fen)
                side_to_move = 'BLACK' if board_check.turn == chess.BLACK else 'WHITE'
                if getattr(self, "debug", False):
                    print(f"      📊 [SCORE_TO_WHITE_CP] FEN provided, side to move: {side_to_move}")
            except Exception:
                pass
        
        # Enhanced logging to verify normalization
        if hasattr(score, 'relative'):
            if getattr(self, "debug", False):
                print(f"      📊 [SCORE_TO_WHITE_CP] Score.relative: {score.relative}")
        if hasattr(score, 'white'):
            pov_white = score.white()
            pov_black = score.black() if hasattr(score, 'black') else None
            if getattr(self, "debug", False):
                print(f"      📊 [SCORE_TO_WHITE_CP] POV (white): {pov_white}")
            if pov_black:
                if getattr(self, "debug", False):
                    print(f"      📊 [SCORE_TO_WHITE_CP] POV (black): {pov_black}")
        
        # Get score from white's perspective - score.white() already handles perspective conversion
        pov = score.white()
        if getattr(self, "debug", False):
            print(f"      📊 [SCORE_TO_WHITE_CP] POV (white): {pov}, is_mate: {pov.is_mate()}")
        if pov.is_mate():
            mate = pov.mate()
            if getattr(self, "debug", False):
                print(f"      📊 [SCORE_TO_WHITE_CP] Mate: {mate}")
            if mate is None:
                if getattr(self, "debug", False):
                    print(f"      ⚠️ [SCORE_TO_WHITE_CP] Mate is None, returning None")
                return None
            result = 10000 if mate > 0 else -10000
            if getattr(self, "debug", False):
                print(f"      ✅ [SCORE_TO_WHITE_CP] Returning mate score: {result}")
            return result
        
        result = pov.score(mate_score=10000)
        if getattr(self, "debug", False):
            print(f"      ✅ [SCORE_TO_WHITE_CP] Returning score: {result}")
        return result
    
    async def investigate_position(
        self,
        fen: str,
        move_index: Optional[int] = None,
        depth: int = 18,
        focus: Optional[str] = None,
        scope: Optional[str] = None,
        pgn_callback: Optional[Callable] = None
    ) -> InvestigationResult:
        """
        Investigate a position - returns structured facts only.
        
        Args:
            fen: FEN string of position
            move_index: Optional move index in game
            depth: Analysis depth
            focus: Optional focus (e.g., "knight", "bishop", "doubled_pawns") - for future filtering/emphasis
            scope: Optional scope - "general_position" | "specific_move" | "piece_focus" | "tactical_scan"
                   If "tactical_scan" or None (default), uses standard investigation
                   If "general_position", uses dual-depth analysis with recursive branching
            pgn_callback: Optional callback for live PGN updates
            
        Returns:
            InvestigationResult with position facts
        """
        # Pipeline timing (fine-grained)
        from contextlib import nullcontext
        try:
            from pipeline_timer import get_pipeline_timer
            _timer = get_pipeline_timer()
        except Exception:
            _timer = None
        # Check cache first
        try:
            cache_span = (_timer.span("investigator:position:cache_get") if _timer else nullcontext())
        except Exception:
            cache_span = nullcontext()

        try:
            with cache_span:
                from investigation_cache import get_investigation_cache
                cache = get_investigation_cache()
                cached_result = cache.get(fen, None, "position")
                if cached_result:
                    print(f"   ✅ [INVESTIGATOR] Cache HIT for position {fen[:30]}...")
                    # Record cache hit (if timer available)
                    try:
                        from pipeline_timer import get_pipeline_timer
                        timer = get_pipeline_timer()
                        if timer:
                            timer.record_cache("investigation", hit=True)
                    except Exception:
                        pass
                    return cached_result
                else:
                    # Record cache miss
                    try:
                        from pipeline_timer import get_pipeline_timer
                        timer = get_pipeline_timer()
                        if timer:
                            timer.record_cache("investigation", hit=False)
                    except Exception:
                        pass
        except Exception as e:
            print(f"   ⚠️ [INVESTIGATOR] Cache check failed: {e}")
        
        # LOG INPUT
        import sys
        print(f"\n   {'='*80}")
        print(f"   🔍 [INVESTIGATOR] investigate_position INPUT:")
        print(f"      FEN: {fen[:50]}...")
        print(f"      Depth: {depth}")
        print(f"      Focus: {focus}")
        print(f"      Scope: {scope}")
        print(f"      Move Index: {move_index}")
        print(f"   {'='*80}\n")
        sys.stdout.flush()
        
        # Route to dual-depth analysis if scope requires it
        print(f"   🔍 [INVESTIGATOR] Scope check: scope={scope}, routing to dual-depth: {scope == 'general_position'}")
        if scope == "general_position":
            print(f"   ✅ [INVESTIGATOR] Routing to investigate_with_dual_depth (D16/D2 analysis with branches)")
            with (_timer.span("investigator:position:dual_depth") if _timer else nullcontext()):
                result = await self.investigate_with_dual_depth(fen, scope=scope, depth_16=16, depth_2=2, pgn_callback=pgn_callback)
            # LOG OUTPUT
            print(f"\n   {'='*80}")
            print(f"   ✅ [INVESTIGATOR] investigate_position OUTPUT:")
            print(f"      Type: InvestigationResult")
            print(f"      Eval D16: {result.eval_d16}")
            print(f"      Best Move D16: {result.best_move_d16}")
            print(f"      Overestimated Moves: {len(result.overestimated_moves)}")
            print(f"      PGN Length: {len(result.pgn_exploration) if result.pgn_exploration else 0} chars")
            print(f"      Themes: {result.themes_identified[:5] if result.themes_identified else []}")
            print(f"   {'='*80}\n")
            sys.stdout.flush()
            
            # Cache result before returning
            try:
                from investigation_cache import get_investigation_cache
                cache = get_investigation_cache()
                with (_timer.span("investigator:position:cache_set") if _timer else nullcontext()):
                    cache.set(fen, result, None, "position")
                print(f"   💾 [INVESTIGATOR] Cached result for position {fen[:30]}...")
            except Exception as e:
                print(f"   ⚠️ [INVESTIGATOR] Cache save failed: {e}")
            
            return result
        else:
            print(f"   ⚠️ [INVESTIGATOR] Scope is NOT 'general_position' ({scope}), using standard investigation (NO dual-depth)")
        self.board.set_fen(fen)
        
        # Get engine evaluation
        try:
            if self.use_pool:
                # Use engine pool for parallel analysis
                with (_timer.span("investigator:position:engine:analyze_single", {"depth": depth, "multipv": 1}) if _timer else nullcontext()):
                    analysis_result = await self.engine_pool.analyze_single(
                        fen=self.board.fen(),
                        depth=depth,
                        multipv=1
                    )
                if analysis_result.get("success") and analysis_result.get("result"):
                    info = analysis_result["result"][0] if isinstance(analysis_result["result"], list) else analysis_result["result"]
                else:
                    info = {}
            else:
                # Use engine queue (legacy)
                with (_timer.span("investigator:position:engine:queue", {"depth": depth}) if _timer else nullcontext()):
                    info = await self.engine_queue.enqueue(
                        self.engine_queue.engine.analyse,
                        self.board,
                        chess.engine.Limit(depth=depth)
                    )
            
            score = info.get("score")
            eval_cp = self._score_to_white_cp(score, fen=self.board.fen())
            
            eval_before = eval_cp / 100.0 if eval_cp is not None else None
            
            # Extract PV with error handling
            pv = info.get("pv", [])
            best_move = None
            if pv:
                try:
                    # Verify the first move is legal before using it
                    if pv[0] in self.board.legal_moves:
                        best_move = pv[0].uci()
                    else:
                        print(f"   ⚠️ PV move {pv[0]} not legal in position {self.board.fen()}")
                except Exception as pv_e:
                    print(f"   ⚠️ Error parsing PV: {pv_e}")
            
            # Get candidate moves (top 3)
            candidate_moves = []
            if pv:
                for i, move in enumerate(pv[:3]):
                    # Verify move is legal before processing
                    if move not in self.board.legal_moves:
                        print(f"   ⚠️ PV move {move} at index {i} not legal, skipping")
                        continue
                    
                    test_board = self.board.copy()
                    test_board.push(move)
                    try:
                        if self.use_pool:
                            # Use engine pool
                            with (_timer.span("investigator:position:engine:candidate_move", {"depth": depth - 2, "multipv": 1}) if _timer else nullcontext()):
                                move_analysis = await self.engine_pool.analyze_single(
                                    fen=test_board.fen(),
                                    depth=depth - 2,
                                    multipv=1
                                )
                            if move_analysis.get("success") and move_analysis.get("result"):
                                move_info = move_analysis["result"][0] if isinstance(move_analysis["result"], list) else move_analysis["result"]
                            else:
                                move_info = {}
                        else:
                            # Use engine queue (legacy)
                            with (_timer.span("investigator:position:engine:candidate_move_queue", {"depth": depth - 2}) if _timer else nullcontext()):
                                move_info = await self.engine_queue.enqueue(
                                    self.engine_queue.engine.analyse,
                                    test_board,
                                    chess.engine.Limit(depth=depth - 2)
                                )
                        move_score = move_info.get("score")
                        move_eval_cp = self._score_to_white_cp(move_score, fen=test_board.fen())
                        candidate_moves.append({
                            "move": self.board.san(move),
                            "eval": move_eval_cp / 100.0 if move_eval_cp is not None else None
                        })
                    except Exception:
                        candidate_moves.append({
                            "move": self.board.san(move),
                            "eval": None
                        })
            
            # Classify position
            game_phase = self._classify_game_phase()
            urgency = self._classify_urgency(eval_cp) if eval_cp is not None else None
            
            result = InvestigationResult(
                eval_before=eval_before,
                best_move=best_move,
                game_phase=game_phase,
                urgency=urgency,
                candidate_moves=candidate_moves,
                pv_after_move=[self.board.san(m) for m in pv[:10]]
            )
            
            # Cache result before returning
            try:
                from investigation_cache import get_investigation_cache
                cache = get_investigation_cache()
                with (_timer.span("investigator:position:cache_set") if _timer else nullcontext()):
                    cache.set(fen, result, None, "position")
                print(f"   💾 [INVESTIGATOR] Cached result for position {fen[:30]}...")
            except Exception as e:
                print(f"   ⚠️ [INVESTIGATOR] Cache save failed: {e}")
            
            return result
        except Exception as e:
            # Return minimal result on error
            return InvestigationResult(
                game_phase=self._classify_game_phase()
            )
    
    async def investigate_move(
        self,
        fen: str,
        move_san: str,
        follow_pv: bool = True,
        depth: int = 12,
        depth_16: int = 16,
        depth_2: int = 2,
        evidence_base_plies: int = 4,
        evidence_max_plies: int = 8,
        focus: Optional[str] = None,
        pgn_callback: Optional[Callable] = None,
        fen_callback: Optional[Callable] = None,
        original_fen: Optional[str] = None
    ) -> InvestigationResult:
        """
        Test a move and return structured consequences.
        Now uses dual-depth analysis (D16/D2) to explore branches from the resulting position.
        
        Args:
            fen: Starting position FEN
            move_san: Move to test (SAN notation)
            follow_pv: If True, follow PV to see consequences
            depth: Depth for light analysis (legacy, now uses D16/D2)
            focus: Optional focus (e.g., move SAN, theme name) - for future filtering/emphasis
            pgn_callback: Optional callback for PGN updates
            fen_callback: Optional callback for FEN updates (fen, move_san, is_reverting)
            original_fen: Optional original FEN to revert to after investigation
            
        Returns:
            InvestigationResult with move consequences and dual-depth analysis (D16/D2, branches, PGN exploration)
        """
        # Check cache first (variant key prevents mixing shallow alt-move investigations with deep primary investigations)
        try:
            from investigation_cache import get_investigation_cache
            cache = get_investigation_cache()
            variant = f"d{int(depth)}|d16{int(depth_16)}|d2{int(depth_2)}|ev{int(evidence_base_plies)}-{int(evidence_max_plies)}"
            cached_result = cache.get(fen, move_san, "move", variant=variant)
            if cached_result:
                print(f"   ✅ [INVESTIGATOR] Cache HIT for move {move_san} at {fen[:30]}...")
                # Record cache hit (if timer available)
                try:
                    from pipeline_timer import get_pipeline_timer
                    timer = get_pipeline_timer()
                    if timer:
                        timer.record_cache("investigation", hit=True)
                except:
                    pass
                return cached_result
            else:
                # Record cache miss
                try:
                    from pipeline_timer import get_pipeline_timer
                    timer = get_pipeline_timer()
                    if timer:
                        timer.record_cache("investigation", hit=False)
                except:
                    pass
        except Exception as e:
            print(f"   ⚠️ [INVESTIGATOR] Cache check failed: {e}")
        
        # LOG INPUT
        import sys
        print(f"\n   {'='*80}")
        print(f"   🔍 [INVESTIGATOR] investigate_move INPUT:")
        print(f"      FEN: {fen[:50]}...")
        print(f"      Move SAN: {move_san}")
        print(f"      Follow PV: {follow_pv}")
        print(f"      Depth: {depth}")
        print(f"      Dual Depth: depth_16={depth_16}, depth_2={depth_2}")
        print(f"      Evidence plies: base={evidence_base_plies}, max={evidence_max_plies}")
        print(f"      Focus: {focus}")
        print(f"   {'='*80}\n")
        sys.stdout.flush()
        
        # Store original FEN if not provided
        if original_fen is None:
            original_fen = fen
        
        # Emit FEN update: move investigation starting
        if fen_callback:
            try:
                fen_callback({
                    "type": "move_investigation_start",
                    "fen": fen,
                    "move_san": move_san,
                    "is_reverting": False
                })
            except Exception:
                pass
        
        self.board.set_fen(fen)
        # Track material balance before/after (centipawns from White perspective)
        def _material_balance_cp(board: chess.Board) -> int:
            values = {
                chess.PAWN: 100,
                chess.KNIGHT: 320,
                chess.BISHOP: 330,
                chess.ROOK: 500,
                chess.QUEEN: 900,
                chess.KING: 0,
            }
            total = 0
            for sq in chess.SQUARES:
                p = board.piece_at(sq)
                if not p:
                    continue
                v = values.get(p.piece_type, 0)
                total += v if p.color == chess.WHITE else -v
            return total
        
        # Check if move is legal
        def _normalize_san_for_match(s: str) -> str:
            # Make SAN comparisons tolerant of missing check/mate markers and annotations.
            # Examples:
            # - "Qxd1" should match "Qxd1+"
            # - "Nf3!" should match "Nf3"
            # - "Qh5#" should match "Qh5"
            if not s:
                return ""
            s = str(s).strip()
            # remove common trailing annotation chars
            while s and s[-1] in ("+", "#", "!", "?", "⟳"):
                s = s[:-1]
            # collapse repeated punctuation (e.g., "!?")
            s = s.replace("!!", "!").replace("??", "?")
            # remove any remaining trailing !/? after collapsing
            while s and s[-1] in ("!", "?"):
                s = s[:-1]
            return s.strip()

        def _parse_san_lenient(board: chess.Board, san: str) -> Optional[chess.Move]:
            """
            Lenient SAN parser that accepts SAN strings missing check/mate suffixes (+/#)
            or annotation suffixes (!/?). Falls back to matching by comparing normalized
            SAN of all legal moves.
            """
            if not san:
                return None
            target = _normalize_san_for_match(san)
            if not target:
                return None
            try:
                # Try strict parse first
                return board.parse_san(san)
            except Exception:
                pass
            try:
                for mv in board.legal_moves:
                    try:
                        ms = board.san(mv)
                    except Exception:
                        continue
                    if _normalize_san_for_match(ms) == target:
                        return mv
            except Exception:
                pass
            return None

        try:
            move = _parse_san_lenient(self.board, move_san)
            if not move or move not in self.board.legal_moves:
                return InvestigationResult(
                    player_move=move_san
                )
        except Exception as e:
            return InvestigationResult(
                player_move=move_san
            )
        
        # Get eval before
        eval_before_cp = None
        material_before_cp = _material_balance_cp(self.board)
        try:
            if self.use_pool:
                # Use engine pool for parallel analysis
                analysis_result = await self.engine_pool.analyze_single(
                    fen=self.board.fen(),
                    depth=depth,
                    multipv=1
                )
                if analysis_result.get("success") and analysis_result.get("result"):
                    # result is a list from engine.analyse(), get first entry
                    info_before = analysis_result["result"][0] if isinstance(analysis_result["result"], list) else analysis_result["result"]
                    score_before = info_before.get("score")
                    eval_before_cp = self._score_to_white_cp(score_before, fen=self.board.fen())
            else:
                # Use engine queue (legacy)
                info_before = await self.engine_queue.enqueue(
                    self.engine_queue.engine.analyse,
                    self.board,
                    chess.engine.Limit(depth=depth)
                )
                score_before = info_before.get("score")
                eval_before_cp = self._score_to_white_cp(score_before, fen=self.board.fen())
        except Exception:
            pass
        
        eval_before = eval_before_cp / 100.0 if eval_before_cp is not None else None
        
        # Log eval before move
        print(f"   🔍 [EVAL_NORM] BEFORE MOVE:", flush=True)
        print(f"      - FEN: {self.board.fen()}", flush=True)
        print(f"      - Side to move: {'WHITE' if self.board.turn == chess.WHITE else 'BLACK'}", flush=True)
        print(f"      - Raw score_before: {score_before}", flush=True)
        print(f"      - Normalized eval_before_cp: {eval_before_cp}", flush=True)
        print(f"      - eval_before (pawns): {eval_before}", flush=True)
        
        # Play move
        fen_before_move = self.board.fen()
        self.board.push(move)
        fen_after = self.board.fen()
        
        # Log turn switch detection
        board_after = chess.Board(fen_after)
        self._log_turn_switch(fen_before_move, fen_after, "in investigate_move")
        material_after_cp = _material_balance_cp(self.board)
        material_change_pawns = (material_after_cp - material_before_cp) / 100.0
        
        # Emit FEN update: move played
        if fen_callback:
            try:
                fen_callback({
                    "type": "move_played",
                    "fen": fen_after,
                    "move_san": move_san,
                    "is_reverting": False
                })
            except Exception:
                pass
        
        # Emit callback for move exploration
        if pgn_callback:
            pgn_callback({
                "type": "move_explored",
                "move_san": move_san,
                "fen": fen_after,
                "eval_before": eval_before
            })
        
        # Get eval after
        eval_after_cp = None
        pv = []
        try:
            if self.use_pool:
                # Use engine pool for parallel analysis
                analysis_result = await self.engine_pool.analyze_single(
                    fen=fen_after,
                    depth=depth,
                    multipv=1
                )
                if analysis_result.get("success") and analysis_result.get("result"):
                    # result is a list from engine.analyse(), get first entry
                    info_after = analysis_result["result"][0] if isinstance(analysis_result["result"], list) else analysis_result["result"]
                    score_after = info_after.get("score")
                    eval_after_cp = self._score_to_white_cp(score_after, fen=fen_after)
                    pv = info_after.get("pv", [])
            else:
                # Use engine queue (legacy)
                info_after = await self.engine_queue.enqueue(
                    self.engine_queue.engine.analyse,
                    self.board,
                    chess.engine.Limit(depth=depth)
                )
                score_after = info_after.get("score")
                eval_after_cp = self._score_to_white_cp(score_after, fen=fen_after)
                pv = info_after.get("pv", [])
        except Exception:
            pass
        
        eval_after = eval_after_cp / 100.0 if eval_after_cp is not None else None
        
        # Log eval after move
        board_after = chess.Board(fen_after)
        print(f"   🔍 [EVAL_NORM] AFTER MOVE ANALYSIS:", flush=True)
        print(f"      - Move played: {move_san}", flush=True)
        print(f"      - FEN after: {fen_after}", flush=True)
        print(f"      - Side to move: {'WHITE' if board_after.turn == chess.WHITE else 'BLACK'}", flush=True)
        print(f"      - Raw score_after: {score_after}", flush=True)
        print(f"      - Normalized eval_after_cp: {eval_after_cp}", flush=True)
        print(f"      - eval_after (pawns): {eval_after}", flush=True)
        
        # Calculate drop
        eval_drop = None
        if eval_before is not None and eval_after is not None:
            eval_drop = eval_after - eval_before
            print(f"   🔍 [EVAL_NORM] EVAL_DROP CALCULATION:", flush=True)
            print(f"      - eval_before: {eval_before}", flush=True)
            print(f"      - eval_after: {eval_after}", flush=True)
            print(f"      - eval_drop = eval_after - eval_before = {eval_drop}", flush=True)
            print(f"      - Interpretation: {'Position improved' if eval_drop < 0 else 'Position worsened'} by {abs(eval_drop):.2f} pawns", flush=True)
            if self.board.turn != board_after.turn:
                print(f"      - ⚠️ TURN SWITCHED: Verify normalization is correct!", flush=True)
        
        # NEW: Use dual-depth analysis on the resulting position after the move
        print(f"   ✅ [INVESTIGATOR] investigate_move: Using dual-depth analysis on position after {move_san}", flush=True)
        print(f"   🔍 [EVAL_NORM] CALLING investigate_with_dual_depth:", flush=True)
        print(f"      - fen_after: {fen_after}", flush=True)
        board_check = chess.Board(fen_after)
        print(f"      - Side to move in fen_after: {'WHITE' if board_check.turn == chess.WHITE else 'BLACK'}", flush=True)
        print(f"      - ⚠️ CRITICAL: After {move_san}, turn should have switched!", flush=True)
        dual_depth_result = await self.investigate_with_dual_depth(
            fen_after,
            scope="general_position",  # This triggers branch exploration
            depth_16=depth_16,
            depth_2=depth_2,
            pgn_callback=pgn_callback,
            original_fen=fen  # Pass FEN before the player's move
        )
        
        # Use dual-depth eval as the authoritative eval_after
        if dual_depth_result.eval_d16 is not None:
            print(f"   🔍 [EVAL_NORM] DUAL-DEPTH OVERRIDE:", flush=True)
            print(f"      - Original eval_after: {eval_after}", flush=True)
            print(f"      - dual_depth_result.eval_d16: {dual_depth_result.eval_d16}", flush=True)
            print(f"      - Overriding eval_after with eval_d16", flush=True)
            board_after_check = chess.Board(fen_after)
            print(f"      - Side to move in fen_after: {'WHITE' if board_after_check.turn == chess.WHITE else 'BLACK'}", flush=True)
            print(f"      - ⚠️ CRITICAL: If turn switched, eval_d16 should be from OPPONENT's perspective!", flush=True)
            print(f"      - ⚠️ CRITICAL: eval_d16 must be normalized to WHITE's perspective!", flush=True)
            eval_after = dual_depth_result.eval_d16
            eval_after_cp = int(dual_depth_result.eval_d16 * 100)
        
        # Recalculate drop using dual-depth eval
        if eval_before is not None and dual_depth_result.eval_d16 is not None:
            eval_drop = dual_depth_result.eval_d16 - eval_before
            print(f"   🔍 [EVAL_NORM] RECALCULATED EVAL_DROP:", flush=True)
            print(f"      - eval_before: {eval_before} (WHITE to move, normalized)", flush=True)
            print(f"      - eval_d16 (new eval_after): {dual_depth_result.eval_d16} (should be normalized to WHITE)", flush=True)
            print(f"      - eval_drop = eval_d16 - eval_before = {eval_drop}", flush=True)
            print(f"      - Interpretation: {'Position improved' if eval_drop < 0 else 'Position worsened'} by {abs(eval_drop):.2f} pawns", flush=True)
        
        # Convert PV to SAN once so we can reuse for threats + PGN
        pv_moves_san: List[str] = []
        if pv:
            # Validate PV moves before converting to SAN
            temp_board = chess.Board(fen)
            temp_board.push(move)  # Push the move we're investigating
            for pv_move in pv[:8]:
                try:
                    if pv_move in temp_board.legal_moves:
                        pv_moves_san.append(temp_board.san(pv_move))
                        temp_board.push(pv_move)
                    else:
                        print(f"   ⚠️ PV move {pv_move} not legal, skipping")
                        break
                except Exception as e:
                    print(f"   ⚠️ Error converting PV move {pv_move} to SAN: {e}")
                    break
            
        # Gather tag/threat context for resulting position
        light_raw_after = None
        try:
            light_raw_after = self._cached_light_raw(fen_after)
        except Exception:
            pass
        
        opponent_threats = await self._summarize_opponent_threats(fen_after, pv_moves_san)
        
        # Build PGN branch if requested
        pgn_branches = {}
        if follow_pv and pv_moves_san:
                pgn_branches["main_line"] = self._build_pgn_branch(fen, [move_san] + pv_moves_san)
                # Emit callback for branch added
                if pgn_callback:
                    pgn_callback({
                        "type": "branch_added",
                        "move_san": move_san,
                        "branch": pgn_branches.get("main_line", {}),
                        "eval_after": eval_after
                    })
        
        # Detect tactics
        tactics = await self._detect_tactics(fen, move_san, move)
        
        # Build evidence_index (use dual-depth exploration_tree if available)
        # Prefer PV from dual-depth analysis, fallback to PV SAN computed on the post-move board.
        # IMPORTANT: pv moves are from the position AFTER the player's move, so we must not use the pre-move board.
        pv_san = list(pv_moves_san[:12]) if pv_moves_san else []
        if dual_depth_result.exploration_tree:
            # Extract PV from dual-depth exploration tree
            root_pv = dual_depth_result.exploration_tree.get("pv_san") or dual_depth_result.exploration_tree.get("pv_full", [])
            if root_pv:
                pv_san = root_pv[:12]  # Use dual-depth PV (limit to 12 moves)
        evidence_index = self._build_evidence_index(
            pv_after_move=pv_san,
            exploration_tree=dual_depth_result.exploration_tree if dual_depth_result.exploration_tree else None
        )
        
        result = InvestigationResult(
            eval_before=eval_before,
            eval_after=eval_after,
            eval_drop=eval_drop,
            player_move=move_san,
            tactics_found=tactics,
            pgn_branches=pgn_branches,
            pv_after_move=pv_san,
            evidence_index=evidence_index,  # NEW: Structured evidence lines
            game_phase=self._classify_game_phase(),
            material_change=material_change_pawns,
            light_raw_analysis=light_raw_after,
            threats=opponent_threats,
            # Dual-depth analysis fields (from investigate_with_dual_depth)
            eval_d16=dual_depth_result.eval_d16,
            best_move_d16=dual_depth_result.best_move_d16,
            best_move_d16_eval_cp=dual_depth_result.best_move_d16_eval_cp,
            second_best_move_d16=dual_depth_result.second_best_move_d16,
            second_best_move_d16_eval_cp=dual_depth_result.second_best_move_d16_eval_cp,
            is_critical=dual_depth_result.is_critical,
            is_winning=dual_depth_result.is_winning,
            eval_d2=dual_depth_result.eval_d2,
            top_moves_d2=dual_depth_result.top_moves_d2,
            overestimated_moves=dual_depth_result.overestimated_moves,
            # PGN exploration from dual-depth
            pgn_exploration=dual_depth_result.pgn_exploration,
            exploration_tree=dual_depth_result.exploration_tree,
            themes_identified=dual_depth_result.themes_identified,
            commentary=dual_depth_result.commentary,
            # NEW: Structured deltas/net changes (propagate from dual-depth result)
            evidence_starting_fen=getattr(dual_depth_result, "evidence_starting_fen", None),
            evidence_pgn_line=getattr(dual_depth_result, "evidence_pgn_line", None),
            evidence_main_line_moves=getattr(dual_depth_result, "evidence_main_line_moves", []) or [],
            evidence_per_move_deltas=getattr(dual_depth_result, "evidence_per_move_deltas", []) or [],
            evidence_tags_gained_net=getattr(dual_depth_result, "evidence_tags_gained_net", []) or [],
            evidence_tags_lost_net=getattr(dual_depth_result, "evidence_tags_lost_net", []) or [],
            evidence_tags_gained_net_raw=getattr(dual_depth_result, "evidence_tags_gained_net_raw", []) or [],
            evidence_tags_lost_net_raw=getattr(dual_depth_result, "evidence_tags_lost_net_raw", []) or [],
            evidence_roles_gained_net=getattr(dual_depth_result, "evidence_roles_gained_net", []) or [],
            evidence_roles_lost_net=getattr(dual_depth_result, "evidence_roles_lost_net", []) or [],
        )

        # NEW: Override/compute structured deltas for the canonical evidence line in move-investigation mode.
        # Here we *do* know the player's move and the pre-move starting FEN.
        try:
            starting_fen = original_fen or fen
            pv_moves = [m for m in (result.pv_after_move or []) if isinstance(m, str)]
            # Build a short line starting with the player's move.
            # Base: 4 plies total (player move + next 3 plies from PV). Then extend up to 8 plies
            # only while D2 best-move agrees with PV continuation (stop on first disagreement).
            base_plies = 4
            max_total_plies = 8
            evidence_moves = [move_san] + pv_moves[: (base_plies - 1)] if pv_moves else [move_san]
            evidence_moves = [m for m in evidence_moves if isinstance(m, str) and m.strip()][:base_plies]

            def _clean_san_for_parse(s: str) -> str:
                # Stockfish SAN sometimes includes "!" / "?" annotations; python-chess parse_san doesn't accept them.
                # Keep check/mate markers (+/#) but strip trailing annotation punctuation.
                s2 = s.strip()
                while s2 and s2[-1] in ("!", "?", "‼", "⁇", "⁉", "⁈"):
                    s2 = s2[:-1].strip()
                return s2

            try:
                import chess as chesslib
                base_plies = int(evidence_base_plies) if isinstance(evidence_base_plies, int) else 4
                max_total_plies = int(evidence_max_plies) if isinstance(evidence_max_plies, int) else 8
                if max_total_plies < base_plies:
                    max_total_plies = base_plies
                if starting_fen and pv_moves and len(evidence_moves) >= base_plies:
                    board_for_extension = chesslib.Board(starting_fen)
                    for mv in evidence_moves:
                        board_for_extension.push_san(_clean_san_for_parse(mv))

                    # We already consumed pv_moves[:base_plies-1] into evidence_moves after move_san.
                    pv_index = base_plies - 1
                    while len(evidence_moves) < max_total_plies and pv_index < len(pv_moves):
                        next_from_pv = pv_moves[pv_index]
                        if not isinstance(next_from_pv, str) or not next_from_pv.strip():
                            break

                        # Check D2 agreement at the current position.
                        d2 = await self._cached_analyze_depth(board_for_extension.fen(), depth=int(depth_2), get_top_2=False)
                        best_d2 = d2.get("best_move_san")
                        if not isinstance(best_d2, str) or not best_d2.strip():
                            break

                        try:
                            pv_move_obj = board_for_extension.parse_san(_clean_san_for_parse(next_from_pv))
                            d2_move_obj = board_for_extension.parse_san(_clean_san_for_parse(best_d2))
                        except Exception:
                            break

                        # Disagreement => stop extending.
                        if pv_move_obj.uci() != d2_move_obj.uci():
                            break

                        # Agreement => extend by the PV move.
                        evidence_moves.append(next_from_pv.strip())
                        board_for_extension.push(pv_move_obj)
                        pv_index += 1
            except Exception:
                # Best-effort only; evidence line should never fail the investigation.
                pass
            # Compute even for 1-ply lines so net lists are not systematically empty.
            if len(evidence_moves) >= 1 and starting_fen:
                per_move, tg, tl, rg, rl, tg_struct, tl_struct = self._compute_per_move_deltas_for_line(starting_fen, evidence_moves)
                result.evidence_starting_fen = starting_fen
                result.evidence_main_line_moves = evidence_moves
                result.evidence_pgn_line = " ".join(evidence_moves)
                result.evidence_per_move_deltas = per_move
                # Preserve full/raw tags (for deep analysis)
                result.evidence_tags_gained_net_raw = list(tg or [])
                result.evidence_tags_lost_net_raw = list(tl or [])
                # Filter clutter from public net lists
                _clutter_prefixes = ("tag.diagonal.", "tag.key.", "tag.color.hole.")
                result.evidence_tags_gained_net = [t for t in (tg or []) if not any(str(t).startswith(p) for p in _clutter_prefixes)]
                result.evidence_tags_lost_net = [t for t in (tl or []) if not any(str(t).startswith(p) for p in _clutter_prefixes)]
                result.evidence_tags_gained_net_structured = tg_struct
                result.evidence_tags_lost_net_structured = tl_struct
                result.evidence_roles_gained_net = rg
                result.evidence_roles_lost_net = rl

                # NEW: evidence eval decomposition (start→end along the evidence line)
                breakdown = await self._compute_evidence_eval_breakdown(
                    starting_fen=starting_fen,
                    evidence_moves=evidence_moves,
                    eval_start_pawns=result.eval_before,
                    end_eval_depth=6
                )
                result.evidence_end_fen = breakdown.get("end_fen")
                result.evidence_eval_start = breakdown.get("eval_start")
                result.evidence_eval_end = breakdown.get("eval_end")
                result.evidence_eval_delta = breakdown.get("eval_delta")
                result.evidence_material_start = breakdown.get("material_start")
                result.evidence_material_end = breakdown.get("material_end")
                result.evidence_positional_start = breakdown.get("positional_start")
                result.evidence_positional_end = breakdown.get("positional_end")

                # NEW: per-move FEN + eval/material/positional series for SAN->words narration
                try:
                    result.evidence_per_move_stats = await self._compute_evidence_per_move_stats(
                        starting_fen=starting_fen,
                        evidence_per_move_deltas=result.evidence_per_move_deltas,
                        eval_start_pawns=result.evidence_eval_start,
                        depth=6,
                        max_plies=16,
                    )
                except Exception:
                    result.evidence_per_move_stats = []
        except Exception as e:
            print(f"   ⚠️ [INVESTIGATOR] Failed to compute move evidence deltas: {e}")
        
        # Revert board to original FEN
        self.board.set_fen(original_fen)
        
        # Emit FEN update: investigation complete, reverting
        if fen_callback:
            try:
                fen_callback({
                    "type": "investigation_complete",
                    "fen": original_fen,
                    "move_san": move_san,
                    "is_reverting": True
                })
            except Exception:
                pass
        
        # LOG OUTPUT
        print(f"\n   {'='*80}")
        print(f"   ✅ [INVESTIGATOR] investigate_move OUTPUT:")
        print(f"      Type: InvestigationResult")
        print(f"      Player Move: {result.player_move}")
        print(f"      Eval Before: {result.eval_before}")
        print(f"      Eval After: {result.eval_after}")
        print(f"      Eval Drop: {result.eval_drop}")
        print(f"      Best Move: {result.best_move}")
        print(f"      Tactics Found: {len(result.tactics_found)}")
        print(f"      ✅ Dual-Depth Analysis: D16 eval={result.eval_d16}, Best Move D16={result.best_move_d16}")
        print(f"         D2 eval={result.eval_d2}, Overestimated Moves={len(result.overestimated_moves)}")
        print(f"         PGN Exploration Length: {len(result.pgn_exploration) if result.pgn_exploration else 0} chars")
        print(f"         Themes: {result.themes_identified[:5] if result.themes_identified else []}")
        print(f"   {'='*80}\n")
        sys.stdout.flush()
        
        # Cache result before returning
        try:
            from investigation_cache import get_investigation_cache
            cache = get_investigation_cache()
            variant = f"d{int(depth)}|d16{int(depth_16)}|d2{int(depth_2)}|ev{int(evidence_base_plies)}-{int(evidence_max_plies)}"
            cache.set(fen, result, move_san, "move", variant=variant)
            print(f"   💾 [INVESTIGATOR] Cached result for move {move_san} at {fen[:30]}...")
        except Exception as e:
            print(f"   ⚠️ [INVESTIGATOR] Cache save failed: {e}")
        
        return result

    async def investigate_target(
        self,
        fen: str,
        goal: Dict[str, Any],
        policy: Optional[Dict[str, Any]] = None,
        pgn_callback: Optional[Callable] = None
    ) -> InvestigationResult:
        """
        Goal-directed search over futures, bounded by policy.
        Returns InvestigationResult with goal outcome stored in `consequences`.
        """
        policy = policy or {}

        query_type = policy.get("query_type", "existence")  # existence | robustness
        max_depth = int(policy.get("max_depth", 8))
        beam_width = int(policy.get("beam_width", 4))
        branching_limit = int(policy.get("branching_limit", 8))
        opponent_model = policy.get("opponent_model", "best")  # best | topN | stochastic
        engine_depth_propose = int(policy.get("engine_depth_propose", 2))
        engine_depth_reply = int(policy.get("engine_depth_reply", 8))
        pv_extend_plies = int(policy.get("pv_extend_plies", 0))
        top_k_witnesses = int(policy.get("top_k_witnesses", 1))

        max_depth = max(0, min(max_depth, 24))
        beam_width = max(1, min(beam_width, 32))
        branching_limit = max(1, min(branching_limit, 24))
        engine_depth_propose = max(1, min(engine_depth_propose, 6))
        engine_depth_reply = max(1, min(engine_depth_reply, 16))
        pv_extend_plies = max(0, min(pv_extend_plies, 12))
        top_k_witnesses = max(1, min(top_k_witnesses, 10))

        root_board = chess.Board(fen)
        root_turn = root_board.turn
        root_material_balance = self._material_balance_pawns(root_board)

        def _compile_goal(node: Any) -> Callable[[chess.Board, List[Tuple[bool, str]]], bool]:
            if not isinstance(node, dict):
                return lambda b, p: False
            op = node.get("op")
            if op in ("and", "or"):
                args = node.get("args") or []
                fs = [_compile_goal(a) for a in args if a is not None]
                if op == "and":
                    return lambda b, p: all(f(b, p) for f in fs)
                return lambda b, p: any(f(b, p) for f in fs)
            if op == "not":
                args = node.get("args") or []
                f0 = _compile_goal(args[0]) if args else (lambda b, p: False)
                return lambda b, p: (not f0(b, p))
            # Default: predicate
            pred = node.get("predicate") if isinstance(node.get("predicate"), dict) else node.get("predicate", {})
            if op != "predicate" and "predicate" not in node:
                # Allow shorthand: treat node itself as predicate object if it looks like one
                if "type" in node:
                    pred = node
                else:
                    pred = {}
            return lambda b, p: self._eval_goal_predicate(
                b,
                p,
                pred,
                root_turn=root_turn,
                root_material_balance=root_material_balance,
            )

        goal_fn = _compile_goal(goal)

        witnesses: List[Dict[str, Any]] = []
        witness_seen: set = set()

        def _record_witness(line_pairs: List[Tuple[bool, str]], *, found_depth: int, score_cp: Optional[int] = None):
            line_san = [m for _, m in line_pairs]
            key = tuple(line_san)
            if not line_san or key in witness_seen:
                return
            witness_seen.add(key)
            score_root = None
            if score_cp is not None:
                score_root = score_cp if root_turn == chess.WHITE else -score_cp
            progress = self._goal_progress(root_board, line_pairs, goal, root_turn=root_turn, root_material_balance=root_material_balance)
            witnesses.append({
                "line_san": line_san,
                "plies": len(line_san),
                "depth": found_depth,
                "score_cp": score_cp,
                "score_root": score_root,
                "progress": progress,
                "nodes_explored": None,  # filled at return time if needed
            })

        def _build_pgn_from_witness(start_fen: str, moves_san: List[str]) -> str:
            try:
                game = chess.pgn.Game()
                game.headers["FEN"] = start_fen
                game.headers["SetUp"] = "1"
                game.headers["Event"] = "Investigation (Target)"
                board = chess.Board(start_fen)
                node = game
                for san in moves_san:
                    mv = board.parse_san(san)
                    node = node.add_variation(mv)
                    board.push(mv)
                exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=False)
                return game.accept(exporter)
            except Exception:
                return ""

        async def _analyze_multipv_first_moves(fen_in: str, depth: int, multipv: int) -> List[Dict[str, Any]]:
            b = chess.Board(fen_in)
            info_list: List[Dict[str, Any]] = []
            try:
                if self.use_pool and self.engine_pool:
                    analysis = await self.engine_pool.analyze_single(fen=fen_in, depth=depth, multipv=multipv)
                    if analysis.get("success") and analysis.get("result") is not None:
                        raw = analysis["result"]
                        info_list = raw if isinstance(raw, list) else [raw]
                elif self.engine_queue:
                    raw = await self.engine_queue.enqueue(
                        self.engine_queue.engine.analyse,
                        b,
                        chess.engine.Limit(depth=depth),
                        multipv=multipv
                    )
                    info_list = raw if isinstance(raw, list) else [raw]
            except TypeError:
                # Some engine bindings may not accept multipv; fallback to single PV
                try:
                    single = await self._analyze_depth(fen_in, depth=depth, get_top_2=False)
                    san = single.get("best_move_san")
                    eval_cp = single.get("best_move_eval_cp")
                    return [{"move_san": san, "eval_cp": eval_cp}] if san else []
                except Exception:
                    return []
            except Exception:
                return []

            out: List[Dict[str, Any]] = []
            for info in info_list:
                if not isinstance(info, dict):
                    continue
                score = info.get("score")
                eval_cp = self._score_to_white_cp(score, fen=fen_in)
                pv = info.get("pv") or []
                if not pv:
                    continue
                first = pv[0]
                if first not in b.legal_moves:
                    continue
                try:
                    san = b.san(first)
                except Exception:
                    continue
                out.append({"move_san": san, "eval_cp": eval_cp})

            # Sort in the side-to-move's preference
            if b.turn == chess.WHITE:
                out.sort(key=lambda x: (x.get("eval_cp") if x.get("eval_cp") is not None else -10**9), reverse=True)
            else:
                out.sort(key=lambda x: (-(x.get("eval_cp") if x.get("eval_cp") is not None else 10**9)), reverse=True)
            return out

        # Evaluate goal at root
        root_path: List[Tuple[bool, str]] = []
        if goal_fn(root_board, root_path):
            witness: List[str] = []
            return InvestigationResult(
                eval_before=None,
                pv_after_move=witness,
                goal_search_results={
                    "goal_status": "success",
                    "witness_line_san": witness,
                    "witnesses": [],
                    "limits": {
                        "depth": 0,
                        "nodes_explored": 0,
                        "policy": {
                            "query_type": query_type,
                            "max_depth": max_depth,
                            "beam_width": beam_width,
                            "branching_limit": branching_limit,
                            "opponent_model": opponent_model,
                            "engine_depth_propose": engine_depth_propose,
                            "engine_depth_reply": engine_depth_reply,
                            "pv_extend_plies": pv_extend_plies,
                            "top_k_witnesses": top_k_witnesses,
                        }
                    },
                    "assumptions": []
                },
                pgn_exploration=_build_pgn_from_witness(fen, witness),
            )

        # Beam search
        frontier: List[Tuple[str, List[Tuple[bool, str]], Optional[int]]] = [(fen, [], None)]  # (fen, path, last_eval_cp)
        visited = {fen}
        nodes_explored = 0
        assumptions: List[str] = []

        if opponent_model != "best":
            assumptions.append(f"opponent_model={opponent_model} (v1 primarily tuned for 'best')")

        for depth in range(1, max_depth + 1):
            next_frontier: List[Tuple[str, List[Tuple[bool, str]], Optional[int]]] = []

            for (cur_fen, path, last_eval_cp) in frontier:
                if nodes_explored > 5000:
                    assumptions.append("node_limit_reached")
                    break

                cur_board = chess.Board(cur_fen)
                side_to_move = cur_board.turn

                # Propose candidate moves for side_to_move
                candidates = await _analyze_multipv_first_moves(cur_fen, depth=engine_depth_propose, multipv=branching_limit)
                if not candidates:
                    # Fallback: try any legal moves (first few SAN)
                    try:
                        candidates = []
                        for mv in list(cur_board.legal_moves)[:min(branching_limit, 6)]:
                            candidates.append({"move_san": cur_board.san(mv), "eval_cp": None})
                    except Exception:
                        continue

                # Expand children from candidates
                for cand in candidates[:beam_width]:
                    san_move = cand.get("move_san")
                    if not san_move or not isinstance(san_move, str):
                        continue
                    child_board = chess.Board(cur_fen)
                    try:
                        mv = child_board.parse_san(san_move)
                        child_board.push(mv)
                    except Exception:
                        continue

                    nodes_explored += 1
                    child_path = list(path) + [(side_to_move, san_move)]

                    # Check goal after this ply
                    if goal_fn(child_board, child_path):
                        _record_witness(child_path, found_depth=depth, score_cp=cand.get("eval_cp"))
                        if top_k_witnesses == 1:
                            witness = [m for _, m in child_path]
                            status = "success"
                            # Compute progress for this witness
                            progress = self._goal_progress(root_board, child_path, goal, root_turn=root_turn, root_material_balance=root_material_balance)
                            return InvestigationResult(
                                pv_after_move=witness,
                                goal_search_results={
                                    "goal_status": status,
                                    "witness_line_san": witness,
                                    "witnesses": [{"line_san": witness, "plies": len(witness), "depth": depth, "score_cp": cand.get("eval_cp"), "score_root": (cand.get("eval_cp") if root_turn == chess.WHITE else (-cand.get("eval_cp") if cand.get("eval_cp") is not None else None)), "progress": progress}],
                                    "best_progress_reached": float(progress) if isinstance(progress, (int, float)) else 0.0,
                                    "limits": {
                                        "depth": depth,
                                        "nodes_explored": nodes_explored,
                                        "policy": {
                                            "query_type": query_type,
                                            "max_depth": max_depth,
                                            "beam_width": beam_width,
                                            "branching_limit": branching_limit,
                                            "opponent_model": opponent_model,
                                            "engine_depth_propose": engine_depth_propose,
                                            "engine_depth_reply": engine_depth_reply,
                                            "pv_extend_plies": pv_extend_plies,
                                            "top_k_witnesses": top_k_witnesses,
                                        }
                                    },
                                    "assumptions": assumptions
                                },
                                pgn_exploration=_build_pgn_from_witness(fen, witness),
                            )
                        # For top-k collection, keep searching siblings at this depth.
                        continue

                    # Apply opponent reply if any depth left
                    if opponent_model == "best":
                        try:
                            reply_candidates = await _analyze_multipv_first_moves(
                                child_board.fen(),
                                depth=engine_depth_reply,
                                multipv=1
                            )
                            reply_san = reply_candidates[0]["move_san"] if reply_candidates else None
                        except Exception:
                            reply_san = None

                        if reply_san:
                            opp_turn = child_board.turn
                            try:
                                mv2 = child_board.parse_san(reply_san)
                                child_board.push(mv2)
                                child_path.append((opp_turn, reply_san))
                            except Exception:
                                pass

                            # Check goal after opponent reply too
                            if goal_fn(child_board, child_path):
                                _record_witness(child_path, found_depth=depth, score_cp=cand.get("eval_cp"))
                                if top_k_witnesses == 1:
                                    witness = [m for _, m in child_path]
                                    status = "success"
                                    # Compute progress for this witness
                                    progress = self._goal_progress(root_board, child_path, goal, root_turn=root_turn, root_material_balance=root_material_balance)
                                    return InvestigationResult(
                                        pv_after_move=witness,
                                        goal_search_results={
                                            "goal_status": status,
                                            "witness_line_san": witness,
                                            "witnesses": [{"line_san": witness, "plies": len(witness), "depth": depth, "score_cp": cand.get("eval_cp"), "score_root": (cand.get("eval_cp") if root_turn == chess.WHITE else (-cand.get("eval_cp") if cand.get("eval_cp") is not None else None)), "progress": progress}],
                                            "best_progress_reached": float(progress) if isinstance(progress, (int, float)) else 0.0,
                                            "limits": {
                                                "depth": depth,
                                                "nodes_explored": nodes_explored,
                                                "policy": {
                                                    "query_type": query_type,
                                                    "max_depth": max_depth,
                                                    "beam_width": beam_width,
                                                    "branching_limit": branching_limit,
                                                    "opponent_model": opponent_model,
                                                    "engine_depth_propose": engine_depth_propose,
                                                    "engine_depth_reply": engine_depth_reply,
                                                    "pv_extend_plies": pv_extend_plies,
                                                    "top_k_witnesses": top_k_witnesses,
                                                }
                                            },
                                            "assumptions": assumptions
                                        },
                                        pgn_exploration=_build_pgn_from_witness(fen, witness),
                                    )
                                continue

                    child_fen = child_board.fen()
                    if child_fen in visited:
                        continue
                    visited.add(child_fen)
                    next_frontier.append((child_fen, child_path, cand.get("eval_cp")))

            if not next_frontier:
                break

            # If we already collected enough witnesses, stop early (witnesses are usually shortest at shallowest depth).
            if len(witnesses) >= top_k_witnesses:
                break

            # Prune to global beam_width based on eval (fallback if None)
            def _score_node(node: Tuple[str, List[Tuple[bool, str]], Optional[int]]) -> int:
                f, p, eval_cp = node
                if eval_cp is None:
                    return -10**9
                # score from root side perspective: prefer higher for root white, lower for root black
                return eval_cp if root_turn == chess.WHITE else -eval_cp

            next_frontier.sort(key=_score_node, reverse=True)
            frontier = next_frontier[:beam_width]

        if witnesses:
            # Sort witnesses: prefer shallow depth, then shorter lines, then better root score.
            def _w_sort(w: Dict[str, Any]):
                depth_v = w.get("depth") if w.get("depth") is not None else 10**9
                plies_v = w.get("plies") if w.get("plies") is not None else 10**9
                prog_v = w.get("progress")
                prog_v = float(prog_v) if isinstance(prog_v, (int, float)) else 0.0
                score_v = w.get("score_root")
                score_v = score_v if isinstance(score_v, int) else -10**9
                return (depth_v, plies_v, -prog_v, -score_v, " ".join(w.get("line_san") or []))

            witnesses_sorted = sorted(witnesses, key=_w_sort)[:top_k_witnesses]
            best_line = list(witnesses_sorted[0].get("line_san") or [])
            for w in witnesses_sorted:
                w["nodes_explored"] = nodes_explored
            
            # Compute best_progress_reached from witnesses
            best_progress = 0.0
            if witnesses_sorted:
                for w in witnesses_sorted:
                    prog = w.get("progress")
                    if isinstance(prog, (int, float)):
                        best_progress = max(best_progress, float(prog))
            
            return InvestigationResult(
                pv_after_move=best_line,
                goal_search_results={
                    "goal_status": "success",
                    "witness_line_san": best_line,
                    "witnesses": witnesses_sorted,
                    "best_progress_reached": best_progress,
                    "limits": {
                        "depth": max_depth,
                        "nodes_explored": nodes_explored,
                        "policy": {
                            "query_type": query_type,
                            "max_depth": max_depth,
                            "beam_width": beam_width,
                            "branching_limit": branching_limit,
                            "opponent_model": opponent_model,
                            "engine_depth_propose": engine_depth_propose,
                            "engine_depth_reply": engine_depth_reply,
                            "pv_extend_plies": pv_extend_plies,
                            "top_k_witnesses": top_k_witnesses,
                        }
                    },
                    "assumptions": assumptions
                },
                pgn_exploration=_build_pgn_from_witness(fen, best_line),
            )

        # If we got here, we did not find a witness within limits
        status = "uncertain" if max_depth > 0 else "failure"
        
        # Compute best_progress_reached from any witnesses we found (even if not successful)
        best_progress = 0.0
        if witnesses:
            for w in witnesses:
                prog = w.get("progress")
                if isinstance(prog, (int, float)):
                    best_progress = max(best_progress, float(prog))
        
        return InvestigationResult(
            pv_after_move=[],
            goal_search_results={
                "goal_status": status,
                "witness_line_san": [],
                "witnesses": [],
                "best_progress_reached": best_progress,
                "limits": {
                    "depth": max_depth,
                    "nodes_explored": nodes_explored,
                    "policy": {
                        "query_type": query_type,
                        "max_depth": max_depth,
                        "beam_width": beam_width,
                        "branching_limit": branching_limit,
                        "opponent_model": opponent_model,
                        "engine_depth_propose": engine_depth_propose,
                        "engine_depth_reply": engine_depth_reply,
                        "pv_extend_plies": pv_extend_plies,
                        "top_k_witnesses": top_k_witnesses,
                    }
                },
                "assumptions": assumptions
            },
            pgn_exploration="",
        )

    def _material_balance_pawns(self, board: chess.Board) -> float:
        """Material balance in pawns from White perspective (white - black)."""
        values = {
            chess.PAWN: 1,
            chess.KNIGHT: 3,
            chess.BISHOP: 3,
            chess.ROOK: 5,
            chess.QUEEN: 9,
            chess.KING: 0,
        }
        white = 0
        black = 0
        for sq, piece in board.piece_map().items():
            v = values.get(piece.piece_type, 0)
            if piece.color == chess.WHITE:
                white += v
            else:
                black += v
        return float(white - black)

    def _eval_goal_predicate(
        self,
        board: chess.Board,
        path: List[Tuple[bool, str]],
        predicate: Dict[str, Any],
        *,
        root_turn: bool,
        root_material_balance: float,
    ) -> bool:
        if not isinstance(predicate, dict):
            return False
        p_type = predicate.get("type")
        params = predicate.get("params") or {}
        if p_type == "castle":
            side = (params.get("side") or "white").lower()
            mode = (params.get("mode") or "already_castled").lower()
            color = chess.WHITE if side == "white" else chess.BLACK
            king_sq = board.king(color)
            if king_sq is None:
                return False
            king_name = chess.square_name(king_sq)
            if mode == "already_castled":
                if color == chess.WHITE:
                    return king_name in ("g1", "c1")
                return king_name in ("g8", "c8")
            if mode == "can_castle_next":
                # v1: only meaningful when it's that side to move
                if board.turn != color:
                    return False
                # must be a legal move right now
                for mv in board.legal_moves:
                    try:
                        san = board.san(mv)
                    except Exception:
                        continue
                    if san in ("O-O", "O-O-O"):
                        return True
                return False
            return False

        if p_type == "play_move":
            move_san = params.get("move_san")
            by = (params.get("by") or "side_to_move").lower()
            if not move_san or not isinstance(move_san, str):
                return False
            if by == "side_to_move":
                # Side to move at root
                by_color = root_turn
            else:
                by_color = chess.WHITE if by == "white" else chess.BLACK
            for ply_color, ply_san in path:
                if ply_color == by_color and ply_san == move_san:
                    return True
            return False

        if p_type == "piece_on_square":
            piece_letter = (params.get("piece") or "").upper()
            side = (params.get("side") or "white").lower()
            square = params.get("square")
            if not piece_letter or not square:
                return False
            try:
                sq = chess.parse_square(square)
            except Exception:
                return False
            p = board.piece_at(sq)
            if not p:
                return False
            color = chess.WHITE if side == "white" else chess.BLACK
            symbol = p.symbol().upper() if color == chess.WHITE else p.symbol().lower()
            return symbol.upper() == piece_letter and p.color == color

        if p_type == "piece_on_color":
            piece_letter = (params.get("piece") or "").upper()
            side = (params.get("side") or "white").lower()
            color_name = (params.get("color") or "light").lower()
            color = chess.WHITE if side == "white" else chess.BLACK
            want_light = color_name == "light"
            for sq, p in board.piece_map().items():
                if p.color != color:
                    continue
                if p.symbol().upper() != piece_letter:
                    continue
                try:
                    is_light = chess.square_color(sq)  # True=light in python-chess
                except Exception:
                    f = chess.square_file(sq)
                    r = chess.square_rank(sq)
                    is_light = ((f + r) % 2 == 1)  # a1 dark
                if bool(is_light) == bool(want_light):
                    return True
            return False

        if p_type == "material_delta_at_least":
            side = (params.get("side") or "white").lower()
            pawns = float(params.get("pawns") or 0)
            cur_bal = self._material_balance_pawns(board)
            delta_white = cur_bal - root_material_balance
            delta = delta_white if side == "white" else -delta_white
            return delta >= pawns

        if p_type == "fen_contains":
            pattern = params.get("pattern") or params.get("text") or ""
            if not isinstance(pattern, str):
                return False
            return pattern in board.fen()

        if p_type == "fen_regex":
            pattern = params.get("pattern") or ""
            if not isinstance(pattern, str) or not pattern:
                return False
            try:
                return re.search(pattern, board.fen()) is not None
            except re.error:
                return False

        return False

    def _goal_progress(
        self,
        root_board: chess.Board,
        path: List[Tuple[bool, str]],
        goal: Dict[str, Any],
        *,
        root_turn: bool,
        root_material_balance: float,
    ) -> float:
        """
        Best-effort progress metric in [0,1].
        - 1.0 if goal satisfied
        - Otherwise heuristic progress for some predicate types; 0.0 fallback
        """
        try:
            goal_fn = None
            # Reuse existing compiler semantics via a tiny local compile to avoid refactors
            def _compile(node: Any) -> Callable[[chess.Board, List[Tuple[bool, str]]], bool]:
                if not isinstance(node, dict):
                    return lambda b, p: False
                op = node.get("op")
                if op in ("and", "or"):
                    args = node.get("args") or []
                    fs = [_compile(a) for a in args if a is not None]
                    if op == "and":
                        return lambda b, p: all(f(b, p) for f in fs)
                    return lambda b, p: any(f(b, p) for f in fs)
                if op == "not":
                    args = node.get("args") or []
                    f0 = _compile(args[0]) if args else (lambda b, p: False)
                    return lambda b, p: (not f0(b, p))
                pred = node.get("predicate") if isinstance(node.get("predicate"), dict) else node.get("predicate", {})
                if op != "predicate" and "predicate" not in node:
                    pred = node if "type" in node else {}
                return lambda b, p: self._eval_goal_predicate(
                    b, p, pred, root_turn=root_turn, root_material_balance=root_material_balance
                )

            goal_fn = _compile(goal)
            if goal_fn and goal_fn(root_board, path):
                return 1.0
        except Exception:
            pass

        # Heuristic: if goal is a single predicate, compute partial progress
        pred = None
        if isinstance(goal, dict):
            if goal.get("op") == "predicate" and isinstance(goal.get("predicate"), dict):
                pred = goal.get("predicate")
            elif "type" in goal:
                pred = goal
        if not isinstance(pred, dict):
            return 0.0

        p_type = pred.get("type")
        params = pred.get("params") or {}

        # Apply path to get current board
        b = root_board.copy()
        try:
            for _, san in path:
                mv = b.parse_san(san)
                b.push(mv)
        except Exception:
            return 0.0

        if p_type == "piece_on_square":
            square = params.get("square")
            piece_letter = (params.get("piece") or "").upper()
            side = (params.get("side") or "white").lower()
            if not square or not piece_letter:
                return 0.0
            try:
                target_sq = chess.parse_square(square)
            except Exception:
                return 0.0
            color = chess.WHITE if side == "white" else chess.BLACK
            # Find a matching piece and compute distance to target
            best_d = None
            for sq, p in b.piece_map().items():
                if p.color != color:
                    continue
                if p.symbol().upper() != piece_letter:
                    continue
                df = abs(chess.square_file(sq) - chess.square_file(target_sq))
                dr = abs(chess.square_rank(sq) - chess.square_rank(target_sq))
                d = df + dr
                best_d = d if best_d is None else min(best_d, d)
            if best_d is None:
                return 0.0
            # Map distance to [0,1] with a soft cap
            return max(0.0, 1.0 - (best_d / 8.0))

        if p_type == "material_delta_at_least":
            side = (params.get("side") or "white").lower()
            pawns = float(params.get("pawns") or 0)
            cur_bal = self._material_balance_pawns(b)
            delta_white = cur_bal - root_material_balance
            delta = delta_white if side == "white" else -delta_white
            if pawns <= 0:
                return 1.0 if delta >= 0 else 0.0
            return max(0.0, min(1.0, delta / pawns))

        if p_type == "castle":
            # progress: 1.0 if already castled; else 0.5 if castling is currently legal (for that side)
            side = (params.get("side") or "white").lower()
            color = chess.WHITE if side == "white" else chess.BLACK
            king_sq = b.king(color)
            if king_sq is None:
                return 0.0
            king_name = chess.square_name(king_sq)
            if color == chess.WHITE and king_name in ("g1", "c1"):
                return 1.0
            if color == chess.BLACK and king_name in ("g8", "c8"):
                return 1.0
            # If it's that side to move and castling move exists, return partial progress.
            if b.turn == color:
                for mv in b.legal_moves:
                    try:
                        san = b.san(mv)
                    except Exception:
                        continue
                    if san in ("O-O", "O-O-O"):
                        return 0.5
            return 0.0

        return 0.0
    
    async def investigate_game(
        self,
        pgn: str,
        focus_move_index: Optional[int] = None,
        focus: Optional[str] = None
    ) -> InvestigationResult:
        """
        Investigate a game and identify decisive moments.
        
        Args:
            pgn: PGN string of game
            focus_move_index: Optional move index to focus on
            focus: Optional focus (e.g., "knight", "opponent_play") - for future filtering/emphasis
            
        Returns:
            InvestigationResult with game analysis facts
        """
        try:
            game = chess.pgn.read_game(io.StringIO(pgn))
            if not game:
                return InvestigationResult()
            
            if focus_move_index is not None:
                # Find the move
                node = game
                for _ in range(focus_move_index):
                    if not node.variations:
                        break
                    node = node.variation(0)
                
                # Analyze before/after
                if node.parent:
                    fen_before = node.parent.board().fen()
                    fen_after = node.board().fen()
                    
                    before_result = await self.investigate_position(fen_before)
                    after_result = await self.investigate_position(fen_after)
                    
                    eval_drop = None
                    if before_result.eval_before is not None and after_result.eval_before is not None:
                        eval_drop = after_result.eval_before - before_result.eval_before
                    
                    return InvestigationResult(
                        eval_before=before_result.eval_before,
                        eval_after=after_result.eval_before,
                        eval_drop=eval_drop,
                        player_move=node.san() if node.move else None,
                        game_phase=before_result.game_phase
                    )
            
            return InvestigationResult()
        except Exception as e:
            return InvestigationResult()
    
    def _classify_game_phase(self) -> str:
        """Classify game phase - enum only"""
        piece_count = len(self.board.piece_map())
        if piece_count > 24:
            return "opening"
        elif piece_count > 12:
            return "middlegame"
        else:
            return "endgame"
    
    def _classify_urgency(self, eval_cp: int) -> str:
        """Classify urgency - enum only"""
        abs_eval = abs(eval_cp)
        if abs_eval > 300:
            return "critical"
        elif abs_eval > 150:
            return "high"
        else:
            return "normal"
    
    def _classify_mistake(self, eval_drop: float) -> str:
        """Classify mistake type - enum only"""
        abs_drop = abs(eval_drop)
        if abs_drop > 3.0:
            return "blunder"
        elif abs_drop > 1.5:
            return "mistake"
        elif abs_drop > 0.5:
            return "inaccuracy"
        else:
            return "none"
    
    def _classify_move_intent(self, move: chess.Move, board: chess.Board) -> str:
        """Classify move intent - enum only"""
        if board.is_capture(move):
            return "tactical"
        elif board.is_castling(move):
            return "defensive"
        elif board.piece_at(move.from_square) and board.piece_at(move.from_square).piece_type == chess.PAWN:
            # Pawn move - could be development or attack
            return "positional_improvement"
        elif board.piece_at(move.from_square) and board.piece_at(move.from_square).piece_type in [chess.KNIGHT, chess.BISHOP]:
            # Minor piece move - likely development
            return "development"
        elif board.gives_check(move):
            return "attack"
        else:
            return "positional_improvement"
    
    async def _analyze_consequences(
        self,
        original_fen: str,
        move_san: str,
        board_after: chess.Board,
        move_obj: chess.Move,
        pv: List[str]
    ) -> Dict[str, Any]:
        """Analyze specific consequences of a move"""
        import chess
        consequences = {}
        
        # Determine which side made the move
        board_before = chess.Board(original_fen)
        player_color = board_before.turn  # Side that made the move
        opponent_color = not player_color  # Side to move next
        
        # Check for doubled pawns - COMPARE before and after, ONLY report PLAYER's doubled pawns
        doubled_before = self._check_doubled_pawns(board_before)
        doubled_after = self._check_doubled_pawns(board_after)
        
        # Filter to only PLAYER's doubled pawns (bad for player)
        if doubled_after and doubled_after.get("doubled"):
            player_doubled_after = [d for d in doubled_after.get("doubled", []) 
                                   if (d.get("color") == "white" and player_color == chess.WHITE) or
                                      (d.get("color") == "black" and player_color == chess.BLACK)]
            
            if player_doubled_after:
                if doubled_before and doubled_before.get("doubled"):
                    player_doubled_before = [d for d in doubled_before.get("doubled", [])
                                            if (d.get("color") == "white" and player_color == chess.WHITE) or
                                               (d.get("color") == "black" and player_color == chess.BLACK)]
                    before_files = {d.get("file") for d in player_doubled_before}
                    after_files = {d.get("file") for d in player_doubled_after}
                    new_doubled_files = after_files - before_files
                    
                    if new_doubled_files:
                        new_doubled = [d for d in player_doubled_after if d.get("file") in new_doubled_files]
                        consequences["doubled_pawns"] = {"doubled": new_doubled, "newly_created": True, "side": "player"}
                else:
                    consequences["doubled_pawns"] = {"doubled": player_doubled_after, "newly_created": True, "side": "player"}
        
        # Check for pins - COMPARE before and after to detect newly created pins
        pins_before = self._check_pins(board_before)
        pins_after = self._check_pins(board_after)
        
        if pins_after:
            # Compare to find newly created pins (like doubled pawns logic)
            if pins_before:
                # Extract pinned piece squares for comparison
                before_pinned_squares = {p.get("pinned_piece") for p in pins_before if p.get("pinned_piece")}
                after_pinned_squares = {p.get("pinned_piece") for p in pins_after if p.get("pinned_piece")}
                newly_pinned_squares = after_pinned_squares - before_pinned_squares
                
                if newly_pinned_squares:
                    # Some pins are newly created
                    new_pins = [p for p in pins_after if p.get("pinned_piece") in newly_pinned_squares]
                    pre_existing_pins = [p for p in pins_after if p.get("pinned_piece") in before_pinned_squares]
                    consequences["pins"] = {
                        "pins": pins_after,  # All pins after move
                        "newly_created": new_pins,  # Only newly created pins
                        "pre_existing": pre_existing_pins,  # Pins that existed before
                        "has_new_pins": True
                    }
                else:
                    # All pins were pre-existing
                    consequences["pins"] = {
                        "pins": pins_after,
                        "newly_created": [],
                        "pre_existing": pins_after,
                        "has_new_pins": False
                    }
            else:
                # No pins before, all are new
                consequences["pins"] = {
                    "pins": pins_after,
                    "newly_created": pins_after,
                    "pre_existing": [],
                    "has_new_pins": True
                }
        
        # Check if move allows opponent captures - verify these are BAD for player
        opponent_captures = []
        for move in board_after.legal_moves:
            if board_after.is_capture(move):
                # These are opponent's captures (bad for player)
                opponent_captures.append(board_after.san(move))
        
        if opponent_captures:
            consequences["allows_captures"] = {
                "captures": opponent_captures[:3],
                "side": "opponent",  # These are opponent's captures (bad for player)
                "severity": "potential_threat"
            }
        
        # NEW: Check for awkward development mechanisms
        awkward_reason = await self._detect_awkward_mechanism(
            original_fen, move_san, board_after, move_obj, pv, consequences
        )
        if awkward_reason:
            consequences["awkward_mechanism"] = awkward_reason
            unlock_condition = self._detect_unlock_condition(
                original_fen, board_after, move_obj, awkward_reason
            )
            if unlock_condition:
                consequences["unlock_condition"] = unlock_condition
        
        # Follow PV to see what happens
        if pv:
            pv_consequences = await self._follow_pv_consequences(board_after.copy(), pv[:8])
            if pv_consequences:
                consequences["pv_shows"] = pv_consequences
        
        return consequences
    
    def _check_doubled_pawns(self, board: chess.Board) -> Optional[Dict[str, Any]]:
        """Check for doubled pawns - structured data only"""
        doubled = []
        for color in [chess.WHITE, chess.BLACK]:
            pawns_by_file = {}
            for square in chess.SQUARES:
                piece = board.piece_at(square)
                if piece and piece.piece_type == chess.PAWN and piece.color == color:
                    file = chess.square_file(square)
                    if file not in pawns_by_file:
                        pawns_by_file[file] = []
                    pawns_by_file[file].append(chess.square_name(square))
            
            for file, squares in pawns_by_file.items():
                if len(squares) > 1:
                    doubled.append({
                        "color": "white" if color == chess.WHITE else "black",
                        "file": file,
                        "squares": squares
                    })
        
        return {"doubled": doubled} if doubled else None
    
    def _check_pins(self, board: chess.Board) -> Optional[List[Dict[str, Any]]]:
        """Check for pins - structured data only"""
        pins = []
        try:
            from threat_analyzer import _get_pin_details
            
            for square in chess.SQUARES:
                piece = board.piece_at(square)
                if piece:
                    pin_info = _get_pin_details(board, None, square)
                    if pin_info:
                        pins.append({
                            "pinned_piece": chess.square_name(square),
                            "target": pin_info.get("target", ""),
                            "attacker": pin_info.get("attacker", "")
                        })
        except ImportError:
            pass
        except Exception:
            pass
        
        return pins if pins else None
    
    async def _detect_awkward_mechanism(
        self,
        original_fen: str,
        move_san: str,
        board_after: chess.Board,
        move_obj: chess.Move,
        pv: List[str],
        consequences: Dict[str, Any]
    ) -> Optional[str]:
        """
        Detect why a move is awkward. Returns one of:
        - "allows_structural_damage"
        - "allows_tactical_capture"
        - "blocked_by_enemy_piece"
        - "leaves_king_exposed"
        - "loses_tempo_under_threat"
        
        Only returns if VERIFIED by board state.
        """
        # Check for structural damage (doubled pawns after capture)
        if "doubled_pawns" in consequences:
            # Verify: Check if opponent can capture and cause doubled pawns
            for move in board_after.legal_moves:
                if board_after.is_capture(move):
                    test_board = board_after.copy()
                    test_board.push(move)
                    doubled = self._check_doubled_pawns(test_board)
                    if doubled:
                        return "allows_structural_damage"
        
        # Check for tactical capture (opponent can capture with advantage)
        if "allows_captures" in consequences:
            capture_info = consequences.get("allows_captures", [])

            # Support both legacy (list) and new (dict) formats and fail loudly on bad types
            if isinstance(capture_info, dict):
                captures = capture_info.get("captures", [])
            elif isinstance(capture_info, list):
                captures = capture_info
            else:
                raise ValueError(
                    f"Unexpected allows_captures type: {type(capture_info).__name__}"
                )

            if captures:
                # Verify the capture is actually available and not trivially refuted
                for capture_san in list(captures)[:2]:  # Check first 2 captures
                    try:
                        capture_move = board_after.parse_san(capture_san)
                        if capture_move in board_after.legal_moves:
                            # Check if capture is winning or equal (not losing)
                            # This is a simplified check - in production, use engine eval
                            return "allows_tactical_capture"
                    except Exception as exc:
                        # Surface unexpected parse errors to avoid silent failures
                        raise RuntimeError(
                            f"Failed to parse capture SAN '{capture_san}'"
                        ) from exc
        
        # Check if blocked by enemy piece (destination square is attacked)
        to_sq = move_obj.to_square
        attackers = board_after.attackers(not board_after.turn, to_sq)
        if attackers:
            # Verify: Check if the attacking piece can actually capture
            for attacker_sq in attackers:
                attacker_piece = board_after.piece_at(attacker_sq)
                if attacker_piece:
                    # Check if attacker can capture the piece on destination
                    if board_after.is_legal(chess.Move(attacker_sq, to_sq)):
                        return "blocked_by_enemy_piece"
        
        # Check if leaves king exposed (king safety check)
        board_before = chess.Board(original_fen)
        king_sq_before = board_before.king(board_before.turn)
        king_sq_after = board_after.king(board_after.turn)
        
        if king_sq_before and king_sq_after:
            # Check if king is more exposed after move
            attackers_before = len(board_before.attackers(not board_before.turn, king_sq_before))
            attackers_after = len(board_after.attackers(not board_after.turn, king_sq_after))
            
            if attackers_after > attackers_before:
                return "leaves_king_exposed"
        
        # Check if loses tempo under threat (there's a threat that should be addressed first)
        if pv and len(pv) > 0:
            # Check if PV shows opponent has a strong threat
            first_pv_move = pv[0] if pv else None
            if first_pv_move:
                try:
                    pv_move_obj = board_after.parse_san(first_pv_move)
                    if board_after.gives_check(pv_move_obj):
                        return "loses_tempo_under_threat"
                except:
                    pass
        
        return None
    
    def _detect_unlock_condition(
        self,
        original_fen: str,
        board_after: chess.Board,
        move_obj: chess.Move,
        awkward_reason: str
    ) -> Optional[str]:
        """
        Detect what needs to change to make the move work.
        Returns unlock condition describing what must change for the move to become viable.
        """
        board_before = chess.Board(original_fen)
        to_sq = move_obj.to_square
        
        if awkward_reason == "blocked_by_enemy_piece":
            # Find what piece is blocking
            attackers = board_after.attackers(not board_after.turn, to_sq)
            if attackers:
                for attacker_sq in attackers:
                    attacker_piece = board_after.piece_at(attacker_sq)
                    if attacker_piece:
                        piece_name = attacker_piece.symbol().upper() if attacker_piece.color == chess.WHITE else attacker_piece.symbol()
                        square_name = chess.square_name(attacker_sq)
                        
                        # Check if we can challenge the piece
                        our_attackers = board_before.attackers(board_before.turn, attacker_sq)
                        if our_attackers:
                            return f"once the {piece_name} on {square_name} is challenged or traded"
                        else:
                            # Check if we can interpose or block
                            return f"once the {piece_name} on {square_name} is removed or blocked"
        
        elif awkward_reason == "allows_tactical_capture":
            # Find what prevents the capture
            captures = []
            for move in board_after.legal_moves:
                if board_after.is_capture(move) and move.to_square == to_sq:
                    captures.append(board_after.san(move))
            
            if captures:
                capture_san = captures[0]
                # Try to find a move that prevents it
                # This is simplified - in production, use engine to find best prevention
                return f"once the capture {capture_san} is prevented"
        
        elif awkward_reason == "allows_structural_damage":
            # Find what prevents the structural damage
            return "once the threat to your pawn structure is removed"
        
        elif awkward_reason == "leaves_king_exposed":
            return "once your king is better protected"
        
        elif awkward_reason == "loses_tempo_under_threat":
            return "once the immediate threat is addressed"
        
        return None
    
    async def _detect_tactics(
        self,
        original_fen: str,
        move_san: str,
        move_obj: chess.Move
    ) -> List[Dict[str, Any]]:
        """Detect tactics - structured data only"""
        tactics = []
        
        try:
            from threat_analyzer import is_fork, is_skewer, _get_fork_details, _get_skewer_details
            
            # Need board before move to check tactics
            board_before = chess.Board(original_fen)
            
            # Check for forks
            if is_fork(board_before, move_obj):
                fork_details = _get_fork_details(board_before, move_obj)
                tactics.append({
                    "type": "fork",
                    "attacker": fork_details.get("attacker_name", ""),
                    "targets": fork_details.get("targets", [])
                })
            
            # Check for skewers
            if is_skewer(board_before, move_obj):
                skewer_details = _get_skewer_details(board_before, move_obj)
                tactics.append({
                    "type": "skewer",
                    "attacker": skewer_details.get("attacker_name", ""),
                    "front_piece": skewer_details.get("front_piece", ""),
                    "back_piece": skewer_details.get("back_piece", "")
                })
            
            # Check for discovered attacks
            discovered = self._check_discovered_attacks(board_before, move_obj)
            if discovered:
                tactics.append(discovered)
            
        except ImportError:
            pass
        except Exception as e:
            pass
        
        return tactics
    
    def _check_discovered_attacks(self, board: chess.Board, move: chess.Move) -> Optional[Dict[str, Any]]:
        """Check if a move creates a discovered attack"""
        # Simplified check - if moving piece reveals line to enemy piece
        from_sq = move.from_square
        to_sq = move.to_square
        
        # Check if any sliding piece can now attack through the from_square
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.color == board.turn:
                if piece.piece_type in [chess.ROOK, chess.BISHOP, chess.QUEEN]:
                    # Check if this piece can attack through from_sq
                    try:
                        if board.is_attacked_by(piece.color, to_sq):
                            return {
                                "type": "discovered_attack",
                                "revealing_piece": chess.square_name(from_sq),
                                "attacking_piece": chess.square_name(square)
                            }
                    except:
                        pass
        
        return None
    
    async def _follow_pv_consequences(
        self,
        board: chess.Board,
        pv: List[str]
    ) -> Dict[str, Any]:
        """Follow PV and check consequences"""
        consequences = {}
        
        try:
            for move_san in pv[:5]:
                try:
                    move = board.parse_san(move_san)
                    if move in board.legal_moves:
                        board.push(move)
                        
                        # Check for captures
                        if board.is_capture(move):
                            if "captures" not in consequences:
                                consequences["captures"] = []
                            consequences["captures"].append(move_san)
                    else:
                        break
                except Exception:
                    break
        except Exception:
            pass
        
        return consequences
    
    def _build_pgn_branch(self, fen: str, moves: List[str]) -> str:
        """Build a PGN branch from moves"""
        try:
            game = chess.pgn.Game()
            game.headers["FEN"] = fen
            node = game
            
            board = chess.Board(fen)
            for move_san in moves:
                try:
                    move = board.parse_san(move_san)
                    if move in board.legal_moves:
                        board.push(move)
                        node = node.add_variation(move)
                    else:
                        break
                except Exception:
                    break
            
            exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=False)
            return str(game.accept(exporter))
        except Exception:
            return ""
    
    async def _analyze_depth(
        self,
        fen: str,
        depth: int,
        get_top_2: bool = False
    ) -> Dict[str, Any]:
        """
        Generic depth analysis wrapper.
        Analyzes position at specified depth and returns eval, best_move, and top_moves.
        
        Args:
            fen: FEN string of position
            depth: Analysis depth
            get_top_2: If True, analyzes top 2 moves at full depth (for D16 critical/winning move detection)
            
        Returns:
            {
                "eval": float,  # In pawns
                "best_move": str,  # UCI notation
                "best_move_san": str,  # SAN notation
                "best_move_eval_cp": int,  # In centipawns
                "pv": List[chess.Move],  # Full PV sequence as Move objects
                "pv_san": List[str],  # Full PV sequence in SAN notation
                "second_best_move": str,  # UCI notation (if get_top_2=True)
                "second_best_move_san": str,  # SAN notation (if get_top_2=True)
                "second_best_move_eval_cp": int,  # In centipawns (if get_top_2=True)
                "is_critical": bool,  # True if cp loss > 50 between best and second best
                "is_winning": bool,  # True if best and second best have different signs
                "top_moves": List[Dict[str, Any]]  # [{move: str, eval: float, rank: int}, ...]
            }
        """
        # This method can generate enormous logs; in non-debug mode, suppress noisy prints
        # but still allow warnings/errors through.
        import builtins as _builtins
        _real_print = _builtins.print
        if not getattr(self, "debug", False):
            def print(*args, **kwargs):  # type: ignore
                try:
                    msg = " ".join(str(a) for a in args)
                    # Suppress routine trace lines; keep warnings/errors and timing visible.
                    if msg.startswith(("   🔍", "   📊", "      🔍", "      📊", "   ✅", "      ✅")):
                        return None
                except Exception:
                    pass
                return _real_print(*args, **kwargs)

        print(f"   🔍 [ANALYZE_DEPTH] INPUT: depth={depth}, get_top_2={get_top_2}, fen={fen[:50]}...")
        print(f"   🔍 [ANALYZE_DEPTH] use_pool={self.use_pool}, engine_pool={self.engine_pool is not None}, engine_queue={self.engine_queue is not None}")
        self.board.set_fen(fen)
        
        # CRITICAL: Verify FEN is correct before analysis
        print(f"   🔍 [EVAL_NORM] FEN VERIFICATION BEFORE ANALYSIS:", flush=True)
        print(f"      - Input FEN: {fen}", flush=True)
        print(f"      - Board FEN after set_fen: {self.board.fen()}", flush=True)
        print(f"      - Side to move in board: {'WHITE' if self.board.turn == chess.WHITE else 'BLACK'}", flush=True)
        if fen != self.board.fen():
            print(f"      - ⚠️ WARNING: FEN mismatch! Input FEN != Board FEN", flush=True)
        
        try:
            if self.use_pool and self.engine_pool:
                # Use engine pool for parallel analysis
                print(f"   🔍 [ANALYZE_DEPTH] Using engine_pool.analyze_single with depth={depth}...", flush=True)
                print(f"      - Passing FEN to engine: {self.board.fen()}", flush=True)
                analysis_result = await self.engine_pool.analyze_single(
                    fen=self.board.fen(),
                    depth=depth,
                    multipv=1
                )
                print(f"   ✅ [ANALYZE_DEPTH] Engine pool call completed")
                print(f"   📊 [ANALYZE_DEPTH] Analysis result success: {analysis_result.get('success')}")
                if analysis_result.get("success") and analysis_result.get("result"):
                    info = analysis_result["result"][0] if isinstance(analysis_result["result"], list) else analysis_result["result"]
                else:
                    print(f"   ⚠️ [ANALYZE_DEPTH] Engine pool returned unsuccessful result: {analysis_result}")
                    info = {}
            elif self.engine_queue:
                # Use engine queue (legacy)
                print(f"   🔍 [ANALYZE_DEPTH] Using engine_queue.enqueue with depth={depth}...")
                info = await self.engine_queue.enqueue(
                    self.engine_queue.engine.analyse,
                    self.board,
                    chess.engine.Limit(depth=depth)
                )
                print(f"   ✅ [ANALYZE_DEPTH] Engine queue call completed")
            else:
                raise ValueError("Neither engine_pool nor engine_queue is available")
            
            print(f"   📊 [ANALYZE_DEPTH] Engine info type: {type(info)}")
            print(f"   📊 [ANALYZE_DEPTH] Engine info keys: {list(info.keys()) if isinstance(info, dict) else 'Not a dict'}")
            
            score = info.get("score")
            print(f"   📊 [ANALYZE_DEPTH] Score object: {score}, type: {type(score)}")
            
            # Log normalization context
            board_analyze = chess.Board(fen)
            print(f"   🔍 [EVAL_NORM] _ANALYZE_DEPTH NORMALIZATION:", flush=True)
            print(f"      - Full FEN: {fen}", flush=True)
            print(f"      - Side to move: {'WHITE' if board_analyze.turn == chess.WHITE else 'BLACK'}", flush=True)
            print(f"      - Raw score from engine: {score}", flush=True)
            print(f"      - Score POV: {score.relative if hasattr(score, 'relative') else 'N/A'}", flush=True)
            if hasattr(score, 'white') and hasattr(score, 'black'):
                print(f"      - Score.white(): {score.white()}", flush=True)
                print(f"      - Score.black(): {score.black()}", flush=True)
            
            eval_cp = self._score_to_white_cp(score, fen=fen)
            print(f"   📊 [ANALYZE_DEPTH] Eval CP: {eval_cp}")
            print(f"      - Normalized eval_cp: {eval_cp}")
            
            eval_pawns = eval_cp / 100.0 if eval_cp is not None else None
            print(f"   📊 [ANALYZE_DEPTH] Eval pawns: {eval_pawns}")
            print(f"      - Normalized eval_pawns: {eval_pawns}")
            
            # Verify normalization logic (score.white() already handles perspective conversion)
            if score is not None and eval_cp is not None:
                raw_pov = score.white() if hasattr(score, 'white') else None
                if raw_pov and not raw_pov.is_mate():
                    raw_cp = raw_pov.score(mate_score=10000)
                    if abs(raw_cp - eval_cp) > 1:  # Allow 1cp tolerance
                        print(f"      - ⚠️ WARNING: Normalization mismatch! raw_cp={raw_cp}, normalized={eval_cp}")
                    else:
                        print(f"      - ✅ Normalization verified: raw_cp={raw_cp}, normalized={eval_cp} (match)")
            
            # Extract PV with error handling - store FULL PV sequence
            pv = info.get("pv", [])
            print(f"   📊 [ANALYZE_DEPTH] PV from engine: {pv}")
            print(f"   📊 [ANALYZE_DEPTH] PV length: {len(pv) if pv else 0}")
            print(f"   📊 [ANALYZE_DEPTH] PV type: {type(pv)}")
            if pv:
                print(f"   📊 [ANALYZE_DEPTH] First PV move: {pv[0]}, type: {type(pv[0])}")
            else:
                print(f"   ⚠️ [ANALYZE_DEPTH] WARNING: Engine returned EMPTY PV!")
                print(f"      Full info dict: {info}")
            
            best_move = None
            best_move_san = None
            pv_san = []  # Full PV in SAN notation
            
            if pv:
                print(f"   🔍 [ANALYZE_DEPTH] Processing PV: {len(pv)} moves")
                try:
                    # Build full PV in SAN notation, validating each move
                    temp_board = self.board.copy()
                    print(f"   🔍 [ANALYZE_DEPTH] Starting board FEN: {temp_board.fen()[:50]}...")
                    for idx, pv_move in enumerate(pv):
                        print(f"   🔍 [ANALYZE_DEPTH] Processing PV move {idx+1}/{len(pv)}: {pv_move}, type: {type(pv_move)}")
                        # Verify move is legal BEFORE adding to PV
                        legal_moves_list = list(temp_board.legal_moves)
                        print(f"   🔍 [ANALYZE_DEPTH] Legal moves count: {len(legal_moves_list)}")
                        if pv_move in temp_board.legal_moves:
                            san_move = temp_board.san(pv_move)
                            print(f"   ✅ [ANALYZE_DEPTH] Move {idx+1} is legal, SAN: {san_move}")
                            pv_san.append(san_move)
                            temp_board.push(pv_move)
                            print(f"   🔍 [ANALYZE_DEPTH] Board after move: {temp_board.fen()[:50]}...")
                        else:
                            # Stop at first invalid move - Stockfish shouldn't return invalid moves
                            # but if it does, we stop here
                            print(f"   ⚠️ [ANALYZE_DEPTH] PV move {pv_move} not legal in position {temp_board.fen()[:50]}, stopping PV")
                            print(f"      First 5 legal moves: {[temp_board.san(m) for m in legal_moves_list[:5]]}")
                            break
                    
                    print(f"   📊 [ANALYZE_DEPTH] PV SAN built: {pv_san} (length: {len(pv_san)})")
                    
                    # Set best_move from first valid move
                    if pv_san:
                        best_move = pv[0].uci()
                        best_move_san = pv_san[0]
                        print(f"   ✅ [ANALYZE_DEPTH] Best move set: UCI={best_move}, SAN={best_move_san}")
                    else:
                        print(f"   ⚠️ [ANALYZE_DEPTH] No valid moves in PV for position {fen[:50]}")
                        print(f"      PV was: {pv}")
                        print(f"      Board FEN: {self.board.fen()}")
                except Exception as pv_e:
                    print(f"   ❌ [ANALYZE_DEPTH] Error parsing PV: {pv_e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"   ⚠️ [ANALYZE_DEPTH] PV is empty, skipping PV processing")
            # best_move_eval_cp will be calculated after playing the move (see get_top_2 section below)
            best_move_eval_cp = None
            
            # NEW: Get top 2 moves at full depth if requested (for D16 analysis)
            second_best_move = None
            second_best_move_san = None
            second_best_move_eval_cp = None
            is_critical = False
            is_winning = False
            
            if get_top_2 and depth >= 16:
                print(f"   🔍 [ANALYZE_DEPTH] get_top_2=True, analyzing top 2 moves at depth {depth}")
                # Get all legal moves and analyze top 2 at full depth
                # We analyze each move by playing it and getting the eval from current side's perspective
                legal_moves = list(self.board.legal_moves)
                print(f"   📊 [ANALYZE_DEPTH] Legal moves count: {len(legal_moves)}")
                print(f"   📊 [ANALYZE_DEPTH] First 5 legal moves: {[self.board.san(m) for m in legal_moves[:5]]}")
                move_scores = []
                
                # Analyze all moves (limit to first 10 for performance)
                print(f"   🔍 [ANALYZE_DEPTH] Analyzing first {min(10, len(legal_moves))} moves...")
                for move_idx, move in enumerate(legal_moves[:10]):
                    print(f"   🔍 [ANALYZE_DEPTH] Analyzing move {move_idx+1}/{min(10, len(legal_moves))}: {self.board.san(move)}")
                    test_board = self.board.copy()
                    test_board.push(move)
                    try:
                        print(f"      🔍 [ANALYZE_DEPTH] Calling engine for move {self.board.san(move)}...")
                        if self.use_pool and self.engine_pool:
                            # Use engine pool
                            move_analysis = await self.engine_pool.analyze_single(
                                fen=test_board.fen(),
                                depth=depth,
                                multipv=1
                            )
                            if move_analysis.get("success") and move_analysis.get("result"):
                                move_info = move_analysis["result"][0] if isinstance(move_analysis["result"], list) else move_analysis["result"]
                            else:
                                print(f"      ⚠️ [ANALYZE_DEPTH] Engine pool returned unsuccessful result for move {self.board.san(move)}")
                                continue
                        elif self.engine_queue:
                            # Use engine queue
                            move_info = await self.engine_queue.enqueue(
                                self.engine_queue.engine.analyse,
                                test_board,
                                chess.engine.Limit(depth=depth)
                            )
                        else:
                            print(f"      ❌ [ANALYZE_DEPTH] Neither engine_pool nor engine_queue available for move analysis")
                            continue
                        
                        print(f"      ✅ [ANALYZE_DEPTH] Engine returned for move {self.board.san(move)}")
                        move_score = move_info.get("score")
                        print(f"      📊 [ANALYZE_DEPTH] Move score: {move_score}")
                        move_eval_cp = self._score_to_white_cp(move_score, fen=test_board.fen())
                        print(f"      📊 [ANALYZE_DEPTH] Move eval CP: {move_eval_cp}")
                        
                        if move_eval_cp is not None:
                            move_scores.append({
                                "move": move,
                                "move_uci": move.uci(),
                                "move_san": self.board.san(move),
                                "eval_cp": move_eval_cp
                            })
                            print(f"      ✅ [ANALYZE_DEPTH] Added move {self.board.san(move)} with eval {move_eval_cp}")
                        else:
                            print(f"      ⚠️ [ANALYZE_DEPTH] Move eval CP is None, skipping")
                    except Exception as e:
                        print(f"      ❌ [ANALYZE_DEPTH] Error analyzing move {self.board.san(move)}: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
                
                # Sort by eval (best first) - highest eval is best for current side to move
                print(f"   📊 [ANALYZE_DEPTH] Move scores before sort: {[(m['move_san'], m['eval_cp']) for m in move_scores]}")
                move_scores.sort(key=lambda x: x["eval_cp"], reverse=True)
                print(f"   📊 [ANALYZE_DEPTH] Move scores after sort: {[(m['move_san'], m['eval_cp']) for m in move_scores]}")
                print(f"   📊 [ANALYZE_DEPTH] Total move_scores: {len(move_scores)}")
                
                # Update best_move, best_move_san, and best_move_eval_cp from analysis
                if move_scores:
                    best_from_analysis = move_scores[0]
                    best_move = best_from_analysis["move_uci"]
                    best_move_san = best_from_analysis["move_san"]
                    best_move_eval_cp = best_from_analysis["eval_cp"]
                    print(f"   ✅ [ANALYZE_DEPTH] Best move from top_2 analysis: {best_move_san} (eval: {best_move_eval_cp})")
                else:
                    print(f"   ⚠️ [ANALYZE_DEPTH] No move_scores available!")
                
                if len(move_scores) >= 2:
                    second_best = move_scores[1]
                    second_best_move = second_best["move_uci"]
                    second_best_move_san = second_best["move_san"]
                    second_best_move_eval_cp = second_best["eval_cp"]
                    print(f"   ✅ [ANALYZE_DEPTH] Second best move: {second_best_move_san} (eval: {second_best_move_eval_cp})")
                    
                    # Check if critical (cp loss > 50 between best and second best)
                    if best_move_eval_cp is not None and second_best_move_eval_cp is not None:
                        cp_loss = abs(best_move_eval_cp - second_best_move_eval_cp)
                        is_critical = cp_loss > 50
                        print(f"   📊 [ANALYZE_DEPTH] CP loss: {cp_loss}, is_critical: {is_critical}")
                        
                        # Check if winning (different signs)
                        if (best_move_eval_cp > 0 and second_best_move_eval_cp < 0) or \
                           (best_move_eval_cp < 0 and second_best_move_eval_cp > 0):
                            is_winning = True
                            print(f"   📊 [ANALYZE_DEPTH] is_winning: {is_winning}")
                elif move_scores:
                    # Only one move available, can't determine critical/winning
                    best_from_analysis = move_scores[0]
                    best_move_eval_cp = best_from_analysis["eval_cp"]
                    print(f"   ⚠️ [ANALYZE_DEPTH] Only one move available, can't determine critical/winning")
                else:
                    print(f"   ⚠️ [ANALYZE_DEPTH] No move_scores, skipping second best analysis")
            
            # Get top moves (analyze first 5 moves from PV) - for backward compatibility
            print(f"   🔍 [ANALYZE_DEPTH] Building top_moves from PV (first 5 moves)")
            top_moves = []
            temp_board_for_pv = self.board.copy()  # Use separate board for PV validation
            print(f"   📊 [ANALYZE_DEPTH] PV length: {len(pv)}, processing first {min(5, len(pv))} moves")
            for rank, move in enumerate(pv[:5]):
                print(f"   🔍 [ANALYZE_DEPTH] Processing top move {rank+1}/5: {move}, type: {type(move)}")
                # Verify move is legal BEFORE processing (using separate board)
                if move not in temp_board_for_pv.legal_moves:
                    print(f"   ⚠️ [ANALYZE_DEPTH] PV move {move} at rank {rank+1} not legal, stopping PV analysis")
                    print(f"      Board FEN: {temp_board_for_pv.fen()[:50]}...")
                    print(f"      Legal moves: {[temp_board_for_pv.san(m) for m in list(temp_board_for_pv.legal_moves)[:5]]}")
                    break  # Stop at first invalid move
                
                test_board = temp_board_for_pv.copy()
                test_board.push(move)
                try:
                    print(f"      🔍 [ANALYZE_DEPTH] Analyzing PV move {rank+1} at depth {max(1, depth - 2)}...")
                    if self.use_pool and self.engine_pool:
                        # Use engine pool
                        move_analysis = await self.engine_pool.analyze_single(
                            fen=test_board.fen(),
                            depth=max(1, depth - 2),
                            multipv=1
                        )
                        if move_analysis.get("success") and move_analysis.get("result"):
                            move_info = move_analysis["result"][0] if isinstance(move_analysis["result"], list) else move_analysis["result"]
                        else:
                            print(f"      ⚠️ [ANALYZE_DEPTH] Engine pool returned unsuccessful result for PV move {rank+1}")
                            move_info = {}
                    elif self.engine_queue:
                        # Use engine queue
                        move_info = await self.engine_queue.enqueue(
                            self.engine_queue.engine.analyse,
                            test_board,
                            chess.engine.Limit(depth=max(1, depth - 2))
                        )
                    else:
                        print(f"      ❌ [ANALYZE_DEPTH] Neither engine_pool nor engine_queue available for PV move analysis")
                        move_info = {}
                    
                    print(f"      ✅ [ANALYZE_DEPTH] Engine returned for PV move {rank+1}")
                    move_score = move_info.get("score")
                    print(f"      📊 [ANALYZE_DEPTH] Move score: {move_score}")
                    move_eval_cp = self._score_to_white_cp(move_score, fen=test_board.fen())
                    print(f"      📊 [ANALYZE_DEPTH] Move eval CP: {move_eval_cp}")
                    
                    # Move was already validated at line 1477 from temp_board_for_pv
                    # Get SAN from the position BEFORE the move was pushed
                    move_san = temp_board_for_pv.san(move)
                    move_eval_pawns = move_eval_cp / 100.0 if move_eval_cp is not None else None
                    top_moves.append({
                        "move": move_san,
                        "move_uci": move.uci(),
                        "eval": move_eval_pawns,
                        "eval_cp": move_eval_cp,  # Also include CP for consistency
                        "rank": rank + 1
                    })
                    print(f"      ✅ [ANALYZE_DEPTH] Added top move {rank+1}: {move_san} (eval: {move_eval_pawns})")
                    
                    # Update temp_board_for_pv for next iteration (push the move we just processed)
                    temp_board_for_pv.push(move)
                except Exception as e:
                    print(f"   ⚠️ [ANALYZE_DEPTH] Error analyzing PV move {move} at rank {rank+1}: {e}")
                    import traceback
                    traceback.print_exc()
                    # Still add the move but with no eval
                    try:
                        # Use temp_board_for_pv (before move was pushed) to get SAN
                        move_san = temp_board_for_pv.san(move)
                        top_moves.append({
                            "move": move_san,
                            "move_uci": move.uci(),
                            "eval": None,
                            "eval_cp": None,
                            "rank": rank + 1
                        })
                        print(f"      ⚠️ [ANALYZE_DEPTH] Added move {rank+1} with no eval: {move_san}")
                        # Update temp_board_for_pv for next iteration
                        temp_board_for_pv.push(move)
                    except Exception as parse_e:
                        # Even parsing the move failed, skip it
                        print(f"      ❌ [ANALYZE_DEPTH] Failed to parse move, skipping: {parse_e}")
                        # Still update board state for next iteration if move was valid
                        try:
                            temp_board_for_pv.push(move)
                        except:
                            pass
            
            print(f"   📊 [ANALYZE_DEPTH] Top moves built: {len(top_moves)} moves")
            for tm in top_moves:
                print(f"      - {tm.get('move')}: eval={tm.get('eval')}, eval_cp={tm.get('eval_cp')}")
            
            result = {
                "eval": eval_pawns,
                "best_move": best_move,
                "best_move_san": best_move_san,
                "best_move_eval_cp": best_move_eval_cp,
                "pv": pv,  # Full PV as Move objects
                "pv_san": pv_san,  # Full PV in SAN notation
                "top_moves": top_moves
            }
            
            # CRITICAL: Verify eval normalization before returning
            board_final_check = chess.Board(fen)
            print(f"   🔍 [EVAL_NORM] FINAL RESULT VERIFICATION:", flush=True)
            print(f"      - FEN: {fen}", flush=True)
            print(f"      - Side to move: {'WHITE' if board_final_check.turn == chess.WHITE else 'BLACK'}", flush=True)
            print(f"      - eval_pawns: {eval_pawns} (should be normalized to WHITE's perspective)", flush=True)
            
            print(f"   📊 [ANALYZE_DEPTH] Base result:")
            print(f"      - eval: {eval_pawns}")
            print(f"      - best_move: {best_move}")
            print(f"      - best_move_san: {best_move_san}")
            print(f"      - best_move_eval_cp: {best_move_eval_cp}")
            print(f"      - pv length: {len(pv)}")
            print(f"      - pv_san length: {len(pv_san)}")
            print(f"      - top_moves length: {len(top_moves)}")
            
            # Add top 2 analysis results if available
            if get_top_2 and depth >= 16:
                result.update({
                    "second_best_move": second_best_move,
                    "second_best_move_san": second_best_move_san,
                    "second_best_move_eval_cp": second_best_move_eval_cp,
                    "is_critical": is_critical,
                    "is_winning": is_winning
                })
                print(f"   📊 [ANALYZE_DEPTH] Added top_2 results:")
                print(f"      - second_best_move: {second_best_move}")
                print(f"      - second_best_move_san: {second_best_move_san}")
                print(f"      - second_best_move_eval_cp: {second_best_move_eval_cp}")
                print(f"      - is_critical: {is_critical}")
                print(f"      - is_winning: {is_winning}")
            
            print(f"   ✅ [ANALYZE_DEPTH] Returning result with keys: {list(result.keys())}")
            return result
        except Exception as e:
            print(f"   ❌ [ANALYZE_DEPTH] EXCEPTION CAUGHT: {e}")
            import traceback
            traceback.print_exc()
            return {
                "eval": None,
                "best_move": None,
                "best_move_san": None,
                "best_move_eval_cp": None,
                "pv": [],
                "pv_san": [],
                "top_moves": []
            }
    
    def _find_overestimated_moves(
        self,
        d16_result: Dict[str, Any],
        d2_result: Dict[str, Any]
    ) -> List[str]:
        """
        Compare D16 vs D2 results to find overestimated moves.
        Overestimated moves are D2 moves ranked above D16 best move.
        
        Args:
            d16_result: Result from _analyze_depth(fen, 16)
            d2_result: Result from _analyze_depth(fen, 2)
            
        Returns:
            List of overestimated move SANs
        """
        overestimated = []
        
        d16_best_move_san = d16_result.get("best_move_san")
        if not d16_best_move_san:
            return overestimated
        
        d2_top_moves = d2_result.get("top_moves", [])
        
        # Find rank of D16 best move in D2 results
        d16_rank_in_d2 = None
        for move_data in d2_top_moves:
            if move_data.get("move") == d16_best_move_san:
                d16_rank_in_d2 = move_data.get("rank")
                break
        
        # If D16 best move not found in D2 top moves, extend D2 analysis
        if d16_rank_in_d2 is None:
            # D16 best move is not in D2 top moves - all D2 moves are potentially overestimated
            # But we need to extend D2 to find it
            # For now, return all D2 moves as potentially overestimated
            return [move_data.get("move") for move_data in d2_top_moves if move_data.get("move")]
        
        # All moves ranked above D16 best in D2 are overestimated
        for move_data in d2_top_moves:
            move_rank = move_data.get("rank", 999)
            if move_rank < d16_rank_in_d2:
                move_san = move_data.get("move")
                if move_san:
                    overestimated.append(move_san)
        
        return overestimated
    
    async def investigate_with_dual_depth(
        self,
        fen: str,
        scope: str = "general_position",
        depth_16: int = 16,
        depth_2: int = 2,
        pgn_callback: Optional[Callable] = None,
        original_fen: Optional[str] = None,
        branching_limit: Optional[int] = None,
        max_pv_plies: int = 32,
        include_pgn: bool = True,
        pgn_max_chars: int = 0,
        branch_depth_limit: int = 5,
    ) -> InvestigationResult:
        """
        Enhanced investigation with dual-depth analysis and recursive branching.
        
        Args:
            fen: FEN string of position
            scope: "general_position" | "specific_move" | "piece_focus" | "tactical_scan"
            depth_16: Depth for ground truth analysis
            depth_2: Depth for shallow analysis
            
        Returns:
            InvestigationResult with exploration tree and PGN
        """
        # Suppress routine trace logs in non-debug mode (this function is extremely verbose).
        # IMPORTANT: do not read local `print` before assignment (Python treats it as local if we define it below).
        import builtins as _builtins
        _real_print = _builtins.print
        if not getattr(self, "debug", False):
            def print(*args, **kwargs):  # type: ignore
                try:
                    msg = " ".join(str(a) for a in args)
                    if msg.startswith(("   🔍", "   📊", "      🔍", "      📊", "   ✅", "      ✅")):
                        return None
                except Exception:
                    pass
                return _real_print(*args, **kwargs)

        print(f"   🔍 [INVESTIGATOR] Starting investigate_with_dual_depth for scope={scope}")
        
        # Some tags are "state tags": they describe a global condition and should NOT churn
        # just because the involved pieces moved squares. For these tags, we intentionally
        # ignore squares/pieces in the tag key so per-move deltas reflect real state changes.
        STABLE_INSTANCE_TAGS = {
            # Bishop pair is a side-level property; bishop square changes should not create gained/lost noise.
            "tag.bishop.pair",
        }
        
        # Step 2: Run Light Raw Analysis
        print(f"   🔍 [INVESTIGATOR] Step 2: Running Light Raw Analysis...")
        light_raw = self._cached_light_raw(fen)
        print(f"   ✅ [INVESTIGATOR] Step 2: Light Raw Analysis complete")
        
        # Note: Roles will be enhanced with PGN exploration data after Step 9
        
        # Speed: if depth_16 == depth_2, avoid running two identical engine analyses.
        # This is especially important when non-primary lines use D2 for both.
        if int(depth_16) == int(depth_2):
            print(f"   🔍 [INVESTIGATOR] Dual-depth shortcut: depth_16 == depth_2 == {int(depth_2)} (single analysis)")
            single = await self._analyze_depth(fen, int(depth_2), get_top_2=False)
            eval_val = single.get("eval")
            best_move_san = single.get("best_move_san")
            return InvestigationResult(
                light_raw_analysis=light_raw,
                eval_d16=eval_val,
                best_move_d16=best_move_san,
                best_move_d16_eval_cp=single.get("best_move_eval_cp"),
                eval_d2=eval_val,
                top_moves_d2=single.get("top_moves", []) or [],
                overestimated_moves=[],
                is_critical=False,
                is_winning=False,
                pgn_exploration="",  # keep empty; full tree/PGN exploration not meaningful at D2-only shortcut
            )

        # Step 3: D16 analysis (ground truth) - with top 2 moves for critical/winning detection
        print(f"   🔍 [INVESTIGATOR] Step 3: Running D16 analysis (get_top_2=True)...", flush=True)
        board_d16 = chess.Board(fen)
        print(f"   🔍 [EVAL_NORM] DUAL-DEPTH D16 ANALYSIS:", flush=True)
        print(f"      - FEN: {fen}", flush=True)
        print(f"      - Side to move: {'WHITE' if board_d16.turn == chess.WHITE else 'BLACK'}", flush=True)
        print(f"      - ⚠️ Stockfish will return eval from {'WHITE' if board_d16.turn == chess.WHITE else 'BLACK'}'s perspective", flush=True)
        print(f"      - ⚠️ _score_to_white_cp MUST normalize to WHITE's perspective!", flush=True)
        d16_result = await self._analyze_depth(fen, depth_16, get_top_2=True)
        print(f"   ✅ [INVESTIGATOR] Step 3: D16 analysis complete")
        eval_d16 = d16_result.get("eval")
        best_move_d16 = d16_result.get("best_move")
        best_move_d16_san = d16_result.get("best_move_san")
        best_move_d16_eval_cp = d16_result.get("best_move_eval_cp")
        second_best_move_d16 = d16_result.get("second_best_move")
        second_best_move_d16_san = d16_result.get("second_best_move_san")
        second_best_move_d16_eval_cp = d16_result.get("second_best_move_eval_cp")
        is_critical = d16_result.get("is_critical", False)
        is_winning = d16_result.get("is_winning", False)
        
        # Log D16 result normalization
        print(f"   🔍 [EVAL_NORM] D16 RESULT:", flush=True)
        print(f"      - eval_d16: {eval_d16} (should be normalized to WHITE's perspective)", flush=True)
        print(f"      - best_move_d16: {best_move_d16_san}", flush=True)
        print(f"      - best_move_d16_eval_cp: {best_move_d16_eval_cp}", flush=True)
        board_d16_check = chess.Board(fen)
        print(f"      - Side to move when D16 was calculated: {'WHITE' if board_d16_check.turn == chess.WHITE else 'BLACK'}", flush=True)
        if best_move_d16_eval_cp is not None:
            best_move_eval_pawns = best_move_d16_eval_cp / 100.0
            print(f"      - best_move_d16_eval (pawns): {best_move_eval_pawns}", flush=True)
            # Verify consistency: eval_d16 should match the position eval, not the move eval
            # Note: eval_d16 is position eval, best_move_eval is the eval after playing that move
            # They can differ, but if they're wildly different, it might indicate a normalization issue
            if eval_d16 is not None and abs(eval_d16 - best_move_eval_pawns) > 2.0:
                print(f"      - ⚠️ WARNING: Large difference between eval_d16 ({eval_d16}) and best_move_eval ({best_move_eval_pawns})", flush=True)
                print(f"         This might be normal if the best move significantly changes the position", flush=True)
        
        # NEW: Verbose D16 logging
        print(f"   📊 [INVESTIGATOR] D16 Analysis Results:")
        if best_move_d16_san:
            eval_str = f"{best_move_d16_eval_cp/100:+.2f}" if best_move_d16_eval_cp is not None else "N/A"
            print(f"      🎯 Best Move: {best_move_d16_san} (eval: {eval_str})")
            if second_best_move_d16_san:
                second_eval_str = f"{second_best_move_d16_eval_cp/100:+.2f}" if second_best_move_d16_eval_cp is not None else "N/A"
                print(f"      🥈 Second Best: {second_best_move_d16_san} (eval: {second_eval_str})")
            print(f"      📈 Position Eval: {eval_d16:+.2f}" if eval_d16 is not None else "      📈 Position Eval: N/A")
            print(f"      ⚠️ Critical: {is_critical}, Winning: {is_winning}")
            pv_full_check = d16_result.get("pv_san", [])
            if pv_full_check:
                print(f"      🔗 PV Sequence: {' '.join(pv_full_check[:5])} ({len(pv_full_check)} moves total)")
            else:
                print(f"      ⚠️ WARNING: No PV sequence found in D16 result!")
        else:
            print(f"      ❌ ERROR: No best move found in D16 analysis!")
            print(f"      🔍 D16 result keys: {list(d16_result.keys())}")
        
        # Step 4: D2 analysis (shallow)
        print(f"   🔍 [INVESTIGATOR] Step 4: Running D2 analysis...")
        d2_result = await self._analyze_depth(fen, depth_2)
        print(f"   ✅ [INVESTIGATOR] Step 4: D2 analysis complete")
        eval_d2 = d2_result.get("eval")
        top_moves_d2 = d2_result.get("top_moves", [])
        
        # NEW: Verbose D2 logging - list moves until D16 best move is found
        print(f"   📊 [INVESTIGATOR] D2 Analysis Results:")
        print(f"      📈 Position Eval: {eval_d2:+.2f}" if eval_d2 is not None else "      📈 Position Eval: N/A")
        if top_moves_d2:
            print(f"      📋 D2 Top Moves (showing until D16 best move found):")
            d16_found_in_d2 = False
            for idx, move_data in enumerate(top_moves_d2, 1):
                move_san = move_data.get("move", "?")
                eval_cp = move_data.get("eval_cp")
                eval_str = f"{eval_cp/100:+.2f}" if eval_cp is not None else "N/A"
                agreement = "✅ MATCHES D16" if move_san == best_move_d16_san else ""
                print(f"         {idx}. {move_san} (eval: {eval_str}) {agreement}")
                if move_san == best_move_d16_san:
                    d16_found_in_d2 = True
                    print(f"      ✅ D16 best move found at rank {idx} in D2 results")
                    break
            if not d16_found_in_d2 and best_move_d16_san:
                print(f"      ⚠️ WARNING: D16 best move ({best_move_d16_san}) NOT found in D2 top {len(top_moves_d2)} moves!")
                print(f"      📋 Full D2 top moves list ({len(top_moves_d2)} total):")
                for idx, move_data in enumerate(top_moves_d2, 1):
                    move_san = move_data.get("move", "?")
                    eval_cp = move_data.get("eval_cp")
                    eval_str = f"{eval_cp/100:+.2f}" if eval_cp is not None else "N/A"
                    print(f"         {idx}. {move_san} (eval: {eval_str})")
        else:
            print(f"      ❌ ERROR: No top moves found in D2 analysis!")
            print(f"      🔍 D2 result keys: {list(d2_result.keys())}")
        
        # Step 5: Extend D2 top moves until D16 best move appears
        # If D16 best not in D2 top moves, we need to extend
        d16_found = any(m.get("move") == best_move_d16_san for m in top_moves_d2)
        if not d16_found and best_move_d16_san:
            # Try to find D16 best in D2 by analyzing it specifically
            # For now, we'll use the top_moves_d2 as-is and find overestimated from there
            pass
        
        # Step 6: Identify overestimated moves
        print(f"   🔍 [INVESTIGATOR] Step 6: Finding overestimated moves...")
        overestimated_moves = self._find_overestimated_moves(d16_result, d2_result)
        print(f"   ✅ [INVESTIGATOR] Step 6: Found {len(overestimated_moves)} overestimated moves")
        if isinstance(branching_limit, int) and branching_limit > 0:
            overestimated_moves = overestimated_moves[: int(branching_limit)]

        # NEW: Verbose overestimated moves logging
        if overestimated_moves:
            print(f"   📋 [INVESTIGATOR] Overestimated Moves (will be explored as branches):")
            print(f"      D16 best move: {best_move_d16_san} (eval: {best_move_d16_eval_cp/100:+.2f})" if best_move_d16_san and best_move_d16_eval_cp is not None else f"      D16 best move: {best_move_d16_san}")
            print(f"      D2 best move: {d2_result.get('best_move_san', 'unknown')}")
            for idx, move_san in enumerate(overestimated_moves, 1):
                # Find this move in D2 results to show its eval
                d2_move_data = next((m for m in top_moves_d2 if m.get("move") == move_san), None)
                if d2_move_data:
                    eval_cp = d2_move_data.get("eval_cp")
                    eval_str = f"{eval_cp/100:+.2f}" if eval_cp is not None else "N/A"
                    rank = d2_move_data.get("rank", "?")
                    # Compare with D16 best move eval
                    if best_move_d16_eval_cp is not None and eval_cp is not None:
                        overestimate_amount = (eval_cp - best_move_d16_eval_cp) / 100.0
                        print(f"      {idx}. {move_san} (D2 rank: {rank}, D2 eval: {eval_str}, overestimates by: {overestimate_amount:+.2f})")
                    else:
                        print(f"      {idx}. {move_san} (D2 rank: {rank}, D2 eval: {eval_str})")
                else:
                    print(f"      {idx}. {move_san} (D2 eval: N/A - not found in D2 results)")
        else:
            print(f"   ℹ️ [INVESTIGATOR] No overestimated moves - D2 and D16 agree on best move")
            print(f"      D16 best: {best_move_d16_san}, D2 best: {d2_result.get('best_move_san', 'unknown')}")
        
        # Step 7: Initialize exploration tree
        print(f"   🔍 [INVESTIGATOR] Step 7: Initializing exploration tree...")
        pv_full = d16_result.get("pv_san", [])  # Get full PV sequence
        # Enforce invariant: PV must start with the D16 best move (SAN) if we have it.
        # Some engine bindings can return pv_san that doesn't align with best_move_san; downstream
        # evidence line + PGN anchoring assume they match.
        try:
            if isinstance(best_move_d16_san, str) and best_move_d16_san:
                if not isinstance(pv_full, list):
                    pv_full = []
                pv_full = [m for m in pv_full if isinstance(m, str)]
                if pv_full:
                    if pv_full[0] != best_move_d16_san:
                        pv_full = [best_move_d16_san] + [m for m in pv_full if m != best_move_d16_san]
                else:
                    pv_full = [best_move_d16_san]
        except Exception:
            pass
        try:
            max_pv_plies_i = int(max_pv_plies)
        except Exception:
            max_pv_plies_i = 32
        if max_pv_plies_i > 0 and isinstance(pv_full, list):
            pv_full = pv_full[:max_pv_plies_i]
        
        # NEW: Check if we have critical data for PGN building
        if not pv_full and not best_move_d16_san:
            print(f"   ❌ [INVESTIGATOR] ERROR: No PV sequence AND no best move from D16!")
            print(f"      This will result in an empty PGN. Continuing with available data...")
        elif not pv_full:
            print(f"   ⚠️ [INVESTIGATOR] WARNING: No PV sequence, will use best_move_d16 ({best_move_d16_san}) as fallback")
        elif not best_move_d16_san:
            print(f"   ⚠️ [INVESTIGATOR] WARNING: No best move from D16, but PV exists ({len(pv_full)} moves)")
        
        # Analyze threats at root position (spec requirement)
        root_threat_claim = await self._analyze_threat_at_position(fen, depth_16)
        if root_threat_claim:
            print(f"   ⚠️ [INVESTIGATOR] Root position has significant threat: {root_threat_claim.get('threat_significance_cp')}cp gap")
        
        # Analyze threats and branch along PV nodes (spec: at every node, branch at perspective side moves)
        pv_threat_claims = []
        pv_branches = []  # Branches from PV nodes
        original_side = chess.Board(fen).turn  # Perspective side
        
        if pv_full and len(pv_full) > 0:
            print(f"   🔍 [INVESTIGATOR] Analyzing threats and branching along PV ({len(pv_full)} moves)...")
            temp_board = chess.Board(fen)
            
            for move_idx, move_san in enumerate(pv_full):
                try:
                    # Get position BEFORE playing this move
                    current_fen = temp_board.fen()
                    
                    # Analyze threat at this position (spec: threat analysis at every node)
                    pv_threat = await self._analyze_threat_at_position(current_fen, depth_16)
                    if pv_threat:
                        pv_threat["pv_move_index"] = move_idx
                        pv_threat["pv_move_san"] = move_san
                        pv_threat_claims.append(pv_threat)
                        print(f"      ⚠️ Threat at PV node {move_idx+1} (before {move_san}): {pv_threat.get('threat_significance_cp')}cp gap")
                    
                    # Check if it's the perspective side's turn (spec: branch at every move of perspective side)
                    is_perspective_side = temp_board.turn == original_side
                    
                    # Branch if it's perspective side's turn (spec requirement: d2 for overestimated moves)
                    if is_perspective_side:
                        print(f"      🔍 [INVESTIGATOR] PV node {move_idx+1} (before {move_san}): perspective side's turn, checking for overestimated moves...")
                        # Analyze this position for overestimated moves (d2 vs d16)
                        pv_d16 = await self._analyze_depth(current_fen, depth_16, get_top_2=False)
                        pv_d2 = await self._analyze_depth(current_fen, depth_2)
                        pv_overestimated = self._find_overestimated_moves(pv_d16, pv_d2)
                        
                        if pv_overestimated:
                            print(f"         Found {len(pv_overestimated)} overestimated moves at PV node {move_idx+1}")
                            # Branch from this PV node (limit to first 2 overestimated moves to avoid explosion)
                            for over_move in pv_overestimated[:2]:
                                try:
                                    branch_board = chess.Board(current_fen)
                                    branch_move = branch_board.parse_san(over_move)
                                    if branch_move in branch_board.legal_moves:
                                        branch_board.push(branch_move)
                                        branch_fen = branch_board.fen()
                                        
                                        # Recursively explore this branch
                                        pv_branch = await self._explore_branch_recursive(
                                            branch_fen,
                                            eval_d16,  # Stop if eval drops below root by 15cp
                                            depth_16,
                                            depth_2,
                                            over_move,
                                            pgn_callback=pgn_callback,
                                            depth_limit=2,  # Limit depth for PV branches
                                            current_depth=0,
                                            perspective_side=original_side
                                        )
                                        pv_branch["pv_node_index"] = move_idx
                                        pv_branch["pv_node_move"] = move_san
                                        pv_branches.append(pv_branch)
                                except Exception as e:
                                    print(f"         ⚠️ Error branching from PV node {move_idx+1}: {e}")
                    
                    # Now play the PV move to continue to next node
                    move = temp_board.parse_san(move_san)
                    if move in temp_board.legal_moves:
                        temp_board.push(move)
                    else:
                        print(f"      ⚠️ PV move {move_san} not legal, stopping PV traversal")
                        break
                except Exception as e:
                    print(f"      ⚠️ Error at PV move {move_idx+1}: {e}")
                    break
        
        exploration_tree = {
            "position": fen,  # Current position (after move if called from investigate_move)
            "original_position": original_fen if original_fen else fen,  # Position before player's move (for PGN)
            "eval_d16": eval_d16,
            "best_move_d16": best_move_d16_san,
            "best_move_d16_eval_cp": best_move_d16_eval_cp,
            "pv_full": pv_full,  # Store full PV sequence
            "second_best_move_d16": second_best_move_d16_san,
            "second_best_move_d16_eval_cp": second_best_move_d16_eval_cp,
            "is_critical": is_critical,
            "is_winning": is_winning,
            "threat_tags": self._extract_tag_labels(light_raw.tags if light_raw else []),
            "threat_claim": root_threat_claim,  # Root threat claim (if significant)
            "pv_threat_claims": pv_threat_claims,  # Threats along PV
            "pv_branches": pv_branches,  # Branches from PV nodes (perspective-aware)
            "light_raw": light_raw.to_dict() if light_raw else {},
            "branches": []
        }
        
        # Step 8: Recursive branching on overestimated moves at root
        # Note: PV branching already done above (Step 7.5)
        print(f"   🔍 [INVESTIGATOR] Step 8: Starting recursive branching on {len(overestimated_moves)} root overestimated moves...")
        for idx, over_move in enumerate(overestimated_moves):
            print(f"   🔍 [INVESTIGATOR] Step 8: Exploring branch {idx+1}/{len(overestimated_moves)}: {over_move}")
            # Emit status update via callback
            if pgn_callback:
                pgn_callback({
                    "type": "status",
                    "message": f"Investigating: trying {over_move} (branch {idx+1}/{len(overestimated_moves)})",
                    "move_san": over_move,
                    "branch_number": idx + 1,
                    "total_branches": len(overestimated_moves)
                })
            # Play move
            self.board.set_fen(fen)
            try:
                move = self.board.parse_san(over_move)
                if move in self.board.legal_moves:
                    self.board.push(move)
                    new_fen = self.board.fen()
                    
                    # Emit callback for move exploration
                    if pgn_callback:
                        pgn_callback({
                            "type": "move_explored",
                            "move_san": over_move,
                            "fen": new_fen,
                            "eval_d16": eval_d16
                        })
                    
                    # Recursive call
                    try:
                        print(f"   🔍 [INVESTIGATOR] Step 8: Recursively exploring branch for {over_move}...")
                        # Determine perspective side from original position
                        original_board = chess.Board(fen)
                        perspective_side = original_board.turn
                        
                        branch_result = await self._explore_branch_recursive(
                            new_fen,
                            eval_d16,  # Original best eval (stop condition)
                            depth_16,
                            depth_2,
                            over_move,  # Move that led here
                            pgn_callback=pgn_callback,
                            depth_limit=int(branch_depth_limit),  # Limit recursion depth
                            current_depth=0,  # Start at depth 0
                            perspective_side=perspective_side  # Pass perspective for branching
                        )
                        print(f"   ✅ [INVESTIGATOR] Step 8: Branch exploration for {over_move} complete")
                        
                        # NEW: Verbose branch logging with agreement check
                        if branch_result:
                            is_stopped = branch_result.get("stopped", False)
                            stop_reason = branch_result.get("reason", "unknown")
                            branch_eval_d16 = branch_result.get("eval_d16")
                            branch_eval_d2 = branch_result.get("eval_d2")
                            branch_best = branch_result.get("best_move_d16")
                            original_eval = branch_result.get("original_eval_d16")
                            
                            if is_stopped:
                                print(f"      ⚠️ Branch {idx+1} STOPPED: {over_move}")
                                print(f"         Stop reason: {stop_reason}")
                                if branch_eval_d16 is not None:
                                    print(f"         D16 eval: {branch_eval_d16:+.2f}")
                                if branch_eval_d2 is not None:
                                    print(f"         D2 eval: {branch_eval_d2:+.2f}")
                                if original_eval is not None:
                                    print(f"         Original D16 eval: {original_eval:+.2f}")
                                    if branch_eval_d2 is not None:
                                        diff = branch_eval_d2 - original_eval
                                        print(f"         Eval change: {diff:+.2f} (D2 vs original)")
                                if branch_best:
                                    print(f"         Best move in branch: {branch_best}")
                                sub_branches = len(branch_result.get("branches", []))
                                print(f"         Sub-branches explored: {sub_branches}")
                            else:
                                print(f"      ✅ Branch {idx+1} complete: {over_move}")
                                if branch_eval_d16 is not None:
                                    print(f"         D16 eval: {branch_eval_d16:+.2f}")
                                if branch_eval_d2 is not None:
                                    print(f"         D2 eval: {branch_eval_d2:+.2f}")
                                if branch_best:
                                    print(f"         Best move: {branch_best}")
                                # Check agreement with root
                                if branch_eval_d16 is not None and eval_d16 is not None:
                                    diff = branch_eval_d16 - eval_d16
                                    agreement = "✅ AGREES" if abs(diff) < 0.1 else "❌ DISAGREES"
                                    print(f"         Agreement with root: {agreement} (diff: {diff:+.2f})")
                        else:
                            print(f"      ❌ Branch {idx+1} FAILED: {over_move} (no result returned)")
                        
                        exploration_tree["branches"].append(branch_result)
                    except Exception as branch_e:
                        print(f"   ❌ [INVESTIGATOR] Error exploring branch {over_move}: {branch_e}")
                        import traceback
                        traceback.print_exc()
                        # Continue with next branch
                    
                    # Emit callback for branch added
                    if pgn_callback:
                        pgn_callback({
                            "type": "branch_added",
                            "move_san": over_move,
                            "branch": branch_result
                        })
            except Exception:
                pass
        
        # Step 8 Complete: Branch Summary
        print(f"   📊 [INVESTIGATOR] Step 8 Complete: Branch Summary")
        branches_list = exploration_tree.get('branches', [])
        print(f"      - Total branches explored: {len(branches_list)}")
        for idx, branch in enumerate(branches_list, 1):
            move = branch.get('move_played', 'unknown')
            stopped = branch.get('stopped', False)
            sub_branches = len(branch.get('branches', []))
            eval_d16 = branch.get('eval_d16')
            eval_str = f"{eval_d16:+.2f}" if eval_d16 is not None else "N/A"
            print(f"      - Branch {idx}: {move} (stopped: {stopped}, sub-branches: {sub_branches}, eval: {eval_str})")
        
        # Step 9: Generate PGN with themes, tactics, commentary
        print(f"   🔍 [INVESTIGATOR] Step 9: Building exploration PGN...")
        pgn_exploration = ""
        if include_pgn:
            pgn_exploration = await self._build_exploration_pgn(exploration_tree, light_raw)
            try:
                if int(pgn_max_chars or 0) > 0 and isinstance(pgn_exploration, str) and len(pgn_exploration) > int(pgn_max_chars):
                    pgn_exploration = pgn_exploration[: int(pgn_max_chars)]
            except Exception:
                pass
        print(f"   ✅ [INVESTIGATOR] Step 9: PGN built ({len(pgn_exploration)} chars)")
        
        # Step 9.5: Enhance light_raw roles with PGN exploration data
        if pgn_exploration and light_raw:
            try:
                print(f"   🔍 [INVESTIGATOR] Step 9.5: Enhancing roles with PGN exploration data...")
                from role_detector import detect_all_piece_roles
                enhanced_roles = detect_all_piece_roles(
                    fen,
                    previous_fen=None,  # Could be enhanced to track previous FEN
                    pgn_exploration=pgn_exploration,
                    investigation_result=None  # Will be set below
                )
                light_raw.roles = enhanced_roles
                print(f"   ✅ [INVESTIGATOR] Step 9.5: Roles enhanced")
            except Exception as e:
                print(f"   ⚠️ [INVESTIGATOR] Error enhancing roles: {e}")
        
        # PGN Structure Analysis
        variation_count = pgn_exploration.count('(')  # Each variation starts with (
        print(f"   📊 [INVESTIGATOR] PGN Structure:")
        print(f"      - Total length: {len(pgn_exploration)} chars")
        print(f"      - Variations (branches): {variation_count}")
        print(f"      - Root PV moves: {len(pv_full)}")
        print(f"      - Branches in tree: {len(branches_list)}")
        if pv_full:
            print(f"      - Root PV sequence: {' '.join(pv_full[:5])}{'...' if len(pv_full) > 5 else ''}")
        
        # NEW: Check if PGN is empty and raise error
        if not pgn_exploration or len(pgn_exploration.strip()) < 100:
            # PGN should have at least headers + some content
            error_msg = f"ERROR: PGN exploration is empty or too short ({len(pgn_exploration)} chars). "
            error_msg += f"Root PV: {pv_full if pv_full else 'None'}, "
            error_msg += f"Best move: {best_move_d16_san if best_move_d16_san else 'None'}, "
            error_msg += f"Branches: {len(exploration_tree.get('branches', []))}"
            print(f"   ❌ [INVESTIGATOR] {error_msg}")
            # Store error in exploration_tree for downstream handling
            exploration_tree["pgn_error"] = error_msg
            # Continue with available data - don't crash
        else:
            # Check if PGN actually contains moves (not just headers)
            if "*" in pgn_exploration and pgn_exploration.count("*") == 1 and len(pv_full) == 0:
                error_msg = f"WARNING: PGN contains no moves (only starting position). "
                error_msg += f"PV empty: {not pv_full}, Best move: {best_move_d16_san if best_move_d16_san else 'None'}"
                print(f"   ⚠️ [INVESTIGATOR] {error_msg}")
                exploration_tree["pgn_warning"] = error_msg
        
        # Extract themes identified
        themes_identified = light_raw.top_themes if light_raw else []
        
        # Generate commentary
        print(f"   🔍 [INVESTIGATOR] Generating commentary...")
        commentary = self._generate_commentary(exploration_tree, light_raw)
        
        # Build evidence_index (deterministic extraction from structured analysis)
        evidence_index = self._build_evidence_index(
            pv_after_move=pv_full if pv_full else None,  # Root PV (SAN) for anchoring evidence to best line
            exploration_tree=exploration_tree
        )
        
        print(f"   ✅ [INVESTIGATOR] investigate_with_dual_depth complete! Returning InvestigationResult")
        investigation_result = InvestigationResult(
            eval_before=eval_d16,
            best_move=best_move_d16,
            pv_after_move=pv_full[:10] if pv_full else [],
            eval_d16=eval_d16,
            # Expose SAN for UI/narrative (avoid UCI like "f3g5" leaking into claims)
            best_move_d16=best_move_d16_san,
            best_move_d16_eval_cp=best_move_d16_eval_cp,
            second_best_move_d16=second_best_move_d16_san,
            second_best_move_d16_eval_cp=second_best_move_d16_eval_cp,
            is_critical=is_critical,
            is_winning=is_winning,
            eval_d2=eval_d2,
            top_moves_d2=top_moves_d2,
            overestimated_moves=overestimated_moves,
            light_raw_analysis=light_raw,
            exploration_tree=exploration_tree,
            pgn_exploration=pgn_exploration,
            themes_identified=themes_identified,
            commentary=commentary,
            evidence_index=evidence_index,  # NEW: Structured evidence lines
            game_phase=self._classify_game_phase()
        )

        # NEW: Precompute structured deltas + net changes for a canonical evidence line (single source of truth).
        try:
            starting_fen = exploration_tree.get("original_position") or exploration_tree.get("position") or fen
            player_move = None  # investigate_with_dual_depth may be called from move or position paths
            # If this was called from investigate_move, original_fen will be the pre-move position and
            # the user's move is not stored here; we still can build a line from pv_after_move alone.
            pv_moves = investigation_result.pv_after_move or []
            # Build an evidence mainline from PV (default: keep reasonably short but not 1-ply).
            # This is used for UI + downstream grounding; keep bounded for compute and payload size.
            try:
                max_evidence_plies = int(os.getenv("INVESTIGATOR_EVIDENCE_MAX_PLIES", "8"))
            except Exception:
                max_evidence_plies = 8
            if max_evidence_plies <= 0:
                max_evidence_plies = 8
            evidence_moves = [m for m in pv_moves if isinstance(m, str)][:max_evidence_plies]
            evidence_pgn_line = " ".join(evidence_moves) if evidence_moves else None

            if starting_fen and evidence_moves:
                per_move, tg, tl, rg, rl, tg_struct, tl_struct = self._compute_per_move_deltas_for_line(starting_fen, evidence_moves)
                investigation_result.evidence_starting_fen = starting_fen
                investigation_result.evidence_pgn_line = evidence_pgn_line
                investigation_result.evidence_main_line_moves = evidence_moves
                investigation_result.evidence_per_move_deltas = per_move
                # Preserve full/raw tags (for deep analysis)
                investigation_result.evidence_tags_gained_net_raw = list(tg or [])
                investigation_result.evidence_tags_lost_net_raw = list(tl or [])
                # Filter clutter from public net lists
                _clutter_prefixes = ("tag.diagonal.", "tag.key.", "tag.color.hole.")
                investigation_result.evidence_tags_gained_net = [t for t in (tg or []) if not any(str(t).startswith(p) for p in _clutter_prefixes)]
                investigation_result.evidence_tags_lost_net = [t for t in (tl or []) if not any(str(t).startswith(p) for p in _clutter_prefixes)]
                investigation_result.evidence_tags_gained_net_structured = tg_struct
                investigation_result.evidence_tags_lost_net_structured = tl_struct
                investigation_result.evidence_roles_gained_net = rg
                investigation_result.evidence_roles_lost_net = rl

                # NEW: evidence eval decomposition (start→end along the evidence line)
                breakdown = await self._compute_evidence_eval_breakdown(
                    starting_fen=starting_fen,
                    evidence_moves=evidence_moves,
                    eval_start_pawns=investigation_result.eval_before,
                    end_eval_depth=6
                )
                investigation_result.evidence_end_fen = breakdown.get("end_fen")
                investigation_result.evidence_eval_start = breakdown.get("eval_start")
                investigation_result.evidence_eval_end = breakdown.get("eval_end")
                investigation_result.evidence_eval_delta = breakdown.get("eval_delta")
                investigation_result.evidence_material_start = breakdown.get("material_start")
                investigation_result.evidence_material_end = breakdown.get("material_end")
                investigation_result.evidence_positional_start = breakdown.get("positional_start")
                investigation_result.evidence_positional_end = breakdown.get("positional_end")

                # NEW: per-move FEN + eval/material/positional series for SAN->words narration
                try:
                    investigation_result.evidence_per_move_stats = await self._compute_evidence_per_move_stats(
                        starting_fen=starting_fen,
                        evidence_per_move_deltas=investigation_result.evidence_per_move_deltas,
                        eval_start_pawns=investigation_result.evidence_eval_start,
                        depth=6,
                        max_plies=16,
                    )
                except Exception:
                    investigation_result.evidence_per_move_stats = []
        except Exception as e:
            print(f"   ⚠️ [INVESTIGATOR] Failed to compute structured evidence deltas: {e}")
        
        # Final enhancement: recompute roles with full investigation_result context
        if pgn_exploration and light_raw:
            try:
                print(f"   🔍 [INVESTIGATOR] Final role enhancement with investigation_result context...")
                from role_detector import detect_all_piece_roles
                final_roles = detect_all_piece_roles(
                    fen,
                    previous_fen=None,
                    pgn_exploration=pgn_exploration,
                    investigation_result=investigation_result
                )
                light_raw.roles = final_roles
                print(f"   ✅ [INVESTIGATOR] Final roles enhanced")
            except Exception as e:
                print(f"   ⚠️ [INVESTIGATOR] Error in final role enhancement: {e}")
        
        return investigation_result
    
    def _build_evidence_index(
        self,
        pv_after_move: Optional[List[str]] = None,
        exploration_tree: Optional[Dict[str, Any]] = None
    ) -> List[EvidenceLine]:
        """
        Deterministically extract evidence lines from structured analysis output.
        Generic, position-agnostic.
        
        Priority:
        1. Principal variations from exploration_tree
        2. PV sequences from pv_after_move
        
        Args:
            pv_after_move: PV sequence after move (if available)
            exploration_tree: Exploration tree with pv_full sequences
        
        Returns:
            List of EvidenceLine objects (2-4 plies each)
        """
        evidence_lines = []
        
        # Priority 1: Extract PV sequences from exploration_tree
        if exploration_tree:
            def extract_pv_from_tree(tree_node: Dict[str, Any]) -> List[List[str]]:
                """Recursively extract all pv_full sequences from tree"""
                pv_sequences = []
                if isinstance(tree_node, dict):
                    if "pv_full" in tree_node and tree_node["pv_full"]:
                        pv_seq = tree_node["pv_full"][:4]  # Max 4 plies
                        if len(pv_seq) >= 2:
                            pv_sequences.append(pv_seq)
                    # Recurse into children
                    for key, value in tree_node.items():
                        if isinstance(value, (dict, list)):
                            if isinstance(value, dict):
                                pv_sequences.extend(extract_pv_from_tree(value))
                            elif isinstance(value, list):
                                for item in value:
                                    if isinstance(item, dict):
                                        pv_sequences.extend(extract_pv_from_tree(item))
                return pv_sequences
            
            pv_sequences = extract_pv_from_tree(exploration_tree)
            for pv_seq in pv_sequences[:5]:  # Limit to first 5 PV sequences
                evidence_lines.append(EvidenceLine(
                    moves=pv_seq,
                    source="pv",
                    context="exploration_tree"
                ))
        
        # Priority 2: Add PV from pv_after_move
        if pv_after_move and len(pv_after_move) >= 2:
            evidence_lines.append(EvidenceLine(
                moves=pv_after_move[:4],  # Max 4 plies
                source="pv",
                context="after_move"
            ))
        
        return evidence_lines

    def _compute_per_move_deltas_for_line(
        self,
        starting_fen: str,
        moves_san: List[str]
    ) -> Tuple[
        List[Dict[str, Any]],
        List[str],
        List[str],
        List[str],
        List[str],
        List[Dict[str, Any]],
        List[Dict[str, Any]],
    ]:
        """
        Compute per-move tag/role deltas and final net deltas for a concrete SAN line.
        This is used to avoid downstream regex parsing of pgn_exploration.
        """
        from light_raw_analyzer import compute_light_raw_analysis

        # Some tags are "state tags": they describe a global condition and should NOT churn
        # just because involved pieces moved squares. For these, we intentionally ignore
        # squares/pieces in the tag instance key so per-move deltas reflect real state changes.
        STABLE_INSTANCE_TAGS = {
            # Bishop pair is a side-level property; bishop square changes should not create gained/lost noise.
            "tag.bishop.pair",
        }

        def _normalize_tag(t: Any) -> Dict[str, Any]:
            """
            Normalize tag objects so downstream can key+group consistently.
            We preserve original fields but ensure tag_name/side/squares/pieces/details exist.
            """
            if isinstance(t, dict):
                tag = dict(t)
            else:
                tag = {"tag_name": str(t)}

            tag_name = tag.get("tag_name") or tag.get("tag") or tag.get("name") or ""
            tag["tag_name"] = str(tag_name)

            # Normalize squares (some older tags use "square")
            squares = tag.get("squares", None)
            if squares is None:
                sq = tag.get("square", None)
                squares = [sq] if sq else []
            if not isinstance(squares, list):
                squares = [squares]
            tag["squares"] = [str(s) for s in squares if s]

            pieces = tag.get("pieces", None)
            if pieces is None:
                pieces = []
            if not isinstance(pieces, list):
                pieces = [pieces]
            tag["pieces"] = [str(p) for p in pieces if p]

            if "details" not in tag or tag["details"] is None:
                tag["details"] = {}

            # side is optional but helpful for grouping
            if "side" not in tag:
                tag["side"] = None

            return tag

        def _tag_key(tag: Dict[str, Any]) -> str:
            """
            Stable identifier for a tag instance (keeps per-square/per-piece instances distinct).
            """
            tn = (tag.get("tag_name") or "").strip()
            side = (tag.get("side") or "").strip()
            if tn in STABLE_INSTANCE_TAGS:
                return f"{tn}|{side}"
            squares = ",".join(sorted([s for s in (tag.get("squares") or []) if s]))
            pieces = ",".join(sorted([p for p in (tag.get("pieces") or []) if p]))
            return f"{tn}|{side}|{squares}|{pieces}"

        def _tag_names(light_raw_obj) -> List[str]:
            """
            Backwards-compatible tag list for net changes (strings only).
            NOTE: this collapses per-square instances; we keep structured lists separately.
            """
            if not light_raw_obj or not getattr(light_raw_obj, "tags", None):
                return []
            out: List[str] = []
            for t in light_raw_obj.tags:
                if isinstance(t, dict):
                    out.append(t.get("tag_name", t.get("tag", "")))
                else:
                    out.append(str(t))
            return [x for x in out if x]

        def _tag_map(light_raw_obj) -> Dict[str, Dict[str, Any]]:
            """
            Map tag_key -> normalized tag dict (keeps instance-level detail).
            """
            if not light_raw_obj or not getattr(light_raw_obj, "tags", None):
                return {}
            m: Dict[str, Dict[str, Any]] = {}
            for t in light_raw_obj.tags:
                nt = _normalize_tag(t)
                k = _tag_key(nt)
                # Keep first occurrence for determinism
                if k not in m:
                    m[k] = nt
            return m

        def _role_set(light_raw_obj) -> set:
            roles = getattr(light_raw_obj, "roles", None) if light_raw_obj else None
            out = set()
            if isinstance(roles, dict):
                for piece_id, role_list in roles.items():
                    if not role_list:
                        continue
                    for r in role_list:
                        out.add(f"{piece_id}:{r}")
            return out

        board = chess.Board()
        board.set_fen(starting_fen)

        before_raw = compute_light_raw_analysis(starting_fen)
        before_tags = set(_tag_names(before_raw))
        before_roles = _role_set(before_raw)
        before_tag_map = _tag_map(before_raw)

        per_move: List[Dict[str, Any]] = []
        # Use counting-based net (cancels out gained vs lost across the sequence)
        tags_gained_counts: Dict[str, int] = {}
        tags_lost_counts: Dict[str, int] = {}
        roles_gained_counts: Dict[str, int] = {}
        roles_lost_counts: Dict[str, int] = {}
        tags_gained_struct_counts: Dict[str, int] = {}
        tags_lost_struct_counts: Dict[str, int] = {}
        # Keep representative tag objects for keys
        tag_key_to_obj: Dict[str, Dict[str, Any]] = dict(before_tag_map)

        for idx, san in enumerate(moves_san):
            if not san:
                continue
            try:
                move = board.parse_san(san)
                if move not in board.legal_moves:
                    # Skip illegal moves (line might include moves already applied upstream)
                    continue
                fen_before = board.fen()
                board.push(move)
                fen_after = board.fen()
                after_raw = compute_light_raw_analysis(board.fen(), previous_fen=fen_before if idx == 0 else None)
                after_tags = set(_tag_names(after_raw))
                after_roles = _role_set(after_raw)
                after_tag_map = _tag_map(after_raw)

                # ------------------------------------------------------------------
                # OVERWORKED → UNDEFENDED PROPAGATION (evidence-friendly, deterministic)
                #
                # LightRawAnalysis does not run the full threat detector (perf reasons),
                # but for "overworked" explanations we want the causal companion signal:
                # if an overworked defender is removed/deflected and a defended piece
                # becomes attacked with zero defenders, emit tag.threat.capture.undefended.
                #
                # Implementation strategy:
                # - If a tag.piece.overworked.* instance exists in BEFORE but not AFTER,
                #   read its defended_pieces squares from the BEFORE tag object.
                # - On the AFTER board, for each such square, if the piece still exists,
                #   is attacked by the opponent, and has zero defenders, inject a
                #   synthetic threat tag instance into AFTER tags/maps.
                # ------------------------------------------------------------------
                try:
                    # Gather overworked instances from BEFORE only (instance-level)
                    before_overworked: List[Dict[str, Any]] = []
                    for _k, _t in (before_tag_map or {}).items():
                        tn = str((_t or {}).get("tag_name") or "")
                        if tn.startswith("tag.piece.overworked."):
                            before_overworked.append(_t)

                    if before_overworked:
                        # Determine which overworked instances are LOST in the after state.
                        after_overworked_keys = set(
                            k for k, t in (after_tag_map or {}).items()
                            if str((t or {}).get("tag_name") or "").startswith("tag.piece.overworked.")
                        )
                        # LOST = before_overworked whose key isn't present in after_overworked_keys.
                        for k_before, t_before in (before_tag_map or {}).items():
                            tn = str((t_before or {}).get("tag_name") or "")
                            if not tn.startswith("tag.piece.overworked."):
                                continue
                            if k_before in after_overworked_keys:
                                continue  # still overworked; no "exploit" resolution on this ply

                            side = str((t_before or {}).get("side") or "").strip()
                            if side not in ("white", "black"):
                                continue
                            defender_color = chess.WHITE if side == "white" else chess.BLACK
                            attacker_color = (not defender_color)
                            attacker_side = "white" if attacker_color == chess.WHITE else "black"

                            defended = (t_before or {}).get("defended_pieces") or []
                            if not isinstance(defended, list):
                                continue

                            # For each defended piece square, check "attacked and undefended" AFTER.
                            for dp in defended:
                                if not isinstance(dp, dict):
                                    continue
                                sq_name = dp.get("square")
                                if not isinstance(sq_name, str) or not sq_name:
                                    continue
                                try:
                                    sq_idx = chess.parse_square(sq_name)
                                except Exception:
                                    continue
                                piece = board.piece_at(sq_idx)
                                if not piece:
                                    continue
                                if piece.color != defender_color:
                                    continue
                                # Do not emit "capture undefended" threats against the king.
                                # (King "capture" isn't a legal threat; check/mate is handled elsewhere.)
                                if piece.piece_type == chess.KING:
                                    continue

                                # Undefended + attacked means attacker has a direct capture threat.
                                if board.is_attacked_by(attacker_color, sq_idx) and len(board.attackers(defender_color, sq_idx)) == 0:
                                    # Build a threat tag instance compatible with tag_detector.aggregate_all_tags conventions.
                                    piece_names = {
                                        chess.PAWN: "Pawn",
                                        chess.KNIGHT: "Knight",
                                        chess.BISHOP: "Bishop",
                                        chess.ROOK: "Rook",
                                        chess.QUEEN: "Queen",
                                        chess.KING: "King",
                                    }
                                    attacker_details = []
                                    for atk_sq in board.attackers(attacker_color, sq_idx):
                                        atk_piece = board.piece_at(atk_sq)
                                        if atk_piece:
                                            attacker_details.append({
                                                "square": chess.square_name(atk_sq),
                                                "piece": atk_piece.symbol(),
                                                "piece_name": piece_names.get(atk_piece.piece_type, "Piece"),
                                            })

                                    synth = _normalize_tag({
                                        "tag_name": "tag.threat.capture.undefended",
                                        "side": attacker_side,
                                        # Ensure instance-key uniqueness.
                                        "squares": [sq_name],
                                        "pieces": [f"{piece.symbol()}{sq_name}"],
                                        # Preserve threat_detector-style payload too.
                                        "target_square": sq_name,
                                        "target_piece": piece.symbol(),
                                        "target_piece_name": piece_names.get(piece.piece_type, "Piece"),
                                        "attackers": [chess.square_name(s) for s in board.attackers(attacker_color, sq_idx)],
                                        "attacker_pieces": attacker_details,
                                    })
                                    sk = _tag_key(synth)
                                    if sk not in after_tag_map:
                                        after_tag_map[sk] = synth
                                        after_tags.add("tag.threat.capture.undefended")
                                        tag_key_to_obj[sk] = synth
                except Exception:
                    # Non-fatal: this is an interpretability enhancement only.
                    pass

                gained_tags = sorted(list(after_tags - before_tags))
                lost_tags = sorted(list(before_tags - after_tags))
                gained_roles = sorted(list(after_roles - before_roles))
                lost_roles = sorted(list(before_roles - after_roles))

                # Structured tag deltas (instance-level)
                before_keys = set(before_tag_map.keys())
                after_keys = set(after_tag_map.keys())
                gained_tag_keys = sorted(list(after_keys - before_keys))
                lost_tag_keys = sorted(list(before_keys - after_keys))
                gained_tags_structured = [after_tag_map[k] for k in gained_tag_keys if k in after_tag_map]
                lost_tags_structured = [before_tag_map[k] for k in lost_tag_keys if k in before_tag_map]

                for k in gained_tag_keys:
                    if k in after_tag_map:
                        tag_key_to_obj[k] = after_tag_map[k]
                for k in lost_tag_keys:
                    if k in before_tag_map:
                        tag_key_to_obj[k] = before_tag_map[k]

                per_move.append({
                    "ply": idx + 1,
                    "move": san,
                    "fen_before": fen_before,
                    "fen_after": fen_after,
                    "tags_gained": gained_tags,
                    "tags_lost": lost_tags,
                    "tags_gained_structured": gained_tags_structured,
                    "tags_lost_structured": lost_tags_structured,
                    "roles_gained": gained_roles,
                    "roles_lost": lost_roles,
                })

                for t in gained_tags:
                    tags_gained_counts[t] = tags_gained_counts.get(t, 0) + 1
                    if t in tags_lost_counts:
                        tags_lost_counts[t] -= 1
                        if tags_lost_counts[t] <= 0:
                            del tags_lost_counts[t]
                for t in lost_tags:
                    tags_lost_counts[t] = tags_lost_counts.get(t, 0) + 1
                    if t in tags_gained_counts:
                        tags_gained_counts[t] -= 1
                        if tags_gained_counts[t] <= 0:
                            del tags_gained_counts[t]

                # Structured net accounting (instance-level)
                for k in gained_tag_keys:
                    tags_gained_struct_counts[k] = tags_gained_struct_counts.get(k, 0) + 1
                    if k in tags_lost_struct_counts:
                        tags_lost_struct_counts[k] -= 1
                        if tags_lost_struct_counts[k] <= 0:
                            del tags_lost_struct_counts[k]
                for k in lost_tag_keys:
                    tags_lost_struct_counts[k] = tags_lost_struct_counts.get(k, 0) + 1
                    if k in tags_gained_struct_counts:
                        tags_gained_struct_counts[k] -= 1
                        if tags_gained_struct_counts[k] <= 0:
                            del tags_gained_struct_counts[k]

                for r in gained_roles:
                    roles_gained_counts[r] = roles_gained_counts.get(r, 0) + 1
                    if r in roles_lost_counts:
                        roles_lost_counts[r] -= 1
                        if roles_lost_counts[r] <= 0:
                            del roles_lost_counts[r]
                for r in lost_roles:
                    roles_lost_counts[r] = roles_lost_counts.get(r, 0) + 1
                    if r in roles_gained_counts:
                        roles_gained_counts[r] -= 1
                        if roles_gained_counts[r] <= 0:
                            del roles_gained_counts[r]

                before_tags = after_tags
                before_roles = after_roles
                before_tag_map = after_tag_map
            except Exception:
                continue

        tags_gained_net = [t for t, c in tags_gained_counts.items() if c > 0]
        tags_lost_net = [t for t, c in tags_lost_counts.items() if c > 0]
        roles_gained_net = [r for r, c in roles_gained_counts.items() if c > 0]
        roles_lost_net = [r for r, c in roles_lost_counts.items() if c > 0]
        tags_gained_net_structured = [
            tag_key_to_obj[k] for k, c in tags_gained_struct_counts.items() if c > 0 and k in tag_key_to_obj
        ]
        tags_lost_net_structured = [
            tag_key_to_obj[k] for k, c in tags_lost_struct_counts.items() if c > 0 and k in tag_key_to_obj
        ]

        # ENHANCEMENT: Extract tag names from structured deltas to catch instance changes
        # This ensures tags that change their squares/pieces (e.g., undeveloped.knight moving from g1 to b1)
        # are still shown as lost/gained in the string-based net changes
        # 
        # Key insight: When a tag instance changes (e.g., undeveloped.knight from g1 to b1), we want to show:
        # - The old instance as LOST (knight on g1 was developed)
        # - Even if a new instance is GAINED (knight on b1 is still undeveloped)
        # This gives users visibility into what actually changed, not just net effect
        
        for tag_obj in tags_lost_net_structured:
            if not isinstance(tag_obj, dict):
                continue
            tag_name = tag_obj.get("tag_name")
            if not tag_name:
                continue
            # Extract squares from the lost tag instance
            lost_squares = set(tag_obj.get("squares", []))
            
            # Check if this tag_name exists in gained with different squares/pieces
            gained_with_same_name_different_squares = False
            for gained_tag in tags_gained_net_structured:
                if not isinstance(gained_tag, dict):
                    continue
                if gained_tag.get("tag_name") == tag_name:
                    gained_squares = set(gained_tag.get("squares", []))
                    # If squares are different, it's a change (not just a net cancellation)
                    if lost_squares != gained_squares:
                        gained_with_same_name_different_squares = True
                        break
            
            # Add to string-based lost list if not already there
            # This catches cases where tag.undeveloped.knight changes from g1 to b1 (or disappears)
            if tag_name not in tags_lost_net:
                tags_lost_net.append(tag_name)
                # Update counts to reflect this loss
                if tag_name not in tags_lost_counts:
                    tags_lost_counts[tag_name] = 0
                tags_lost_counts[tag_name] += 1
                # Only cancel out if it was gained with the SAME squares (true net cancellation)
                # If squares differ, keep both lost and gained to show the change
                if not gained_with_same_name_different_squares and tag_name in tags_gained_counts:
                    tags_gained_counts[tag_name] -= 1
                    if tags_gained_counts[tag_name] <= 0:
                        del tags_gained_counts[tag_name]
                        if tag_name in tags_gained_net:
                            tags_gained_net.remove(tag_name)

        for tag_obj in tags_gained_net_structured:
            if not isinstance(tag_obj, dict):
                continue
            tag_name = tag_obj.get("tag_name")
            if not tag_name:
                continue
            # Extract squares from the gained tag instance
            gained_squares = set(tag_obj.get("squares", []))
            
            # Check if this tag_name exists in lost with different squares/pieces
            lost_with_same_name_different_squares = False
            for lost_tag in tags_lost_net_structured:
                if not isinstance(lost_tag, dict):
                    continue
                if lost_tag.get("tag_name") == tag_name:
                    lost_squares = set(lost_tag.get("squares", []))
                    # If squares are different, it's a change (not just a net cancellation)
                    if lost_squares != gained_squares:
                        lost_with_same_name_different_squares = True
                        break
            
            # Add to string-based gained list if not already there
            if tag_name not in tags_gained_net:
                tags_gained_net.append(tag_name)
                # Update counts to reflect this gain
                if tag_name not in tags_gained_counts:
                    tags_gained_counts[tag_name] = 0
                tags_gained_counts[tag_name] += 1
                # Only cancel out if it was lost with the SAME squares (true net cancellation)
                # If squares differ, keep both lost and gained to show the change
                if not lost_with_same_name_different_squares and tag_name in tags_lost_counts:
                    tags_lost_counts[tag_name] -= 1
                    if tags_lost_counts[tag_name] <= 0:
                        del tags_lost_counts[tag_name]
                        if tag_name in tags_lost_net:
                            tags_lost_net.remove(tag_name)

        # Recompute final lists after merging structured deltas
        tags_gained_net = [t for t, c in tags_gained_counts.items() if c > 0]
        tags_lost_net = [t for t, c in tags_lost_counts.items() if c > 0]

        return (
            per_move,
            tags_gained_net,
            tags_lost_net,
            roles_gained_net,
            roles_lost_net,
            tags_gained_net_structured,
            tags_lost_net_structured,
        )

    def _material_balance_pawns_from_fen(self, fen: str) -> Optional[float]:
        """Material balance in pawns (+ for White), using the shared material_calculator."""
        try:
            from material_calculator import calculate_material_balance
            b = chess.Board(fen)
            return calculate_material_balance(b) / 100.0
        except Exception:
            return None

    def _apply_san_line_get_end_fen(self, starting_fen: str, moves_san: List[str]) -> Optional[str]:
        """Apply SAN moves from starting_fen and return resulting FEN (or None if illegal)."""
        try:
            b = chess.Board(starting_fen)
            for san in moves_san:
                if not san:
                    continue
                m = b.parse_san(san)
                if m not in b.legal_moves:
                    return None
                b.push(m)
            return b.fen()
        except Exception:
            return None

    async def _compute_evidence_eval_breakdown(
        self,
        *,
        starting_fen: str,
        evidence_moves: List[str],
        eval_start_pawns: Optional[float],
        end_eval_depth: int = 6
    ) -> Dict[str, Any]:
        """
        Compute eval/material/positional start→end for the evidence line.
        All values are normalized to White (positive = good for White).
        """
        end_fen = self._apply_san_line_get_end_fen(starting_fen, evidence_moves)

        material_start = self._material_balance_pawns_from_fen(starting_fen) if starting_fen else None
        positional_start = (eval_start_pawns - material_start) if (eval_start_pawns is not None and material_start is not None) else None

        eval_end = None
        material_end = None
        positional_end = None
        eval_delta = None

        if end_fen:
            try:
                end_analysis = await self._analyze_depth(end_fen, depth=end_eval_depth, get_top_2=False)
                eval_end = end_analysis.get("eval")
            except Exception:
                eval_end = None
            material_end = self._material_balance_pawns_from_fen(end_fen)
            positional_end = (eval_end - material_end) if (eval_end is not None and material_end is not None) else None
            eval_delta = (eval_end - eval_start_pawns) if (eval_end is not None and eval_start_pawns is not None) else None

        return {
            "end_fen": end_fen,
            "eval_start": eval_start_pawns,
            "eval_end": eval_end,
            "eval_delta": eval_delta,
            "material_start": material_start,
            "material_end": material_end,
            "positional_start": positional_start,
            "positional_end": positional_end,
        }

    async def _compute_evidence_per_move_stats(
        self,
        *,
        starting_fen: str,
        evidence_per_move_deltas: List[Dict[str, Any]],
        eval_start_pawns: Optional[float],
        depth: int = 6,
        max_plies: int = 16,
    ) -> List[Dict[str, Any]]:
        """
        Compute a per-move series for the evidence line so an LLM can narrate SAN->words
        with correct piece naming (via FENs) and quantitative context (eval/material/positional).

        Output entries (one per ply/move):
        - ply, move_san
        - fen_before, fen_after
        - eval_before/after (pawns, + for White)
        - material_before/after (pawns, + for White)
        - positional_before/after (= eval - material)
        - deltas (after - before)
        """
        if not starting_fen or not evidence_per_move_deltas:
            return []

        # Cap for safety (avoid huge time cost if someone requests a long witness line)
        deltas = [d for d in evidence_per_move_deltas if isinstance(d, dict)][:max_plies]
        if not deltas:
            return []

        # Collect a canonical list of fens for evaluation: start + after each ply
        fens: List[str] = [starting_fen]
        for d in deltas:
            fa = d.get("fen_after")
            if isinstance(fa, str) and fa:
                fens.append(fa)
            else:
                # If missing, we stop; downstream needs FENs to narrate correctly.
                break

        # Compute eval/material/positional for each position
        evals: List[Optional[float]] = [None] * len(fens)
        mats: List[Optional[float]] = [None] * len(fens)
        poss: List[Optional[float]] = [None] * len(fens)

        for i, fen in enumerate(fens):
            mats[i] = self._material_balance_pawns_from_fen(fen)
            if i == 0 and eval_start_pawns is not None:
                evals[i] = eval_start_pawns
            else:
                try:
                    analysis = await self._analyze_depth(fen, depth=depth, get_top_2=False)
                    evals[i] = analysis.get("eval")
                except Exception:
                    evals[i] = None
            poss[i] = (evals[i] - mats[i]) if (evals[i] is not None and mats[i] is not None) else None

        out: List[Dict[str, Any]] = []
        for idx, d in enumerate(deltas):
            if idx + 1 >= len(fens):
                break
            ply = d.get("ply", idx + 1)
            move_san = d.get("move")
            fen_before = d.get("fen_before") or fens[idx]
            fen_after = d.get("fen_after") or fens[idx + 1]

            ev_b = evals[idx]
            ev_a = evals[idx + 1]
            m_b = mats[idx]
            m_a = mats[idx + 1]
            p_b = poss[idx]
            p_a = poss[idx + 1]

            out.append({
                "ply": ply,
                "move_san": move_san,
                "fen_before": fen_before,
                "fen_after": fen_after,
                "eval_before": ev_b,
                "eval_after": ev_a,
                "eval_delta": (ev_a - ev_b) if (ev_a is not None and ev_b is not None) else None,
                "material_before": m_b,
                "material_after": m_a,
                "material_delta": (m_a - m_b) if (m_a is not None and m_b is not None) else None,
                "positional_before": p_b,
                "positional_after": p_a,
                "positional_delta": (p_a - p_b) if (p_a is not None and p_b is not None) else None,
            })

        return out
    
    async def _analyze_threat_at_position(
        self,
        fen: str,
        depth_16: int = 16
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze threats at a position following spec:
        1. Flip side to move (create threat position)
        2. Compute best d16 move T1 and second-best d16 move T2
        3. Calculate threat_significance = |eval(T2) - eval(T1)|
        4. If threat_significance >= 60cp, return threat claim data
        
        Args:
            fen: Current position FEN
            depth_16: Depth for threat analysis
            
        Returns:
            Threat claim dict if significant (>= 60cp), None otherwise
        """
        try:
            board = chess.Board(fen)
            current_side = board.turn
            
            # Flip side to move (threat position)
            threat_board = board.copy()
            threat_board.turn = not threat_board.turn
            threat_fen = threat_board.fen()
            
            # Analyze threat position with top 2 moves
            threat_result = await self._analyze_depth(threat_fen, depth_16, get_top_2=True)
            
            best_eval_cp = threat_result.get("best_move_eval_cp")
            second_best_eval_cp = threat_result.get("second_best_move_eval_cp")
            
            if best_eval_cp is None or second_best_eval_cp is None:
                return None
            
            # Calculate threat significance (absolute gap)
            threat_significance = abs(second_best_eval_cp - best_eval_cp)
            
            # Only return if significant (>= 60cp)
            if threat_significance < 60:
                return None
            
            # Get threat PV
            threat_pv = threat_result.get("pv_san", [])
            best_move_san = threat_result.get("best_move_san")
            
            # Normalize eval to current side's perspective
            # Threat eval is from opponent's perspective, so flip sign
            threat_eval_pawns = -best_eval_cp / 100.0 if current_side == chess.WHITE else best_eval_cp / 100.0
            
            return {
                "threat_significance_cp": int(threat_significance),
                "threat_eval_cp": best_eval_cp,
                "threat_eval_pawns": threat_eval_pawns,
                "threat_move_san": best_move_san,
                "threat_pv_san": threat_pv,
                "threat_second_best_eval_cp": second_best_eval_cp,
                "threat_position_fen": threat_fen,
                "original_position_fen": fen,
                "threatening_side": "white" if current_side == chess.BLACK else "black"
            }
        except Exception as e:
            print(f"   ⚠️ [INVESTIGATOR] Error analyzing threat: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def _explore_branch_recursive(
        self,
        fen: str,
        original_eval_d16: float,
        depth_16: int,
        depth_2: int,
        move_played: Optional[str] = None,
        pgn_callback: Optional[Callable] = None,
        depth_limit: int = 5,
        current_depth: int = 0,
        perspective_side: Optional[chess.Color] = None
    ) -> Dict[str, Any]:
        """
        Recursively explore a branch until stop condition.
        
        Stop condition: if d2_best_eval < original_eval_d16, stop this branch.
        
        Args:
            fen: Current position FEN
            original_eval_d16: Original D16 best eval from starting position
            depth_16: Depth for D16 analysis
            depth_2: Depth for D2 analysis
            move_played: Move that led to this position (for tree structure)
            depth_limit: Maximum recursion depth to prevent infinite loops
            current_depth: Current recursion depth
            
        Returns:
            Branch structure with position, analysis, and sub-branches
        """
        if current_depth >= depth_limit:
            print(f"   ⚠️ [INVESTIGATOR] Recursion depth limit ({depth_limit}) reached, stopping branch")
            # Get PV from a quick analysis before stopping
            try:
                quick_result = await self._analyze_depth(fen, depth_16, get_top_2=False)
                pv_san = quick_result.get("pv_san", [])
                # Keep only the top D16 move (we don't need top-3 terminal widening anymore).
                terminal_top = (quick_result.get("top_moves") or [])[:1]
            except Exception:
                pv_san = []
                terminal_top = []
            return {
                "position": fen,
                "move_played": move_played,
                "eval_d16": None,
                "eval_d2": None,
                "branches": [],
                "stopped": "depth_limit",
                "pv_full": pv_san,
                "pv_san": pv_san,
                "terminal_top_moves_d16": terminal_top,
            }
        
        print(f"   🔍 [INVESTIGATOR] Recursive branch (depth {current_depth}): move={move_played}, fen={fen[:30]}...")
        # Emit status update via callback
        if pgn_callback:
            pgn_callback({
                "type": "status",
                "message": f"Exploring branch: {move_played} (depth {current_depth})",
                "move_san": move_played,
                "depth": current_depth
            })
        from light_raw_analyzer import compute_light_raw_analysis
        
        # D16 and D2 analysis - D16 with top 2 for critical/winning detection
        try:
            d16_result = await self._analyze_depth(fen, depth_16, get_top_2=True)
            d2_result = await self._analyze_depth(fen, depth_2)
        except Exception as e:
            print(f"   ❌ [INVESTIGATOR] Error in recursive analysis: {e}")
            import traceback
            traceback.print_exc()
            return {
                "position": fen,
                "move_played": move_played,
                "eval_d16": None,
                "eval_d2": None,
                "branches": [],
                "error": str(e)
            }
        
        eval_d16 = d16_result.get("eval")
        eval_d2 = d2_result.get("eval")
        best_move_d2 = d2_result.get("best_move_san")
        
        # Log branch exploration eval normalization
        print(f"   🔍 [EVAL_NORM] BRANCH EXPLORATION:")
        print(f"      - Branch move: {move_played}")
        print(f"      - Branch eval_d16: {eval_d16}")
        print(f"      - Branch eval_d2: {eval_d2}")
        print(f"      - Original eval_d16: {original_eval_d16}")
        if eval_d16 is not None and original_eval_d16 is not None:
            eval_change = eval_d16 - original_eval_d16
            print(f"      - Eval change: {eval_change:+.2f} pawns")
            print(f"      - Interpretation: {'Position improved' if eval_change < 0 else 'Position worsened'} by {abs(eval_change):.2f} pawns")
        
        # Extract critical/winning move info from D16
        best_move_d16_eval_cp = d16_result.get("best_move_eval_cp")
        second_best_move_d16_eval_cp = d16_result.get("second_best_move_eval_cp")
        second_best_move_d16_san = d16_result.get("second_best_move_san")
        is_critical = d16_result.get("is_critical", False)
        is_winning = d16_result.get("is_winning", False)
        
        # Check stop condition
        if eval_d2 is not None and original_eval_d16 is not None:
            eval_diff = eval_d2 - original_eval_d16
            print(f"   📊 [INVESTIGATOR] Recursive branch stop check: D2 eval={eval_d2:+.2f}, original D16={original_eval_d16:+.2f}, diff={eval_diff:+.2f}")
            if eval_d2 < original_eval_d16:
                print(f"   ⚠️ [INVESTIGATOR] Branch STOPPED: D2 eval ({eval_d2:+.2f}) < original D16 eval ({original_eval_d16:+.2f})")
                print(f"      Reason: Position after {move_played} is worse than original position")
                print(f"      Eval drop: {eval_diff:+.2f} pawns")
                return {
                    "position": fen,
                    "move_played": move_played,
                    "stopped": True,
                    "reason": "d2_eval_below_original",
                    "eval_d16": eval_d16,
                    "eval_d2": eval_d2,
                    "original_eval_d16": original_eval_d16,
                    "best_move_d16": d16_result.get("best_move_san"),
                    "best_move_d2": d2_result.get("best_move_san"),
                    "pv_full": d16_result.get("pv_san", []),
                    "pv_san": d16_result.get("pv_san", []),
                    # Keep only the top D16 move (we don't need top-3 terminal widening anymore).
                    "terminal_top_moves_d16": (d16_result.get("top_moves") or [])[:1],
                }
        
        # Analyze threats at this position (spec requirement: threat analysis at every node)
        threat_claim = await self._analyze_threat_at_position(fen, depth_16)
        
        # Find overestimated moves
        overestimated = self._find_overestimated_moves(d16_result, d2_result)
        d16_best = d16_result.get("best_move_san", "unknown")
        d2_best = d2_result.get("best_move_san", "unknown")
        print(f"   📊 [INVESTIGATOR] Recursive branch analysis:")
        print(f"      - D16 eval: {eval_d16:+.2f}, best move: {d16_best}")
        print(f"      - D2 eval: {eval_d2:+.2f}, best move: {d2_best}")
        print(f"      - Overestimated moves found: {len(overestimated)}")
        if overestimated:
            print(f"      - Overestimated moves: {', '.join(overestimated)}")
        if threat_claim:
            print(f"      - ⚠️ Significant threat detected: {threat_claim.get('threat_significance_cp')}cp gap")
        
        if not overestimated:
            print(f"   ⚠️ [INVESTIGATOR] Branch STOPPED: No overestimated moves found")
            print(f"      Reason: D16 and D2 agree on best move ({d16_best})")
            print(f"      D16 best: {d16_best}, D2 best: {d2_best}")
            return {
                "position": fen,
                "move_played": move_played,
                "stopped": True,
                "reason": "no_overestimated_moves",
                "eval_d16": eval_d16,
                "eval_d2": eval_d2,
                "best_move_d16": d16_best,
                "best_move_d2": d2_best,
                "pv_full": d16_result.get("pv_san", []),
                "pv_san": d16_result.get("pv_san", []),
                # Keep only the top D16 move (we don't need top-3 terminal widening anymore).
                "terminal_top_moves_d16": (d16_result.get("top_moves") or [])[:1],
                "threat_claim": threat_claim,  # Include threat if detected
            }
        
        # Continue branching
        print(f"   🔍 [INVESTIGATOR] Recursive: Found {len(overestimated)} overestimated moves, continuing to depth {current_depth + 1}")
        branches = []
        self.board.set_fen(fen)
        
        # Determine perspective side for branching (spec: branch at every move of perspective side)
        if perspective_side is None:
            # Default: use original position's side to move as perspective
            try:
                original_board = chess.Board(fen)
                perspective_side = original_board.turn
            except Exception:
                perspective_side = chess.WHITE  # Default fallback
        
        for move_san in overestimated:
            try:
                move = self.board.parse_san(move_san)
                if move in self.board.legal_moves:
                    self.board.push(move)
                    new_fen = self.board.fen()
                    
                    # Emit callback for move exploration
                    if pgn_callback:
                        pgn_callback({
                            "type": "move_explored",
                            "move_san": move_san,
                            "fen": new_fen,
                            "eval_d16": eval_d16
                        })
                    
                    print(f"   🔍 [INVESTIGATOR] Recursive: Exploring {move_san} at depth {current_depth + 1}")
                    branch = await self._explore_branch_recursive(
                        new_fen,
                        original_eval_d16,
                        depth_16,
                        depth_2,
                        move_san,
                        pgn_callback=pgn_callback,
                        depth_limit=depth_limit,
                        current_depth=current_depth + 1,
                        perspective_side=perspective_side
                    )
                    print(f"   ✅ [INVESTIGATOR] Recursive: Completed {move_san} at depth {current_depth + 1}")
                    branches.append(branch)
                    
                    # Emit callback for branch added
                    if pgn_callback:
                        pgn_callback({
                            "type": "branch_added",
                            "move_san": move_san,
                            "branch": branch
                        })
                    
                    self.board.pop()
            except Exception:
                pass
        
        # Get tactical and light raw analysis for this position (cached)
        light_raw = self._cached_light_raw(fen)
        threat_tags = self._extract_tag_labels(light_raw.tags if light_raw else [])
        
        # Return branch structure with threat claim
        return {
            "position": fen,
            "move_played": move_played,
            "stopped": False,
            "eval_d16": eval_d16,
            "eval_d2": eval_d2,
            "best_move_d16": d16_result.get("best_move_san"),
            "best_move_d16_eval_cp": best_move_d16_eval_cp,
            "second_best_move_d16": d16_result.get("second_best_move_san"),
            "second_best_move_d16_eval_cp": second_best_move_d16_eval_cp,
            "is_critical": is_critical,
            "is_winning": is_winning,
            "overestimated_moves": overestimated,
            "threat_tags": threat_tags,
            "threat_claim": threat_claim,  # Include threat if detected (>= 60cp)
            "light_raw": light_raw.to_dict() if light_raw else {},
            "branches": branches,
            "pv_full": d16_result.get("pv_san", []),
            "pv_san": d16_result.get("pv_san", []),
            "terminal_top_moves_d16": (d16_result.get("top_moves") or [])[:1],
        }
    
    async def _build_exploration_pgn(
        self,
        exploration_tree: Dict[str, Any],
        light_raw: Optional[LightRawAnalysis]
    ) -> str:
        """
        Build massive PGN from exploration tree with themes, threats, and commentary.
        
        Args:
            exploration_tree: Tree structure from recursive exploration
            light_raw: Light raw analysis results
            
        Returns:
            PGN string with annotations
        """
        try:
            # Use original_position if available (position before player's move)
            # Otherwise fall back to position (position after move)
            original_fen = exploration_tree.get("original_position")
            fen = original_fen if original_fen else exploration_tree.get("position", "")
            current_position = exploration_tree.get("position", "")  # Position after move (for analysis)
            
            game = chess.pgn.Game()
            game.headers["FEN"] = fen  # Use FEN before player's move for PGN
            game.headers["Event"] = "Investigation"
            
            # Add starting position tag list and roles as comment on the game
            # Compute from original_fen (before player's move) if available
            if original_fen:
                # Use original position (before player's move) for starting tags/roles
                start_light_raw = self._cached_light_raw(original_fen)
                starting_tags = [tag.get('tag_name', tag.get('tag', '')) for tag in start_light_raw.tags] if start_light_raw else []
                starting_roles = start_light_raw.roles if (start_light_raw and hasattr(start_light_raw, 'roles')) else {}
            else:
                # Fallback: use provided light_raw or compute from current fen
                if light_raw and light_raw.tags:
                    starting_tags = [tag.get('tag_name', tag.get('tag', '')) for tag in light_raw.tags]
                else:
                    # Compute if not provided
                    start_light_raw = self._cached_light_raw(fen)
                    starting_tags = [tag.get('tag_name', tag.get('tag', '')) for tag in start_light_raw.tags] if start_light_raw else []
                
                # Get starting roles
                starting_roles = {}
                if light_raw and hasattr(light_raw, 'roles') and light_raw.roles:
                    starting_roles = light_raw.roles
                else:
                    # Compute if not provided
                    if not start_light_raw:
                        start_light_raw = self._cached_light_raw(fen)
                    if start_light_raw and hasattr(start_light_raw, 'roles'):
                        starting_roles = start_light_raw.roles
            
            # Format starting roles for comment
            # IMPORTANT: Summariser expects bracketed headers:
            #   [Starting tags: ...]
            #   [Starting roles: piece_id:role.name, piece_id:role.name, ...]
            # and it expects each role entry to be a single "piece_id:role" (not "role1,role2").
            starting_roles_list = []
            max_roles_total = 40  # keep header bounded
            for piece_id, roles_list in starting_roles.items():
                if not roles_list:
                    continue
                for role in roles_list[:3]:  # cap roles per piece
                    starting_roles_list.append(f"{piece_id}:{role}")
                    if len(starting_roles_list) >= max_roles_total:
                        break
                if len(starting_roles_list) >= max_roles_total:
                    break
            
            # Build game comment with both tags and roles.
            # IMPORTANT: Keep them as separate bracket blocks so downstream regexes can parse them cleanly.
            comment_blocks = []
            if starting_tags:
                comment_blocks.append(f"[Starting tags: {', '.join(starting_tags[:20])}]")
            if starting_roles_list:
                comment_blocks.append(f"[Starting roles: {', '.join(starting_roles_list[:max_roles_total])}]")
            if comment_blocks:
                game.comment = "".join(comment_blocks)
            
            # Build PGN recursively from tree
            node = game
            await self._build_pgn_from_tree(node, exploration_tree, light_raw, 0)
            
            exporter = chess.pgn.StringExporter(
                headers=True,
                variations=True,
                comments=True
            )
            return str(game.accept(exporter))
        except Exception as e:
            print(f"   ❌ [INVESTIGATOR] ERROR in _build_exploration_pgn: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return ""
    
    async def _build_pgn_from_tree(
        self,
        node: chess.pgn.GameNode,
        tree_node: Dict[str, Any],
        light_raw: Optional[LightRawAnalysis],
        move_number: int
    ):
        """Recursively build PGN from exploration tree - FOLLOWS FULL PV SEQUENCE"""
        try:
            def _safe_san(b: chess.Board, mv: chess.Move) -> str:
                """
                python-chess asserts if you call san() on an illegal move for that board.
                PGN building must never crash due to logging/formatting, so fall back to UCI.
                """
                try:
                    return b.san(mv)
                except Exception:
                    try:
                        return mv.uci()
                    except Exception:
                        return str(mv)

            fen = tree_node.get("position", "")
            self.board.set_fen(fen)
            
            # Get full PV sequence, not just first move
            pv_full = tree_node.get("pv_full", [])
            if not pv_full:
                # Fallback to best_move_d16 if pv_full not available
                best_move_d16 = tree_node.get("best_move_d16")
                if best_move_d16:
                    pv_full = [best_move_d16]
                    print(f"   🔄 [INVESTIGATOR] Using best_move_d16 fallback: {best_move_d16}")
                else:
                    print(f"   ❌ [INVESTIGATOR] ERROR: No pv_full AND no best_move_d16 in tree_node!")
                    print(f"      Tree node keys: {list(tree_node.keys())}")
                    # Return early - can't build PGN without moves
                    return
            
            eval_d16 = tree_node.get("eval_d16")
            
            # Follow the ENTIRE PV sequence, not just first move
            current_node = node
            current_board = self.board.copy()
            
            # Get starting tags and roles (for first move comparison)
            tags_before = []
            roles_before = {}
            if light_raw and light_raw.tags:
                tags_before = light_raw.tags
            if light_raw and hasattr(light_raw, 'roles') and light_raw.roles:
                roles_before = light_raw.roles
            else:
                # Compute if not provided
                start_light_raw = self._cached_light_raw(current_board.fen())
                if start_light_raw:
                    tags_before = start_light_raw.tags
                    if hasattr(start_light_raw, 'roles'):
                        roles_before = start_light_raw.roles
            
            for move_idx, move_san in enumerate(pv_full):
                try:
                    print(f"   🔍 [PGN_BUILD] Processing PV move {move_idx+1}/{len(pv_full)}: {move_san}")
                    print(f"      Current board FEN: {current_board.fen()}")
                    
                    # Get PGN node's board state for validation
                    try:
                        node_board = current_node.board()
                        print(f"      PGN node board FEN: {node_board.fen()}")
                        boards_match = current_board.fen() == node_board.fen()
                        print(f"      Boards match: {boards_match}")
                        if not boards_match:
                            print(f"      ⚠️ BOARD STATE MISMATCH!")
                            print(f"         Current board: {current_board.fen()}")
                            print(f"         PGN node board: {node_board.fen()}")
                    except Exception as board_check_e:
                        print(f"      ⚠️ Could not get PGN node board state: {board_check_e}")
                    
                    # If SAN can't be parsed from this node position, PV is misaligned.
                    # Stop PV processing for this node (best-effort PGN building).
                    try:
                        move = current_board.parse_san(move_san)
                    except Exception as e:
                        print(
                            f"   ⚠️ [PGN_BUILD] PV misaligned for node; stopping PV here. "
                            f"illegal san {move_san!r} in {current_board.fen()} ({type(e).__name__})"
                        )
                        break
                    print(f"      Parsed move: {move} (UCI: {move.uci()})")
                    
                    # Check legality in current_board
                    is_legal_current = move in current_board.legal_moves
                    print(f"      Legal in current_board: {is_legal_current}")
                    
                    # Check legality in PGN node board
                    is_legal_pgn = False
                    try:
                        node_board = current_node.board()
                        is_legal_pgn = move in node_board.legal_moves
                        print(f"      [CHAIN] Legal in PGN node board: {is_legal_pgn}")
                        if not is_legal_pgn:
                            print(f"      ❌ [CHAIN] MOVE NOT LEGAL IN PGN NODE BOARD!")
                            print(f"         Move: {move_san} ({move.uci()})")
                            print(f"         PGN node FEN: {node_board.fen()}")
                            print(f"         Current board FEN: {current_board.fen()}")
                            print(f"         Legal moves in PGN node: {[_safe_san(node_board, m) for m in list(node_board.legal_moves)[:10]]}")
                    except Exception as pgn_check_e:
                        print(f"      ⚠️ [CHAIN] Could not check PGN node legality: {pgn_check_e}")
                        import traceback
                        traceback.print_exc()
                        is_legal_pgn = False  # Don't assume legal - fail safe
                    
                    # CRITICAL: Only add variation if move is legal in BOTH boards
                    if move in current_board.legal_moves and is_legal_pgn:
                        # Get tags and roles BEFORE the move
                        tags_before_move = tags_before.copy() if tags_before else []
                        tags_before_names = {tag.get('tag_name', tag.get('tag', '')) for tag in tags_before_move}
                        
                        roles_before_move = roles_before.copy() if roles_before else {}
                        roles_before_set = set()
                        for piece_id, roles_list in roles_before_move.items():
                            for role in roles_list:
                                roles_before_set.add(f"{piece_id}:{role}")
                        
                        # Make the move
                        fen_before_move = current_board.fen()
                        current_board.push(move)
                        print(f"      ✅ Move pushed to current_board, new FEN: {current_board.fen()}")
                        
                        # Compute tags and roles AFTER the move
                        previous_fen_for_move = fen_before_move if move_idx == 0 else None
                        after_light_raw = compute_light_raw_analysis(
                            current_board.fen(),
                            previous_fen=previous_fen_for_move
                        )
                        tags_after_move = after_light_raw.tags if after_light_raw else []
                        tags_after_names = {tag.get('tag_name', tag.get('tag', '')) for tag in tags_after_move}
                        
                        roles_after_move = {}
                        if after_light_raw and hasattr(after_light_raw, 'roles'):
                            roles_after_move = after_light_raw.roles
                        
                        roles_after_set = set()
                        for piece_id, roles_list in roles_after_move.items():
                            for role in roles_list:
                                roles_after_set.add(f"{piece_id}:{role}")
                        
                        # Find tags gained and lost
                        tags_gained = [tag.get('tag_name', tag.get('tag', '')) for tag in tags_after_move 
                                     if tag.get('tag_name', tag.get('tag', '')) not in tags_before_names]
                        tags_lost = [tag.get('tag_name', tag.get('tag', '')) for tag in tags_before_move 
                                   if tag.get('tag_name', tag.get('tag', '')) not in tags_after_names]
                        
                        # NEW: Find roles gained and lost
                        roles_gained = []
                        roles_lost = []
                        
                        # Roles gained: in after but not in before
                        for role_key in roles_after_set:
                            if role_key not in roles_before_set:
                                roles_gained.append(role_key)
                        
                        # Roles lost: in before but not in after
                        for role_key in roles_before_set:
                            if role_key not in roles_after_set:
                                roles_lost.append(role_key)
                        
                        # Store role deltas in tree_node for evidence extraction
                        if "role_deltas" not in tree_node:
                            tree_node["role_deltas"] = []
                        tree_node["role_deltas"].append({
                            "move": move_san,
                            "roles_gained": roles_gained,
                            "roles_lost": roles_lost
                        })
                        
                        # Tag-based tactical highlights
                        tag_highlights = [
                            self._humanize_tag(tag_name)
                            for tag_name in (tags_gained[:5] if tags_gained else [])
                            if self._humanize_tag(tag_name)
                        ]
                        threat_labels = tag_highlights.copy()
                        
                        # Build annotation for THIS move
                        annotation_parts = []
                        
                        # Add eval annotation
                        if move_idx == 0 and eval_d16 is not None:
                            # Use D16 eval for first move
                            annotation_parts.append(f"[%eval {eval_d16:+.2f}]")
                        elif move_idx > 0:
                            # Compute shallow eval for subsequent moves
                            try:
                                if self.use_pool and self.engine_pool:
                                    # Use engine pool
                                    analysis_result = await self.engine_pool.analyze_single(
                                        fen=current_board.fen(),
                                        depth=2,
                                        multipv=1
                                    )
                                    if analysis_result.get("success") and analysis_result.get("result"):
                                        info = analysis_result["result"][0] if isinstance(analysis_result["result"], list) else analysis_result["result"]
                                    else:
                                        info = {}
                                elif self.engine_queue:
                                    # Use engine queue
                                    info = await self.engine_queue.enqueue(
                                        self.engine_queue.engine.analyse,
                                        current_board,
                                        chess.engine.Limit(depth=2)
                                    )
                                else:
                                    info = {}
                                
                                score = info.get("score")
                                eval_cp = self._score_to_white_cp(score, fen=current_board.fen())
                                if eval_cp is not None:
                                    annotation_parts.append(f"[%eval {eval_cp/100:+.2f}]")
                            except Exception:
                                pass
                        
                        # Add theme annotation (from position after move)
                        if after_light_raw and after_light_raw.top_themes:
                            theme_str = ",".join(after_light_raw.top_themes[:2])
                            annotation_parts.append(f"[%theme \"{theme_str}\"]")
                        
                        # Add tactic annotation (from position after move)
                        tactic_type = tag_highlights[0] if tag_highlights else "none"
                        annotation_parts.append(f"[%tactic \"{tactic_type}\"]")
                        
                        # Build commentary in format: {[tags gained], [tags lost], [roles gained], [roles lost], [threats]}
                        # Format tags gained (limit to 10 for readability)
                        gained_str = ", ".join(tags_gained[:10]) if tags_gained else "none"
                        if len(tags_gained) > 10:
                            gained_str += f" (+{len(tags_gained) - 10} more)"
                        
                        # Format tags lost (limit to 10 for readability)
                        lost_str = ", ".join(tags_lost[:10]) if tags_lost else "none"
                        if len(tags_lost) > 10:
                            lost_str += f" (+{len(tags_lost) - 10} more)"
                        
                        # NEW: Format roles gained
                        roles_gained_formatted = []
                        for role_key in roles_gained[:10]:
                            # Format: "piece_id:role" -> "piece_id role"
                            if ":" in role_key:
                                piece_id, role = role_key.split(":", 1)
                                # Extract readable piece name
                                parts = piece_id.split("_")
                                if len(parts) >= 3:
                                    piece_type = parts[1]
                                    square = parts[2]
                                    roles_gained_formatted.append(f"{piece_type}_{square}:{role}")
                                else:
                                    roles_gained_formatted.append(role_key)
                            else:
                                roles_gained_formatted.append(role_key)
                        
                        roles_gained_str = ", ".join(roles_gained_formatted) if roles_gained_formatted else "none"
                        if len(roles_gained) > 10:
                            roles_gained_str += f" (+{len(roles_gained) - 10} more)"
                        
                        # NEW: Format roles lost
                        roles_lost_formatted = []
                        for role_key in roles_lost[:10]:
                            if ":" in role_key:
                                piece_id, role = role_key.split(":", 1)
                                parts = piece_id.split("_")
                                if len(parts) >= 3:
                                    piece_type = parts[1]
                                    square = parts[2]
                                    roles_lost_formatted.append(f"{piece_type}_{square}:{role}")
                                else:
                                    roles_lost_formatted.append(role_key)
                            else:
                                roles_lost_formatted.append(role_key)
                        
                        roles_lost_str = ", ".join(roles_lost_formatted) if roles_lost_formatted else "none"
                        if len(roles_lost) > 10:
                            roles_lost_str += f" (+{len(roles_lost) - 10} more)"
                        
                        # Format threat labels
                        threat_str = ", ".join(threat_labels[:5]) if threat_labels else "none"
                        if len(threat_labels) > 5:
                            threat_str += f" (+{len(threat_labels) - 5} more)"
                        
                        # Build final commentary with roles
                        commentary = f"{{[gained: {gained_str}], [lost: {lost_str}], [roles_gained: {roles_gained_str}], [roles_lost: {roles_lost_str}], [threats: {threat_str}]}}"
                        
                        # Add move with annotation
                        print(f"      🔍 [CHAIN] [PGN_BUILD] Attempting to add variation to PGN node...")
                        print(f"         [CHAIN] PGN node type: {type(current_node)}")
                        print(f"         [CHAIN] Move to add: {move} (UCI: {move.uci()}, SAN: {move_san})")
                        try:
                            node_board_before = current_node.board()
                            print(f"         [CHAIN] PGN node board BEFORE add_variation: {node_board_before.fen()}")
                            print(f"         [CHAIN] Move legal in node_board_before: {move in node_board_before.legal_moves}")
                        except Exception as pre_check_e:
                            print(f"         ⚠️ [CHAIN] Could not get node board before add_variation: {pre_check_e}")
                        
                        try:
                            current_node = current_node.add_variation(move)
                            print(f"      ✅ [CHAIN] Variation added successfully")
                        except AssertionError as ae:
                            print(f"      ❌ [CHAIN] AssertionError in add_variation: {ae}")
                            print(f"         [CHAIN] Move: {move_san} ({move.uci()})")
                            print(f"         [CHAIN] Current board FEN: {current_board.fen()}")
                            try:
                                node_board = current_node.board()
                                print(f"         [CHAIN] PGN node board FEN: {node_board.fen()}")
                                print(f"         [CHAIN] Move legal in node_board: {move in node_board.legal_moves}")
                            except:
                                pass
                            import traceback
                            traceback.print_exc()
                            # Skip this move but continue with next
                            break
                        except Exception as add_var_e:
                            print(f"      ❌ [CHAIN] Unexpected error in add_variation: {type(add_var_e).__name__}: {add_var_e}")
                            import traceback
                            traceback.print_exc()
                            break
                        
                        try:
                            node_board_after = current_node.board()
                            print(f"         PGN node board AFTER add_variation: {node_board_after.fen()}")
                        except:
                            pass
                        
                        if annotation_parts or commentary:
                            full_comment = " ".join(annotation_parts) + " " + commentary
                            current_node.comment = full_comment.strip()
                        
                        # Update tags_before and roles_before for next iteration
                        tags_before = tags_after_move
                        roles_before = roles_after_move
                    else:
                        # Invalid move in PV - stop here
                        print(f"   ⚠️ [CHAIN] PV move {move_san} at index {move_idx} not legal, stopping PV")
                        print(f"      [CHAIN] Legal in current_board: {move in current_board.legal_moves}")
                        print(f"      [CHAIN] Legal in PGN node: {is_legal_pgn}")
                        print(f"      [CHAIN] Current board FEN: {current_board.fen()}")
                        try:
                            node_board = current_node.board()
                            print(f"      [CHAIN] PGN node board FEN: {node_board.fen()}")
                        except:
                            pass
                        print(f"      [CHAIN] Legal moves: {[_safe_san(current_board, m) for m in list(current_board.legal_moves)[:10]]}")
                        break
                except Exception as e:
                    print(f"   ❌ [PGN_BUILD] ERROR adding PV move {move_san} at index {move_idx}: {type(e).__name__}: {e}")
                    print(f"      Current board FEN: {current_board.fen()}")
                    # Do not traceback-spam; PGN build is best-effort.
                    break
            
            # Add branches as variations (only from the root position)
            if move_number == 0:  # Only add branches at root level
                branches = tree_node.get("branches", [])
                if branches:
                    print(f"   📊 [INVESTIGATOR] Building {len(branches)} variation(s) from branches")
                    for idx, branch in enumerate(branches, 1):
                        move_played = branch.get('move_played', 'unknown')
                        sub_branches = len(branch.get('branches', []))
                        stopped = branch.get('stopped', False)
                        print(f"      - Variation {idx}: {move_played} (stopped: {stopped}, has {sub_branches} sub-branches)")
                for branch in branches:
                    # Include both stopped and non-stopped branches in PGN
                    branch_move = branch.get("move_played")
                    is_stopped = branch.get("stopped", False)
                    stop_reason = branch.get("reason", "unknown")
                    
                    print(f"   🔍 [PGN_BUILD] Processing branch: {branch_move} (stopped: {is_stopped}, reason: {stop_reason})")
                    
                    if branch_move:
                        try:
                            # Make sure board is at correct position
                            self.board.set_fen(fen)
                            print(f"      Branch starting FEN: {fen}")
                            print(f"      Self.board FEN: {self.board.fen()}")
                            
                            # Check PGN node board state
                            try:
                                node_board = node.board()
                                print(f"      PGN node board FEN: {node_board.fen()}")
                                boards_match = fen == node_board.fen()
                                print(f"      Branch FEN matches PGN node: {boards_match}")
                                if not boards_match:
                                    print(f"      ⚠️ BRANCH BOARD STATE MISMATCH!")
                                    print(f"         Branch FEN: {fen}")
                                    print(f"         PGN node FEN: {node_board.fen()}")
                            except Exception as node_check_e:
                                print(f"      ⚠️ Could not get PGN node board state: {node_check_e}")
                            
                            branch_move_obj = self.board.parse_san(branch_move)
                            print(f"      Parsed branch move: {branch_move_obj} (UCI: {branch_move_obj.uci()})")
                            
                            is_legal_self = branch_move_obj in self.board.legal_moves
                            print(f"      Legal in self.board: {is_legal_self}")
                            
                            # Check legality in PGN node
                            try:
                                node_board = node.board()
                                is_legal_pgn = branch_move_obj in node_board.legal_moves
                                print(f"      Legal in PGN node board: {is_legal_pgn}")
                                if not is_legal_pgn:
                                    print(f"      ❌ BRANCH MOVE NOT LEGAL IN PGN NODE BOARD!")
                                    print(f"         Move: {branch_move} ({branch_move_obj.uci()})")
                                    print(f"         PGN node FEN: {node_board.fen()}")
                                    print(f"         Self.board FEN: {self.board.fen()}")
                                    print(f"         Legal moves in PGN node: {[_safe_san(node_board, m) for m in list(node_board.legal_moves)[:10]]}")
                            except Exception as pgn_check_e:
                                print(f"      ⚠️ [CHAIN] Could not check PGN node legality: {pgn_check_e}")
                                is_legal_pgn = False  # Fail safe - don't assume legal
                            
                            # CRITICAL: Check legality in BOTH boards before adding variation
                            if branch_move_obj in self.board.legal_moves and is_legal_pgn:
                                print(f"      🔍 [CHAIN] [PGN_BUILD] Attempting to add branch variation...")
                                print(f"         [CHAIN] PGN node type: {type(node)}")
                                print(f"         Branch move: {branch_move_obj} (UCI: {branch_move_obj.uci()}, SAN: {branch_move})")
                                try:
                                    node_board_before = node.board()
                                    print(f"         PGN node board BEFORE add_variation: {node_board_before.fen()}")
                                except:
                                    pass
                                
                                # NEW: Get tags and roles before branch move
                                branch_tags_before = []
                                branch_roles_before = {}
                                branch_fen_before = self.board.fen()
                                branch_light_raw_before = self._cached_light_raw(branch_fen_before)
                                if branch_light_raw_before:
                                    branch_tags_before = branch_light_raw_before.tags if branch_light_raw_before.tags else []
                                    if hasattr(branch_light_raw_before, 'roles'):
                                        branch_roles_before = branch_light_raw_before.roles
                                
                                # Make the branch move
                                self.board.push(branch_move_obj)
                                branch_fen_after = self.board.fen()
                                
                                # NEW: Get tags and roles after branch move
                                branch_tags_after = []
                                branch_roles_after = {}
                                branch_light_raw_after = compute_light_raw_analysis(
                                    branch_fen_after,
                                    previous_fen=branch_fen_before
                                )
                                if branch_light_raw_after:
                                    branch_tags_after = branch_light_raw_after.tags if branch_light_raw_after.tags else []
                                    if hasattr(branch_light_raw_after, 'roles'):
                                        branch_roles_after = branch_light_raw_after.roles
                                
                                # NEW: Calculate role changes for branch move
                                branch_roles_before_set = set()
                                for piece_id, roles_list in branch_roles_before.items():
                                    for role in roles_list:
                                        branch_roles_before_set.add(f"{piece_id}:{role}")
                                
                                branch_roles_after_set = set()
                                for piece_id, roles_list in branch_roles_after.items():
                                    for role in roles_list:
                                        branch_roles_after_set.add(f"{piece_id}:{role}")
                                
                                branch_roles_gained = branch_roles_after_set - branch_roles_before_set
                                branch_roles_lost = branch_roles_before_set - branch_roles_after_set
                                
                                # Calculate tag changes for branch move
                                branch_tags_before_names = {tag.get('tag_name', tag.get('tag', '')) for tag in branch_tags_before}
                                branch_tags_after_names = {tag.get('tag_name', tag.get('tag', '')) for tag in branch_tags_after}
                                branch_tags_gained = branch_tags_after_names - branch_tags_before_names
                                branch_tags_lost = branch_tags_before_names - branch_tags_after_names
                                
                                # Store role deltas in branch for evidence extraction
                                if "role_deltas" not in branch:
                                    branch["role_deltas"] = []
                                branch["role_deltas"].append({
                                    "move": branch_move,
                                    "roles_gained": list(branch_roles_gained),
                                    "roles_lost": list(branch_roles_lost)
                                })
                                
                                try:
                                    branch_node = node.add_variation(branch_move_obj)
                                    print(f"      ✅ [CHAIN] Branch variation added successfully")
                                    
                                    try:
                                        branch_node_board = branch_node.board()
                                        print(f"         [CHAIN] Branch node board AFTER add_variation: {branch_node_board.fen()}")
                                    except Exception as post_check_e:
                                        print(f"         ⚠️ [CHAIN] Could not get branch node board after add_variation: {post_check_e}")
                                except AssertionError as ae:
                                    print(f"      ❌ [CHAIN] AssertionError adding branch variation: {ae}")
                                    print(f"         [CHAIN] Branch move: {branch_move} ({branch_move_obj.uci()})")
                                    print(f"         [CHAIN] Self.board FEN: {self.board.fen()}")
                                    try:
                                        node_board = node.board()
                                        print(f"         [CHAIN] PGN node board FEN: {node_board.fen()}")
                                        print(f"         [CHAIN] Move legal in node_board: {branch_move_obj in node_board.legal_moves}")
                                    except:
                                        pass
                                    import traceback
                                    traceback.print_exc()
                                    continue  # Skip this branch but continue with next
                                except Exception as add_branch_e:
                                    print(f"      ❌ [CHAIN] Unexpected error adding branch variation: {type(add_branch_e).__name__}: {add_branch_e}")
                                    import traceback
                                    traceback.print_exc()
                                    continue  # Skip this branch but continue with next
                                
                                # Add branch annotation
                                branch_eval_d2 = branch.get("eval_d2")
                                branch_eval_d16 = branch.get("eval_d16")
                                branch_annotation = []
                                
                                # Add eval annotation (prefer D16 if available, otherwise D2)
                                if branch_eval_d16 is not None:
                                    branch_annotation.append(f"[%eval {branch_eval_d16:+.2f}]")
                                elif branch_eval_d2 is not None:
                                    branch_annotation.append(f"[%eval {branch_eval_d2:+.2f}]")
                                
                                # Add theme annotation
                                if is_stopped:
                                    branch_annotation.append("[%theme \"stopped_branch\"]")
                                    # Add stop reason to theme
                                    if stop_reason == "d2_eval_below_original":
                                        branch_annotation.append("[%theme \"d2_worse_than_original\"]")
                                    elif stop_reason == "no_overestimated_moves":
                                        branch_annotation.append("[%theme \"d2_d16_agree\"]")
                                    elif stop_reason == "depth_limit":
                                        branch_annotation.append("[%theme \"max_depth_reached\"]")
                                else:
                                    branch_annotation.append("[%theme \"overestimated\"]")
                                
                                branch_threats = branch.get("threat_tags", [])
                                if branch_threats:
                                    branch_annotation.append(f"[%tactic \"{branch_threats[0]}\"]")
                                
                                # Build commentary with roles
                                branch_commentary = ""
                                if is_stopped:
                                    branch_commentary = f"Branch stopped: {stop_reason}."
                                    if stop_reason == "d2_eval_below_original":
                                        original_eval = branch.get("original_eval_d16")
                                        if original_eval is not None and branch_eval_d2 is not None:
                                            diff = branch_eval_d2 - original_eval
                                            branch_commentary += f" D2 eval ({branch_eval_d2:+.2f}) below original ({original_eval:+.2f}, diff: {diff:+.2f})."
                                    elif stop_reason == "no_overestimated_moves":
                                        branch_commentary += " D16 and D2 agree on best move."
                                    elif stop_reason == "depth_limit":
                                        branch_commentary += " Maximum recursion depth reached."
                                else:
                                    branch_commentary = "D2 overestimates."
                                    if branch_threats:
                                        branch_commentary += f" Threat: {branch_threats[0]}."
                                
                                # NEW: Format role changes for branch commentary
                                branch_roles_gained_formatted = []
                                for role_key in list(branch_roles_gained)[:10]:
                                    if ":" in role_key:
                                        piece_id, role = role_key.split(":", 1)
                                        parts = piece_id.split("_")
                                        if len(parts) >= 3:
                                            piece_type = parts[1]
                                            square = parts[2]
                                            branch_roles_gained_formatted.append(f"{piece_type}_{square}:{role}")
                                        else:
                                            branch_roles_gained_formatted.append(role_key)
                                    else:
                                        branch_roles_gained_formatted.append(role_key)
                                
                                branch_roles_lost_formatted = []
                                for role_key in list(branch_roles_lost)[:10]:
                                    if ":" in role_key:
                                        piece_id, role = role_key.split(":", 1)
                                        parts = piece_id.split("_")
                                        if len(parts) >= 3:
                                            piece_type = parts[1]
                                            square = parts[2]
                                            branch_roles_lost_formatted.append(f"{piece_type}_{square}:{role}")
                                        else:
                                            branch_roles_lost_formatted.append(role_key)
                                    else:
                                        branch_roles_lost_formatted.append(role_key)
                                
                                branch_roles_gained_str = ', '.join(branch_roles_gained_formatted) if branch_roles_gained_formatted else 'none'
                                branch_roles_lost_str = ', '.join(branch_roles_lost_formatted) if branch_roles_lost_formatted else 'none'
                                
                                # Format tag changes
                                branch_tags_gained_str = ', '.join([self._humanize_tag(t) or t for t in list(branch_tags_gained)[:10]]) if branch_tags_gained else 'none'
                                branch_tags_lost_str = ', '.join([self._humanize_tag(t) or t for t in list(branch_tags_lost)[:10]]) if branch_tags_lost else 'none'
                                
                                # Add role and tag deltas to commentary
                                if branch_tags_gained_str != 'none' or branch_tags_lost_str != 'none' or branch_roles_gained_str != 'none' or branch_roles_lost_str != 'none':
                                    branch_commentary += f" {{[gained: {branch_tags_gained_str}], [lost: {branch_tags_lost_str}], [roles_gained: {branch_roles_gained_str}], [roles_lost: {branch_roles_lost_str}], [threats: none]}}"
                                
                                branch_node.comment = " ".join(branch_annotation) + " " + branch_commentary
                                
                                # Restore board state
                                self.board.pop()
                                
                                # Recursively build branch (even if stopped, to show the position)
                                branch_light_raw_obj = None
                                if branch.get("light_raw"):
                                    from light_raw_analyzer import LightRawAnalysis
                                    lr_dict = branch.get("light_raw", {})
                                    branch_light_raw_obj = LightRawAnalysis(
                                        themes=lr_dict.get("themes", {}),
                                        tags=lr_dict.get("tags", []),
                                        material_balance_cp=lr_dict.get("material_balance_cp", 0),
                                        material_advantage=lr_dict.get("material_advantage", "equal"),
                                        theme_scores=lr_dict.get("theme_scores", {}),
                                        top_themes=lr_dict.get("top_themes", [])
                                    )
                                
                                # Only recursively build if not stopped (or if stopped but has sub-branches)
                                if not is_stopped or branch.get("branches"):
                                    await self._build_pgn_from_tree(
                                        branch_node,
                                        branch,
                                        branch_light_raw_obj,
                                        move_number + 1
                                    )
                                else:
                                    # Branch stopped, but extend it with PV if available
                                    pv_full = branch.get("pv_full") or branch.get("pv_san", [])
                                    terminal_top = branch.get("terminal_top_moves_d16") or []
                                    if not isinstance(terminal_top, list):
                                        terminal_top = []

                                    # NEW: include only the top D16 continuation (no top-3 widening).
                                    try:
                                        branch_fen = branch.get("position") or self.board.fen()
                                        temp_board2 = chess.Board()
                                        temp_board2.set_fen(branch_fen)
                                        for tm in terminal_top[:1]:
                                            if not isinstance(tm, dict):
                                                continue
                                            san = tm.get("move")
                                            if not isinstance(san, str) or not san.strip():
                                                continue
                                            try:
                                                mv = temp_board2.parse_san(san)
                                                if mv not in temp_board2.legal_moves:
                                                    continue
                                                var = branch_node.add_variation(mv)
                                                var.comment = f"[d16_top] {san} (rank={tm.get('rank')}, eval_cp={tm.get('eval_cp')})"
                                            except Exception:
                                                continue
                                    except Exception:
                                        pass

                                    if pv_full and len(pv_full) > 0:
                                        # Extend the branch with PV moves (limit to first 10 moves)
                                        print(f"   🔄 [INVESTIGATOR] Extending stopped branch {branch_move} with PV ({len(pv_full)} moves available)")
                                        temp_board = chess.Board()
                                        branch_fen = branch.get("position")
                                        if not branch_fen:
                                            # Fallback to current board position
                                            branch_fen = self.board.fen()
                                        temp_board.set_fen(branch_fen)
                                        
                                        # Get light raw for PV moves (compute_light_raw_analysis already imported at top of file)
                                        
                                        for pv_idx, pv_move_san in enumerate(pv_full[:10]):  # Limit to first 10 PV moves
                                            try:
                                                print(f"      🔍 [PGN_BUILD] Processing stopped branch PV move {pv_idx+1}/{min(len(pv_full), 10)}: {pv_move_san}")
                                                print(f"         Temp board FEN: {temp_board.fen()}")
                                                
                                                # Check branch_node board state
                                                try:
                                                    branch_node_board = branch_node.board()
                                                    print(f"         Branch node board FEN: {branch_node_board.fen()}")
                                                    boards_match = temp_board.fen() == branch_node_board.fen()
                                                    print(f"         Boards match: {boards_match}")
                                                    if not boards_match:
                                                        print(f"         ⚠️ STOPPED BRANCH BOARD STATE MISMATCH!")
                                                        print(f"            Temp board: {temp_board.fen()}")
                                                        print(f"            Branch node board: {branch_node_board.fen()}")
                                                except Exception as branch_check_e:
                                                    print(f"         ⚠️ Could not get branch node board state: {branch_check_e}")
                                                
                                                pv_move = temp_board.parse_san(pv_move_san)
                                                print(f"         Parsed PV move: {pv_move} (UCI: {pv_move.uci()})")
                                                
                                                is_legal_temp = pv_move in temp_board.legal_moves
                                                print(f"         Legal in temp_board: {is_legal_temp}")
                                                
                                                # Check legality in branch_node
                                                try:
                                                    branch_node_board = branch_node.board()
                                                    is_legal_branch = pv_move in branch_node_board.legal_moves
                                                    print(f"         Legal in branch node board: {is_legal_branch}")
                                                    if not is_legal_branch:
                                                        print(f"         ❌ STOPPED BRANCH PV MOVE NOT LEGAL IN BRANCH NODE BOARD!")
                                                        print(f"            Move: {pv_move_san} ({pv_move.uci()})")
                                                        print(f"            Branch node FEN: {branch_node_board.fen()}")
                                                        print(f"            Temp board FEN: {temp_board.fen()}")
                                                        print(f"            Legal moves in branch node: {[branch_node_board.san(m) for m in list(branch_node_board.legal_moves)[:10]]}")
                                                except Exception as branch_pgn_check_e:
                                                    print(f"         ⚠️ Could not check branch node legality: {branch_pgn_check_e}")
                                                    is_legal_branch = True  # Assume legal if we can't check
                                                
                                                if pv_move in temp_board.legal_moves:
                                                    # Get tags and roles before move
                                                    tags_before_pv = []
                                                    roles_before_pv = {}
                                                    fen_before_pv = temp_board.fen()
                                                    pv_light_raw = self._cached_light_raw(fen_before_pv)
                                                    if pv_light_raw:
                                                        tags_before_pv = pv_light_raw.tags if pv_light_raw.tags else []
                                                        if hasattr(pv_light_raw, 'roles'):
                                                            roles_before_pv = pv_light_raw.roles
                                                    
                                                    # Make the move
                                                    temp_board.push(pv_move)
                                                    print(f"         ✅ PV move pushed to temp_board, new FEN: {temp_board.fen()}")
                                                    
                                                    # Get tags and roles after move
                                                    tags_after_pv = []
                                                    roles_after_pv = {}
                                                    pv_light_raw_after = compute_light_raw_analysis(
                                                        temp_board.fen(),
                                                        previous_fen=fen_before_pv
                                                    )
                                                    if pv_light_raw_after:
                                                        tags_after_pv = pv_light_raw_after.tags if pv_light_raw_after.tags else []
                                                        if hasattr(pv_light_raw_after, 'roles'):
                                                            roles_after_pv = pv_light_raw_after.roles
                                                    
                                                    # Calculate tag changes
                                                    tags_before_names = {tag.get('tag_name', tag.get('tag', '')) for tag in tags_before_pv}
                                                    tags_after_names = {tag.get('tag_name', tag.get('tag', '')) for tag in tags_after_pv}
                                                    gained_tags = tags_after_names - tags_before_names
                                                    lost_tags = tags_before_names - tags_after_names
                                                    
                                                    # NEW: Calculate role changes
                                                    roles_before_set = set()
                                                    for piece_id, roles_list in roles_before_pv.items():
                                                        for role in roles_list:
                                                            roles_before_set.add(f"{piece_id}:{role}")
                                                    
                                                    roles_after_set = set()
                                                    for piece_id, roles_list in roles_after_pv.items():
                                                        for role in roles_list:
                                                            roles_after_set.add(f"{piece_id}:{role}")
                                                    
                                                    gained_roles = roles_after_set - roles_before_set
                                                    lost_roles = roles_before_set - roles_after_set
                                                    
                                                    # Get themes
                                                    themes = []
                                                    if pv_light_raw_after:
                                                        themes = pv_light_raw_after.top_themes[:3] if pv_light_raw_after.top_themes else []
                                                    
                                                    # Get tactic
                                                    tactic = "none"
                                                    if gained_tags:
                                                        # Check for tactical tags
                                                        for tag_name in gained_tags:
                                                            if 'tactic' in tag_name.lower() or 'fork' in tag_name.lower() or 'pin' in tag_name.lower():
                                                                tactic = self._humanize_tag(tag_name) or "none"
                                                                break
                                                    
                                                    # Add move to branch variation
                                                    print(f"         🔍 [PGN_BUILD] Attempting to add PV move to branch node...")
                                                    print(f"            Branch node type: {type(branch_node)}")
                                                    print(f"            PV move: {pv_move} (UCI: {pv_move.uci()}, SAN: {pv_move_san})")
                                                    try:
                                                        branch_node_board_before = branch_node.board()
                                                        print(f"            Branch node board BEFORE add_variation: {branch_node_board_before.fen()}")
                                                    except:
                                                        pass
                                                    
                                                    pv_node = branch_node.add_variation(pv_move)
                                                    print(f"         ✅ PV move added to branch node successfully")
                                                    
                                                    try:
                                                        pv_node_board = pv_node.board()
                                                        print(f"            PV node board AFTER add_variation: {pv_node_board.fen()}")
                                                    except:
                                                        pass
                                                    
                                                    # Update branch_node for next iteration
                                                    branch_node = pv_node
                                                    
                                                    # Build annotation
                                                    pv_annotation = []
                                                    if branch_eval_d16 is not None and pv_idx == 0:
                                                        pv_annotation.append(f"[%eval {branch_eval_d16:+.2f}]")
                                                    
                                                    if themes:
                                                        pv_annotation.append(f"[%theme \"{','.join(themes)}\"]")
                                                    
                                                    if tactic != "none":
                                                        pv_annotation.append(f"[%tactic \"{tactic}\"]")
                                                    
                                                    # Build commentary with roles
                                                    gained_str = ', '.join([self._humanize_tag(t) or t for t in list(gained_tags)[:10]]) if gained_tags else 'none'
                                                    lost_str = ', '.join([self._humanize_tag(t) or t for t in list(lost_tags)[:10]]) if lost_tags else 'none'
                                                    
                                                    # NEW: Format roles gained and lost
                                                    roles_gained_formatted = []
                                                    for role_key in list(gained_roles)[:10]:
                                                        if ":" in role_key:
                                                            piece_id, role = role_key.split(":", 1)
                                                            parts = piece_id.split("_")
                                                            if len(parts) >= 3:
                                                                piece_type = parts[1]
                                                                square = parts[2]
                                                                roles_gained_formatted.append(f"{piece_type}_{square}:{role}")
                                                            else:
                                                                roles_gained_formatted.append(role_key)
                                                        else:
                                                            roles_gained_formatted.append(role_key)
                                                    
                                                    roles_lost_formatted = []
                                                    for role_key in list(lost_roles)[:10]:
                                                        if ":" in role_key:
                                                            piece_id, role = role_key.split(":", 1)
                                                            parts = piece_id.split("_")
                                                            if len(parts) >= 3:
                                                                piece_type = parts[1]
                                                                square = parts[2]
                                                                roles_lost_formatted.append(f"{piece_type}_{square}:{role}")
                                                            else:
                                                                roles_lost_formatted.append(role_key)
                                                        else:
                                                            roles_lost_formatted.append(role_key)
                                                    
                                                    roles_gained_str = ', '.join(roles_gained_formatted) if roles_gained_formatted else 'none'
                                                    roles_lost_str = ', '.join(roles_lost_formatted) if roles_lost_formatted else 'none'
                                                    
                                                    pv_comment = ' '.join(pv_annotation)
                                                    if gained_str != 'none' or lost_str != 'none' or roles_gained_str != 'none' or roles_lost_str != 'none':
                                                        pv_comment += f" {{[gained: {gained_str}], [lost: {lost_str}], [roles_gained: {roles_gained_str}], [roles_lost: {roles_lost_str}], [threats: none]}}"
                                                    
                                                    pv_node.comment = pv_comment
                                                    
                                                    # Update tags_before and roles_before for next iteration
                                                    tags_before_pv = tags_after_pv
                                                    roles_before_pv = roles_after_pv
                                                else:
                                                    break
                                            except Exception as e:
                                                print(f"   ⚠️ [INVESTIGATOR] Error adding PV move {pv_move_san} to stopped branch: {e}")
                                                break
                                        
                                        # Add final comment about stop reason
                                        if branch_eval_d16 is not None:
                                            branch_node.comment += f" Final eval: {branch_eval_d16:+.2f}."
                                    else:
                                        # No PV available, just add comment
                                        if branch_eval_d16 is not None:
                                            branch_node.comment += f" Final eval: {branch_eval_d16:+.2f}."
                        except Exception as e:
                            print(f"   ⚠️ [INVESTIGATOR] Error adding branch {branch_move} to PGN: {e}")
                            import traceback
                            traceback.print_exc()
                            pass
        except Exception:
            pass
    
    def _generate_commentary(
        self,
        exploration_tree: Dict[str, Any],
        light_raw: Optional[LightRawAnalysis]
    ) -> Dict[str, str]:
        """
        Generate move-by-move commentary from exploration tree.
        
        Args:
            exploration_tree: Tree structure
            light_raw: Light raw analysis
            
        Returns:
            Dict mapping move SAN to commentary string
        """
        commentary = {}
        
        best_move_d16 = exploration_tree.get("best_move_d16")
        if best_move_d16:
            comment_parts = ["Best move (D16)."]
            if light_raw and light_raw.top_themes:
                comment_parts.append(f"Themes: {', '.join(light_raw.top_themes[:3])}.")
            root_threats = exploration_tree.get("threat_tags", [])
            if root_threats:
                comment_parts.append(f"Threat: {root_threats[0]}.")
            commentary[best_move_d16] = " ".join(comment_parts)
        
        # Add commentary for branches
        for branch in exploration_tree.get("branches", []):
            move_played = branch.get("move_played")
            if move_played:
                branch_comment = "D2 overestimates."
                branch_threats = branch.get("threat_tags", [])
                if branch_threats:
                    branch_comment += f" Threat: {branch_threats[0]}."
                commentary[move_played] = branch_comment
        
        return commentary

