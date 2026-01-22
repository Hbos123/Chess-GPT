# Confidence Tree Fixes Applied

## Issues Identified from User Logs

**Before:** 18 total, 18 pv, 0 triangles, 17 red circles, 1 green circle
**After:** 122 total, 18 pv, 28 triangles, 63 red circles, 31 green circles

### Problems:
1. ❌ Incomplete transformation of red circles to triangles (only 28/17)
2. ❌ Incomplete recoloring of blue triangles to red or green
3. ❌ Branches extending even though terminal node has confidence over requirement
4. ❌ Some branches ending early
5. ❌ Too many nodes created (122 from 18 is excessive)

## Fixes Applied

### 1. **Stop Extending When Terminal is Green**

**File:** `backend/confidence_engine.py` (lines 503-569)

**Problem:** Triangles were being recolored even when they had green terminal nodes (>= target confidence).

**Fix:** Added check for highest terminal confidence:
```python
highest_terminal_conf = max(spawned_leaf_confs) if spawned_leaf_confs else nd['ConfidencePercent']

# Only recolor if highest terminal is still below target
if extended_moves and highest_terminal_conf < target_conf:
    # Do recoloring check...
elif highest_terminal_conf >= target_conf:
    # At least one terminal is green - this triangle is satisfied
    nodes[pick_idx]['insufficient_confidence'] = False
    print(f"Triangle marked GREEN: highest terminal conf={highest_terminal_conf}% >= target")
```

**Result:** Triangles with green terminals are immediately marked as satisfied (blue/green) and won't be re-extended.

---

### 2. **Proper Min Line Confidence Calculation**

**File:** `backend/confidence_engine.py` (lines 583-600)

**Problem:** `min_line_conf` used `ConfidencePercent` for all nodes, including triangles. This caused the loop to continue even when triangles were satisfied.

**Fix:** For PV nodes:
- **Red triangles** (insufficient_confidence=True): Use `frozen_confidence`
- **Blue/green triangles** (insufficient_confidence=False): Treat as `target_conf` (satisfied)
- **Circles**: Use `ConfidencePercent`

```python
for n in nodes:
    if n['id'].startswith('pv-'):
        if n.get('has_branches', False):
            if n.get('insufficient_confidence', False):
                pv_confs.append(n.get('frozen_confidence', n['ConfidencePercent']))
            else:
                # Blue/green triangle - consider it "solved"
                pv_confs.append(target_conf)
        else:
            pv_confs.append(n['ConfidencePercent'])
min_line_conf = min(pv_confs)
```

**Result:** Loop exits when all PV nodes are either green or blue/green triangles, preventing excessive iterations.

---

### 3. **Improved Eligible Node Selection**

**File:** `backend/confidence_engine.py` (lines 373-391)

**Problem:** Green nodes (confidence >= target) might have been included in eligible list for extension.

**Fix:** Explicitly skip green nodes and clarify red node logic:
```python
is_red_circle = (nd['ConfidencePercent'] < target_conf and not nd.get('has_branches', False))
is_red_triangle = (nd.get('has_branches', False) and nd.get('insufficient_confidence', False))
is_red_node = is_red_circle or is_red_triangle

# Skip nodes that are already at or above target (green nodes)
if nd['ConfidencePercent'] >= target_conf and not is_red_triangle:
    continue

if is_red_node and not is_final_pv(nd['id']) and nd['ply_from_S0'] < max_ply_from_S0:
    # Use frozen_confidence for triangles in heap priority
    conf_for_heap = nd.get('frozen_confidence', nd['ConfidencePercent']) if nd.get('has_branches', False) else nd['ConfidencePercent']
    heapq.heappush(heap, (conf_for_heap, idx))
```

**Result:** Only truly red nodes (circles or triangles) are extended, not green or blue nodes.

---

### 4. **Better Logging for Debugging**

**File:** `backend/confidence_engine.py` (lines 508, 559, 562, 566)

**Added:** More detailed logging messages:
- `"Spawned X alternates from Y, frozen at Z% (terminals: [...], highest: H%)"`
- `"Triangle marked RED: best move has conf=X%"`
- `"Triangle stays BLUE: best move conf=X%"`
- `"Triangle marked GREEN: highest terminal conf=X% >= target"`

**Result:** Clear visibility into why triangles are colored red/blue/green.

---

## Expected Behavior After Fixes

### Iteration Flow:
1. **Initial state:** PV spine with some red circles (low confidence)
2. **Iteration 1:** Red circles become triangles, spawn branch terminals
3. **Triangle coloring:**
   - If highest terminal is **green** → Triangle becomes **green/blue** (satisfied)
   - If all terminals are **red** but best move has confidence → Triangle becomes **blue** (working on it)
   - If all terminals are **red** AND best move lacks confidence → Triangle becomes **red** (needs more work)
4. **Iteration 2+:** Only extend from red circles or red triangles
5. **Exit:** When `min_line_conf >= target` (all PV nodes satisfied)

### Node Counts:
- **Before fix:** Could create 100+ nodes (excessive branching)
- **After fix:** Should create 20-50 nodes typically (more efficient)

### Triangle Colors:
- 🔴▲ **Red triangle:** Has branches, but best move still lacks confidence (needs re-extension)
- 🔵▲ **Blue triangle:** Has branches, working on it, best move is OK (wait for terminals to resolve)
- 🟢▲ **Green triangle:** Has branches with green terminals OR confidence >= target (satisfied)

---

## How to Verify

### Check Backend Logs (Terminal)

You should now see console output like:
```
================================================================================
🌳 INITIAL TREE (target=80%)
================================================================================

📏 PV SPINE (horizontal line):
  🟢■[85%] → 🔴●[65%] → 🔴●[72%] → 🟢■[81%]

... (detailed tree structure) ...

================================================================================
🌳 AFTER ITERATION 0 (min_line_conf=65%)
================================================================================

... (shows red circle → blue triangle transformation) ...

================================================================================
🌳 FINAL TREE (iterations=3, min_line_conf=80%)
================================================================================
```

### What to Look For:
1. ✅ Red circles (🔴●) become triangles (🔴▲ or 🔵▲ or 🟢▲)
2. ✅ Triangles with green terminals immediately marked green/blue
3. ✅ Triangles with red terminals checked for recoloring
4. ✅ Only red nodes (🔴● or 🔴▲) in eligible list for next iteration
5. ✅ Loop exits when min_line_conf >= target

### Frontend Logs Should Show:
- **Before raise:** Similar starting point (e.g., 18 PV, 17 red circles)
- **After raise:** Fewer total nodes (e.g., 40-60 instead of 122), more triangles, fewer red circles

---

## Testing Next Steps

Run a confidence raise and check:
1. Does the tree visualization show proper color transitions?
2. Do triangles get marked red/blue/green correctly?
3. Does the loop exit at a reasonable number of nodes?
4. Are red circles fully transformed to triangles?

If issues persist, look for these patterns in backend logs:
- **"Triangle marked RED"** - recoloring detected insufficient best move
- **"Triangle marked GREEN"** - highest terminal was green
- **"Triangle stays BLUE"** - best move is OK but confidence not yet perfect
- **"No eligible nodes found, breaking"** - loop exited successfully

