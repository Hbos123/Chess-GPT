# 🎯 Smart Annotation Filtering System

## Problem Solved

**Old Behavior:**
- LLM receives 14 themes in analysis data
- System highlighted ALL themes with non-zero scores
- Board showed themes LLM never mentioned
- Confusing and cluttered

**New Behavior:**
- LLM receives same data
- System parses LLM response text
- ONLY highlights themes/tags actually mentioned
- Clean, relevant annotations

---

## Implementation

### **1. Comprehensive Theme Dictionary** (`themeDictionary.ts`)

Maps each theme code to all possible natural language variations:

```typescript
{
  code: 'S_CENTER_SPACE',
  primary: ['center', 'central', 'centre'],
  synonyms: ['middle', 'core', 'd4', 'e4', 'd5', 'e5'],
  related: ['space', 'control', 'occupy', 'dominate'],
  negations: ['lose center', 'give up center']
}
```

**Coverage for all 14 themes:**
- ✅ S_CENTER_SPACE (center, central, control)
- ✅ S_SPACE (space, room, territory, cramped)
- ✅ S_PAWN (pawn structure, isolated, doubled, passed)
- ✅ S_KING (king safety, exposed, shield, castled)
- ✅ S_ACTIVITY (piece activity, mobility, active)
- ✅ S_DEV (development, develop, mobilize)
- ✅ S_THREATS (threat, attack, pressure, danger)
- ✅ S_TACTICS (combination, fork, pin, skewer)
- ✅ S_BREAKS (pawn break, lever, storm)
- ✅ S_PROMOTION (passed pawn, queening, runner)
- ✅ S_LANES (file, diagonal, open, battery)
- ✅ S_COLOR_COMPLEX (dark squares, light squares, holes)
- ✅ S_TRADES (exchange, swap, simplify)
- ✅ S_PROPHYLAXIS (prevent, restrain, stop)

---

### **2. Smart Tag Matching**

Tags matched by:
- **Keyword patterns** (e.g., "attacking queen" → threat.capture)
- **Square mentions** (e.g., "c3" → any tag involving c3)
- **Piece references** (e.g., "knight on c3" → tags with Nc3)
- **Tactical terms** (e.g., "fork" → tactic.fork)

**Common tag patterns:**
```typescript
{
  'threat.capture': ['attacking', 'attack', 'capture', 'threat', 'hanging'],
  'threat.fork': ['fork', 'double attack', 'attacks two'],
  'threat.pin': ['pin', 'pinned', 'cannot move'],
  'outpost': ['outpost', 'strong square', 'stable'],
  'file.open': ['open file', 'open lane'],
  'bishop.pair': ['bishop pair', 'two bishops'],
  'pawn.passed': ['passed pawn', 'passer', 'runner'],
  // ... 20+ more patterns
}
```

---

### **3. Filtering Algorithm**

```typescript
// Parse LLM response
const parsed = parseLLMResponse(llmText, engineData, fen);

// parsed.themes only contains themes LLM mentioned
// parsed.tags only contains tags LLM mentioned

// Generate annotations ONLY for mentioned items
const themeAnnotations = generateThemeAnnotations(
  parsed.themes,  // ← Filtered list!
  parsed.tags,    // ← Filtered list!
  engineData,
  fen,
  side
);
```

---

## Examples

### **Example 1: Center Focus**

**LLM Response:**
> "White is better due to strong central control. The pieces on d4 and e4 dominate the center."

**Detected:**
- ✅ Theme: S_CENTER_SPACE (keywords: "central control", "center", "d4", "e4")

**Annotations:**
- 🟢 Highlight d4, e4, d5, e5
- 🟢 Arrows showing central control

**NOT highlighted:**
- ❌ S_KING (not mentioned)
- ❌ S_PAWN (not mentioned)
- ❌ S_ACTIVITY (not mentioned)

---

### **Example 2: Threat Focused**

**LLM Response:**
> "Black is better. The knight on c3 is attacking the queen on d5, forcing it to move."

**Detected:**
- ✅ Theme: S_THREATS (keywords: "attacking", "forcing")
- ✅ Tag: threat.capture.more_value (keywords: "knight on c3", "attacking queen", "d5")

**Annotations:**
- 🔴 Red arrow: Nc3 → Qd5
- 🔴 Red highlight: d5 square

**NOT highlighted:**
- ❌ Center control (present in data but not mentioned)
- ❌ Development (present but not mentioned)

---

### **Example 3: Multi-Theme**

**LLM Response:**
> "White is winning. Strong central control and the king is very safe after castling. The bishop pair also gives long-term advantage."

**Detected:**
- ✅ S_CENTER_SPACE ("central control")
- ✅ S_KING ("king is very safe", "castling")
- ✅ Tag: bishop.pair ("bishop pair")

**Annotations:**
- 🟢 Center squares highlighted
- 🟡 King + pawn shield highlighted
- 🔷 Both bishops highlighted

**NOT highlighted:**
- ❌ S_ACTIVITY (high score but not mentioned)
- ❌ S_LANES (data exists but not discussed)

---

### **Example 4: Negations Count**

**LLM Response:**
> "The position is balanced, though White has a slightly weak king with no pawn shield."

**Detected:**
- ✅ S_KING ("weak king", "no pawn shield" - negation counts!)

**Annotations:**
- 🔴 King highlighted (exposed)
- 🔴 Missing shield pawns marked

---

## Matching Logic

### **Primary Keywords** (High confidence)
```typescript
if (text.includes('center') || text.includes('central'))
  → S_CENTER_SPACE
```

### **Synonyms** (Medium confidence)
```typescript
if (text.includes('middle') || text.includes('core'))
  → S_CENTER_SPACE
```

### **Related + Primary** (Contextual)
```typescript
if (text.includes('central') && text.includes('control'))
  → S_CENTER_SPACE
```

### **Negations** (Still counts)
```typescript
if (text.includes('weak center') || text.includes('lose center'))
  → S_CENTER_SPACE (negatively)
```

---

## Benefits

### **1. Relevance** ✅
Only shows what LLM is talking about

### **2. Clarity** ✅
No random highlights that confuse users

### **3. Education** ✅
Visual reinforcement of what's being explained

### **4. Accuracy** ✅
Comprehensive keyword coverage prevents false negatives

### **5. Robustness** ✅
Handles synonyms, related terms, and negations

---

## Technical Details

### **Dictionary Structure:**
```typescript
interface ThemeKeywords {
  code: string;           // 'S_CENTER_SPACE'
  primary: string[];      // Main keywords
  synonyms: string[];     // Alternate terms
  related: string[];      // Context words
  negations: string[];    // Negative mentions
}
```

### **Matching Functions:**
- `isThemeMentioned(code, text)` → boolean
- `extractMentionedThemes(text)` → string[]
- `isTagMentioned(tag, text)` → boolean
- `filterMentionedThemes(themes, text)` → string[]

### **Integration:**
```typescript
// In applyLLMAnnotations()
const parsed = parseLLMResponse(llmText, engineData, fen);
// parsed.themes = only themes LLM mentioned
// parsed.tags = only tags LLM mentioned

generateThemeAnnotations(parsed.themes, parsed.tags, ...)
// Only generates annotations for mentioned items
```

---

## Testing Examples

**Test 1: Mention center only**
```
LLM: "Good central control"
Expected: ✅ Center highlights only
```

**Test 2: Mention threat**
```
LLM: "Knight attacking queen on c3→d5"
Expected: ✅ Red arrow Nc3→Qd5 only
```

**Test 3: Mention multiple**
```
LLM: "Strong center and safe king"
Expected: ✅ Center + king highlights
```

**Test 4: Generic response**
```
LLM: "White is better"
Expected: ❌ No theme-based highlights (only move arrows)
```

---

## Result

**Before:**
- 🎨 10+ highlights every response (overwhelming)
- 🔴 Themes user wasn't told about
- 🤷 Confusing what's relevant

**After:**
- ✅ 2-5 precise highlights (clean)
- ✅ Only what LLM explains
- 🎯 Clear visual reinforcement

**The board now acts as a laser pointer for the LLM's explanations!** 🎯✨

