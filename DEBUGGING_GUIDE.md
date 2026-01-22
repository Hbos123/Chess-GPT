# Debugging Guide - PGN Operations

## 🔍 **Comprehensive Logging Added**

I've added detailed console logging to diagnose exactly where the issue is happening.

---

## 📊 **Console Logs to Watch:**

### **When you perform an operation, you'll see:**

### **1. Delete Move:**
```
[PGNViewer] Delete move button clicked
[PGNViewer] Calling onDeleteMove with node: {...}
🗑️ DELETE MOVE CALLED
Node to delete: {...}
Current tree before delete: {...}
Tree cloned
Navigated to node
Delete operation result: {...}
New PGN after delete: "..."
Setting new tree...
Tree version increment: X → Y
✅ Delete move complete
```

### **2. Delete Variation:**
```
[PGNViewer] Delete variation button clicked
[PGNViewer] Calling onDeleteVariation with node: {...}
❌ DELETE VARIATION CALLED
Node to delete: {...}
Delete variation result: {...}
New PGN after delete variation: "..."
✅ Delete variation complete
```

### **3. Promote Variation:**
```
[PGNViewer] Promote variation button clicked
[PGNViewer] Calling onPromoteVariation with node: {...}
⬆️ PROMOTE VARIATION CALLED
Node to promote: {...}
Promote operation result: true/false
New PGN after promote: "..."
✅ Promote variation complete
```

### **4. Add Comment:**
```
[PGNViewer] Add comment button clicked
[PGNViewer] Opening comment editor for node: {...}
[User types and clicks Save]
[PGNViewer] Save comment clicked
[PGNViewer] Comment text: "..."
[PGNViewer] Calling onAddComment with: {...} "..."
💬 ADD COMMENT CALLED
Node: {...}
Comment: "..."
Comment added to tree
New PGN with comment: "..."
Version increment for comment: X → Y
✅ Add comment complete
```

### **5. Tree Cloning:**
```
[MoveTree] Cloning tree...
[MoveTree] Current node path: ["0", "1", "2"]
[MoveTree] Clone complete, current node: "Nf3"
```

### **6. PGN Generation:**
```
[MoveTree] Generating PGN from root...
[MoveTree] Generated PGN: "1. e4 e5 2. Nf3..."
```

---

## 🎯 **How to Diagnose:**

### **Test Each Operation:**

1. **Open browser console** (F12 or Cmd+Option+I)
2. **Perform operation** (right-click → delete/promote/comment)
3. **Watch console logs**
4. **Look for:**
   - ✅ All steps completing
   - ❌ Any errors
   - ⚠️ Missing logs (operation not called)

---

## 🔍 **What to Look For:**

### **If Delete Doesn't Work:**

**Check console for:**
```
Q: Do you see "[PGNViewer] Delete move button clicked"?
   NO → Context menu not working
   YES → Continue...

Q: Do you see "🗑️ DELETE MOVE CALLED"?
   NO → Handler not connected
   YES → Continue...

Q: Do you see "Delete operation result: {...}"?
   NO → Delete function failing
   YES → Continue...

Q: Is the result NULL?
   YES → Parent is null, can't delete root
   NO → Continue...

Q: Do you see "New PGN after delete"?
   NO → PGN generation failing
   YES → Continue...

Q: Do you see "Tree version increment"?
   NO → State not updating
   YES → React should re-render
```

### **If Comments Don't Show:**

**Check console for:**
```
Q: Do you see comment editor open?
   NO → Context menu issue
   YES → Continue...

Q: After typing and clicking Save, see "Save comment clicked"?
   NO → Button not working
   YES → Continue...

Q: See "💬 ADD COMMENT CALLED"?
   NO → Handler not connected
   YES → Continue...

Q: See "New PGN with comment"?
   NO → Comment not added to tree
   YES → Check if comment is in PGN string

Q: See "✅ Add comment complete"?
   NO → Operation failed
   YES → Should work (check PGN string in logs)
```

---

## 🐛 **Potential Issues to Check:**

### **Issue 1: Node Not Found**
```
If you see errors about node not found:
→ The clone might not be finding the right node
→ Check the "Current node path" log
```

### **Issue 2: Parent is Null**
```
If delete returns null parent:
→ Can't delete root node
→ Can only delete moves that have a parent
```

### **Issue 3: PGN Not Updating**
```
If PGN string looks same:
→ Check "Generated PGN" log
→ Compare before/after
→ If they're same, operation didn't modify tree
```

### **Issue 4: React Not Re-rendering**
```
If all logs show success but UI doesn't update:
→ Check "Tree version increment" shows new number
→ Check PGNViewer key prop
→ React issue - needs different approach
```

---

## 🧪 **Diagnostic Tests:**

### **Test 1: Simple Delete**
```
1. Play: 1. e4 e5
2. Right-click "1... e5"
3. Delete move
4. Watch console logs
5. Check if PGN becomes empty
```

### **Test 2: Comment**
```
1. Play: 1. e4
2. Right-click "1. e4"
3. Add comment "Test"
4. Save
5. Check console for "New PGN with comment"
6. See if it contains {Test}
```

### **Test 3: Variation**
```
1. Play: 1. e4 e5 2. Nf3
2. Click "1... e5"
3. Play c5
4. Right-click c5
5. Try deleting
6. Watch all logs
```

---

## 📋 **What to Report:**

**When testing, copy:**
1. **All console logs** from the operation
2. **What you clicked**
3. **What you expected**
4. **What happened instead**

**This will show exactly where the issue is!**

---

## 🚀 **Next Steps:**

1. **Test in browser** at http://localhost:3000
2. **Open console** (F12)
3. **Perform operations** (delete, comment, promote)
4. **Check console logs**
5. **Share the logs** if something fails

**The logs will tell us exactly what's going wrong!** 🔍

---

## ✅ **Logging Coverage:**

✅ PGNViewer button clicks
✅ Handler function calls
✅ Tree cloning
✅ Tree operations (delete, promote, comment)
✅ PGN generation
✅ State updates
✅ Version increments
✅ Error catching

**Complete diagnostic coverage!** 🎯

---

**Frontend running:** http://localhost:3000

**Open console and test the operations now!** 🚀
