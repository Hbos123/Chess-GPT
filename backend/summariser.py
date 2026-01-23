"""
Summariser - Editorial Intelligence
Purpose: Choose what to say, not why it's true.
FORBIDDEN: Engine calls, chess analysis, mentioning moves not in input
"""

import json
import re
import chess
import chess.pgn
import os
from typing import Dict, Any, List, Optional, Tuple, TYPE_CHECKING, Literal
from dataclasses import dataclass, field
from openai import OpenAI
from investigator import InvestigationResult
from evidence_semantic_story import build_semantic_story
from minimal_prompts import MIN_SYSTEM_PROMPT_V1, SUMMARISER_CONTRACT_V1
from command_protocol import render_command

if TYPE_CHECKING:
    from planner import ExecutionPlan


@dataclass
class ClaimEvidencePayload:
    """
    Optional rich evidence payload for a claim.
    Must be referential: selected/copied from InvestigationResult only (no invention).
    """
    pgn_line: Optional[str] = None
    pgn_moves: List[str] = field(default_factory=list)  # Full SAN sequence used as evidence (starts with the player's move when applicable)
    theme_tags: List[str] = field(default_factory=list)
    raw_tags: List[str] = field(default_factory=list)
    two_move: Optional[Dict[str, Any]] = None  # Tag/tactics snippet for quick reference
    fen_snapshot: Optional[str] = None  # Only if available from upstream facts
    eval_before: Optional[float] = None
    eval_after: Optional[float] = None
    eval_drop: Optional[float] = None
    material_change: Optional[float] = None  # In pawns (positive = better for White)
    # NEW: Eval decomposition along the evidence line (all pawns, + for White)
    evidence_eval_start: Optional[float] = None
    evidence_eval_end: Optional[float] = None
    evidence_eval_delta: Optional[float] = None
    evidence_material_start: Optional[float] = None
    evidence_material_end: Optional[float] = None
    evidence_positional_start: Optional[float] = None
    evidence_positional_end: Optional[float] = None
    tactic_tags: List[str] = field(default_factory=list)  # From Investigator tactics_found (not TwoMove)
    # NEW: Net changes from following the PGN sequence from start to end
    tags_gained_net: List[str] = field(default_factory=list)  # Net tags gained after following the sequence
    tags_lost_net: List[str] = field(default_factory=list)  # Net tags lost after following the sequence
    # NEW: Structured tag instances for net changes (preserves squares/pieces/details for grouping)
    tags_gained_net_structured: List[Dict[str, Any]] = field(default_factory=list)
    tags_lost_net_structured: List[Dict[str, Any]] = field(default_factory=list)
    roles_gained_net: List[str] = field(default_factory=list)  # NEW: Net roles gained after following the sequence
    roles_lost_net: List[str] = field(default_factory=list)  # NEW: Net roles lost after following the sequence
    material_change_net: Optional[float] = None  # Net material change after following the sequence (in pawns)
    # NEW: Eval breakdown (material and positional balance) that fundamentally informs the claim
    key_eval_breakdown: Optional[Dict[str, Any]] = None  # Material and positional balance before/after

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pgn_line": self.pgn_line,
            "pgn_moves": self.pgn_moves,
            "theme_tags": self.theme_tags,
            "raw_tags": self.raw_tags,
            "two_move": self.two_move,
            "fen_snapshot": self.fen_snapshot,
            "eval_before": self.eval_before,
            "eval_after": self.eval_after,
            "eval_drop": self.eval_drop,
            "material_change": self.material_change,
            "evidence_eval_start": self.evidence_eval_start,
            "evidence_eval_end": self.evidence_eval_end,
            "evidence_eval_delta": self.evidence_eval_delta,
            "evidence_material_start": self.evidence_material_start,
            "evidence_material_end": self.evidence_material_end,
            "evidence_positional_start": self.evidence_positional_start,
            "evidence_positional_end": self.evidence_positional_end,
            "tactic_tags": self.tactic_tags,
            "tags_gained_net": self.tags_gained_net,
            "tags_lost_net": self.tags_lost_net,
            "tags_gained_net_structured": self.tags_gained_net_structured,
            "tags_lost_net_structured": self.tags_lost_net_structured,
            "roles_gained_net": self.roles_gained_net,  # NEW
            "roles_lost_net": self.roles_lost_net,  # NEW
            "material_change_net": self.material_change_net,
            "key_eval_breakdown": self.key_eval_breakdown,  # NEW
        }


ClauseRole = Literal[
    "hook",
    "mechanism",
    "position_comparison",
    "candidate_moves",
    "comparison",
    "consequence",
    "recommendation",
    "takeaway",
    "detail",
]


@dataclass
class RenderHints:
    """Rendering hints for the Explainer / frontend (does not change truth)."""
    role: ClauseRole = "detail"
    priority: int = 2  # 1=must include, 2=include, 3=optional detail
    inline_pgn: bool = False
    show_theme_tags: bool = False
    show_two_move: bool = False
    show_board: bool = False  # Only if fen_snapshot exists

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "priority": self.priority,
            "inline_pgn": self.inline_pgn,
            "show_theme_tags": self.show_theme_tags,
            "show_two_move": self.show_two_move,
            "show_board": self.show_board,
        }


@dataclass
class Claim:
    """
    Evidence-locked claim abstraction (generic, position-agnostic).
    
    Rules:
    - connector MUST be None unless evidence_moves exists
    - summary MUST make sense without causality
    - Claims are position-agnostic
    - claim_type is a generic classification label (not position-specific)
    """
    summary: str  # Descriptive, non-causal sentence (e.g., "This move is problematic")
    claim_type: str  # Generic classification label (e.g., "positional_concession", "tactical_opportunity", "development_issue")
    connector: Optional[str] = None  # None | "because" | "allows" | "leads_to" | "causes" | "results_in" | "therefore" | "so_that" | "which_means"
    evidence_moves: Optional[List[str]] = None  # SAN moves proving the causality (2-4 plies max)
    evidence_source: Optional[str] = None  # "pv" | "pgn" | "validated"
    evidence_payload: Optional[ClaimEvidencePayload] = None
    hints: RenderHints = field(default_factory=RenderHints)
    
    def __post_init__(self):
        """Enforce invariant: connector requires evidence_moves"""
        if self.connector and not self.evidence_moves:
            # Mandatory downgrade: remove causality if evidence missing
            self.connector = None
            self.evidence_source = None
        # Enforce invariant: show_board requires fen_snapshot
        if self.hints.show_board and not (self.evidence_payload and self.evidence_payload.fen_snapshot):
            self.hints.show_board = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "summary": self.summary,
            "connector": self.connector,
            "evidence_moves": self.evidence_moves,
            "evidence_source": self.evidence_source,
            "claim_type": self.claim_type,
            "evidence_payload": self.evidence_payload.to_dict() if self.evidence_payload else None,
            "hints": self.hints.to_dict() if self.hints else None,
        }


@dataclass
class RefinedPGN:
    """Curated PGN with only relevant branches"""
    pgn: str  # Refined PGN string
    key_branches: List[Dict[str, Any]] = field(default_factory=list)  # Selected branches with metadata
    themes: List[str] = field(default_factory=list)  # Key themes identified
    tactical_highlights: List[str] = field(default_factory=list)  # Tactical opportunities
    moves_of_interest: List[str] = field(default_factory=list)  # Moves from execution plan
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "pgn": self.pgn,
            "key_branches": self.key_branches,
            "themes": self.themes,
            "tactical_highlights": self.tactical_highlights,
            "moves_of_interest": self.moves_of_interest
        }


@dataclass
class NarrativeDecision:
    """What to say and how to frame it"""
    core_message: str  # One sentence summary
    mechanism: str  # MANDATORY: Concrete board-level mechanism explaining how the move works
    mechanism_evidence: Optional[Dict[str, Any]] = None  # Evidence linking mechanism to PV/PGN/board_check
    claims: List[Claim] = field(default_factory=list)  # NEW: Evidence-locked claims (replaces free-form causal text)
    emphasis: List[str] = field(default_factory=list)  # Facts to emphasize (max 2)
    psychological_frame: str = "reasonable idea, wrong moment"  # MANDATORY: How to frame it psychologically
    takeaway: Optional[Claim] = None  # NEW: Takeaway as a Claim object (allows evidence binding)
    verbosity: str = "medium"  # "brief" | "medium" | "detailed"
    suppress: List[str] = field(default_factory=list)  # Facts to NOT mention (code-enforced)
    refined_pgn: Optional[RefinedPGN] = None  # Curated PGN
    # NEW: Pre-cooked clause template for Explainer (deterministic plan, evidence-locked)
    explainer_template: Optional[Dict[str, Any]] = None
    # NEW: LLM-selected PGN sequences that prove the narrative
    pgn_sequences_to_extract: List[Dict[str, Any]] = field(default_factory=list)  # [{start_move, end_move, reason, proves}]
    # NEW: Worded PGN (LLM-generated SAN→words narration with per-move FEN+stats+deltas)
    worded_pgn: Optional[Dict[str, Any]] = None
    # NEW: Explicit original PGN context used for grounding (evidence line + full exploration if available)
    original_pgn_context: Optional[Dict[str, Any]] = None
    # NEW: Discussion agenda from planner (for explainer to structure response)
    discussion_agenda: List[Dict[str, Any]] = field(default_factory=list)  # Planner-provided agenda questions
    # NEW: Motif/pattern summary (deterministic, user-facing phrasing; no tag.* leakage)
    pattern_summary: Optional[str] = None
    # NEW: Structured top patterns (safe subset of motifs) for UI and explainer
    patterns_top: List[Dict[str, Any]] = field(default_factory=list)
    # NEW: Patterns as claim-like objects for UI rendering (summary + evidence payload + eval deltas)
    pattern_claims: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "core_message": self.core_message,
            "mechanism": self.mechanism,
            "mechanism_evidence": self.mechanism_evidence,
            "claims": [claim.to_dict() for claim in self.claims],
            "emphasis": self.emphasis,
            "psychological_frame": self.psychological_frame,
            "takeaway": self.takeaway.to_dict() if self.takeaway else None,
            "verbosity": self.verbosity,
            "suppress": self.suppress,
            "refined_pgn": self.refined_pgn.to_dict() if self.refined_pgn else None,
            "explainer_template": self.explainer_template,
            "pgn_sequences_to_extract": self.pgn_sequences_to_extract,
            "worded_pgn": self.worded_pgn,
            "original_pgn_context": self.original_pgn_context,
            "discussion_agenda": self.discussion_agenda,
            "pattern_summary": self.pattern_summary,
            "patterns_top": self.patterns_top,
            "pattern_claims": self.pattern_claims,
        }


class Summariser:
    """
    Editorial Intelligence - Decides meaning, not truth.
    Takes investigator facts and decides what matters.
    """
    
    def __init__(self, openai_client: OpenAI, llm_router=None):
        """
        Initialize Summariser with OpenAI client.
        
        Args:
            openai_client: OpenAI client instance
        """
        self.client = openai_client
        self.llm_router = llm_router
        # Model is configurable so we can dial cost/quality.
        # Default to cheaper model; `summarise()` includes a retry + fallback guard for reliability.
        self.model = os.getenv("SUMMARISER_MODEL", "gpt-5-mini")
        self.fallback_model = os.getenv("SUMMARISER_FALLBACK_MODEL", "gpt-5")
        try:
            self.max_retries = int(os.getenv("SUMMARISER_MAX_RETRIES", "1"))
        except Exception:
            self.max_retries = 1
        # Debug/audit: last LLM I/O (prompts + raw response texts + parsed JSON)
        self._audit_llm_io: Dict[str, Any] = {}
        # Speed: memoize PGN tag-delta extraction (pure function of pgn_exploration)
        self._pgn_tag_deltas_cache: Dict[str, List[Dict[str, Any]]] = {}
        # Tag importance hierarchy (HIGH > MEDIUM > LOW) — used by _rank_and_suppress_tag_deltas.
        # Missing this breaks the summariser and forces main.py fallback.
        self.tag_importance = {
            # HIGH: critical safety and tactics/material
            "tag.king": "HIGH",
            "tag.mate": "HIGH",
            "tag.tactic": "HIGH",
            "tag.material": "HIGH",
            "tag.check": "HIGH",
            "tag.capture": "HIGH",
            "tag.threat": "HIGH",
            # MEDIUM: development / structure / initiative / castling
            "tag.development": "MEDIUM",
            "tag.castling": "MEDIUM",
            "tag.piece": "MEDIUM",
            "tag.overworked": "MEDIUM",
            "tag.pawn": "MEDIUM",
            "tag.space": "MEDIUM",
            "tag.center": "MEDIUM",
            # LOW: geometric/positional descriptors that are often noisy in explanations
            "tag.diagonal": "LOW",
            "tag.file": "LOW",
            "tag.key": "LOW",
            "tag.activity": "LOW",
            "tag.color.hole": "LOW",
            "tag.lever": "LOW",
        }
        # Relaxed mode = minimal constraints, more LLM freedom (can tighten later).
        # Default: RELAXED (true). Set STRICT_LLM_MODE=true to re-enable forced behaviors.
        strict = os.getenv("STRICT_LLM_MODE", "").lower().strip() == "true"
        self.relaxed_llm_mode = not strict

    def _build_pattern_summary_from_motifs(
        self,
        motifs: Any,
        *,
        top_n: int = 6,
    ) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        """
        Deterministic, user-facing pattern summary derived from motif mining.
        Output MUST NOT leak raw tag.* / role.* identifiers (motif signatures can contain those).
        Returns: (summary_text, patterns_top_structured)
        """
        try:
            import re
        except Exception:
            re = None  # type: ignore

        if not isinstance(motifs, list) or not motifs:
            return (None, [])

        # Rank deterministically: count_total desc, then significance desc, then signature.
        def _score(m: Dict[str, Any]) -> Tuple[int, float, str]:
            loc = m.get("location") if isinstance(m, dict) else None
            ct = 0
            try:
                ct = int((loc or {}).get("count_total") or 0) if isinstance(loc, dict) else int(m.get("count_total") or 0)
            except Exception:
                ct = 0
            try:
                sigv = float(m.get("significance") or 0.0)
            except Exception:
                sigv = 0.0
            sig = ""
            try:
                sig = str(((m.get("pattern") or {}) if isinstance(m.get("pattern"), dict) else {}).get("signature") or m.get("signature") or "")
            except Exception:
                sig = ""
            return (ct, sigv, sig)

        ms = [m for m in motifs if isinstance(m, dict)]
        ms.sort(key=_score, reverse=True)
        ms = ms[: max(1, int(top_n))]

        def _extract_san(signature: str) -> List[str]:
            if not signature or not re:
                return []
            # signature often contains "SAN:<move>" segments; keep only those.
            # NOTE: place '-' at the end of the character class to avoid regex range ambiguity.
            return re.findall(r"SAN:([A-Za-z0-9O+=#\\-]+)", signature)[:6]

        def _coarse_phrase(signature: str) -> str:
            # Prefer SAN list; otherwise fall back to a scrubbed/truncated signature.
            sans = _extract_san(signature)
            if sans:
                return " → ".join(sans)
            if not signature:
                return "(pattern)"
            # Strip tag/role identifiers if present.
            out = signature
            out = re.sub(r"\\btag\\.[a-z0-9_.]+\\b", "", out, flags=re.IGNORECASE) if re else out
            out = re.sub(r"\\brole\\.[a-z0-9_.]+\\b", "", out, flags=re.IGNORECASE) if re else out
            out = re.sub(r"\\s+", " ", out).strip() if re else out.strip()
            return out[:140] + ("..." if len(out) > 140 else "")

        patterns_top: List[Dict[str, Any]] = []
        lines: List[str] = []
        seen_phrases: set = set()
        for m in ms:
            sig = str(((m.get("pattern") or {}) if isinstance(m.get("pattern"), dict) else {}).get("signature") or m.get("signature") or "")
            loc = m.get("location") if isinstance(m, dict) else None
            ct = (loc or {}).get("count_total") if isinstance(loc, dict) else m.get("count_total")
            cls = m.get("classification") or m.get("class")
            phrase = _coarse_phrase(sig)
            if phrase in seen_phrases:
                continue
            seen_phrases.add(phrase)
            try:
                ct_i = int(ct) if ct is not None else 0
            except Exception:
                ct_i = 0

            patterns_top.append({
                "phrase": phrase,
                "count_total": ct_i,
                "classification": str(cls) if cls else None,
            })
            if ct_i > 0:
                lines.append(f"- {phrase} (seen {ct_i}×){f' [{cls}]' if cls else ''}")
            else:
                lines.append(f"- {phrase}{f' [{cls}]' if cls else ''}")

        summary = "Patterns (recurring motifs across branches):\n" + "\n".join(lines)
        return (summary, patterns_top)

    def _find_overworked_exploitation(
        self,
        investigation_result: Any,
    ) -> Optional[Dict[str, Any]]:
        """
        Strict detector for "overworked piece was exploited".
        We ONLY consider it exploited if, on the SAME ply where an overworked-tag instance disappears,
        at least one of the defended targets becomes `tag.threat.capture.undefended` (attacked with 0 defenders).

        Returns a small evidence dict (or None):
          {
            "defender_square": "d1",
            "targets_became_undefended": ["e2", ...],
          }
        """
        try:
            per_move = getattr(investigation_result, "evidence_per_move_deltas", None)
        except Exception:
            per_move = None
        if not isinstance(per_move, list) or not per_move:
            return None

        hits: Dict[str, set] = {}
        for mv in per_move:
            if not isinstance(mv, dict):
                continue
            lost_struct = mv.get("tags_lost_structured") or []
            gained_struct = mv.get("tags_gained_structured") or []
            if not isinstance(lost_struct, list) or not isinstance(gained_struct, list):
                continue

            # Collect any "capture undefended" targets that appear on this ply.
            undef_targets: set = set()
            for t in gained_struct:
                if not isinstance(t, dict):
                    continue
                if str(t.get("tag_name") or "") != "tag.threat.capture.undefended":
                    continue
                tsq = t.get("target_square") or (t.get("squares")[0] if isinstance(t.get("squares"), list) and t.get("squares") else None)
                if isinstance(tsq, str) and tsq:
                    undef_targets.add(tsq)
            if not undef_targets:
                continue

            # For each overworked instance that is LOST on this ply, check if any defended piece became undefended.
            for t in lost_struct:
                if not isinstance(t, dict):
                    continue
                tn = str(t.get("tag_name") or "")
                if not tn.startswith("tag.piece.overworked."):
                    continue
                defender_square = tn.split(".")[-1] if "." in tn else None
                defended = t.get("defended_pieces") or []
                if not isinstance(defender_square, str) or not defender_square:
                    continue
                if not isinstance(defended, list) or not defended:
                    continue
                defended_sqs = {dp.get("square") for dp in defended if isinstance(dp, dict) and isinstance(dp.get("square"), str)}
                became = sorted(list(defended_sqs.intersection(undef_targets)))
                if became:
                    if defender_square not in hits:
                        hits[defender_square] = set()
                    for sq in became:
                        hits[defender_square].add(sq)

        if not hits:
            return None
        # Return the strongest single defender (most targets became undefended), deterministic tie-break by square.
        best_def = sorted(hits.items(), key=lambda kv: (len(kv[1]), kv[0]), reverse=True)[0]
        return {
            "defender_square": best_def[0],
            "targets_became_undefended": sorted(list(best_def[1])),
        }
        
        # Tag importance hierarchy (HIGH > MEDIUM > LOW)
        self.tag_importance = {
            # HIGH: Critical safety and material
            "tag.king": "HIGH",
            "tag.mate": "HIGH",
            "tag.tactic": "HIGH",
            "tag.material": "HIGH",
            "tag.check": "HIGH",
            "tag.capture": "HIGH",
            # MEDIUM: Structural and positional
            "tag.pawn": "MEDIUM",
            "tag.structure": "MEDIUM",
            "tag.pin": "MEDIUM",
            "tag.overworked": "MEDIUM",
            # LOW: Space and activity
            "tag.space": "LOW",
            "tag.activity": "LOW",
            "tag.center": "LOW",
            "tag.file": "LOW",
            "tag.diagonal": "LOW"
        }

    # ---------------------------------------------------------------------
    # Primary vs secondary context helpers (to keep prompts compact)
    # ---------------------------------------------------------------------

    def _is_major_tag_name(self, tag_name: str) -> bool:
        """
        Major tags are high-level, easy-to-ground concepts that should be shown first.
        Geometry/micro-structure tags (diagonals/files/etc.) are treated as secondary context.
        """
        if not tag_name or not isinstance(tag_name, str):
            return False

        # Explicit major tags
        if tag_name in {
            "tag.bishop.pair",
            "tag.piece.trapped",
        }:
            return True

        major_prefixes = (
            "tag.square.outpost.",
            "tag.undeveloped.",
            "tag.pawn.passed",
            "tag.pawn.isolated",
            "tag.pawn.backward",
            "tag.pawn.hanging",
            "tag.battery.",
            "tag.king.",  # keep king-safety major
            "tag.mate",
            "tag.tactic.",
            "tag.threat.",
        )
        if tag_name.startswith(major_prefixes):
            return True

        # CLUTTERING TAGS - Exclude from explanations entirely (too verbose, not significant)
        cluttering_prefixes = (
            "tag.diagonal.",      # Diagonal control tags (too granular)
            "tag.file.",          # File control tags (too granular)
            "tag.key.",           # Key square tags (too granular)
            "tag.center.",        # Center control tags (too granular, use themes instead)
            "tag.activity.",      # Activity tags (too granular)
            "tag.lever.",         # Lever tags (too granular)
            "tag.color.hole.",    # Color hole tags (too granular)
        )
        if tag_name.startswith(cluttering_prefixes):
            return False

        # Default: treat unknown tags as secondary to avoid prompt bloat
        return False

    def _is_major_role_name(self, role_name: str) -> bool:
        if not role_name or not isinstance(role_name, str):
            return False
        major_role_prefixes = (
            "role.status.",          # hanging / trapped / under/over-defended
            "role.tactical.",        # pinned / fork etc.
            "role.attacking.",       # overloaded, attack lines
            "role.control.outpost",  # outpost role
            "role.position.edge",    # knight on edge
            "role.blocking_development",
            "role.defending.king",
        )
        return role_name.startswith(major_role_prefixes)

    def _is_good_to_lose_tag(self, tag_name: str) -> bool:
        """Check if losing this tag is actually good (e.g., undeveloped.knight → developed)."""
        if not tag_name or not isinstance(tag_name, str):
            return False
        good_to_lose_prefixes = (
            "tag.undeveloped.",
            "tag.piece.trapped",
            "tag.king.center.exposed",
            "tag.king.shield.missing",
            "tag.pawn.backward",
            "tag.pawn.isolated",
            "tag.bishop.bad",
        )
        return any(tag_name.startswith(prefix) for prefix in good_to_lose_prefixes)

    def _compute_tag_competition(
        self,
        tags_lost_net: List[str],
        evidence_eval: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compute competition between "good to lose" tags and "bad to lose" tags.
        Uses eval breakdown to determine which side wins and by how much.
        
        Returns:
            {
                "good_tags_lost": List[str],  # Tags that are good to lose
                "bad_tags_lost": List[str],    # Tags that are bad to lose
                "net_eval_delta": float,       # Overall eval change (negative = bad)
                "positional_delta": float,     # Positional eval change
                "winner": "good"|"bad"|"neutral",  # Which side wins
                "margin": float,               # How much the winner wins by (in pawns)
                "interpretation": str          # Human-readable interpretation
            }
        """
        good_tags_lost = [t for t in tags_lost_net if self._is_good_to_lose_tag(t)]
        bad_tags_lost = [t for t in tags_lost_net if not self._is_good_to_lose_tag(t)]
        
        # Extract eval breakdown
        eval_delta = None
        positional_delta = None
        if evidence_eval:
            eval_delta = evidence_eval.get("eval_delta")
            positional_start = evidence_eval.get("positional_start")
            positional_end = evidence_eval.get("positional_end")
            if positional_start is not None and positional_end is not None:
                positional_delta = positional_end - positional_start
        
        # Determine winner based on eval breakdown
        # Negative eval_delta = position got worse (bad tags won)
        # Positive eval_delta = position got better (good tags won)
        winner = "neutral"
        margin = 0.0
        
        if eval_delta is not None:
            # Use positional delta if available (more accurate for tag-based changes)
            # Otherwise use total eval delta
            delta_to_use = positional_delta if positional_delta is not None else eval_delta
            
            if abs(delta_to_use) < 0.3:  # Roughly equal
                winner = "neutral"
                margin = abs(delta_to_use)
            elif delta_to_use < 0:  # Position got worse
                winner = "bad"
                margin = abs(delta_to_use)
            else:  # Position got better
                winner = "good"
                margin = delta_to_use
        
        # Build interpretation
        interpretation_parts = []
        if good_tags_lost:
            good_desc = ", ".join([t.replace("tag.", "").replace(".", " ") for t in good_tags_lost[:3]])
            interpretation_parts.append(f"Good: {good_desc}")
        if bad_tags_lost:
            bad_desc = ", ".join([t.replace("tag.", "").replace(".", " ") for t in bad_tags_lost[:3]])
            interpretation_parts.append(f"Bad: {bad_desc}")
        
        if winner == "bad" and margin >= 0.5:
            interpretation = f"While {'; '.join(interpretation_parts)}, the negative changes dominate (cost: {margin:.2f} pawns)"
        elif winner == "good" and margin >= 0.5:
            interpretation = f"{'; '.join(interpretation_parts)} - positive changes dominate (gain: {margin:.2f} pawns)"
        elif winner == "neutral" or margin < 0.5:
            interpretation = f"{'; '.join(interpretation_parts)} - roughly balanced (net: {margin:.2f} pawns)"
        else:
            interpretation = "; ".join(interpretation_parts) if interpretation_parts else "No significant tag changes"
        
        return {
            "good_tags_lost": good_tags_lost,
            "bad_tags_lost": bad_tags_lost,
            "net_eval_delta": eval_delta,
            "positional_delta": positional_delta,
            "winner": winner,
            "margin": margin,
            "interpretation": interpretation
        }

    def _piece_map_from_fen(self, fen: Optional[str]) -> Dict[str, str]:
        """
        Map square_name -> piece_id (color_pieceType_square) for a given FEN.
        """
        if not fen or not isinstance(fen, str):
            return {}
        try:
            b = chess.Board(fen)
            out: Dict[str, str] = {}
            for sq in chess.SQUARES:
                p = b.piece_at(sq)
                if not p:
                    continue
                color = "white" if p.color == chess.WHITE else "black"
                piece_type = chess.piece_name(p.piece_type)
                sq_name = chess.square_name(sq)
                out[sq_name] = f"{color}_{piece_type}_{sq_name}"
            return out
        except Exception:
            return {}

    def _build_organized_pgn_structure(
        self,
        investigation_result: InvestigationResult,
        evidence_eval: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Build organized PGN structure with per-move data for the summariser.
        
        Returns:
            Dict with:
                - starting_position: {eval, material, positional, tags, roles}
                - moves: [{move, eval, material, positional, tag_delta, role_delta}, ...]
                - ending_position: {eval, material, positional, tags, roles}
                - alternate_branches: [...] (if available)
        """
        try:
            # Get starting position info
            starting_fen = getattr(investigation_result, "evidence_starting_fen", None)
            moves = getattr(investigation_result, "evidence_main_line_moves", []) or []
            per_move_deltas = getattr(investigation_result, "evidence_per_move_deltas", []) or []
            per_move_stats = getattr(investigation_result, "evidence_per_move_stats", []) or []
            
            if not starting_fen or not moves:
                return None

            # Compute starting/ending tags+roles deterministically from FEN (no LLM, no engine)
            try:
                from light_raw_analyzer import compute_light_raw_analysis
                start_lr = compute_light_raw_analysis(starting_fen)
                end_fen = getattr(investigation_result, "evidence_end_fen", None)
                end_lr = compute_light_raw_analysis(end_fen) if end_fen else None
            except Exception:
                start_lr = None
                end_lr = None

            def _slim_structured_tags(tags: Any, *, max_items: int = 120) -> List[Dict[str, Any]]:
                if not isinstance(tags, list):
                    return []
                cluttering_prefixes = (
                    "tag.diagonal.", "tag.file.", "tag.key.", "tag.center.",
                    "tag.activity.", "tag.lever.", "tag.color.hole."
                )
                out: List[Dict[str, Any]] = []
                for t in tags:
                    if not isinstance(t, dict):
                        continue
                    tn = str(t.get("tag_name") or t.get("tag") or "")
                    if not tn:
                        continue
                    if any(tn.startswith(p) for p in cluttering_prefixes):
                        continue
                    out.append(t)
                    if len(out) >= max_items:
                        break
                return out

            def _slim_roles_map(roles: Any, *, max_pieces: int = 64, max_roles_per_piece: int = 12) -> Dict[str, List[str]]:
                if not isinstance(roles, dict):
                    return {}
                out: Dict[str, List[str]] = {}
                for i, (pid, rlist) in enumerate(roles.items()):
                    if i >= max_pieces:
                        break
                    if not isinstance(pid, str):
                        continue
                    if not isinstance(rlist, list):
                        continue
                    cleaned = [str(r) for r in rlist if r]
                    out[pid] = cleaned[:max_roles_per_piece]
                return out
            
            # Starting position data
            starting_position = {
                "fen": starting_fen,
                "eval": {
                    "total": getattr(investigation_result, "evidence_eval_start", None),
                    "material": getattr(investigation_result, "evidence_material_start", None),
                    "positional": getattr(investigation_result, "evidence_positional_start", None),
                },
                # Full starting tags/roles for grounding (can be large; summariser should select, not copy blindly)
                "tags": _slim_structured_tags(start_lr.tags if start_lr else []),
                "roles": _slim_roles_map(start_lr.roles if start_lr else {}),
            }
            
            # Build per-move data
            moves_data = []
            stats_by_ply = {}
            for s in per_move_stats:
                if isinstance(s, dict) and s.get("ply") is not None:
                    stats_by_ply[int(s["ply"])] = s

            for i, move in enumerate(moves):
                ply = i + 1
                move_data = {
                    "ply": ply,
                    "move_san": move,
                    # FENs for piece naming correctness
                    "fen_before": None,
                    "fen_after": None,
                    "tag_delta": {
                        "gained": [],
                        "lost": []
                    },
                    "role_delta": {
                        "gained": [],
                        "lost": []
                    }
                }
                
                # Get deltas for this move from per_move_deltas
                if i < len(per_move_deltas):
                    delta = per_move_deltas[i]
                    if isinstance(delta, dict):
                        move_data["fen_before"] = delta.get("fen_before")
                        move_data["fen_after"] = delta.get("fen_after")
                        move_data["tag_delta"]["gained"] = delta.get("tags_gained", [])
                        move_data["tag_delta"]["lost"] = delta.get("tags_lost", [])
                        move_data["role_delta"]["gained"] = delta.get("roles_gained", [])
                        move_data["role_delta"]["lost"] = delta.get("roles_lost", [])

                # Attach per-move stats if present
                s = stats_by_ply.get(ply)
                if isinstance(s, dict):
                    move_data["fen_before"] = move_data["fen_before"] or s.get("fen_before")
                    move_data["fen_after"] = move_data["fen_after"] or s.get("fen_after")
                
                moves_data.append(move_data)
            
            # Ending position data
            ending_position = {
                "fen": getattr(investigation_result, "evidence_end_fen", None),
                "eval": {
                    "total": getattr(investigation_result, "evidence_eval_end", None),
                    "material": getattr(investigation_result, "evidence_material_end", None),
                    "positional": getattr(investigation_result, "evidence_positional_end", None),
                },
                "tags": _slim_structured_tags(end_lr.tags if end_lr else []),
                "roles": _slim_roles_map(end_lr.roles if end_lr else {}),
            }
            
            return {
                "starting_position": starting_position,
                "moves": moves_data,
                "ending_position": ending_position,
                "alternate_branches": []  # Not currently extracted
            }
        except Exception as e:
            print(f"   ⚠️ [SUMMARISER] Error in _build_organized_pgn_structure: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _build_primary_context(
        self,
        inv: "InvestigationResult",
        *,
        tags_gained_net: List[str],
        tags_lost_net: List[str],
        tags_gained_net_structured: List[Dict[str, Any]],
        tags_lost_net_structured: List[Dict[str, Any]],
        roles_gained_net: List[str],
        roles_lost_net: List[str],
    ) -> Dict[str, Any]:
        """
        Primary context: roles + major tags, grouped by piece where possible.
        """
        start_map = self._piece_map_from_fen(getattr(inv, "evidence_starting_fen", None))
        end_map = self._piece_map_from_fen(getattr(inv, "evidence_end_fen", None))

        major_tags_gained = [t for t in tags_gained_net if self._is_major_tag_name(t)]
        major_tags_lost = [t for t in tags_lost_net if self._is_major_tag_name(t)]

        # Group role changes by piece_id (keep only major roles to reduce clutter)
        piece_ctx: Dict[str, Dict[str, Any]] = {}

        def _ensure_piece(pid: str) -> Dict[str, Any]:
            if pid not in piece_ctx:
                piece_ctx[pid] = {"piece_id": pid, "roles_gained": [], "roles_lost": [], "tags_gained": [], "tags_lost": []}
            return piece_ctx[pid]

        for r in roles_gained_net:
            if ":" not in r:
                continue
            pid, role_name = r.split(":", 1)
            if self._is_major_role_name(role_name):
                _ensure_piece(pid)["roles_gained"].append(role_name)

        for r in roles_lost_net:
            if ":" not in r:
                continue
            pid, role_name = r.split(":", 1)
            if self._is_major_role_name(role_name):
                _ensure_piece(pid)["roles_lost"].append(role_name)

        # Attach major tag instances to pieces when possible (by square)
        def _attach_structured(tags: List[Dict[str, Any]], *, dest_key: str, square_map: Dict[str, str]):
            for t in tags:
                if not isinstance(t, dict):
                    continue
                tn = t.get("tag_name") or t.get("tag") or ""
                if not self._is_major_tag_name(str(tn)):
                    continue
                squares = t.get("squares") or []
                if not isinstance(squares, list):
                    squares = [squares]
                attached = False
                for sq in squares:
                    pid = square_map.get(str(sq))
                    if pid:
                        _ensure_piece(pid)[dest_key].append(str(tn))
                        attached = True
                if not attached and squares:
                    # Leave as global if we couldn't map it to a piece_id
                    pass

        _attach_structured(tags_gained_net_structured, dest_key="tags_gained", square_map=end_map)
        _attach_structured(tags_lost_net_structured, dest_key="tags_lost", square_map=start_map)

        # Keep only pieces with any signal and cap to avoid prompt blow-up
        pieces_ranked = sorted(
            piece_ctx.values(),
            key=lambda d: (len(d.get("roles_gained", [])) + len(d.get("roles_lost", [])) + len(d.get("tags_gained", [])) + len(d.get("tags_lost", []))),
            reverse=True,
        )
        pieces_ranked = pieces_ranked[:12]

        # Major structural consequences (not tags) - keep concise
        consequences = getattr(inv, "consequences", None) or {}
        major_consequences = {}
        if isinstance(consequences, dict):
            if "doubled_pawns" in consequences:
                major_consequences["doubled_pawns"] = consequences.get("doubled_pawns")

        return {
            "major_tags_gained": major_tags_gained[:20],
            "major_tags_lost": major_tags_lost[:20],
            "major_consequences": major_consequences,
            "piece_context": pieces_ranked,
        }

    def _canonicalize_claims(self, claims: List["Claim"]) -> List["Claim"]:
        """
        Deduplicate/merge claims that represent the same idea but were produced by different pathways
        (e.g. llm_claims vs bind_evidence vs hammer/mechanism anchors).
        This prevents duplicated evidence payloads and prevents losing LLM key evidence.
        """
        if not claims:
            return []

        import re

        def _normalize_summary(s: Optional[str]) -> str:
            if not s:
                return ""
            s = s.strip().lower()
            # normalize whitespace
            s = re.sub(r"\s+", " ", s)
            # strip trailing punctuation
            s = s.rstrip(" .,!;:")
            # remove boilerplate prefixes to reduce trivial divergence
            for prefix in ("this move ", "this "):
                if s.startswith(prefix):
                    s = s[len(prefix):].strip()
                    break
            return s

        def _evidence_sig(c: "Claim") -> str:
            moves = getattr(c, "evidence_moves", None) or []
            if not isinstance(moves, list):
                return ""
            moves = [m for m in moves if isinstance(m, str)]
            return " ".join(moves[:4]).strip().lower()

        def _score(c: "Claim") -> int:
            score = 0
            connector = getattr(c, "connector", None)
            evidence_moves = getattr(c, "evidence_moves", None) or []
            if connector and isinstance(evidence_moves, list) and len(evidence_moves) >= 2:
                score += 100  # hammer-quality
            origin = getattr(c, "_origin", "")
            if origin == "llm_claims":
                score += 40
            src = getattr(c, "evidence_source", None) or ""
            if src == "pv":
                score += 20
            elif src == "pgn":  # Previously "two_move", now consolidated to "pgn"
                score += 15
            elif src == "evidence_index":
                score += 10
            ct = getattr(c, "claim_type", "") or ""
            if ct and ct != "general":
                score += 10
            payload = getattr(c, "evidence_payload", None)
            if payload is not None:
                score += 5
            return score

        def _merge_into(winner: "Claim", loser: "Claim") -> "Claim":
            # Prefer stronger evidence moves/source if winner lacks them
            if not getattr(winner, "evidence_moves", None) and getattr(loser, "evidence_moves", None):
                winner.evidence_moves = loser.evidence_moves
                winner.evidence_source = getattr(loser, "evidence_source", None)

            # Merge origin: keep winner origin, but annotate if we merged
            if not getattr(winner, "_origin_detail", None) and getattr(loser, "_origin", None):
                try:
                    winner._origin_detail = f"merged_from:{getattr(loser, '_origin', 'unknown')}"
                except Exception:
                    pass

            # Prefer higher-priority render hints if loser is more important (priority=1 is higher than 2)
            wh = getattr(winner, "hints", None)
            lh = getattr(loser, "hints", None)
            try:
                wprio = getattr(wh, "priority", None)
                lprio = getattr(lh, "priority", None)
                if wprio is None and lh is not None:
                    winner.hints = lh
                elif isinstance(wprio, int) and isinstance(lprio, int) and lprio < wprio:
                    winner.hints = lh
            except Exception:
                pass

            # Prefer richer payload if winner lacks it
            if getattr(winner, "evidence_payload", None) is None and getattr(loser, "evidence_payload", None) is not None:
                winner.evidence_payload = loser.evidence_payload

            return winner

        buckets: Dict[str, List["Claim"]] = {}
        for c in claims:
            summary_norm = _normalize_summary(getattr(c, "summary", None))
            conn = getattr(c, "connector", None) or "none"
            # Primary key: connector + normalized summary.
            # We intentionally do NOT key on evidence_moves, because duplicates often share the same summary but
            # arrive with different evidence binding pathways (pv vs evidence_index).
            key = f"{conn}::{summary_norm}"
            buckets.setdefault(key, []).append(c)

        canonical: List["Claim"] = []
        dropped = 0
        for key, group in buckets.items():
            if len(group) == 1:
                canonical.append(group[0])
                continue
            # pick best-scoring winner
            group_sorted = sorted(group, key=_score, reverse=True)
            winner = group_sorted[0]
            for loser in group_sorted[1:]:
                winner = _merge_into(winner, loser)
                dropped += 1
            canonical.append(winner)

        # Keep stable order: by hints priority first (if any), else original order fallback
        def _order_key(c: "Claim") -> Tuple[int, int]:
            prio = getattr(getattr(c, "hints", None), "priority", None)
            if not isinstance(prio, int):
                prio = 99
            return (prio, 0)

        canonical.sort(key=_order_key)
        if dropped:
            print(f"   🧹 [CLAIM_CANON] Dropped/merged {dropped} duplicate claim(s) (kept {len(canonical)})")
        return canonical

    def _infer_candidate_move_from_claim_text(self, text: Optional[str], candidate_moves: List[str]) -> Optional[str]:
        """
        Heuristic: infer which candidate move a claim is talking about by scanning its summary text.
        This is used ONLY for comparison-mode evidence binding, so alternate-move claims don't get
        accidentally grounded to the primary line.
        """
        if not text or not candidate_moves:
            return None
        t = text.strip()
        if not t:
            return None
        t_lower = t.lower()

        # Prefer exact SAN token match (case-insensitive).
        exact_matches: List[str] = []
        for mv in candidate_moves:
            if not isinstance(mv, str) or not mv:
                continue
            if mv.lower() in t_lower:
                exact_matches.append(mv)
        exact_matches = list(dict.fromkeys(exact_matches))
        if len(exact_matches) == 1:
            return exact_matches[0]

        # Secondary: if the summary mentions a specific destination square and a piece word,
        # map it back to a single candidate move with that destination.
        # Example: "knight to f3" -> candidate move "Nf3" if present.
        import re

        piece_word_for = {"n": "knight", "b": "bishop", "r": "rook", "q": "queen", "k": "king"}
        candidates: List[str] = []
        for mv in candidate_moves:
            if not isinstance(mv, str) or not mv:
                continue
            m = re.match(r"^([KQRBN])([a-h][1-8])$", mv)  # simple quiet moves only
            if not m:
                continue
            piece_letter, dest = m.group(1), m.group(2)
            word = piece_word_for.get(piece_letter.lower())
            if not word:
                continue
            # "knight ... f3" (allow any words in between)
            if re.search(rf"\b{re.escape(word)}\b[\s\S]{{0,40}}\b{re.escape(dest)}\b", t_lower):
                candidates.append(mv)
        candidates = list(dict.fromkeys(candidates))
        if len(candidates) == 1:
            return candidates[0]

        return None

    def _pick_result_for_claim_in_comparison(
        self,
        *,
        claim: "Claim",
        multiple_results: List[Dict[str, Any]],
        default_result: Optional["InvestigationResult"],
    ) -> Optional["InvestigationResult"]:
        """
        In comparison mode we have multiple investigated candidates (one per move).
        Bind each claim to the *right* candidate result so claims about alternate moves
        get their own PV/evidence line (instead of being overwritten by the primary line).
        """
        if not multiple_results:
            return default_result

        # Build candidate map by move SAN (player_move).
        candidate_map: Dict[str, InvestigationResult] = {}
        candidate_moves: List[str] = []
        for item in multiple_results:
            if not isinstance(item, dict):
                continue
            res = item.get("result")
            if not isinstance(res, InvestigationResult):
                continue
            mv = getattr(res, "player_move", None)
            if isinstance(mv, str) and mv:
                candidate_map[mv] = res
                candidate_moves.append(mv)

        candidate_moves = list(dict.fromkeys(candidate_moves))

        # First preference: claim.evidence_moves[0] matches a candidate move.
        em = getattr(claim, "evidence_moves", None) or []
        if isinstance(em, list) and em and isinstance(em[0], str):
            first = em[0]
            if first in candidate_map:
                return candidate_map[first]

        # Second preference: infer move from claim summary text (helps when LLM forgets to set evidence_moves correctly).
        inferred = self._infer_candidate_move_from_claim_text(getattr(claim, "summary", None), candidate_moves)
        if inferred and inferred in candidate_map:
            return candidate_map[inferred]

        # Fallback: default result (primary recommendation / first item).
        if default_result and isinstance(default_result, InvestigationResult):
            return default_result
        try:
            first_item = multiple_results[0]
            if isinstance(first_item, dict) and isinstance(first_item.get("result"), InvestigationResult):
                return first_item.get("result")
        except Exception:
            pass
        return None

    def _dedupe_claims_one_per_evidence_line(self, claims: List["Claim"]) -> List["Claim"]:
        """
        Enforce: at most ONE claim per attached evidence line (pgn_line).
        This prevents multiple claims from reusing the exact same PV/mainline.
        """
        if not claims:
            return []

        def _key(c: "Claim") -> str:
            payload = getattr(c, "evidence_payload", None)
            try:
                pgn_line = getattr(payload, "pgn_line", None) if payload else None
                if isinstance(pgn_line, str) and pgn_line.strip():
                    return pgn_line.strip()
            except Exception:
                pass
            # Fallback: evidence signature
            moves = getattr(c, "evidence_moves", None) or []
            if isinstance(moves, list):
                ms = [m for m in moves if isinstance(m, str)]
                if ms:
                    return " ".join(ms[:4]).strip()
            return "no_evidence"

        # Prefer claims with richer evidence payload/source.
        def _score(c: "Claim") -> int:
            score = 0
            origin = getattr(c, "_origin", "")
            if origin == "llm_claims":
                score += 20
            src = getattr(c, "evidence_source", None) or ""
            if src == "pv":
                score += 10
            elif src == "pgn":
                score += 8
            if getattr(c, "evidence_payload", None) is not None:
                score += 5
            # Prefer causal claims slightly, but don't require them.
            if getattr(c, "connector", None) and getattr(c, "evidence_moves", None):
                score += 2
            return score

        buckets: Dict[str, List["Claim"]] = {}
        order: List[str] = []
        for c in claims:
            k = _key(c)
            if k not in buckets:
                order.append(k)
            buckets.setdefault(k, []).append(c)

        out: List["Claim"] = []
        dropped = 0
        for k in order:
            group = buckets.get(k, [])
            if not group:
                continue
            if len(group) == 1:
                out.append(group[0])
                continue
            group_sorted = sorted(group, key=_score, reverse=True)
            out.append(group_sorted[0])
            dropped += (len(group_sorted) - 1)

        if dropped:
            print(f"   🧹 [CLAIM_LINE_DEDUPE] Dropped {dropped} claim(s) sharing the same evidence line")
        return out

    def _rewrite_claim_summary_from_evidence(self, claim: "Claim", *, lead: Optional[str] = None) -> "Claim":
        """
        Deterministic, evidence-first summary writer for fallback claims.
        Uses ONLY claim.evidence_payload fields (already grounded by Investigator).
        """
        payload = getattr(claim, "evidence_payload", None)
        if payload is None:
            return claim

        try:
            pgn_line = getattr(payload, "pgn_line", None)
            d_ev = getattr(payload, "evidence_eval_delta", None)
            ev0 = getattr(payload, "evidence_eval_start", None)
            ev1 = getattr(payload, "evidence_eval_end", None)
            tg = list(getattr(payload, "tags_gained_net", []) or [])
            tl = list(getattr(payload, "tags_lost_net", []) or [])

            def _pick(xs: List[str], n: int = 2) -> List[str]:
                out: List[str] = []
                for x in xs:
                    if isinstance(x, str) and x and x not in out:
                        out.append(x)
                    if len(out) >= n:
                        break
                return out

            def _pretty_tag(x: str) -> str:
                if not isinstance(x, str):
                    return ""
                t = x.strip()
                if t.startswith("tag."):
                    t = t[4:]
                return t.replace(".", " ").replace("_", " ").strip()

            gained = [_pretty_tag(x) for x in _pick(tg, 2)]
            gained = [x for x in gained if x]
            lost = [_pretty_tag(x) for x in _pick(tl, 2)]
            lost = [x for x in lost if x]

            parts: List[str] = []
            if lead:
                parts.append(lead.strip())
            if isinstance(pgn_line, str) and pgn_line.strip():
                parts.append(f"Line: {pgn_line.strip()}")
            if isinstance(d_ev, (int, float)) and isinstance(ev0, (int, float)) and isinstance(ev1, (int, float)):
                parts.append(f"Eval Δ {d_ev:+.2f} ({ev0:+.2f} → {ev1:+.2f})")
            if gained:
                parts.append(f"Progress signals: {', '.join(gained)}")
            if lost:
                parts.append(f"Tradeoffs: {', '.join(lost)}")

            if parts:
                claim.summary = "; ".join(parts) + "."
        except Exception:
            return claim
        return claim

    def _ensure_agenda_coverage_claims(
        self,
        *,
        claims: List["Claim"],
        execution_plan: Optional[Any],
        multiple_results: List[Dict[str, Any]],
        primary_result_for_evidence: Optional["InvestigationResult"],
        force_suggestion: bool,
    ) -> List["Claim"]:
        """
        Enforce minimal agenda coverage for suggestion-style queries:
        - At least one claim per agenda question (capped), each grounded to a distinct candidate evidence line.
        - Claims must use distinct evidence lines (one claim per line).
        """
        if not execution_plan or not getattr(execution_plan, "discussion_agenda", None):
            return claims
        agenda = execution_plan.discussion_agenda or []
        if not isinstance(agenda, list) or not agenda:
            return claims
        if not multiple_results or not isinstance(multiple_results, list):
            return claims

        # Count required questions (cap to keep output concise)
        questions: List[str] = []
        for item in agenda:
            if not isinstance(item, dict):
                continue
            qs = item.get("questions_to_answer") or []
            if isinstance(qs, list):
                for q in qs:
                    if isinstance(q, str) and q.strip():
                        questions.append(q.strip())
        # Keep it small: 2-3 coverage claims max.
        required = min(max(len(questions), 2), 3) if force_suggestion else min(len(questions), 2)
        if required <= 0:
            return claims

        # Build candidate list: primary (first), then best alternates by evidence_eval_end if available.
        candidates: List[InvestigationResult] = []
        for item in multiple_results:
            if not isinstance(item, dict):
                continue
            res = item.get("result")
            if isinstance(res, InvestigationResult):
                candidates.append(res)
        if not candidates:
            return claims

        # Primary first (already ordered upstream in suggestion mode), then sort remaining by eval_end desc.
        primary = candidates[0]
        rest = candidates[1:]
        def _score(res: InvestigationResult) -> float:
            v = getattr(res, "evidence_eval_end", None)
            if isinstance(v, (int, float)):
                return float(v)
            v = getattr(res, "eval_after", None)
            if isinstance(v, (int, float)):
                return float(v)
            return -9999.0
        rest_sorted = sorted(rest, key=_score, reverse=True)
        picked: List[InvestigationResult] = [primary] + rest_sorted

        # Add deterministic claims until we have required count, preferring distinct evidence lines.
        out = list(claims or [])
        used_lines = set()
        for c in out:
            payload = getattr(c, "evidence_payload", None)
            try:
                line = getattr(payload, "pgn_line", None) if payload else None
                if isinstance(line, str) and line.strip():
                    used_lines.add(line.strip())
            except Exception:
                pass

        for idx in range(required):
            if len(out) >= required:
                break
            # Choose next candidate whose evidence line isn't already used
            chosen = None
            for cand in picked:
                line = getattr(cand, "evidence_pgn_line", None)
                if isinstance(line, str) and line.strip() and line.strip() not in used_lines:
                    chosen = cand
                    break
            if not chosen:
                break
            lead = None
            if idx < len(questions):
                lead = questions[idx]
            else:
                lead = "Candidate line"

            new_claim = Claim(
                summary="",
                claim_type="general",
                connector=None,
                evidence_moves=None,
                evidence_source=None,
            )
            new_claim._origin = "agenda_coverage_fallback"
            # Bind evidence from the candidate result, then render a deterministic evidence-first summary.
            self._attach_rich_evidence(new_claim, chosen, want_pgn_line=True, want_tags=True, want_two_move=False)
            self._rewrite_claim_summary_from_evidence(new_claim, lead=lead)
            out.append(new_claim)
            line = getattr(chosen, "evidence_pgn_line", None)
            if isinstance(line, str) and line.strip():
                used_lines.add(line.strip())

        # Enforce 1-claim-per-line again after insertion.
        out = self._dedupe_claims_one_per_evidence_line(out)
        return out

    def _build_original_pgn_context(self, inv: "InvestigationResult") -> Dict[str, Any]:
        """
        Build a compact, grounded PGN context payload for downstream LLMs.
        Must never assume comparison-dict shape; takes an InvestigationResult only.
        """
        try:
            # Include the full PGN by default (artifact for UI / admin / logs),
            # but allow a cap to avoid enormous payloads.
            try:
                max_chars = int(os.getenv("SUMMARISER_ORIGINAL_PGN_CONTEXT_MAX_CHARS", "20000"))
            except Exception:
                max_chars = 20000
            pgn = (getattr(inv, "pgn_exploration", "") or "")
            if max_chars > 0 and isinstance(pgn, str) and len(pgn) > max_chars:
                pgn = pgn[:max_chars]
            return {
                "evidence_pgn_line": getattr(inv, "evidence_pgn_line", None),
                "evidence_main_line_moves": getattr(inv, "evidence_main_line_moves", []) or [],
                # NOTE: This is NOT automatically fed into the LLM prompt (we control prompt size separately).
                "pgn_exploration": pgn,
            }
        except Exception:
            return {}

    def _generate_worded_pgn(
        self,
        *,
        inv: "InvestigationResult",
        user_message: Optional[str],
        organized_pgn_data: Optional[Dict[str, Any]],
        original_pgn_context: Dict[str, Any],
        alternate_results: Optional[List["InvestigationResult"]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate the worded-PGN JSON using the existing prompt, but fully grounded in inv + organized_pgn_data.
        Safe: returns None on any failure.
        """
        # Worded PGN feature removed (cost/latency). Explainer consumes PGN directly.
        return None
        if not organized_pgn_data or not isinstance(organized_pgn_data, dict):
            return None
        if not getattr(self, "client", None):
            return None
        try:
            # Reuse the same transformation helpers from the single-result code path.
            def _classify_semantics(name: Optional[str]) -> str:
                s = (name or "").lower()
                if any(k in s for k in ("trapped", "hanging", "overloaded", "undefended", "exposed", "pinned", "fork", "skewer", "overworked")):
                    return "problem"
                if any(k in s for k in ("pair", "connected", "advantage")):
                    return "benefit"
                return "property"

            def _polarity_hints_for_move(role_delta: Dict[str, Any], meaningful_tag_delta: Dict[str, Any]) -> List[Dict[str, str]]:
                hints: List[Dict[str, str]] = []
                rg = role_delta.get("gained") if isinstance(role_delta, dict) else []
                rl = role_delta.get("lost") if isinstance(role_delta, dict) else []
                tg = meaningful_tag_delta.get("gained") if isinstance(meaningful_tag_delta, dict) else []
                tl = meaningful_tag_delta.get("lost") if isinstance(meaningful_tag_delta, dict) else []

                for r in (rg or []):
                    if not isinstance(r, str) or not r:
                        continue
                    c = _classify_semantics(r)
                    hints.append({"type": "role", "polarity": ("problem_appeared" if c == "problem" else "benefit_appeared" if c == "benefit" else "property_appeared"), "name": r})
                for r in (rl or []):
                    if not isinstance(r, str) or not r:
                        continue
                    c = _classify_semantics(r)
                    hints.append({"type": "role", "polarity": ("problem_resolved" if c == "problem" else "benefit_removed" if c == "benefit" else "property_removed"), "name": r})
                for t in (tg or []):
                    if not isinstance(t, str) or not t:
                        continue
                    c = _classify_semantics(t)
                    hints.append({"type": "tag", "polarity": ("problem_appeared" if c == "problem" else "benefit_appeared" if c == "benefit" else "property_appeared"), "name": t})
                for t in (tl or []):
                    if not isinstance(t, str) or not t:
                        continue
                    c = _classify_semantics(t)
                    hints.append({"type": "tag", "polarity": ("problem_resolved" if c == "problem" else "benefit_removed" if c == "benefit" else "property_removed"), "name": t})
                return hints

            def _fmt_eval_header(*, evidence_eval: Dict[str, Any], prefix: str = "") -> Optional[str]:
                try:
                    ev0 = evidence_eval.get("eval_start")
                    ev1 = evidence_eval.get("eval_end")
                    m0 = evidence_eval.get("material_start")
                    m1 = evidence_eval.get("material_end")
                    p0 = evidence_eval.get("positional_start")
                    p1 = evidence_eval.get("positional_end")
                    if ev0 is None or ev1 is None or m0 is None or m1 is None:
                        return None
                    d_ev = ev1 - ev0
                    d_m = m1 - m0
                    d_p = (p1 - p0) if (p0 is not None and p1 is not None) else None
                    def _side(x: float) -> str:
                        return "White" if x > 0 else "Black" if x < 0 else "Equal"
                    def _bucket(total: float) -> str:
                        a = abs(total)
                        if a < 0.4:
                            return "roughly equal"
                        if a < 1.5:
                            return f"slightly better for {_side(total)}"
                        if a < 3.0:
                            return f"better for {_side(total)}"
                        return f"winning for {_side(total)}"
                    exchange_note = "no net material change" if abs(d_m) < 0.5 else ("material gain for White" if d_m > 0 else "material gain for Black")
                    overall = _bucket(ev1)
                    if d_p is not None and p0 is not None and p1 is not None:
                        # Phrase from White POV to avoid confusing mixed perspective.
                        pos_note = ("position improved for White" if d_p > 0 else "position worsened for White" if d_p < 0 else "position unchanged")
                        return f"{prefix}Eval {ev0:+.2f} → {ev1:+.2f} (Δ {d_ev:+.2f}); material {m0:+.2f} → {m1:+.2f} (Δ {d_m:+.2f}) ({exchange_note}); position {p0:+.2f} → {p1:+.2f} (Δ {d_p:+.2f}) ({pos_note}); overall: {overall}."
                    return f"{prefix}Eval {ev0:+.2f} → {ev1:+.2f} (Δ {d_ev:+.2f}); material {m0:+.2f} → {m1:+.2f} (Δ {d_m:+.2f}) ({exchange_note}); overall: {overall}."
                except Exception:
                    return None

            def _is_clutter_tag_name(t: Any) -> bool:
                if not isinstance(t, str):
                    return False
                cluttering_prefixes = ("tag.diagonal.", "tag.file.", "tag.key.", "tag.center.", "tag.activity.", "tag.lever.", "tag.color.hole.")
                return any(t.startswith(p) for p in cluttering_prefixes)

            def _filter_meaningful_tag_list(xs: Any) -> List[str]:
                if not isinstance(xs, list):
                    return []
                out: List[str] = []
                for x in xs:
                    if isinstance(x, str) and x and (not _is_clutter_tag_name(x)):
                        out.append(x)
                return out

            # Mainline moves: strip per-move eval/material/positional, keep deltas + FENs.
            organized_pgn_meaningful = dict(organized_pgn_data)
            moves_in = organized_pgn_meaningful.get("moves") if isinstance(organized_pgn_meaningful.get("moves"), list) else []
            moves_out: List[Dict[str, Any]] = []
            for m in moves_in:
                if not isinstance(m, dict):
                    continue
                m2 = dict(m)
                td = m2.get("tag_delta") if isinstance(m2.get("tag_delta"), dict) else {}
                m2["meaningful_tag_delta"] = {"gained": _filter_meaningful_tag_list(td.get("gained")), "lost": _filter_meaningful_tag_list(td.get("lost"))}
                rd = m2.get("role_delta") if isinstance(m2.get("role_delta"), dict) else {}
                m2["polarity_hints"] = _polarity_hints_for_move(rd, m2["meaningful_tag_delta"])
                for k in ("eval", "material", "positional", "tag_delta"):
                    if k in m2:
                        del m2[k]
                moves_out.append(m2)
            organized_pgn_meaningful["moves"] = moves_out

            main_header = _fmt_eval_header(
                evidence_eval={
                    "eval_start": getattr(inv, "evidence_eval_start", None),
                    "eval_end": getattr(inv, "evidence_eval_end", None),
                    "material_start": getattr(inv, "evidence_material_start", None),
                    "material_end": getattr(inv, "evidence_material_end", None),
                    "positional_start": getattr(inv, "evidence_positional_start", None),
                    "positional_end": getattr(inv, "evidence_positional_end", None),
                },
                prefix="Main line: ",
            )

            alternate_lines: List[Dict[str, Any]] = []
            for alt in (alternate_results or [])[:4]:
                if not isinstance(alt, InvestigationResult):
                    continue
                if getattr(alt, "evidence_pgn_line", None) == getattr(inv, "evidence_pgn_line", None):
                    continue
                alt_ev = {
                    "eval_start": getattr(alt, "evidence_eval_start", None),
                    "eval_end": getattr(alt, "evidence_eval_end", None),
                    "material_start": getattr(alt, "evidence_material_start", None),
                    "material_end": getattr(alt, "evidence_material_end", None),
                    "positional_start": getattr(alt, "evidence_positional_start", None),
                    "positional_end": getattr(alt, "evidence_positional_end", None),
                }
                alt_struct = self._build_organized_pgn_structure(alt, {}) or {}
                alt_meaningful = dict(alt_struct) if isinstance(alt_struct, dict) else {}
                alt_moves_in = alt_meaningful.get("moves") if isinstance(alt_meaningful.get("moves"), list) else []
                alt_moves_out: List[Dict[str, Any]] = []
                for m in alt_moves_in:
                    if not isinstance(m, dict):
                        continue
                    m2 = dict(m)
                    td = m2.get("tag_delta") if isinstance(m2.get("tag_delta"), dict) else {}
                    m2["meaningful_tag_delta"] = {"gained": _filter_meaningful_tag_list(td.get("gained")), "lost": _filter_meaningful_tag_list(td.get("lost"))}
                    for k in ("eval", "material", "positional", "tag_delta"):
                        if k in m2:
                            del m2[k]
                    alt_moves_out.append(m2)
                alt_meaningful["moves"] = alt_moves_out
                label = getattr(alt, "player_move", None) or "alternate"
                alternate_lines.append({"label": label, "header_summary": _fmt_eval_header(evidence_eval=alt_ev, prefix=f"Alternate ({label}): "), "organized_pgn_meaningful": alt_meaningful})

            worded_payload = {
                "user_query": user_message,
                "original_pgn_context": original_pgn_context,
                "mainline": {"header_summary": main_header, "organized_pgn_meaningful": organized_pgn_meaningful},
                "alternate_lines": alternate_lines,
            }

            worded_prompt = (
                "You convert SAN PGN into a grounded English narration.\n"
                "\n"
                "MANDATORY INPUTS:\n"
                "- mainline.organized_pgn_meaningful.moves[] includes: ply, move_san, fen_before, fen_after, meaningful_tag_delta, role_delta, polarity_hints.\n"
                "- mainline.header_summary summarizes start/end eval/material/positional.\n"
                "- alternate_lines[] (if present) each have header_summary + organized_pgn_meaningful.\n"
                "\n"
                "RULES (MANDATORY):\n"
                "- If mainline.header_summary is a non-empty string, start the mainline narration with it as the first sentence (or a close paraphrase). Do not invent numbers.\n"
                "- If alternate_lines exist, produce a separate narration per alternate. If its header_summary is non-empty, start with it.\n"
                "- Use fen_before/fen_after to identify pieces and their squares. If uncertain, refer to the piece by square (e.g. 'the bishop on e2').\n"
                "- Polarity MUST match polarity_hints. You may not flip gained/lost direction.\n"
                "- For EACH move, your sentence MUST include: action + ALL meaningful tag deltas + ALL role deltas + a short polarity clause.\n"
                "- Do NOT invent tags/roles/evals not present in the input.\n"
                "\n"
                "OUTPUT JSON:\n"
                "{\n"
                '  "mainline": {"header_summary": "...", "worded_pgn": "...", "moves": []},\n'
                '  "alternate_lines": [{"label": "...", "header_summary": "...", "worded_pgn": "...", "moves": []}],\n'
                '  "notes": []\n'
                "}\n"
            )

            # Only set temperature if model supports it (gpt-5 doesn't support custom temperature)
            model_params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": worded_prompt},
                    {"role": "user", "content": json.dumps(worded_payload, ensure_ascii=False)},
                ],
                "response_format": {"type": "json_object"}
            }
            if "gpt-5" not in self.model.lower():
                model_params["temperature"] = 0.2
            
            import time as _time
            from pipeline_timer import get_pipeline_timer
            _timer = get_pipeline_timer()
            _t0 = _time.perf_counter()
            resp = self.client.chat.completions.create(**model_params)
            _dt = _time.perf_counter() - _t0
            try:
                usage = getattr(resp, "usage", None)
                prompt_tokens = getattr(usage, "prompt_tokens", None)
                completion_tokens = getattr(usage, "completion_tokens", None)
            except Exception:
                prompt_tokens = None
                completion_tokens = None
            # worded_pgn feature removed; no longer record summariser_worded_pgn stats
            import json as _json
            return _json.loads(resp.choices[0].message.content)
        except Exception as e:
            print(f"   ⚠️ [SUMMARISER] Worded PGN generation failed (non-fatal): {e}")
            return None

    def _tag_to_phrase(self, tag_name: Optional[str]) -> Optional[str]:
        """Convert structured tag identifiers into human-readable phrases."""
        if not tag_name:
            return None
        cleaned = tag_name.replace("tag.", "").replace(".", " ").replace("_", " ").strip()
        return cleaned if cleaned else None

    def _get_request_attr(self, request: Optional[Any], attr: str, default: Optional[Any] = None):
        """Safely extract InvestigationRequest metadata regardless of representation."""
        if request is None:
            return default
        if isinstance(request, dict):
            return request.get(attr, default)
        return getattr(request, attr, default)
    
    def _build_tag_highlight(
        self,
        inv: InvestigationResult,
        prefer_tactic_types: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """Fallback tactic highlight based purely on tags/threat data."""
        tags = []
        if inv.light_raw_analysis and inv.light_raw_analysis.tags:
            tags = inv.light_raw_analysis.tags
        
        prefer_lower = [p.lower() for p in prefer_tactic_types] if prefer_tactic_types else []
        for tag in tags:
            tag_name = tag.get("tag") or tag.get("tag_name") or ""
            tag_lower = tag_name.lower()
            if prefer_lower and not any(pref in tag_lower for pref in prefer_lower):
                continue
            phrase = self._tag_to_phrase(tag_name)
            if not phrase:
                continue
            return {
                "type": phrase,
                "move": tag.get("square") or phrase,
                "sequence": [phrase],
                "targets": [],
                "material_gain": 0.0,
                "threat_level": "tag_inference",
                "is_valid_tactic": True,
                "forced_sequence_exists": False,
                "best_opponent_defense": None,
            }
        
        # Fall back to threats list if tags unavailable
        if inv.threats:
            threat = inv.threats[0]
            label = threat.get("tag_labels", [])
            phrase = label[0] if label else threat.get("best_reply")
            if phrase:
                return {
                    "type": phrase,
                    "move": threat.get("best_reply") or phrase,
                    "sequence": [threat.get("best_reply")] if threat.get("best_reply") else [phrase],
                    "targets": [],
                    "material_gain": 0.0,
                    "threat_level": "opponent_threat",
                    "is_valid_tactic": True,
                    "forced_sequence_exists": False,
                    "best_opponent_defense": None,
                }
        return None

    # =========================================================================
    # Rich evidence attachment (referential only; no invention)
    # =========================================================================
    def _is_two_move_item_verified(self, item: Any) -> bool:
        """
        Generic verifier for a single TwoMoveWinEngine item (tactic/capture/mate pattern).
        We treat "refuted" as NOT usable for narrative mechanisms/evidence snippets.
        """
        if not isinstance(item, dict):
            return False

        verification = item.get("verification")
        if isinstance(verification, dict) and verification.get("refuted") is True:
            return False

        # If engine explicitly marks validity, require it.
        if "is_valid_tactic" in item:
            return bool(item.get("is_valid_tactic"))

        # For some item types the engine may only provide "forced_sequence_exists".
        if "forced_sequence_exists" in item:
            if item.get("forced_sequence_exists") is False:
                return False

        # Otherwise: accept as long as it isn't explicitly refuted.
        return True

    def _select_verified_two_move_item(
        self,
        inv: InvestigationResult,
        *,
        prefer_sections: Optional[List[str]] = None,
        prefer_tactic_types: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Select the first non-refuted (verified) two-move item to use as "proof-like" evidence.
        Optionally prefer certain dict sections and/or tactic types.
        """
        tm = getattr(inv, "two_move_tactics", None)
        if not tm:
            return self._build_tag_highlight(inv, prefer_tactic_types)
        try:
            d = tm.to_dict()
        except Exception:
            d = tm if isinstance(tm, dict) else None
        if not isinstance(d, dict):
            return self._build_tag_highlight(inv, prefer_tactic_types)

        sections = prefer_sections or ["checkmates", "open_tactics", "open_captures", "mate_patterns", "promotions", "blocked_tactics", "closed_captures"]
        prefer_types = [t.lower() for t in (prefer_tactic_types or []) if isinstance(t, str)]

        def iter_items():
            for sec in sections:
                items = d.get(sec)
                if isinstance(items, list):
                    for it in items:
                        yield sec, it

        # First pass: respect preferred tactic types if provided.
        if prefer_types:
            for sec, it in iter_items():
                if not self._is_two_move_item_verified(it):
                    continue
                t = it.get("type")
                if isinstance(t, str) and t.lower() in prefer_types:
                    it2 = dict(it)
                    it2["_section"] = sec
                    return it2

        # Second pass: any verified item.
        for sec, it in iter_items():
            if not self._is_two_move_item_verified(it):
                continue
            it2 = dict(it)
            it2["_section"] = sec
            return it2

        return None

    def _determine_evidence_source(self, inv: InvestigationResult, pgn_line: Optional[str], max_plies: int = 4) -> Optional[str]:
        """
        Determine the evidence source for a given PGN line.
        Matches the priority order used in _select_pgn_line.
        
        Args:
            inv: InvestigationResult with evidence
            pgn_line: The PGN line to match
            max_plies: Maximum number of plies in the line
            
        Returns:
            Evidence source string ("pv", "pgn", or from evidence_index) or None
        """
        if not pgn_line:
            return None
        
        # Priority 1: Check pv_after_move
        pv = getattr(inv, "pv_after_move", None) or []
        pv_moves = [m for m in pv if isinstance(m, str)]
        player_move = getattr(inv, "player_move", None)
        
        if player_move and isinstance(player_move, str) and pv_moves:
            # Check if pgn_line matches pv with player_move prepended
            if pv_moves[0] != player_move:
                full_sequence = [player_move] + pv_moves
                if pgn_line == " ".join(full_sequence[:max_plies]) or pgn_line.startswith(" ".join(full_sequence[:max_plies])):
                    return "pv"
            # Check if pgn_line matches pv directly
            if pgn_line == " ".join(pv_moves[:max_plies]) or pgn_line.startswith(" ".join(pv_moves[:max_plies])):
                return "pv"
        elif pv_moves:
            if pgn_line == " ".join(pv_moves[:max_plies]) or pgn_line.startswith(" ".join(pv_moves[:max_plies])):
                return "pv"
        
        # Priority 2: Check evidence_index
        if getattr(inv, "evidence_index", None):
            lines = inv.evidence_index or []
            for line in lines:
                if getattr(line, "moves", None):
                    moves = [m for m in line.moves if isinstance(m, str)]
                    player_move = getattr(inv, "player_move", None)
                    if player_move and isinstance(player_move, str) and moves:
                        if moves[0] != player_move:
                            moves = [player_move] + moves
                    if len(moves) >= 2:
                        line_str = " ".join(moves[:max_plies])
                        # Check if pgn_line matches or contains this line
                        if pgn_line == line_str or pgn_line.startswith(line_str) or line_str in pgn_line:
                            return getattr(line, "source", "pgn")
        
        # Priority 3: Check pgn_branches or pgn_exploration (fallback to "pgn")
        # If we have a pgn_line but it didn't match pv or evidence_index, it's from pgn
        return "pgn"
    
    def _select_pgn_line(self, inv: InvestigationResult, max_plies: int = 4, move_san: Optional[str] = None) -> Optional[str]:
        """
        Select a short SAN/PGN line for inline display.
        If move_san is provided, prefer lines that contain that move.
        Order: pv_after_move -> evidence_index (best match) -> pgn_branches -> pgn_exploration (short snippet).
        """
        # If move_san provided, try to find a line containing it first
        if move_san:
            # Check pv_after_move - if it starts with the move, use it
            pv = getattr(inv, "pv_after_move", None) or []
            pv_moves = [m for m in pv if isinstance(m, str)]
            if pv_moves and pv_moves[0] == move_san:
                return " ".join(pv_moves[:max_plies])
            
            # Check pgn_branches for lines containing the move
            branches = getattr(inv, "pgn_branches", None) or {}
            if isinstance(branches, dict) and branches:
                for key in sorted(branches.keys()):
                    val = branches.get(key)
                    if isinstance(val, str) and move_san in val:
                        # Extract a short sequence around the move
                        import re
                        # Find move in the PGN string
                        move_pattern = re.escape(move_san)
                        match = re.search(move_pattern, val)
                        if match:
                            # Extract context around the move
                            start = max(0, match.start() - 50)
                            end = min(len(val), match.end() + 100)
                            snippet = val[start:end]
                            # Extract SAN moves from snippet
                            san_pattern = r'\b([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)\b'
                            moves = re.findall(san_pattern, snippet)
                            if moves and move_san in moves:
                                # Find move index and get sequence starting from it
                                try:
                                    move_idx = moves.index(move_san)
                                    sequence = moves[move_idx:move_idx + max_plies]
                                    if len(sequence) >= 2:
                                        return " ".join(sequence)
                                except ValueError:
                                    pass
                        # Fallback: return the branch if it contains the move
                        return val.strip()[:220]
        
        # Standard selection (no move_san or move_san not found)
        pv = getattr(inv, "pv_after_move", None) or []
        pv_moves = [m for m in pv if isinstance(m, str)]
        
        # FIX: If we have a player_move, prepend it to pv_after_move to show full sequence
        # This ensures evidence PGN starts with the player's move, not the opponent's response
        player_move = getattr(inv, "player_move", None)
        if player_move and isinstance(player_move, str) and pv_moves:
            # Only prepend if pv_after_move doesn't already start with player_move
            if pv_moves[0] != player_move:
                full_sequence = [player_move] + pv_moves
                return " ".join(full_sequence[:max_plies])
        
        if pv_moves:
            return " ".join(pv_moves[:max_plies])

        try:
            if getattr(inv, "evidence_index", None):
                # Prefer an evidence line that is explicitly "after_move" if present.
                lines = inv.evidence_index or []
                preferred = None
                for cand in lines:
                    if getattr(cand, "context", None) == "after_move":
                        preferred = cand
                        break
                line = preferred or (lines[0] if lines else None)
                if line and getattr(line, "moves", None):
                    moves = [m for m in line.moves if isinstance(m, str)]
                    # FIX: Prepend player_move if available and not already present
                    player_move = getattr(inv, "player_move", None)
                    if player_move and isinstance(player_move, str) and moves:
                        if moves[0] != player_move:
                            moves = [player_move] + moves
                    if len(moves) >= 2:
                        return " ".join(moves[:max_plies])
        except Exception:
            pass

        branches = getattr(inv, "pgn_branches", None) or {}
        if isinstance(branches, dict) and branches:
            # Stable selection: first key alphabetically
            first_key = sorted(branches.keys())[0]
            val = branches.get(first_key)
            if isinstance(val, str) and val.strip():
                return val.strip()[:220]

        pgn_expl = getattr(inv, "pgn_exploration", "") or ""
        if isinstance(pgn_expl, str) and pgn_expl.strip():
            return pgn_expl.strip()[:220]

        return None

    def _select_theme_tags(self, inv: InvestigationResult, cap: int = 5) -> List[str]:
        out: List[str] = []
        themes_identified = getattr(inv, "themes_identified", None) or []
        for t in themes_identified:
            if isinstance(t, str) and t and t not in out:
                out.append(t)
            if len(out) >= cap:
                return out

        lra = getattr(inv, "light_raw_analysis", None)
        if lra and getattr(lra, "top_themes", None):
            for t in lra.top_themes:
                if isinstance(t, str) and t and t not in out:
                    out.append(t)
                if len(out) >= cap:
                    break
        return out[:cap]

    def _select_tactic_tags(self, inv: InvestigationResult, cap: int = 8) -> List[str]:
        """
        Extract tactic tags from Investigator.tactics_found (more reliable than TwoMove for narrative).
        Returns e.g. ["tactic.fork", "tactic.pin"].
        """
        out: List[str] = []
        tactics = getattr(inv, "tactics_found", None) or []
        if not isinstance(tactics, list):
            return out
        for t in tactics:
            if not isinstance(t, dict):
                continue
            tt = t.get("type")
            if isinstance(tt, str) and tt:
                tag = f"tactic.{tt}"
                if tag not in out:
                    out.append(tag)
            if len(out) >= cap:
                break
        return out[:cap]

    def _select_raw_tags(self, inv: InvestigationResult, cap: int = 6) -> List[str]:
        lra = getattr(inv, "light_raw_analysis", None)
        if not lra or not getattr(lra, "tags", None):
            return []
        out: List[str] = []
        for tag_obj in lra.tags:
            if not isinstance(tag_obj, dict):
                continue
            name = tag_obj.get("tag") or tag_obj.get("name") or tag_obj.get("tag_name")
            phrase = self._tag_to_phrase(name)
            if phrase and phrase not in out:
                out.append(phrase)
            if len(out) >= cap:
                break
        return out[:cap]

    def _select_two_move_snippet(self, inv: InvestigationResult) -> Optional[Dict[str, Any]]:
        tm = getattr(inv, "two_move_tactics", None)
        snippet: Dict[str, Any] = {}
        d = None
        if tm:
            try:
                d = tm.to_dict()
            except Exception:
                d = tm if isinstance(tm, dict) else None
        if isinstance(d, dict):
            # Prefer a VERIFIED (non-refuted) proof-like snippet.
            best = self._select_verified_two_move_item(inv)
        else:
            best = None
        if best:
            sec = best.get("_section")
            if isinstance(sec, str):
                best_clean = dict(best)
                best_clean.pop("_section", None)
                if sec in ("checkmates", "mate_patterns"):
                    snippet.setdefault("checkmates", [best_clean])
                elif sec in ("open_tactics", "blocked_tactics"):
                    snippet.setdefault("open_tactics", [best_clean])
                elif sec in ("open_captures", "closed_captures"):
                    snippet.setdefault("open_captures", [best_clean])
                elif sec == "promotions":
                    snippet.setdefault("promotions", [best_clean])
        has_verified = bool(best)
        snippet["has_winning_tactic"] = has_verified
        snippet["has_immediate_threat"] = has_verified
        snippet["has_mate_threat"] = bool(snippet.get("checkmates"))
        snippet["has_promotion_threat"] = bool(snippet.get("promotions"))
        if snippet:
            return snippet

        fallback = self._build_tag_highlight(inv)
        if fallback:
            return {"tags": [fallback], "has_winning_tactic": True, "has_immediate_threat": True}
        return None

    def _attach_rich_evidence(
        self,
        claim: Claim,
        inv: InvestigationResult,
        *,
        want_pgn_line: bool,
        want_tags: bool,
        want_two_move: bool,
        move_san: Optional[str] = None
    ) -> Claim:
        """
        Attach evidence payload to an existing Claim.
        This must be referential-only (copied from inv), never computed/derived.
        
        Args:
            claim: Claim to attach evidence to
            inv: InvestigationResult with evidence
            want_pgn_line: Whether to include PGN line
            want_tags: Whether to include tags
            want_two_move: Whether to include two-move tactics
            move_san: Optional move SAN to prefer in PGN line selection
        """
        # For consequence claims, use longer PGN lines and more theme tags
        is_consequence = claim.claim_type == "consequence"
        max_plies = 6 if is_consequence else 4  # Longer PGN for consequences
        theme_cap = 8 if is_consequence else 5  # More themes for consequences
        
        pgn_line = self._select_pgn_line(inv, max_plies=max_plies, move_san=move_san) if want_pgn_line else None

        # Prefer Investigator canonical evidence line/moves (ensures the starting move is included).
        inv_evidence_line = getattr(inv, "evidence_pgn_line", None)
        inv_evidence_moves = getattr(inv, "evidence_main_line_moves", None)
        if isinstance(inv_evidence_line, str) and inv_evidence_line.strip():
            pgn_line = inv_evidence_line.strip()
        pgn_moves = []
        if isinstance(inv_evidence_moves, list) and inv_evidence_moves:
            pgn_moves = [m for m in inv_evidence_moves if isinstance(m, str) and m]
        elif isinstance(pgn_line, str) and pgn_line.strip():
            pgn_moves = [m for m in pgn_line.strip().split() if m]
        
        # Determine and update evidence_source based on where PGN line came from
        # This ensures evidence_source matches the actual source of the evidence
        if pgn_line and claim.evidence_moves:
            # Only update if we don't already have a valid source, or if it's "llm_generated"
            if not claim.evidence_source or claim.evidence_source == "llm_generated":
                determined_source = self._determine_evidence_source(inv, pgn_line, max_plies=max_plies)
                if determined_source:
                    claim.evidence_source = determined_source

        # Make claim.evidence_moves match the actual PGN evidence line we attached (fixes LLM omitting the starting move).
        if pgn_moves:
            claim.evidence_moves = pgn_moves[:max_plies]
            if claim.connector:
                # Replace "llm_generated" with a real source when possible.
                if not claim.evidence_source or claim.evidence_source == "llm_generated":
                    claim.evidence_source = self._determine_evidence_source(inv, pgn_line, max_plies=max_plies) or "validated"
        
        # Net changes: Prefer the precomputed InvestigationResult evidence deltas (single source of truth).
        # This avoids re-parsing/scanning PGN in the Summariser and ensures prompt-time + payload-time match.
        tags_gained_net = list(getattr(inv, "evidence_tags_gained_net", []) or [])
        tags_lost_net = list(getattr(inv, "evidence_tags_lost_net", []) or [])
        tags_gained_net_structured = list(getattr(inv, "evidence_tags_gained_net_structured", []) or [])
        tags_lost_net_structured = list(getattr(inv, "evidence_tags_lost_net_structured", []) or [])
        roles_gained_net = list(getattr(inv, "evidence_roles_gained_net", []) or [])
        roles_lost_net = list(getattr(inv, "evidence_roles_lost_net", []) or [])
        # Material change must reflect the evidence line, not the full-move investigation summary.
        evidence_material_start = getattr(inv, "evidence_material_start", None)
        evidence_material_end = getattr(inv, "evidence_material_end", None)
        material_change_net = (
            (evidence_material_end - evidence_material_start)
            if (isinstance(evidence_material_start, (int, float)) and isinstance(evidence_material_end, (int, float)))
            else getattr(inv, "material_change", None)
        )
        
        # Backward-compat fallback: if precomputed lists are missing, fall back to old PGN-based calc.
        if (pgn_line and hasattr(inv, "pgn_exploration") and inv.pgn_exploration and
            not (tags_gained_net or tags_lost_net or roles_gained_net or roles_lost_net)):
            tags_gained_net, tags_lost_net, roles_gained_net, roles_lost_net, _ = self._calculate_net_changes_from_pgn_sequence(
                pgn_line, inv.pgn_exploration
            )
        
        # Trace claim identity + origin (helps debug duplicate Claim objects / overwritten evidence)
        origin = getattr(claim, "_origin", None)
        if origin is None:
            origin = "unknown"
        print(f"   🧩 [CLAIM_TRACE] id={id(claim)} origin={origin} type={getattr(claim, 'claim_type', None)} connector={getattr(claim, 'connector', None)} has_evidence_moves={bool(getattr(claim, 'evidence_moves', None))}")

        # Calculate eval breakdown for evidence (material and positional balance)
        evidence_eval_start = getattr(inv, "evidence_eval_start", None)
        evidence_eval_end = getattr(inv, "evidence_eval_end", None)
        evidence_material_start = getattr(inv, "evidence_material_start", None)
        evidence_material_end = getattr(inv, "evidence_material_end", None)
        evidence_positional_start = getattr(inv, "evidence_positional_start", None)
        evidence_positional_end = getattr(inv, "evidence_positional_end", None)
        
        # Calculate positional balance (eval - material) if both are available
        # Positional balance = eval - material balance
        # More positive = better for White, more negative = better for Black
        positional_start_calc = None
        if evidence_eval_start is not None and evidence_material_start is not None:
            positional_start_calc = evidence_eval_start - evidence_material_start
        elif evidence_positional_start is not None:
            positional_start_calc = evidence_positional_start
        
        positional_end_calc = None
        if evidence_eval_end is not None and evidence_material_end is not None:
            positional_end_calc = evidence_eval_end - evidence_material_end
        elif evidence_positional_end is not None:
            positional_end_calc = evidence_positional_end
        
        # Create eval breakdown if we have the data
        key_eval_breakdown = None
        if (evidence_material_start is not None or evidence_material_end is not None or
            positional_start_calc is not None or positional_end_calc is not None):
            key_eval_breakdown = {
                "material_balance_before": evidence_material_start,
                "material_balance_after": evidence_material_end,
                "material_balance_delta": (evidence_material_end - evidence_material_start) if (evidence_material_end is not None and evidence_material_start is not None) else None,
                "positional_balance_before": positional_start_calc,
                "positional_balance_after": positional_end_calc,
                "positional_balance_delta": (positional_end_calc - positional_start_calc) if (positional_end_calc is not None and positional_start_calc is not None) else None,
                "eval_before": evidence_eval_start,
                "eval_after": evidence_eval_end,
                "eval_delta": (evidence_eval_end - evidence_eval_start) if (evidence_eval_end is not None and evidence_eval_start is not None) else None,
            }
        
        payload = ClaimEvidencePayload(
            pgn_line=pgn_line,
            pgn_moves=pgn_moves[:max_plies] if pgn_moves else [],
            theme_tags=self._select_theme_tags(inv, cap=theme_cap) if want_tags else [],
            raw_tags=self._select_raw_tags(inv) if want_tags else [],
            two_move=self._select_two_move_snippet(inv) if want_two_move else None,
            fen_snapshot=None,  # Only attach if upstream provides it; keep None by default
            eval_before=getattr(inv, "eval_before", None),
            eval_after=getattr(inv, "eval_after", None),
            eval_drop=getattr(inv, "eval_drop", None),
            material_change=getattr(inv, "material_change", None),
            evidence_eval_start=getattr(inv, "evidence_eval_start", None),
            evidence_eval_end=getattr(inv, "evidence_eval_end", None),
            evidence_eval_delta=getattr(inv, "evidence_eval_delta", None),
            evidence_material_start=getattr(inv, "evidence_material_start", None),
            evidence_material_end=getattr(inv, "evidence_material_end", None),
            evidence_positional_start=getattr(inv, "evidence_positional_start", None),
            evidence_positional_end=getattr(inv, "evidence_positional_end", None),
            tactic_tags=self._select_tactic_tags(inv) if want_tags else [],
            tags_gained_net=tags_gained_net,
            tags_lost_net=tags_lost_net,
            tags_gained_net_structured=tags_gained_net_structured,
            tags_lost_net_structured=tags_lost_net_structured,
            roles_gained_net=roles_gained_net,  # NEW
            roles_lost_net=roles_lost_net,  # NEW
            material_change_net=material_change_net,
            key_eval_breakdown=key_eval_breakdown,  # NEW: Eval breakdown that fundamentally informs the claim
        )
        
        # Update evidence_source based on key_eval_breakdown if available
        if key_eval_breakdown and claim.evidence_source:
            # If we have rich eval breakdown, prefer "validated" as source
            if claim.evidence_source == "llm_generated":
                claim.evidence_source = "validated"

        has_any = (
            bool(payload.pgn_line)
            or bool(payload.theme_tags)
            or bool(payload.raw_tags)
            or bool(payload.two_move)
            or bool(payload.fen_snapshot)
            or (payload.eval_before is not None)
            or (payload.eval_after is not None)
            or (payload.eval_drop is not None)
            or (payload.material_change is not None)
            or bool(payload.tactic_tags)
            or bool(payload.tags_gained_net)
            or bool(payload.tags_lost_net)
            or bool(payload.roles_gained_net)  # NEW
            or bool(payload.roles_lost_net)  # NEW
            or (payload.material_change_net is not None)
        )
        if has_any:
            claim.evidence_payload = payload
        return claim
    
    def _calculate_net_changes_from_pgn_sequence(
        self,
        pgn_line: str,
        pgn_exploration: str
    ) -> Tuple[List[str], List[str], List[str], List[str], Optional[float]]:
        """
        Calculate net tag and role changes from following a PGN sequence from start to end.
        
        This aggregates all tag and role changes across the sequence to show the final net effect.
        Instead of matching moves against extracted deltas, we calculate deltas sequentially by
        playing each move and comparing before/after states.
        
        Args:
            pgn_line: PGN sequence (e.g., "h3 Bxe2 Ngxe2 Nc6 d4")
            pgn_exploration: Full PGN exploration with starting tags, roles, and FEN
            
        Returns:
            Tuple of (tags_gained_net, tags_lost_net, roles_gained_net, roles_lost_net, material_change_net)
        """
        if not pgn_line or not pgn_exploration:
            return [], [], [], [], None
        
        import re
        from light_raw_analyzer import compute_light_raw_analysis
        
        # Extract starting tags, roles, and FEN from PGN
        starting_tags = []
        starting_roles = {}
        starting_fen = None
        
        # Extract FEN from PGN headers
        fen_match = re.search(r'\[FEN\s+"([^"]+)"\]', pgn_exploration)
        if fen_match:
            starting_fen = fen_match.group(1)
        
        # Extract starting tags
        starting_tags_match = re.search(r'\[Starting tags:\s*([^\]]+)\]', pgn_exploration)
        if starting_tags_match:
            starting_tags = [t.strip() for t in starting_tags_match.group(1).split(",") if t.strip()]
        
        # Extract starting roles
        starting_roles_match = re.search(r'\[Starting roles:\s*([^\]]+)\]', pgn_exploration)
        if starting_roles_match:
            starting_roles_list = [r.strip() for r in starting_roles_match.group(1).split(",") if r.strip()]
            # Convert list format to dict format: "piece_id:role1, piece_id:role2" -> {piece_id: [role1, role2]}
            for role_str in starting_roles_list:
                if ":" in role_str:
                    piece_id, role = role_str.split(":", 1)
                    piece_id = piece_id.strip()
                    role = role.strip()
                    if piece_id not in starting_roles:
                        starting_roles[piece_id] = []
                    starting_roles[piece_id].append(role)
        
        if not starting_fen:
            print(f"   ⚠️ [NET_CHANGES] No starting FEN found in PGN exploration")
            return [], [], [], [], None
        
        # Parse the PGN line into individual moves (SAN format)
        # Match SAN moves: K, Q, R, B, N (optional), square, optional capture, optional promotion, optional check/mate
        moves = re.findall(r'\b([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)\b', pgn_line)
        
        if not moves:
            print(f"   ⚠️ [NET_CHANGES] No moves parsed from PGN line: {pgn_line}")
            return [], [], [], [], None
        
        print(f"   🔍 [NET_CHANGES] PGN line: {pgn_line}")
        print(f"   🔍 [NET_CHANGES] Parsed moves: {moves}")
        print(f"   🔍 [NET_CHANGES] Starting FEN: {starting_fen[:50]}...")
        print(f"   🔍 [NET_CHANGES] Starting tags: {len(starting_tags)}, Starting roles: {sum(len(roles) for roles in starting_roles.values())}")
        
        # Track all tags and roles gained and lost across the sequence
        # Use dictionaries to handle duplicates and calculate net effect
        all_tags_gained = {}  # tag -> count (how many times gained)
        all_tags_lost = {}  # tag -> count (how many times lost)
        all_roles_gained = {}  # role -> count (how many times gained)
        all_roles_lost = {}  # role -> count (how many times lost)
        
        # Initialize board with starting position
        board = chess.Board(starting_fen)
        
        # Get starting tags and roles as sets for comparison
        before_tags_set = set(starting_tags)
        before_roles_set = set()
        for piece_id, roles_list in starting_roles.items():
            for role in roles_list:
                before_roles_set.add(f"{piece_id}:{role}")
        
        # For each move in the sequence, calculate its delta by playing it
        for move_idx, move_san in enumerate(moves):
            move_clean = move_san.strip()
            
            try:
                # Get FEN before the move
                fen_before = board.fen()
                
                # Check if it's the correct side to move
                # If the move fails to parse, it might be because it's the wrong side
                # In that case, we'll try to skip it or handle it gracefully
                try:
                    move_obj = board.parse_san(move_clean)
                except ValueError as e:
                    error_msg = str(e).lower()
                    if "illegal" in error_msg or "not a legal" in error_msg:
                        # Check if it's a turn mismatch
                        expected_side = "White" if board.turn else "Black"
                        print(f"   ⚠️ [NET_CHANGES] Move {move_idx+1} ({move_clean}) is illegal - board expects {expected_side} to move. Skipping this move.")
                        # Skip this move and continue with the next one
                        continue
                    else:
                        # Re-raise if it's a different error
                        raise
                
                board.push(move_obj)
                fen_after = board.fen()
                
                # Compute tags/roles after the move
                after_light_raw = compute_light_raw_analysis(fen_after, previous_fen=fen_before)
                
                # Extract tags after move
                after_tags = []
                if after_light_raw and hasattr(after_light_raw, 'tags'):
                    after_tags = [tag.get('tag_name', tag.get('tag', '')) for tag in (after_light_raw.tags if isinstance(after_light_raw.tags, list) else [])]
                after_tags_set = set(after_tags)
                
                # Extract roles after move
                after_roles = {}
                if after_light_raw and hasattr(after_light_raw, 'roles'):
                    after_roles = after_light_raw.roles if isinstance(after_light_raw.roles, dict) else {}
                after_roles_set = set()
                for piece_id, roles_list in after_roles.items():
                    for role in roles_list:
                        after_roles_set.add(f"{piece_id}:{role}")
                
                # Calculate deltas by comparing to before state
                tags_gained = list(after_tags_set - before_tags_set)
                tags_lost = list(before_tags_set - after_tags_set)
                roles_gained = list(after_roles_set - before_roles_set)
                roles_lost = list(before_roles_set - after_roles_set)
                
                print(f"   ✅ [NET_CHANGES] Move {move_idx+1} ({move_clean}): gained {len(tags_gained)} tags, {len(roles_gained)} roles; lost {len(tags_lost)} tags, {len(roles_lost)} roles")
                
                # Accumulate tags gained - each move contributes its tag deltas
                for tag in tags_gained:
                    if tag not in all_tags_gained:
                        all_tags_gained[tag] = 0
                    all_tags_gained[tag] += 1
                    # If a tag was previously lost, reduce the lost count (net effect)
                    # This cancels out opposite changes: if tag is gained then lost, net = 0
                    if tag in all_tags_lost:
                        all_tags_lost[tag] -= 1
                        if all_tags_lost[tag] <= 0:
                            del all_tags_lost[tag]
                
                # Accumulate tags lost - each move contributes its tag deltas
                for tag in tags_lost:
                    if tag not in all_tags_lost:
                        all_tags_lost[tag] = 0
                    all_tags_lost[tag] += 1
                    # If a tag was previously gained, reduce the gained count (net effect)
                    # This cancels out opposite changes: if tag is lost then gained, net = 0
                    if tag in all_tags_gained:
                        all_tags_gained[tag] -= 1
                        if all_tags_gained[tag] <= 0:
                            del all_tags_gained[tag]
                
                # Accumulate roles gained - each move contributes its role deltas
                for role in roles_gained:
                    if role not in all_roles_gained:
                        all_roles_gained[role] = 0
                    all_roles_gained[role] += 1
                    # If a role was previously lost, reduce the lost count (net effect)
                    if role in all_roles_lost:
                        all_roles_lost[role] -= 1
                        if all_roles_lost[role] <= 0:
                            del all_roles_lost[role]
                
                # Accumulate roles lost - each move contributes its role deltas
                for role in roles_lost:
                    if role not in all_roles_lost:
                        all_roles_lost[role] = 0
                    all_roles_lost[role] += 1
                    # If a role was previously gained, reduce the gained count (net effect)
                    if role in all_roles_gained:
                        all_roles_gained[role] -= 1
                        if all_roles_gained[role] <= 0:
                            del all_roles_gained[role]
                
                # Update "before" state for next iteration
                before_tags_set = after_tags_set
                before_roles_set = after_roles_set
                
            except Exception as e:
                error_msg = str(e).lower()
                if "illegal" in error_msg or "not a legal" in error_msg:
                    # This move can't be played (likely wrong side to move or already played)
                    # Skip it - the starting position might already include this move
                    print(f"   ⚠️ [NET_CHANGES] Move {move_idx+1} ({move_clean}) cannot be played from current position (likely already played or wrong side). Skipping.")
                else:
                    print(f"   ⚠️ [NET_CHANGES] Failed to process move {move_idx+1} ({move_clean}): {e}")
                # Continue with next move even if this one fails
                continue
        
        print(f"   📊 [NET_CHANGES] Processed {len(moves)} moves")
        
        # Return only tags/roles with net positive count (actually gained/lost overall after canceling)
        tags_gained_net = [tag for tag, count in all_tags_gained.items() if count > 0]
        tags_lost_net = [tag for tag, count in all_tags_lost.items() if count > 0]
        roles_gained_net = [role for role, count in all_roles_gained.items() if count > 0]
        roles_lost_net = [role for role, count in all_roles_lost.items() if count > 0]
        
        print(f"   📊 [NET_CHANGES] Final net changes: gained {len(tags_gained_net)} tags, {len(roles_gained_net)} roles; lost {len(tags_lost_net)} tags, {len(roles_lost_net)} roles")
        
        # Material change net: Use eval_drop as approximation if available
        # In practice, material_change should come from investigation_result
        # For now, we'll return None and let _attach_rich_evidence use material_change from inv
        material_change_net = None
        
        return tags_gained_net, tags_lost_net, roles_gained_net, roles_lost_net, material_change_net
    
    def _extract_tag_deltas_from_pgn(self, pgn_exploration: str) -> List[Dict[str, Any]]:
        """
        Extract tag and role deltas from PGN exploration.
        Parses the format: MOVE {[gained: tag1, tag2], [lost: tag3], [roles_gained: ...], [roles_lost: ...], [threats: threat1]}
        Handles comments that may include other annotations before the tag delta comment.
        NOTE: Investigator generates [threats: ...], not [two_move: ...]
        
        Returns:
            List of dicts with move, tags_gained, tags_lost, roles_gained, roles_lost, threats_output
        """
        import re
        import hashlib

        # Memoize by content hash (PGN strings can be large; hash key keeps cache small)
        try:
            h = hashlib.md5((pgn_exploration or "").encode("utf-8")).hexdigest()
            cached = self._pgn_tag_deltas_cache.get(h)
            if cached is not None:
                return cached
        except Exception:
            h = None
        
        tag_deltas = []
        
        # Pattern to match: MOVE {[gained: ...], [lost: ...], [roles_gained: ...], [roles_lost: ...], [threats: ...]}
        # Handles both white and black moves (with and without ...)
        # Allows for optional annotations (like [%eval ...] [%theme ...]) before the tag delta comment
        # The comment may be on the same line or next line after the move
        # Use DOTALL to allow . to match newlines within the comment
        # NOTE: Investigator generates [threats: ...], not [two_move: ...]
        # Updated pattern to include roles_gained and roles_lost
        pattern = r'(\d+\.\s*(?:\.\.\.\s*)?\S+)\s+(?:[^\{\n]*?\s+)?\{\[gained:\s*([^\]]+)\],\s*\[lost:\s*([^\]]+)\],\s*\[roles_gained:\s*([^\]]+)\],\s*\[roles_lost:\s*([^\]]+)\],\s*\[threats:\s*([^\]]+)\]\}'
        
        matches = re.findall(pattern, pgn_exploration, re.MULTILINE | re.DOTALL)
        
        # If no matches, try a more permissive pattern to find any comments with "gained"
        if len(matches) == 0:
            # Debug: Check if we're entering the fallback
            import sys
            print(f"   🔍 [SUMMARISER] Entering fallback pattern matching...")
            sys.stdout.flush()
            
            # Try to find any comment block containing "gained:" - handle nested braces
            # Use finditer to get all matches with their positions
            # Pattern: {[gained: ...], [lost: ...], [roles_gained: ...], [roles_lost: ...], [threats: ...]}
            # Allow for flexible whitespace and newlines between brackets and commas
            # NOTE: Investigator generates [threats: ...], not [two_move: ...]
            # Updated pattern to include roles_gained and roles_lost
            inner_pattern = r'\{\[gained:\s*([^\]]+)\]\s*,\s*\[lost:\s*([^\]]+)\]\s*,\s*\[roles_gained:\s*([^\]]+)\]\s*,\s*\[roles_lost:\s*([^\]]+)\]\s*,\s*\[threats:\s*([^\]]+)\]\s*\}'
            fallback_matches = list(re.finditer(inner_pattern, pgn_exploration, re.MULTILINE | re.DOTALL))
            
            # Debug: Log pattern matching results
            print(f"   🔍 [SUMMARISER] Fallback pattern found {len(fallback_matches)} matches")
            if len(fallback_matches) == 0:
                # Try a simpler pattern to see if we can find any "gained:" at all
                simple_pattern = r'\[gained:\s*([^\]]+)\]'
                simple_matches = list(re.finditer(simple_pattern, pgn_exploration, re.MULTILINE | re.DOTALL))
                print(f"   🔍 [SUMMARISER] Simple 'gained:' pattern found {len(simple_matches)} matches")
                if simple_matches:
                    # Show what the first match looks like
                    first_match = simple_matches[0]
                    context_start = max(0, first_match.start() - 50)
                    context_end = min(len(pgn_exploration), first_match.end() + 50)
                    context = pgn_exploration[context_start:context_end]
                    print(f"   🔍 [SUMMARISER] First 'gained:' match context: ...{context}...")
            sys.stdout.flush()
            
            if fallback_matches:
                print(f"   🔍 [SUMMARISER] Found {len(fallback_matches)} comments with tag deltas using fallback pattern")
                # For each match, find the full comment block and the move before it
                for i, match_obj in enumerate(fallback_matches):
                    gained = match_obj.group(1)
                    lost = match_obj.group(2)
                    roles_gained = match_obj.group(3)
                    roles_lost = match_obj.group(4)
                    two_move = match_obj.group(5)
                    comment_start = match_obj.start()
                    
                    # Find the start of the outer comment block (look backwards for opening {)
                    outer_start = pgn_exploration.rfind('{', 0, comment_start)
                    if outer_start != -1:
                        # Find the matching closing brace by counting braces
                        brace_count = 0
                        outer_end = outer_start
                        for j in range(outer_start, len(pgn_exploration)):
                            if pgn_exploration[j] == '{':
                                brace_count += 1
                            elif pgn_exploration[j] == '}':
                                brace_count -= 1
                                if brace_count == 0:
                                    outer_end = j + 1
                                    break
                        
                        # Look backwards from outer_start for the move
                        before_comment = pgn_exploration[:outer_start]
                        # Find the last move on a line before this comment
                        move_match = re.search(r'(\d+\.\s*(?:\.\.\.\s*)?\S+)\s*$', before_comment, re.MULTILINE)
                        if move_match:
                            move_san = move_match.group(1).strip()
                            matches.append((move_san, gained, lost, roles_gained, roles_lost, two_move))
                            if i < 3:  # Only log first 3
                                print(f"   🔍 [SUMMARISER] Recovered match {i+1}: move={move_san}, gained={gained[:50]}...")
                        else:
                            if i < 3:  # Debug why move matching failed
                                # Show a sample of what's before the comment
                                sample_before = before_comment[-100:] if len(before_comment) > 100 else before_comment
                                print(f"   🔍 [SUMMARISER] Failed to find move before comment {i+1} (outer_start={outer_start}, before_comment sample: ...{sample_before})")
                    else:
                        if i < 3:  # Debug why outer comment finding failed
                            print(f"   🔍 [SUMMARISER] Failed to find outer comment start for match {i+1} (comment_start={comment_start})")
        
        # Debug logging
        import sys
        print(f"   🔍 [SUMMARISER] PGN tag extraction: found {len(matches)} matches in PGN (length: {len(pgn_exploration)} chars)")
        if len(matches) == 0 and pgn_exploration:
            # Show a sample of the PGN to debug regex - look for moves with comments
            sample = pgn_exploration[:2000] if len(pgn_exploration) > 2000 else pgn_exploration
            print(f"   🔍 [SUMMARISER] PGN sample (first 2000 chars): {sample}")
            
            # Also try to find any lines with "gained:" to see the actual format
            lines_with_gained = [line for line in pgn_exploration.split('\n') if 'gained:' in line]
            if lines_with_gained:
                print(f"   🔍 [SUMMARISER] Found {len(lines_with_gained)} lines containing 'gained:', showing first 3:")
                for i, line in enumerate(lines_with_gained[:3]):
                    print(f"   🔍 [SUMMARISER]   Line {i+1}: {line[:200]}")
            else:
                # Try to find any comment blocks
                comment_pattern = r'\{[^}]*gained[^}]*\}'
                comment_matches = re.findall(comment_pattern, pgn_exploration)
                if comment_matches:
                    print(f"   🔍 [SUMMARISER] Found {len(comment_matches)} comment blocks with 'gained', showing first 3:")
                    for i, comment in enumerate(comment_matches[:3]):
                        print(f"   🔍 [SUMMARISER]   Comment {i+1}: {comment[:200]}")
        sys.stdout.flush()
        
        for match in matches:
            move_san = match[0].strip()
            gained_str = match[1].strip()
            lost_str = match[2].strip()
            # Handle both old format (without roles) and new format (with roles)
            if len(match) >= 6:
                # New format with roles
                roles_gained_str = match[3].strip()
                roles_lost_str = match[4].strip()
                threats_str = match[5].strip()
            else:
                # Old format without roles (backward compatibility)
                roles_gained_str = "none"
                roles_lost_str = "none"
                threats_str = match[3].strip() if len(match) > 3 else "none"
            
            # Parse tags gained (handle "none" and "+X more")
            tags_gained = []
            if gained_str != "none":
                tags_gained = [t.strip() for t in gained_str.split(",") if t.strip() and not t.strip().startswith("(+")]
            
            # Parse tags lost (handle "none" and "+X more")
            tags_lost = []
            if lost_str != "none":
                tags_lost = [t.strip() for t in lost_str.split(",") if t.strip() and not t.strip().startswith("(+")]
            
            # NEW: Parse roles gained (handle "none" and "+X more")
            roles_gained = []
            if roles_gained_str != "none":
                roles_gained = [t.strip() for t in roles_gained_str.split(",") if t.strip() and not t.strip().startswith("(+")]
            
            # NEW: Parse roles lost (handle "none" and "+X more")
            roles_lost = []
            if roles_lost_str != "none":
                roles_lost = [t.strip() for t in roles_lost_str.split(",") if t.strip() and not t.strip().startswith("(+")]
            
            # Parse threats output (investigator generates [threats: ...], not [two_move: ...])
            threats_items = []
            if threats_str != "none":
                threats_items = [t.strip() for t in threats_str.split(",") if t.strip() and not t.strip().startswith("(+")]
            
            tag_deltas.append({
                "move": move_san,
                "tags_gained": tags_gained,
                "tags_lost": tags_lost,
                "roles_gained": roles_gained,  # NEW
                "roles_lost": roles_lost,  # NEW
                "threats_output": threats_items  # Changed from two_move_output to threats_output
            })
        
        # Debug logging
        if tag_deltas:
            total_gained = sum(len(td["tags_gained"]) for td in tag_deltas)
            total_lost = sum(len(td["tags_lost"]) for td in tag_deltas)
            total_roles_gained = sum(len(td.get("roles_gained", [])) for td in tag_deltas)
            total_roles_lost = sum(len(td.get("roles_lost", [])) for td in tag_deltas)
            print(f"   🔍 [SUMMARISER] Extracted {len(tag_deltas)} moves with tag deltas: {total_gained} gained, {total_lost} lost")
            print(f"   🔍 [SUMMARISER] Extracted role deltas: {total_roles_gained} gained, {total_roles_lost} lost")
            sys.stdout.flush()
        
        # Store in cache (best-effort bounded)
        try:
            if h:
                if len(self._pgn_tag_deltas_cache) > 64:
                    self._pgn_tag_deltas_cache.pop(next(iter(self._pgn_tag_deltas_cache)))
                self._pgn_tag_deltas_cache[h] = tag_deltas
        except Exception:
            pass
        return tag_deltas
    
    def _extract_pgn_sequence_with_deltas(self, pgn_exploration: str) -> Dict[str, Any]:
        """
        Extract the main sequence from PGN with tag deltas for each move.
        
        Returns:
            Dict with starting_tags, main_sequence (list of moves with deltas)
        """
        import re
        
        # Extract starting tags
        starting_tags_match = re.search(r'\[Starting tags:\s*([^\]]+)\]', pgn_exploration)
        starting_tags = []
        if starting_tags_match:
            starting_tags = [t.strip() for t in starting_tags_match.group(1).split(",")]
        
        # NEW: Extract starting roles
        starting_roles_match = re.search(r'\[Starting roles:\s*([^\]]+)\]', pgn_exploration)
        starting_roles = []
        if starting_roles_match:
            starting_roles = [t.strip() for t in starting_roles_match.group(1).split(",")]
        
        # Extract main sequence moves with their tag and role deltas
        tag_deltas = self._extract_tag_deltas_from_pgn(pgn_exploration)
        
        return {
            "starting_tags": starting_tags,
            "starting_roles": starting_roles,  # NEW
            "main_sequence": tag_deltas
        }
    
    def _format_pgn_with_tag_deltas(self, pgn_exploration: str) -> str:
        """
        Format PGN with tag and role deltas in a readable format for LLM.
        
        Returns:
            Formatted string showing moves with their tag and role changes
        """
        tag_deltas = self._extract_tag_deltas_from_pgn(pgn_exploration)
        
        if not tag_deltas:
            return pgn_exploration[:1000]  # Return first 1000 chars if no deltas
        
        formatted_lines = []
        for delta in tag_deltas[:20]:  # Limit to first 20 moves
            move = delta.get("move", "?")
            tags_gained = delta.get("tags_gained", [])
            tags_lost = delta.get("tags_lost", [])
            roles_gained = delta.get("roles_gained", [])
            roles_lost = delta.get("roles_lost", [])
            
            line = f"Move {move}:"
            if tags_gained:
                line += f" Gained tags: {', '.join(tags_gained[:3])}"
            if tags_lost:
                line += f" Lost tags: {', '.join(tags_lost[:3])}"
            if roles_gained:
                line += f" Gained roles: {', '.join(roles_gained[:3])}"
            if roles_lost:
                line += f" Lost roles: {', '.join(roles_lost[:3])}"
            if not tags_gained and not tags_lost and not roles_gained and not roles_lost:
                line += " No significant changes"
            
            formatted_lines.append(line)
        
        return "\n".join(formatted_lines)

    def _get_structured_deltas_from_inv(self, inv: "InvestigationResult") -> Optional[Dict[str, Any]]:
        """
        Prefer Investigator-provided structured deltas (no PGN regex parsing).
        Fallback to PGN parsing only if structured fields are missing (backward compat).
        """
        per_move = getattr(inv, "evidence_per_move_deltas", None)
        if isinstance(per_move, list) and per_move:
            return {"main_sequence": per_move}
        pgn_expl = getattr(inv, "pgn_exploration", "") or ""
        if isinstance(pgn_expl, str) and pgn_expl.strip():
            return self._extract_pgn_sequence_with_deltas(pgn_expl)
        return None

    def _format_structured_deltas_for_llm(self, deltas: List[Dict[str, Any]], cap_moves: int = 20) -> str:
        """
        Lightweight formatter for Investigator-provided per-move deltas (avoids PGN regex).
        """
        if not deltas:
            return "No deltas available"
        lines: List[str] = []
        for d in deltas[:cap_moves]:
            move = d.get("move", "?")
            tg = d.get("tags_gained", []) or []
            tl = d.get("tags_lost", []) or []
            rg = d.get("roles_gained", []) or []
            rl = d.get("roles_lost", []) or []
            parts = [f"Move {move}:"]
            if tg:
                parts.append(f"Gained tags: {', '.join(tg[:3])}")
            if tl:
                parts.append(f"Lost tags: {', '.join(tl[:3])}")
            if rg:
                parts.append(f"Gained roles: {', '.join(rg[:3])}")
            if rl:
                parts.append(f"Lost roles: {', '.join(rl[:3])}")
            lines.append(" ".join(parts))
        return "\n".join(lines)
    
    def _extract_d2_vs_d16_comparison(self, investigation_result: InvestigationResult) -> Dict[str, Any]:
        """
        Extract D2 vs D16 comparison to understand if D16 move is obvious.
        
        Returns:
            Dict with comparison data
        """
        comparison = {
            "d16_best_move": investigation_result.best_move_d16,
            "d16_eval": investigation_result.eval_d16,
            "d2_eval": investigation_result.eval_d2,
            "d2_top_moves": investigation_result.top_moves_d2[:3] if investigation_result.top_moves_d2 else [],
            "overestimated_moves": investigation_result.overestimated_moves,
            "is_critical": investigation_result.is_critical,
            "is_winning": investigation_result.is_winning,
            "second_best_d16": investigation_result.second_best_move_d16,
            "second_best_d16_eval_cp": investigation_result.second_best_move_d16_eval_cp
        }
        
        # Check if D2 suggests different moves than D16
        d2_suggests_different = False
        if investigation_result.top_moves_d2 and investigation_result.best_move_d16:
            # Get D2 top move UCI
            d2_top_move_uci = investigation_result.top_moves_d2[0].get("move", "")
            # Check if D16 best move is in D2 top 3
            d2_top_3_ucis = [m.get("move", "") for m in investigation_result.top_moves_d2[:3]]
            if investigation_result.best_move_d16 not in d2_top_3_ucis:
                d2_suggests_different = True
        
        comparison["d2_suggests_different"] = d2_suggests_different
        
        return comparison
    
    def _select_primary_narrative(self, investigation_result: InvestigationResult) -> str:
        """
        Deterministically select exactly ONE primary narrative reason.
        
        Priority order:
        1. missed_move + has_threats (tactical blindness)
        2. intent_mismatch (wrong moment)
        3. material_change (material error)
        4. eval_drop + urgency (time pressure)
        5. Default fallback
        
        Returns:
            One of: "missed_forcing_reply", "played_slow_move_under_threat", 
            "allowed_structural_damage", "misjudged_equal_trade", "tactical_blindness",
            "positional_concession_without_compensation", "time_pressure_error"
        """
        # Priority 1: missed_move + has_threats
        if investigation_result.missed_move and investigation_result.has_threats:
            return "tactical_blindness"
        
        # Priority 2: intent_mismatch
        if investigation_result.intent_mismatch:
            return "positional_concession_without_compensation"
        
        # Priority 3: material_change
        if investigation_result.material_change:
            return "misjudged_equal_trade"
        
        # Priority 4: eval_drop + urgency (time pressure)
        if investigation_result.urgency and investigation_result.eval_drop and abs(investigation_result.eval_drop) > 0.5:
            if "time" in investigation_result.urgency.lower() or "pressure" in investigation_result.urgency.lower():
                return "time_pressure_error"
        
        # Default fallback
        return "positional_concession_without_compensation"
    
    def _select_psychological_frame(
        self,
        investigation_result: InvestigationResult,
        primary_narrative: str,
        user_goal: Optional[str] = None
    ) -> str:
        """
        Deterministically derive psychological frame from intent_mismatch, urgency.
        
        Args:
            investigation_result: Investigation result
            primary_narrative: Primary narrative reason
            user_goal: User's stated goal (e.g. "develop", "castling")
        
        Returns:
            Mandatory psychological frame string
        """
        # NEW: Check if this is a development question (not a mistake)
        if user_goal == "develop":
            return "the position is temporarily awkward"
        
        # Map primary narrative to frame
        narrative_to_frame = {
            "missed_forcing_reply": "missed a concrete reply",
            "played_slow_move_under_threat": "reasonable idea, wrong moment",
            "allowed_structural_damage": "position looked safe but wasn't",
            "misjudged_equal_trade": "evaluation error in calculation",
            "tactical_blindness": "missed a tactical opportunity",
            "positional_concession_without_compensation": "reasonable idea, wrong moment",
            "time_pressure_error": "played for simplicity under pressure"
        }
        
        # Check if we have a direct mapping
        if primary_narrative in narrative_to_frame:
            base_frame = narrative_to_frame[primary_narrative]
        else:
            base_frame = "reasonable idea, wrong moment"
        
        # Override based on urgency if present
        if investigation_result.urgency:
            urgency_lower = investigation_result.urgency.lower()
            if "time" in urgency_lower or "pressure" in urgency_lower:
                return "played for simplicity under pressure"
            elif "critical" in urgency_lower:
                return "missed a concrete reply"
        
        # Override based on intent_mismatch
        if investigation_result.intent_mismatch:
            return "reasonable idea, wrong moment"
        
        return base_frame
    
    def _extract_user_goal(self, user_message: str) -> Optional[str]:
        """
        Extract user's stated goal from message.
        
        Returns:
            Goal string like "castling", "attack", "simplify", or None
        """
        import re
        msg_lower = user_message.lower()
        
        if re.search(r"castle|castling", msg_lower):
            return "castling"
        if re.search(r"attack|aggressive|strike", msg_lower):
            return "attack"
        if re.search(r"simplify|trade|exchange", msg_lower):
            return "simplify"
        if re.search(r"defend|defense|safe", msg_lower):
            return "defend"
        if re.search(r"develop|development", msg_lower):
            return "develop"
        
        return None

    def _build_explainer_template(
        self,
        *,
        narrative_decision: NarrativeDecision,
        user_message: str
    ) -> Dict[str, Any]:
        """
        Build a pre-cooked, clause-by-clause template for the Explainer.
        This is NOT prose. It is a deterministic plan that ties each clause to a Claim
        and its evidence payload.
        """
        import re
        goal = self._extract_user_goal(user_message) if user_message else None
        user_goal_text = user_message.strip() if user_message else ""
        if not user_goal_text:
            user_goal_text = f"user_goal={goal}" if goal else "no_user_goal_provided"

        # Detect if user proposed a concrete move (SAN-like)
        user_move_mentioned = None
        if user_message:
            san_pattern = r"\b([NBRQK]?[a-h]?[1-8]?x?[a-h][1-8](?:=[NBRQ])?[+#]?|O-O(?:-O)?)\b"
            m = re.search(san_pattern, user_message, re.IGNORECASE)
            if m:
                user_move_mentioned = m.group(1)

        # Recommended move: prefer an explicit recommendation claim
        recommended_move = None
        for c in (narrative_decision.claims or []):
            if getattr(c, "hints", None) and getattr(c.hints, "role", None) == "recommendation":
                if c.evidence_moves and isinstance(c.evidence_moves, list) and c.evidence_moves:
                    recommended_move = c.evidence_moves[0]
                    break
        if not recommended_move:
            # fallback: first evidence move from any claim
            for c in (narrative_decision.claims or []):
                if c.evidence_moves and isinstance(c.evidence_moves, list) and c.evidence_moves:
                    recommended_move = c.evidence_moves[0]
                    break

        # Decide template comparison mode:
        # - If the user mentioned a move, treat as move_comparison against best move (baseline=user_move).
        # - If we have a valid comparison claim, treat as move_comparison (baseline=alt_move).
        # - Otherwise treat as position_comparison against theme requirements (baseline=none).
        has_valid_comparison = False
        for c in (narrative_decision.claims or []):
            role = getattr(getattr(c, "hints", None), "role", None)
            if role == "comparison":
                ev = c.evidence_moves or []
                if isinstance(ev, list) and len(ev) >= 2 and ev[0] != ev[1]:
                    has_valid_comparison = True
                    break

        if user_move_mentioned:
            comparison_type = "move_comparison"
            baseline = "user_move"
            theme = goal or "general"
        elif has_valid_comparison:
            comparison_type = "move_comparison"
            baseline = "alt_move"
            theme = goal or "general"
        else:
            comparison_type = "position_comparison"
            baseline = "none"
            theme = goal or "general"

        # Build a position assessment (theme readiness) for baseline=none (or always, but only rendered when needed)
        # Keep it evidence-locked: only use already extracted themes/tags/PGN.
        themes_from_refined = []
        if narrative_decision.refined_pgn and narrative_decision.refined_pgn.themes:
            themes_from_refined = list(narrative_decision.refined_pgn.themes)[:8]

        first_payload = None
        for c in (narrative_decision.claims or []):
            if getattr(c, "evidence_payload", None):
                first_payload = c.evidence_payload
                break

        evidence_themes = themes_from_refined or (first_payload.theme_tags if first_payload else [])
        evidence_tags = first_payload.raw_tags if first_payload else []
        evidence_pgn = first_payload.pgn_line if first_payload else None

        # Extract recommendation payload BEFORE reconciliation logic
        rec_payload = None
        for c in (narrative_decision.claims or []):
            if getattr(c, "hints", None) and getattr(c.hints, "role", None) == "recommendation":
                rec_payload = getattr(c, "evidence_payload", None)
                break
        if not rec_payload:
            # fallback: first payload from any claim
            for c in (narrative_decision.claims or []):
                if getattr(c, "evidence_payload", None):
                    rec_payload = c.evidence_payload
                    break
        
        rec_eval_after = rec_payload.eval_after if rec_payload else None
        
        # Simple timing classification from psychological frame (avoid inventing eval logic here)
        # BUT: If final_verdict recommends a move, reconcile timing to align with recommendation
        frame_lower = (narrative_decision.psychological_frame or "").lower()
        if "wrong moment" in frame_lower or "not the right moment" in frame_lower:
            timing = "no"
        elif "right moment" in frame_lower or "good moment" in frame_lower:
            timing = "yes"
        else:
            timing = "unclear"
        
        # RECONCILIATION: If we have a strong recommendation (final_verdict), adjust timing
        # to avoid contradiction (e.g., "wrong moment" but "play Ng5" -> make timing "unclear" or "yes")
        if recommended_move and rec_eval_after is not None:
            # If eval_after is positive or only slightly negative, it's a good move despite frame
            if rec_eval_after >= -0.3:  # Within 0.3 pawns of equality
                if timing == "no":
                    timing = "unclear"  # Soften "wrong moment" if move is actually good
            # If eval_after is strongly positive, override to "yes"
            if rec_eval_after >= 0.5:
                timing = "yes"

        position_assessment = {
            "theme": theme,
            "baseline": baseline,
            "comparison_type": comparison_type,
            "is_good_time": timing,
            "reasons": [
                narrative_decision.mechanism,
            ] if narrative_decision.mechanism else [],
            "evidence": {
                "themes": evidence_themes[:8] if isinstance(evidence_themes, list) else [],
                "raw_tags": evidence_tags[:12] if isinstance(evidence_tags, list) else [],
                "pgn": evidence_pgn,
            }
        }

        # Deterministic final verdict to reconcile "best move" with any risk clauses.
        # Evidence-locked to recommendation payload: eval + material change.
        has_consequence = any(getattr(getattr(c, "hints", None), "role", None) == "consequence" for c in (narrative_decision.claims or []))
        rec_eval_drop = rec_payload.eval_drop if rec_payload else None
        rec_material = rec_payload.material_change if rec_payload else None

        if recommended_move:
            verdict = f"Final verdict: play {recommended_move}."
            if rec_eval_after is not None:
                verdict += f" Eval_after={rec_eval_after:+.2f}."
            if rec_eval_drop is not None:
                verdict += f" Δeval={rec_eval_drop:+.2f}."
            if rec_material is not None and abs(rec_material) > 0.001:
                verdict += f" Δmaterial={rec_material:+.1f} pawns."
            if has_consequence:
                verdict += " It may be sharp, but it’s still the best by eval—accept the risk and play precisely."
        else:
            verdict = "Final verdict: no clear recommendation available."

        # Candidate moves shortlist (evidence-locked).
        # Prefer moves_of_interest from refined PGN (comes from execution plan / investigated moves),
        # otherwise fall back to unique moves mentioned in claims.
        candidate_pool: List[str] = []
        if narrative_decision.refined_pgn and narrative_decision.refined_pgn.moves_of_interest:
            for m in narrative_decision.refined_pgn.moves_of_interest:
                if isinstance(m, str) and m:
                    candidate_pool.append(m)
        else:
            for c in (narrative_decision.claims or []):
                for m in (c.evidence_moves or []):
                    if isinstance(m, str) and m:
                        candidate_pool.append(m)

        # Dedup while preserving order
        seen = set()
        candidate_pool = [m for m in candidate_pool if not (m in seen or seen.add(m))]

        # Keep only top 3, and ensure recommended move (if present) is first
        if recommended_move and recommended_move in candidate_pool:
            candidate_pool = [recommended_move] + [m for m in candidate_pool if m != recommended_move]
        candidate_pool = candidate_pool[:3]
        
        # Debug logging
        import sys
        print(f"   🔍 [TEMPLATE] Candidate pool: {candidate_pool}")
        print(f"   🔍 [TEMPLATE] Recommended move: {recommended_move}")
        sys.stdout.flush()

        # Bind candidate metadata from existing claims (no new analysis)
        # Enhanced: Also check consequence claims and ensure all data is extracted
        candidates: List[Dict[str, Any]] = []
        for mv in candidate_pool:
            best_payload = None
            best_role = None
            best_eval_drop = None
            best_material = None
            best_tactic_tags = []
            
            # Search through all claims to find the best payload for this move
            for c in (narrative_decision.claims or []):
                if c.evidence_moves and isinstance(c.evidence_moves, list) and mv in c.evidence_moves:
                    payload = getattr(c, "evidence_payload", None)
                    if not payload:
                        continue
                    # Prefer recommendation payload, then comparison/consequence
                    role_c = getattr(getattr(c, "hints", None), "role", None)
                    score = 0
                    if role_c == "recommendation":
                        score = 3
                    elif role_c == "comparison":
                        score = 2
                    elif role_c == "consequence":
                        score = 1
                    else:
                        score = 0  # Other roles (detail, mechanism, etc.)
                    
                    current_best_score = (3 if best_role == "recommendation" else 2 if best_role == "comparison" else 1 if best_role == "consequence" else 0)
                    if best_payload is None or score > current_best_score:
                        best_payload = payload
                        best_role = role_c
                        best_eval_drop = payload.eval_drop
                        best_material = payload.material_change
                        best_tactic_tags = payload.tactic_tags if payload.tactic_tags else []
            
            # If we found a payload, use it; otherwise create minimal candidate entry
            candidate_entry = {
                "move": mv,
                "role": best_role,
                "is_recommended": bool(recommended_move and mv == recommended_move),
                "evidence_pgn": best_payload.pgn_line if best_payload else None,
                "themes": best_payload.theme_tags if best_payload else [],
                "two_move": best_payload.two_move if best_payload else None,
                "eval_drop": best_eval_drop,  # Can be None if not found
                "material_change": best_material,  # Can be None if not found
                "tactic_tags": best_tactic_tags,  # Empty list if not found
            }
            candidates.append(candidate_entry)
            
            # Debug logging for candidate data
            import sys
            print(f"   🔍 [TEMPLATE] Candidate {mv}: eval_drop={best_eval_drop}, material={best_material}, tactics={len(best_tactic_tags)}")
            sys.stdout.flush()

        outline: List[Dict[str, Any]] = []

        # If there is no real move-vs-move baseline, lead with a position_comparison section.
        if baseline == "none":
            outline.append({
                "clause_id": "P0",
                "claim_ref": None,
                "role": "position_comparison",
                "skip": False,
                "must_include": [
                    "Describe the position relative to the requested theme (e.g., attack readiness).",
                    "State whether it is a good time to pursue the theme (yes/no/unclear) without inventing evidence.",
                    "Use only themes/tags/PGN provided in evidence."
                ],
                "position_assessment": position_assessment
            })
            outline.append({
                "clause_id": "P1",
                "claim_ref": None,
                "role": "candidate_moves",
                "skip": False,
                "must_include": [
                    "List up to 3 best candidate moves for the theme (from investigated moves only).",
                    "Mark which one is recommended.",
                    "Use PV/PGN evidence if available for each move; do not invent lines."
                ],
                "candidates": candidates
            })
        for idx, claim in enumerate(narrative_decision.claims or []):
            claim_ref = idx + 1
            role = getattr(getattr(claim, "hints", None), "role", None) or "detail"

            # Skip-invalid comparison rule:
            # - If evidence moves collapse to the same SAN, or
            # - summary is "X better than X"
            skip_clause = False
            if role == "comparison":
                ev = claim.evidence_moves or []
                if isinstance(ev, list) and len(ev) >= 2 and ev[0] == ev[1]:
                    skip_clause = True
                if isinstance(claim.summary, str) and " better than " in claim.summary:
                    try:
                        parts = claim.summary.split(" better than ")
                        if len(parts) >= 2:
                            left = parts[0].strip().split()[-1]
                            right = parts[1].strip().split()[0]
                            if left == right:
                                skip_clause = True
                    except Exception:
                        pass

            # Clause requirements by role
            must_include: List[str] = []
            if role == "comparison":
                must_include = [
                    "State which move is better and why (from claim.summary).",
                    "Include inline PGN evidence if available (claim.evidence_payload.pgn_line).",
                    "If comparison is invalid (same move vs same move), skip this clause."
                ]
            elif role == "recommendation":
                must_include = [
                    "Name the recommended move (SAN) and immediate purpose.",
                    "Include inline PGN evidence if available (claim.evidence_payload.pgn_line).",
                    "Do not introduce new candidate moves not present in claims."
                ]
            elif role == "consequence":
                must_include = [
                    "Explain the main downside of the inferior move (from claim.summary).",
                    "Include inline PGN evidence if available (claim.evidence_payload.pgn_line).",
                    "If two_move indicates mate_threat, phrase as dangerous threat (not 'slightly inferior')."
                ]
            else:
                must_include = [
                    "Restate the claim summary in natural language without adding new analysis.",
                    "Keep evidence locked to payload."
                ]

            payload = getattr(claim, "evidence_payload", None)
            outline.append({
                "clause_id": f"C{len(outline) + 1}",
                "claim_ref": claim_ref,
                "role": role,
                "skip": skip_clause,
                "must_include": must_include,
                "evidence": {
                    "pgn": payload.pgn_line if payload else None,
                    "themes": payload.theme_tags if payload else [],
                    "raw_tags": payload.raw_tags if payload else [],
                    "two_move": payload.two_move if payload else None,
                    "eval_before": payload.eval_before if payload else None,
                    "eval_after": payload.eval_after if payload else None,
                    "eval_drop": payload.eval_drop if payload else None,
                }
            })

        closing_takeaway = None
        if narrative_decision.takeaway and isinstance(narrative_decision.takeaway, Claim):
            closing_takeaway = narrative_decision.takeaway.summary

        return {
            "user_goal": user_goal_text,
            "recommended_move": recommended_move,
            "psychological_frame": narrative_decision.psychological_frame,
            "core_message": narrative_decision.core_message,
            "comparison_type": comparison_type,
            "baseline": baseline,
            "theme": theme,
            "position_assessment": position_assessment,
            "candidates": candidates,
            "final_verdict": verdict,
            "outline": outline,
            "closing_takeaway": closing_takeaway,
        }
    
    def _resolve_piece_identity(
        self,
        fen: str,
        piece_type: str,
        color: str,
        user_goal: Optional[str] = None
    ) -> Optional[Dict[str, str]]:
        """
        Resolve piece to its actual square on the board.
        
        Args:
            fen: FEN string of the position
            piece_type: Piece type ("knight", "bishop", "rook", "queen", "king", "pawn")
            color: Piece color ("white" or "black")
            user_goal: Optional user goal for disambiguation (e.g., "castling")
        
        Returns:
            {"type": piece_type, "color": color, "square": "square_name"} or None if not found
        """
        import chess
        
        try:
            board = chess.Board(fen)
            piece_color = chess.WHITE if color.lower() == "white" else chess.BLACK
            
            # Map piece type string to chess constant
            type_map = {
                "knight": chess.KNIGHT,
                "bishop": chess.BISHOP,
                "rook": chess.ROOK,
                "queen": chess.QUEEN,
                "king": chess.KING,
                "pawn": chess.PAWN
            }
            chess_piece_type = type_map.get(piece_type.lower(), None)
            if chess_piece_type is None:
                return None
            
            # Enumerate all pieces of this type and color
            pieces = list(board.pieces(chess_piece_type, piece_color))
            
            if len(pieces) == 0:
                return None
            
            if len(pieces) == 1:
                # Only one piece, return it
                square = chess.square_name(pieces[0])
                return {
                    "type": piece_type.lower(),
                    "color": color.lower(),
                    "square": square
                }
            
            # Multiple pieces exist - need to disambiguate
            # For castling goal, prefer king-side pieces
            if user_goal == "castling":
                if chess_piece_type == chess.KNIGHT:
                    # For castling, prefer king-side knight
                    # King-side is files e-h for white, e-h for black
                    king_side_pieces = [
                        sq for sq in pieces
                        if chess.square_file(sq) >= 4  # Files e-h (4-7)
                    ]
                    if king_side_pieces:
                        square = chess.square_name(king_side_pieces[0])
                        return {
                            "type": piece_type.lower(),
                            "color": color.lower(),
                            "square": square
                        }
                elif chess_piece_type == chess.ROOK:
                    # For castling, prefer king-side rook
                    king_side_rooks = [
                        sq for sq in pieces
                        if chess.square_file(sq) >= 4
                    ]
                    if king_side_rooks:
                        square = chess.square_name(king_side_rooks[0])
                        return {
                            "type": piece_type.lower(),
                            "color": color.lower(),
                            "square": square
                        }
            
            # Default: return first piece found (ambiguous)
            square = chess.square_name(pieces[0])
            return {
                "type": piece_type.lower(),
                "color": color.lower(),
                "square": square
            }
        except Exception:
            return None
    
    def _infer_candidate_piece(
        self,
        investigation_result: InvestigationResult,
        user_goal: Optional[str],
        piece_type: str
    ) -> Optional[Dict[str, str]]:
        """
        Infer which specific piece is the candidate for development.
        
        Args:
            investigation_result: Investigation result with board state
            user_goal: User's stated goal (e.g., "castling", "develop")
            piece_type: Type of piece to find (e.g., "knight")
        
        Returns:
            Piece identity dict or None if ambiguous/not found
        """
        # Get FEN from investigation result
        fen = None
        if investigation_result.light_raw_analysis:
            fen = investigation_result.light_raw_analysis.fen
        elif hasattr(investigation_result, 'eval_before') and investigation_result.eval_before is not None:
            # Try to get FEN from context - this is a fallback
            # In practice, FEN should be in light_raw_analysis
            return None
        
        if not fen:
            return None
        
        # Determine color from user goal or default to white
        # In practice, this should come from the board state
        color = "white"  # Default - could be improved to detect from FEN
        
        # Resolve piece identity
        return self._resolve_piece_identity(fen, piece_type, color, user_goal)
    
    def _select_mechanism(
        self,
        investigation_result: InvestigationResult,
        selected_tags: List[Dict[str, Any]],
        consequences: Dict[str, Any]
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        Deterministically select ONE concrete mechanism from VERIFIED consequences only.
        
        Priority:
        1. Verified awkward mechanisms (for development questions)
        2. Verified consequences (only if explicitly in consequences dict)
        3. Tags (only if they represent verified board state)
        4. Move intent (as fallback)
        
        Returns:
            Tuple of (mechanism_string, evidence_dict)
            evidence_dict: {"type": "pv"|"pgn"|"two_move"|"board_check", "source": str, "verified": bool}
        """
        # PRIORITY 1: Verified awkward mechanisms (for development questions)
        if consequences and "awkward_mechanism" in consequences:
            awkward_type = consequences["awkward_mechanism"]
            mechanism_map = {
                "allows_structural_damage": "allows opponent to damage your pawn structure",
                "allows_tactical_capture": "allows opponent to capture with advantage",
                "blocked_by_enemy_piece": "is blocked by an enemy piece",
                "leaves_king_exposed": "leaves your king exposed",
                "loses_tempo_under_threat": "loses tempo when you should address a threat first"
            }
            mechanism = mechanism_map.get(awkward_type, "is awkward for development")
            # Evidence: from board_check (verified in _detect_awkward_mechanism)
            evidence = {
                "type": "board_check",
                "source": awkward_type,
                "verified": True
            }
            return (mechanism, evidence)
        
        # PRIORITY 2: Verified consequences (only if explicitly in consequences dict)
        if consequences:
            # Only use if explicitly verified in consequences
            if "doubled_pawns" in consequences:
                doubled_info = consequences["doubled_pawns"]
                if doubled_info and isinstance(doubled_info, dict) and doubled_info.get("doubled"):
                    evidence = {
                        "type": "board_check",
                        "source": "doubled_pawns",
                        "verified": True
                    }
                    return ("forces pawn structure that weakens your position", evidence)
            
            if "allows_captures" in consequences:
                captures = consequences.get("allows_captures", [])
                if captures and isinstance(captures, list) and len(captures) > 0:
                    # Only return if captures are actually verified
                    evidence = {
                        "type": "board_check",
                        "source": f"capture_{captures[0]}",
                        "verified": True
                    }
                    return (f"allows opponent to capture ({captures[0]})", evidence)
            
            if "pins" in consequences:
                pin_info = consequences.get("pins", {})
                # Handle both new format (dict with newly_created) and legacy format (list)
                if isinstance(pin_info, dict):
                    pins = pin_info.get("pins", [])
                    newly_created = pin_info.get("newly_created", [])
                    has_new_pins = pin_info.get("has_new_pins", False)
                else:
                    # Legacy format - assume it's a list
                    pins = pin_info if isinstance(pin_info, list) else []
                    newly_created = pins  # Assume all are new if legacy format
                    has_new_pins = len(pins) > 0
                
                if pins and len(pins) > 0:
                    evidence = {
                        "type": "board_check",
                        "source": "pins",
                        "verified": True
                    }
                    # Only say "creates" if pins were newly created
                    if has_new_pins and newly_created and len(newly_created) > 0:
                        # Get details of first newly created pin for specificity
                        first_new_pin = newly_created[0] if newly_created else None
                        if first_new_pin and isinstance(first_new_pin, dict):
                            pinned_piece = first_new_pin.get("pinned_piece", "piece")
                            return (f"creates a pin on your {pinned_piece}", evidence)
                        else:
                            return ("creates a pin", evidence)
                    else:
                        # Pin was pre-existing - describe it differently
                        first_pin = pins[0] if pins else None
                        if first_pin and isinstance(first_pin, dict):
                            pinned_piece = first_pin.get("pinned_piece", "piece")
                            return (f"involves a pin on your {pinned_piece}", evidence)
                        else:
                            return ("involves a pin", evidence)
        
        # PRIORITY 2.5: Roles (check roles first, then fallback to tags)
        if hasattr(investigation_result, 'light_raw_analysis') and investigation_result.light_raw_analysis:
            light_raw = investigation_result.light_raw_analysis
            if hasattr(light_raw, 'roles') and light_raw.roles:
                # Extract starting roles and role deltas from PGN exploration if available
                starting_roles = None
                role_deltas = None
                
                if hasattr(investigation_result, 'pgn_exploration') and investigation_result.pgn_exploration:
                    # Extract starting roles from PGN
                    pgn_seq = self._extract_pgn_sequence_with_deltas(investigation_result.pgn_exploration)
                    if pgn_seq:
                        # Starting roles are stored as a list of strings in format "piece_id:role"
                        starting_roles_list = pgn_seq.get("starting_roles", [])
                        if starting_roles_list:
                            # Convert list format to dict format for easier lookup
                            starting_roles = {}
                            for role_str in starting_roles_list:
                                if ":" in role_str:
                                    piece_id, role = role_str.split(":", 1)
                                    if piece_id not in starting_roles:
                                        starting_roles[piece_id] = []
                                    starting_roles[piece_id].append(role)
                        
                        # Extract role deltas from main sequence
                        main_sequence = pgn_seq.get("main_sequence", [])
                        if main_sequence:
                            # Get role deltas from the first move (the player's move)
                            first_move_delta = main_sequence[0] if main_sequence else None
                            if first_move_delta:
                                role_deltas = [first_move_delta]  # Just the first move's deltas
                
                mechanism_from_roles = self._select_mechanism_from_roles(
                    investigation_result, 
                    light_raw.roles,
                    starting_roles=starting_roles,
                    role_deltas=role_deltas
                )
                if mechanism_from_roles:
                    return mechanism_from_roles
        
        # PRIORITY 3: Tags (only if they represent verified board state)
        # Check selected tags (top 2 most important)
        for tag_data in selected_tags:
            tag = tag_data.get("tag", "")
            direction = tag_data.get("direction", "")
            tag_lower = tag.lower()
            
            if "overworked" in tag_lower:
                # STRICT SEMANTICS:
                # - If overworked is LOST, it might be "problem fixed" OR "exploited".
                #   Only call it exploited if we also see tag.threat.capture.undefended appear
                #   for a formerly defended target on the same ply.
                # - If overworked is GAINED, it's an overload being created (negative).
                overworked_sq = None
                if "." in tag:
                    parts = tag.split(".")
                    if len(parts) > 1:
                        overworked_sq = parts[-1]

                exploit = self._find_overworked_exploitation(investigation_result)
                if direction == "lost":
                    if exploit and isinstance(exploit, dict):
                        dsq = exploit.get("defender_square") or overworked_sq
                        became = exploit.get("targets_became_undefended") or []
                        if isinstance(became, list) and became:
                            mechanism = f"deflects the overworked defender on {dsq}, leaving {became[0]} undefended"
                        else:
                            mechanism = f"exploits the overworked defender on {dsq}" if dsq else "exploits an overworked defender"
                        evidence = {"type": "pgn", "source": "overworked_exploit", "verified": True, "details": exploit}
                        return (mechanism, evidence)
                    # Not exploited → describe as resolving the issue (or fall through to other mechanisms).
                    if overworked_sq:
                        return ("relieves the overwork on " + overworked_sq, {"type": "pgn", "source": "overworked_resolved", "verified": True})
                    # No square → don't lock mechanism to overwork; keep searching.
                    continue

                if direction == "gained":
                    if overworked_sq:
                        return ("overloads your defender on " + overworked_sq, {"type": "pgn", "source": "overworked_created", "verified": True})
                    return ("overloads one of your defenders", {"type": "pgn", "source": "overworked_created", "verified": True})

                # Unknown direction → do not force "exploits".
                continue
            if "pin" in tag_lower:
                if direction == "gained":
                    mechanism = "creates a pin"
                else:
                    mechanism = "breaks a pin"
                evidence = {
                    "type": "board_check",
                    "source": "pin",
                    "verified": True
                }
                return (mechanism, evidence)
            if "fork" in tag_lower:
                # Only use fork mechanism if tag was GAINED (not pre-existing)
                if direction != "gained":
                    continue  # Skip if fork tag was lost or unchanged
                
                # Check roles first for fork quality assessment
                if hasattr(investigation_result, 'light_raw_analysis') and investigation_result.light_raw_analysis:
                    light_raw = investigation_result.light_raw_analysis
                    if hasattr(light_raw, 'roles') and light_raw.roles:
                        # Extract starting roles to check if fork was pre-existing
                        starting_roles = None
                        if hasattr(investigation_result, 'pgn_exploration') and investigation_result.pgn_exploration:
                            pgn_seq = self._extract_pgn_sequence_with_deltas(investigation_result.pgn_exploration)
                            if pgn_seq:
                                starting_roles_list = pgn_seq.get("starting_roles", [])
                                if starting_roles_list:
                                    starting_roles = {}
                                    for role_str in starting_roles_list:
                                        if ":" in role_str:
                                            piece_id, role = role_str.split(":", 1)
                                            if piece_id not in starting_roles:
                                                starting_roles[piece_id] = []
                                            starting_roles[piece_id].append(role)
                        
                        # Check for good fork or refuted fork roles
                        for piece_id, roles_list in light_raw.roles.items():
                            if "role.tactical.good_fork" in roles_list:
                                # Check if fork was pre-existing
                                is_pre_existing = starting_roles and piece_id in starting_roles and "role.tactical.good_fork" in starting_roles.get(piece_id, [])
                                evidence = {
                                    "type": "roles",
                                    "source": "fork",
                                    "verified": True,
                                    "quality": "good"
                                }
                                # Only say "creates" if fork was newly gained (tag direction == "gained" already checked above)
                                if not is_pre_existing:
                                    return ("creates a fork opportunity", evidence)
                                else:
                                    return ("involves a fork opportunity", evidence)
                            elif "role.tactical.refuted_fork" in roles_list:
                                # Refuted fork - don't use as mechanism
                                continue
                
                # Fallback to TwoMove verification
                fork_item = self._select_verified_two_move_item(
                    investigation_result,
                    prefer_sections=["open_tactics", "blocked_tactics", "open_captures", "checkmates"],
                    prefer_tactic_types=["fork"],
                )
                if fork_item:
                    evidence = {
                        "type": "two_move",
                        "source": "fork",
                        "verified": True
                    }
                    return ("creates a fork opportunity", evidence)
                # Refuted/unsupported by TwoMove → do not lock mechanism to "fork".
                continue
            if "king" in tag_lower and "file" in tag_lower and "semi" in tag_lower:
                if direction == "lost":
                    mechanism = "weakens your king's position on the semi-open file"
                else:
                    mechanism = "strengthens your king's position on the semi-open file"
                evidence = {
                    "type": "board_check",
                    "source": "semi_open_file",
                    "verified": True
                }
                return (mechanism, evidence)
            # Skip diagonal/center tags unless verified (conservative approach)
        
        # Move intent removed - no longer available, skip this fallback
        
        # Check two-move tactics
        if hasattr(investigation_result, 'two_move_tactics') and investigation_result.two_move_tactics:
            best_item = self._select_verified_two_move_item(investigation_result)
            if best_item:
                tactic_type = best_item.get("type")
                section = best_item.get("_section")
                if isinstance(tactic_type, str) and tactic_type.strip():
                    evidence = {
                        "type": "two_move",
                        "source": tactic_type,
                        "verified": True
                    }
                    return (f"creates a {tactic_type} opportunity", evidence)
                # If no explicit type, fall back to section-based generic wording.
                if section in ("open_captures", "closed_captures"):
                    return ("creates a winning capture opportunity", {"type": "two_move", "source": "capture", "verified": True})
                if section in ("checkmates", "mate_patterns"):
                    return ("creates a checkmate threat", {"type": "two_move", "source": "checkmate", "verified": True})
                if section == "promotions":
                    return ("creates a promotion threat", {"type": "two_move", "source": "promotion", "verified": True})
        
        # Check threats
        if hasattr(investigation_result, 'threats') and investigation_result.threats:
            return ("responds to a threat", None)
        
        # Try to generate a meaningful fallback based on game phase and position type
        fallback_msg = self._generate_contextual_fallback(investigation_result)
        return (fallback_msg, None)
    
    def _select_mechanism_from_roles(
        self,
        investigation_result: InvestigationResult,
        roles: Dict[str, List[str]],
        starting_roles: Optional[Dict[str, List[str]]] = None,
        role_deltas: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Tuple[str, Optional[Dict[str, Any]]]]:
        """
        Select mechanism from roles, preferring action-oriented roles.
        
        Priority:
        1. Good forks (non-refuted)
        2. Overworked pieces
        3. Attacking roles with specific targets
        4. Defensive roles
        
        Args:
            investigation_result: Investigation result
            roles: Roles in the position AFTER the move
            starting_roles: Roles in the position BEFORE the move (to check if roles were pre-existing)
            role_deltas: List of role deltas from PGN (to check if roles were gained by the move)
        
        Returns:
            Tuple of (mechanism_string, evidence_dict) or None
        """
        # Helper function to check if a role was newly gained (not pre-existing)
        def is_role_newly_gained(piece_id: str, role: str) -> bool:
            """Check if a role was newly gained by comparing with starting roles or role deltas."""
            # First, try to check role deltas (most accurate - shows what was gained by the move)
            if role_deltas:
                for delta in role_deltas:
                    roles_gained = delta.get("roles_gained", [])
                    # Check if this specific role was gained (format: "piece_id:role")
                    role_key = f"{piece_id}:{role}"
                    if role_key in roles_gained:
                        return True
            
            # Fallback: check starting roles (if role exists in starting position, it's not newly gained)
            if starting_roles:
                starting_roles_list = starting_roles.get(piece_id, [])
                if role in starting_roles_list:
                    return False  # Role was pre-existing
            
            # If we can't determine, assume it might be new (conservative approach)
            # But we'll use "involves" instead of "creates" to be safe
            return None  # Unknown - use neutral language
        # Check for good forks first
        for piece_id, roles_list in roles.items():
            if "role.tactical.good_fork" in roles_list:
                # Check if fork was newly created
                is_new = is_role_newly_gained(piece_id, "role.tactical.good_fork")
                
                # Extract piece info from piece_id (e.g., "white_knight_f3")
                parts = piece_id.split("_")
                if len(parts) >= 3:
                    piece_type = parts[1]
                    square = parts[2]
                    evidence = {
                        "type": "roles",
                        "source": "fork",
                        "verified": True,
                        "quality": "good",
                        "piece": piece_id
                    }
                    # Only say "creates" if fork was newly gained
                    if is_new is True:
                        return (f"creates a fork opportunity with {piece_type} on {square}", evidence)
                    elif is_new is False:
                        return (f"involves a fork opportunity with {piece_type} on {square}", evidence)
                    else:
                        # Unknown - use neutral language
                        return (f"involves a fork opportunity with {piece_type} on {square}", evidence)
                else:
                    evidence = {
                        "type": "roles",
                        "source": "fork",
                        "verified": True,
                        "quality": "good"
                    }
                    # Only say "creates" if fork was newly gained
                    if is_new is True:
                        return ("creates a fork opportunity", evidence)
                    else:
                        return ("involves a fork opportunity", evidence)
        
        # Check for overworked pieces
        for piece_id, roles_list in roles.items():
            if "role.defending.overworked" in roles_list:
                # Check if overworked status was newly created
                is_new = is_role_newly_gained(piece_id, "role.defending.overworked")
                
                parts = piece_id.split("_")
                if len(parts) >= 3:
                    piece_type = parts[1]
                    square = parts[2]
                    # STRICT SEMANTICS:
                    # Roles can tell us a piece is overworked, but "exploited" must be proven by
                    # the companion consequence `tag.threat.capture.undefended` appearing after the overwork resolves.
                    exploit = self._find_overworked_exploitation(investigation_result)
                    if isinstance(exploit, dict) and (exploit.get("defender_square") == square):
                        targets = exploit.get("targets_became_undefended") or []
                        if isinstance(targets, list) and targets:
                            return (
                                f"deflects the overworked {piece_type} on {square}, leaving {targets[0]} undefended",
                                {"type": "pgn", "source": "overworked_exploit", "verified": True, "piece": piece_id, "details": exploit},
                            )
                        return (
                            f"exploits the overworked {piece_type} on {square}",
                            {"type": "pgn", "source": "overworked_exploit", "verified": True, "piece": piece_id, "details": exploit},
                        )

                    # Otherwise: it's overworked (may be pre-existing or newly created), but not proven exploited.
                    if is_new is True:
                        return (
                            f"overloads your {piece_type} on {square}",
                            {"type": "roles", "source": "overworked_created", "verified": True, "piece": piece_id},
                        )
                    if is_new is False:
                        return (
                            f"leaves your {piece_type} on {square} overworked",
                            {"type": "roles", "source": "overworked_preexisting", "verified": True, "piece": piece_id},
                        )
                    return (
                        f"involves an overworked {piece_type} on {square}",
                        {"type": "roles", "source": "overworked", "verified": True, "piece": piece_id},
                    )
        
        # Check for attacking undefended pieces
        for piece_id, roles_list in roles.items():
            if "role.attacking.undefended_piece" in roles_list:
                parts = piece_id.split("_")
                if len(parts) >= 3:
                    piece_type = parts[1]
                    square = parts[2]
                    evidence = {
                        "type": "roles",
                        "source": "attack",
                        "verified": True,
                        "piece": piece_id
                    }
                    return (f"allows {piece_type} on {square} to attack an undefended piece", evidence)
        
        # Check for hanging pieces
        for piece_id, roles_list in roles.items():
            if "role.status.hanging" in roles_list:
                parts = piece_id.split("_")
                if len(parts) >= 3:
                    piece_type = parts[1]
                    square = parts[2]
                    evidence = {
                        "type": "roles",
                        "source": "hanging",
                        "verified": True,
                        "piece": piece_id
                    }
                    return (f"leaves {piece_type} on {square} hanging", evidence)
        
        return None
    
    def _generate_contextual_fallback(self, investigation_result: InvestigationResult) -> str:
        """
        Generate a contextual fallback mechanism when no specific mechanism can be determined.
        Uses game phase, evaluation, and other context to provide a meaningful message.
        """
        parts = []
        
        # Check evaluation context
        if investigation_result.eval_before is not None:
            eval_cp = investigation_result.eval_before
            if abs(eval_cp) > 200:  # Clear advantage
                side = "White" if eval_cp > 0 else "Black"
                parts.append(f"{side} has an advantage")
            elif abs(eval_cp) < 50:
                parts.append("the position is roughly equal")
        
        # Check game phase
        if investigation_result.game_phase:
            phase = investigation_result.game_phase.lower()
            if "opening" in phase:
                parts.append("in the opening phase")
            elif "middlegame" in phase or "middle" in phase:
                parts.append("in the middlegame")
            elif "endgame" in phase or "end" in phase:
                parts.append("in the endgame")
        
        # Check if there's a best move recommendation
        if investigation_result.best_move:
            parts.append(f"the engine suggests {investigation_result.best_move}")
        
        # Build the message
        if parts:
            return "This is a position where " + ", ".join(parts) + "."
        
        # Ultimate fallback - still informative
        return "This position requires careful analysis of piece activity and pawn structure"
    
    def _bind_evidence_to_claim(
        self,
        summary: str,
        connector: Optional[str],
        claim_type: str,
        investigation_result: InvestigationResult
    ) -> Claim:
        """
        Deterministically bind evidence to a claim summary (generic, position-agnostic).
        
        Priority order:
        1. Evidence index (structured evidence lines from Investigator)
        2. PV sequences from pv_after_move
        3. PV sequences from exploration_tree
        4. Two-move engine validated sequences
        
        If no evidence found, returns Claim with connector=None (mandatory downgrade).
        
        Args:
            summary: Non-causal claim summary
            connector: Desired causal connector ("because", "allows", etc.) or None
            claim_type: Generic classification label
            investigation_result: Investigation result with evidence_index and PV/PGN data
        
        Returns:
            Claim object with evidence bound if found, otherwise non-causal Claim
        """
        import re
        
        evidence_moves = None
        evidence_source = None
        
        # Priority 1: Check evidence_index (structured evidence from Investigator)
        if investigation_result.evidence_index:
            # Use first available evidence line (generic selection)
            evidence_line = investigation_result.evidence_index[0]
            # evidence_line can be either an EvidenceLine dataclass OR a dict (comparison-mode serialization).
            try:
                if isinstance(evidence_line, dict):
                    moves = evidence_line.get("moves") or []
                    source = evidence_line.get("source") or "evidence_index"
                else:
                    moves = getattr(evidence_line, "moves", None) or []
                    source = getattr(evidence_line, "source", None) or "evidence_index"
            except Exception:
                moves = []
                source = "evidence_index"

            if isinstance(moves, list) and len(moves) >= 2:
                evidence_moves = [m for m in moves if isinstance(m, str)][:4]  # Max 4 plies
                evidence_source = source
        
        # Priority 2: Check pgn_exploration for move sequences (fallback)
        if not evidence_moves and investigation_result.pgn_exploration:
            pgn_text = investigation_result.pgn_exploration
            
            # Extract move sequences from PGN (generic SAN pattern matching)
            san_pattern = r'\b([KQRBN]?[a-h]?[1-8]?x?[a-h][1-8](?:=[QRBN])?[+#]?)\b'
            all_moves = re.findall(san_pattern, pgn_text)
            
            # Extract first valid sequence (2-4 plies)
            if len(all_moves) >= 2:
                sequence = all_moves[:4]  # Max 4 plies
                evidence_moves = sequence
                evidence_source = "pgn"
        
        # Priority 2: Check PV sequences
        if not evidence_moves and investigation_result.pv_after_move:
            pv = investigation_result.pv_after_move
            if len(pv) >= 2:
                evidence_moves = pv[:4]  # Max 4 plies
                evidence_source = "pv"
        
        # Priority 3: Check exploration_tree for PV sequences
        if not evidence_moves and investigation_result.exploration_tree:
            def find_pv_in_tree(tree_node: Dict[str, Any]) -> Optional[List[str]]:
                if isinstance(tree_node, dict):
                    if "pv_full" in tree_node and tree_node["pv_full"]:
                        return tree_node["pv_full"][:4]
                    # Recurse into children
                    for key, value in tree_node.items():
                        if isinstance(value, (dict, list)):
                            result = find_pv_in_tree(value) if isinstance(value, dict) else None
                            if result:
                                return result
                return None
            
            pv_from_tree = find_pv_in_tree(investigation_result.exploration_tree)
            if pv_from_tree and len(pv_from_tree) >= 2:
                evidence_moves = pv_from_tree[:4]
                evidence_source = "pv"
        
        # Priority 4: Check two_move_tactics
        # NOTE: Not all InvestigationResult objects have two_move_tactics (avoid AttributeError).
        tactics = getattr(investigation_result, "two_move_tactics", None)
        if not evidence_moves and tactics:
            
            # Check open tactics
            if tactics.open_tactics:
                for tactic in tactics.open_tactics:
                    if not self._is_two_move_item_verified(tactic):
                        continue
                    if "sequence" in tactic and tactic["sequence"]:
                        evidence_moves = tactic["sequence"][:4]
                        evidence_source = "pgn"  # Changed from "two_move" to "pgn"
                        break
            
            # Check open captures
            if not evidence_moves and tactics.open_captures:
                for capture in tactics.open_captures:
                    if not self._is_two_move_item_verified(capture):
                        continue
                    if "move" in capture:
                        move_seq = [capture["move"]]
                        if "forced_recapture" in capture and capture["forced_recapture"]:
                            move_seq.append(capture["forced_recapture"])
                        if len(move_seq) >= 2:
                            evidence_moves = move_seq[:4]
                            evidence_source = "pgn"  # Changed from "two_move" to "pgn"
                            break
        
        # Create Claim: if evidence found and connector provided, use it; otherwise mandatory downgrade
        if evidence_moves and connector:
            claim = Claim(
                summary=summary,
                claim_type=claim_type,
                connector=connector,
                evidence_moves=evidence_moves,
                evidence_source=evidence_source
            )
        else:
            # No evidence or no connector requested: return non-causal claim (mandatory downgrade)
            claim = Claim(
                summary=summary,
                claim_type=claim_type,
                connector=None,
                evidence_moves=None,
                evidence_source=None
            )
        # Trace: bind_evidence claims are not LLM-created; mark origin for debugging
        claim._origin = "bind_evidence"
        try:
            pm = getattr(investigation_result, "player_move", None)
            if pm:
                claim._origin_detail = f"bind_evidence:{claim_type}:{pm}"
        except Exception:
            pass
        return claim
    
    def _validate_claim_against_evidence(
        self,
        claim: Claim,
        investigation_result: InvestigationResult
    ) -> Optional[Claim]:
        """
        Validate claim summary against evidence sequence data and reword if necessary.
        
        Checks:
        1. Material claims vs actual material change
        2. Positional claims vs actual positional change
        3. Development claims vs actual roles (pieces developing)
        
        Args:
            claim: Claim object with evidence attached
            investigation_result: InvestigationResult with evidence sequence data
        
        Returns:
            Reworded Claim if validation found issues, None if claim is valid
        """
        if not claim.evidence_payload:
            return None
        
        summary = claim.summary
        original_summary = summary
        needs_rewrite = False
        
        # Get evidence eval data
        evidence_eval_start = getattr(investigation_result, "evidence_eval_start", None)
        evidence_eval_end = getattr(investigation_result, "evidence_eval_end", None)
        evidence_material_start = getattr(investigation_result, "evidence_material_start", None)
        evidence_material_end = getattr(investigation_result, "evidence_material_end", None)
        evidence_positional_start = getattr(investigation_result, "evidence_positional_start", None)
        evidence_positional_end = getattr(investigation_result, "evidence_positional_end", None)
        evidence_roles_gained_net = getattr(investigation_result, "evidence_roles_gained_net", []) or []
        evidence_roles_lost_net = getattr(investigation_result, "evidence_roles_lost_net", []) or []
        
        # Check material claims
        if evidence_material_start is not None and evidence_material_end is not None:
            material_delta = abs(evidence_material_end - evidence_material_start)
            summary_lower = summary.lower()
            
            # Check for material-related claims (more specific patterns)
            material_patterns = [
                "material advantage", "gain material", "lose material", "loses material",
                "material gain", "material loss", "winning material", "losing material"
            ]
            has_material_claim = any(pattern in summary_lower for pattern in material_patterns)
            
            if has_material_claim and material_delta < 0.5:
                # Claim mentions material but change is insignificant
                needs_rewrite = True
                # Remove material-related phrases more carefully
                for pattern in material_patterns:
                    summary = re.sub(re.escape(pattern), "", summary, flags=re.IGNORECASE)
                # Clean up extra spaces
                summary = re.sub(r'\s+', ' ', summary).strip()
                # Remove "with advantage" if it appears standalone (not part of another phrase)
                if material_delta < 0.5:
                    summary = re.sub(r'\s+with\s+advantage\b', '', summary, flags=re.IGNORECASE)
                    summary = re.sub(r'\bwith\s+advantage\s+', '', summary, flags=re.IGNORECASE)
                    summary = re.sub(r'\s+', ' ', summary).strip()
        
        # Check positional claims
        if evidence_positional_start is not None and evidence_positional_end is not None:
            positional_delta = abs(evidence_positional_end - evidence_positional_start)
            summary_lower = summary.lower()
            
            # More specific positional patterns
            positional_patterns = ["positional advantage", "positional disadvantage", "gains positional", "loses positional"]
            has_positional_claim = any(pattern in summary_lower for pattern in positional_patterns)
            
            if has_positional_claim and positional_delta < 0.5:
                needs_rewrite = True
                for pattern in positional_patterns:
                    summary = re.sub(re.escape(pattern), "", summary, flags=re.IGNORECASE)
                summary = re.sub(r'\s+', ' ', summary).strip()
        
        # Check development claims vs actual roles
        summary_lower = summary.lower()
        development_block_patterns = [
            "blocks development", "prevents development", "hinders development", 
            "development is blocked", "cannot develop", "stops development",
            "blocks piece development", "prevents piece development"
        ]
        has_development_block_claim = any(pattern in summary_lower for pattern in development_block_patterns)
        
        if has_development_block_claim:
            # Check if evidence shows development happening (pieces gaining development-related roles)
            development_role_indicators = [
                "role.control.outpost", "role.developing", "role.control.moderate_mobility", 
                "role.control.high_mobility", "role.control"
            ]
            development_roles = [r for r in evidence_roles_gained_net if any(
                indicator in r.lower() for indicator in development_role_indicators
            )]
            
            if development_roles:
                # Evidence shows development, but claim says it's blocked
                needs_rewrite = True
                # Remove development block language
                for pattern in development_block_patterns:
                    summary = re.sub(re.escape(pattern), "", summary, flags=re.IGNORECASE)
                summary = re.sub(r'\s+', ' ', summary).strip()
        
        # If rewrite needed, create new claim with corrected summary
        if needs_rewrite and summary != original_summary:
            print(f"   ⚠️ [CLAIM_VALIDATION] Rewording claim summary:")
            print(f"      Original: {original_summary}")
            print(f"      Reworded: {summary}")
            
            # Create new claim with corrected summary
            corrected_claim = Claim(
                summary=summary,
                claim_type=claim.claim_type,
                connector=claim.connector,
                evidence_moves=claim.evidence_moves,
                evidence_source=claim.evidence_source,
                evidence_payload=claim.evidence_payload,
                hints=claim.hints
            )
            # Preserve origin tracking
            if hasattr(claim, "_origin"):
                corrected_claim._origin = claim._origin
            
            return corrected_claim
        
        return None
    
    def _create_comparison_claims(
        self,
        multiple_results: List[Dict[str, Any]],
        primary_narrative: str,
        mechanism: str
    ) -> List[Claim]:
        """
        Create claims that compare multiple move options and recommend the better one.
        
        Used for any "A vs B" / "which move is better" style question.
        Claims should state which option is better and provide a concise, evidence-backed reason.
        
        Args:
            multiple_results: List of investigation results with request metadata
            primary_narrative: Primary narrative for context
            mechanism: Mechanism string
            
        Returns:
            List of Claim objects including a comparison claim
        """
        claims = []
        
        if not multiple_results or len(multiple_results) < 2:
            # Not enough results to compare, fall back to first result
            if multiple_results and len(multiple_results) > 0:
                first_result = multiple_results[0].get("result")
                if isinstance(first_result, InvestigationResult):
                    return self._create_claims_from_facts(
                        first_result,
                        primary_narrative,
                        mechanism
                    )
            return claims
        
        # Extract move data for comparison
        move_data = []
        for item in multiple_results:
            inv_req = item.get("request")
            result = item.get("result")
            if isinstance(result, InvestigationResult):
                # Priority: inv_req.focus > player_move > best_move_d16 (SAN) > best_move (UCI->SAN)
                move_san = None
                focus_move = self._get_request_attr(inv_req, "focus")
                if focus_move:
                    move_san = focus_move
                elif result.player_move:
                    move_san = result.player_move
                elif result.best_move_d16:
                    # best_move_d16 is already SAN
                    move_san = result.best_move_d16
                elif result.best_move:
                    # best_move is UCI, convert to SAN
                    try:
                        import chess
                        board = chess.Board(result.light_raw_analysis.fen if result.light_raw_analysis else "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")
                        move_uci = chess.Move.from_uci(result.best_move)
                        if move_uci in board.legal_moves:
                            move_san = board.san(move_uci)
                    except Exception:
                        pass
                
                # If still None, use a placeholder
                if not move_san:
                    continue
                
                eval_drop = result.eval_drop or 0
                eval_after = result.eval_after
                move_data.append({
                    "move": move_san,
                    "eval_drop": eval_drop,
                    "eval_after": eval_after,
                    "result": result
                })
        
        if len(move_data) < 2:
            return claims
        
        # Sort by eval drop (lower is better - less position lost)
        move_data.sort(key=lambda x: x["eval_drop"])
        best_move = move_data[0]
        worse_move = move_data[1]

        # Sanity gate: if both moves are the same (e.g. "Ng5 vs Ng5"), don't emit a comparison.
        # This can happen if upstream plan duplicated a move or SAN normalization collapsed two labels.
        if best_move.get("move") == worse_move.get("move"):
            # Still allow recommendation + consequence (if any), but skip comparison claim entirely.
            claims = []

            # Recommendation claim (best move)
            recommendation = f"You should play {best_move['move']}"
            recommendation_claim = Claim(
                summary=recommendation,
                claim_type="recommendation",
                connector=None,
                evidence_moves=[best_move["move"]],
                evidence_source="best_move_recommendation"
            )
            recommendation_claim.hints = RenderHints(role="recommendation", priority=1, inline_pgn=False)
            self._attach_rich_evidence(
                recommendation_claim,
                best_move["result"],
                want_pgn_line=True,
                want_tags=True,
                want_two_move=True,
                move_san=best_move["move"]
            )
            claims.append(recommendation_claim)

            # Optional consequence claim if there is a meaningful eval drop or threats
            eval_drop_val = worse_move.get("eval_drop", 0) or 0
            has_mate_threat = False
            try:
                if worse_move["result"] and getattr(worse_move["result"], "two_move_tactics", None):
                    has_mate_threat = bool(worse_move["result"].two_move_tactics.has_mate_threat)
            except Exception:
                pass

            if has_mate_threat or eval_drop_val >= 0.3:
                worse_explanation = f"{worse_move['move']} allows dangerous threats" if has_mate_threat else f"{worse_move['move']} is slightly inferior"
                consequence_claim = Claim(
                    summary=worse_explanation,
                    claim_type="consequence",
                    connector=None,
                    evidence_moves=[worse_move["move"]],
                    evidence_source="consequence_analysis"
                )
                consequence_claim.hints = RenderHints(role="consequence", priority=2, inline_pgn=True)
                self._attach_rich_evidence(
                    consequence_claim,
                    worse_move["result"],
                    want_pgn_line=True,
                    want_tags=True,
                    want_two_move=True,
                    move_san=worse_move["move"]
                )
                claims.append(consequence_claim)

            return claims
        
        # Calculate the difference
        eval_difference = abs(worse_move["eval_drop"] - best_move["eval_drop"])
        
        # Create primary comparison claim
        if eval_difference > 0.5:  # Significant difference (0.5 pawns)
            comparison_text = f"{best_move['move']} is clearly better than {worse_move['move']}"
            if eval_difference >= 1.0:
                comparison_text += f" (saves about {eval_difference:.1f} pawns)"
        else:
            comparison_text = f"{best_move['move']} is slightly better than {worse_move['move']}"
        
        # Add consequence reason if available - ONLY from worse move (never from best move)
        consequences = worse_move.get("consequences")
        if consequences:
            comparison_text += f" because {worse_move['move']} {consequences}"
        # DO NOT use best_move consequences - they might be negative and confusing
        
        comparison_claim = Claim(
            summary=comparison_text,
            claim_type="move_comparison",
            connector=None,  # Comparison claims are descriptive
            evidence_moves=[best_move["move"], worse_move["move"]],
            evidence_source="move_comparison_analysis"
        )
        comparison_claim.hints = RenderHints(role="comparison", priority=1, inline_pgn=True)
        # For comparison, use worse_move's result to show the problem
        self._attach_rich_evidence(
            comparison_claim,
            worse_move["result"],  # Changed from best_move["result"] - use worse move's evidence
            want_pgn_line=True,
            want_tags=True,
            want_two_move=True,
            move_san=worse_move["move"]  # Prefer line showing the worse move's consequences
        )
        claims.append(comparison_claim)
        
        # Add recommendation claim
        recommendation = f"You should play {best_move['move']}"
        # Consequences removed - infer from tags/roles if needed
        
        recommendation_claim = Claim(
            summary=recommendation,
            claim_type="recommendation",
            connector=None,
            evidence_moves=[best_move["move"]],
            evidence_source="best_move_recommendation"
        )
        recommendation_claim.hints = RenderHints(role="recommendation", priority=1, inline_pgn=False)
        self._attach_rich_evidence(
            recommendation_claim,
            best_move["result"],
            want_pgn_line=True,
            want_tags=True,
            want_two_move=True,
            move_san=best_move["move"]  # Prefer line showing the recommended move
        )
        claims.append(recommendation_claim)
        
        # Add explanation for why the worse move is worse
        if worse_move["consequences"]:
            worse_explanation = f"{worse_move['move']} {worse_move['consequences']}, which hurts your position"
        else:
            eval_drop_val = worse_move["eval_drop"]
            # Check for mate threats in two_move_tactics
            has_mate_threat = False
            if hasattr(worse_move["result"], "two_move_tactics") and worse_move["result"].two_move_tactics:
                has_mate_threat = worse_move["result"].two_move_tactics.has_mate_threat or False
            
            if has_mate_threat:
                worse_explanation = f"{worse_move['move']} allows dangerous threats"
            elif eval_drop_val >= 1.0:
                worse_explanation = f"{worse_move['move']} loses significant material or position"
            elif eval_drop_val >= 0.5:
                worse_explanation = f"{worse_move['move']} gives up more than necessary"
            else:
                worse_explanation = f"{worse_move['move']} is playable but slightly inferior"
        
        consequence_claim = Claim(
            summary=worse_explanation,
            claim_type="consequence",
            connector="leads_to" if worse_move["consequences"] else None,
            evidence_moves=[worse_move["move"]],
            evidence_source="consequence_analysis"
        )
        consequence_claim.hints = RenderHints(role="consequence", priority=2, inline_pgn=True)
        # CRITICAL: Use worse_move's result and prefer PGN line containing the move to show the consequence
        self._attach_rich_evidence(
            consequence_claim,
            worse_move["result"],
            want_pgn_line=True,
            want_tags=True,
            want_two_move=True,
            move_san=worse_move["move"]  # Prefer line showing the move that creates the problem
        )
        claims.append(consequence_claim)
        
        return claims
    
    def _synthesize_hammer_claim(
        self,
        investigation_result: Optional[InvestigationResult],
        mechanism: str,
        selected_tag_deltas: List[Dict[str, Any]],
        is_comparison: bool = False
    ) -> Optional[Claim]:
        """
        Attempt to synthesize a hammer claim (causal with evidence) from available data.
        
        A hammer claim must have:
        - connector is not None
        - evidence_moves is not None (2-4 plies)
        - mechanism is not None (implicitly via summary)
        
        Args:
            investigation_result: Investigation result for evidence binding
            mechanism: Selected mechanism string
            selected_tag_deltas: Top tag deltas
            is_comparison: Whether this is comparison mode
            
        Returns:
            Claim with connector and evidence_moves if successful, None otherwise
        """
        if not investigation_result:
            return None
        
        # Determine connector and summary from mechanism/tags
        connector = None
        summary = None
        
        # Priority 1: Infer from mechanism text
        if not connector:
            mechanism_lower = mechanism.lower()
            if "allows" in mechanism_lower:
                connector = "allows"
                summary = f"This move {mechanism}"
            elif "leads" in mechanism_lower or "causes" in mechanism_lower:
                connector = "leads_to"
                summary = f"This move {mechanism}"
            elif "creates" in mechanism_lower:
                connector = "creates"
                summary = f"This move {mechanism}"
        
        # Priority 3: Generic fallback
        if not connector:
            connector = "allows"
            summary = f"This move {mechanism}"
        
        # Attempt to bind evidence
        if summary and connector:
            claim = self._bind_evidence_to_claim(
                summary=summary,
                connector=connector,
                claim_type="hammer_synthesized",
                investigation_result=investigation_result
            )
            
            # Verify it's a proper hammer claim
            if claim.connector and claim.evidence_moves and len(claim.evidence_moves) >= 2:
                claim.hints = RenderHints(role="mechanism", priority=1, inline_pgn=True)
                # Attach rich evidence if available
                try:
                    self._attach_rich_evidence(
                        claim,
                        investigation_result,
                        want_pgn_line=True,
                        want_tags=True,
                        want_two_move=False
                    )
                except Exception:
                    pass  # Non-critical
                return claim
        
        return None
    
    def _create_claims_from_facts(
        self,
        investigation_result: InvestigationResult,
        primary_narrative: str,
        mechanism: str
    ) -> List[Claim]:
        """
        Deterministically create Claim objects from structured facts (NO LLM prose parsing).
        
        Rules:
        - Selects claim_type based on structured fields (primary_narrative, tactics, threats)
        - If a Claim is causal (connector not None), it MUST bind evidence_moves from evidence_index
        - If no evidence can be bound, the Claim MUST be downgraded: connector=None
        - Do NOT rely on LLM prose to decide claim_type or connector presence
        
        Args:
            investigation_result: Investigation result with structured facts and evidence_index
            primary_narrative: Deterministically selected primary narrative
            mechanism: Deterministically selected mechanism
        
        Returns:
            List of Claim objects (proof-carrying)
        """
        claims = []
        
        # Determine claim_type from structured facts (generic, position-agnostic)
        claim_type = "general"
        if primary_narrative:
            # Map primary_narrative to generic claim_type (position-agnostic mapping)
            narrative_lower = primary_narrative.lower()
            if "tactical" in narrative_lower or "blunder" in narrative_lower:
                claim_type = "tactical_issue"
            elif "positional" in narrative_lower or "concession" in narrative_lower:
                claim_type = "positional_concession"
            elif "development" in narrative_lower:
                claim_type = "development_issue"
            elif "missed" in narrative_lower:
                claim_type = "missed_opportunity"
        
        # Create base summary from mechanism (non-causal by default)
        summary = mechanism
        
        # Enhance summary with role information if available
        if hasattr(investigation_result, 'light_raw_analysis') and investigation_result.light_raw_analysis:
            light_raw = investigation_result.light_raw_analysis
            if hasattr(light_raw, 'roles') and light_raw.roles:
                # Check for overworked pieces in summary
                for piece_id, roles_list in light_raw.roles.items():
                    if "role.defending.overworked" in roles_list:
                        parts = piece_id.split("_")
                        if len(parts) >= 3:
                            piece_type = parts[1]
                            square = parts[2]
                            if "overworked" not in summary.lower():
                                summary += f" (the {piece_type} on {square} is overworked, defending multiple targets)"
                        break
        
        # Determine connector from mechanism text (consequences removed - infer from tags/roles)
        connector = None
        mechanism_lower = mechanism.lower() if mechanism else ""
        if "allows" in mechanism_lower:
            connector = "allows"
        elif "creates" in mechanism_lower:
            connector = "creates"
        elif "leads" in mechanism_lower or "causes" in mechanism_lower:
            connector = "leads_to"
        
        # Infer consequences from tags/roles if needed
        # Check tags for pin/capture patterns
        if not connector and hasattr(investigation_result, 'evidence_tags_gained_net'):
            tags_gained = investigation_result.evidence_tags_gained_net or []
            for tag in tags_gained:
                if "pin" in tag.lower():
                    connector = "creates"
                    summary = "This move creates a pin"
                    break
                elif "hanging" in tag.lower() or "capture" in tag.lower():
                    connector = "allows"
                    summary = "This move allows opponent captures"
                    break
        
        # Attempt to bind evidence from evidence_index
        claim = self._bind_evidence_to_claim(
            summary=summary,
            connector=connector,
            claim_type=claim_type,
            investigation_result=investigation_result
        )
        # Attach rich evidence payload for the explainer (referential only)
        role: ClauseRole = "consequence" if connector else "mechanism"
        priority = 1
        inline_pgn = True if connector else False
        show_two_move = bool(getattr(investigation_result, "two_move_tactics", None)) and claim_type in ("tactical_issue", "missed_opportunity")
        claim.hints = RenderHints(
            role=role,
            priority=priority,
            inline_pgn=inline_pgn,
            show_theme_tags=False,
            show_two_move=show_two_move,
            show_board=False
        )
        self._attach_rich_evidence(
            claim,
            investigation_result,
            want_pgn_line=True,
            want_tags=True,
            want_two_move=show_two_move
        )
        
        if claim.summary:
            claims.append(claim)
        
        return claims
    
    def _rank_and_suppress_tag_deltas(self, pgn_tag_deltas: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Rank tag deltas by importance and suppress all but top 2.
        
        Returns:
            Dict with:
            - selected_tags: List of top 2 most important tag changes
            - suppressed_tags: List of all other tags to suppress
        """
        if not pgn_tag_deltas or not pgn_tag_deltas.get("main_sequence"):
            return {
                "selected_tags": [],
                "suppressed_tags": []
            }
        
        # Collect all tags from all moves
        all_tags = []
        for move_data in pgn_tag_deltas["main_sequence"]:
            # Tags gained
            for tag in move_data.get("tags_gained", []):
                all_tags.append(("gained", tag, move_data.get("move", "")))
            # Tags lost
            for tag in move_data.get("tags_lost", []):
                all_tags.append(("lost", tag, move_data.get("move", "")))
        
        # Rank tags by importance
        def get_tag_importance(tag: str) -> int:
            """Return importance score: 3=HIGH, 2=MEDIUM, 1=LOW, 0=UNKNOWN"""
            tag_lower = tag.lower()
            for key, importance in self.tag_importance.items():
                if key in tag_lower:
                    if importance == "HIGH":
                        return 3
                    elif importance == "MEDIUM":
                        return 2
                    else:
                        return 1
            return 0
        
        # Sort by importance (descending)
        all_tags.sort(key=lambda x: get_tag_importance(x[1]), reverse=True)
        
        # Select top 2 unique tags (by tag name, not direction)
        selected_tags = []
        seen_tag_names = set()
        suppressed_tags = []
        
        for direction, tag, move in all_tags:
            tag_name = tag.split(".")[-1] if "." in tag else tag
            if tag_name not in seen_tag_names and len(selected_tags) < 2:
                selected_tags.append({
                    "direction": direction,
                    "tag": tag,
                    "move": move,
                    "importance": get_tag_importance(tag)
                })
                seen_tag_names.add(tag_name)
            else:
                suppressed_tags.append(f"{direction}:{tag}@{move}")
        
        # Debug logging
        import sys
        print(f"   🔍 [SUMMARISER] Tag ranking: found {len(all_tags)} total tags from {len(pgn_tag_deltas.get('main_sequence', [])) if pgn_tag_deltas else 0} moves")
        print(f"   🔍 [SUMMARISER] Selected: {len(selected_tags)}, Suppressed: {len(suppressed_tags)}")
        if selected_tags:
            print(f"   🔍 [SUMMARISER] Selected tags: {[s['tag'] for s in selected_tags]}")
        if suppressed_tags:
            print(f"   🔍 [SUMMARISER] Suppressed tags (first 5): {suppressed_tags[:5]}")
        sys.stdout.flush()
        
        return {
            "selected_tags": selected_tags,
            "suppressed_tags": suppressed_tags
        }
    
    async def summarise(
        self,
        investigation_result: Any,  # Can be InvestigationResult or dict with multiple results
        execution_plan: Optional[Any] = None,  # ExecutionPlan from Planner
        user_history: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None,  # NEW: User message for goal extraction
        context: Optional[Dict[str, Any]] = None,  # Optional full request context (baseline_intuition/significance)
        session_id: Optional[str] = None,
    ) -> NarrativeDecision:
        """
        Decide what narrative to tell based on investigation facts.
        NO chess analysis - only prioritization and framing.
        
        Args:
            investigation_result: Structured facts from Investigator, or dict with multiple_results for comparisons
            user_history: Optional user history for context
            
        Returns:
            NarrativeDecision with what to say and how to frame it
        """
        # These are threaded through to Explainer; ensure they are always defined even if
        # a specific branch (e.g., comparison mode) doesn't build them.
        worded_pgn: Optional[Dict[str, Any]] = None
        original_pgn_context: Dict[str, Any] = {}
        # Always define fallbacks used later (even in comparison mode).
        user_goal: Optional[str] = self._extract_user_goal(user_message) if user_message else None
        fallback_primary_narrative: str = ""
        fallback_psychological_frame: str = "reasonable idea, wrong moment"
        fallback_mechanism: Optional[str] = None
        # Initialize discussion_agenda at the top (before any branching) to avoid UnboundLocalError
        discussion_agenda: List[Dict[str, Any]] = []
        if execution_plan and hasattr(execution_plan, "discussion_agenda"):
            discussion_agenda = execution_plan.discussion_agenda or []

        # LOG INPUT
        import sys
        print(f"\n{'='*80}")
        print(f"🔍 [SUMMARISER] INPUT:")
        # Determine if user intent suggests comparison or suggestion
        intent_goal = None
        if execution_plan and hasattr(execution_plan, "original_intent") and execution_plan.original_intent:
            try:
                intent_goal = getattr(execution_plan.original_intent, "goal", None) or execution_plan.original_intent.get("goal")
            except Exception:
                intent_goal = None

        def _should_force_suggestion(goal: Optional[str], user_msg: Optional[str]) -> bool:
            goal_text = (goal or "").lower()
            msg = (user_msg or "").lower()
            if "compare" in goal_text:
                return False
            # Heuristics: progress / develop / castle questions should not force comparison
            progress_triggers = ["progress", "proceed", "plan", "castle", "develop", "how do i", "what should i do", "how should i"]
            return any(tok in msg for tok in progress_triggers) or ("suggest" in goal_text)

        raw_is_comparison = isinstance(investigation_result, dict) and investigation_result.get("comparison_mode", False)
        force_suggestion = _should_force_suggestion(intent_goal, user_message)
        # For suggestion-style queries we still keep comparison context (multiple_results), but we deterministically
        # pick a primary recommendation move and reorder the candidate list so it is first.
        is_comparison = raw_is_comparison

        primary_recommendation: Optional[Dict[str, Any]] = None
        if force_suggestion and isinstance(investigation_result, dict) and investigation_result.get("multiple_results"):
            try:
                mr_list = list(investigation_result.get("multiple_results", []) or [])
                scored_items: List[Tuple[float, int]] = []
                for idx, item in enumerate(mr_list):
                    res = item.get("result")
                    if not isinstance(res, InvestigationResult):
                        continue
                    ev_end = getattr(res, "evidence_eval_end", None)
                    ev_after = getattr(res, "eval_after", None)
                    ev_before = getattr(res, "eval_before", None)
                    score_val = None
                    for v in (ev_end, ev_after, ev_before):
                        if isinstance(v, (int, float)):
                            score_val = float(v)
                            break
                    if score_val is None:
                        continue
                    scored_items.append((score_val, idx))

                if scored_items:
                    scored_items.sort(key=lambda x: x[0], reverse=True)
                    best_score, best_idx = scored_items[0]
                    best_item = mr_list[best_idx]
                    best_res = best_item.get("result") if isinstance(best_item, dict) else None
                    if isinstance(best_res, InvestigationResult):
                        primary_recommendation = {
                            "move_san": getattr(best_res, "player_move", None),
                            "evidence_pgn_line": getattr(best_res, "evidence_pgn_line", None),
                            "eval_end": getattr(best_res, "evidence_eval_end", None),
                            "eval_delta": getattr(best_res, "evidence_eval_delta", None),
                            "material_delta": (
                                getattr(best_res, "evidence_material_end", None) - getattr(best_res, "evidence_material_start", None)
                            ) if (getattr(best_res, "evidence_material_start", None) is not None and getattr(best_res, "evidence_material_end", None) is not None) else None,
                            "why": "highest terminal eval among investigated candidate moves",
                            "score": best_score,
                        }
                    # Reorder so best move is first (downstream logic often uses multiple_results[0]).
                    reordered = [mr_list[best_idx]] + [mr_list[i] for i in range(len(mr_list)) if i != best_idx]
                    investigation_result["multiple_results"] = reordered
            except Exception as e:
                print(f"   ⚠️ [SUMMARISER] Failed to select primary recommendation: {e}")
        multiple_results: List[Dict[str, Any]] = investigation_result.get("multiple_results", []) if is_comparison else []
        if is_comparison:
            print(f"   Mode: COMPARISON")
            print(f"   Multiple Results Count: {len(multiple_results)}")
            for i, item in enumerate(multiple_results):
                result = item.get("result")
                if isinstance(result, InvestigationResult):
                    req = item.get("request")
                    focus = self._get_request_attr(req, "focus")
                    print(f"      [{i+1}] Focus: {focus}, Eval: {result.eval_before}")
        else:
            if isinstance(investigation_result, InvestigationResult):
                print(f"   Mode: SINGLE RESULT")
                print(f"   Type: InvestigationResult")
                print(f"   Eval Before: {investigation_result.eval_before}")
                print(f"   Eval After: {investigation_result.eval_after}")
                print(f"   Eval Drop: {investigation_result.eval_drop}")
                print(f"   Game Phase: {investigation_result.game_phase}")
                print(f"   Best Move: {investigation_result.best_move}")
                print(f"   Player Move: {investigation_result.player_move}")
                print(f"   Tactics Found: {len(investigation_result.tactics_found)}")
            else:
                print(f"   Type: {type(investigation_result).__name__}")
        print(f"{'='*80}\n")
        sys.stdout.flush()
        
        # Variables for both modes
        selected_psychological_frame = None
        selected_primary_narrative = None
        selected_mechanism = None
        all_suppressed_tags_combined = []
        primary_result_for_evidence: Optional[InvestigationResult] = investigation_result if isinstance(investigation_result, InvestigationResult) else None
        if not primary_result_for_evidence and multiple_results:
            for item in multiple_results:
                candidate = item.get("result")
                if isinstance(candidate, InvestigationResult):
                    primary_result_for_evidence = candidate
                    break

        # Ensure deterministic fallbacks exist for both single-result and comparison modes.
        # (These are referenced later regardless of LLM-claims presence.)
        if primary_result_for_evidence and isinstance(primary_result_for_evidence, InvestigationResult):
            try:
                fallback_primary_narrative = self._select_primary_narrative(primary_result_for_evidence)
            except Exception:
                fallback_primary_narrative = ""
            try:
                fallback_psychological_frame = self._select_psychological_frame(
                    primary_result_for_evidence,
                    fallback_primary_narrative or "positional_concession_without_compensation",
                    user_goal,
                )
            except Exception:
                fallback_psychological_frame = "reasonable idea, wrong moment"

        # Worded PGN feature removed (cost/latency). Explainer uses curated PGN directly.
        worded_pgn = None
        try:
            if primary_result_for_evidence and isinstance(primary_result_for_evidence, InvestigationResult):
                original_pgn_context = self._build_original_pgn_context(primary_result_for_evidence)
        except Exception:
            pass

        # For suggestion-style queries, ensure our primary_result_for_evidence is the deterministic primary recommendation.
        if force_suggestion and primary_recommendation and multiple_results:
            try:
                first = multiple_results[0].get("result") if isinstance(multiple_results[0], dict) else None
                if isinstance(first, InvestigationResult):
                    primary_result_for_evidence = first
            except Exception:
                pass
        
        if is_comparison:
            # Handle multiple investigation results (comparison mode)
            multiple_results = investigation_result.get("multiple_results", [])
            
            # Extract facts from each result with primary narrative selection
            facts_list = []
            all_suppressed_tags = []
            primary_narratives = []
            psychological_frames = []
            
            for item in multiple_results:
                inv_req = item.get("request")
                result = item.get("result")
                if isinstance(result, InvestigationResult):
                    # Select primary narrative for this result
                    primary_narrative = self._select_primary_narrative(result)
                    primary_narratives.append(primary_narrative)
                    
                    # Extract and rank tag deltas
                    pgn_tag_deltas_raw = None
                    if result.pgn_exploration:
                        pgn_tag_deltas_raw = self._extract_pgn_sequence_with_deltas(result.pgn_exploration)
                    
                    tag_ranking = self._rank_and_suppress_tag_deltas(pgn_tag_deltas_raw)
                    selected_tags = tag_ranking["selected_tags"]
                    suppressed_tags = tag_ranking["suppressed_tags"]
                    all_suppressed_tags.extend(suppressed_tags)
                    
                    # Select psychological frame
                    user_goal = self._extract_user_goal(user_message) if user_message else None
                    psychological_frame = self._select_psychological_frame(result, primary_narrative, user_goal)
                    psychological_frames.append(psychological_frame)
                    
                    # Extract D2 vs D16 comparison
                    d2_vs_d16 = self._extract_d2_vs_d16_comparison(result)
                    
                    facts = {
                        "focus": self._get_request_attr(inv_req, "focus"),
                        "purpose": self._get_request_attr(inv_req, "purpose"),
                        "primary_narrative": primary_narrative,  # NEW
                        "eval_before": result.eval_before,
                        "eval_after": result.eval_after,
                        "eval_drop": result.eval_drop,
                        "game_phase": result.game_phase,
                        "urgency": result.urgency,
                        "tactics_found": len(result.tactics_found) > 0,
                        "has_threats": len(result.threats) > 0,
                        "player_move": result.player_move,
                        "best_move": result.best_move,
                        "material_change": result.material_change,
                        "positional_change": result.positional_change,
                        "selected_tag_deltas": selected_tags,  # NEW: Only top 2
                        "d2_vs_d16": d2_vs_d16
                    }
                    facts_list.append(facts)
            
            # Select dominant primary narrative (most common or highest priority)
            dominant_narrative = primary_narratives[0] if primary_narratives else "positional_concession_without_compensation"
            dominant_frame = psychological_frames[0] if psychological_frames else "reasonable idea, wrong moment"
            
            # Select dominant mechanism (use first result's mechanism)
            dominant_mechanism = "changes the position in a way that affects your goal"
            if multiple_results and len(multiple_results) > 0:
                first_result = multiple_results[0].get("result")
                if isinstance(first_result, InvestigationResult):
                    # Get selected tags from first result
                    first_pgn_deltas = self._get_structured_deltas_from_inv(first_result)
                    first_tag_ranking = self._rank_and_suppress_tag_deltas(first_pgn_deltas)
                    first_selected_tags = first_tag_ranking["selected_tags"]
                    mechanism_result = self._select_mechanism(
                        first_result,
                        first_selected_tags,
                        {}
                    )
                    dominant_mechanism, dominant_evidence = mechanism_result if isinstance(mechanism_result, tuple) else (mechanism_result, None)
            
            # Store for validation
            selected_primary_narrative = dominant_narrative
            selected_psychological_frame = dominant_frame
            selected_mechanism = dominant_mechanism
            selected_mechanism_evidence = dominant_evidence
            all_suppressed_tags_combined = all_suppressed_tags
            
            # Extract ALL tag and role deltas from all results (no suppression)
            all_tag_deltas_comparison = []
            all_role_deltas_comparison = []  # NEW: Extract role deltas for comparison
            pgn_with_tag_deltas = ""
            if multiple_results and len(multiple_results) > 0:
                for item in multiple_results:
                    result = item.get("result")
                    if isinstance(result, InvestigationResult):
                        pgn_deltas = self._get_structured_deltas_from_inv(result)
                        if pgn_deltas and pgn_deltas.get("main_sequence"):
                            for move_data in pgn_deltas["main_sequence"]:
                                move_label = move_data.get("move", "")
                                for tag in move_data.get("tags_gained", []):
                                    all_tag_deltas_comparison.append({
                                        "direction": "gained",
                                        "tag": tag,
                                        "move": move_label,
                                        "result_index": multiple_results.index(item)
                                    })
                                for tag in move_data.get("tags_lost", []):
                                    all_tag_deltas_comparison.append({
                                        "direction": "lost",
                                        "tag": tag,
                                        "move": move_label,
                                        "result_index": multiple_results.index(item)
                                    })
                                for role in move_data.get("roles_gained", []):
                                    all_role_deltas_comparison.append({
                                        "direction": "gained",
                                        "role": role,
                                        "move": move_label,
                                        "result_index": multiple_results.index(item)
                                    })
                                for role in move_data.get("roles_lost", []):
                                    all_role_deltas_comparison.append({
                                        "direction": "lost",
                                        "role": role,
                                        "move": move_label,
                                        "result_index": multiple_results.index(item)
                                    })
                        # Use first result's structured deltas for reference
                        if not pgn_with_tag_deltas:
                            per_move = getattr(result, "evidence_per_move_deltas", []) or []
                            if per_move:
                                pgn_with_tag_deltas = self._format_structured_deltas_for_llm(per_move)
            
            # Calculate net changes for the first result's main PGN line (for key evidence selection)
            tags_gained_net_for_prompt = []
            tags_lost_net_for_prompt = []
            roles_gained_net_for_prompt = []
            roles_lost_net_for_prompt = []
            if multiple_results and len(multiple_results) > 0:
                first_result = multiple_results[0].get("result")
                if isinstance(first_result, InvestigationResult):
                    tags_gained_net_for_prompt = list(getattr(first_result, "evidence_tags_gained_net", []) or [])
                    tags_lost_net_for_prompt = list(getattr(first_result, "evidence_tags_lost_net", []) or [])
                    roles_gained_net_for_prompt = list(getattr(first_result, "evidence_roles_gained_net", []) or [])
                    roles_lost_net_for_prompt = list(getattr(first_result, "evidence_roles_lost_net", []) or [])
            
            # Build conditional sections based on force_suggestion
            comparison_data_section = ""
            if force_suggestion:
                # In suggestion mode, we still allow a *brief* contrast if the user explicitly asked to compare.
                # Keep the data small; the model should lead with the PRIMARY RECOMMENDATION regardless.
                comparison_data_section = (
                    "OTHER CANDIDATES (for optional brief contrast if the user asked to compare; do not over-focus):\n"
                    f"{json.dumps(facts_list[:4], indent=2)}"
                )
            else:
                comparison_data_section = f"COMPARISON DATA (other moves analyzed for context - DO NOT mention in core_message):\n{json.dumps(facts_list, indent=2)}"
            
            all_tag_deltas_section = ""
            if not force_suggestion and all_tag_deltas_comparison:
                all_tag_deltas_section = f"""ALL TAG DELTAS (from all results - for reference only):
Each entry has format: {{"direction": "gained"|"lost", "tag": "tag_name", "move": "move_san"}}
{json.dumps(all_tag_deltas_comparison[:40], indent=2)}"""
            
            all_role_deltas_section = ""
            if not force_suggestion and all_role_deltas_comparison:
                all_role_deltas_section = f"""ALL ROLE DELTAS (from all results - for reference only):
Each entry has format: {{"direction": "gained"|"lost", "role": "piece_id:role_name", "move": "move_san"}}
{json.dumps(all_role_deltas_comparison[:40], indent=2)}"""
            
            pgn_header = "PRIMARY RECOMMENDATION PGN (for reference):" if force_suggestion else "FULL PGN WITH TAG AND ROLE DELTAS (for reference):"
            
            core_message_instruction = ""
            if force_suggestion:
                core_message_instruction = """If SUGGESTION MODE: Lead with the PRIMARY RECOMMENDATION move directly (e.g., 'Play d4' or 'd4 helps you develop and castle'). If the user's question is explicitly comparative, you may add ONE brief contrast clause, but keep the recommendation first. If COMPARISON MODE: Explain the comparison."""
            else:
                core_message_instruction = """CRITICAL RULES FOR MOVE REFERENCES:
    - If user mentions a general goal (e.g., 'developing the knight', 'castling') but no specific move, identify which move they're thinking about
    - Structure options:
      * '[Better_move] is better than [worse_move] because [better_move] [tag_explanation] while [worse_move] [tag_explanation]'
      * 'Developing your [piece] is thwarted by [next_move] which [tag_explanation]'
      * 'Developing your [piece] doesn't work because after [full_PGN_sequence] [outcome_tag_explanation]'"""
            
            core_message_end = "For SUGGESTION MODE: State the recommendation directly without comparing." if force_suggestion else "Recommend the better move and explain why."
            
            strict_rules_prefix = "If SUGGESTION MODE: Lead with the PRIMARY RECOMMENDATION directly. If the user explicitly asked to compare, you may mention at most ONE alternative briefly. If COMPARISON MODE: " if force_suggestion else ""
            strict_rules_structure = "For SUGGESTION MODE: 'Play [move] ...' (optionally + one brief contrast). For COMPARISON MODE: " if force_suggestion else ""
            strict_rules_end = "For SUGGESTION MODE: Keep it decisive and recommendation-led. For COMPARISON MODE: " if force_suggestion else ""
            
            # Use LLM to decide narrative from multiple candidate move investigations.
            prompt = f"""You are an editorial decision-maker.
The analysis is already correct.
You must not introduce new chess ideas.
You must explain as a single cause → consequence → lesson chain.
Do not list facts. Do not hedge. Do not speculate.

USER QUERY: {user_message or "Compare these moves"}
USER GOAL (extracted): {user_goal or "unknown"}
DISCUSSION AGENDA (planner-provided; MUST cover): {json.dumps((execution_plan.discussion_agenda or [])[:6], indent=2) if execution_plan and getattr(execution_plan, "discussion_agenda", None) else "None"}

SUGGESTION MODE: {bool(force_suggestion)}
If SUGGESTION MODE is true:
- Treat this as "what should I do?" not a pure comparison.
- You MUST recommend the PRIMARY RECOMMENDATION move (below) in core_message.
- If the user's question is explicitly comparative, you MAY include ONE brief contrast clause, but the recommendation must come first and stay primary.
- Claim 1 MUST be the recommendation claim for the PRIMARY RECOMMENDATION move (with its evidence line).
- Remaining claims (2..N) should cover agenda topics and optionally warn about specific bad candidates.

PRIMARY RECOMMENDATION (deterministic; do not contradict):
{json.dumps(primary_recommendation, indent=2) if primary_recommendation else "None"}

{comparison_data_section}

{all_tag_deltas_section}

NET TAG CHANGES (final net tags after the PRIMARY RECOMMENDATION sequence):
These are the actual tags that will be shown to the user. Use these exact strings; do not invent tags.
Tags gained (net): {json.dumps(tags_gained_net_for_prompt[:20], indent=2) if tags_gained_net_for_prompt else "No net tags gained"}
Tags lost (net): {json.dumps(tags_lost_net_for_prompt[:20], indent=2) if tags_lost_net_for_prompt else "No net tags lost"}

{all_role_deltas_section}

NET ROLE CHANGES (final net roles after the PRIMARY RECOMMENDATION sequence):
These are the actual roles that will be shown to the user. Use these exact strings; do not invent roles.
Roles gained (net): {json.dumps(roles_gained_net_for_prompt[:20], indent=2) if roles_gained_net_for_prompt else "No net roles gained"}
Roles lost (net): {json.dumps(roles_lost_net_for_prompt[:20], indent=2) if roles_lost_net_for_prompt else "No net roles lost"}

{pgn_header}
{pgn_with_tag_deltas[:2000] if pgn_with_tag_deltas else "No PGN available"}

NARRATIVE STRUCTURE (suggestions - you have flexibility):
- You may want to consider: INTENT (what the player intended) → MECHANISM (what the move physically does) → OUTCOME (how it affects the goal)
- You have full control over how to organize and present the information
- Use whatever structure best answers the user's question

Output JSON:
{{
  "core_message": "ONE clear sentence. {core_message_instruction}
    - NEVER reference the LAST move in a sequence when explaining why something doesn't work
    - If referencing a single move, it must be the NEXT move the user would play (not the last move in the sequence)
    - If referencing a sequence, use the full PGN sequence and explain the final outcome with tag-based explanation
    - You may find it helpful to consider INTENT → MECHANISM → OUTCOME, but structure it however best answers the question.
    {core_message_end}",
  "psychological_frame": "How to frame this psychologically. For suggestions: encouraging. For mistakes: understanding but clear.",
  "mechanism": "ONE concrete board-level action describing what the move physically does. Generate from consequences and tags.",
  "selected_tags": ["tag1", "tag2", ...],  // Select 2-5 most relevant tags
  "claims": [
    {{
      "summary": "One clear sentence describing the claim",
      "claim_type": "tactical_issue|positional_concession|development_issue|missed_opportunity|general",
      "connector": "allows|creates|leads_to|because|None",
      "evidence_moves": ["Bxe2", "Qxe2"]  // If referencing a sequence, include the full sequence, not just the last move.
    }}
  ],
  "emphasis": ["primary_narrative", "key_consequence"],  // MAX 2 items
  "takeaway": "One concrete, actionable lesson (non-causal descriptive sentence only). DO NOT use generic phrases like 'Always consider', 'Always evaluate', 'By keeping', 'It's important to', 'Remember to'. Be specific and direct. If no specific takeaway, use null.",
  "verbosity": "brief|medium|detailed"
}}

STRICT RULES (anti-hallucination and quality - these are mandatory):
- core_message: Must be ONE clear sentence. {strict_rules_prefix}CRITICAL: If user mentions a general goal (developing, castling) but no specific move, identify which move they're thinking about. Structure: {strict_rules_structure}Either 'X is thwarted by [next_move] which [tag_explanation]' OR 'X doesn't work because after [full_PGN_sequence] [outcome_tag_explanation]'. NEVER reference the last move in a sequence when explaining why something doesn't work. {strict_rules_end}Recommend the better move and explain why.
- psychological_frame: Must match query type (encouraging for suggestions, understanding for mistakes)
- mechanism: Generate from consequences and tags. Must be concrete and verifiable. Do NOT invent mechanisms not supported by evidence.
- selected_tags: Choose 2-5 tags that directly support your narrative. Only use tags from the provided data.
- claims: Generate 3-6 claims (small scope each). Use multiple claims so each stays narrow and concrete.
  Coverage requirement: Across all claims, cover ALL DISCUSSION AGENDA questions/topics (at least one claim per agenda question or per topic).
  CRITICAL: Every claim must be grounded in evidence_moves or evidence_payload. Do NOT invent claims without evidence.
- emphasis must contain at most 2 items: primary_narrative and one key consequence
- takeaway must be concrete and reusable
- Do NOT add new chess analysis
- Do NOT invent tags, roles, or moves not present in the provided data
- Do NOT claim mechanisms or outcomes without evidence from tags/roles/eval deltas"""
        else:
            # Handle single investigation result (original format)
            # Note: discussion_agenda is already initialized at function top
            if not isinstance(investigation_result, InvestigationResult):
                # Fallback if wrong type
                print(f"   ⚠️ [SUMMARISER] WARNING: investigation_result is not InvestigationResult, type: {type(investigation_result)}")
                print(f"      Returning minimal NarrativeDecision")
                # Still attach PGN artifact if available via baseline_intuition context (UI/admin use).
                oc = None
                try:
                    baseline = (context or {}).get("baseline_intuition") if isinstance(context, dict) else None
                    scan_root = baseline.get("scan_root") if isinstance(baseline, dict) else None
                    if isinstance(scan_root, dict):
                        oc = {
                            "evidence_pgn_line": scan_root.get("evidence_pgn_line"),
                            "evidence_main_line_moves": scan_root.get("evidence_main_line_moves") or [],
                            "pgn_exploration": scan_root.get("pgn_exploration") or scan_root.get("pgn") or "",
                        }
                except Exception:
                    oc = None
                return NarrativeDecision(
                    core_message="Analysis complete",
                    mechanism="changes the position in a way that affects your goal",
                    mechanism_evidence=None,
                    emphasis=[],
                    verbosity="medium",
                    discussion_agenda=discussion_agenda,
                    original_pgn_context=oc,
                )
            
            # STEP 1: Extract ALL tag deltas (no suppression - LLM will decide what matters)
            pgn_tag_deltas_raw = None
            pgn_tag_deltas_raw = self._get_structured_deltas_from_inv(investigation_result)
            
            # Get all tag deltas without suppression
            all_tag_deltas = []
            all_role_deltas = []  # NEW: Extract role deltas
            if pgn_tag_deltas_raw and pgn_tag_deltas_raw.get("main_sequence"):
                for move_data in pgn_tag_deltas_raw["main_sequence"]:
                    for tag in move_data.get("tags_gained", []):
                        all_tag_deltas.append({
                            "direction": "gained",
                            "tag": tag,
                            "move": move_data.get("move", "")
                        })
                    for tag in move_data.get("tags_lost", []):
                        all_tag_deltas.append({
                            "direction": "lost",
                            "tag": tag,
                            "move": move_data.get("move", "")
                        })
                    # NEW: Extract role deltas
                    for role in move_data.get("roles_gained", []):
                        all_role_deltas.append({
                            "direction": "gained",
                            "role": role,
                            "move": move_data.get("move", "")
                        })
                    for role in move_data.get("roles_lost", []):
                        all_role_deltas.append({
                            "direction": "lost",
                            "role": role,
                            "move": move_data.get("move", "")
                        })
            
            # FALLBACK: Keep old mechanism selection for evidence binding only
            fallback_mechanism_result = self._select_mechanism(
                investigation_result,
                all_tag_deltas[:10],  # Pass first 10 for fallback
                {}  # consequences field removed - pass empty dict
            )
            fallback_mechanism, fallback_mechanism_evidence = fallback_mechanism_result if isinstance(fallback_mechanism_result, tuple) else (fallback_mechanism_result, None)
            
            # FALLBACK: Select primary narrative and psychological frame (only used if LLM fails)
            fallback_primary_narrative = self._select_primary_narrative(investigation_result)
            user_goal = self._extract_user_goal(user_message) if user_message else None
            fallback_psychological_frame = self._select_psychological_frame(investigation_result, fallback_primary_narrative, user_goal)
            
            # STEP 4: Extract D2 vs D16 comparison
            d2_vs_d16 = self._extract_d2_vs_d16_comparison(investigation_result)
            
            # STEP 5: Determine investigation type from execution plan
            investigation_type = "position"
            if execution_plan and hasattr(execution_plan, 'steps'):
                for step in execution_plan.steps:
                    if step.action_type == "investigate_move":
                        investigation_type = "move"
                        break
            
            # STEP 6: Build facts with ALL tag and role deltas for LLM reference
            facts = {
                "eval_drop": investigation_result.eval_drop,
                "intent_mismatch": investigation_result.intent_mismatch,
                "game_phase": investigation_result.game_phase,
                "urgency": investigation_result.urgency,
                "tactics_found": len(investigation_result.tactics_found) > 0,
                "has_threats": len(investigation_result.threats) > 0,
                "player_move": investigation_result.player_move,
                "best_move": investigation_result.best_move,
                "missed_move": investigation_result.missed_move,
                "material_change": investigation_result.material_change,
                "positional_change": investigation_result.positional_change,
                "d2_vs_d16": d2_vs_d16,
                "investigation_type": investigation_type,
                # Starting tags/roles are optional; prefer Investigator-provided structured data if present.
                "starting_roles": pgn_tag_deltas_raw.get("starting_roles", {}) if isinstance(pgn_tag_deltas_raw, dict) else {},
                "starting_tags": pgn_tag_deltas_raw.get("starting_tags", []) if isinstance(pgn_tag_deltas_raw, dict) else []
            }

            # NEW: Evidence-line eval decomposition (core quantitative driver for claims)
            facts["evidence_eval"] = {
                "pgn_line": getattr(investigation_result, "evidence_pgn_line", None),
                "eval_start": getattr(investigation_result, "evidence_eval_start", None),
                "eval_end": getattr(investigation_result, "evidence_eval_end", None),
                "eval_delta": getattr(investigation_result, "evidence_eval_delta", None),
                "material_start": getattr(investigation_result, "evidence_material_start", None),
                "material_end": getattr(investigation_result, "evidence_material_end", None),
                "positional_start": getattr(investigation_result, "evidence_positional_start", None),
                "positional_end": getattr(investigation_result, "evidence_positional_end", None),
            }
            
            # Build organized PGN structure with per-move data
            try:
                organized_pgn_data = self._build_organized_pgn_structure(
                    investigation_result,
                    facts.get("evidence_eval", {})
                )
            except Exception as e:
                print(f"   ⚠️ [SUMMARISER] Error building organized PGN structure: {e}")
                organized_pgn_data = None

            # NEW: Build a "worded PGN" via a dedicated LLM call (SAN -> words), grounded by per-move FEN+stats+deltas.
            # This is used to help the downstream narrative avoid SAN->words hallucinations without hard-coded rules.
            # NOTE: worded_pgn/original_pgn_context are defined at function scope; do not re-declare here.
            worded_pgn = None
            original_pgn_context = {}
            try:
                # Use the shared helper so we include the full PGN artifact (with cap) consistently.
                original_pgn_context = self._build_original_pgn_context(investigation_result)
            except Exception:
                original_pgn_context = {}

            # For suggestion-style questions ("how should I progress / castle / develop"),
            # the user-facing "evidence line" should be the RECOMMENDED MOVE itself (often 1 ply),
            # not an arbitrary longer PV. We still attach the full exploration PGN separately.
            try:
                if force_suggestion:
                    bm = getattr(investigation_result, "best_move_d16", None) or getattr(investigation_result, "best_move", None)
                    if isinstance(bm, str) and bm.strip() and isinstance(original_pgn_context, dict):
                        original_pgn_context["evidence_pgn_line"] = bm.strip()
                        # Prefer the investigator-provided evidence_main_line_moves (now a fuller PV line).
                        pv = getattr(investigation_result, "evidence_main_line_moves", None) or getattr(investigation_result, "pv_after_move", None) or []
                        if not isinstance(pv, list):
                            pv = []
                        pv = [m for m in pv if isinstance(m, str) and m.strip()]
                        if pv and pv[0] != bm.strip():
                            pv = [bm.strip()] + [m for m in pv if m != bm.strip()]
                        original_pgn_context["evidence_main_line_moves"] = pv if pv else [bm.strip()]
            except Exception:
                pass

            try:
                if organized_pgn_data and isinstance(organized_pgn_data, dict):
                    def _classify_semantics(name: Optional[str]) -> str:
                        """
                        Deterministic coarse classification used to prevent polarity flips in Worded-PGN.
                        Returns: "problem" | "benefit" | "property"
                        """
                        s = (name or "").lower()
                        if any(k in s for k in ("trapped", "hanging", "overloaded", "undefended", "exposed", "pinned", "fork", "skewer", "overworked")):
                            return "problem"
                        if any(k in s for k in ("pair", "connected", "advantage")):
                            return "benefit"
                        return "property"

                    def _polarity_hints_for_move(role_delta: Dict[str, Any], meaningful_tag_delta: Dict[str, Any]) -> List[Dict[str, str]]:
                        """
                        Deterministic polarity hints so the Worded-PGN LLM cannot flip gained/lost semantics.
                        """
                        hints: List[Dict[str, str]] = []

                        rg = role_delta.get("gained") if isinstance(role_delta, dict) else []
                        rl = role_delta.get("lost") if isinstance(role_delta, dict) else []
                        tg = meaningful_tag_delta.get("gained") if isinstance(meaningful_tag_delta, dict) else []
                        tl = meaningful_tag_delta.get("lost") if isinstance(meaningful_tag_delta, dict) else []

                        for r in (rg or []):
                            if not isinstance(r, str) or not r:
                                continue
                            c = _classify_semantics(r)
                            if c == "problem":
                                hints.append({"type": "role", "polarity": "problem_appeared", "name": r})
                            elif c == "benefit":
                                hints.append({"type": "role", "polarity": "benefit_appeared", "name": r})
                            else:
                                hints.append({"type": "role", "polarity": "property_appeared", "name": r})

                        for r in (rl or []):
                            if not isinstance(r, str) or not r:
                                continue
                            c = _classify_semantics(r)
                            if c == "problem":
                                hints.append({"type": "role", "polarity": "problem_resolved", "name": r})
                            elif c == "benefit":
                                hints.append({"type": "role", "polarity": "benefit_removed", "name": r})
                            else:
                                hints.append({"type": "role", "polarity": "property_removed", "name": r})

                        for t in (tg or []):
                            if not isinstance(t, str) or not t:
                                continue
                            c = _classify_semantics(t)
                            if c == "problem":
                                hints.append({"type": "tag", "polarity": "problem_appeared", "name": t})
                            elif c == "benefit":
                                hints.append({"type": "tag", "polarity": "benefit_appeared", "name": t})
                            else:
                                hints.append({"type": "tag", "polarity": "property_appeared", "name": t})

                        for t in (tl or []):
                            if not isinstance(t, str) or not t:
                                continue
                            c = _classify_semantics(t)
                            if c == "problem":
                                hints.append({"type": "tag", "polarity": "problem_resolved", "name": t})
                            elif c == "benefit":
                                hints.append({"type": "tag", "polarity": "benefit_removed", "name": t})
                            else:
                                hints.append({"type": "tag", "polarity": "property_removed", "name": t})

                        return hints

                    def _fmt_eval_header(*, evidence_eval: Dict[str, Any], prefix: str = "") -> Optional[str]:
                        """
                        Build a single human-readable header sentence describing start/end eval + material/positional breakdown.
                        Generic (no chess-specific wording beyond "material"/"position").
                        """
                        try:
                            ev0 = evidence_eval.get("eval_start")
                            ev1 = evidence_eval.get("eval_end")
                            m0 = evidence_eval.get("material_start")
                            m1 = evidence_eval.get("material_end")
                            p0 = evidence_eval.get("positional_start")
                            p1 = evidence_eval.get("positional_end")
                            if ev0 is None or ev1 is None or m0 is None or m1 is None:
                                return None

                            d_ev = ev1 - ev0
                            d_m = m1 - m0
                            d_p = (p1 - p0) if (p0 is not None and p1 is not None) else None

                            def _side(x: float) -> str:
                                return "White" if x > 0 else "Black" if x < 0 else "Equal"

                            def _bucket(total: float) -> str:
                                a = abs(total)
                                if a < 0.4:
                                    return "roughly equal"
                                if a < 1.5:
                                    return f"slightly better for {_side(total)}"
                                if a < 3.0:
                                    return f"better for {_side(total)}"
                                return f"winning for {_side(total)}"

                            exchange_note = "no net material change" if abs(d_m) < 0.5 else (f"material gain for White" if d_m > 0 else "material gain for Black")
                            # Phrase from White POV to avoid confusing mixed perspective.
                            pos_note = "positional shift unclear" if d_p is None else ("position improved for White" if d_p > 0 else "position worsened for White" if d_p < 0 else "position unchanged")
                            overall = _bucket(ev1)
                            return (
                                f"{prefix}Eval {ev0:+.2f} → {ev1:+.2f} (Δ {d_ev:+.2f}); "
                                f"material {m0:+.2f} → {m1:+.2f} (Δ {d_m:+.2f}) ({exchange_note}); "
                                f"position {p0:+.2f} → {p1:+.2f} (Δ {d_p:+.2f}) ({pos_note}); "
                                f"overall: {overall}."
                                if (p0 is not None and p1 is not None and d_p is not None)
                                else
                                f"{prefix}Eval {ev0:+.2f} → {ev1:+.2f} (Δ {d_ev:+.2f}); "
                                f"material {m0:+.2f} → {m1:+.2f} (Δ {d_m:+.2f}) ({exchange_note}); "
                                f"overall: {overall}."
                            )
                        except Exception:
                            return None

                    def _is_clutter_tag_name(t: Any) -> bool:
                        if not isinstance(t, str):
                            return False
                        cluttering_prefixes = (
                            "tag.diagonal.", "tag.file.", "tag.key.", "tag.center.",
                            "tag.activity.", "tag.lever.", "tag.color.hole."
                        )
                        return any(t.startswith(p) for p in cluttering_prefixes)

                    def _filter_meaningful_tag_list(xs: Any) -> List[str]:
                        if not isinstance(xs, list):
                            return []
                        out: List[str] = []
                        for x in xs:
                            if isinstance(x, str) and x and (not _is_clutter_tag_name(x)):
                                out.append(x)
                        return out

                    # Provide BOTH: a filtered "meaningful-only" view and the full view.
                    # The worded-PGN call MUST include all meaningful tags/roles, but should ignore clutter.
                    organized_pgn_meaningful = dict(organized_pgn_data)
                    moves_in = organized_pgn_meaningful.get("moves") if isinstance(organized_pgn_meaningful.get("moves"), list) else []
                    moves_out: List[Dict[str, Any]] = []
                    for m in moves_in:
                        if not isinstance(m, dict):
                            continue
                        m2 = dict(m)
                        td = m2.get("tag_delta") if isinstance(m2.get("tag_delta"), dict) else {}
                        # Filter deltas to meaningful-only; keep ALL (no cap) after filtering.
                        m2["meaningful_tag_delta"] = {
                            "gained": _filter_meaningful_tag_list(td.get("gained")),
                            "lost": _filter_meaningful_tag_list(td.get("lost")),
                        }
                        # Deterministic polarity hints to prevent the worded-PGN model from flipping gained/lost semantics.
                        rd = m2.get("role_delta") if isinstance(m2.get("role_delta"), dict) else {}
                        m2["polarity_hints"] = _polarity_hints_for_move(rd, m2["meaningful_tag_delta"])
                        # For the worded-PGN call, do NOT include per-move eval/material/positional.
                        # We only want start/end evaluation summary for the line.
                        if "eval" in m2:
                            del m2["eval"]
                        if "material" in m2:
                            del m2["material"]
                        if "positional" in m2:
                            del m2["positional"]
                        # Remove raw tag_delta entirely to prevent clutter leakage; use meaningful_tag_delta instead.
                        if "tag_delta" in m2:
                            del m2["tag_delta"]
                        moves_out.append(m2)
                    organized_pgn_meaningful["moves"] = moves_out

                    # Header summary for the main evidence line (start/end only)
                    main_header = _fmt_eval_header(evidence_eval=facts.get("evidence_eval", {}) or {}, prefix="Main line: ")

                    # Build alternate lines from comparison payloads if available (e.g., other investigated moves)
                    alternate_lines: List[Dict[str, Any]] = []
                    try:
                        # If we're in comparison mode, a `multiple_results` list should be in scope.
                        mr = locals().get("multiple_results")
                        if isinstance(mr, list) and mr:
                            # Add up to 4 alternates (excluding the primary line move if possible)
                            for item in mr[:6]:
                                if not isinstance(item, dict):
                                    continue
                                alt_res = item.get("result")
                                alt_req = item.get("request")
                                if not isinstance(alt_res, InvestigationResult):
                                    continue
                                # Skip same line as main evidence line
                                if getattr(alt_res, "evidence_pgn_line", None) == getattr(investigation_result, "evidence_pgn_line", None):
                                    continue

                                alt_ev = {
                                    "pgn_line": getattr(alt_res, "evidence_pgn_line", None),
                                    "eval_start": getattr(alt_res, "evidence_eval_start", None),
                                    "eval_end": getattr(alt_res, "evidence_eval_end", None),
                                    "eval_delta": getattr(alt_res, "evidence_eval_delta", None),
                                    "material_start": getattr(alt_res, "evidence_material_start", None),
                                    "material_end": getattr(alt_res, "evidence_material_end", None),
                                    "positional_start": getattr(alt_res, "evidence_positional_start", None),
                                    "positional_end": getattr(alt_res, "evidence_positional_end", None),
                                }
                                alt_struct = self._build_organized_pgn_structure(alt_res, alt_ev) or {}
                                alt_meaningful = dict(alt_struct) if isinstance(alt_struct, dict) else {}
                                alt_moves_in = alt_meaningful.get("moves") if isinstance(alt_meaningful.get("moves"), list) else []
                                alt_moves_out: List[Dict[str, Any]] = []
                                for m in alt_moves_in:
                                    if not isinstance(m, dict):
                                        continue
                                    m2 = dict(m)
                                    td = m2.get("tag_delta") if isinstance(m2.get("tag_delta"), dict) else {}
                                    m2["meaningful_tag_delta"] = {
                                        "gained": _filter_meaningful_tag_list(td.get("gained")),
                                        "lost": _filter_meaningful_tag_list(td.get("lost")),
                                    }
                                    for k in ("eval", "material", "positional", "tag_delta"):
                                        if k in m2:
                                            del m2[k]
                                    alt_moves_out.append(m2)
                                alt_meaningful["moves"] = alt_moves_out

                                label = None
                                try:
                                    label = getattr(alt_req, "focus", None) if alt_req else None
                                except Exception:
                                    label = None
                                label = label or getattr(alt_res, "player_move", None) or "alternate"
                                alt_header = _fmt_eval_header(evidence_eval=alt_ev, prefix=f"Alternate ({label}): ")
                                alternate_lines.append({
                                    "label": label,
                                    "header_summary": alt_header,
                                    "organized_pgn_meaningful": alt_meaningful,
                                })
                                if len(alternate_lines) >= 4:
                                    break
                    except Exception:
                        alternate_lines = []

                    worded_payload = {
                        "user_query": user_message,
                        "original_pgn_context": original_pgn_context,
                        "mainline": {
                            "header_summary": main_header,
                            "organized_pgn_meaningful": organized_pgn_meaningful,
                        },
                        "alternate_lines": alternate_lines,
                    }

                    worded_prompt = (
                        "You convert SAN PGN into a grounded English narration.\n"
                        "\n"
                        "MANDATORY INPUTS:\n"
                        "- mainline.organized_pgn_meaningful.moves[] includes: ply, move_san, fen_before, fen_after, meaningful_tag_delta, role_delta, polarity_hints.\n"
                        "- mainline.header_summary summarizes start/end eval/material/positional.\n"
                        "- alternate_lines[] (if present) each have header_summary + organized_pgn_meaningful.\n"
                        "\n"
                        "RULES (MANDATORY):\n"
                        "- If mainline.header_summary is a non-empty string, start the mainline narration with it as the first sentence (or a close paraphrase). Do not invent numbers.\n"
                        "- If alternate_lines exist, produce a separate narration per alternate. If its header_summary is non-empty, start with it.\n"
                        "- Use fen_before/fen_after to identify pieces and their squares. If uncertain, refer to the piece by square (e.g. 'the bishop on e2').\n"
                        "- Polarity MUST match polarity_hints. You may not flip gained/lost direction.\n"
                        "  * If polarity_hints contains problem_appeared for X: do NOT say it was resolved/fixed/freed.\n"
                        "  * If polarity_hints contains problem_resolved for X: do NOT say it appeared/was created.\n"
                        "- For EACH move, your sentence MUST include:\n"
                        "  1) the board action in words (capture/develop/etc.) grounded in SAN + FEN,\n"
                        "  2) ALL meaningful tag deltas for that move (from meaningful_tag_delta), and\n"
                        "  3) ALL role deltas for that move (from role_delta).\n"
                        "- Also include a short polarity clause per move using ONLY polarity_hints (no inventions).\n"
                        "- You MAY interpret tag/role meaning using only GENERIC substring heuristics, not specific tag names.\n"
                        "  Examples of generic heuristics:\n"
                        "  * If a LOST tag contains words like 'trapped', 'undeveloped', 'hanging', 'overworked', or 'exposed' → phrase it as a problem being resolved.\n"
                        "  * If a GAINED tag contains those words → phrase it as a problem appearing.\n"
                        "  * If a LOST tag contains words like 'pair', 'advantage', or 'connected' → phrase it as a benefit being removed.\n"
                        "  * Otherwise, treat it as a neutral property change.\n"
                        "- Do NOT invent tags/roles/evals not present in the input.\n"
                        "\n"
                        "OUTPUT JSON:\n"
                        "{\n"
                        '  \"mainline\": {\n'
                        '    \"header_summary\": \"...\",\n'
                        '    \"worded_pgn\": \"...\",\n'
                        '    \"moves\": [\n'
                        "      {\n"
                        '        \"ply\": 1,\n'
                        '        \"move_san\": \"...\",\n'
                        '        \"sentence\": \"...\",\n'
                        '        \"meaningful_tag_delta\": {\"gained\": [...], \"lost\": [...]},\n'
                        '        \"role_delta\": {\"gained\": [...], \"lost\": [...]},\n'
                        '        \"polarity_hints\": [{\"type\":\"role|tag\",\"polarity\":\"...\",\"name\":\"...\"}],\n'
                        '        \"fen_before\": \"...\",\n'
                        '        \"fen_after\": \"...\"\n'
                        "      }\n"
                        "    ]\n"
                        "  },\n"
                        '  \"alternate_lines\": [\n'
                        '    {\n'
                        '      \"label\": \"...\",\n'
                        '      \"header_summary\": \"...\",\n'
                        '      \"worded_pgn\": \"...\",\n'
                        '      \"moves\": [ {\"ply\": 1, \"move_san\": \"...\", \"sentence\": \"...\", \"meaningful_tag_delta\": {\"gained\":[],\"lost\":[]}, \"role_delta\": {\"gained\":[],\"lost\":[]}, \"polarity_hints\": [{\"type\":\"role|tag\",\"polarity\":\"...\",\"name\":\"...\"}], \"fen_before\": \"...\", \"fen_after\": \"...\"} ]\n'
                        "    }\n"
                        "  ],\n"
                        '  \"notes\": []\n'
                        "}\n"
                    )
                    import time as _time
                    from pipeline_timer import get_pipeline_timer
                    _timer = get_pipeline_timer()
                    _t0 = _time.perf_counter()
                    resp = None
                    if self.llm_router:
                        worded_pgn = self.llm_router.complete_json(
                            session_id=session_id or "default",
                            stage="summariser_worded_pgn",
                            system_prompt=worded_prompt,
                            user_text=json.dumps(worded_payload, ensure_ascii=False),
                            temperature=(0.2 if "gpt-5" not in self.model.lower() else None),
                            model=self.model,
                        )
                    else:
                        resp = self.client.chat.completions.create(
                            model=self.model,
                            messages=[
                                {"role": "system", "content": worded_prompt},
                                {"role": "user", "content": json.dumps(worded_payload, ensure_ascii=False)}
                            ],
                            response_format={"type": "json_object"},
                            # Only set temperature if model supports it (gpt-5 doesn't support custom temperature)
                            **({"temperature": 0.2} if "gpt-5" not in self.model.lower() else {}),
                        )
                    _dt = _time.perf_counter() - _t0
                    try:
                        usage = getattr(resp, "usage", None) if resp is not None else None
                        prompt_tokens = getattr(usage, "prompt_tokens", None)
                        completion_tokens = getattr(usage, "completion_tokens", None)
                    except Exception:
                        prompt_tokens = None
                        completion_tokens = None
                    # worded_pgn feature removed; no longer record summariser_worded_pgn stats
                    if resp is not None:
                        import json as _json
                        worded_pgn = _json.loads(resp.choices[0].message.content)
            except Exception as e:
                print(f"   ⚠️ [SUMMARISER] Worded PGN generation failed (non-fatal): {e}")
                worded_pgn = None

            # NEW: Deterministic semantic story (grounded interpretation aid for tag/role deltas)
            semantic_story = None
            try:
                semantic_story = build_semantic_story(
                    investigation_result=investigation_result,
                    evidence_eval=facts.get("evidence_eval", {}) or {}
                )
            except Exception as e:
                print(f"   ⚠️ [SUMMARISER] Error building semantic story: {e}")
                semantic_story = None
            
            # Net changes for prompt: Prefer Investigator's precomputed evidence deltas (single source of truth).
            tags_gained_net_full = list(getattr(investigation_result, "evidence_tags_gained_net", []) or [])
            tags_lost_net_full = list(getattr(investigation_result, "evidence_tags_lost_net", []) or [])
            tags_gained_net_structured_full = list(getattr(investigation_result, "evidence_tags_gained_net_structured", []) or [])
            tags_lost_net_structured_full = list(getattr(investigation_result, "evidence_tags_lost_net_structured", []) or [])
            roles_gained_net_full = list(getattr(investigation_result, "evidence_roles_gained_net", []) or [])
            roles_lost_net_full = list(getattr(investigation_result, "evidence_roles_lost_net", []) or [])

            # PRIMARY CONTEXT: roles + major tags, grouped by piece (keeps prompt compact)
            primary_context = self._build_primary_context(
                investigation_result,
                tags_gained_net=tags_gained_net_full,
                tags_lost_net=tags_lost_net_full,
                tags_gained_net_structured=tags_gained_net_structured_full,
                tags_lost_net_structured=tags_lost_net_structured_full,
                roles_gained_net=roles_gained_net_full,
                roles_lost_net=roles_lost_net_full,
            )

            # Net tag lists are already slimmed at the source (Investigator/Executor),
            # so we should expose MOST of them as selectable evidence and omit only clutter.
            # (We keep major-tags inside primary_context for quick scanning.)
            #
            # Additional filtering: remove any cluttering tags that slipped through
            cluttering_prefixes = (
                "tag.diagonal.", "tag.file.", "tag.key.", "tag.center.", 
                "tag.activity.", "tag.lever.", "tag.color.hole."
            )
            tags_gained_net_for_prompt = [
                t for t in tags_gained_net_full
                if isinstance(t, str) and not any(t.startswith(prefix) for prefix in cluttering_prefixes)
            ]
            tags_lost_net_for_prompt = [
                t for t in tags_lost_net_full
                if isinstance(t, str) and not any(t.startswith(prefix) for prefix in cluttering_prefixes)
            ]
            roles_gained_net_for_prompt = [
                r for r in roles_gained_net_full
                if (":" in r and self._is_major_role_name(r.split(":", 1)[1]))
            ]
            roles_lost_net_for_prompt = [
                r for r in roles_lost_net_full
                if (":" in r and self._is_major_role_name(r.split(":", 1)[1]))
            ]
            main_pgn_line = getattr(investigation_result, "evidence_pgn_line", None)
            if main_pgn_line:
                print(f"   🔍 [NET_CHANGES_PROMPT] Using precomputed evidence line: {main_pgn_line}")
            print(f"   🔍 [NET_CHANGES_PROMPT] Net changes calculated (primary context):")
            print(f"      - Tags gained (major): {len(tags_gained_net_for_prompt)} items (sample: {tags_gained_net_for_prompt[:5]})")
            print(f"      - Tags lost (major): {len(tags_lost_net_for_prompt)} items (sample: {tags_lost_net_for_prompt[:5]})")
            print(f"      - Roles gained (major): {len(roles_gained_net_for_prompt)} items (sample: {roles_gained_net_for_prompt[:5]})")
            print(f"      - Roles lost (major): {len(roles_lost_net_for_prompt)} items (sample: {roles_lost_net_for_prompt[:5]})")
            
            # Compute tag competition (good vs bad tags using eval breakdown)
            tag_competition = self._compute_tag_competition(
                tags_lost_net=tags_lost_net_for_prompt,
                evidence_eval=facts.get("evidence_eval")
            )

            # Optional: NNUE-driven tag relevance from baseline_intuition (if present in context).
            nnue_tag_relevance_ranked: List[Dict[str, Any]] = []
            try:
                baseline = (context or {}).get("baseline_intuition") if isinstance(context, dict) else None
                scan_root = baseline.get("scan_root") if isinstance(baseline, dict) else None
                claims = scan_root.get("claims") if isinstance(scan_root, dict) else None
                if isinstance(claims, list):
                    evidence_claim = None
                    for c in claims:
                        if isinstance(c, dict) and c.get("claim_type") == "evidence_line":
                            evidence_claim = c
                            break
                    if isinstance(evidence_claim, dict):
                        nnue = evidence_claim.get("nnue_tag_relevance") or {}
                        ranked = nnue.get("tag_relevance_ranked")
                        if isinstance(ranked, list):
                            nnue_tag_relevance_ranked = [x for x in ranked if isinstance(x, dict)][:8]
            except Exception:
                nnue_tag_relevance_ranked = []

            significance = {
                # In relaxed mode, don't force mention; just provide as optional guidance.
                "top_outcomes_rule": (
                    "OPTIONAL: mention the top 1-2 outcomes by relevance_score if it helps the user's question."
                    if getattr(self, "relaxed_llm_mode", False)
                    else "MUST mention the top 2 outcomes by relevance_score (if present) or by importance."
                ),
                "evidence_eval": facts.get("evidence_eval") or {},
                "tag_competition": tag_competition or {},
                "nnue_tag_relevance_top": nnue_tag_relevance_ranked,
            }
            
            # Use LLM to decide narrative, core message, psychological frame, mechanism, tags, claims, and PGN sequences
            agenda_text = ""
            try:
                if execution_plan and hasattr(execution_plan, "discussion_agenda") and execution_plan.discussion_agenda:
                    # Enrich agenda with deterministic "must-surface" evidence so coverage is enforceable.
                    # This avoids the planner sending empty must_surface arrays.
                    moves_tested: List[str] = []
                    try:
                        if hasattr(execution_plan, "steps") and execution_plan.steps:
                            for st in execution_plan.steps:
                                if getattr(st, "action_type", None) == "investigate_move":
                                    san = (getattr(st, "parameters", {}) or {}).get("move_san")
                                    if isinstance(san, str) and san:
                                        moves_tested.append(san)
                    except Exception:
                        moves_tested = []

                    agenda_for_prompt: List[Dict[str, Any]] = []
                    for item in (execution_plan.discussion_agenda or []):
                        if not isinstance(item, dict):
                            continue
                        enriched = dict(item)
                        enriched.setdefault("moves_tested", moves_tested[:12])
                        enriched.setdefault("primary_evidence_pgn_line", main_pgn_line)
                        # Pass through any resolved piece identity so the LLM doesn't mix multiple instances
                        # (e.g., two knights) when summarising "the knight".
                        try:
                            target_piece = None
                            oi = getattr(execution_plan, "original_intent", None)
                            ci = getattr(oi, "connected_ideas", None) if oi else None
                            if isinstance(ci, dict):
                                ents = ci.get("entities") or []
                                if isinstance(ents, list):
                                    for e in ents:
                                        if not isinstance(e, dict):
                                            continue
                                        label = e.get("label")
                                        if not isinstance(label, str):
                                            continue
                                        # Piece-instance ids look like: white_knight_g1
                                        if label.count("_") == 2 and label.split("_")[0] in ("white", "black"):
                                            target_piece = label
                                            break
                                        if label.startswith("needs_clarification:"):
                                            # Surface ambiguity for the LLM to ask a question (if execution reached summariser)
                                            enriched.setdefault("needs_clarification", label)
                            if target_piece:
                                enriched.setdefault("target_piece", target_piece)
                        except Exception:
                            pass
                        enriched["must_surface"] = {
                            # Tags: must be surfaced somewhere across the claims. (Roles can be selective if long.)
                            "tags_gained_net": tags_gained_net_for_prompt[:60],
                            "tags_lost_net": tags_lost_net_for_prompt[:60],
                            "roles_gained_net": roles_gained_net_for_prompt[:40],
                            "roles_lost_net": roles_lost_net_for_prompt[:40],
                        }
                        # If we have comparison mode, provide quick per-move evidence summaries to guide coverage.
                        try:
                            if is_comparison and isinstance(investigation_result, dict) and investigation_result.get("multiple_results"):
                                candidates: List[Dict[str, Any]] = []
                                for mr in investigation_result.get("multiple_results", [])[:8]:
                                    res = mr.get("result")
                                    req = mr.get("request")
                                    if not isinstance(res, InvestigationResult):
                                        continue
                                    label = None
                                    try:
                                        label = getattr(req, "focus", None) if req else None
                                    except Exception:
                                        label = None
                                    label = label or getattr(res, "player_move", None) or "candidate"
                                    candidates.append({
                                        "label": label,
                                        "evidence_pgn_line": getattr(res, "evidence_pgn_line", None),
                                        "eval_start": getattr(res, "evidence_eval_start", None),
                                        "eval_end": getattr(res, "evidence_eval_end", None),
                                        "eval_delta": getattr(res, "evidence_eval_delta", None),
                                        "material_delta": (getattr(res, "evidence_material_end", None) - getattr(res, "evidence_material_start", None))
                                        if (getattr(res, "evidence_material_start", None) is not None and getattr(res, "evidence_material_end", None) is not None)
                                        else None,
                                    })
                                enriched["candidate_lines"] = candidates
                        except Exception:
                            pass

                        agenda_for_prompt.append(enriched)

                    agenda_text = "\nDISCUSSION AGENDA (planner-provided; MUST cover these topics):\n"
                    agenda_text += json.dumps(agenda_for_prompt, indent=2) + "\n"
            except Exception:
                agenda_text = ""

            # Keep prompt size bounded (vLLM context is limited).
            def _dump_json_limited(obj: Any, max_chars: int) -> str:
                try:
                    s = json.dumps(obj, indent=2)
                except Exception:
                    s = str(obj)
                if not isinstance(s, str):
                    s = str(s)
                if max_chars <= 0:
                    return ""
                if len(s) <= max_chars:
                    return s
                return s[:max_chars] + f"\n... <truncated {len(s) - max_chars} chars>"

            facts_json = _dump_json_limited(facts, int(os.getenv("SUMMARISER_FACTS_MAX_CHARS", "4500")))
            significance_json = _dump_json_limited(significance, int(os.getenv("SUMMARISER_SIGNIFICANCE_MAX_CHARS", "1800")))
            primary_context_json = _dump_json_limited(primary_context, int(os.getenv("SUMMARISER_PRIMARY_CONTEXT_MAX_CHARS", "3500")))
            original_pgn_context_json = _dump_json_limited(original_pgn_context, int(os.getenv("SUMMARISER_ORIGINAL_PGN_CONTEXT_MAX_CHARS", "2500")))
            worded_pgn_json = _dump_json_limited(worded_pgn, int(os.getenv("SUMMARISER_WORDED_PGN_MAX_CHARS", "2500"))) if worded_pgn else "No worded PGN available"
            prompt = f"""You are an editorial decision-maker.
The analysis is already correct.
You must not introduce new chess ideas.
You must explain the position as a single cause → consequence → lesson chain.
Do not list facts. Do not hedge. Do not speculate.

USER QUERY: {user_message or "Analyze this position"}
USER GOAL (extracted): {user_goal or "unknown"}

INVESTIGATION FACTS (structured data only):
{facts_json}

{agenda_text}

SIGNIFICANCE SCORES (deterministic; optional guidance):
Use these only if they help; do NOT force-mention them.
These are intended to prevent hallucinated mechanisms that are not supported by evidence.
{significance_json}

PRIMARY CONTEXT (use this first; compact and piece-linked):
{primary_context_json}

ORIGINAL PGN CONTEXT (grounding only; do NOT invent beyond this):
{original_pgn_context_json}

WORDED PGN (SAN→words; grounded by per-move FEN+deltas):
{worded_pgn_json}

NET TAG CHANGES (final net tags after the sequence):
These are the actual tags that will be shown to the user. Copy the EXACT strings from these lists; do not invent tags.
Tags gained (net): {json.dumps(tags_gained_net_for_prompt[:60], indent=2) if tags_gained_net_for_prompt else "No net tags gained"}
Tags lost (net): {json.dumps(tags_lost_net_for_prompt[:60], indent=2) if tags_lost_net_for_prompt else "No net tags lost"}

ALL ROLE DELTAS (all role changes from the position - for reference only):
Each entry has format: {{"direction": "gained"|"lost", "role": "piece_id:role_name", "move": "move_san"}}
{json.dumps(all_role_deltas[:30], indent=2) if all_role_deltas else "No role deltas available"}

NET ROLE CHANGES (final net roles after the sequence):
These are the actual roles that will be shown to the user. Copy the EXACT strings from these lists; do not invent roles.
IMPORTANT: Role format is "color_piece_type_square:role.name" (e.g., "white_bishop_e2:role.tactical.pinned" or "black_queen_e5:role.attacking.overloaded_piece")
Roles gained (net): {json.dumps(roles_gained_net_for_prompt[:40], indent=2) if roles_gained_net_for_prompt else "No net roles gained"}
Roles lost (net): {json.dumps(roles_lost_net_for_prompt[:40], indent=2) if roles_lost_net_for_prompt else "No net roles lost"}

GROUNDING CONTRACT (keep this light; style is up to you):
- You are free in tone/structure.
- Any concrete chess claim MUST be supported by the provided evidence move sequence / PV / facts. If not supported, say it's unclear.
- Do NOT output raw internal identifiers (no `tag.*`, `role.*`, no debug labels like "Evidence:", "Eval Δ").
- Prefer quoting the evidence line (SAN sequence) when making a causal claim.
- Keep claims few and high-signal (2–5).

Output JSON (only these fields; keep strings short but natural):
{{
  "needs_more_context": false,
  "requested_context": [],
  "core_message": "1–2 sentences answering the user's question.",
  "psychological_frame": "Optional short framing (can be empty).",
  "mechanism": "One board-level mechanism grounded in the evidence line (or a neutral mechanism if unclear).",
  "selected_tags": ["tag.name", "..."],  // 0–5, optional; INTERNAL ONLY (will be hidden from user)
  "claims": [
    {{
      "summary": "Natural language claim grounded in evidence.",
      "claim_type": "tactical_issue|positional_concession|development_issue|missed_opportunity|general",
      "connector": "allows|creates|leads_to|because|None",
      "evidence_moves": ["SAN1", "SAN2"]
    }}
  ],
  "emphasis": [],
  "takeaway": null,
  "verbosity": "brief|medium|detailed"
}}

STRICT RULES (anti-hallucination and quality - these are mandatory):
- core_message: Must be ONE clear sentence. CRITICAL: If user mentions a general goal (developing, castling) but no specific move, identify which move they're thinking about. Structure: Either 'X is thwarted by [next_move] which [tag_explanation]' OR 'X doesn't work because after [full_PGN_sequence] [outcome_tag_explanation]'. NEVER reference the last move in a sequence when explaining why something doesn't work. You have flexibility in how you structure and present this.
- psychological_frame: Must match query type (encouraging for suggestions, understanding for mistakes)
- mechanism: Generate from consequences and tags. Must be concrete and verifiable. Examples from consequences: 'allows opponent to capture', 'weakens pawn structure', 'creates a pin'. Examples from tags: 'exploits overworked piece', 'weakens king safety'. Do NOT invent mechanisms not supported by evidence.
- CRITICAL EVAL STRUCTURE: You MUST use facts.evidence_eval to ground the direction of claims.
  * If eval_end < eval_start, the evidence line favors Black.
  * If eval_end > eval_start, the evidence line favors White.
  * Use material_start/material_end and positional_start/positional_end to justify whether the swing is material-driven or positional-driven.
  * EQUALITY CHECK: If |material_end - material_start| < 0.5 pawns AND |positional_end - positional_start| < 0.5 pawns, the position is roughly equal. In this case:
    - Do NOT claim "with advantage" or "with disadvantage" 
    - Use neutral language: "allows opponent captures" (not "allows opponent captures with advantage")
    - Only claim advantage/disadvantage if material OR positional change is >= 0.5 pawns
  * Do NOT say "this helps Black" unless evidence_eval supports it.
- selected_tags: Choose 2-5 tags that directly support your narrative. Don't just pick HIGH importance tags - pick contextually relevant ones. Only use tags from the provided data.
- suppressed_tags: List all tags NOT in selected_tags (for code enforcement).
- claims: Generate 3-6 claims (small scope each). Use multiple claims so each stays narrow and concrete.
  Coverage requirement: Across all claims, cover ALL DISCUSSION AGENDA questions/topics (at least one claim per agenda question or per topic).
  CRITICAL: Claims must be EVIDENCE-DRIVEN, not mechanism-driven. Every claim must be grounded in evidence_moves or evidence_payload. Do NOT invent claims without evidence.
  GENERATION PROCESS (MANDATORY ORDER):
  1. FIRST: Check facts.evidence_eval to see what actually happens in the evidence sequence
  2. SECOND: Check evidence_roles_gained_net and evidence_roles_lost_net to see piece activity/development
  3. THIRD: Generate claim summary that matches what the evidence shows, not what the mechanism suggests
  4. If evidence shows roughly equal position (material < 0.5 AND positional < 0.5), use neutral language
  5. If evidence shows development happening (roles with outpost/developing), do NOT claim development is blocked
  
  Each claim should have:
  * summary: Clear, non-causal sentence (or causal if connector provided). MUST match evidence sequence reality, not mechanism inference.
  * claim_type: Based on the type of issue (tactical, positional, development, etc.)
  * connector: Use if the claim is causal (e.g., "allows", "creates"). Use None for non-causal claims.
  * evidence_moves: 2-4 SAN moves from PGN/PV that prove the claim
  * reason: Why this claim matters
- pgn_sequences_to_extract: Select 2-3 sequences that PROVE your narrative. Each sequence should show a meaningful tag change.
- emphasis must contain at most 2 items: primary_narrative and one key consequence
- takeaway must be concrete and reusable
- Do NOT add new chess analysis
- Do NOT invent tags, roles, or moves not present in the provided data
- Do NOT claim mechanisms or outcomes without evidence from tags/roles/eval deltas"""

            # Log what's being sent to LLM
            print(f"   🔍 [LLM_PROMPT] Net changes being sent to LLM:")
            print(f"      - Tags gained (net): {len(tags_gained_net_for_prompt)} items")
            if tags_gained_net_for_prompt:
                print(f"         Sample: {tags_gained_net_for_prompt[:5]}")
            print(f"      - Tags lost (net): {len(tags_lost_net_for_prompt)} items")
            if tags_lost_net_for_prompt:
                print(f"         Sample: {tags_lost_net_for_prompt[:5]}")
            print(f"      - Roles gained (net): {len(roles_gained_net_for_prompt)} items")
            if roles_gained_net_for_prompt:
                print(f"         Sample: {roles_gained_net_for_prompt[:5]}")
            print(f"      - Roles lost (net): {len(roles_lost_net_for_prompt)} items")
            if roles_lost_net_for_prompt:
                print(f"         Sample: {roles_lost_net_for_prompt[:5]}")

        try:
            def _is_low_quality_decision(d: Any) -> bool:
                """
                Heuristic guard to avoid 'schema-valid but empty' outputs.
                Conservative: reject only clearly unhelpful placeholders.
                """
                if not isinstance(d, dict):
                    return True

                core = d.get("core_message")
                mech = d.get("mechanism")
                claims = d.get("claims", [])

                if not isinstance(core, str) or not core.strip():
                    return True
                if not isinstance(mech, str) or not mech.strip():
                    return True

                core_l = core.strip().lower()
                if core_l in {
                    "analysis complete",
                    "analysis complete.",
                    "comparison of moves",
                    "analysis of position",
                    "analysis of the position",
                }:
                    return True
                if len(core.strip()) < 8:
                    return True

                # In suggestion mode we need at least one grounded claim.
                if force_suggestion:
                    if not isinstance(claims, list) or len(claims) < 1:
                        return True

                return False

            def _call_llm(prompt_text: str, model: str) -> Tuple[Dict[str, Any], str]:
                import time as _time
                from pipeline_timer import get_pipeline_timer
                _timer = get_pipeline_timer()
                _t0 = _time.perf_counter()
                resp = None
                if self.llm_router:
                    cmd = render_command(
                        command="SUMMARIZE_FINDINGS",
                        input={"prompt": prompt_text},
                        constraints={"json_only": True},
                    )
                    parsed = self.llm_router.complete_json(
                        session_id=session_id or "default",
                        stage="summariser",
                        system_prompt=MIN_SYSTEM_PROMPT_V1,
                        task_seed=SUMMARISER_CONTRACT_V1,
                        user_text=cmd,
                        model=model,
                        max_tokens=int(os.getenv("SUMMARISER_MAX_TOKENS", "1200")),
                    )
                    raw = json.dumps(parsed, ensure_ascii=False)
                else:
                    resp = self.client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt_text}],
                        response_format={"type": "json_object"},
                    )
                    raw = resp.choices[0].message.content
                _dt = _time.perf_counter() - _t0
                try:
                    usage = getattr(resp, "usage", None) if resp is not None else None
                    prompt_tokens = getattr(usage, "prompt_tokens", None)
                    completion_tokens = getattr(usage, "completion_tokens", None)
                except Exception:
                    prompt_tokens = None
                    completion_tokens = None
                if _timer:
                    _timer.record_llm("summariser", _dt, tokens_in=prompt_tokens, tokens_out=completion_tokens, model=model)
                return json.loads(raw), raw

            # Pass 1: primary context only
            try:
                self._audit_llm_io = {
                    "model": self.model,
                    "passes": [
                        {"pass": 1, "prompt": prompt},
                    ],
                }
            except Exception:
                self._audit_llm_io = {}
            decision_dict: Dict[str, Any] = {}
            raw_1: str = ""
            chosen_model: str = self.model
            last_err: Optional[str] = None

            def _try_once(model_to_use: str) -> Tuple[Optional[Dict[str, Any]], str, Optional[str]]:
                try:
                    dd, rr = _call_llm(prompt_text=prompt, model=model_to_use)
                    if _is_low_quality_decision(dd):
                        return None, rr, "low_quality"
                    return dd, rr, None
                except Exception as e:
                    return None, "", f"exception:{e}"

            retries = max(0, int(getattr(self, "max_retries", 0) or 0))
            for attempt_idx in range(retries + 1):
                dd, rr, err = _try_once(self.model)
                if rr:
                    raw_1 = rr
                if dd is not None:
                    decision_dict = dd
                    chosen_model = self.model
                    last_err = None
                    break
                last_err = err
                if attempt_idx < retries:
                    print(
                        f"   ⚠️ [SUMMARISER] Low-quality summariser output on {self.model} "
                        f"(attempt {attempt_idx+1}/{retries+1}); retrying..."
                    )

            fb_model = getattr(self, "fallback_model", None)
            if (
                (not decision_dict or _is_low_quality_decision(decision_dict))
                and isinstance(fb_model, str)
                and fb_model
                and fb_model != self.model
            ):
                print(f"   ⚠️ [CHAIN] [SUMMARISER] Falling back to fallback model (reason: {last_err})")
                dd, rr, err = _try_once(fb_model)
                if rr:
                    raw_1 = rr
                if dd is not None:
                    decision_dict = dd
                    chosen_model = fb_model
                    last_err = None
                else:
                    last_err = err

            if not decision_dict or _is_low_quality_decision(decision_dict):
                print(
                    f"   ⚠️ [SUMMARISER] Summariser output unusable after retry/fallback "
                    f"(last_error={last_err}); continuing with deterministic fallbacks."
                )
                decision_dict = {}
            try:
                self._audit_llm_io["passes"][0]["raw_response_text"] = raw_1
                self._audit_llm_io["passes"][0]["parsed_json"] = decision_dict
                self._audit_llm_io["passes"][0]["model_used"] = chosen_model
            except Exception:
                pass

            # Pass 2 (optional): expand with secondary context only if requested
            if decision_dict.get("needs_more_context") is True:
                requested = decision_dict.get("requested_context") or []
                print(f"   🧠 [LLM_SECOND_PASS] Model requested more context: {requested}")

                secondary = f"""

SECONDARY CONTEXT (expanded):
Use this only if needed. You still must not invent tags/roles.

ALL TAG DELTAS (full; reference only):
{json.dumps(all_tag_deltas[:60], indent=2) if all_tag_deltas else "No tag deltas available"}

ALL ROLE DELTAS (full; reference only):
{json.dumps(all_role_deltas[:60], indent=2) if all_role_deltas else "No role deltas available"}

FULL NET TAG CHANGES:
Tags gained (net): {json.dumps(tags_gained_net_full[:60], indent=2) if tags_gained_net_full else "No net tags gained"}
Tags lost (net): {json.dumps(tags_lost_net_full[:60], indent=2) if tags_lost_net_full else "No net tags lost"}

FULL NET ROLE CHANGES:
Roles gained (net): {json.dumps(roles_gained_net_full[:60], indent=2) if roles_gained_net_full else "No net roles gained"}
Roles lost (net): {json.dumps(roles_lost_net_full[:60], indent=2) if roles_lost_net_full else "No net roles lost"}

FULL PGN WITH TAG/ROLE DELTAS:
{pgn_with_tag_deltas[:2500] if pgn_with_tag_deltas else "No PGN available"}
"""

                decision_dict_2, raw_2 = _call_llm(prompt + secondary, model=chosen_model)
                # If pass 2 regresses to a low-quality output, keep pass 1.
                if not _is_low_quality_decision(decision_dict_2):
                    decision_dict = decision_dict_2
                try:
                    if isinstance(self._audit_llm_io.get("passes"), list):
                        self._audit_llm_io["passes"].append(
                            {
                                "pass": 2,
                                "prompt": prompt + secondary,
                                "raw_response_text": raw_2,
                                "parsed_json": decision_dict,
                                "model_used": chosen_model,
                            }
                        )
                except Exception:
                    pass

            # Pass 3 (proofreader): hallucination check + rewrite based ONLY on deltas + significance.
            # This is intentionally case-agnostic. It exists to force reliance on tag/role/eval evidence.
            try:
                if self.llm_router and isinstance(decision_dict, dict) and decision_dict:
                    proofread_enabled = os.getenv("SUMMARISER_PROOFREADER_ENABLED", "true").lower().strip() == "true"
                else:
                    proofread_enabled = False
            except Exception:
                proofread_enabled = False

            # In relaxed mode, disable the proofreader pass (it strongly constrains style).
            if getattr(self, "relaxed_llm_mode", False):
                proofread_enabled = False

            if proofread_enabled:
                try:
                    def _cap_obj(obj: Any, max_chars: int) -> Any:
                        # Convert to JSON-ish string and truncate; keep as string for prompt safety.
                        try:
                            s = json.dumps(obj, ensure_ascii=False)
                        except Exception:
                            s = str(obj)
                        if not isinstance(s, str):
                            s = str(s)
                        if max_chars <= 0:
                            return ""
                        if len(s) <= max_chars:
                            return s
                        return s[:max_chars] + f"... <truncated {len(s) - max_chars} chars>"

                    evidence_packet = {
                        "evidence_eval": facts.get("evidence_eval") if isinstance(facts, dict) else {},
                        "tags_gained_net": tags_gained_net_for_prompt[:60],
                        "tags_lost_net": tags_lost_net_for_prompt[:60],
                        "roles_gained_net": roles_gained_net_for_prompt[:40],
                        "roles_lost_net": roles_lost_net_for_prompt[:40],
                        "significance": significance,
                    }

                    draft = {
                        "core_message": decision_dict.get("core_message"),
                        "mechanism": decision_dict.get("mechanism"),
                        "psychological_frame": decision_dict.get("psychological_frame"),
                        "selected_tags": decision_dict.get("selected_tags", []),
                        "claims": decision_dict.get("claims", []),
                        "emphasis": decision_dict.get("emphasis", []),
                        "verbosity": decision_dict.get("verbosity", None),
                    }

                    proofread_prompt = (
                        "You are a strict proofreader for chess explanations.\n"
                        "You receive ONLY evidence deltas + significance scores.\n"
                        "TASK: Identify hallucinations/unsupported claims in the draft (core_message/mechanism/claims)\n"
                        "and rewrite the draft so that EVERY statement is supported by the evidence packet.\n"
                        "\n"
                        "HARD RULES:\n"
                        "- Do NOT invent moves, tags, roles, evals, or tactics not present below.\n"
                        "- You may ONLY reference tags/roles that appear in tags_gained_net/tags_lost_net/roles_*.\n"
                        "- If the evidence_eval shows eval_delta near 0, do NOT claim big swings.\n"
                        "- If you cannot support a mechanism, rewrite it in terms of tags/roles/eval only.\n"
                        "- Significance outcomes are optional; use them only if they help.\n"
                        "\n"
                        "Return JSON with the SAME SHAPE as draft: {core_message, mechanism, psychological_frame, selected_tags, claims, emphasis, verbosity}.\n"
                    )

                    cmd = render_command(
                        command="PROOFREAD_SUMMARY",
                        input={
                            "evidence_packet": _cap_obj(evidence_packet, int(os.getenv("SUMMARISER_PROOFREADER_EVIDENCE_MAX_CHARS", "8000"))),
                            "draft": _cap_obj(draft, int(os.getenv("SUMMARISER_PROOFREADER_DRAFT_MAX_CHARS", "5000"))),
                        },
                        constraints={"json_only": True},
                    )

                    repaired = self.llm_router.complete_json(
                        session_id=session_id or "default",
                        stage="summariser_proofread",
                        system_prompt=MIN_SYSTEM_PROMPT_V1,
                        task_seed=SUMMARISER_CONTRACT_V1,
                        user_text=cmd,
                        model=chosen_model,
                        max_tokens=int(os.getenv("SUMMARISER_PROOFREADER_MAX_TOKENS", "900")),
                    )

                    if isinstance(repaired, dict) and not _is_low_quality_decision(repaired):
                        decision_dict = repaired
                        try:
                            if isinstance(self._audit_llm_io.get("passes"), list):
                                self._audit_llm_io["passes"].append(
                                    {
                                        "pass": 3,
                                        "prompt": proofread_prompt,
                                        "parsed_json": decision_dict,
                                        "model_used": chosen_model,
                                        "stage": "summariser_proofread",
                                    }
                                )
                        except Exception:
                            pass
                except Exception as _proof_e:
                    print(f"   ⚠️ [SUMMARISER] Proofreader pass failed (non-fatal): {_proof_e}")
            
            # Extract LLM-generated values
            llm_core_message = decision_dict.get("core_message")
            llm_psychological_frame = decision_dict.get("psychological_frame")
            llm_mechanism = decision_dict.get("mechanism")
            llm_selected_tags = decision_dict.get("selected_tags", [])
            llm_claims = decision_dict.get("claims", [])
            
            # Use LLM-generated values, with fallback to deterministic if missing.
            # IMPORTANT: `investigation_result` can be either an InvestigationResult OR a dict (comparison bundle).
            # Never assume attribute access exists on the dict form.
            fallback_core_msg = "Analysis complete"
            if isinstance(investigation_result, InvestigationResult):
                fallback_core_msg = f"Analysis of {getattr(investigation_result, 'player_move', None) or 'position'}"
            elif isinstance(investigation_result, dict) and investigation_result.get("multiple_results"):
                fallback_core_msg = "Comparison of moves"
            
            final_core_message = llm_core_message or fallback_core_msg
            final_psychological_frame = llm_psychological_frame or (fallback_psychological_frame if 'fallback_psychological_frame' in locals() else (dominant_frame if 'dominant_frame' in locals() else "reasonable idea, wrong moment"))
            
            # Use LLM-generated mechanism (with fallback)
            # For comparison mode, use dominant_mechanism as fallback if available
            comparison_fallback_mechanism = dominant_mechanism if 'dominant_mechanism' in locals() else None
            final_mechanism = llm_mechanism or fallback_mechanism or comparison_fallback_mechanism or "changes the position in a way that affects your goal"

            # NOTE: We intentionally avoid case-specific heuristic rewrites here.
            # Hallucination repair is handled by an explicit proofreader pass that sees only evidence deltas.
            
            # Use LLM-selected tags (small), but compute suppression deterministically to avoid huge LLM outputs.
            tag_universe = []
            try:
                tag_universe = sorted(set([t for t in (tags_gained_net_full or []) + (tags_lost_net_full or []) if isinstance(t, str) and t]))
            except Exception:
                tag_universe = []

            selected_tags_for_evidence = []
            try:
                if isinstance(llm_selected_tags, list):
                    selected_tags_for_evidence = [t for t in llm_selected_tags if isinstance(t, str) and t in set(tag_universe)]
            except Exception:
                selected_tags_for_evidence = []
            selected_tags_for_evidence = selected_tags_for_evidence[:5]

            suppressed_tags_combined = [t for t in tag_universe if t not in set(selected_tags_for_evidence)]

            # Roles are optional; do not require/emit them from the LLM.
            role_universe = []
            try:
                role_universe = sorted(set([r for r in (roles_gained_net_full or []) + (roles_lost_net_full or []) if isinstance(r, str) and r]))
            except Exception:
                role_universe = []
            selected_roles_for_evidence = []
            suppressed_roles_combined = [r for r in role_universe if r not in set(selected_roles_for_evidence)]

            # Derive PGN sequences to extract deterministically from claim evidence (keeps LLM output small).
            pgn_sequences_to_extract: List[Dict[str, Any]] = []
            try:
                if isinstance(llm_claims, list):
                    seen = set()
                    for c in llm_claims:
                        if not isinstance(c, dict):
                            continue
                        seq = c.get("evidence_moves") or []
                        if not (isinstance(seq, list) and len(seq) >= 2):
                            continue
                        seq_clean = tuple([m for m in seq if isinstance(m, str) and m][:4])
                        if len(seq_clean) < 2 or seq_clean in seen:
                            continue
                        seen.add(seq_clean)
                        pgn_sequences_to_extract.append({
                            "start_move": seq_clean[0],
                            "end_move": seq_clean[-1],
                        })
                        if len(pgn_sequences_to_extract) >= 3:
                            break
            except Exception:
                pgn_sequences_to_extract = []
            
            # STRICT OUTPUT VALIDATION: Enforce contract
            emphasis_list = decision_dict.get("emphasis", [])
            if len(emphasis_list) > 2:
                emphasis_list = emphasis_list[:2]  # Enforce max 2 items
            
            # NEW: Curate PGN using LLM-selected sequences if available
            refined_pgn = None
            result_for_pgn = None
            
            # Handle both single result and comparison mode
            if isinstance(investigation_result, InvestigationResult):
                result_for_pgn = investigation_result
            elif isinstance(investigation_result, dict) and investigation_result.get("multiple_results"):
                # Comparison mode: use first result for PGN curation
                multiple_results = investigation_result.get("multiple_results", [])
                if multiple_results and len(multiple_results) > 0:
                    first_item = multiple_results[0]
                    result_for_pgn = first_item.get("result")
            
            if result_for_pgn and isinstance(result_for_pgn, InvestigationResult):
                if result_for_pgn.pgn_exploration and result_for_pgn.exploration_tree and execution_plan:
                    try:
                        # Create temporary NarrativeDecision with pgn_sequences_to_extract
                        temp_decision = NarrativeDecision(
                            core_message=final_core_message,
                            mechanism=final_mechanism,
                            psychological_frame=final_psychological_frame,
                            pgn_sequences_to_extract=pgn_sequences_to_extract,
                            discussion_agenda=discussion_agenda
                        )
                        refined_pgn = await self.curate_pgn(
                            result_for_pgn, 
                            execution_plan,
                            narrative_decision=temp_decision
                        )
                    except Exception as e:
                        print(f"   ⚠️ PGN curation error: {e}")
                        import traceback
                        traceback.print_exc()
            
            # Use LLM-suppressed tags
            suppress_list = suppressed_tags_combined[:20]  # Limit to 20 for performance
            
            # Get mechanism evidence (use fallback if available, otherwise try to bind from LLM mechanism)
            final_mechanism_evidence = fallback_mechanism_evidence if 'fallback_mechanism_evidence' in locals() else None
            # For comparison mode, also check dominant_mechanism_evidence
            if not final_mechanism_evidence and 'selected_mechanism_evidence' in locals():
                final_mechanism_evidence = selected_mechanism_evidence
            if not final_mechanism_evidence and llm_mechanism:
                # Try to bind evidence for LLM-generated mechanism
                # Use fallback evidence binding logic
                final_mechanism_evidence = {
                    "type": "llm_generated",
                    "source": "consequences_and_tags",
                    "verified": True
                }
            
            # Create Claim objects from LLM-generated claims
            # Debug: confirm whether we are taking the LLM-claims path or falling back
            print(f"   🔎 [LLM_CLAIMS_CHECK] llm_claims truthy: {bool(llm_claims)}")
            print(f"      - llm_claims type: {type(llm_claims).__name__}")
            if isinstance(llm_claims, list):
                print(f"      - llm_claims length: {len(llm_claims)}")
                if llm_claims and isinstance(llm_claims[0], dict):
                    print(f"      - first claim keys: {list(llm_claims[0].keys())}")
                    # Net tag/role lists are canonical; there is no separate "key_evidence" contract.
            elif llm_claims is not None:
                # Unexpected type; still show a preview
                try:
                    print(f"      - llm_claims preview: {str(llm_claims)[:300]}")
                except Exception:
                    pass
            claims = []
            if llm_claims:
                # Convert LLM-generated claims to Claim objects
                for llm_claim_data in llm_claims:
                    summary = llm_claim_data.get("summary", "")
                    claim_type = llm_claim_data.get("claim_type", "general")
                    connector = llm_claim_data.get("connector")
                    evidence_moves = llm_claim_data.get("evidence_moves", [])
                    
                    if not summary:
                        continue
                    
                    # Create Claim object
                    claim = Claim(
                        summary=summary,
                        claim_type=claim_type,
                        connector=connector if connector and connector != "None" else None,
                        evidence_moves=evidence_moves if evidence_moves else None,
                        evidence_source="llm_generated" if evidence_moves else None
                    )
                    # Trace: mark origin so we can distinguish LLM-created claims from fallback/bound claims
                    claim._origin = "llm_claims"
                    
                    # Bind evidence if moves provided
                    result_for_evidence = investigation_result
                    if is_comparison and isinstance(investigation_result, dict):
                        # For comparison mode, bind each claim to the correct candidate result
                        # (otherwise all claims get overwritten by the primary line).
                        multiple_results = investigation_result.get("multiple_results", []) or []
                        result_for_evidence = self._pick_result_for_claim_in_comparison(
                            claim=claim,
                            multiple_results=multiple_results if isinstance(multiple_results, list) else [],
                            default_result=primary_result_for_evidence if isinstance(primary_result_for_evidence, InvestigationResult) else None,
                        )
                    
                    if evidence_moves and isinstance(result_for_evidence, InvestigationResult):
                        # Attach rich evidence payload
                        self._attach_rich_evidence(
                            claim,
                            result_for_evidence,
                            want_pgn_line=True,
                            want_tags=True,
                            want_two_move=False
                        )
                        
                        # Validate and potentially reword claim against evidence
                        validated_claim = self._validate_claim_against_evidence(claim, result_for_evidence)
                        if validated_claim:
                            claim = validated_claim
                    
                    claims.append(claim)

            # Enforce: don't keep multiple claims that attach to the exact same evidence line.
            # First canonicalize by semantic summary, then dedupe strictly by evidence line.
            claims = self._canonicalize_claims(claims)
            claims = self._dedupe_claims_one_per_evidence_line(claims)

            # Enforce minimal agenda coverage for suggestion-style queries.
            if is_comparison and isinstance(investigation_result, dict):
                mr = investigation_result.get("multiple_results", []) or []
                claims = self._ensure_agenda_coverage_claims(
                    claims=claims,
                    execution_plan=execution_plan,
                    multiple_results=mr if isinstance(mr, list) else [],
                    primary_result_for_evidence=primary_result_for_evidence if isinstance(primary_result_for_evidence, InvestigationResult) else None,
                    force_suggestion=bool(force_suggestion),
                )

            # Suggestion-mode safety: Add a deterministic recommendation claim at the front,
            # but DO NOT drop other claims (they may cover tactics/nuance the user asked for).
            # The only hard rule: no claim summary should mention a different first move than its evidence.
            if bool(force_suggestion):
                try:
                    # Choose a canonical recommendation line from the investigator output.
                    inv_for_rec = primary_result_for_evidence if isinstance(primary_result_for_evidence, InvestigationResult) else None
                    if inv_for_rec is None and isinstance(investigation_result, InvestigationResult):
                        inv_for_rec = investigation_result

                    if isinstance(inv_for_rec, InvestigationResult):
                        # CRITICAL: Use best_move_d16 (SAN) as the canonical first move, not pv[0]
                        # This ensures the recommendation always matches the engine's best move.
                        best_move_san = getattr(inv_for_rec, "best_move_d16", None)
                        if not isinstance(best_move_san, str) or not best_move_san.strip():
                            # Fallback: try to convert best_move (UCI) to SAN if available
                            best_move_uci = getattr(inv_for_rec, "best_move", None)
                            if isinstance(best_move_uci, str) and best_move_uci.strip():
                                try:
                                    import chess
                                    board = chess.Board(getattr(inv_for_rec, "evidence_starting_fen", None) or getattr(inv_for_rec, "starting_fen", None) or "")
                                    move_obj = chess.Move.from_uci(best_move_uci)
                                    if move_obj in board.legal_moves:
                                        best_move_san = board.san(move_obj)
                                except Exception:
                                    pass
                        
                        # Get the PV (may start with a different move, we'll fix that)
                        pv_raw = getattr(inv_for_rec, "evidence_main_line_moves", None) or getattr(inv_for_rec, "pv_after_move", None) or []
                        if not isinstance(pv_raw, list):
                            pv_raw = []
                        pv_raw = [m for m in pv_raw if isinstance(m, str) and m.strip()]
                        
                        # If we have a best_move_san, ensure PV starts with it
                        if best_move_san and best_move_san.strip():
                            rec_move = best_move_san.strip()
                            # Only use PV if it starts with best_move_san (otherwise it's from a different line)
                            if pv_raw and pv_raw[0] == rec_move:
                                # PV is valid, use it
                                pv = pv_raw[:6]
                            else:
                                # PV doesn't start with best_move, use just the best move
                                # (evidence will be computed by _attach_rich_evidence)
                                pv = [rec_move]
                        elif pv_raw:
                            # No best_move_san available, fall back to pv[0]
                            rec_move = pv_raw[0]
                            pv = pv_raw[:6]
                        else:
                            rec_move = None
                            pv = []
                        
                        if rec_move:
                            # Build a deterministic recommendation claim and put it first.
                            rec_claim = Claim(
                                summary=f"Play {rec_move}.",
                                claim_type="recommendation",
                                connector=None,
                                evidence_moves=pv,
                                evidence_source="pv",
                            )
                            rec_claim._origin = "deterministic_recommendation"
                            rec_claim.hints = RenderHints(role="detail", priority=1, inline_pgn=True, show_board=True)
                            try:
                                self._attach_rich_evidence(rec_claim, inv_for_rec, want_pgn_line=True, want_tags=True, want_two_move=False)
                            except Exception:
                                pass

                            # Keep existing claims; just prepend rec_claim if not already present.
                            already = any(getattr(c, "_origin", "") == "deterministic_recommendation" for c in claims)
                            if not already:
                                claims = [rec_claim] + claims
                except Exception:
                    pass
            
            # FALLBACK: If LLM didn't generate claims, use deterministic creation
            if not claims:
                print(f"   ⚠️ [SUMMARISER] LLM didn't generate claims, using fallback deterministic creation")
                if is_comparison:
                    # For comparison mode, create comparison claims that recommend the better move
                    multiple_results = investigation_result.get("multiple_results", [])
                    claims = self._create_comparison_claims(multiple_results, fallback_primary_narrative, final_mechanism)
                else:
                    # Single result mode
                    if isinstance(investigation_result, InvestigationResult):
                        claims = self._create_claims_from_facts(
                            investigation_result,
                            fallback_primary_narrative,
                            final_mechanism
                        )
                        # Validate fallback claims against evidence
                        validated_claims = []
                        for claim in claims:
                            if claim.evidence_moves:
                                validated_claim = self._validate_claim_against_evidence(claim, investigation_result)
                                validated_claims.append(validated_claim if validated_claim else claim)
                            else:
                                validated_claims.append(claim)
                        claims = validated_claims
                    else:
                        claims = []

            # Single-source claims: If LLM produced claims, do NOT synthesize extra deterministic claims
            # (hammer synthesis / mechanism anchor are skipped below in that case).
            llm_claims_used = bool(claims) and bool(llm_claims)
            
            # Create takeaway as Claim object (non-causal by default, unless evidence available)
            takeaway_text = decision_dict.get("takeaway")
            takeaway_claim = None
            if takeaway_text:
                # Get investigation result for evidence binding (handle comparison mode)
                result_for_takeaway = investigation_result
                if is_comparison:
                    multiple_results = investigation_result.get("multiple_results", [])
                    if multiple_results and len(multiple_results) > 0:
                        result_for_takeaway = multiple_results[0].get("result")
                
                if isinstance(result_for_takeaway, InvestigationResult):
                    # Attempt to bind evidence for takeaway (generic approach)
                    takeaway_claim = self._bind_evidence_to_claim(
                        summary=takeaway_text,
                        connector=None,  # Start non-causal
                        claim_type="takeaway",
                        investigation_result=result_for_takeaway
                    )
                    # Trace: mark explicit origin (helps debug duplicates vs LLM claims)
                    takeaway_claim._origin = "takeaway_bind_evidence"
                    # Attach rendering hints + referential evidence payload
                    takeaway_claim.hints = RenderHints(role="takeaway", priority=2, inline_pgn=False)
                    self._attach_rich_evidence(
                        takeaway_claim,
                        result_for_takeaway,
                        want_pgn_line=True,
                        want_tags=True,
                        want_two_move=bool(getattr(result_for_takeaway, "two_move_tactics", None))
                    )
                    # If evidence found, upgrade to causal
                    if takeaway_claim.evidence_moves:
                        # Determine appropriate connector based on takeaway content (generic)
                        if "avoid" in takeaway_text.lower() or "prevent" in takeaway_text.lower():
                            takeaway_claim.connector = "allows"
                        elif "leads" in takeaway_text.lower():
                            takeaway_claim.connector = "leads_to"
                        # If no generic match, keep non-causal
            
            # Use LLM-generated core_message (with fallback if missing).
            # If it is missing or equals the deterministic fallback, generate from claims.
            if not final_core_message or final_core_message == fallback_core_msg:
                core_message_parts = [claim.summary for claim in claims[:2]]  # Use first 2 claims
                if core_message_parts:
                    final_core_message = ". ".join(core_message_parts) + "."
                else:
                    final_core_message = fallback_primary_narrative if fallback_primary_narrative else "Analysis complete"
            
            # Override "brief" verbosity to "medium" - brief is too short for good explanations
            llm_verbosity = decision_dict.get("verbosity", "medium")
            if llm_verbosity == "brief":
                llm_verbosity = "medium"
                print(f"   🔧 [VERBOSITY_OVERRIDE] LLM chose 'brief', overriding to 'medium' for better explanation quality")
            
            narrative_decision = NarrativeDecision(
                core_message=final_core_message,  # LLM-generated (with fallback)
                mechanism=final_mechanism,  # Mandatory
                mechanism_evidence=final_mechanism_evidence,  # Evidence linking mechanism to source
                claims=claims,  # Evidence-locked claims (primary output)
                emphasis=emphasis_list,  # Enforced max 2
                psychological_frame=final_psychological_frame,  # LLM-generated (with fallback)
                takeaway=takeaway_claim,  # Takeaway as Claim object
                verbosity=llm_verbosity,
                suppress=suppress_list,  # Code-enforced
                refined_pgn=refined_pgn,
                pgn_sequences_to_extract=pgn_sequences_to_extract,  # LLM-selected sequences
                # NEW: pass through worded/original PGN context so Explainer can use it too
                worded_pgn=worded_pgn,
                original_pgn_context=original_pgn_context,
                discussion_agenda=discussion_agenda,  # Pass agenda to explainer
            )

            # Attach deterministic pattern summary from baseline_intuition motifs (if available).
            try:
                baseline = (context or {}).get("baseline_intuition") if isinstance(context, dict) else None
                scan_root = baseline.get("scan_root") if isinstance(baseline, dict) else None
                motifs = scan_root.get("motifs") if isinstance(scan_root, dict) else None
                pattern_summary, patterns_top = self._build_pattern_summary_from_motifs(motifs, top_n=6)
                narrative_decision.pattern_summary = pattern_summary
                narrative_decision.patterns_top = patterns_top
                # Also emit patterns in claim-like format for the UI Evidence panel.
                pattern_claims: List[Dict[str, Any]] = []
                if isinstance(motifs, list):
                    for m in [x for x in motifs if isinstance(x, dict)][:10]:
                        loc = m.get("location") if isinstance(m.get("location"), dict) else {}
                        ct = (loc.get("count_total") if isinstance(loc, dict) else None) or m.get("count_total") or 0
                        cls = m.get("classification") or m.get("class") or "pattern"
                        sig = ((m.get("pattern") or {}) if isinstance(m.get("pattern"), dict) else {}).get("signature") or m.get("signature") or ""

                        # Prefer the first example window if present.
                        moves: List[str] = []
                        exs = m.get("examples_san") or []
                        if isinstance(exs, list) and exs:
                            ex0 = exs[0] if isinstance(exs[0], dict) else None
                            mv0 = (ex0 or {}).get("moves_san") if isinstance(ex0, dict) else None
                            if isinstance(mv0, list):
                                moves = [mm for mm in mv0 if isinstance(mm, str) and mm.strip()]
                        # Fallback: parse SAN tokens from motif signature.
                        if not moves and isinstance(sig, str) and sig:
                            try:
                                import re as _re
                                moves = _re.findall(r"SAN:([A-Za-z0-9O+=#\\-]+)", sig)[:6]
                            except Exception:
                                moves = []

                        stats = m.get("eval_stats") if isinstance(m.get("eval_stats"), dict) else {}
                        tag_role = m.get("tag_role_deltas") if isinstance(m.get("tag_role_deltas"), dict) else {}
                        # Human-ish one-liner, avoid tag/role leakage by using our sanitized summary builder.
                        one = self._build_pattern_summary_from_motifs([m], top_n=1)[0] or ""
                        line = one.split("\n")[-1].strip() if isinstance(one, str) else ""
                        if line.startswith("-"):
                            line = line.lstrip("-").strip()
                        # Avoid duplicating "(seen X×)" / "[class]" if the line already contains it.
                        summary = line or "Pattern"

                        pattern_claims.append({
                            "summary": summary,
                            "claim_type": "pattern",
                            "connector": None,
                            "evidence_moves": moves[:6] if moves else None,
                            "evidence_source": "motif_miner",
                            "evidence_payload": {
                                "pgn_moves": moves,
                                "pgn_line": " ".join(moves) if moves else None,
                                "evidence_eval_start": stats.get("avg_eval_start"),
                                "evidence_eval_end": stats.get("avg_eval_end"),
                                "evidence_eval_delta": stats.get("avg_eval_delta"),
                                "evidence_material_start": stats.get("avg_material_start"),
                                "evidence_material_end": stats.get("avg_material_end"),
                                "evidence_positional_start": stats.get("avg_positional_start"),
                                "evidence_positional_end": stats.get("avg_positional_end"),
                                "tags_gained_net": tag_role.get("tags_gained_net") if isinstance(tag_role.get("tags_gained_net"), list) else [],
                                "tags_lost_net": tag_role.get("tags_lost_net") if isinstance(tag_role.get("tags_lost_net"), list) else [],
                                "roles_gained_net": tag_role.get("roles_gained_net") if isinstance(tag_role.get("roles_gained_net"), list) else [],
                                "roles_lost_net": tag_role.get("roles_lost_net") if isinstance(tag_role.get("roles_lost_net"), list) else [],
                                "tags_gained_net_structured": tag_role.get("tags_gained_net_structured") if isinstance(tag_role.get("tags_gained_net_structured"), list) else [],
                                "tags_lost_net_structured": tag_role.get("tags_lost_net_structured") if isinstance(tag_role.get("tags_lost_net_structured"), list) else [],
                                "key_eval_breakdown": {
                                    "material_balance": {"start": stats.get("avg_material_start"), "end": stats.get("avg_material_end")},
                                    "positional_balance": {"start": stats.get("avg_positional_start"), "end": stats.get("avg_positional_end")},
                                    "total_eval": {"start": stats.get("avg_eval_start"), "end": stats.get("avg_eval_end"), "delta": stats.get("avg_eval_delta")},
                                    "n_samples": stats.get("n_samples"),
                                },
                                "motif_meta": {
                                    "signature": sig,
                                    "count_total": int(ct),
                                    "classification": cls,
                                    "significance": m.get("significance"),
                                },
                            },
                            "hints": {"role": "pattern", "priority": 2, "inline_pgn": True, "show_board": False},
                        })
                narrative_decision.pattern_claims = pattern_claims
            except Exception:
                narrative_decision.pattern_summary = None
                narrative_decision.patterns_top = []
                narrative_decision.pattern_claims = []

            # NEW: Mandatory Hammer Claim Enforcement
            # If the primary narrative is non-trivial, we MUST have at least one causal claim with evidence
            primary_narrative_lower = fallback_primary_narrative.lower() if fallback_primary_narrative else ""
            is_trivial = "neutral_improvement" in primary_narrative_lower or not fallback_primary_narrative
            
            if (not getattr(self, "relaxed_llm_mode", False)) and (not is_trivial) and (not llm_claims_used):
                # Check if we have a qualifying hammer claim
                has_hammer_claim = any(
                    c.connector is not None 
                    and c.evidence_moves is not None 
                    and len(c.evidence_moves) >= 2
                    for c in narrative_decision.claims
                )
                
                if not has_hammer_claim:
                    # Attempt to synthesize a hammer claim from mechanism/consequences/tags
                    hammer_claim = self._synthesize_hammer_claim(
                        investigation_result=primary_result_for_evidence,
                        mechanism=final_mechanism,
                        # Consequences removed
                        selected_tag_deltas=selected_tags_for_evidence,
                        is_comparison=is_comparison
                    )
                    
                    if hammer_claim and hammer_claim.connector and hammer_claim.evidence_moves:
                        # Re-attach evidence payload (net tag/role changes are canonical).
                        if isinstance(primary_result_for_evidence, InvestigationResult):
                            try:
                                self._attach_rich_evidence(
                                    hammer_claim,
                                    primary_result_for_evidence,
                                    want_pgn_line=True,
                                    want_tags=True,
                                    want_two_move=False
                                )
                            except Exception:
                                pass  # Non-critical
                        # Successfully synthesized hammer claim
                        narrative_decision.claims.insert(0, hammer_claim)  # Insert at front for priority
                        print(f"   🔨 [HAMMER] Auto-generated hammer claim: {hammer_claim.summary[:60]}... [{hammer_claim.connector}]")
                    else:
                        # Evidence binding failed - suppress causal language but keep medium verbosity
                        # (Don't downgrade to brief - brief is too short for good explanations)
                        # narrative_decision.verbosity = "brief"  # REMOVED - keep medium verbosity
                        # Remove all causal connectors from existing claims
                        for claim in narrative_decision.claims:
                            if claim.connector:
                                claim.connector = None
                                claim.evidence_source = None
                        if narrative_decision.takeaway and narrative_decision.takeaway.connector:
                            narrative_decision.takeaway.connector = None
                            narrative_decision.takeaway.evidence_source = None
                        print(f"   ⚠️ [HAMMER] No board-verifiable causal chain found; forcing non-causal explanation.")
            
            # NEW: Mechanism Anchoring Validation
            # If mechanism is set, at least one Claim MUST explicitly reference it
            if (not getattr(self, "relaxed_llm_mode", False)) and (
                final_mechanism
                and final_mechanism != "changes the position in a way that affects your goal"
                and (not llm_claims_used)
            ):
                mechanism_referenced = any(
                    final_mechanism.lower() in c.summary.lower() 
                    or any(part in c.summary.lower() for part in final_mechanism.lower().split() if len(part) > 4)
                    for c in narrative_decision.claims
                )
                
                if not mechanism_referenced:
                    # Create a non-causal claim that restates the mechanism
                    # Handle mechanisms that already start with "This is" or similar
                    mechanism_lower = final_mechanism.lower()
                    if mechanism_lower.startswith("this is") or mechanism_lower.startswith("this position"):
                        # Use mechanism as-is, don't prepend "This move"
                        mechanism_summary = final_mechanism
                    elif mechanism_lower.startswith("this move"):
                        # Already has "This move", use as-is
                        mechanism_summary = final_mechanism
                    else:
                        # Prepend "This move" for other mechanisms
                        mechanism_summary = f"This move {final_mechanism}"
                    
                    mechanism_claim = Claim(
                        summary=mechanism_summary,
                        claim_type="mechanism_anchor",
                        connector=None,  # Non-causal anchor
                        evidence_moves=None,
                        evidence_source=None
                    )
                    mechanism_claim.hints = RenderHints(role="mechanism", priority=2, inline_pgn=False)
                    
                    # Attach rich evidence payload even though it's non-causal
                    # Use the first available investigation result for evidence
                    result_for_mechanism = primary_result_for_evidence
                    
                    if isinstance(result_for_mechanism, InvestigationResult):
                        try:
                            self._attach_rich_evidence(
                                mechanism_claim,
                                result_for_mechanism,
                                want_pgn_line=True,
                                want_tags=True,
                                want_two_move=False
                            )
                        except Exception as e:
                            print(f"   ⚠️ [MECHANISM] Failed to attach evidence to mechanism anchor: {e}")
                    
                    narrative_decision.claims.append(mechanism_claim)
                    print(f"   📌 [MECHANISM] Added mechanism anchor claim: {mechanism_summary[:60]}...")

            # Canonicalize claims to remove duplicates across pathways (LLM vs bind_evidence vs hammer, etc.)
            try:
                narrative_decision.claims = self._canonicalize_claims(narrative_decision.claims or [])
            except Exception as e:
                print(f"   ⚠️ [CLAIM_CANON] Failed to canonicalize claims: {e}")

            # NEW: Pre-cooked clause template for Explainer (goal-anchored, evidence-locked)
            try:
                narrative_decision.explainer_template = self._build_explainer_template(
                    narrative_decision=narrative_decision,
                    user_message=user_message or ""
                )
            except Exception:
                narrative_decision.explainer_template = None
            
            # LOG OUTPUT
            print(f"\n{'='*80}")
            print(f"✅ [SUMMARISER] OUTPUT:")
            print(f"   Core Message: {narrative_decision.core_message}")
            print(f"   Mechanism: {narrative_decision.mechanism}")
            print(f"   Claims: {len(narrative_decision.claims)} claim(s)")
            # Log claim statistics
            causal_count = sum(1 for c in narrative_decision.claims if c.connector is not None)
            evidence_count = sum(1 for c in narrative_decision.claims if c.evidence_moves is not None)
            downgraded_count = sum(1 for c in narrative_decision.claims if c.connector is None and c.summary)
            
            print(f"   Claims: {len(narrative_decision.claims)} total")
            print(f"      - Causal claims: {causal_count}")
            print(f"      - Claims with evidence: {evidence_count}")
            print(f"      - Downgraded claims: {downgraded_count}")
            
            for i, claim in enumerate(narrative_decision.claims):
                if claim.connector and claim.evidence_moves:
                    print(f"      Claim {i+1} ({claim.claim_type}): {claim.summary[:50]}... [{claim.connector}] with evidence: {' '.join(claim.evidence_moves[:2])}")
                else:
                    print(f"      Claim {i+1} ({claim.claim_type}): {claim.summary[:50]}... (non-causal)")
            
            # Log evidence sources used
            evidence_sources = set(c.evidence_source for c in narrative_decision.claims if c.evidence_source)
            if evidence_sources:
                print(f"   Evidence sources used: {', '.join(evidence_sources)}")
            
            print(f"   Emphasis: {narrative_decision.emphasis}")
            print(f"   Psychological Frame: {narrative_decision.psychological_frame}")
            if narrative_decision.takeaway:
                if narrative_decision.takeaway.connector and narrative_decision.takeaway.evidence_moves:
                    print(f"   Takeaway: {narrative_decision.takeaway.summary[:50]}... [{narrative_decision.takeaway.connector}] with evidence")
                else:
                    print(f"   Takeaway: {narrative_decision.takeaway.summary[:50]}... (non-causal)")
            print(f"   Verbosity: {narrative_decision.verbosity}")
            print(f"   Suppress: {narrative_decision.suppress}")
            if narrative_decision.refined_pgn:
                print(f"   Refined PGN Length: {len(narrative_decision.refined_pgn.pgn) if narrative_decision.refined_pgn.pgn else 0} chars")
                print(f"   Refined PGN Themes: {narrative_decision.refined_pgn.themes}")
            print(f"{'='*80}\n")
            sys.stdout.flush()
            
            return narrative_decision
        except Exception as e:
            # Fallback decision
            print(f"   ❌ [SUMMARISER] EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            print(f"   ⚠️ [SUMMARISER] Returning fallback NarrativeDecision due to exception")
            # Extract discussion_agenda from execution_plan if available (fallback case)
            discussion_agenda = []
            if execution_plan and hasattr(execution_plan, "discussion_agenda"):
                discussion_agenda = execution_plan.discussion_agenda or []
            
            return NarrativeDecision(
                core_message="Analysis complete",
                mechanism="changes the position in a way that affects your goal",
                mechanism_evidence=None,
                emphasis=[],
                verbosity="medium",
                refined_pgn=None,
                discussion_agenda=discussion_agenda,
                original_pgn_context=(
                    self._build_original_pgn_context(investigation_result)
                    if isinstance(investigation_result, InvestigationResult)
                    else None
                ),
            )
    
    def _extract_pgn_sequences_by_tag_changes(
        self,
        inv: InvestigationResult,
        sequences_to_extract: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extract specific PGN sequences that prove a narrative point.
        
        Looks for sequences where meaningful tag changes occur:
        - Captures → doubled pawns
        - Moves → lose castling rights
        - Sequences that show position improvement/deterioration
        
        Args:
            inv: InvestigationResult (prefer structured deltas, avoid PGN regex parsing)
            sequences_to_extract: List of {start_move, end_move, reason, proves} from LLM
            
        Returns:
            List of extracted PGN sequences with annotations
        """
        sequences = []
        
        if not sequences_to_extract:
            return sequences

        # Prefer Investigator structured deltas (single main evidence line).
        per_move = getattr(inv, "evidence_per_move_deltas", None)
        if not isinstance(per_move, list) or not per_move:
            # Backward compat: if structured not present, do nothing (caller will fall back to scoring)
            return sequences

        def _meaningful(tags_gained: List[str], tags_lost: List[str]) -> List[str]:
            out: List[str] = []
            for tag in (tags_gained or []):
                tl = tag.lower()
                if any(k in tl for k in ["doubled_pawn", "castling", "king", "pawn_structure", "pawn", "trapped", "pinned", "fork", "hanging", "overworked"]):
                    out.append(f"gained: {tag}")
            for tag in (tags_lost or []):
                tl = tag.lower()
                if any(k in tl for k in ["castling", "king", "pawn_structure", "pawn", "trapped", "pinned", "fork", "hanging", "overworked"]):
                    out.append(f"lost: {tag}")
            return out

        # For each requested sequence, find it within the main evidence line deltas
        for seq_request in sequences_to_extract:
            start_move = seq_request.get("start_move")
            end_move = seq_request.get("end_move")
            reason = seq_request.get("reason", "")
            proves = seq_request.get("proves", "")
            if not start_move:
                continue

            found_start = False
            sequence_moves: List[Dict[str, Any]] = []
            for d in per_move:
                mv = d.get("move")
                if mv == start_move:
                    found_start = True
                if not found_start:
                    continue

                tg = d.get("tags_gained", []) or []
                tl = d.get("tags_lost", []) or []
                move_entry = {
                    "move": mv,
                    "tags_gained": tg,
                    "tags_lost": tl,
                    "comment": ""  # structured deltas don't carry PGN comments
                }
                m = _meaningful(tg, tl)
                if m:
                    move_entry["meaningful_tags"] = m
                sequence_moves.append(move_entry)

                if end_move and mv == end_move:
                    break

            if sequence_moves:
                sequences.append({
                    "moves": sequence_moves,
                    "reason": reason,
                    "proves": proves,
                    "start_move": start_move,
                    "end_move": end_move
                })
        
        return sequences
    
    async def curate_pgn(
        self,
        investigation_result: InvestigationResult,
        execution_plan: Any,  # ExecutionPlan (using Any to avoid circular import)
        narrative_decision: Optional[NarrativeDecision] = None  # NEW: Pass narrative decision with pgn_sequences_to_extract
    ) -> RefinedPGN:
        """
        Curate PGN by extracting sequences that prove the narrative.
        
        NEW: Uses LLM-selected sequences from narrative_decision instead of scoring branches.
        Falls back to old scoring method if no sequences provided.
        """
        # Step 1: Extract moves of interest from execution plan
        moves_of_interest = []
        focus_areas = []
        
        if execution_plan and hasattr(execution_plan, 'steps'):
            for step in execution_plan.steps:
                if step.action_type == "investigate_move":
                    move_san = step.parameters.get("move_san")
                    if move_san:
                        moves_of_interest.append(move_san)
                elif step.action_type == "investigate_position":
                    focus = step.parameters.get("focus")
                    if focus:
                        focus_areas.append(focus)
        
        # NEW: Check if we have LLM-selected sequences
        if narrative_decision and narrative_decision.pgn_sequences_to_extract:
            sequences_to_extract = narrative_decision.pgn_sequences_to_extract
            print(f"   📋 [PGN_CURATION] Using LLM-selected sequences: {len(sequences_to_extract)} sequences")
            
            # Extract sequences based on tag changes
            extracted_sequences = self._extract_pgn_sequences_by_tag_changes(
                investigation_result,
                sequences_to_extract
            )
            
            if extracted_sequences:
                # Build refined PGN from extracted sequences
                refined_pgn_str = self._build_pgn_from_sequences(
                    investigation_result,
                    extracted_sequences
                )
                
                # Extract themes from sequences
                all_themes = set()
                for seq in extracted_sequences:
                    for move_data in seq.get("moves", []):
                        # Extract themes from meaningful tags
                        for tag in move_data.get("meaningful_tags", []):
                            if "doubled_pawn" in tag.lower():
                                all_themes.add("pawn_structure")
                            if "castling" in tag.lower():
                                all_themes.add("king_safety")
                
                return RefinedPGN(
                    pgn=refined_pgn_str,
                    key_branches=[],  # Not using branch metadata for LLM-selected sequences
                    themes=list(all_themes)[:10],
                    tactical_highlights=[],
                    moves_of_interest=moves_of_interest
                )
            else:
                print(f"   ⚠️ [PGN_CURATION] No sequences extracted, falling back to scoring method")
        
        # FALLBACK: Use old scoring method
        # Step 2: Parse exploration_tree
        exploration_tree = investigation_result.exploration_tree
        if not exploration_tree:
            # Fallback: return empty refined PGN
            return RefinedPGN(
                pgn="",
                moves_of_interest=moves_of_interest
            )
        
        # Step 3: Score and collect all branches recursively
        scored_branches = []
        
        def score_and_collect_branches(node: Dict[str, Any], depth: int = 0, path: List[str] = []):
            """Recursively score branches and collect them"""
            move_played = node.get("move_played")
            if move_played:
                path = path + [move_played]
            
            # Calculate relevance score
            score = 0.0
            
            # Plan alignment (weight: 0.4)
            plan_alignment_score = 0.0
            if move_played and move_played in moves_of_interest:
                plan_alignment_score = 100.0
            elif focus_areas:
                # Check if move relates to focus areas
                for focus in focus_areas:
                    if focus.lower() in str(move_played).lower() if move_played else False:
                        plan_alignment_score = 50.0
                        break
            score += plan_alignment_score * 0.4
            
            # Eval significance (weight: 0.3)
            eval_d16 = node.get("eval_d16")
            eval_d2 = node.get("eval_d2")
            eval_significance_score = 0.0
            if eval_d16 is not None and eval_d2 is not None:
                eval_drop = abs(eval_d16 - eval_d2)
                if eval_drop > 1.0:
                    eval_significance_score = min(100.0, eval_drop * 20.0)  # Cap at 100
            score += eval_significance_score * 0.3
            
            # Tactical value (weight: 0.2)
            tactical_value_score = 0.0
            tactics = node.get("tactics", {})
            if tactics:
                if tactics.get("open_tactics") or tactics.get("checkmates"):
                    tactical_value_score = 100.0
                elif tactics.get("open_captures") or tactics.get("promotions"):
                    tactical_value_score = 50.0
            score += tactical_value_score * 0.2
            
            # Theme importance (weight: 0.1)
            theme_importance_score = 0.0
            light_raw = node.get("light_raw", {})
            if light_raw:
                top_themes = light_raw.get("top_themes", [])
                if top_themes:
                    theme_importance_score = min(100.0, len(top_themes) * 20.0)
            score += theme_importance_score * 0.1
            
            # Only include branches that aren't stopped and have some relevance
            if not node.get("stopped", False) and score > 0:
                scored_branches.append({
                    "node": node,
                    "score": score,
                    "path": path,
                    "move_played": move_played,
                    "depth": depth
                })
            
            # Recurse into sub-branches
            for branch in node.get("branches", []):
                score_and_collect_branches(branch, depth + 1, path)
        
        # Start scoring from root branches
        for branch in exploration_tree.get("branches", []):
            score_and_collect_branches(branch, depth=0, path=[])
        
        # Step 4: Select top N branches (top 5)
        scored_branches.sort(key=lambda x: x["score"], reverse=True)
        selected_branches = scored_branches[:5]  # Top 5
        
        # Step 5: Extract themes and tactical highlights
        all_themes = set()
        tactical_highlights = []
        
        # Collect from root
        root_light_raw = exploration_tree.get("light_raw", {})
        if root_light_raw:
            all_themes.update(root_light_raw.get("top_themes", []))
        
        root_tactics = exploration_tree.get("tactics", {})
        if root_tactics:
            if root_tactics.get("open_tactics"):
                tactical_highlights.append("open_tactics")
            if root_tactics.get("checkmates"):
                tactical_highlights.append("checkmates")
        
        # Collect from selected branches
        key_branches_metadata = []
        for branch_data in selected_branches:
            node = branch_data["node"]
            branch_metadata = {
                "move": branch_data["move_played"],
                "path": branch_data["path"],
                "score": branch_data["score"],
                "eval_d16": node.get("eval_d16"),
                "eval_d2": node.get("eval_d2"),
                "themes": [],
                "tactics": []
            }
            
            # Extract themes
            branch_light_raw = node.get("light_raw", {})
            if branch_light_raw:
                branch_themes = branch_light_raw.get("top_themes", [])
                branch_metadata["themes"] = branch_themes
                all_themes.update(branch_themes)
            
            # Extract tactics
            branch_tactics = node.get("tactics", {})
            if branch_tactics:
                if branch_tactics.get("open_tactics"):
                    branch_metadata["tactics"].append("open_tactics")
                if branch_tactics.get("checkmates"):
                    branch_metadata["tactics"].append("checkmates")
                if branch_tactics.get("open_captures"):
                    branch_metadata["tactics"].append("open_captures")
            
            key_branches_metadata.append(branch_metadata)
        
        # Step 6: Build refined PGN (pass investigation_result to preserve commentary)
        refined_pgn_str = self._build_refined_pgn(
            exploration_tree, 
            selected_branches,
            investigation_result=investigation_result
        )
        
        return RefinedPGN(
            pgn=refined_pgn_str,
            key_branches=key_branches_metadata,
            themes=list(all_themes)[:10],  # Top 10 themes
            tactical_highlights=list(set(tactical_highlights)),
            moves_of_interest=moves_of_interest
        )
    
    def _build_pgn_from_sequences(
        self,
        investigation_result: InvestigationResult,
        extracted_sequences: List[Dict[str, Any]]
    ) -> str:
        """
        Build refined PGN from LLM-selected sequences that prove the narrative.
        
        Args:
            investigation_result: The investigation result with exploration_tree
            extracted_sequences: List of sequences with moves, tags, and annotations
            
        Returns:
            PGN string with only the selected sequences
        """
        import chess.pgn
        
        try:
            exploration_tree = investigation_result.exploration_tree
            if not exploration_tree:
                return ""
            
            fen = exploration_tree.get("position", "")
            if not fen:
                return ""
            
            game = chess.pgn.Game()
            game.headers["FEN"] = fen
            game.headers["Event"] = "Investigation (Refined)"
            game.headers["Site"] = "?"
            game.headers["Date"] = "????.??.??"
            game.headers["Round"] = "?"
            game.headers["White"] = "?"
            game.headers["Black"] = "?"
            game.headers["Result"] = "*"
            
            board = chess.Board(fen)
            node = game
            
            # Build main line from first sequence (if available)
            if extracted_sequences:
                first_seq = extracted_sequences[0]
                seq_moves = first_seq.get("moves", [])
                
                for move_data in seq_moves[:10]:  # Limit to 10 moves per sequence
                    move_san = move_data.get("move")
                    if not move_san:
                        continue
                    
                    try:
                        move = board.parse_san(move_san)
                        if move in board.legal_moves:
                            board.push(move)
                            new_node = node.add_main_variation(move)
                            
                            # Add annotation with meaningful tags
                            annotation_parts = []
                            meaningful_tags = move_data.get("meaningful_tags", [])
                            if meaningful_tags:
                                annotation_parts.append(f"[%theme \"{', '.join(meaningful_tags[:2])}\"]")
                            
                            if annotation_parts:
                                new_node.comment = " ".join(annotation_parts)
                            
                            node = new_node
                    except Exception:
                        continue
            
            # Add other sequences as variations
            for seq in extracted_sequences[1:]:  # Skip first (already in main line)
                seq_moves = seq.get("moves", [])
                if not seq_moves:
                    continue
                
                # Reset board to starting position
                board.set_fen(fen)
                
                # Find the starting move
                start_move_san = seq.get("start_move")
                if not start_move_san:
                    continue
                
                try:
                    start_move = board.parse_san(start_move_san)
                    if start_move in board.legal_moves:
                        board.push(start_move)
                        branch_variation = game.add_variation(start_move)
                        
                        # Add comment explaining why this sequence matters
                        reason = seq.get("reason", "")
                        proves = seq.get("proves", "")
                        comment_parts = []
                        if reason:
                            comment_parts.append(reason)
                        if proves:
                            comment_parts.append(f"Proves: {proves}")
                        
                        if comment_parts:
                            branch_variation.comment = " ".join(comment_parts)
                        
                        # Continue the sequence
                        current_node = branch_variation
                        for move_data in seq_moves[1:10]:  # Skip first move (already added)
                            move_san = move_data.get("move")
                            if not move_san:
                                continue
                            
                            try:
                                move = board.parse_san(move_san)
                                if move in board.legal_moves:
                                    board.push(move)
                                    new_node = current_node.add_variation(move)
                                    
                                    # Add annotation with meaningful tags
                                    annotation_parts = []
                                    meaningful_tags = move_data.get("meaningful_tags", [])
                                    if meaningful_tags:
                                        annotation_parts.append(f"[%theme \"{', '.join(meaningful_tags[:2])}\"]")
                                    
                                    if annotation_parts:
                                        new_node.comment = " ".join(annotation_parts)
                                    
                                    current_node = new_node
                            except Exception:
                                break
                except Exception:
                    continue
            
            # Export PGN
            exporter = chess.pgn.StringExporter(
                headers=True,
                variations=True,
                comments=True
            )
            return str(game.accept(exporter))
        except Exception as e:
            print(f"   ⚠️ Error building PGN from sequences: {e}")
            import traceback
            traceback.print_exc()
            return ""
    
    def _build_refined_pgn(
        self,
        exploration_tree: Dict[str, Any],
        selected_branches: List[Dict[str, Any]],
        investigation_result: Optional[InvestigationResult] = None
    ) -> str:
        """
        Build refined PGN with only selected branches.
        Uses chess.pgn to build a clean PGN with essential annotations.
        """
        try:
            fen = exploration_tree.get("position", "")
            if not fen:
                return ""
            
            game = chess.pgn.Game()
            game.headers["FEN"] = fen
            game.headers["Event"] = "Investigation (Refined)"
            
            board = chess.Board(fen)
            node = game
            
            # Build main line (best move)
            best_move_d16 = exploration_tree.get("best_move_d16")
            if best_move_d16:
                try:
                    move = board.parse_san(best_move_d16)
                    if move in board.legal_moves:
                        board.push(move)
                        new_node = node.add_main_variation(move)
                        
                        # Add essential annotation
                        eval_d16 = exploration_tree.get("eval_d16")
                        annotation_parts = []
                        if eval_d16 is not None:
                            annotation_parts.append(f"[%eval {eval_d16:+.2f}]")
                        
                        # Add theme if available
                        light_raw = exploration_tree.get("light_raw", {})
                        if light_raw and light_raw.get("top_themes"):
                            themes = ",".join(light_raw["top_themes"][:2])
                            annotation_parts.append(f"[%theme \"{themes}\"]")
                        
                        if annotation_parts:
                            new_node.comment = " ".join(annotation_parts)
                        
                        node = new_node
                except Exception:
                    pass
            
            # Add selected branches as variations
            for branch_data in selected_branches:
                branch_node = branch_data["node"]
                move_played = branch_data["move_played"]
                if not move_played:
                    continue
                
                try:
                    # Reset board to starting position
                    board.set_fen(fen)
                    
                    # Parse and play the branch move
                    move = board.parse_san(move_played)
                    if move in board.legal_moves:
                        board.push(move)
                        branch_variation = game.add_variation(move)
                        
                        # Build comprehensive commentary
                        commentary_parts = []
                        
                        # Extract existing commentary if available in investigation_result
                        if investigation_result and investigation_result.commentary:
                            existing_comment = investigation_result.commentary.get(move_played)
                            if existing_comment:
                                commentary_parts.append(existing_comment)
                        
                        # Extract consequences from branch node if available
                        branch_consequences = branch_node.get("consequences", {})
                        if branch_consequences and isinstance(branch_consequences, dict):
                            # Format consequences generically
                            for key, value in branch_consequences.items():
                                if value:
                                    commentary_parts.append(f"{key}: {value}")
                        
                        # Extract tactical information from branch node
                        branch_tactics = branch_node.get("tactics", {})
                        if branch_tactics:
                            tactic_descriptions = []
                            if branch_tactics.get("open_tactics"):
                                for tactic in branch_tactics["open_tactics"][:2]:
                                    tactic_type = tactic.get("type", "tactic")
                                    tactic_descriptions.append(tactic_type)
                            if tactic_descriptions:
                                commentary_parts.append(f"Tactical opportunities: {', '.join(tactic_descriptions)}")
                        
                        # Extract themes from branch node
                        branch_light_raw = branch_node.get("light_raw", {})
                        if branch_light_raw and branch_light_raw.get("top_themes"):
                            themes = branch_light_raw["top_themes"][:2]
                            commentary_parts.append(f"Themes: {', '.join(themes)}")
                        
                        # Add branch annotation
                        branch_annotation = []
                        branch_eval_d2 = branch_node.get("eval_d2")
                        if branch_eval_d2 is not None:
                            branch_annotation.append(f"[%eval {branch_eval_d2:+.2f}]")
                        branch_annotation.append("[%theme \"overestimated\"]")
                        
                        # Add tactics if present
                        if branch_tactics.get("open_tactics"):
                            branch_annotation.append("[%tactic \"open_tactic\"]")
                        
                        # Combine annotations with commentary
                        if branch_annotation:
                            final_comment = " ".join(branch_annotation)
                            if commentary_parts:
                                final_comment += " " + " ".join(commentary_parts)
                            branch_variation.comment = final_comment
                        elif commentary_parts:
                            branch_variation.comment = " ".join(commentary_parts)
                except Exception:
                    continue
            
            # Export PGN
            exporter = chess.pgn.StringExporter(
                headers=True,
                variations=True,
                comments=True
            )
            return str(game.accept(exporter))
        except Exception as e:
            print(f"   ⚠️ Error building refined PGN: {e}")
            import traceback
            traceback.print_exc()
            return ""

