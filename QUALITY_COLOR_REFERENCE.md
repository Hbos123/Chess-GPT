# Move Quality Color Reference

## 🎨 **COMPLETE COLOR CODING SYSTEM**

---

## 📊 **CP Loss Ranges & Colors:**

### **1. BEST** (Dark Green `#15803d`)
```
CP Loss: < 10cp
Word colored: "best"
Sample: "1.e4 is the best move. I played 1...e5 to fight for center."
                  ↑ Only "best" is dark green
```

---

### **2. EXCELLENT** (Green `#16a34a`)
```
CP Loss: 10-25cp
Word colored: "excellent"
Sample: "2.Nf3 is an excellent move. I played 2...Nc6 to develop."
                     ↑ Only "excellent" is green
```

---

### **3. GOOD** (Light Green `#22c55e`)
```
CP Loss: 25-50cp
Word colored: "good"
Sample: "3.Nc3 is a good move. I played 3...d6 to prepare e5."
                   ↑ Only "good" is light green
```

---

### **4. INACCURACY** (Yellow `#eab308`)
```
CP Loss: 50-100cp
Word colored: "inaccuracy"
Sample: "4.h3 is an inaccuracy. I played 4...d5 to seize center."
                   ↑ Only "inaccuracy" is yellow
```

---

### **5. MISTAKE** (Orange `#f97316`)
```
CP Loss: 100-200cp
Word colored: "mistake"
Sample: "5.f3 is a mistake. I played 5...Qh4+ to exploit weakness."
                  ↑ Only "mistake" is orange
```

---

### **6. BLUNDER** (Red `#dc2626`)
```
CP Loss: 200cp+
Word colored: "blunder"
Sample: "6.Kd2 is a blunder. I played 6...Qxf2 winning the queen."
                   ↑ Only "blunder" is red
```

---

## 🎯 **Visual Examples:**

### **Example Sentence Breakdown:**

```
"1.e4 is the best move. I played 1...e5 to control center."

Normal: "1.e4 is the "
COLORED: "best"  ← Dark green (#15803d)
Normal: " move. I played 1...e5 to control center."
```

### **Another Example:**

```
"3.h4 is an inaccuracy. I played 3...d5 to punish."

Normal: "3.h4 is an "
COLORED: "inaccuracy"  ← Yellow (#eab308)
Normal: ". I played 3...d5 to punish."
```

---

## 📋 **Complete Reference Table:**

| CP Loss | Quality | Color | Hex | Sample |
|---------|---------|-------|-----|--------|
| **0-9** | best | Dark Green | `#15803d` | "1.e4 is the best move" |
| **10-24** | excellent | Green | `#16a34a` | "2.Nf3 is an excellent move" |
| **25-49** | good | Light Green | `#22c55e` | "3.Nc3 is a good move" |
| **50-99** | inaccuracy | Yellow | `#eab308` | "4.h3 is an inaccuracy" |
| **100-199** | mistake | Orange | `#f97316` | "5.f3 is a mistake" |
| **200+** | blunder | Red | `#dc2626` | "6.Kd2 is a blunder" |

---

## 🖱️ **Hover Tooltip Format:**

```
BEST | CP Loss: 5cp | Best: e4
EXCELLENT | CP Loss: 15cp | Best: Nf3
GOOD | CP Loss: 35cp | Best: Bc4
INACCURACY | CP Loss: 75cp | Best: d4
MISTAKE | CP Loss: 150cp | Best: Nf3
BLUNDER | CP Loss: 250cp | Best: O-O
```

---

## 🎨 **Color Palette:**

```
#15803d  ██  Dark Green  (Best)
#16a34a  ██  Green       (Excellent)
#22c55e  ██  Light Green (Good)
#eab308  ██  Yellow      (Inaccuracy)
#f97316  ██  Orange      (Mistake)
#dc2626  ██  Red         (Blunder)
```

**Gradual transition from green (good) to red (bad)!**

---

## 📝 **Sample Sentences for Each Quality:**

### **BEST (< 10cp)** - Dark Green
```
"1.e4 is the best move. I played 1...e5."
         ↑ #15803d

"2.Nf3 is the best move. I played 2...Nc6."
          ↑ #15803d

"Nxe5 is the best move. I played Qe7."
         ↑ #15803d
```

### **EXCELLENT (10-25cp)** - Green
```
"1.d4 is an excellent move. I played 1...Nf6."
            ↑ #16a34a

"2.Nc3 is an excellent move. I played 2...d5."
             ↑ #16a34a

"3.Bf4 is an excellent move. I played 3...c5."
             ↑ #16a34a
```

### **GOOD (25-50cp)** - Light Green
```
"3.Bc4 is a good move. I played 3...Nf6."
            ↑ #22c55e

"4.d3 is a good move. I played 4...d6."
           ↑ #22c55e

"5.h3 is a good move. I played 5...O-O."
           ↑ #22c55e
```

### **INACCURACY (50-100cp)** - Yellow
```
"4.h3 is an inaccuracy. I played 4...d5."
            ↑ #eab308

"5.a3 is an inaccuracy. I played 5...Nf6."
            ↑ #eab308

"6.Qe2 is an inaccuracy. I played 6...Bg4."
              ↑ #eab308
```

### **MISTAKE (100-200cp)** - Orange
```
"5.f3 is a mistake. I played 5...Qh4+."
          ↑ #f97316

"6.g4 is a mistake. I played 6...Bxg4."
          ↑ #f97316

"7.Kd2 is a mistake. I played 7...Qxf2."
            ↑ #f97316
```

### **BLUNDER (200cp+)** - Red
```
"6.Qxd8+ is a blunder. I played 6...Kxd8."
              ↑ #dc2626

"7.Rh3 is a blunder. I played 7...Qxh3."
            ↑ #dc2626

"8.f4 is a blunder. I played 8...Qh4#."
          ↑ #dc2626
```

---

## ✅ **Quick Spotcheck:**

### **Test 1: Best Move (< 10cp)**
```
Input: CP Loss = 5
Output: "1.e4 is the best move."
Color: "best" is #15803d (dark green) ✅
Tooltip: "BEST | CP Loss: 5cp | Best: e4" ✅
```

### **Test 2: Excellent (10-25cp)**
```
Input: CP Loss = 18
Output: "2.Nf3 is an excellent move."
Color: "excellent" is #16a34a (green) ✅
Tooltip: "EXCELLENT | CP Loss: 18cp | Best: Nf3" ✅
```

### **Test 3: Good (25-50cp)**
```
Input: CP Loss = 35
Output: "3.Nc3 is a good move."
Color: "good" is #22c55e (light green) ✅
Tooltip: "GOOD | CP Loss: 35cp | Best: Nc3" ✅
```

### **Test 4: Inaccuracy (50-100cp)**
```
Input: CP Loss = 75
Output: "4.h3 is an inaccuracy."
Color: "inaccuracy" is #eab308 (yellow) ✅
Tooltip: "INACCURACY | CP Loss: 75cp | Best: d4" ✅
```

### **Test 5: Mistake (100-200cp)**
```
Input: CP Loss = 150
Output: "5.f3 is a mistake."
Color: "mistake" is #f97316 (orange) ✅
Tooltip: "MISTAKE | CP Loss: 150cp | Best: Nf3" ✅
```

### **Test 6: Blunder (200cp+)**
```
Input: CP Loss = 300
Output: "6.Kd2 is a blunder."
Color: "blunder" is #dc2626 (red) ✅
Tooltip: "BLUNDER | CP Loss: 300cp | Best: O-O" ✅
```

---

## 🎯 **What Gets Colored:**

```
✅ COLORED:
- best
- excellent
- good
- inaccuracy
- mistake
- blunder

❌ NOT COLORED:
- Numbers (1.e4, 2.Nf3)
- Articles (is, a, the, an)
- Rest of sentence
- "move" word
- Everything else
```

---

## ✅ **Status:**

🟢 **PERFECT**

- ✅ Only operator word colored
- ✅ 6 distinct colors
- ✅ CP ranges defined
- ✅ Tooltips with data
- ✅ Clean & minimalistic
- ✅ Sample sentences provided

---

## 🚀 **Frontend Ready:**

http://localhost:3000

**Test and see beautiful color-coded feedback!** 🎉♟️✨
