# Critical Fix: Branch Terminal Nodes Causing Explosion

## The Problem

After the indentation fix, the system was working but creating too many nodes:

**Before raise:** 18 total, 16 red circles, 2 green  
**After raise:** 121 total, 45 triangles, 23 red circles, 53 green

**Issues:**
1. 121 nodes is excessive (should be ~40-70)
2. 45 triangles created but still 23 red circles remaining
3. Branch terminal nodes (the leaf nodes of extended branches) were being added to eligible list and getting extended again

## Root Cause

When extending a red circle on the PV, we create branch terminals like:
```
pv-1 (red circle)
  ├─ iter-altm-0 (intermediate branch node)
  └─ iter-alt-0 (terminal branch node) <-- This was getting extended!
```

The **terminal branch nodes** (`iter-alt-*`) were red (low confidence) and were being included in the eligible nodes list for the next iteration. This caused:
1. Explosion of nodes as terminals spawned more branches
2. Red circles remaining because terminals were being extended instead
3. Excessive iteration count

## The Fix

**File:** `backend/confidence_engine.py` (lines 387-407)

**Changed:** Eligible node selection to ONLY include PV nodes

```python
for idx, nd in enumerate(nodes):
    # Only extend PV nodes or red triangles on PV
    # Skip all branch terminal nodes (non-PV nodes)
    if not nd['id'].startswith('pv-') and not nd['id'].startswith('alt-'):
        continue
    
    # For PV nodes: include if below target OR (branched but insufficient)
    if nd['id'].startswith('pv-'):
        is_red_circle = (nd['ConfidencePercent'] < target_conf and not nd.get('has_branches', False))
        is_red_triangle = (nd.get('has_branches', False) and nd.get('insufficient_confidence', False))
        is_red_node = is_red_circle or is_red_triangle
        
        # Skip nodes that are already at or above target (green nodes)
        if nd['ConfidencePercent'] >= target_conf and not is_red_triangle:
            continue
        
        if (is_red_node and 
            not is_final_pv(nd['id']) and
            nd['ply_from_S0'] < max_ply_from_S0):
            conf_for_heap = nd.get('frozen_confidence', nd['ConfidencePercent']) if nd.get('has_branches', False) else nd['ConfidencePercent']
            heapq.heappush(heap, (conf_for_heap, idx))
```

**Key changes:**
1. **First check:** Skip all nodes that don't start with `'pv-'` (skips all branch terminals)
2. **Second check:** Only process PV nodes for extension
3. **Result:** Branch terminals are never added to eligible list

## Expected Behavior After Fix

### Node Counts:
- **Before:** 121 total (excessive)
- **After:** 30-50 total (reasonable)

### Triangle Conversion:
- **Before:** 16 red circles → 45 triangles (over-extended)
- **After:** 16 red circles → 16-20 triangles (all PV reds converted)

### Iteration Flow:
1. **Iteration 0:** Extend pv-1 (red circle) → becomes triangle, spawns 2 terminals
2. **Iteration 1:** Extend pv-3 (red circle) → becomes triangle, spawns 2 terminals
3. **Iteration 2:** Extend pv-1 (red triangle, if insufficient) → spawns more branches
4. **etc...**

**Branch terminals are NEVER extended** - they are the endpoint of exploration for that branch.

## Why This Is Correct

The confidence tree concept:
- **PV spine** = The main line we're investigating
- **Red circles on PV** = Positions needing confidence improvement
- **Triangles** = PV positions that have been explored with branches
- **Branch terminals** = The endpoints showing "what if" alternatives

**Branch terminals should NOT be extended because:**
1. They are not on the main line (PV)
2. They serve as reference points for eval comparison
3. Extending them would create a tree-of-trees (excessive complexity)
4. The goal is to raise confidence on THE PV, not on every possible alternative

## How to Verify

**Backend logs should show:**
```
[Confidence] Iteration 0: min_line_conf=65, nodes=18
[Confidence] Extending node pv-1 (conf=65%, has_branches=False)
✓ Node pv-1 now TRIANGLE: spawned 2 branches...
[Confidence] Iteration 1: min_line_conf=65, nodes=24
[Confidence] Extending node pv-3 (conf=68%, has_branches=False)
✓ Node pv-3 now TRIANGLE: spawned 2 branches...
```

**You should NOT see:**
```
[Confidence] Extending node iter-alt-0 (conf=55%, has_branches=False)
```

**Frontend should show:**
```
🌳 BEFORE RAISE: {total: 18, pv: 18, triangles: 0, red_circles: 16}
🌳 AFTER RAISE: {total: 40-60, pv: 18, triangles: 16-20, red_circles: 0-5}
```

---

## Bonus Issue: Annotation Parsing Error

**Separate issue** from confidence tree:

```
[Warning] Failed to parse PGN sequence
Error: Invalid move: e4
```

**Problem:** The annotation system is trying to parse "e4" but the board state might be wrong or it's trying to parse from the wrong position.

**Quick fix location:** `frontend/app/page.tsx` - search for "Failed to parse PGN" and check the board state being passed to the parser.

**Likely cause:** The PGN parser is being called with a board that's not at the starting position when trying to parse "1. e4".

---

## Test Now!

1. **Restart backend**
2. **Raise confidence on a move**
3. **Check backend terminal** for tree visualizations
4. **Check frontend** for node counts

Expected improvement:
- ✅ Fewer total nodes (40-60 instead of 121)
- ✅ All PV red circles become triangles
- ✅ No branch terminals in "Extending node X" messages
- ✅ Reasonable iteration count (3-10 instead of 30+)

