import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

try:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    import uvicorn
except ImportError as exc:  # pragma: no cover - optional dependency
    raise SystemExit(
        "fastapi and uvicorn are required for the HTTP API. Install with `pip install fastapi uvicorn`."
    ) from exc

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT / "chess-interpretability" / "python-tools"))

from end_to_end_analysis import analyze_position, DEFAULT_ENGINE_PATH, DEFAULT_DUMP_DIR  # noqa: E402


app = FastAPI(title="NNUE Interpretability API")


@app.post("/analyze")
async def analyze(payload: Dict[str, Any]) -> JSONResponse:
    fen = payload.get("fen")
    if not fen:
        return JSONResponse({"error": "fen is required"}, status_code=400)
    engine_path = payload.get("engine_path", DEFAULT_ENGINE_PATH)
    dump_dir = payload.get("dump_dir", DEFAULT_DUMP_DIR)
    result = analyze_position(fen, engine_path=engine_path, dump_dir=dump_dir)
    return JSONResponse(result)


def main():
    port = int(os.environ.get("NNUE_API_PORT", "8088"))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()

