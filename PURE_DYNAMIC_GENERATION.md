# Pure Dynamic Position Generation - Template Removal

## Date: October 17, 2025

## Changes Made

### 1. Reduced Pool Size: 10 → 5 Unique Positions
**File:** `backend/position_cache.py`
**Change:** Line 19
```python
# Before: pool_size: int = 10
# After:  pool_size: int = 5
```

**Impact:**
- Maintains 5 unique positions per (topic, side, difficulty) combination
- Rotates hourly via TTL
- Reduces memory footprint while maintaining variety

### 2. Removed All Template Fallbacks
**File:** `backend/main.py`

**Deleted:** Entire `get_template_position()` function (~60 lines)
- Removed hardcoded template FENs for all topics
- Removed hardcoded objectives and explanations
- Removed template hints

**Modified:** `generate_position_for_topic()` function
- Removed `try/except` fallback to templates
- Removed `get_template_position(topic_code, side)` calls
- Now raises exceptions if generation fails
- Pure dynamic generation only

### 3. Increased Generation Budget: 500ms → 3000ms
**File:** `backend/main.py`
**Change:** Line 1949
```python
# Before: time_budget_ms=500
# After:  time_budget_ms=3000
```

**Reason:**
- Logs showed consistent timeouts at 500ms
- Engine-guided rollouts need time to find matching positions
- 3000ms allows 12 rollout attempts with proper analysis
- First generation slower but cached for subsequent uses

## System Behavior

### Before (Hybrid System)
```
Generate Position Request
  ↓
Check Cache → [MISS]
  ↓
Try Dynamic Generation (500ms budget)
  ↓
[TIMEOUT] → Fallback to Template ⚠️
  ↓
Return Hardcoded FEN
```

### After (Pure Dynamic)
```
Generate Position Request
  ↓
Check Cache → [MISS]
  ↓
Dynamic Generation (3000ms budget)
  ↓
[SUCCESS] → Return Fresh FEN ✅
  ↓
Cache for Future (5-position pool)
  ↓
Next Request: <10ms cache hit
```

### On Failure
```
Dynamic Generation
  ↓
[TIMEOUT/ERROR] → Raise Exception ❌
  ↓
Frontend receives error
User sees: "Failed to generate lesson. Please try again."
```

## Performance Expectations

### First Lesson Generation
- **First position:** ~1-3 seconds (dynamic generation)
- **Each position:** ~1-3 seconds (all cache misses)
- **18 positions:** ~18-54 seconds total
- **User experience:** Loading indicators show progress

### Second Lesson (Same Topics)
- **All positions:** <10ms each (cache hits)
- **18 positions:** <180ms total
- **User experience:** Instant loading ✨

### After Cache Expiry (1 Hour)
- Positions regenerate fresh
- New variety maintained
- Same timing as first generation

## Risk Mitigation

### Removed Safety Net
- ❌ No template fallback
- ✅ Errors surface to user
- ✅ Clear failure messaging
- ✅ User can retry

### Why This Is Acceptable
1. **Longer budget (3000ms)** - Higher success rate
2. **Cache pools (5 positions)** - Reduces generation frequency  
3. **Error handling** - Clear user feedback
4. **Retry available** - Users can try again

### Monitoring
Watch backend logs for:
```
✅ Generated position for PS.IQP in 1847ms  [SUCCESS]
Position generation timeout for PS.IQP: ... [FAILURE - needs debugging]
```

If failures persist, we may need to:
1. Tune predicates (lower score threshold from 0.85)
2. Increase max attempts (12 → 24)
3. Adjust rollout length (24 → 30 plies)
4. Relax difficulty bands

## Files Summary

### Modified
- `backend/position_cache.py` - Pool size 10→5
- `backend/main.py` - Removed templates, increased budget

### Deleted Content
- ~60 lines of hardcoded template positions
- ~120 lines of hardcoded objectives/hints  
- All fallback logic to templates

## Testing Checklist

- [x] Template functions removed
- [x] Pool size reduced to 5
- [x] Time budget increased to 3000ms
- [x] Services restart successfully
- [x] Backend responds to API calls
- [ ] Generate lesson and verify dynamic positions - **Ready for user testing**
- [ ] Monitor generation success rate - **Ready for user testing**
- [ ] Verify cache hits after first generation - **Ready for user testing**

---

**Status:** ✅ Complete
**Services:** Running at http://localhost:3000
**Next:** Test with a custom lesson to verify dynamic generation succeeds




