import base64
import json
import os
from dataclasses import dataclass
from io import BytesIO
from typing import Any, List, Optional

try:
    # Optional dependency: backend should still boot without Pillow.
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover
    Image = None  # type: ignore


class BoardVisionError(Exception):
    """Raised when the vision pipeline fails to produce a FEN."""


@dataclass
class VisionSquare:
    square: str
    confidence: float
    piece: Optional[str] = None


@dataclass
class VisionResult:
    fen: str
    confidence: float
    orientation: str
    uncertain_squares: List[VisionSquare]
    notes: Optional[str] = None


def _downscale_and_encode(image_bytes: bytes, max_dimension: int = 1280) -> str:
    if Image is None:
        raise BoardVisionError(
            "Board vision requires Pillow (PIL) but it is not installed. "
            "Install Pillow or set CG_FAKE_VISION=1 to bypass vision."
        )
    image = Image.open(BytesIO(image_bytes)).convert("RGB")
    image.thumbnail((max_dimension, max_dimension), Image.LANCZOS)
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def _fake_result(orientation_hint: str) -> VisionResult:
    start_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    return VisionResult(
        fen=start_fen,
        confidence=0.0,
        orientation=orientation_hint,
        uncertain_squares=[
            VisionSquare(square="e2", confidence=0.0, piece="wP"),
            VisionSquare(square="d7", confidence=0.0, piece="bP"),
        ],
        notes="Vision model unavailable – returned starting position as placeholder.",
    )


def _extract_json_payload(raw_text: str) -> str:
    """
    Vision models occasionally wrap JSON in Markdown fences (```json ... ```).
    This helper strips the fences and returns the inner JSON string.
    """
    text = raw_text.strip()
    if text.startswith("```"):
        # Remove leading fence, optional language tag, and trailing fence
        text = text[3:]
        if text.lower().startswith("json"):
            text = text[4:]
        closing = text.rfind("```")
        if closing != -1:
            text = text[:closing]
    text = text.strip()
    # Fall back to extracting the first {...} block if extra commentary exists
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return text


def analyze_board_image(
    image_bytes: bytes,
    preset: str,
    orientation_hint: str,
    openai_client: Optional[Any],
) -> VisionResult:
    """
    Uses the configured OpenAI client to transcribe a chessboard photo into a FEN.
    If the OpenAI client is unavailable (or CG_FAKE_VISION env var is set) a
    deterministic placeholder result is returned.
    """
    if os.getenv("CG_FAKE_VISION") == "1" or openai_client is None:
        return _fake_result(orientation_hint)

    data_url = f"data:image/jpeg;base64,{_downscale_and_encode(image_bytes)}"
    preset = preset.lower()
    orientation_hint = orientation_hint.lower() if orientation_hint else "white"

    instructions = (
        "You convert chessboard photos into Forsyth-Edwards Notation (FEN). "
        "Return a strict JSON object with keys: fen (string), confidence (0-1 float), "
        "orientation (\"white\" or \"black\" from the player's perspective at the bottom), "
        "and uncertain_squares (array of objects with square, piece in SAN such as wP/bQ, "
        "and confidence 0-1)."
        "\nGuidelines:\n"
        f"- Board preset hint: {preset} (digital boards usually match Chess GPT's brown/cream palette).\n"
        f"- Orientation hint: {orientation_hint} at the bottom if the image is ambiguous.\n"
        "- If the board is cropped or partially visible, adjust orientation based on files/ranks.\n"
        "- Use lowercase letters for black pieces in FEN.\n"
        "- Do not include extra commentary; respond with JSON only."
    )

    response = openai_client.responses.create(
        model="gpt-5",
        input=[
            {"role": "system", "content": "You are a meticulous chessboard vision assistant."},
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": instructions},
                    {"type": "input_image", "image_url": data_url},
                ],
            },
        ],
        max_output_tokens=600,
    )

    try:
        raw_text = response.output[0].content[0].text  # type: ignore[attr-defined]
    except Exception as exc:  # pragma: no cover - defensive
        raise BoardVisionError(f"Vision model returned an unexpected payload: {exc}") from exc

    cleaned_text = _extract_json_payload(raw_text)

    try:
        parsed = json.loads(cleaned_text)
    except json.JSONDecodeError as exc:
        raise BoardVisionError(f"Vision model response was not valid JSON: {raw_text}") from exc

    fen = parsed.get("fen")
    confidence = float(parsed.get("confidence", 0))
    orientation = parsed.get("orientation", orientation_hint).lower()
    uncertain_squares_payload = parsed.get("uncertain_squares", [])

    if not isinstance(fen, str) or "/" not in fen:
        raise BoardVisionError("Vision model did not return a valid FEN string.")

    squares: List[VisionSquare] = []
    for square_payload in uncertain_squares_payload:
        square = square_payload.get("square")
        piece = square_payload.get("piece")
        square_conf = float(square_payload.get("confidence", 0))
        if isinstance(square, str):
            squares.append(VisionSquare(square=square, piece=piece, confidence=square_conf))

    return VisionResult(
        fen=fen.strip(),
        confidence=max(0.0, min(1.0, confidence)),
        orientation="black" if orientation == "black" else "white",
        uncertain_squares=squares,
    )

