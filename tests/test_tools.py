"""Tests for the Python tooling: .mcstructure codec, lenient JSON, and the static validator — including
negative tests that inject real defects into a copy of the packs and require the validator to catch them.

Run: python3 -m unittest discover -s tests -p "test_*.py"
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from tools.lib.jsonio import load_lenient, strip_comments  # noqa: E402
from tools.lib.mcstructure import BLOCK_VERSION, read_structure, write_structure  # noqa: E402
from validate import Validator  # noqa: E402


class McStructureTests(unittest.TestCase):
    def test_roundtrip(self):
        cells = {(0, 0, 0): ("apocalypse:runestone_bricks", {}), (1, 0, 1): ("minecraft:stone", {}),
                 (1, 1, 0): ("minecraft:air", {})}
        doc = read_structure(write_structure((2, 2, 2), cells))
        self.assertEqual(doc["format_version"], 1)
        self.assertEqual(list(doc["size"]), [2, 2, 2])
        palette = doc["structure"]["palette"]["default"]["block_palette"]
        names = [p["name"] for p in palette]
        self.assertEqual(sorted(names), sorted({"apocalypse:runestone_bricks", "minecraft:stone", "minecraft:air"}))
        self.assertTrue(all(p["version"] == BLOCK_VERSION for p in palette))
        primary = list(doc["structure"]["block_indices"][0])
        self.assertEqual(len(primary), 8)
        # index order: x-major, then y, then z
        idx = lambda x, y, z: (x * 2 + y) * 2 + z  # noqa: E731
        self.assertEqual(names[primary[idx(0, 0, 0)]], "apocalypse:runestone_bricks")
        self.assertEqual(names[primary[idx(1, 0, 1)]], "minecraft:stone")
        self.assertEqual(primary[idx(0, 1, 1)], -1, "unspecified cells are structure void")
        self.assertTrue(all(i == -1 for i in doc["structure"]["block_indices"][1]))

    def test_shipped_structures(self):
        blocks = {json.load(open(p))["minecraft:block"]["description"]["identifier"]
                  for p in glob.glob(os.path.join(ROOT, "behavior_pack", "blocks", "**", "*.json"), recursive=True)}
        files = glob.glob(os.path.join(ROOT, "behavior_pack", "structures", "**", "*.mcstructure"), recursive=True)
        self.assertEqual(len(files), 4)
        for f in files:
            with open(f, "rb") as fh:
                doc = read_structure(fh.read())
            sx, sy, sz = doc["size"]
            palette = doc["structure"]["palette"]["default"]["block_palette"]
            primary = doc["structure"]["block_indices"][0]
            self.assertEqual(len(primary), sx * sy * sz, f)
            self.assertTrue(all(-1 <= i < len(palette) for i in primary), f)
            for p in palette:
                if p["name"].startswith("apocalypse:"):
                    self.assertIn(p["name"], blocks, f"{f}: palette block {p['name']} is defined")


class JsonTests(unittest.TestCase):
    def test_strip_comments_keeps_strings(self):
        text = '{"a": "http://x//y", /* c */ "b": 1 // tail\n}'
        self.assertEqual(json.loads(strip_comments(text)), {"a": "http://x//y", "b": 1})

    def test_load_lenient_bom(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8-sig") as f:
            f.write('// header\n{"ok": true}')
        try:
            self.assertEqual(load_lenient(f.name), {"ok": True})
        finally:
            os.unlink(f.name)


class ValidatorTests(unittest.TestCase):
    def test_shipped_packs_are_clean(self):
        R = Validator(ROOT, None).run()
        self.assertEqual(R.errors, [], "\n".join(R.errors))
        self.assertGreater(sum(R.passes.values()), 1500)

    def test_injected_defects_are_caught(self):
        tmp = tempfile.mkdtemp(prefix="apocalypse_validator_")
        try:
            for d in ("behavior_pack", "resource_pack"):
                shutil.copytree(os.path.join(ROOT, d), os.path.join(tmp, d))
            os.symlink(os.path.join(ROOT, "node_modules"), os.path.join(tmp, "node_modules"))
            bp, rp = os.path.join(tmp, "behavior_pack"), os.path.join(tmp, "resource_pack")

            def edit(path, fn):
                with open(path, encoding="utf-8") as f:
                    d = json.load(f)
                fn(d)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(d, f)

            # 1. a vanilla id typo inside a loot table
            edit(os.path.join(bp, "loot_tables", "entities", "apocalypse", "thornling.json"),
                 lambda d: d["pools"][0]["entries"].append({"type": "item", "name": "minecraft:dead_bush", "weight": 1}))
            # 2. a texture that no longer exists
            os.remove(os.path.join(rp, "textures", "blocks", "apocalypse", "rift_ore.png"))
            # 3. a client entity pointing at missing geometry
            edit(os.path.join(rp, "entity", "apocalypse", "thornling.entity.json"),
                 lambda d: d["minecraft:client_entity"]["description"]["geometry"].update({"default": "geometry.apocalypse.ghost"}))
            # 4. an item using a custom component no script registers
            edit(os.path.join(bp, "items", "apocalypse", "rift_shard.json"),
                 lambda d: d["minecraft:item"]["components"].update({"apocalypse:ghost_component": {}}))
            # 5. the behavior pack no longer depends on the resource pack's version
            edit(os.path.join(bp, "manifest.json"), lambda d: d["dependencies"][0].update({"version": [9, 9, 9]}))
            # 6. an entity event that adds a component group that does not exist
            edit(os.path.join(bp, "entities", "apocalypse", "hollow_shade.json"),
                 lambda d: d["minecraft:entity"]["events"]["apocalypse:become_crimson"]["add"]["component_groups"].append("apocalypse:nope"))

            R = Validator(tmp, None).run()
            joined = "\n".join(R.errors)
            for needle in ("minecraft:dead_bush", "rift_ore", "geometry.apocalypse.ghost", "apocalypse:ghost_component",
                           "does not depend on the resource pack", "apocalypse:nope"):
                self.assertIn(needle, joined, f"validator missed injected defect '{needle}'\n{joined}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
