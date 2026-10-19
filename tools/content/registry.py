"""Central registry that content modules write into; generate_all.py flushes it to disk."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from PIL import Image

from tools.lib import tex

# texel density per resource tier (relative to the asset's base unit size)
TIERS = ("base", "balanced", "enhanced")


@dataclass
class TexAsset:
    """A texture painted once at max density then downscaled for lower tiers."""
    path: str                                   # e.g. textures/entity/apocalypse/hollow_king (no ext)
    painter: Callable[[int], tex.Canvas]        # density -> canvas
    densities: dict[str, int]                   # tier -> density (base must exist)
    pbr: bool = True                            # emit texture_set + MER for balanced/enhanced
    normal: bool = False                        # emit normal map (blocks)
    glow: bool = False                          # emit classic emissive overlay (<name>_glow)
    post: Callable[[Image.Image, str], Image.Image] | None = None  # (image, tier) -> image
    _cache: dict = field(default_factory=dict)

    def render(self, tier: str):
        d = self.densities[tier]
        top = max(self.densities.values())
        if top not in self._cache:
            self._cache[top] = self.painter(top)
        cv = self._cache[top]
        factor = top // d
        color = tex.downscale(cv.image(), factor)
        if self.post:
            color = self.post(color, tier)
        out = {"color": color}
        if self.pbr and tier != "base":
            out["mer"] = tex.downscale(cv.mer_image().convert("RGB"), factor)
            if self.normal:
                out["normal"] = tex.downscale(cv.normal_image(), factor)
        if self.glow:
            out["glow"] = tex.downscale(cv.emissive_overlay(), factor)
        return out


class Registry:
    def __init__(self):
        self.bp: dict[str, object] = {}
        self.rp: dict[str, object] = {}
        self.bp_bin: dict[str, bytes] = {}
        self.rp_bin: dict[str, bytes] = {}
        self.textures: dict[str, TexAsset] = {}
        self.images: dict[str, Image.Image] = {}          # rp-relative path (with .png) -> fixed image (all tiers)
        self.subpack_json: dict[str, dict[str, object]] = {t: {} for t in ("potato", "balanced", "enhanced")}
        self.lang: dict[str, str] = {}
        self.bp_lang: dict[str, str] = {}
        self.item_textures: dict[str, str] = {}
        self.terrain_textures: dict[str, str] = {}
        self.blocks_json: dict[str, dict] = {}
        self.sound_defs: dict[str, dict] = {}
        self.entity_sounds: dict[str, dict] = {}
        self.ts_ids: dict[str, dict[str, str]] = {}
        self.notes: list[str] = []

    # helpers -----------------------------------------------------------------------------------
    def add_bp(self, path: str, obj):
        assert path not in self.bp, f"duplicate bp file {path}"
        self.bp[path] = obj

    def add_rp(self, path: str, obj):
        assert path not in self.rp, f"duplicate rp file {path}"
        self.rp[path] = obj

    def add_texture(self, asset: TexAsset):
        assert asset.path not in self.textures, f"duplicate texture {asset.path}"
        self.textures[asset.path] = asset

    def name(self, key: str, value: str):
        self.lang[key] = value

    def ts(self, group: str, const: str, value: str):
        self.ts_ids.setdefault(group, {})[const] = value


REG = Registry()
