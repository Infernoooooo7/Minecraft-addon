"""Minimal little-endian NBT writer/reader for Bedrock .mcstructure files.

Layout (Bedrock structure format_version 1):
  root{ format_version:int, size:list<int>[3],
        structure{ block_indices:list<list<int>>[primary, secondary], entities:list<compound>,
                   palette{ default{ block_palette:list<compound{name,states,version}>, block_position_data{} } } },
        structure_world_origin:list<int>[3] }
Block index order: x-major, then y, then z (z fastest). -1 = structure void (leaves terrain untouched).
"""
from __future__ import annotations

import io
import struct

# block state version written into palette entries: 1.21.40.0 (major<<24 | minor<<16 | patch<<8 | rev)
BLOCK_VERSION = (1 << 24) | (21 << 16) | (40 << 8)

END, BYTE, SHORT, INT, LONG, FLOAT, DOUBLE, BYTE_ARRAY, STRING, LIST, COMPOUND = range(11)


class Int(int):
    pass


class Byte(int):
    pass


def _w_str(buf, s: str):
    b = s.encode("utf-8")
    buf.write(struct.pack("<H", len(b)))
    buf.write(b)


def _tag_type(v) -> int:
    if isinstance(v, Byte) or isinstance(v, bool):
        return BYTE
    if isinstance(v, int):
        return INT
    if isinstance(v, float):
        return FLOAT
    if isinstance(v, str):
        return STRING
    if isinstance(v, list):
        return LIST
    if isinstance(v, dict):
        return COMPOUND
    raise TypeError(type(v))


def _w_payload(buf, t: int, v, list_type: int | None = None):
    if t == BYTE:
        buf.write(struct.pack("<b", int(v)))
    elif t == INT:
        buf.write(struct.pack("<i", int(v)))
    elif t == FLOAT:
        buf.write(struct.pack("<f", float(v)))
    elif t == STRING:
        _w_str(buf, v)
    elif t == LIST:
        et = list_type if list_type is not None else (_tag_type(v[0]) if v else END)
        buf.write(struct.pack("<b", et))
        buf.write(struct.pack("<i", len(v)))
        for e in v:
            _w_payload(buf, et, e)
    elif t == COMPOUND:
        for k, e in v.items():
            et = _tag_type(e)
            buf.write(struct.pack("<b", et))
            _w_str(buf, k)
            _w_payload(buf, et, e)
        buf.write(struct.pack("<b", END))
    else:
        raise ValueError(t)


def write_structure(size: tuple[int, int, int], cells: dict[tuple[int, int, int], tuple[str, dict]]) -> bytes:
    """cells: {(x,y,z): (block_name, states)}; missing cells become structure void."""
    sx, sy, sz = size
    palette: list[tuple[str, tuple]] = []
    pindex: dict = {}
    primary = []
    for x in range(sx):
        for y in range(sy):
            for z in range(sz):
                c = cells.get((x, y, z))
                if c is None:
                    primary.append(-1)
                    continue
                key = (c[0], tuple(sorted(c[1].items())))
                if key not in pindex:
                    pindex[key] = len(palette)
                    palette.append(key)
                primary.append(pindex[key])
    secondary = [-1] * len(primary)
    block_palette = []
    for name, states in palette:
        st = {}
        for k, v in states:
            st[k] = Byte(1 if v else 0) if isinstance(v, bool) else v
        block_palette.append({"name": name, "states": st, "version": Int(BLOCK_VERSION)})
    root = {
        "format_version": Int(1),
        "size": [Int(sx), Int(sy), Int(sz)],
        "structure": {
            "block_indices": [primary, secondary],
            "entities": [],
            "palette": {"default": {"block_palette": block_palette, "block_position_data": {}}},
        },
        "structure_world_origin": [Int(0), Int(0), Int(0)],
    }
    buf = io.BytesIO()
    buf.write(struct.pack("<b", COMPOUND))
    _w_str(buf, "")
    # block_indices is a list of int lists; entities an empty compound list
    _w_compound_root(buf, root)
    return buf.getvalue()


def _w_compound_root(buf, root: dict):
    for k, v in root.items():
        if k == "structure":
            buf.write(struct.pack("<b", COMPOUND))
            _w_str(buf, k)
            st = v
            buf.write(struct.pack("<b", LIST))
            _w_str(buf, "block_indices")
            buf.write(struct.pack("<b", LIST))
            buf.write(struct.pack("<i", 2))
            for layer in st["block_indices"]:
                buf.write(struct.pack("<b", INT))
                buf.write(struct.pack("<i", len(layer)))
                buf.write(struct.pack(f"<{len(layer)}i", *layer))
            buf.write(struct.pack("<b", LIST))
            _w_str(buf, "entities")
            buf.write(struct.pack("<b", COMPOUND))
            buf.write(struct.pack("<i", 0))
            buf.write(struct.pack("<b", COMPOUND))
            _w_str(buf, "palette")
            _w_payload(buf, COMPOUND, st["palette"])
            buf.write(struct.pack("<b", END))
        else:
            t = _tag_type(v)
            buf.write(struct.pack("<b", t))
            _w_str(buf, k)
            _w_payload(buf, t, v, INT if k in ("size", "structure_world_origin") else None)
    buf.write(struct.pack("<b", END))


# ------------------------------------------------------------------------------------------------
# reader (used by validate.py to verify structure files)
# ------------------------------------------------------------------------------------------------

def _r_str(b: io.BytesIO) -> str:
    (n,) = struct.unpack("<H", b.read(2))
    return b.read(n).decode("utf-8")


def _r_payload(b: io.BytesIO, t: int):
    if t == BYTE:
        return struct.unpack("<b", b.read(1))[0]
    if t == SHORT:
        return struct.unpack("<h", b.read(2))[0]
    if t == INT:
        return struct.unpack("<i", b.read(4))[0]
    if t == LONG:
        return struct.unpack("<q", b.read(8))[0]
    if t == FLOAT:
        return struct.unpack("<f", b.read(4))[0]
    if t == DOUBLE:
        return struct.unpack("<d", b.read(8))[0]
    if t == STRING:
        return _r_str(b)
    if t == LIST:
        et = struct.unpack("<b", b.read(1))[0]
        (n,) = struct.unpack("<i", b.read(4))
        return [_r_payload(b, et) for _ in range(n)]
    if t == COMPOUND:
        out = {}
        while True:
            tt = struct.unpack("<b", b.read(1))[0]
            if tt == END:
                return out
            name = _r_str(b)
            out[name] = _r_payload(b, tt)
    raise ValueError(f"unsupported tag {t}")


def read_structure(data: bytes) -> dict:
    b = io.BytesIO(data)
    t = struct.unpack("<b", b.read(1))[0]
    assert t == COMPOUND, "root must be compound"
    _r_str(b)
    return _r_payload(b, COMPOUND)
