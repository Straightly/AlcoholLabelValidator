from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class VisionResult:
    text: str
    confidence: float
    engine: str
    width: int | None = None
    height: int | None = None
    blur_score: float | None = None
    glare_ratio: float | None = None
    rotation_degrees: float | None = None
    quality_flags: list[str] = field(default_factory=list)


class LocalVisionEngine:
    """One resident OCR engine with deterministic fixture support."""

    def __init__(self) -> None:
        self._ocr: Any = None
        self.engine_name = "unavailable"
        self.ready = False
        self.detail = ""

    def prepare(self) -> None:
        mode = os.getenv("ALV_OCR_ENGINE", "fixture-sidecar").casefold()
        if mode in {"auto", "paddle"}:
            try:
                from paddleocr import PaddleOCR

                self._ocr = PaddleOCR(
                    text_detection_model_name="PP-OCRv5_mobile_det",
                    text_recognition_model_name="PP-OCRv5_mobile_rec",
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                    text_det_limit_side_len=960,
                )
                self.engine_name = "PaddleOCR"
                self.ready = True
                self.detail = "Local PaddleOCR model loaded."
                return
            except Exception as exc:
                if mode == "paddle":
                    self.detail = f"PaddleOCR unavailable: {exc}"

        # Committed fixtures carry OCR sidecars so reviewers can exercise the
        # complete workflow without network/model installation.
        self.engine_name = "fixture-sidecar"
        self.ready = True
        self.detail = "Fixture sidecars enabled; real images require PaddleOCR."

    def analyze(self, image_path: Path) -> VisionResult:
        metrics = self._quality_metrics(image_path)
        sidecar = image_path.with_suffix(image_path.suffix + ".ocr.txt")
        if sidecar.exists() and self._ocr is None:
            return VisionResult(
                text=sidecar.read_text(encoding="utf-8").strip(),
                confidence=0.99,
                engine="fixture-sidecar",
                **metrics,
            )
        if self._ocr is None:
            raise RuntimeError(
                "No OCR model is available for this image. Run scripts/prepare_models.py "
                "or use the committed demonstration fixtures."
            )

        ocr_input: Any = str(image_path)
        try:
            import cv2

            image = cv2.imread(str(image_path))
            max_side = int(os.getenv("ALV_OCR_MAX_SIDE", "1200"))
            if image is not None and max(image.shape[:2]) > max_side:
                scale = max_side / max(image.shape[:2])
                ocr_input = cv2.resize(
                    image,
                    None,
                    fx=scale,
                    fy=scale,
                    interpolation=cv2.INTER_AREA,
                )
        except ImportError:
            pass

        output = self._ocr.predict(ocr_input)
        texts: list[str] = []
        scores: list[float] = []
        for page in output:
            payload = page.json if hasattr(page, "json") else page
            if callable(payload):
                payload = payload()
            if isinstance(payload, str):
                import json

                payload = json.loads(payload)
            data = payload.get("res", payload) if isinstance(payload, dict) else {}
            texts.extend(str(item) for item in data.get("rec_texts", []))
            scores.extend(float(item) for item in data.get("rec_scores", []))
        confidence = sum(scores) / len(scores) if scores else 0.0
        return VisionResult(
            text="\n".join(texts),
            confidence=confidence,
            engine="PaddleOCR",
            **metrics,
        )

    def _quality_metrics(self, image_path: Path) -> dict[str, Any]:
        try:
            import cv2

            image = cv2.imread(str(image_path))
            if image is None:
                return {"quality_flags": ["Image quality could not be measured."]}
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            glare = float((gray >= 250).sum() / gray.size)
            flags = []
            if blur < 70:
                flags.append("Possible blur or insufficient detail.")
            if glare > 0.08:
                flags.append("Possible glare or overexposure.")
            height, width = gray.shape
            if min(height, width) < 500:
                flags.append("Low image resolution.")
            return {
                "width": int(width),
                "height": int(height),
                "blur_score": round(blur, 2),
                "glare_ratio": round(glare, 4),
                "rotation_degrees": 0.0,
                "quality_flags": flags,
            }
        except ImportError:
            return {"quality_flags": ["OpenCV quality metrics are unavailable."]}
