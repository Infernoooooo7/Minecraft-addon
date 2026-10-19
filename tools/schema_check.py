"""Validate behavior-pack JSON against Mojang's official Bedrock JSON schemas.

The schemas ship in Mojang's `bedrock-samples` repository (metadata/json_schemas). They are
copyright Mojang and are NOT redistributed with this project; point this module at a local
checkout via the BEDROCK_SAMPLES environment variable or the `--schemas` flag of validate.py.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from urllib.parse import urljoin

from jsonschema import Draft7Validator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7


def _relax(node):
    """Mojang's generated schemas use `oneOf` for overlapping alternatives (an integer is also a
    number; a filter test object also matches the all-optional filter map), which rejects valid
    vanilla content. Treat them as `anyOf`, which is the evident intent."""
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            out["anyOf" if k == "oneOf" else k] = _relax(v)
        return out
    if isinstance(node, list):
        return [_relax(v) for v in node]
    return node


def _version_key(v: str):
    return tuple(int(p) for p in re.findall(r"\d+", v))


class SchemaSet:
    def __init__(self, root: str):
        self.root = root  # .../metadata/json_schemas
        self._registry = self._load_registry()

    def _load_registry(self) -> Registry:
        resources = []
        for dirpath, _, files in os.walk(self.root):
            for fn in files:
                if not fn.endswith(".json"):
                    continue
                full = os.path.join(dirpath, fn)
                with open(full, encoding="utf-8") as f:
                    doc = _relax(json.load(f))
                sid = doc.get("$id")
                if not sid:
                    rel = "/" + os.path.relpath(full, self.root).replace(os.sep, "/")
                    sid = rel
                    doc["$id"] = sid
                resources.append((sid, Resource(contents=doc, specification=DRAFT7)))
                # also index the un-escaped and %20-escaped variants used by relative refs
                if " " in sid:
                    resources.append((sid.replace(" ", "%20"), Resource(contents=doc, specification=DRAFT7)))
        return Registry().with_resources(resources)

    def component_names(self, area: str, fmt: str, components_file: str) -> set[str] | None:
        """Whitelist of component names declared by the official schema for this version."""
        v = self.pick(area, fmt)
        if v is None:
            return None
        sid = f"/{area}/{v}/{components_file}".replace(" ", "%20")
        try:
            doc = self._registry.contents(sid)
        except Exception:
            return None
        return set(doc.get("properties", {}).keys())

    def is_dynamic(self, area: str, fmt: str, components_file: str, comp: str) -> bool:
        """True when the official schema leaves a component untyped ("Dynamic value")."""
        v = self.pick(area, fmt)
        sid = f"/{area}/{v}/{components_file}".replace(" ", "%20")
        try:
            node = self._registry.contents(sid).get("properties", {}).get(comp, {})
        except Exception:
            return True
        return "$ref" not in node and "properties" not in node

    def versions(self, area: str) -> list[str]:
        d = os.path.join(self.root, area)
        return sorted([v for v in os.listdir(d) if re.match(r"^\d+(\.\d+)*$", v)], key=_version_key)

    def pick(self, area: str, fmt: str) -> str | None:
        """Highest schema version <= fmt for an area like 'server/entity'."""
        best = None
        for v in self.versions(area):
            if _version_key(v) <= _version_key(fmt):
                best = v
        return best

    @lru_cache(maxsize=None)
    def validator(self, schema_id: str) -> Draft7Validator:
        schema = self._registry.contents(schema_id)
        return Draft7Validator(schema, registry=self._registry)

    def validate(self, area: str, document_file: str, fmt: str, instance) -> tuple[str | None, list[str]]:
        """Return (schema_version_used, [error strings])."""
        v = self.pick(area, fmt)
        if v is None:
            return None, [f"no official schema for {area} at or below format {fmt}"]
        sid = f"/{area}/{v}/{document_file}"
        try:
            val = self.validator(sid)
        except Exception as e:  # missing doc schema for this version: walk back
            return v, [f"schema {sid} unavailable: {e}"]
        errs = []
        for e in sorted(val.iter_errors(instance), key=lambda e: list(e.absolute_path)):
            path = "/".join(str(p) for p in e.absolute_path)
            errs.append(f"{path or '<root>'}: {e.message[:300]}")
        return v, errs


def find_schema_root(explicit: str | None = None) -> str | None:
    cands = []
    if explicit:
        cands.append(explicit)
    env = os.environ.get("BEDROCK_SAMPLES")
    if env:
        cands.append(env)
    cands.append(os.path.join(os.path.dirname(__file__), "..", ".cache", "bedrock-samples"))
    for c in cands:
        for sub in ("", "metadata/json_schemas"):
            p = os.path.join(c, sub) if sub else c
            if os.path.isdir(os.path.join(p, "server", "entity")):
                return os.path.abspath(p)
    return None
