import os
import sys


def main() -> int:
    try:
        import cv2  # noqa: F401
    except ImportError:
        print('OpenCV is missing. Run: python -m pip install -e ".[dev]"', file=sys.stderr)
        return 1
    try:
        from paddleocr import PaddleOCR
    except ImportError:
        print('PaddleOCR is optional for seeded fixtures. For real images run: pip install -e ".[ocr]"')
        return 0

    os.environ.setdefault("PADDLE_PDX_MODEL_SOURCE", "BOS")
    print("Initializing PaddleOCR and preparing local model files...")
    PaddleOCR(
        text_detection_model_name="PP-OCRv5_mobile_det",
        text_recognition_model_name="PP-OCRv5_mobile_rec",
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        text_det_limit_side_len=960,
    )
    print("Local OCR runtime is ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
