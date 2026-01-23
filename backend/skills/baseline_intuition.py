from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
import os

import chess  # type: ignore

from investigator import Investigator
from scan_service import ScanPolicy
from skills.claims import build_claims_from_investigation
from skills.motifs import MotifPolicy, mine_motifs


def _build_pattern_claims_from_motifs(motifs: Any, *, top_n: int = 12) -> List[Dict[str, Any]]:
    """
    Deterministically convert mined motifs into "claim format" objects suitable for UI evidence panels.

    This is intentionally non-LLM and best-effort:
    - Uses motif signature/examples for evidence moves
    - Passes through eval_stats + tag_role_deltas (if present)
    - Preserves significance/count metadata for ranking
    """
    if not isinstance(motifs, list) or not motifs:
        return []

    def _rank(m: Dict[str, Any]) -> Tuple[int, float]:
        loc = m.get("location") if isinstance(m, dict) else None
        ct = (loc or {}).get("count_total") if isinstance(loc, dict) else m.get("count_total")
        try:
            ct_i = int(ct or 0)
        except Exception:
            ct_i = 0
        try:
            sig = float(m.get("significance") or 0.0)
        except Exception:
            sig = 0.0
        return (ct_i, sig)

    ms: List[Dict[str, Any]] = [m for m in motifs if isinstance(m, dict)]
    ms.sort(key=_rank, reverse=True)
    out: List[Dict[str, Any]] = []

    for m in ms[: max(0, int(top_n))]:
        pattern = m.get("pattern") if isinstance(m.get("pattern"), dict) else {}
        sig = (pattern or {}).get("signature") or m.get("signature") or ""
        classification = m.get("classification") or m.get("class") or "pattern"
        loc = m.get("location") if isinstance(m.get("location"), dict) else {}
        count_total = loc.get("count_total") if isinstance(loc, dict) else m.get("count_total")
        distinct_roots = loc.get("distinct_root_branches") if isinstance(loc, dict) else None
        significance = m.get("significance")

        # Prefer deterministic SAN windows captured during mining.
        evidence_moves: List[str] = []
        examples = m.get("examples_san") or []
        if isinstance(examples, list) and examples:
            ex0 = examples[0] if isinstance(examples[0], dict) else None
            mv = ex0.get("moves_san") if isinstance(ex0, dict) else None
            if isinstance(mv, list):
                evidence_moves = [x for x in mv if isinstance(x, str) and x.strip()][:8]

        # Best-effort fallback: extract SAN tokens from signature string.
        if not evidence_moves and isinstance(sig, str) and sig.strip():
            import re as _re
            toks = _re.findall(r"SAN:([A-Za-z0-9O+=#\\-]+)", sig)[:8]
            evidence_moves = [t for t in toks if isinstance(t, str) and t.strip()]

        eval_stats = m.get("eval_stats") if isinstance(m.get("eval_stats"), dict) else {}
        trd = m.get("tag_role_deltas") if isinstance(m.get("tag_role_deltas"), dict) else {}

        summary = f"{classification}: {(' '.join(evidence_moves) if evidence_moves else (sig or '(motif)'))}".strip()

        out.append(
            {
                "summary": summary,
                "claim_type": "pattern",
                "connector": None,
                "evidence_moves": evidence_moves,
                "evidence_source": "motifs",
                "evidence_payload": {
                    "pgn_moves": evidence_moves,
                    "pgn_line": " ".join(evidence_moves) if evidence_moves else None,
                    "eval_stats": eval_stats,
                    "motif_meta": {
                        "classification": classification,
                        "signature": sig,
                        "count_total": count_total,
                        "distinct_root_branches": distinct_roots,
                        "significance": significance,
                    },
                    "tag_role_deltas": trd,
                    # Convenience top-level mirrors for UI (older renderers sometimes look here).
                    "tags_gained_net": trd.get("tags_gained_net", []) if isinstance(trd, dict) else [],
                    "tags_lost_net": trd.get("tags_lost_net", []) if isinstance(trd, dict) else [],
                    "roles_gained_net": trd.get("roles_gained_net", []) if isinstance(trd, dict) else [],
                    "roles_lost_net": trd.get("roles_lost_net", []) if isinstance(trd, dict) else [],
                },
            }
        )

    return out


@dataclass(frozen=True)
class BaselineIntuitionPolicy:
    # Use default_factory to avoid mutable default issues (Python 3.14+).
    scan: ScanPolicy = field(default_factory=ScanPolicy)
    motifs: MotifPolicy = field(default_factory=MotifPolicy)
    # Default: single-pass (Scan A only). Scan B is diminishing returns unless explicitly requested.
    include_second_pass: bool = False


def _investigator(engine_pool_instance=None, engine_queue=None) -> Investigator:
    return (
        Investigator(engine_pool=engine_pool_instance)
        if engine_pool_instance is not None
        else Investigator(engine_queue=engine_queue)
    )


async def _run_single_scan(
    *,
    engine_pool_instance=None,
    engine_queue=None,
    start_fen: str,
    policy: BaselineIntuitionPolicy,
    progress_cb: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    inv = _investigator(engine_pool_instance, engine_queue)
    b = chess.Board(start_fen)
    fen = b.fen()

    if progress_cb:
        try:
            progress_cb("scan_start", {"fen": fen})
        except Exception:
            pass
    res = await inv.investigate_with_dual_depth(
        fen,
        scope="general_position",
        depth_16=int(policy.scan.d16_depth),
        depth_2=int(policy.scan.d2_depth),
        original_fen=fen,
        branching_limit=int(policy.scan.branching_limit),
        max_pv_plies=int(policy.scan.max_pv_plies),
        include_pgn=bool(policy.scan.include_pgn),
        pgn_max_chars=int(policy.scan.pgn_max_chars),
    )

    inv_dict = res.to_dict(include_semantic_story=False)

    # Motifs + claims are derived deterministically on top of investigation tree/evidence.
    exploration_tree = inv_dict.get("exploration_tree") or {}
    motifs = []
    try:
        if isinstance(exploration_tree, dict) and exploration_tree:
            if progress_cb:
                try:
                    progress_cb("motifs_start", {"fen": fen})
                except Exception:
                    pass
            motifs = mine_motifs(
                starting_fen=fen,
                exploration_tree=exploration_tree,
                engine_pool_instance=engine_pool_instance,
                engine_queue=engine_queue,
                policy=policy.motifs,
            )
    except Exception:
        motifs = []

    # NEW: Compute cheap eval/material/positional deltas for motifs so they can be rendered like claims.
    # Deterministic + bounded: sample up to N motifs and M examples per motif.
    try:
        if motifs and isinstance(motifs, list):
            from investigator import Investigator
            inv = Investigator(engine_pool=engine_pool_instance) if engine_pool_instance is not None else Investigator(engine_queue=engine_queue)
            try:
                max_motifs = int(os.getenv("MOTIF_EVAL_MAX_MOTIFS", "8"))
            except Exception:
                max_motifs = 8
            try:
                max_examples = int(os.getenv("MOTIF_EVAL_MAX_EXAMPLES_PER_MOTIF", "2"))
            except Exception:
                max_examples = 2
            try:
                depth = int(os.getenv("MOTIF_EVAL_DEPTH", "4"))
            except Exception:
                depth = 4

            base_eval = inv_dict.get("eval_d16")
            for m in [x for x in motifs if isinstance(x, dict)][:max(0, max_motifs)]:
                exs = m.get("examples_san") or []
                if not isinstance(exs, list):
                    exs = []
                samples = []
                for ex in exs[:max(0, max_examples)]:
                    if not isinstance(ex, dict):
                        continue
                    moves = ex.get("moves_san") or []
                    if not (isinstance(moves, list) and moves and all(isinstance(mm, str) for mm in moves)):
                        continue
                    try:
                        br = await inv._compute_evidence_eval_breakdown(  # type: ignore
                            starting_fen=fen,
                            evidence_moves=[mm for mm in moves if isinstance(mm, str) and mm.strip()][:8],
                            eval_start_pawns=base_eval,
                            end_eval_depth=depth,
                        )
                        samples.append(br)
                    except Exception:
                        continue

                if samples:
                    # Average numeric fields
                    def _avg(key: str):
                        vals = [s.get(key) for s in samples if isinstance(s.get(key), (int, float))]
                        return (sum(vals) / len(vals)) if vals else None
                    m["eval_stats"] = {
                        "n_samples": len(samples),
                        "avg_eval_start": _avg("eval_start"),
                        "avg_eval_end": _avg("eval_end"),
                        "avg_eval_delta": _avg("eval_delta"),
                        "avg_material_start": _avg("material_start"),
                        "avg_material_end": _avg("material_end"),
                        "avg_positional_start": _avg("positional_start"),
                        "avg_positional_end": _avg("positional_end"),
                    }
                    
                    # Also compute aggregated tag/role deltas for the sampled windows
                    tag_deltas_samples: List[Dict[str, Any]] = []
                    for ex in exs[:max(0, max_examples)]:
                        if not isinstance(ex, dict):
                            continue
                        moves = ex.get("moves_san") or []
                        if not (isinstance(moves, list) and moves and all(isinstance(mm, str) for mm in moves)):
                            continue
                        try:
                            per_move, tg_net, tl_net, rg_net, rl_net, tg_struct, tl_struct = inv._compute_per_move_deltas_for_line(  # type: ignore
                                starting_fen=fen,
                                moves_san=[mm for mm in moves if isinstance(mm, str) and mm.strip()][:8],
                            )
                            tag_deltas_samples.append({
                                "tags_gained_net": tg_net if isinstance(tg_net, list) else [],
                                "tags_lost_net": tl_net if isinstance(tl_net, list) else [],
                                "roles_gained_net": rg_net if isinstance(rg_net, list) else [],
                                "roles_lost_net": rl_net if isinstance(rl_net, list) else [],
                                "tags_gained_net_structured": tg_struct if isinstance(tg_struct, list) else [],
                                "tags_lost_net_structured": tl_struct if isinstance(tl_struct, list) else [],
                            })
                        except Exception:
                            continue
                    
                    # Aggregate tag/role deltas across samples (union of all tags/roles seen)
                    if tag_deltas_samples:
                        all_tags_gained: set = set()
                        all_tags_lost: set = set()
                        all_roles_gained: set = set()
                        all_roles_lost: set = set()
                        all_tags_gained_struct: List[Dict[str, Any]] = []
                        all_tags_lost_struct: List[Dict[str, Any]] = []
                        seen_tag_keys_gained: set = set()
                        seen_tag_keys_lost: set = set()
                        
                        for sample in tag_deltas_samples:
                            for tg in sample.get("tags_gained_net", []):
                                if isinstance(tg, str):
                                    all_tags_gained.add(tg)
                            for tl in sample.get("tags_lost_net", []):
                                if isinstance(tl, str):
                                    all_tags_lost.add(tl)
                            for rg in sample.get("roles_gained_net", []):
                                if isinstance(rg, str):
                                    all_roles_gained.add(rg)
                            for rl in sample.get("roles_lost_net", []):
                                if isinstance(rl, str):
                                    all_roles_lost.add(rl)
                            # For structured tags, dedupe by tag_key (tag_name|side|squares|pieces)
                            for tg_struct in sample.get("tags_gained_net_structured", []):
                                if not isinstance(tg_struct, dict):
                                    continue
                                tag_name = tg_struct.get("tag_name") or ""
                                side = tg_struct.get("side") or ""
                                squares = ",".join(sorted([str(s) for s in (tg_struct.get("squares") or []) if s]))
                                pieces = ",".join(sorted([str(p) for p in (tg_struct.get("pieces") or []) if p]))
                                key = f"{tag_name}|{side}|{squares}|{pieces}"
                                if key not in seen_tag_keys_gained:
                                    seen_tag_keys_gained.add(key)
                                    all_tags_gained_struct.append(tg_struct)
                            for tl_struct in sample.get("tags_lost_net_structured", []):
                                if not isinstance(tl_struct, dict):
                                    continue
                                tag_name = tl_struct.get("tag_name") or ""
                                side = tl_struct.get("side") or ""
                                squares = ",".join(sorted([str(s) for s in (tl_struct.get("squares") or []) if s]))
                                pieces = ",".join(sorted([str(p) for p in (tl_struct.get("pieces") or []) if p]))
                                key = f"{tag_name}|{side}|{squares}|{pieces}"
                                if key not in seen_tag_keys_lost:
                                    seen_tag_keys_lost.add(key)
                                    all_tags_lost_struct.append(tl_struct)
                        
                        m["tag_role_deltas"] = {
                            "tags_gained_net": sorted(list(all_tags_gained)),
                            "tags_lost_net": sorted(list(all_tags_lost)),
                            "roles_gained_net": sorted(list(all_roles_gained)),
                            "roles_lost_net": sorted(list(all_roles_lost)),
                            "tags_gained_net_structured": all_tags_gained_struct,
                            "tags_lost_net_structured": all_tags_lost_struct,
                        }
    except Exception:
        pass
    if progress_cb:
        try:
            progress_cb("motifs_done", {"fen": fen, "motifs_count": len(motifs) if isinstance(motifs, list) else 0})
        except Exception:
            pass

    claims = []
    try:
        if progress_cb:
            try:
                progress_cb("claims_start", {"fen": fen})
            except Exception:
                pass
        claims = build_claims_from_investigation(inv_dict)
    except Exception:
        claims = []
    if progress_cb:
        try:
            progress_cb("claims_done", {"fen": fen, "claims_count": len(claims) if isinstance(claims, list) else 0})
        except Exception:
            pass

    # NEW: Pattern claims (claim-like motif entries for UI + LLM grounding).
    pattern_claims: List[Dict[str, Any]] = []
    try:
        pattern_claims = _build_pattern_claims_from_motifs(motifs, top_n=int(os.getenv("MOTIF_PATTERN_CLAIMS_TOP", "12")))
    except Exception:
        pattern_claims = []

    # Preserve the compact root summary fields (for easy UI indexing)
    out = {
        "fen": fen,
        "root": {
            "eval_d2": inv_dict.get("eval_d2"),
            "eval_d16": inv_dict.get("eval_d16"),
            "best_move_d16_san": inv_dict.get("best_move_d16"),
            "best_move_d16_eval_cp": inv_dict.get("best_move_d16_eval_cp"),
            "second_best_d16_san": inv_dict.get("second_best_move_d16"),
            "second_best_d16_eval_cp": inv_dict.get("second_best_move_d16_eval_cp"),
            "is_critical": inv_dict.get("is_critical"),
            "is_winning": inv_dict.get("is_winning"),
        },
        # Verbose artifacts (as requested)
        "pgn_bundle": {
            "fen": fen,
            "pgn": inv_dict.get("pgn_exploration") or "",
        },
        "pgn_exploration": inv_dict.get("pgn_exploration") or "",
        "commentary": inv_dict.get("commentary") or {},
        "exploration_tree": exploration_tree,
        "overestimated_moves": inv_dict.get("overestimated_moves") or [],
        "evidence_index": inv_dict.get("evidence_index") or [],
        "evidence": {
            "evidence_pgn_line": inv_dict.get("evidence_pgn_line"),
            "evidence_main_line_moves": inv_dict.get("evidence_main_line_moves") or [],
            "evidence_per_move_deltas": inv_dict.get("evidence_per_move_deltas") or [],
            "evidence_eval_start": inv_dict.get("evidence_eval_start"),
            "evidence_eval_end": inv_dict.get("evidence_eval_end"),
            "evidence_eval_delta": inv_dict.get("evidence_eval_delta"),
            "evidence_material_start": inv_dict.get("evidence_material_start"),
            "evidence_material_end": inv_dict.get("evidence_material_end"),
            "evidence_positional_start": inv_dict.get("evidence_positional_start"),
            "evidence_positional_end": inv_dict.get("evidence_positional_end"),
            "evidence_tags_gained_net_structured": inv_dict.get("evidence_tags_gained_net_structured") or [],
            "evidence_tags_lost_net_structured": inv_dict.get("evidence_tags_lost_net_structured") or [],
            "evidence_roles_gained_net": inv_dict.get("evidence_roles_gained_net") or [],
            "evidence_roles_lost_net": inv_dict.get("evidence_roles_lost_net") or [],
        },
        "claims": claims,
        "motifs": motifs,
        "pattern_claims": pattern_claims,
    }
    return out


async def run_baseline_intuition(
    *,
    engine_pool_instance=None,
    engine_queue=None,
    start_fen: str,
    policy: Optional[BaselineIntuitionPolicy] = None,
    progress_cb: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """
    Baseline intuition (default: single-pass):
    - ScanA: dual-depth (D2/D16) from start_fen
    - Optional ScanB: apply ScanA best_move_d16_san, then rescan (only if include_second_pass=True)
    """
    pol = policy or BaselineIntuitionPolicy()

    if progress_cb:
        try:
            progress_cb("baseline_start", {"start_fen": start_fen, "include_second_pass": bool(getattr(pol, "include_second_pass", False))})
        except Exception:
            pass
    scan_root = await _run_single_scan(
        engine_pool_instance=engine_pool_instance,
        engine_queue=engine_queue,
        start_fen=start_fen,
        policy=pol,
        progress_cb=progress_cb,
    )
    if progress_cb:
        try:
            progress_cb("scan_done", {"which": "root"})
        except Exception:
            pass

    scan_after_best: Optional[Dict[str, Any]] = None
    if bool(getattr(pol, "include_second_pass", False)):
        best_san = (scan_root.get("root") or {}).get("best_move_d16_san")
        fen_after_best = None
        if isinstance(best_san, str) and best_san.strip():
            try:
                b = chess.Board(start_fen)
                mv = b.parse_san(best_san)
                if mv in b.legal_moves:
                    b.push(mv)
                    fen_after_best = b.fen()
            except Exception:
                fen_after_best = None

        scan_after_best = {"error": "could_not_apply_best_move_for_second_pass"}
        if fen_after_best:
            if progress_cb:
                try:
                    progress_cb("second_pass_start", {"fen": fen_after_best, "best_move_d16_san": best_san})
                except Exception:
                    pass
            scan_after_best = await _run_single_scan(
                engine_pool_instance=engine_pool_instance,
                engine_queue=engine_queue,
                start_fen=fen_after_best,
                policy=pol,
                progress_cb=progress_cb,
            )
            if progress_cb:
                try:
                    progress_cb("second_pass_done", {})
                except Exception:
                    pass

    out = {
        "start_fen": start_fen,
        "policy_used": {
            "d2_depth": int(pol.scan.d2_depth),
            "d16_depth": int(pol.scan.d16_depth),
            "branching_limit": int(pol.scan.branching_limit),
            "max_pv_plies": int(pol.scan.max_pv_plies),
            "include_pgn": bool(pol.scan.include_pgn),
            "pgn_max_chars": int(pol.scan.pgn_max_chars),
            "motifs_max_pattern_plies": int(pol.motifs.max_pattern_plies),
            "motifs_top": int(pol.motifs.motifs_top),
            "motifs_max_line_plies": int(pol.motifs.max_line_plies),
            "motifs_max_branch_lines": int(pol.motifs.max_branch_lines),
            "include_second_pass": bool(getattr(pol, "include_second_pass", False)),
        },
        "scan_root": scan_root,
        "scan_after_best": scan_after_best,
    }
    if progress_cb:
        try:
            progress_cb("baseline_done", {"has_scan_after_best": isinstance(scan_after_best, dict)})
        except Exception:
            pass
    return out


def format_baseline_intuition_for_chat(baseline: Dict[str, Any]) -> str:
    """
    Render a verbose, deterministic chat block (no LLM) containing:
    - ScanA PGN + claims + motifs
    - ScanB PGN + claims + motifs
    """
    def _fmt_scan(title: str, scan: Dict[str, Any]) -> str:
        if not isinstance(scan, dict):
            return f"{title}\n<invalid scan payload>"
        root = scan.get("root") or {}
        best = root.get("best_move_d16_san")
        ev16 = root.get("eval_d16")
        ev2 = root.get("eval_d2")
        header = f"{title}\nD16 eval: {ev16} | D2 eval: {ev2} | Best D16: {best}"
        pgn = scan.get("pgn_exploration") or ""
        claims = scan.get("claims") or []
        motifs = scan.get("motifs") or []

        claims_txt = ""
        if isinstance(claims, list) and claims:
            lines = []
            for c in claims[:12]:
                if not isinstance(c, dict):
                    continue
                ct = c.get("claim_type")
                st = c.get("statement")
                sup = c.get("support")
                lines.append(f"- {ct}: {st} | support={sup}")
            claims_txt = "Claims:\n" + "\n".join(lines) if lines else ""

        motifs_txt = ""
        if isinstance(motifs, list) and motifs:
            lines = []
            for m in motifs[:25]:
                if not isinstance(m, dict):
                    continue
                sig = ((m.get("pattern") or {}).get("signature"))
                loc = m.get("location") or {}
                lines.append(
                    f"- {m.get('classification')}: {sig} | count={loc.get('count_total')} | roots={loc.get('distinct_root_branches')}"
                )
            motifs_txt = "Motifs:\n" + "\n".join(lines) if lines else ""

        parts = [header, "PGN:\n" + pgn.strip() if isinstance(pgn, str) and pgn.strip() else "PGN:\n<empty>"]
        if claims_txt:
            parts.append(claims_txt)
        if motifs_txt:
            parts.append(motifs_txt)
        return "\n\n".join(parts)

    scan_root = baseline.get("scan_root") if isinstance(baseline, dict) else {}
    scan_after = baseline.get("scan_after_best") if isinstance(baseline, dict) else None

    parts = [
        "=== Baseline D2/D16 Intuition ===",
        _fmt_scan("Scan A (root FEN)", scan_root if isinstance(scan_root, dict) else {}),
    ]
    if isinstance(scan_after, dict):
        parts.append(_fmt_scan("Scan B (after best D16 move)", scan_after))
    return "\n\n".join(parts).strip()


