# How To Start Backend and See Logs

## Quick Start

**In your terminal, run:**

```bash
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT
./start_backend.sh
```

**OR if that doesn't work:**

```bash
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/backend
python3 main.py
```

## What You Should See

The backend will start and show:
```
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

## Where The Logs Appear

**All the debugging logs will print in THIS terminal window** where you started the backend.

When you click "Raise Confidence" in your browser, you'll see output like:

```
[Confidence] Building PV spine: 18 moves

====================================================================================================
📋 BEFORE ITERATIVE RAISE (target=80%) - FULL NODE DETAILS
====================================================================================================
Total nodes: 18

[  0] pv-0                 | parent=None                  | conf= 85% | ply= 1 | move=e4      
      has_branches=False | frozen=-    | initial=-    | insufficient=False
      FEN: rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3

... (lots of detailed output)

────────────────────────────────────────────────────────────────────────────────
[Confidence] 🔄 ITERATION 0: min_line_conf=65, total_nodes=18
────────────────────────────────────────────────────────────────────────────────

✅ ELIGIBLE NODES (5):
   pv-1            - RED CIRCLE        conf=65%
   ...
```

## Troubleshooting

### If you get "Permission Denied"

```bash
chmod +x start_backend.sh
./start_backend.sh
```

### If you get "module not found" errors

```bash
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT/backend
pip3 install -r requirements.txt
python3 main.py
```

### If you want to see logs in a file

```bash
cd /Users/hugobosnic/Desktop/Projects/Chess-GPT
./start_backend.sh 2>&1 | tee backend_logs.txt
```

This will show logs in terminal AND save them to `backend_logs.txt`

## Next Steps

1. **Start backend** (leave terminal open)
2. **Open browser** to your app
3. **Make a move** 
4. **Click "Raise Confidence"**
5. **Switch back to terminal** - scroll up to see all the detailed logs
6. **Copy the logs** starting from `📋 BEFORE ITERATIVE RAISE` through `📋 FINAL STATE`
7. **Send me the logs** so I can analyze what's happening!

## What I Need To See

Copy everything from the backend terminal starting from:
- `[Confidence] Building PV spine`
- Through all the `📋 BEFORE/AFTER` dumps
- Through all the `✅ ELIGIBLE NODES` lists
- To `📋 FINAL STATE`

That will show me exactly what's happening! 🔍

