from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent
src = ROOT / "assets" / "industrializer.png"
out = ROOT / "assets" / "industrializer.ico"
if not src.exists():
    raise SystemExit("Falta assets/industrializer.png")
img = Image.open(src).convert("RGBA")
img.save(out, format="ICO", sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])
print(f"Icono creado: {out}")
