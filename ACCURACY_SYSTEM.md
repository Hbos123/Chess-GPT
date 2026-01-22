# Game Review Accuracy System

## Overview

The Chess GPT game review now includes a **comprehensive accuracy scoring system** that rates each move on a 0-100% scale and calculates average accuracy for both players.

---

## 🎯 **Accuracy Calculation Formula**

### **Exponential Decay Formula**

The accuracy system uses a **sophisticated exponential decay formula** that accounts for:
1. The centipawn loss (CPL) from the played move
2. The evaluation of the best move (E) in the position
3. Position-dependent scaling

### **Formula:**

```
Accuracy% = 100 × exp( -CPL / (89.6284023545 + 44.8142011772 × |E|) )
```

**Where:**
- **CPL** = Centipawn Loss (difference between best move and played move)
- **E** = Best move evaluation in **pawns** (clamped to ±24)
- **|E|** = Absolute value of E

### **Formula Components:**

#### **1. Centipawn Loss (CPL)**
```
CPL = best_move_eval - played_move_eval
```

#### **2. Best Move Eval (E)**
```
E = best_move_eval_cp / 100  (convert to pawns)
E = clamp(E, -24, +24)        (limit range)
```

#### **3. Exponential Decay**
The denominator adjusts based on position evaluation:
```
denominator = 89.6284023545 + 44.8142011772 × |E|
```

**Key insight:** Mistakes in winning positions (high |E|) are penalized less harshly than mistakes in equal positions, as the winning side has margin for error.

---

## 📊 **Examples**

### **Example 1: Small Mistake in Equal Position**
- **Best move eval:** E = 0 pawns (0cp)
- **Centipawn loss:** CPL = 30cp

```
denominator = 89.6284023545 + 44.8142011772 × |0| = 89.6284
accuracy = 100 × exp(-30 / 89.6284)
accuracy = 100 × exp(-0.3348)
accuracy = 100 × 0.7155
accuracy = 71.6%
```

✅ **Result: 71.6% accuracy**

---

### **Example 2: Small Mistake in Winning Position**
- **Best move eval:** E = +3 pawns (+300cp)
- **Centipawn loss:** CPL = 30cp

```
denominator = 89.6284 + 44.8142 × |3| = 89.6284 + 134.4426 = 224.071
accuracy = 100 × exp(-30 / 224.071)
accuracy = 100 × exp(-0.1339)
accuracy = 100 × 0.8747
accuracy = 87.5%
```

✅ **Result: 87.5% accuracy** (higher than equal position!)

---

### **Example 3: Large Blunder in Equal Position**
- **Best move eval:** E = 0 pawns
- **Centipawn loss:** CPL = 200cp (blunder)

```
denominator = 89.6284
accuracy = 100 × exp(-200 / 89.6284)
accuracy = 100 × exp(-2.232)
accuracy = 100 × 0.1068
accuracy = 10.7%
```

✅ **Result: 10.7% accuracy**

---

### **Example 4: Large Blunder in Winning Position**
- **Best move eval:** E = +5 pawns (+500cp, clamped to +24)
- **Centipawn loss:** CPL = 200cp

```
E_clamped = min(5, 24) = 5
denominator = 89.6284 + 44.8142 × |5| = 313.699
accuracy = 100 × exp(-200 / 313.699)
accuracy = 100 × exp(-0.6377)
accuracy = 100 × 0.5284
accuracy = 52.8%
```

✅ **Result: 52.8% accuracy** (less harsh penalty!)

---

### **Example 5: Perfect Move (0 CPL)**
- **Any position**
- **Centipawn loss:** CPL = 0

```
accuracy = 100.0%
```

✅ **Result: 100.0% accuracy** (always!)

---

## 🏆 **Default Values**

Moves that don't need accuracy calculation:

| Move Type | Accuracy |
|-----------|----------|
| **Theory moves** | 100.0% |
| **Best moves** | 100.0% |
| **Excellent moves** (0cp loss) | 100.0% |

---

## 📈 **Average Accuracy**

### **Overall Accuracy (Per Player):**

```
Average White Accuracy = (Sum of all White move accuracies) / (Number of White moves)
Average Black Accuracy = (Sum of all Black move accuracies) / (Number of Black moves)
```

### **Phase-Based Accuracy:**

The system automatically divides the game into three phases and calculates accuracy for each:

#### **Phase Detection Rules:**

1. **Opening Phase:**
   - Game starts in the opening phase
   - **Opening ends when ANY of these conditions are met:**
     - ✅ All pieces have moved off their starting squares (≤4 pieces remain on back rank)
     - ✅ Rooks are connected (no pieces between them on back rank)
     - ✅ A non-pawn piece has been captured
   - Typically moves 1-12

2. **Middlegame Phase:**
   - Begins when opening ends (see above)
   - Continues while:
     - At least one queen remains on the board, AND
     - More than 12 pieces remain
   - Typically moves 12-35

3. **Endgame Phase:**
   - Begins when:
     - No queens remain on the board, OR
     - Piece count ≤ 12 pieces total
   - Typically moves 35+

#### **Accuracy Calculated For:**
- ✅ Overall (all moves)
- ✅ Opening phase only
- ✅ Middlegame phase only
- ✅ Endgame phase only

### **Displayed in Review:**

```
Overall Accuracy:
⚪ White: 94.3%
⚫ Black: 91.7%

Phase-Based Accuracy:

📖 Opening (16 moves):
  ⚪ White: 97.2%
  ⚫ Black: 95.8%

⚔️ Middlegame (24 moves):
  ⚪ White: 92.5%
  ⚫ Black: 89.3%

👑 Endgame (8 moves):
  ⚪ White: 91.7%
  ⚫ Black: 88.6%
```

---

## 📄 **PGN with Accuracy**

Each move in the full PGN display now includes its accuracy percentage:

```
1. e4 {100.0%} e5 {100.0%}
2. Nf3 {100.0%} Nc6 {100.0%}
3. Bc4 {98.5%} Nf6 {97.2%}
4. d3 {92.1%} Be7 {95.6%}
5. O-O {100.0%} d6 {89.3%}
```

This appears at the bottom of the game review card under:
```
--- Full PGN with Accuracy ---
```

---

## 💡 **Interpretation Guide**

### **Accuracy Ranges:**

| Range | Interpretation |
|-------|----------------|
| **98-100%** | Near-perfect play |
| **95-97%** | Excellent play, minor inaccuracies |
| **90-94%** | Good play, some mistakes |
| **85-89%** | Decent play, notable errors |
| **80-84%** | Weak play, significant mistakes |
| **< 80%** | Poor play, major blunders |

### **Game-Level Accuracy:**

- **Both players > 95%:** High-quality game
- **One player > 95%, other < 90%:** Skill mismatch or one-sided game
- **Both players < 85%:** Tactical slugfest or both players struggling

---

## 🔍 **What Accuracy Measures**

### **Accuracy measures:**
- ✅ How close each move was to the optimal move
- ✅ Consistency of play across the game
- ✅ Ability to maintain advantages
- ✅ Precision in difficult positions

### **Accuracy does NOT directly measure:**
- ❌ Strategic understanding (only tactical precision)
- ❌ Time pressure effects
- ❌ Opening memorization (theory moves = 100%)
- ❌ Endgame technique vs. calculation

---

## 🎮 **Example Game Review Output**

```
Game Review Complete!

Opening: Ruy Lopez: Morphy Defense

Move Quality:
📖 Theory: 8
✓ Best: 3
✓ Excellent: 6
✓ Good: 4
⚠ Inaccuracies: 3
❌ Mistakes: 2
❌ Blunders: 1

Overall Accuracy:
⚪ White: 94.3%
⚫ Black: 91.7%

Phase-Based Accuracy:

📖 Opening (16 moves):
  ⚪ White: 97.2%
  ⚫ Black: 95.8%

⚔️ Middlegame (24 moves):
  ⚪ White: 92.5%
  ⚫ Black: 89.3%

👑 Endgame (8 moves):
  ⚪ White: 91.7%
  ⚫ Black: 88.6%

The PGN viewer has been updated with detailed analysis!

--- Key Moments ---

Left Opening Theory: 9. a4

Critical Moves (gap >50cp to 2nd best):
  12. Nxd5 (+115cp)
  15. Rxe8+ (+220cp)

Missed Wins:
  18. Qxf7 (+450cp)

Advantage Shifts:
  ±100cp threshold:
    12. Nxd5 (White gains advantage)
  ±300cp threshold:
    18. Qxf7 (White winning)

--- Full PGN with Accuracy ---

1. e4 {100.0%} e5 {100.0%}
2. Nf3 {100.0%} Nc6 {100.0%}
3. Bb5 {100.0%} a6 {100.0%}
4. Ba4 {100.0%} Nf6 {100.0%}
5. O-O {100.0%} Be7 {100.0%}
6. Re1 {100.0%} b5 {100.0%}
7. Bb3 {100.0%} d6 {100.0%}
8. c3 {100.0%} O-O {100.0%}
9. a4 {98.5%} Bg4 {95.2%}
10. h3 {97.1%} Bh5 {94.8%}
11. d3 {93.6%} Rb8 {89.7%}
12. Nxd5 {100.0%} Nxd5 {88.3%}
[... continues for all moves ...]
```

---

## 🛠️ **Implementation Details**

### **Backend (Python):**
- File: `backend/main.py`
- Function: `/review_game` endpoint
- Calculation happens for each move during analysis
- Stored in `accuracy` field of move data

### **Frontend (TypeScript):**
- File: `frontend/app/page.tsx`
- Function: `handleReviewGame()`
- Aggregates accuracy per player
- Formats PGN with accuracy annotations
- Displays in game review summary

---

## 📚 **Benefits**

1. **Quantifiable Performance**: Objective measure of play quality
2. **Player Comparison**: Easy to compare skill levels
3. **Improvement Tracking**: Monitor progress over time
4. **Move-by-Move Detail**: See exactly which moves lowered accuracy
5. **Context Awareness**: Accounts for position evaluation
6. **Fair Scoring**: Adjusts for player perspective (White/Black)

---

**All features are live! Play a game and click "Review Game" to see your accuracy scores!** 🎉

