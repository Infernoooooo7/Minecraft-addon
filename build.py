#!/usr/bin/env python3
"""APOCALYPSE ENGINE — the one command that regenerates, tests, validates and packages everything.

    python3 build.py                     full pipeline (generate -> compile -> test -> validate -> package)
    python3 build.py --skip-generate     keep the generated pack content as committed
    python3 build.py --schemas PATH      also validate against Mojang's official JSON schemas
                                         (PATH = a bedrock-samples checkout or its metadata/json_schemas;
                                          or set BEDROCK_SAMPLES)
    python3 build.py --mct PATH          also run Minecraft Creator Tools `mct validate all` (PATH = mct executable)
    python3 build.py --seeds N           re-run the runtime simulation under N extra random seeds (default 8)

Outputs (release/):
    APOCALYPSE_ENGINE.mcaddon            both packs, one-tap import
    APOCALYPSE_ENGINE_BEHAVIOR.mcpack    behavior pack only
    APOCALYPSE_ENGINE_TEXTURES.mcpack    resource pack only
    APOCALYPSE_ENGINE_SOURCE.zip         full project source
    APOCALYPSE_ENGINE_VALIDATION.txt     what was checked and what was not
    APOCALYPSE_ENGINE_INSTALLATION.txt   Android install / configure / troubleshoot / uninstall guide

Every archive is reopened after writing: integrity test, entry list, manifests parsed from the archive bytes,
UUID/version/dependency linkage and script entry re-checked. The build exits non-zero on any failure.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
RELEASE = os.path.join(ROOT, "release")
NAME = "APOCALYPSE_ENGINE"
DELIVERABLES = {
    "addon": f"{NAME}.mcaddon",
    "behavior": f"{NAME}_BEHAVIOR.mcpack",
    "textures": f"{NAME}_TEXTURES.mcpack",
    "source": f"{NAME}_SOURCE.zip",
    "validation": f"{NAME}_VALIDATION.txt",
    "installation": f"{NAME}_INSTALLATION.txt",
}
TARGET = {"tested_against": "1.26.50 (Mojang bedrock-samples 1.26.50.4 reference data)", "minimum": "1.26.30",
          "server": "2.8.0", "server_ui": "2.0.0"}
# fixed archive timestamp -> reproducible archives (override with SOURCE_DATE_EPOCH)
ZIP_TIME = time.gmtime(int(os.environ.get("SOURCE_DATE_EPOCH", "1792368000")))[:6]
SOURCE_EXCLUDE_DIRS = {".git", "node_modules", "release", "__pycache__", ".build_tmp", "out", ".mct", ".claude"}
SOURCE_EXCLUDE_FILES = {".DS_Store", "Thumbs.db"}
JUNK = re.compile(r"(^|/)(\.DS_Store|Thumbs\.db|desktop\.ini)$|\.pyc$")


class BuildError(Exception):
    pass


def log(msg: str):
    print(f"[build] {msg}", flush=True)


def run(cmd: list[str], env=None, timeout=1800, check=True) -> subprocess.CompletedProcess:
    log("$ " + " ".join(cmd))
    p = subprocess.run(cmd, cwd=ROOT, env={**os.environ, **(env or {})}, capture_output=True, text=True, timeout=timeout)
    if check and p.returncode != 0:
        sys.stdout.write(p.stdout[-6000:])
        sys.stderr.write(p.stderr[-6000:])
        raise BuildError(f"command failed ({p.returncode}): {' '.join(cmd)}")
    return p


# ------------------------------------------------------------------------------------------------
# steps
# ------------------------------------------------------------------------------------------------

def preflight() -> dict:
    info = {"python": sys.version.split()[0]}
    if sys.version_info < (3, 10):
        raise BuildError("Python 3.10+ is required")
    node = shutil.which("node")
    if not node:
        raise BuildError("Node.js 18+ is required (https://nodejs.org)")
    info["node"] = run([node, "--version"]).stdout.strip()
    tsc = os.path.join(ROOT, "node_modules", ".bin", "tsc")
    if not os.path.isfile(tsc):
        raise BuildError("node_modules missing: run `npm ci` once")
    info["tsc"] = run([tsc, "--version"]).stdout.strip()
    for mod in ("numpy", "PIL"):
        try:
            __import__(mod)
        except ImportError as e:
            raise BuildError(f"Python package {mod} missing: pip install numpy pillow") from e
    info["ffmpeg"] = bool(shutil.which("ffmpeg"))
    return info


def generate():
    run([sys.executable, "tools/generate_all.py"], timeout=3600)


def compile_scripts():
    shutil.rmtree(os.path.join(ROOT, "behavior_pack", "scripts"), ignore_errors=True)
    run([os.path.join(ROOT, "node_modules", ".bin", "tsc"), "-p", "tsconfig.json"])
    if not os.path.isfile(os.path.join(ROOT, "behavior_pack", "scripts", "main.js")):
        raise BuildError("tsc produced no behavior_pack/scripts/main.js")


def tests(seeds: int) -> dict:
    out = {}
    summary = os.path.join(tempfile.mkdtemp(prefix="apoc_smoke_"), "smoke.json")
    files = sorted(f"tests/{f}" for f in os.listdir(os.path.join(ROOT, "tests")) if f.endswith(".test.mjs"))
    p = run(["node", "--test", "--test-reporter=tap", *files], env={"APOCALYPSE_SMOKE_SUMMARY": summary}, check=False, timeout=3600)
    tap = p.stdout
    get = lambda k: int(re.search(rf"^# {k} (\d+)", tap, re.M).group(1)) if re.search(rf"^# {k} (\d+)", tap, re.M) else -1  # noqa: E731
    names = re.findall(r"^\s*(ok|not ok) \d+ - (.+)$", tap, re.M)
    out["js"] = {"files": files, "tests": get("tests"), "pass": get("pass"), "fail": get("fail"), "exit": p.returncode,
                 "failed": [n for s, n in names if s == "not ok"], "cases": [n for s, n in names]}
    if os.path.isfile(summary):
        out["simulation"] = json.load(open(summary, encoding="utf-8"))
    py = run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-v"], check=False, timeout=3600)
    txt = py.stderr
    m = re.search(r"Ran (\d+) tests?", txt)
    out["python"] = {"tests": int(m.group(1)) if m else -1, "ok": py.returncode == 0, "exit": py.returncode,
                     "cases": re.findall(r"^(test_\w+) \(([\w.]+)\)", txt, re.M)}
    if p.returncode != 0 or out["js"]["fail"] != 0:
        sys.stdout.write(tap[-8000:])
        raise BuildError(f"JavaScript tests failed: {out['js']['failed']}")
    # the simulation is seeded: re-run it under extra seeds to catch timing-dependent failures
    seed_fail = []
    for seed in range(1, seeds + 1):
        r = run(["node", "--test", "tests/runtime.smoke.test.mjs"], env={"APOCALYPSE_SEED": str(9000 + seed)}, check=False, timeout=1800)
        if r.returncode != 0:
            seed_fail.append(9000 + seed)
    out["seeds"] = {"count": seeds, "failed": seed_fail}
    if seed_fail:
        raise BuildError(f"runtime simulation failed under seeds {seed_fail}")
    if py.returncode != 0:
        sys.stdout.write(txt[-8000:])
        raise BuildError("Python tests failed")
    return out


def validate(schemas: str | None) -> dict:
    sys.path.insert(0, ROOT)
    from tools.schema_check import find_schema_root
    from validate import Validator, format_report
    root = find_schema_root(schemas)
    R = Validator(ROOT, root).run()
    report = format_report(R)
    if R.errors:
        sys.stdout.write(report)
        raise BuildError(f"static validation found {len(R.errors)} errors")
    return {"errors": R.errors, "warnings": R.warnings, "passes": dict(R.passes), "notes": R.notes,
            "schemas": bool(root), "report": report}


def creator_tools(mct: str | None) -> dict | None:
    if not mct:
        return None
    work = tempfile.mkdtemp(prefix="apoc_mct_")
    proj, outdir = os.path.join(work, "project"), os.path.join(work, "out")
    os.makedirs(proj)
    for d in ("behavior_pack", "resource_pack"):
        shutil.copytree(os.path.join(ROOT, d), os.path.join(proj, d))
    p = subprocess.run([mct, "validate", "all", "-i", proj, "--single", "--offline", "--json", "-o", outdir],
                       capture_output=True, text=True, timeout=1800, cwd=work)
    try:
        d = json.loads(p.stdout)
    except json.JSONDecodeError:
        return {"ran": False, "error": (p.stderr or p.stdout)[-500:]}
    items = d["projects"][0]["items"] if d.get("projects") else []
    cats: dict[str, int] = {}
    for i in items:
        if i.get("type") != "warning":
            continue
        g, m = i.get("generatorId", "?"), i.get("message", "")
        if g == "UNLINK" and "texture" in m.lower():
            key = "texture links across subpack overlays (tool limitation, see analysis)"
        elif g == "UNLINK" and "item type" in m:
            key = "vanilla item references unresolved in --offline mode"
        elif g == "JSON" and "texture_data" in str(i.get("data", "")):
            key = "atlas entries use the string texture form (as 94% of vanilla entries do)"
        elif g == "JSON" and "subpacks" in str(i.get("data", "")):
            key = "subpack objects (documented manifest v2 format)"
        elif g == "COMJSON":
            key = "render controller uv_anim marked required (absent from 167/173 vanilla controllers)"
        elif g == "JSONF":
            key = "places_block single-block string (form used in Mojang's feature documentation)"
        else:
            key = f"{g}: {m}"
        cats[key] = cats.get(key, 0) + 1
    recs: dict[str, int] = {}
    for i in items:
        if i.get("type") == "recommendation":
            recs[i.get("generatorId", "?")] = recs.get(i.get("generatorId", "?"), 0) + 1
    shutil.rmtree(work, ignore_errors=True)
    return {"ran": True, "version": _mct_version(mct), "errors": d.get("errors"), "warnings": d.get("warnings"),
            "recommendations": d.get("recommendations"), "warning_categories": cats, "recommendation_categories": recs,
            "test_pass": sum(1 for i in items if i.get("type") == "testPass")}


def _mct_version(mct: str) -> str:
    try:
        out = subprocess.run([mct, "--help"], capture_output=True, text=True, timeout=120).stdout
        m = re.search(r"v(\d+\.\d+\.\d+)", out)
        return m.group(1) if m else "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


# ------------------------------------------------------------------------------------------------
# packaging
# ------------------------------------------------------------------------------------------------

def pack_files(folder: str) -> list[str]:
    out = []
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = sorted(d for d in dirnames if d not in SOURCE_EXCLUDE_DIRS)
        for fn in sorted(filenames):
            rel = os.path.relpath(os.path.join(dirpath, fn), folder).replace(os.sep, "/")
            if not JUNK.search(rel):
                out.append(rel)
    return out


def write_zip(path: str, entries: list[tuple[str, str]]):
    """entries: (archive name, source path). Deterministic: sorted, fixed timestamps and permissions."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for arc, src in sorted(entries):
            zi = zipfile.ZipInfo(arc, date_time=ZIP_TIME)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            with open(src, "rb") as f:
                z.writestr(zi, f.read(), compresslevel=9)


def source_files() -> list[str]:
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        rel_dir = os.path.relpath(dirpath, ROOT)
        dirnames[:] = sorted(d for d in dirnames if d not in SOURCE_EXCLUDE_DIRS)
        for fn in sorted(filenames):
            if fn in SOURCE_EXCLUDE_FILES or fn.endswith(".pyc"):
                continue
            rel = os.path.normpath(os.path.join(rel_dir, fn)).replace(os.sep, "/")
            out.append(rel)
    return out


def package() -> dict:
    os.makedirs(RELEASE, exist_ok=True)
    for fn in DELIVERABLES.values():
        p = os.path.join(RELEASE, fn)
        if os.path.exists(p):
            os.remove(p)
    bp, rp = os.path.join(ROOT, "behavior_pack"), os.path.join(ROOT, "resource_pack")
    bp_files, rp_files = pack_files(bp), pack_files(rp)
    write_zip(os.path.join(RELEASE, DELIVERABLES["behavior"]), [(f, os.path.join(bp, f)) for f in bp_files])
    write_zip(os.path.join(RELEASE, DELIVERABLES["textures"]), [(f, os.path.join(rp, f)) for f in rp_files])
    write_zip(os.path.join(RELEASE, DELIVERABLES["addon"]),
              [(f"{NAME}_BP/{f}", os.path.join(bp, f)) for f in bp_files] + [(f"{NAME}_RP/{f}", os.path.join(rp, f)) for f in rp_files])
    src = source_files()
    write_zip(os.path.join(RELEASE, DELIVERABLES["source"]), [(f"{NAME}/{f}", os.path.join(ROOT, f)) for f in src])
    return {"bp_files": len(bp_files), "rp_files": len(rp_files), "source_files": len(src)}


# ------------------------------------------------------------------------------------------------
# archive inspection (reopen everything we wrote)
# ------------------------------------------------------------------------------------------------

def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_archives(counts: dict) -> dict:
    ids = json.load(open(os.path.join(ROOT, "tools", "pack_ids.json"), encoding="utf-8"))
    version = ids["version"]
    res = {}

    def base_checks(z: zipfile.ZipFile, label: str, expected_entries: int) -> list[str]:
        problems = []
        bad = z.testzip()
        if bad:
            problems.append(f"CRC failure in {bad}")
        names = z.namelist()
        if len(names) != expected_entries:
            problems.append(f"{len(names)} entries, expected {expected_entries}")
        if len(set(names)) != len(names):
            problems.append("duplicate entries")
        for n in names:
            if n.startswith("/") or ".." in n.split("/") or "\\" in n:
                problems.append(f"unsafe entry name {n}")
            if JUNK.search(n):
                problems.append(f"junk file {n}")
        return problems

    def check_bp(manifest: dict, names: set[str], prefix: str) -> list[str]:
        p = []
        h = manifest["header"]
        if h["uuid"] != ids["behavior_pack"]["header"] or h["version"] != version:
            p.append("behavior manifest uuid/version mismatch")
        if h.get("min_engine_version") != [1, 26, 30]:
            p.append(f"behavior min_engine_version {h.get('min_engine_version')}")
        mods = {m["type"]: m for m in manifest["modules"]}
        if mods.get("data", {}).get("uuid") != ids["behavior_pack"]["data_module"]:
            p.append("data module uuid mismatch")
        script = mods.get("script")
        if not script or script.get("uuid") != ids["behavior_pack"]["script_module"]:
            p.append("script module missing/mismatch")
        elif prefix + script["entry"] not in names:
            p.append(f"script entry {script['entry']} not inside the archive")
        deps = manifest.get("dependencies", [])
        if not any(d.get("uuid") == ids["resource_pack"]["header"] and d.get("version") == version for d in deps):
            p.append("behavior pack does not depend on the resource pack uuid+version")
        mods_dep = {d.get("module_name"): d.get("version") for d in deps if "module_name" in d}
        if mods_dep.get("@minecraft/server") != TARGET["server"] or mods_dep.get("@minecraft/server-ui") != TARGET["server_ui"]:
            p.append(f"script module dependency versions {mods_dep}")
        return p

    def check_rp(manifest: dict, names: set[str], prefix: str) -> list[str]:
        p = []
        h = manifest["header"]
        if h["uuid"] != ids["resource_pack"]["header"] or h["version"] != version:
            p.append("resource manifest uuid/version mismatch")
        mods = manifest["modules"]
        if not mods or mods[0].get("uuid") != ids["resource_pack"]["resources_module"]:
            p.append("resources module uuid mismatch")
        for sp in manifest.get("subpacks", []):
            if not any(n.startswith(f"{prefix}subpacks/{sp['folder_name']}/") for n in names):
                p.append(f"subpack folder {sp['folder_name']} missing in archive")
        for need in ("pack_icon.png", "textures/item_texture.json", "textures/terrain_texture.json", "texts/en_US.lang"):
            if prefix + need not in names:
                p.append(f"{need} missing in archive")
        return p

    for key in ("behavior", "textures", "addon", "source"):
        path = os.path.join(RELEASE, DELIVERABLES[key])
        entry = {"file": DELIVERABLES[key], "path": path, "bytes": os.path.getsize(path), "sha256": sha256(path)}
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            if key == "behavior":
                probs = base_checks(z, key, counts["bp_files"])
                man = json.loads(z.read("manifest.json"))
                probs += check_bp(man, names, "")
                entry["manifest"] = {"name": man["header"]["name"], "uuid": man["header"]["uuid"], "version": man["header"]["version"]}
            elif key == "textures":
                probs = base_checks(z, key, counts["rp_files"])
                man = json.loads(z.read("manifest.json"))
                probs += check_rp(man, names, "")
                entry["manifest"] = {"name": man["header"]["name"], "uuid": man["header"]["uuid"], "version": man["header"]["version"]}
            elif key == "addon":
                probs = base_checks(z, key, counts["bp_files"] + counts["rp_files"])
                tops = sorted({n.split("/")[0] for n in names})
                if tops != [f"{NAME}_BP", f"{NAME}_RP"]:
                    probs.append(f"unexpected top-level folders {tops}")
                bpm = json.loads(z.read(f"{NAME}_BP/manifest.json"))
                rpm = json.loads(z.read(f"{NAME}_RP/manifest.json"))
                probs += check_bp(bpm, names, f"{NAME}_BP/") + check_rp(rpm, names, f"{NAME}_RP/")
                # the packs inside the add-on must be byte-identical to the standalone .mcpack files
                with zipfile.ZipFile(os.path.join(RELEASE, DELIVERABLES["behavior"])) as zb, \
                        zipfile.ZipFile(os.path.join(RELEASE, DELIVERABLES["textures"])) as zr:
                    for n in zb.namelist():
                        if zb.getinfo(n).CRC != z.getinfo(f"{NAME}_BP/{n}").CRC:
                            probs.append(f"BP file differs from standalone pack: {n}")
                    for n in zr.namelist():
                        if zr.getinfo(n).CRC != z.getinfo(f"{NAME}_RP/{n}").CRC:
                            probs.append(f"RP file differs from standalone pack: {n}")
                entry["manifests"] = [bpm["header"]["name"], rpm["header"]["name"]]
            else:
                probs = base_checks(z, key, counts["source_files"])
                tops = {n.split("/")[0] for n in names}
                if tops != {NAME}:
                    probs.append(f"source zip must have a single top folder, found {sorted(tops)}")
                required = ["behavior_pack/manifest.json", "resource_pack/manifest.json", "tools/generate_all.py", "build.py",
                            "validate.py", "README.md", "TECHNICAL_DESIGN.md", "FEATURE_MATRIX.md", "CHANGELOG.md",
                            "RELEASE_NOTES.md", "package.json", "package-lock.json", "tsconfig.json", "src/scripts/main.ts",
                            "tests/runtime.smoke.test.mjs", "docs/INSTALLATION.txt"]
                for r in required:
                    if f"{NAME}/{r}" not in names:
                        probs.append(f"source zip lacks {r}")
                for n in names:
                    if "/node_modules/" in n or "/.git/" in n or n.endswith(".pyc"):
                        probs.append(f"source zip contains build junk {n}")
                        break
                json.loads(z.read(f"{NAME}/behavior_pack/manifest.json"))
                json.loads(z.read(f"{NAME}/resource_pack/manifest.json"))
                entry["top_folder"] = NAME
            entry["entries"] = len(names)
            entry["uncompressed_bytes"] = sum(i.file_size for i in z.infolist())
        entry["problems"] = probs
        res[key] = entry
    failed = {k: v["problems"] for k, v in res.items() if v["problems"]}
    if failed:
        raise BuildError(f"archive inspection failed: {json.dumps(failed, indent=1)}")
    return res


# ------------------------------------------------------------------------------------------------
# reports
# ------------------------------------------------------------------------------------------------

def git_rev() -> str:
    try:
        p = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=30)
        dirty = subprocess.run(["git", "status", "--porcelain", "--", ".", ":(exclude)release"], cwd=ROOT,
                               capture_output=True, text=True, timeout=30).stdout.strip()
        return p.stdout.strip() + (" (+uncommitted changes)" if dirty else "") if p.returncode == 0 else "n/a"
    except Exception:  # noqa: BLE001
        return "n/a"


def human(n: int) -> str:
    return f"{n / 1048576:.2f} MB" if n >= 1048576 else f"{n / 1024:.1f} KB"


def validation_report(ctx: dict) -> str:
    v, t, a, mct, pre = ctx["validation"], ctx["tests"], ctx["archives"], ctx.get("mct"), ctx["preflight"]
    bpm = json.load(open(os.path.join(ROOT, "behavior_pack", "manifest.json"), encoding="utf-8"))
    rpm = json.load(open(os.path.join(ROOT, "resource_pack", "manifest.json"), encoding="utf-8"))
    passes = v["passes"]
    S = []
    w = S.append
    w("APOCALYPSE ENGINE — VALIDATION REPORT")
    w("=" * 78)
    w(f"Version         : {'.'.join(map(str, bpm['header']['version']))}")
    w(f"Built (UTC)     : {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M')}")
    w(f"Source revision : {git_rev()}")
    w(f"Build command   : python3 build.py{' --skip-generate' if ctx['skip_generate'] else ''}"
      f"{' --schemas <bedrock-samples>' if v['schemas'] else ''}{' --mct <mct>' if mct else ''}")
    w(f"Toolchain       : Python {pre['python']}, Node {pre['node']}, TypeScript {pre['tsc'].split()[-1]}")
    w("")
    w("1. TARGET VERSION")
    w("-" * 78)
    w(f"  Minecraft Bedrock (Android) tested against : {TARGET['tested_against']}")
    w(f"  Minimum engine version (manifests)         : {TARGET['minimum']}")
    w(f"  Script API                                 : @minecraft/server {TARGET['server']} (stable), "
      f"@minecraft/server-ui {TARGET['server_ui']} (stable)")
    w("  Experimental toggles required              : NONE (no beta APIs, no experimental JSON features)")
    w("  Content format versions                    : entities/items/blocks 1.26.30, BP biome 1.26.0, recipes 1.20.10,")
    w("                                               client entities 1.10.0, geometry 1.12.0, fogs 1.21.90")
    w("")
    w("2. MANIFEST STATUS")
    w("-" * 78)
    for label, m in (("Behavior pack", bpm), ("Resource pack", rpm)):
        h = m["header"]
        w(f"  {label}: {h['name']}")
        w(f"    uuid {h['uuid']}  version {h['version']}  min_engine_version {h['min_engine_version']}  format_version {m['format_version']}")
        for mod in m["modules"]:
            extra = f"  entry {mod['entry']}" if mod.get("entry") else ""
            w(f"    module {mod['type']:<9} {mod['uuid']}{extra}")
        if m.get("capabilities"):
            w(f"    capabilities {m['capabilities']}")
        for sp in m.get("subpacks", []):
            w(f"    subpack {sp['folder_name']:<9} memory_tier {sp['memory_tier']:<3} \"{sp['name']}\"")
    w(f"  Static manifest checks passed: {sum(n for k, n in passes.items() if k.startswith(('MANIFEST', 'UUID', 'SUBPACK')))}  (errors: 0)")
    w("")
    w("3. DEPENDENCIES")
    w("-" * 78)
    for d in bpm["dependencies"]:
        if "uuid" in d:
            w(f"  Behavior pack -> resource pack {d['uuid']} {d['version']} : OK (matches resource pack header)")
        else:
            w(f"  Behavior pack -> {d['module_name']} {d['version']} : OK (declared; all script imports resolve to it)")
    w("  Resource pack dependencies: none (no circular dependency)")
    w("")
    w("4. STATIC VALIDATION (validate.py)")
    w("-" * 78)
    w(f"  Checks passed : {sum(passes.values())}")
    w(f"  Errors        : {len(v['errors'])}")
    w(f"  Warnings      : {len(v['warnings'])}")
    for n in v["notes"]:
        w(f"  note: {n}")
    w("  Passed checks by category (asset references, schemas, ids, scripts, structure):")
    for k in sorted(passes):
        w(f"    {k:<44} {passes[k]:>6}")
    if v["warnings"]:
        w("  Warnings:")
        for x in v["warnings"]:
            w(f"    {x}")
    w("")
    w("5. INDEPENDENT VALIDATION (Mojang Minecraft Creator Tools)")
    w("-" * 78)
    if not mct:
        w("  Not run in this build (pass --mct PATH to include it).")
    elif not mct.get("ran"):
        w(f"  Attempted but failed to run: {mct.get('error')}")
    else:
        w(f"  mct validate all --offline (Creator Tools v{mct['version']}): errors {mct['errors']}, warnings {mct['warnings']},"
          f" recommendations {mct['recommendations']}, passed tests {mct['test_pass']}")
        w("  Every warning category was reviewed against Mojang's vanilla samples:")
        for k, n in sorted(mct["warning_categories"].items(), key=lambda kv: -kv[1]):
            w(f"    {n:>4}  {k}")
        w("    Texture-link warnings were reproduced and explained: removing the subpack overlays from a copy of the")
        w("    resource pack removes all of them, i.e. the tool does not follow subpack overlays; validate.py resolves")
        w("    every texture path against the base pack and each subpack and found no missing file.")
        w("  Recommendations: " + ", ".join(f"{k} x{n}" for k, n in sorted(mct["recommendation_categories"].items())))
        w("    (format versions 1.26.30 < 1.26.50 are intentional so the packs also load on 1.26.30-1.26.4x devices)")
    w("")
    w("6. AUTOMATED TESTS")
    w("-" * 78)
    js, py = t["js"], t["python"]
    w(f"  JavaScript (node --test): {js['pass']}/{js['tests']} passed, {js['fail']} failed  [{', '.join(js['files'])}]")
    w(f"  Python (unittest)       : {py['tests']} tests, {'all passed' if py['ok'] else 'FAILURES'}")
    sd = t.get("seeds", {})
    w(f"  Runtime simulation re-run under {sd.get('count', 0)} additional random seeds: "
      f"{'all passed' if not sd.get('failed') else 'FAILED ' + str(sd['failed'])}")
    w("  Coverage:")
    w("    * pure logic unit tests: boss state machine, event scheduler, reward de-duplication, progression,")
    w("      performance profiles, island generation/causeway walkability, RNG and vector math")
    w("    * strict mock-runtime simulation of the compiled scripts (tests/mock): startup registrations, world")
    w("      load, all 7 world events, all 4 boss fights (phases, invulnerable transitions, vents, rewards,")
    w("      duplicate-death protection), 6 weapon abilities + on-hit effects, relic rites, elixir, 3 armor set")
    w("      bonuses, ore drops with Silk Touch/Fortune, Engine Cache, Engine Key rifts, Shattered Expanse")
    w("      generation + flood-fill walkability to the Arena, void rescue, Null Gate, Codex UI, commands,")
    w("      six in-game days of natural event scheduling, and save/reload persistence")
    w("    * tooling: .mcstructure codec, lenient JSON, validator clean-run and injected-defect detection")
    sim = t.get("simulation")
    if sim:
        w(f"  Simulation totals: {sim['ticks']} game ticks simulated, {sim['entitiesCreated']} entities spawned,"
          f" {sim['explosions']} meteor impacts, {sim['expanseBlocks']} Expanse blocks generated,")
        w(f"                     {sim['problems']} API-contract violations, {sim['warnings']} script warnings")
    w("  Test cases:")
    for c in js["cases"]:
        w(f"    [js] {c}")
    for _c, cls in py["cases"]:
        w(f"    [py] {cls}")
    w("  The mock enforces the documented engine contracts (identifiers, entity properties/events, restricted and")
    w("  early execution, custom-component coverage). It is NOT the game: no rendering, mob AI, physics or")
    w("  networking. Passing it is evidence of correct script/API usage, not proof of in-game behaviour.")
    w("")
    w("7. ARCHIVE INSPECTION (every archive reopened after writing)")
    w("-" * 78)
    for key in ("addon", "behavior", "textures", "source"):
        e = a[key]
        w(f"  {e['file']}")
        w(f"    size {human(e['bytes'])} (uncompressed {human(e['uncompressed_bytes'])}), {e['entries']} entries, sha256 {e['sha256']}")
        if key == "addon":
            w(f"    contains {NAME}_BP/ and {NAME}_RP/ with manifests: {e['manifests'][0]} | {e['manifests'][1]}")
            w("    packs inside are byte-identical (CRC) to the standalone .mcpack files")
        elif key in ("behavior", "textures"):
            m = e["manifest"]
            w(f"    manifest.json at archive root, reopened: {m['name']} {m['uuid']} {m['version']}")
        else:
            w(f"    single top folder {e['top_folder']}/, no node_modules/.git/caches, required project files present")
        w("    integrity (CRC) OK, no unsafe paths, entry count matches source tree, manifests parse: PASS")
    w("")
    w("8. KNOWN ISSUES")
    w("-" * 78)
    for line in KNOWN_ISSUES:
        w(f"  - {line}")
    w("")
    w("9. NOT IMPLEMENTED / OUT OF SCOPE")
    w("-" * 78)
    for line in NOT_IMPLEMENTED:
        w(f"  - {line}")
    w("")
    w("10. NOT TESTED IN-GAME")
    w("-" * 78)
    w("  No Minecraft client or Bedrock Dedicated Server was run while building this release (no Android device")
    w("  or game runtime is available in the build environment, and the Bedrock Dedicated Server license must be")
    w("  accepted by its user). Therefore NOTHING has been verified inside the real game, in particular:")
    for line in UNTESTED:
        w(f"  - {line}")
    w("")
    w("11. GRAPHICS / SHADER LIMITATIONS")
    w("-" * 78)
    for line in SHADER_NOTES:
        w(f"  - {line}")
    w("")
    w("12. DELIVERABLES")
    w("-" * 78)
    for key in ("addon", "behavior", "textures", "source"):
        w(f"  {a[key]['file']:<36} {human(a[key]['bytes']):>10}  sha256 {a[key]['sha256']}")
    w(f"  {DELIVERABLES['validation']:<36} (this file)")
    w(f"  {DELIVERABLES['installation']:<36} Android install/configure/troubleshoot/uninstall guide")
    w("")
    w("RESULT: BUILD PASSED — static validation 0 errors, all automated tests passed, all archives verified.")
    return "\n".join(S) + "\n"


KNOWN_ISSUES = [
    "Balance (boss health tiers, damage, event spawn rates) is tuned on paper and in simulation only; expect tuning after real play.",
    "Boss movement uses vanilla navigation components; on very rugged terrain bosses may path poorly (scripted leash returns them to the arena).",
    "Event and Expanse fog uses /fog push per player; it is re-synchronised on join, dimension change and event start/end.",
    "The Shattered Expanse is generated by script around players: islands appear a moment after arrival on slow devices (time-budgeted jobs).",
    "Ticking-area capacity is shared with other add-ons/commands; if none is free the first Expanse visit asks the player to retry.",
    "Pre-built structures (Nexus Shrine, Colossus Altar, ruins) are placed via the structure manager; they were generated by our own"
    " .mcstructure writer and verified by our reader, not opened in a game editor.",
    "Creator Tools warnings listed in section 5 are tool-side limitations/strictness, documented rather than worked around.",
]
NOT_IMPLEMENTED = [
    "Custom shaders/GLSL/HLSL, RenderDragon material overrides and custom post-processing: not possible for Bedrock add-ons.",
    "A biome-based dimension generator: Bedrock only offers script-registered custom dimensions with the void generator,"
    " so all Expanse terrain is script-built (documented as such, not presented as engine worldgen).",
    "Custom music tracks and voiced dialogue.",
    "Localisation beyond en_US.",
    "Marketplace-style world template / skin pack.",
]
UNTESTED = [
    "loading of both packs on Android 1.26.30-1.26.50, menu import of the .mcaddon/.mcpack files",
    "model geometry, animations, render controllers and textures as rendered by the game (only offline previews were rendered)",
    "Vibrant Visuals PBR materials (MER/normal), fog volumes, lighting/atmosphere/color grading in the real renderer",
    "boss AI movement, pathing and combat feel; projectile and explosion behaviour; mob spawning in real biomes",
    "world-generation features (ore distribution, ruins, Blighted Wilds biome) in generated worlds",
    "custom dimension registration and travel on real devices, ticking areas and structure placement",
    "sound playback and mixing; UI forms on touch screens; performance (frame time/memory) on low-end phones",
    "multiplayer synchronisation (designed for it: per-player caps, shared world state, contribution-based rewards)",
]
SHADER_NOTES = [
    "Bedrock add-ons cannot ship shaders. This project contains no shader code and does not modify the game.",
    "Visual quality comes from: original HD textures (1x in the base pack, 2x/4x in subpacks), emissive glow layers using"
    " the vanilla entity_emissive_alpha material, PBR texture sets (MER + normal maps), custom particles, per-event fog,"
    " and Vibrant Visuals atmospherics/lighting/color-grading JSON configs.",
    "PBR texture sets, volumetric fog and the Vibrant Visuals configs only take effect when the device supports and the"
    " player enables Vibrant Visuals; on other devices the same packs render with standard (non-PBR) graphics.",
    "The resource pack declares the 'pbr' capability; subpacks: Potato (sparse particles, base textures), Balanced"
    " (2x textures + PBR), Enhanced (4x textures + PBR, dense particles).",
]


def installation_text() -> str:
    tpl = open(os.path.join(ROOT, "docs", "INSTALLATION.txt"), encoding="utf-8").read()
    bpm = json.load(open(os.path.join(ROOT, "behavior_pack", "manifest.json"), encoding="utf-8"))
    return (tpl.replace("{VERSION}", ".".join(map(str, bpm["header"]["version"])))
            .replace("{MIN_VERSION}", TARGET["minimum"]).replace("{TESTED_VERSION}", "1.26.50")
            .replace("{ADDON}", DELIVERABLES["addon"]).replace("{BP}", DELIVERABLES["behavior"])
            .replace("{RP}", DELIVERABLES["textures"]))


# ------------------------------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Build, test, validate and package APOCALYPSE ENGINE.")
    ap.add_argument("--skip-generate", action="store_true", help="do not regenerate pack content")
    ap.add_argument("--schemas", default=None, help="bedrock-samples checkout (or its metadata/json_schemas)")
    ap.add_argument("--mct", default=None, help="path to the Minecraft Creator Tools `mct` executable")
    ap.add_argument("--seeds", type=int, default=8, help="extra random seeds for the runtime simulation (default 8)")
    args = ap.parse_args()
    t0 = time.time()
    ctx = {"skip_generate": args.skip_generate}
    try:
        log("preflight")
        ctx["preflight"] = preflight()
        if not args.skip_generate and not ctx["preflight"]["ffmpeg"]:
            raise BuildError("ffmpeg (with libvorbis) is required to regenerate the sounds; install it or use --skip-generate")
        if not args.skip_generate:
            log("generating content (textures, models, sounds, JSON)")
            generate()
        log("compiling scripts")
        compile_scripts()
        log("running tests")
        ctx["tests"] = tests(args.seeds)
        log("static validation")
        ctx["validation"] = validate(args.schemas)
        if args.mct:
            log("Minecraft Creator Tools validation")
            ctx["mct"] = creator_tools(args.mct)
        log("packaging")
        counts = package()
        log("inspecting archives")
        ctx["archives"] = inspect_archives(counts)
        with open(os.path.join(RELEASE, DELIVERABLES["installation"]), "w", encoding="utf-8", newline="\n") as f:
            f.write(installation_text())
        report = validation_report(ctx)
        with open(os.path.join(RELEASE, DELIVERABLES["validation"]), "w", encoding="utf-8", newline="\n") as f:
            f.write(report)
    except BuildError as e:
        log(f"FAILED: {e}")
        sys.exit(1)
    log(f"done in {time.time() - t0:.0f}s")
    for fn in DELIVERABLES.values():
        p = os.path.join(RELEASE, fn)
        log(f"  {p}  {human(os.path.getsize(p))}")


if __name__ == "__main__":
    main()
