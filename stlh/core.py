"""Switch Translation Helper — mesin inti (tanpa GUI): scan, extract, import, patch CRC."""
import fnmatch
import json
import re
import shutil
import struct
import zlib
from pathlib import Path


MB = 1024 * 1024
CONFIG = Path.home() / ".switch_translation_helper.json"


def load_lang() -> str:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8")).get("lang", "id")
    except Exception:
        return "id"


def save_lang(lang: str):
    try:
        CONFIG.write_text(json.dumps({"lang": lang}), encoding="utf-8")
    except OSError:
        pass
TEXT_EXT = {".txt", ".csv", ".tsv", ".xml", ".yml", ".yaml", ".ini", ".lua", ".po", ".srt"}
COMPRESSED = {"zstd", "yaz0", "lz4"}


# ============================================================ util umum
def crc32(data: bytes) -> int:
    """CRC32 standar (zlib). Ganti di sini jika game memakai varian lain (mis. CRC32C)."""
    return zlib.crc32(data) & 0xFFFFFFFF


def detect_type(head: bytes, ext: str) -> str:
    if head[:8] == b"MsgStdBn":
        return "msbt"
    if head[:4] == b"\x28\xb5\x2f\xfd":
        return "zstd"
    if head[:4] == b"Yaz0":
        return "yaz0"
    if head[:4] == b"\x04\x22\x4d\x18":
        return "lz4"
    if head[:4] == b"SARC":
        return "sarc"
    if head[:2] in (b"BY", b"YB") and ext in (".byml", ".byaml", ".bgyml"):
        return "byml"
    if ext == ".json":
        return "json"
    if ext in TEXT_EXT:
        return "text"
    return "binary"


def decode_text(data: bytes):
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig"), "utf-8-sig"
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16"), "utf-16"
    for enc in ("utf-8", "shift_jis", "cp1252"):
        try:
            return data.decode(enc), enc
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", "replace"), "utf-8"


# ============================================================ MSBT
TAG_RE = re.compile(r"\{\{([EF]):(\d+):(\d+)(?::([0-9a-fA-F]*))?\}\}")


def msbt_parse(data: bytes):
    end = "<" if data[8:10] == b"\xff\xfe" else ">"
    enc = data[0x0C]
    nsec = struct.unpack_from(end + "H", data, 0x0E)[0]
    pos, secs = 0x20, []
    for _ in range(nsec):
        magic = data[pos:pos + 4]
        size = struct.unpack_from(end + "I", data, pos + 4)[0]
        secs.append((magic, pos, size))
        pos = (pos + 16 + size + 15) & ~15
    return end, enc, secs


def msbt_decode(raw: bytes, end: str) -> str:
    """UTF-16 -> teks. Control code dijadikan token {{E:grup:tipe:hex}} / {{F:grup:tipe}}."""
    n = len(raw) // 2
    units = struct.unpack(end + f"{n}H", raw[:n * 2])
    out, i = [], 0
    codec = "utf-16-le" if end == "<" else "utf-16-be"
    buf = bytearray()

    def flush():
        if buf:
            out.append(bytes(buf).decode(codec, "replace"))
            buf.clear()

    while i < n:
        u = units[i]
        if u == 0:
            break
        if u == 0x0E and i + 3 < n:
            g, t, ps = units[i + 1], units[i + 2], units[i + 3]
            params = raw[(i + 4) * 2:(i + 4) * 2 + ps]
            flush()
            out.append("{{E:%d:%d:%s}}" % (g, t, params.hex()))
            i += 4 + (ps + 1) // 2
        elif u == 0x0F and i + 2 < n:
            flush()
            out.append("{{F:%d:%d}}" % (units[i + 1], units[i + 2]))
            i += 3
        else:
            buf += struct.pack(end + "H", u)
            i += 1
    flush()
    return "".join(out)


def msbt_encode(text: str, end: str) -> bytes:
    codec = "utf-16-le" if end == "<" else "utf-16-be"
    out, p = bytearray(), 0
    for m in TAG_RE.finditer(text):
        out += text[p:m.start()].encode(codec)
        kind, g, t, h = m.groups()
        if kind == "E":
            params = bytes.fromhex(h or "")
            out += struct.pack(end + "HHHH", 0x0E, int(g), int(t), len(params)) + params
            if len(params) % 2:
                out += b"\0"
        else:
            out += struct.pack(end + "HHH", 0x0F, int(g), int(t))
        p = m.end()
    out += text[p:].encode(codec)
    out += b"\0\0"
    return bytes(out)


def msbt_extract(data: bytes) -> dict:
    end, enc, secs = msbt_parse(data)
    if enc != 1:
        raise ValueError("MSBT non UTF-16 belum didukung")
    for magic, pos, size in secs:
        if magic == b"TXT2":
            base = pos + 16
            cnt = struct.unpack_from(end + "I", data, base)[0]
            offs = struct.unpack_from(end + f"{cnt}I", data, base + 4)
            ents = []
            for i in range(cnt):
                s = base + offs[i]
                e = base + (offs[i + 1] if i + 1 < cnt else size)
                ents.append({"id": i, "original": msbt_decode(data[s:e], end), "translation": ""})
            return {"format": "msbt", "entries": ents}
    raise ValueError("Section TXT2 tidak ditemukan")


def msbt_apply(data: bytes, doc: dict):
    end, enc, secs = msbt_parse(data)
    tr = {e["id"]: e["translation"] for e in doc["entries"] if e.get("translation")}
    out = bytearray(data[:0x20])
    n = 0
    for magic, pos, size in secs:
        body = data[pos + 16:pos + 16 + size]
        if magic == b"TXT2":
            cnt = struct.unpack_from(end + "I", body, 0)[0]
            offs = struct.unpack_from(end + f"{cnt}I", body, 4)
            blobs = []
            for i in range(cnt):
                s = offs[i]
                e = offs[i + 1] if i + 1 < cnt else len(body)
                if i in tr:
                    blobs.append(msbt_encode(tr[i], end))
                    n += 1
                else:
                    blobs.append(body[s:e])
            cur, new_offs = 4 + 4 * cnt, []
            for b in blobs:
                new_offs.append(cur)
                cur += len(b)
            body = (struct.pack(end + "I", cnt) + struct.pack(end + f"{cnt}I", *new_offs)
                    + b"".join(blobs))
        out += magic + struct.pack(end + "I", len(body)) + data[pos + 8:pos + 16] + body
        out += b"\xab" * ((-len(out)) % 16)
    struct.pack_into(end + "I", out, 0x12, len(out))
    return bytes(out), n, []


# ============================================================ teks & JSON
def text_extract(data: bytes) -> dict:
    text, enc = decode_text(data)
    lines = text.splitlines()
    ents = [{"id": i, "original": l, "translation": ""} for i, l in enumerate(lines) if l.strip()]
    return {"format": "text", "encoding": enc, "entries": ents}


def text_apply(data: bytes, doc: dict):
    text, _ = decode_text(data)
    nl = "\r\n" if "\r\n" in text else "\n"
    trailing = text.endswith(("\n", "\r"))
    lines = text.splitlines()
    n = 0
    for e in doc["entries"]:
        if e.get("translation"):
            lines[e["id"]] = e["translation"]
            n += 1
    res = nl.join(lines) + (nl if trailing else "")
    return res.encode(doc.get("encoding", "utf-8")), n, []


def _walk(o, path):
    if isinstance(o, str):
        if any(c.isalpha() for c in o):
            yield path, o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield from _walk(v, path + [k])
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _walk(v, path + [i])


def json_extract(data: bytes) -> dict:
    obj = json.loads(data.decode("utf-8-sig"))
    ents = [{"id": "/".join(map(str, p)), "path": p, "original": s, "translation": ""}
            for p, s in _walk(obj, [])]
    return {"format": "json", "entries": ents}


def json_apply(data: bytes, doc: dict):
    obj = json.loads(data.decode("utf-8-sig"))
    n = 0
    for e in doc["entries"]:
        if e.get("translation"):
            cur = obj
            for k in e["path"][:-1]:
                cur = cur[k]
            cur[e["path"][-1]] = e["translation"]
            n += 1
    return json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8"), n, []


# ============================================================ string biner
IDENT_RE = re.compile(r"[A-Za-z0-9_./:\-\[\]%{}]+")


def _is_noise(s: str, skip_ident: bool) -> bool:
    if not any(c.isalpha() for c in s):
        return True
    return skip_ident and bool(IDENT_RE.fullmatch(s))


def _strong16(t: str) -> bool:
    return (all(ord(c) < 0x250 for c in t)
            or any(0x3000 <= ord(c) <= 0x30FF or 0xFF00 <= ord(c) <= 0xFFEF for c in t))


def find_strings(data: bytes, min_len=6, skip_ident=True) -> list:
    """Cari string UTF-8 dan UTF-16LE ber-terminator null di file biner."""
    unit = rb"(?:[\x20-\x7e\x09\x0a\x0d\xa0-\xff]\x00|[\x00-\xff][\x30-\x9f\xff])"
    p16 = re.compile(unit + rb"{%d,}(?=\x00\x00)" % min_len)
    p8 = re.compile(rb"[\x20-\x7e\x80-\xff\n\r\t]{%d,}(?=\x00)" % min_len)
    mask = bytearray(len(data))
    utf8_seen = bytearray(len(data))  # semua run UTF-8 valid, termasuk yang disaring sebagai noise
    strong, weak, found = [], [], []

    for m in p16.finditer(data):
        s = m.start()
        if s & 1:
            m = p16.match(data, s + 1)
            if not m:
                continue
            s = m.start()
        t = m.group().decode("utf-16-le", "ignore")
        if _is_noise(t, skip_ident):
            continue
        (strong if _strong16(t) else weak).append((s, m.end(), t, "utf-16-le"))

    def accept(s, e, t, enc):
        mask[s:e] = b"\x01" * (e - s)
        found.append((s, e, t, enc))

    for c in strong:
        accept(*c)
    for m in p8.finditer(data):
        s, raw = m.start(), m.group()
        while raw and 0x80 <= raw[0] <= 0xBF:
            raw, s = raw[1:], s + 1
        try:
            t = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        utf8_seen[s:s + len(raw)] = b"\x01" * len(raw)
        if len(t) < min_len // 2 or _is_noise(t, skip_ident):
            continue
        if mask.find(1, s, s + len(raw)) == -1:
            accept(s, s + len(raw), t, "utf-8")
    for c in weak:
        if mask.find(1, c[0], c[1]) == -1 and utf8_seen.find(1, c[0], c[1]) == -1:
            accept(*c)

    ents = []
    for s, e, t, enc in sorted(found):
        term = 2 if enc == "utf-16-le" else 1
        z = 0
        while e + z < len(data) and data[e + z] == 0 and z < 64:
            z += 1
        align_end = (e + term + 3) & ~3
        extra = max(0, min(z - term, align_end - (e + term)))
        ents.append({"id": len(ents), "offset": s, "encoding": enc, "byte_len": e - s,
                     "max_bytes": (e - s) + extra, "original": t, "translation": ""})
    return ents


def binary_extract(data: bytes, min_len=6, skip_ident=True) -> dict:
    return {"format": "binary", "entries": find_strings(data, min_len, skip_ident)}


def binary_apply(data: bytes, doc: dict):
    buf, n, warns = bytearray(data), 0, []
    for e in doc["entries"]:
        tr = e.get("translation")
        if not tr:
            continue
        enc = e["encoding"]
        term = 2 if enc.startswith("utf-16") else 1
        new = tr.encode(enc)
        if len(new) > e["max_bytes"]:
            warns.append(f"offset {e['offset']:#x}: terjemahan {len(new)} byte > batas {e['max_bytes']} byte, dilewati")
            continue
        off = e["offset"]
        region_end = off + e["max_bytes"] + term
        buf[off:region_end] = new + b"\0" * (region_end - off - len(new))
        n += 1
    return bytes(buf), n, warns


# ============================================================ keyword & CRC
def search_keywords(data: bytes, kws) -> dict:
    hits = {}
    for kw in kws:
        offs = []
        for enc in ("utf-8", "utf-16-le", "shift_jis"):
            try:
                pat = kw.encode(enc)
            except UnicodeEncodeError:
                continue
            i = data.find(pat)
            while i != -1 and len(offs) < 5:
                offs.append([i, enc])
                i = data.find(pat, i + 1)
        if offs:
            hits[kw] = offs
    return hits


def detect_crc(data: bytes) -> list:
    """Cek apakah file menyimpan CRC32 dirinya sendiri di awal / akhir."""
    res = []
    if len(data) > 8:
        c_tail, c_head = crc32(data[:-4]), crc32(data[4:])
        for e in "<>":
            if struct.unpack(e + "I", data[-4:])[0] == c_tail:
                res.append({"kind": "embedded_end", "endian": e})
            if struct.unpack(e + "I", data[:4])[0] == c_head:
                res.append({"kind": "embedded_start", "endian": e})
    return res


def _crc_patterns(c: int) -> dict:
    return {"bin_le": struct.pack("<I", c), "bin_be": struct.pack(">I", c),
            "hex_lower": f"{c:08x}".encode(), "hex_upper": f"{c:08X}".encode()}


def find_crc_refs(root: Path, files: list, idx_globs: list, max_bytes: int, log):
    """Cari CRC32 file target di dalam file indeks/manifest yang ditentukan user."""
    targets = [f for f in files if f.get("candidate") and f.get("crc32")]
    idx = [f for f in files if any(
        fnmatch.fnmatch(f["path"], g) or fnmatch.fnmatch(Path(f["path"]).name, g) for g in idx_globs)]
    for ix in idx:
        if ix["size"] > max_bytes:
            continue
        data = (root / ix["path"]).read_bytes()
        for t in targets:
            if t["path"] == ix["path"]:
                continue
            for kind, pat in _crc_patterns(int(t["crc32"], 16)).items():
                i, cnt = data.find(pat), 0
                while i != -1 and cnt < 4:
                    t["crc_refs"].append({"file": ix["path"], "offset": i, "kind": kind})
                    log(f"CRC {t['path']} direferensikan di {ix['path']} @ {i:#x} ({kind})")
                    i, cnt = data.find(pat, i + 1), cnt + 1


def patch_crc_for(rel: str, orig_root: Path, out_root: Path, refs: list, log):
    op, src = out_root / rel, orig_root / rel
    if not op.exists() or not src.exists():
        return
    odata, data = src.read_bytes(), bytearray(op.read_bytes())
    if bytes(data) == odata:
        return
    for r in detect_crc(odata):
        e = r["endian"]
        if r["kind"] == "embedded_end":
            data[-4:] = struct.pack(e + "I", crc32(bytes(data[:-4])))
        else:
            data[:4] = struct.pack(e + "I", crc32(bytes(data[4:])))
        log(f"CRC tertanam dipatch: {rel} ({r['kind']})")
    op.write_bytes(bytes(data))
    new_crc = crc32(bytes(data))
    for r in refs or []:
        ip = out_root / r["file"]
        if not ip.exists():
            ip.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(orig_root / r["file"], ip)
        ib = bytearray(ip.read_bytes())
        pat = _crc_patterns(new_crc)[r["kind"]]
        ib[r["offset"]:r["offset"] + len(pat)] = pat
        ip.write_bytes(bytes(ib))
        log(f"CRC di indeks dipatch: {r['file']} @ {r['offset']:#x} untuk {rel}")


# ============================================================ scan / extract / import
EXTRACTORS = {"msbt": msbt_extract, "json": json_extract, "text": text_extract}
APPLIERS = {"msbt": msbt_apply, "json": json_apply, "text": text_apply, "binary": binary_apply}


def scan_file(path: Path, rel: str, kws, min_len, max_bytes, scan_bin, skip_ident) -> dict:
    size = path.stat().st_size
    info = {"path": rel, "size": size, "type": "binary", "strings": 0, "hits": {},
            "crc": [], "crc32": "", "crc_refs": [], "candidate": False, "note": ""}
    with open(path, "rb") as f:
        head = f.read(16)
    info["type"] = detect_type(head, path.suffix.lower())
    if info["type"] in COMPRESSED:
        info["note"] = "terkompresi, dekompres dulu"
        return info
    if size > max_bytes:
        info["note"] = "terlalu besar, dilewati"
        return info
    data = path.read_bytes()
    try:
        if info["type"] in EXTRACTORS:
            info["strings"] = len(EXTRACTORS[info["type"]](data)["entries"])
        elif scan_bin:
            info["strings"] = len(find_strings(data, min_len, skip_ident))
    except Exception as ex:
        info["note"] = f"gagal parse: {ex}"
    if kws:
        info["hits"] = search_keywords(data, kws)
    info["candidate"] = bool(info["strings"] or info["hits"])
    if info["candidate"]:
        info["crc32"] = f"{crc32(data):08x}"
        info["crc"] = detect_crc(data)
    return info


def extract_file(path: Path, rel: str, ftype: str, min_len, skip_ident) -> dict:
    data = path.read_bytes()
    doc = EXTRACTORS[ftype](data) if ftype in EXTRACTORS else binary_extract(data, min_len, skip_ident)
    doc["source"] = rel
    return doc


def import_doc(doc: dict, orig_root: Path, out_root: Path):
    rel = doc["source"]
    data = (orig_root / rel).read_bytes()
    new, n, warns = APPLIERS[doc["format"]](data, doc)
    if n:
        dst = out_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(new)
    return n, warns
