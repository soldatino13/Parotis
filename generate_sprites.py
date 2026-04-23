#!/usr/bin/env python3
"""
PAROTIS – Sprite Generator
Generiert alle Spiel-Sprites einmalig via OpenAI API (gpt-image-1)
und legt sie in ~/parotis/assets/ ab.

Voraussetzung: OPENAI_API_KEY als Umgebungsvariable gesetzt
  export OPENAI_API_KEY=sk-...

Aufruf:
  python3 generate_sprites.py              # Alle Sprites
  python3 generate_sprites.py --food       # Nur Futter
  python3 generate_sprites.py --deco       # Nur Dekorationen
  python3 generate_sprites.py --skip-existing  # Bereits vorhandene überspringen
"""

import os
import sys
import base64
import time
import argparse
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("❌ openai nicht installiert. Bitte: pip3 install openai --break-system-packages")
    sys.exit(1)

try:
    from PIL import Image
    import io
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("⚠  Pillow nicht installiert – Transparenz-Verarbeitung übersprungen")
    print("   Optional: pip3 install Pillow --break-system-packages")

# ─── Konfiguration ────────────────────────────────────────────────────────────
ASSETS_DIR = Path(__file__).parent / "assets"
SIZE       = "1024x1024"   # gpt-image-1 unterstützt 1024x1024
MODEL      = "gpt-image-1.5"

# Basis-Stil für alle Sprites
STYLE_BASE = (
    "isometric pixel art, Habbo Hotel style, chunky retro 32-bit game sprite, "
    "clean bold black outline, white background, "
    "isometric 45 degree top-down view, soft top-left lighting, "
    "crisp pixels, no anti-aliasing, vibrant colors, "
    "simple flat shading with highlights"
)

# ─── Sprite-Definitionen ─────────────────────────────────────────────────────
SPRITES = {

    # ── Futter ────────────────────────────────────────────────────────────────
    "food/pizza": (
        "isometric pixel art pizza slice, Habbo Hotel style, "
        "triangular pizza slice with red tomato sauce, yellow melted cheese, "
        "small pepperoni pieces, golden brown crust edge, "
        "floating slightly above ground, white background, "
        "crisp pixel art, bold outline, 32-bit retro game style"
    ),
    "food/kebab": (
        "isometric pixel art kebab on a skewer, Habbo Hotel style, "
        "vertical wooden skewer with alternating chunks of brown meat, "
        "red tomato, green pepper, floating above ground, "
        "white background, crisp pixel art, bold outline"
    ),
    "food/burger": (
        "isometric pixel art cheeseburger, Habbo Hotel style, "
        "tall burger with sesame bun, yellow cheese, brown beef patty, "
        "green lettuce, red tomato slice, floating above ground, "
        "white background, crisp pixel art, bold outline, "
        "visible layers from the side"
    ),
    "food/cake": (
        "isometric pixel art birthday cake, Habbo Hotel style, "
        "round layered cake with pink frosting, white cream layers, "
        "lit yellow candle on top, small colorful sprinkles, "
        "floating above ground, white background, "
        "crisp pixel art, bold outline, cute chibi style"
    ),
    "food/apple": (
        "isometric pixel art red apple, Habbo Hotel style, "
        "shiny round red apple with green leaf, brown stem, "
        "white highlight reflection, floating above ground, "
        "white background, crisp pixel art, bold outline"
    ),
    "food/broccoli": (
        "isometric pixel art broccoli, Habbo Hotel style, "
        "chunky broccoli head with dark green bumpy florets, "
        "light green thick stalk, floating above ground, "
        "white background, crisp pixel art, bold black outline"
    ),
    "food/sushi": (
        "isometric pixel art sushi nigiri, Habbo Hotel style, "
        "white rice block with orange salmon on top, "
        "thin black nori strip around the sides, "
        "floating above ground, white background, "
        "crisp pixel art, bold outline, cute chibi style"
    ),
    "food/taco": (
        "isometric pixel art taco, Habbo Hotel style, "
        "U-shaped yellow corn taco shell filled with brown meat, "
        "green lettuce, red salsa, yellow cheese visible from open top, "
        "floating above ground, white background, "
        "crisp pixel art, bold outline"
    ),
    "food/watermelon": (
        "isometric pixel art watermelon slice, Habbo Hotel style, "
        "triangular watermelon slice showing bright red flesh, "
        "black seeds, green rind, floating above ground, "
        "white background, crisp pixel art, bold outline"
    ),
    "food/donut": (
        "isometric pixel art donut, Habbo Hotel style, "
        "ring-shaped donut with pink glaze frosting, "
        "colorful rainbow sprinkles, visible hole in center, "
        "floating above ground, white background, "
        "crisp pixel art, bold outline"
    ),

    # ── Dekorationen ──────────────────────────────────────────────────────────
    "deco/tree_big": (
        "isometric pixel art large oak tree, Habbo Hotel style, "
        "tall tree with wide round lush green crown, "
        "three overlapping layers of foliage getting smaller toward top, "
        "thick brown chunky trunk, dark green pixel outline, "
        "top-left highlight on crown, white background, "
        "crisp pixel art, 32-bit retro game style"
    ),
    "deco/tree_small": (
        "isometric pixel art small tree or round bush, Habbo Hotel style, "
        "small green round tree with thin brown trunk, "
        "compact round green crown with highlight, "
        "white background, crisp pixel art, bold outline, "
        "32-bit retro game style"
    ),
    "deco/shrub": (
        "isometric pixel art green shrub or bush, Habbo Hotel style, "
        "round low green bush made of three overlapping spheres, "
        "varied green shades, dark outline, no trunk, "
        "white background, crisp pixel art, 32-bit retro game"
    ),
    "deco/rock": (
        "isometric pixel art grey rock boulder, Habbo Hotel style, "
        "round chunky grey stone with lighter top-left highlight, "
        "subtle crack detail, sitting on ground, "
        "white background, crisp pixel art, bold outline, "
        "32-bit retro game style"
    ),
    "deco/stump": (
        "isometric pixel art tree stump, Habbo Hotel style, "
        "short brown tree stump with visible rings on top, "
        "small green moss patch, white background, "
        "crisp pixel art, bold outline, 32-bit retro game"
    ),

    # ── Objekte ───────────────────────────────────────────────────────────────
    "objects/mailbox": (
        "isometric pixel art green wooden mailbox on a short post, "
        "Habbo Hotel style, small letter slot visible on front, "
        "green painted wood, metal hinges, sitting on ground, "
        "white background, crisp pixel art, bold outline, "
        "32-bit retro game style"
    ),
    "objects/mailbox_glow": (
        "isometric pixel art green wooden mailbox on a short post, "
        "Habbo Hotel style, yellow envelope letter sticking out of the slot, "
        "warm golden glow around the letter, magical sparkle effect, "
        "white background, crisp pixel art, bold outline, "
        "32-bit retro game style"
    ),
}


# ─── Hilfsfunktionen ──────────────────────────────────────────────────────────
def make_transparent(img_bytes: bytes, bg_color=(255, 255, 255),
                     tolerance=30) -> bytes:
    """Weisser Hintergrund → Transparent (einfach, ohne komplexe Segmentierung)."""
    if not HAS_PIL:
        return img_bytes
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    data = img.load()
    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = data[x, y]
            if (abs(r - bg_color[0]) < tolerance and
                    abs(g - bg_color[1]) < tolerance and
                    abs(b - bg_color[2]) < tolerance):
                data[x, y] = (r, g, b, 0)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def resize_sprite(img_bytes: bytes, target_size=(64, 96)) -> bytes:
    """Skaliert Sprite auf Zielgrösse (nearest neighbor für Pixel-Art)."""
    if not HAS_PIL:
        return img_bytes
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    img = img.resize(target_size, Image.NEAREST)
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def target_size(sprite_key: str) -> tuple:
    """Zielgrösse je Sprite-Typ."""
    if sprite_key.startswith("food/"):     return (48, 48)
    if sprite_key == "deco/tree_big":      return (80, 112)
    if sprite_key in ("deco/tree_small",
                      "deco/shrub"):       return (56, 72)
    if sprite_key in ("deco/rock",
                      "deco/stump"):       return (48, 40)
    if sprite_key.startswith("objects/"): return (64, 80)
    return (64, 64)


# ─── Hauptfunktion ────────────────────────────────────────────────────────────
def generate_all(skip_existing=False, only=None, output_dir=None):
    global ASSETS_DIR
    if output_dir:
        ASSETS_DIR = Path(output_dir)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY nicht gesetzt.")
        print("   export OPENAI_API_KEY=sk-...")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    sprites = {k: v for k, v in SPRITES.items()
               if only is None or k.startswith(only + "/")}

    total = len(sprites)
    print(f"\n╔══════════════════════════════════════════╗")
    print(f"║  PAROTIS Sprite Generator                ║")
    print(f"║  {total} Sprites werden generiert           ║")
    print(f"║  Modell: {MODEL}                    ║")
    print(f"╚══════════════════════════════════════════╝\n")

    success = 0
    failed  = []

    for i, (key, prompt) in enumerate(sprites.items(), 1):
        out_path = ASSETS_DIR / f"{key}.png"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        if skip_existing and out_path.exists():
            print(f"  [{i:02d}/{total}] ⏭  {key} (bereits vorhanden)")
            success += 1
            continue

        print(f"  [{i:02d}/{total}] 🎨 {key} ...", end="", flush=True)

        try:
            full_prompt = f"{prompt}, {STYLE_BASE}"
            resp = client.images.generate(
                model=MODEL,
                prompt=full_prompt,
                n=1,
                size=SIZE,
            )
            img_bytes = base64.b64decode(resp.data[0].b64_json)

            # Nachbearbeitung
            img_bytes = make_transparent(img_bytes)
            img_bytes = resize_sprite(img_bytes, target_size(key))

            out_path.write_bytes(img_bytes)
            print(f" ✅  ({out_path.stat().st_size // 1024}KB)")
            success += 1

            # Rate-Limit schonen
            if i < total:
                time.sleep(1.2)

        except Exception as e:
            print(f" ❌  {e}")
            failed.append(key)
            time.sleep(2)

    print(f"\n{'─'*44}")
    print(f"✅ {success}/{total} Sprites generiert")
    print(f"📁 Gespeichert in: {ASSETS_DIR}")
    if failed:
        print(f"❌ Fehlgeschlagen: {', '.join(failed)}")
        print(f"   Erneut versuchen: python3 generate_sprites.py --skip-existing")
    print()


# ─── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parotis Sprite Generator")
    parser.add_argument("--food",    action="store_true", help="Nur Futter-Sprites")
    parser.add_argument("--deco",    action="store_true", help="Nur Dekorationen")
    parser.add_argument("--objects", action="store_true", help="Nur Objekte")
    parser.add_argument("--skip-existing", action="store_true",
                        help="Bereits vorhandene Sprites überspringen")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Ausgabe-Verzeichnis (Standard: ./assets/)")
    args = parser.parse_args()

    only = None
    if args.food:      only = "food"
    elif args.deco:    only = "deco"
    elif args.objects: only = "objects"

    if args.output_dir:
        ASSETS_DIR = Path(args.output_dir)
        print(f"📁 Ausgabe-Verzeichnis: {ASSETS_DIR}")

    generate_all(skip_existing=args.skip_existing, only=only)
