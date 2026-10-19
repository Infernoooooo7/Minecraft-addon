"""Assemble the documentation preview sheets in docs/previews/.

Model renders come from Mojang's Creator Tools (not bundled), e.g. for each model:
    mct rendermodel models/entity/apocalypse/<name>.geo.json <renders>/<name>.png -i <rp copy> --no-vanilla \
        --width 640 --height 640
where <rp copy> is a copy of resource_pack/ with subpacks/balanced/textures overlaid onto textures/.
Item and block sheets are made directly from the pack textures.

    python3 tools/compose_previews.py --renders <folder with the 12 renders>
"""
from __future__ import annotations

import argparse
import glob
import json
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "docs", "previews")
BG = (18, 14, 28)
BOSSES = [("hollow_king", "The Hollow King"), ("star_eater", "The Star Eater"), ("root_titan", "The Root Titan"),
          ("null_colossus", "The Null Colossus")]
OTHERS = [("hollow_shade", "Hollow Shade"), ("void_crawler", "Void Crawler"), ("astral_mite", "Astral Mite"),
          ("thornling", "Thornling"), ("rift_sentinel", "Rift Sentinel"), ("void_rift", "Void Rift"),
          ("rift_portal", "Rift Portal"), ("meteor", "Meteor")]


def font(size: int, bold: bool = True):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    for d in ("/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/dejavu", "/Library/Fonts", "C:/Windows/Fonts"):
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def render_sheet(renders: str, entries, cell: int, cols: int, path: str, crop=(110, 90, 530, 510)):
    f = font(22)
    rows = (len(entries) + cols - 1) // cols
    im = Image.new("RGB", (cols * cell, rows * (cell + 34)), BG)
    d = ImageDraw.Draw(im)
    for i, (name, label) in enumerate(entries):
        t = Image.open(os.path.join(renders, name + ".png")).convert("RGB").crop(crop).resize((cell, cell), Image.LANCZOS)
        x, y = (i % cols) * cell, (i // cols) * (cell + 34)
        im.paste(t, (x, y))
        w = d.textlength(label, font=f)
        d.text((x + (cell - w) / 2, y + cell + 5), label, fill=(230, 220, 255), font=f)
    im.save(path, optimize=True)


def lang() -> dict:
    out = {}
    with open(os.path.join(ROOT, "resource_pack", "texts", "en_US.lang"), encoding="utf-8") as fh:
        for line in fh:
            if "=" in line:
                k, v = line.rstrip("\n").split("=", 1)
                out[k] = v.split("\t#")[0]
    return out


def icon_sheet(entries, path: str, cols: int = 8, cell: int = 150):
    f = font(15, bold=False)
    rows = (len(entries) + cols - 1) // cols
    im = Image.new("RGB", (cols * cell, rows * (cell + 30)), BG)
    d = ImageDraw.Draw(im)
    for i, (src, label) in enumerate(entries):
        t = Image.open(src).convert("RGBA")
        size = min(128, t.width * 4)
        t = t.resize((size, size), Image.NEAREST)
        x, y = (i % cols) * cell, (i // cols) * (cell + 30)
        bg = Image.new("RGBA", t.size, (38, 32, 54, 255))
        bg.alpha_composite(t)
        im.paste(bg.convert("RGB"), (x + (cell - t.width) // 2, y + (cell - t.height) // 2))
        label = label if len(label) <= 19 else label[:18] + "…"
        w = d.textlength(label, font=f)
        d.text((x + (cell - w) / 2, y + cell + 4), label, fill=(225, 218, 245), font=f)
    im.save(path, optimize=True)


def tex(rel: str) -> str:
    hd = os.path.join(ROOT, "resource_pack", "subpacks", "balanced", rel + ".png")
    return hd if os.path.isfile(hd) else os.path.join(ROOT, "resource_pack", rel + ".png")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--renders", required=True)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    render_sheet(args.renders, BOSSES, 400, 4, os.path.join(OUT, "bosses.png"))
    render_sheet(args.renders, BOSSES + OTHERS, 320, 4, os.path.join(OUT, "bestiary.png"))
    names = lang()
    items = []
    for p in sorted(glob.glob(os.path.join(ROOT, "behavior_pack", "items", "apocalypse", "*.json"))):
        with open(p, encoding="utf-8") as fh:
            iid = json.load(fh)["minecraft:item"]["description"]["identifier"]
        items.append((tex(f"textures/items/apocalypse/{iid.split(':')[1]}"), names.get(f"item.{iid}.name", iid)))
    icon_sheet(items, os.path.join(OUT, "items.png"))
    with open(os.path.join(ROOT, "resource_pack", "textures", "terrain_texture.json"), encoding="utf-8") as fh:
        terrain = json.load(fh)["texture_data"]
    blocks = []
    for p in sorted(glob.glob(os.path.join(ROOT, "behavior_pack", "blocks", "apocalypse", "*.json"))):
        with open(p, encoding="utf-8") as fh:
            b = json.load(fh)["minecraft:block"]
        mi = b["components"]["minecraft:material_instances"]
        key = (mi.get("north") or mi.get("*") or next(iter(mi.values())))["texture"]
        blocks.append((tex(terrain[key]["textures"]), names.get(f"tile.{b['description']['identifier']}.name", key)))
    icon_sheet(blocks, os.path.join(OUT, "blocks.png"), cols=7)
    print("wrote", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
