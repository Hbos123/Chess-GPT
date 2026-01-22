# Confidence Engine Protocol

This document captures the rules and expectations that the rewritten confidence engine must satisfy. It serves as the canonical reference for backend logic, data modelling, and frontend rendering.

## Visual Semantics

- **Shapes**
  - Square (`■`): first and last node of the PV spine.
  - Circle (`●`): PV node or branch node that has not been expanded.
  - Triangle (`▲`): PV node that has spawned alternate branches. Once triangular, it never reverts to a circle.

- **Colors**
  - Green (`🟢`): node meets or exceeds the confidence baseline.
  - Blue (`🔵`): branched node whose worst branch still meets the baseline (triangle only).
  - Red (`🔴`): node below baseline or branched node whose worst branch is below baseline.

## Confidence Baseline

- A configurable threshold (default 80).
- PV nodes must all meet the baseline before the raise completes.
- `frozen_confidence` captures the lowest terminal confidence produced by a branched node and drives red/blue status.

## Node Data Requirements

Each node emitted to the frontend must include:

| Field | Description |
| --- | --- |
| `id` | Stable identifier (`pv-N`, `alt-PARENT-INDEX`, `iter-altm-ID`, etc.). |
| `parent_id` | Identifier of the parent node, or `null` for the PV root. |
| `move` | UCI of the move from parent to node; `null` for PV root. |
| `ply_index` | Distance from S0 in plies. |
| `confidence` | Current confidence percent (0-100). |
| `shape` | `square`, `circle`, or `triangle`. |
| `color` | `green`, `blue`, or `red`. |
| `frozen_confidence` | Lowest terminal branch confidence for triangles; `null` otherwise. |
| `initial_confidence` | Confidence before branching; used for tooltips. |
| `labels` | Set of tags (best move, played move, branch, etc.) |
| `fen` | FEN of the node. |
| `branch_summary` | Metadata for branch leaves (count, min/max confidence). |

## Engine Phases

1. **PV Construction**
   - Play the chosen move from the starting FEN and generate depth-18 PV from the engine.
   - Score each PV node at depth-18 and depth-2 to obtain initial confidence values.

2. **Branch Generation**
   - For any PV node below baseline, request multipv depth-2 analysis.
   - Create alternate move nodes for deviations within the `delta2` window or when forcing at least one branch.
   - For each alternate, analyse `(depth=18)` and the opponent reply `(depth=2/18)` to obtain terminal confidence.

3. **Triangle Freezing**
   - Convert the PV node to a triangle.
   - Store `frozen_confidence = min(branch_confidences)` and `initial_confidence`.
   - Mark red if `frozen_confidence < baseline`, blue if `>= baseline`.

4. **Iterative Raise Loop**
   - While the minimum PV confidence is below the baseline:
     - Select next candidate using a priority queue (lowest confidence first) with round-robin fairness.
     - Candidates include PV nodes and branch midpoints whose effective confidence is below baseline.
     - Expand candidate as in branch generation.
     - Update node states and recompute min PV confidence.

5. **Termination**
   - Stop when all PV nodes meet baseline or when global caps are hit (max nodes, iterations, depth).
   - Output final nodes and intermediate snapshots for animation.

## Eligibility Rules

- PV Nodes
  - Include if confidence < baseline or triangle with `frozen_confidence < baseline`.
  - Exclude final PV node unless explicitly below baseline.
- Branch Midpoints (`iter-altm-*`)
  - Eligible if their `frozen_confidence` (or current confidence) < baseline.
- Branch Leaves (`iter-alt-*`)
  - Never eligible; they describe terminal positions only.

## Logging & Metrics

- Each iteration logs:
  - Candidate list, skipped reasons, node counts.
  - Snapshot JSON of node state.
  - Aggregated statistics (PV length, triangle count, red/blue/green counts, min/max confidence).

## Frontend Snapshot Schema

Snapshots delivered to the UI must include:

```json
{
  "baseline": 80,
  "nodes": [...],
  "min_confidence": 70,
  "stats": {
    "pv_length": 18,
    "triangles": 4,
    "red_nodes": 6,
    "green_nodes": 12
  }
}
```

Each entry in `nodes` uses the structure defined above. Snapshots are appended chronologically so the UI can animate transitions.

## Forced Branching

- When a PV node is below baseline and no alternate meets the `delta2` window, force the best available alternate to ensure the triangle is explored.
- Forced branches are still scored and contribute to `frozen_confidence`.

## Repeated Raises

- Previously branched nodes (triangles) are eligible in future raises if their `frozen_confidence` is below baseline.
- Branch midpoints remain eligible after the first raise to continue pushing depth when confidence is still low.

## Testing Expectations

- Unit tests cover PV construction, branch generation, triangle state transitions, and eligibility determination.
- Integration tests run the full raise loop on curated positions to ensure convergence and cap behaviour.
- Frontend snapshot diff tests ensure shape/color/metadata output remains consistent.
