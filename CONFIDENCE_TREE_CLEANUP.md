# Confidence Tree Code Cleanup Summary

## Deprecated/Unused Code Identified and Marked

### 1. `_expand_node()` Method
- **Status**: ✅ DEPRECATED and disabled
- **Location**: `backend/confidence_engine.py:1078`
- **Action**: Method now returns `False` immediately and logs a warning
- **Reason**: Replaced by 3-phase system (Phase 1/2/3)
- **Old Behavior**: Iterative expansion with candidate selection
- **New Behavior**: Direct 3-phase processing

### 2. `_eligible_candidates()` Method
- **Status**: ✅ DEPRECATED and disabled
- **Location**: `backend/confidence_engine.py:709`
- **Action**: Method now returns empty list and logs a warning
- **Reason**: Not used in 3-phase system
- **Old Behavior**: Selected candidates for iterative expansion
- **New Behavior**: All red nodes processed directly in Phase 1

### 3. `mark_branch()` Method
- **Status**: ⚠️ DOCUMENTED as unused by 3-phase system
- **Location**: `backend/confidence_engine.py:166`
- **Action**: Added documentation note
- **Reason**: Only called by deprecated `_expand_node()`
- **Note**: Kept for potential future use or backward compatibility

### 4. `round_robin_counter` Variable
- **Status**: ⚠️ DOCUMENTED as deprecated
- **Location**: `backend/confidence_engine.py:244`
- **Action**: Added comment noting it's only used in deprecated method
- **Reason**: Only used in `_eligible_candidates()` which is deprecated

### 5. `max_iterations` Parameter
- **Status**: ⚠️ DOCUMENTED as unused in 3-phase system
- **Location**: `backend/confidence_engine.py:229, 240`
- **Action**: Added comment explaining it's kept for API compatibility
- **Reason**: Part of API but 3-phase system processes all nodes in one pass

## Active Code (3-Phase System)

### Phase 1: `_extend_branch_from_blue_triangle()` (conversion)
- Converts red nodes to blue triangles
- Called from `run()` method

### Phase 2: `_extend_branch_from_blue_triangle()` (extension)
- Extends branches from blue triangles
- Called from `run()` method

### Phase 3: `_freeze_and_recolor_blue_triangle()` (freezing)
- Freezes and recolors blue triangles
- Called from `run()` method

### Helper Methods (Active)
- `_expand_branch_recursive()`: Recursively extends branches until green or 18 ply
- `refresh_color()`: ✅ FIXED - now makes triangles green (not blue) when >= baseline
- `_load_existing_nodes()`: ✅ FIXED - ignores old colors and refreshes with new logic

## Verification

All deprecated methods will log warnings if called, making it easy to identify any remaining old code paths.

## Next Steps

If no warnings appear in logs after testing, these deprecated methods can be fully removed in a future cleanup:
- `_expand_node()` - can be deleted
- `_eligible_candidates()` - can be deleted
- `round_robin_counter` - can be removed
- `mark_branch()` - evaluate if needed for future features

