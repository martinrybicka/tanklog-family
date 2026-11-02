"""Vlastní pumpa TankLog, bez externích obrázků. Spustit Pythonem z backend/.venv."""

from pathlib import Path

from PIL import Image, ImageDraw

folder = Path(__file__).resolve().parents[1] / "public/icons"
for size, name in [
    (192, "icon-192.png"),
    (512, "icon-512.png"),
    (512, "maskable-512.png"),
    (180, "apple-touch-icon.png"),
]:
    image = Image.new("RGB", (512, 512), "#315fa3")
    draw = ImageDraw.Draw(image)
    draw.line([(146, 371), (146, 146), (303, 146), (303, 371)], fill="white", width=22)
    draw.line([(125, 371), (324, 371)], fill="white", width=22)
    draw.rectangle((168, 176, 280, 264), outline="white", width=16)
    draw.line([(303, 204), (338, 204), (369, 238), (369, 319)], fill="white", width=19)
    draw.arc((369, 299, 409, 339), 0, 180, fill="white", width=18)
    draw.line([(409, 319), (409, 238), (372, 190)], fill="white", width=18)
    image.resize((size, size), Image.Resampling.LANCZOS).save(folder / name)
