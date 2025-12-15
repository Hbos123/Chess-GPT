# Confidence Tree Console Logging Guide

## Overview

The confidence engine now prints detailed tree visualizations to the console at key points:
1. **INITIAL TREE** - Before any confidence raising iterations
2. **AFTER ITERATION N** - After each expansion iteration
3. **FINAL TREE** - When all iterations complete

## Reading the Output

### Node Symbols

**Shapes:**
- `■` = **Square** (first or last PV node)
- `●` = **Circle** (regular PV or branch terminal node)
- `▲` = **Triangle** (branched node - has had alternates extended from it)

**Colors:**
- 🔴 = **Red** (confidence below threshold OR triangle with insufficient best move)
- 🔵 = **Blue** (triangle with acceptable confidence but below threshold)
- 🟢 = **Green** (confidence at or above threshold)

### Color Rules by Shape

**Circles/Squares:**
- 🔴● = Red circle: confidence < target (needs extension)
- 🟢● = Green circle: confidence >= target (good)
- 🔴■ = Red square: first/last PV node, confidence < target
- 🟢■ = Green square: first/last PV node, confidence >= target

**Triangles:**
- 🔴▲ = Red triangle: `insufficient_confidence=True` (best move lacks confidence after recoloring check)
- 🔵▲ = Blue triangle: branched, confidence < target, but best move is OK
- 🟢▲ = Green triangle: branched, confidence >= target

## Output Sections

### 1. PV SPINE (horizontal line)
Shows the principal variation as a linear sequence from left to right:
```
📏 PV SPINE (horizontal line):
  🟢■[85%] → 🔴●[65%] → 🔴●[72%] → 🟢■[81%]
```

### 2. DETAILED NODE LIST
Lists all nodes with their properties:
```
📋 DETAILED NODE LIST:
  🟢■ pv-0            conf= 85%  move=•
  🔴● pv-1            conf= 65%  move=e4
  🔵▲ pv-2            conf= 72% frozen= 68% init= 72%  move=Nf3
  🔴● iter-alt-0      conf= 55%  move=e2e4
```

**Fields:**
- `conf` = current confidence percentage
- `frozen` = frozen confidence (for triangles, based on terminal branch nodes)
- `init` = initial confidence before branching
- `move` = the move that led to this position

### 3. TREE STRUCTURE
Shows parent-child relationships:
```
🌲 TREE STRUCTURE:
└─ 🟢■ pv-0 [85%] START
   ├─ 🔴● pv-1 [65%] e4
   │  ├─ 🔵▲ pv-2 [72%] Nf3
   │  │  ├─ 🟢● iter-alt-0 [82%] d4
   │  │  └─ 🔴● iter-alt-1 [68%] c4
   │  └─ 🟢● pv-3 [81%] d5
```

### 4. STATISTICS
Summary counts:
```
📊 STATISTICS:
  Total nodes: 12
  PV nodes: 4
  Triangles: 2 (🔴1 🔵0 🟢1)
  Circles: 6 (🔴3 🟢3)
```

## What to Look For

### Normal Behavior:
1. **Red circles → Blue triangles**: Low-confidence circles should become blue triangles when extended
2. **Branches grow**: Each iteration should add new nodes as children of triangles
3. **Green terminals**: Branches should stop when they reach green nodes (>= target)
4. **Distance cap**: Branches stop when `ply_from_S0` exceeds 18

### Problem Indicators:
1. **Red triangles**: If many triangles are red, recoloring detected insufficient confidence in best moves
2. **Too many iterations**: If iterations exceed ~10-20, something may be stuck
3. **Circles remain red**: If red circles don't become triangles, extension logic isn't working
4. **Missing branches**: If tree structure shows no children for red triangles, branching failed

## Example Flow

### Initial State:
```
🟢■[85%] → 🔴●[65%] → 🔴●[72%] → 🟢■[81%]
```
PV spine with 2 red circles that need confidence raising.

### After Iteration 1:
```
🟢■[85%] → 🔵▲[68%] → 🔴●[72%] → 🟢■[81%]
           └─ 🟢●[82%] (extended branch)
```
First red circle became blue triangle, spawned green terminal branch.

### After Iteration 2:
```
🟢■[85%] → 🔵▲[68%] → 🔵▲[74%] → 🟢■[81%]
           │          └─ 🔴●[71%] (extended branch)
           └─ 🟢●[82%]
```
Second red circle became blue triangle, spawned red terminal (needs more work).

### Final State:
```
🟢■[85%] → 🔵▲[68%] → 🟢▲[78%] → 🟢■[81%]
           │          └─ 🟢●[82%]
           └─ 🟢●[82%]
```
All nodes above threshold or properly triangulated.

## Debugging Tips

1. **Compare INITIAL vs FINAL**: Check if red circles decreased
2. **Check triangle colors**: Red triangles indicate recoloring found issues
3. **Verify branch structure**: Use tree structure view to ensure branches connect properly
4. **Watch node counts**: Should grow with each iteration (unless hitting caps)
5. **Monitor ply_from_S0**: Should not exceed 18 for any branch terminal

## Legend Summary

| Symbol | Meaning |
|--------|---------|
| 🔴● | Red circle - needs extension |
| 🟢● | Green circle - confidence OK |
| 🔴▲ | Red triangle - best move lacks confidence |
| 🔵▲ | Blue triangle - branched, working on it |
| 🟢▲ | Green triangle - branched and confident |
| 🔴■ | Red square - first/last PV, low confidence |
| 🟢■ | Green square - first/last PV, good confidence |

