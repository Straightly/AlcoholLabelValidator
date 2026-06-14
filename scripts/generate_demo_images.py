from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "fixtures" / "intake"
FONT = Path("/System/Library/Fonts/Supplemental/Arial.ttf")
FONT_BOLD = Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf")


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT
    return ImageFont.truetype(str(path), size)


def centered(draw: ImageDraw.ImageDraw, text: str, y: int, size: int, bold: bool = False) -> None:
    selected = font(size, bold)
    box = draw.textbbox((0, 0), text, font=selected)
    draw.text(((900 - (box[2] - box[0])) / 2, y), text, fill="#231812", font=selected)


def create_front(path: Path, attention: bool) -> None:
    image = Image.new("RGB", (900, 1200), "#efe5c8" if not attention else "#d8c38b")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((55, 55, 845, 1145), 24, outline="#301f16", width=8)
    centered(draw, "CEDAR RIDGE" if attention else "OLD TOM DISTILLERY", 210, 58, True)
    centered(draw, "Straight Rye Whiskey" if attention else "Kentucky Straight Bourbon Whiskey", 470, 36)
    centered(draw, "50% Alc./Vol. (100 Proof)" if attention else "45% Alc./Vol. (90 Proof)", 720, 34)
    centered(draw, "750 mL", 790, 34)
    centered(
        draw,
        "Cedar Ridge Spirits, Seattle, Washington"
        if attention
        else "Old Tom Distillery, Louisville, Kentucky",
        1010,
        24,
    )
    if attention:
        draw.polygon([(310, 55), (470, 55), (700, 1145), (540, 1145)], fill="#fff7d9")
    image.save(path, optimize=True)


def create_back(path: Path, attention: bool) -> None:
    image = Image.new("RGB", (900, 1200), "#f6f1e5")
    draw = ImageDraw.Draw(image)
    draw.rectangle((70, 150, 830, 1050), fill="white", outline="#151515", width=5)
    if attention:
        draw.text((110, 280), "Government Warning:", fill="black", font=font(38))
        draw.text((110, 360), "Please drink responsibly.", fill="black", font=font(30))
    else:
        draw.text((110, 230), "GOVERNMENT WARNING:", fill="black", font=font(36, True))
        lines = [
            "(1) According to the Surgeon General, women",
            "should not drink alcoholic beverages during",
            "pregnancy because of the risk of birth defects.",
            "(2) Consumption of alcoholic beverages impairs",
            "your ability to drive a car or operate machinery,",
            "and may cause health problems.",
        ]
        for index, line in enumerate(lines):
            draw.text((110, 310 + index * 55), line, fill="black", font=font(27))
    image.save(path, optimize=True)


def main() -> None:
    create_front(OUTPUT / "sample-compliant-front.png", False)
    create_back(OUTPUT / "sample-compliant-back.png", False)
    create_front(OUTPUT / "sample-attention-front.png", True)
    create_back(OUTPUT / "sample-attention-back.png", True)
    print("Generated four raster demonstration labels.")


if __name__ == "__main__":
    main()
