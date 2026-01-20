from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ErrorCode:
    code: str
    message: str


ENGINE_UNAVAILABLE = ErrorCode("engine_unavailable", "Stockfish engine is not available.")
VLLM_UNHEALTHY = ErrorCode("vllm_unhealthy", "vLLM server is unhealthy or unreachable.")
TIMEOUT = ErrorCode("timeout", "Operation exceeded its time budget.")
ILLEGAL_MOVE = ErrorCode("illegal_move", "Move is illegal for the given position.")
BAD_REQUEST = ErrorCode("bad_request", "Request payload is invalid.")


def format_error(code: ErrorCode, *, detail: Optional[str] = None) -> dict:
    return {"code": code.code, "message": code.message, "detail": detail}






