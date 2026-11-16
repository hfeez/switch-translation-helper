import struct, tempfile, unittest
from pathlib import Path
from stlh import core


def mk_msbt(strings):
    blobs = [core.msbt_encode(x, "<") for x in strings]
    cnt, cur, offs = len(blobs), 4 + 4 * len(blobs), []
    for b in blobs:
        offs.append(cur); cur += len(b)
    body = struct.pack("<I", cnt) + struct.pack(f"<{cnt}I", *offs) + b"".join(blobs)
    out = bytearray(b"MsgStdBn" + b"\xff\xfe" + b"\0\0" + bytes([1, 3]) + struct.pack("<H", 1) + b"\0\0" + b"\0" * 14)
    out += b"TXT2" + struct.pack("<I", len(body)) + b"\0" * 8 + body
    out += b"\xab" * ((-len(out)) % 16)
    struct.pack_into("<I", out, 0x12, len(out))
    return bytes(out)


class CoreTests(unittest.TestCase):
    def test_msbt_roundtrip(self):
        orig = mk_msbt(["Halo dunia", "Pilih {{E:0:3:0100}}item{{F:0:3}} ini"])
        doc = core.msbt_extract(orig)
        self.assertEqual(doc["entries"][1]["original"], "Pilih {{E:0:3:0100}}item{{F:0:3}} ini")
        doc["entries"][1]["translation"] = "Select {{E:0:3:0100}}the item{{F:0:3}} now, a longer text"
        new, n, _ = core.msbt_apply(orig, doc)
        self.assertEqual(n, 1)
        self.assertEqual(core.msbt_extract(new)["entries"][1]["original"], doc["entries"][1]["translation"])
        self.assertEqual(len(new) % 16, 0)
        self.assertEqual(struct.unpack_from("<I", new, 0x12)[0], len(new))

    def test_binary_strings_and_apply(self):
        data = bytearray(b"\x01\x02\x03\x04" * 4) + b"Press A to continue\0\0\0\0\0"
        data += "こんにちは世界".encode("utf-16-le") + b"\0\0\0\0" + b"some_identifier_name\0\0\0\0" + b"\xff" * 8
        ents = core.find_strings(bytes(data))
        self.assertEqual([e["original"] for e in ents], ["Press A to continue", "こんにちは世界"])
        ents[0]["translation"] = "Tekan A lanjut"
        out, n, warns = core.binary_apply(bytes(data), {"entries": ents})
        self.assertEqual((n, warns, len(out)), (1, [], len(data)))
        ents[0]["translation"] = "x" * 80
        self.assertEqual(core.binary_apply(bytes(data), {"entries": ents})[1], 0)

    def test_keywords(self):
        self.assertIn("Press A", core.search_keywords(b"..Press A..", ["Press A"]))

    def test_embedded_crc_patch_after_import(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d); r = tmp / "romfs"; r.mkdir()
            body = b"Hello world text file\0\0\0\0padding"
            (r / "a.bin").write_bytes(body + struct.pack("<I", core.crc32(body)))
            info = core.scan_file(r / "a.bin", "a.bin", [], 6, 10**8, True, False)
            self.assertTrue(info["candidate"] and info["crc"])
            doc = core.extract_file(r / "a.bin", "a.bin", "binary", 6, False)
            doc["entries"][0]["translation"] = "Halo dunia!"
            core.import_doc(doc, r, tmp / "out")
            core.patch_crc_for("a.bin", r, tmp / "out", [], lambda *_: None)
            p = (tmp / "out" / "a.bin").read_bytes()
            self.assertEqual(struct.unpack("<I", p[-4:])[0], core.crc32(p[:-4]))

    def test_json_and_text(self):
        d = core.json_extract(b'{"a": {"b": "Hello there"}, "n": 1}')
        d["entries"][0]["translation"] = "Halo"
        out, n, _ = core.json_apply(b'{"a": {"b": "Hello there"}, "n": 1}', d)
        self.assertIn("Halo", out.decode())
        t = core.text_extract(b"one\r\n\r\ntwo\r\n")
        t["entries"][1]["translation"] = "dua"
        self.assertEqual(core.text_apply(b"one\r\n\r\ntwo\r\n", t)[0], b"one\r\n\r\ndua\r\n")


if __name__ == "__main__":
    unittest.main()
