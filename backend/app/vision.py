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
                    text_det_thresh=0.2,
                    text_det_box_thresh=0.4,
                    text_det_unclip_ratio=1.6,
                )
                self.engine_name = "PaddleOCR"
                self.ready = True
                self.detail = "Local PaddleOCR model loaded."
                return
            except Exception as exc:
                if mode == "paddle":
                    self.detail = f"PaddleOCR unavailable: {exc}"
                    self.ready = False
                    return

        if mode in {"auto", "tesseract"}:
            try:
                import pytesseract

                pytesseract.get_tesseract_version()
                self.engine_name = "Tesseract"
                self.ready = True
                self.detail = "Local Tesseract OCR engine loaded."
                return
            except Exception as exc:
                if mode == "tesseract":
                    self.engine_name = "unavailable"
                    self.ready = False
                    self.detail = f"Tesseract unavailable: {exc}"
                    return

        if mode == "ollama":
            ollama_host = os.getenv("ALV_OLLAMA_HOST", "http://localhost:11434").rstrip("/")
            model_name = os.getenv("ALV_OLLAMA_MODEL", "moondream")
            try:
                import urllib.request

                # Check connectivity by hitting the tags endpoint
                req = urllib.request.Request(f"{ollama_host}/api/tags")
                with urllib.request.urlopen(req, timeout=3.0) as response:
                    if response.status == 200:
                        self.engine_name = "Ollama"
                        self.ready = True
                        self.detail = f"Local Ollama engine loaded (Model: {model_name})."
                        return
            except Exception as exc:
                self.engine_name = "unavailable"
                self.ready = False
                self.detail = f"Ollama engine unavailable at {ollama_host}: {exc}"
                return

        # Committed fixtures carry OCR sidecars so reviewers can exercise the
        # complete workflow without network/model installation.
        self.engine_name = "fixture-sidecar"
        self.ready = True
        self.detail = "Fixture sidecars enabled; real images require PaddleOCR/Tesseract."

    def analyze(self, image_path: Path) -> VisionResult:
        import time
        start_time = time.perf_counter()

        print(f"[VisionEngine] Starting analysis of {image_path.name} (Engine: {self.engine_name})", flush=True)

        metrics = self._quality_metrics(image_path)
        sidecar = image_path.with_suffix(image_path.suffix + ".ocr.txt")

        result = None

        if sidecar.exists() and self.engine_name == "fixture-sidecar":
            result = VisionResult(
                text=sidecar.read_text(encoding="utf-8").strip(),
                confidence=0.99,
                engine="fixture-sidecar",
                **metrics,
            )
        elif self.engine_name == "Tesseract":
            try:
                import pytesseract
                print(f"[VisionEngine] Running Tesseract OCR on {image_path.name}...", flush=True)
                text = pytesseract.image_to_string(str(image_path)).strip()
                result = VisionResult(
                    text=text,
                    confidence=0.85,
                    engine="Tesseract",
                    **metrics,
                )
            except Exception as exc:
                raise RuntimeError(f"Tesseract OCR failed: {exc}")
        elif self.engine_name == "Ollama":
            try:
                import base64
                import json
                import urllib.request

                with open(image_path, "rb") as img_file:
                    base64_image = base64.b64encode(img_file.read()).decode("utf-8")

                ollama_host = os.getenv("ALV_OLLAMA_HOST", "http://localhost:11434").rstrip("/")
                model_name = os.getenv("ALV_OLLAMA_MODEL", "moondream")

                print(f"[VisionEngine] Sending {image_path.name} to Ollama local API (Model: {model_name})...", flush=True)

                payload = {
                    "model": model_name,
                    "prompt": "Transcribe all readable text on this alcohol label verbatim.",
                    "images": [base64_image],
                    "stream": False,
                    "options": {
                        "temperature": 0.0,
                        "num_predict": 300,
                    }
                }
                data = json.dumps(payload).encode("utf-8")

                req = urllib.request.Request(
                    f"{ollama_host}/api/generate",
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )

                with urllib.request.urlopen(req, timeout=300.0) as response:
                    res_body = json.loads(response.read().decode("utf-8"))
                    text = res_body.get("response", "").strip()

                result = VisionResult(
                    text=text,
                    confidence=0.95,
                    engine=f"Ollama ({model_name})",
                    **metrics,
                )
            except Exception as exc:
                raise RuntimeError(f"Ollama VLM failed: {exc}")
        else:
            if self._ocr is None:
                raise RuntimeError(
                    "No OCR model is available for this image. Run scripts/prepare_models.py "
                    "or use the committed demonstration fixtures."
                )

            print(f"[VisionEngine] Running PaddleOCR on {image_path.name}...", flush=True)
            output = self._ocr.predict(str(image_path))
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
            result = VisionResult(
                text="\n".join(texts),
                confidence=confidence,
                engine="PaddleOCR",
                **metrics,
            )

        duration = time.perf_counter() - start_time
        print(f"[VisionEngine] Done processing {image_path.name} in {duration:.2f}s (Engine: {result.engine}). Chars extracted: {len(result.text)}", flush=True)
        preview = result.text.replace('\n', ' | ')[:150]
        print(f"[VisionEngine] Extracted text preview: '{preview}...'", flush=True)

        return result

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
