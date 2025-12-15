<!-- 3cb7b888-d73f-453b-95ec-9187efef4176 9f46425a-f8c1-4fce-beb7-bde30a49e6d5 -->
# Personal Review System Enhancement

## Issues Identified

**Critical Bugs:**

1. All three charts show identical "Performance by Phase" data (bug in frontend chart rendering)
2. Narrative shows 82.8% but charts show 0.0% (data inconsistency)
3. No loading indicator while fetching/analyzing games
4. Backend returns phase_stats as top-level object, but charts expect nested accuracy/cp_loss structure

**Missing Features:**

5. No accuracy by color (White vs Black)
6. No time control analysis
7. No theme-based weakness detection
8. LLM doesn't ask clarifying questions before long analysis

## Implementation Plan

### Phase 1: Fix Critical Display Bugs

#### 1.1 Fix Chart Data Structure (backend/tool_executor.py:366-370)

**Problem:** Charts receive `phase_stats` object directly, but PersonalReviewCharts expects nested structure.

**Current:**

```python
"charts": {
    "accuracy_by_phase": aggregated.get("phase_stats", {}),  # Wrong
    "opening_performance": aggregated.get("opening_performance", [])[:5],
    "common_mistakes": aggregated.get("theme_frequency", [])[:5]
}
```

**Fix:**

```python
"charts": {
    "accuracy_by_phase": aggregated.get("phase_stats", {}),  # Keep as-is for phase chart
    "opening_performance": aggregated.get("opening_performance", [])[:5],
    "common_mistakes": aggregated.get("theme_frequency", [])[:5],
    "phase_stats": aggregated.get("phase_stats", {}),  # Add explicit phase_stats
    "accuracy_by_rating": aggregated.get("accuracy_by_rating", []),  # Add rating data
    "win_rate_by_phase": aggregated.get("win_rate_by_phase", {})  # Add win rate
}
```

#### 1.2 Fix Frontend Chart Rendering (frontend/app/page.tsx:579-596)

**Problem:** All three charts get same `data` object, PersonalReviewCharts needs full aggregated data.

**Current:**

```typescript
Object.entries(chartData).forEach(([chartType, data]) => {
  setMessages(prev => [...prev, {
    meta: {
      personalReviewChart: {
        type: chartType,
        data: data  // Wrong - individual chart data
      }
    }
  }]);
});
```

**Fix:** Send complete chart data object once:

```typescript
setMessages(prev => [...prev, {
  role: 'assistant',
  content: '📊 Visual Analysis\n\nClick to expand details.',
  meta: {
    personalReviewChart: {
      data: result.charts  // Full object with all chart types
    }
  }
}]);
```

### Phase 2: Add Loading Indicators

#### 2.1 Add System Messages During Fetch (frontend/app/page.tsx:553)

Before tool call:

```typescript
if (hasPersonalReview) {
  // Add loading message
  addSystemMessage("🔍 Fetching games from " + platform + "...");
  
  const personalReviewTool = data.tool_calls?.find(...);
  
  if (result.success && result.narrative) {
    // Update loading to analyzing
    addSystemMessage("⚙️ Analyzing " + result.games_analyzed + " games with Stockfish...");
  }
}
```

#### 2.2 Add Backend Progress Logging (backend/tool_executor.py:305)

Add print statements that frontend can capture:

```python
print(f"📥 Fetching games for {username} from {platform}...")
games = await self.game_fetcher.fetch_games(...)
print(f"✅ Fetched {len(games)} games")

print(f"🔍 Analyzing {games_to_analyze} games with Stockfish (depth {depth})...")
for idx, game in enumerate(games[:games_to_analyze]):
    print(f"   📊 Analyzing game {idx+1}/{games_to_analyze}...")
```

### Phase 3: Enhance Backend Aggregation

#### 3.1 Add Color-Based Accuracy (backend/personal_review_aggregator.py)

Add new method after `_calculate_phase_stats` (~line 250):

```python
def _calculate_accuracy_by_color(self, games: List[Dict]) -> Dict:
    """Calculate accuracy split by playing color"""
    white_games = [g for g in games if g.get('metadata', {}).get('player_color') == 'white']
    black_games = [g for g in games if g.get('metadata', {}).get('player_color') == 'black']
    
    white_acc = self._avg_accuracy_from_games(white_games) if white_games else 0
    black_acc = self._avg_accuracy_from_games(black_games) if black_games else 0
    
    return {
        'white': {
            'accuracy': white_acc,
            'game_count': len(white_games),
            'win_rate': self._calculate_win_rate(white_games)
        },
        'black': {
            'accuracy': black_acc,
            'game_count': len(black_games),
            'win_rate': self._calculate_win_rate(black_games)
        }
    }
```

Call in `aggregate()` method (~line 59):

```python
accuracy_by_color = self._calculate_accuracy_by_color(filtered_games)
```

Add to return dict (~line 82):

```python
"accuracy_by_color": accuracy_by_color,
```

#### 3.2 Add Time Control Analysis (backend/personal_review_aggregator.py)

Add new method:

```python
def _calculate_performance_by_time_control(self, games: List[Dict]) -> List[Dict]:
    """Group performance by time control (blitz/rapid/classical)"""
    time_controls = defaultdict(list)
    
    for game in games:
        tc = game.get('metadata', {}).get('time_control', 'unknown')
        # Classify: <180s = blitz, <900s = rapid, else classical
        if isinstance(tc, int):
            if tc < 180:
                category = 'blitz'
            elif tc < 900:
                category = 'rapid'
            else:
                category = 'classical'
        else:
            category = 'unknown'
        
        time_controls[category].append(game)
    
    results = []
    for tc, tc_games in time_controls.items():
        if tc_games:
            results.append({
                'time_control': tc,
                'accuracy': self._avg_accuracy_from_games(tc_games),
                'game_count': len(tc_games),
                'win_rate': self._calculate_win_rate(tc_games)
            })
    
    return sorted(results, key=lambda x: x['game_count'], reverse=True)
```

#### 3.3 Add Theme-Based Weakness Detection (backend/personal_review_aggregator.py)

Enhance existing `_calculate_theme_frequency` (~line 350) to identify weaknesses:

```python
def _calculate_theme_frequency(self, games: List[Dict]) -> List[Dict]:
    # ... existing code ...
    
    # Add weakness classification
    for theme_data in sorted_themes:
        error_rate = theme_data.get('error_count', 0) / theme_data.get('occurrence_count', 1)
        if error_rate > 0.4:  # 40%+ error rate
            theme_data['weakness_level'] = 'critical'
        elif error_rate > 0.25:
            theme_data['weakness_level'] = 'moderate'
        else:
            theme_data['weakness_level'] = 'minor'
    
    return sorted_themes
```

### Phase 4: Improve LLM Interaction

#### 4.1 Update System Prompt (backend/enhanced_system_prompt.py:38-40)

Add guidance for personal reviews:

```
- User: "Review my games" or "Analyze my profile" → If appropriate, ask what they want to know:
  "I can analyze your recent games! What would you like to focus on?
                                                                                 - Overall performance and accuracy
                                                                                 - Specific openings or phases
                                                                                 - Tactical vs positional weaknesses
                                                                                 - Or I can give you a complete overview"
  
  Then call fetch_and_review_games with appropriate parameters.
```

#### 4.2 Add Conversational Decision Logic (backend/tool_executor.py)

Modify `_generate_review_narrative` to adapt based on what was found:

```python
# After calculating stats, add contextual insights
if avg_accuracy > 90:
    narrative += "\n🎉 Excellent overall performance! You're playing at a very high level.\n"
elif avg_accuracy < 70:
    narrative += "\n💪 There's significant room for improvement. Focus on reducing mistakes.\n"

# Suggest focus areas based on data
weakest_areas = []
if phase_stats.get('endgame', {}).get('accuracy', 100) < 75:
    weakest_areas.append('endgame technique')
if summary.get('tactical_error_rate', 0) > 0.3:
    weakest_areas.append('tactical awareness')

if weakest_areas:
    narrative += f"\n**Recommended focus:** {', '.join(weakest_areas)}\n"
```

### Phase 5: Update Frontend Chart Component

#### 5.1 Enhance PersonalReviewCharts (frontend/components/PersonalReviewCharts.tsx:14)

Add color-based accuracy chart:

```typescript
const accuracyByColor = data.accuracy_by_color || {};

// After phase stats section
{Object.keys(accuracyByColor).length > 0 && (
  <div className="chart-section">
    <h4>Performance by Color</h4>
    <div className="color-comparison">
      {Object.entries(accuracyByColor).map(([color, stats]: [string, any]) => (
        <div key={color} className="color-stat-card">
          <div className="color-icon">
            {color === 'white' ? '⚪' : '⚫'}
          </div>
          <div className="color-name">{color.toUpperCase()}</div>
          <div className="color-accuracy">{stats.accuracy?.toFixed(1)}%</div>
          <div className="color-games">{stats.game_count} games</div>
          <div className="color-winrate">Win Rate: {(stats.win_rate * 100).toFixed(0)}%</div>
        </div>
      ))}
    </div>
  </div>
)}
```

Add time control chart similarly at ~line 150.

## Files to Modify

1. **backend/tool_executor.py** - Fix chart data structure, add loading messages
2. **backend/personal_review_aggregator.py** - Add color/time/theme analysis methods
3. **backend/enhanced_system_prompt.py** - Add LLM guidance for personal reviews
4. **frontend/app/page.tsx** - Fix chart rendering, add loading indicators
5. **frontend/components/PersonalReviewCharts.tsx** - Add color/time charts, fix data access
6. **frontend/styles/chatUI.css** - Add styles for new chart types

## Testing Plan

1. Type "review my chess.com profile HKB03"
2. Verify loading messages appear
3. Verify narrative shows correct stats
4. Verify three different charts render correctly:

                                                                                                                                                                                                - Accuracy by Phase (with actual percentages)
                                                                                                                                                                                                - Opening Performance (list of openings)
                                                                                                                                                                                                - Common Mistakes (theme list)

5. Verify new charts appear:

                                                                                                                                                                                                - Accuracy by Color (White vs Black)
                                                                                                                                                                                                - Performance by Time Control

6. Verify LLM asks clarifying questions when appropriate

### To-dos

- [ ] Create confidence_engine.py with Level-1 iterative algorithm
- [ ] Add confidence to /analyze_move (played and best) and raise_move endpoint
- [ ] Add position_confidence to /analyze_position and raise_position endpoint
- [ ] Add ConfidenceBadge to assistant messages with inline panel
- [ ] Wire badge controls to raise confidence via new endpoints
- [ ] Define Confidence types and plumb through meta on messages
- [ ] Unit tests for confidence math and branching caps
- [ ] UI tests for badge/panel and state updates