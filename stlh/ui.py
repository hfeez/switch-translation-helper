"""Switch Translation Helper — antarmuka PySide6 (Qt)."""
import json
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QFileDialog, QFrame, QGridLayout,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QSpinBox, QStackedWidget, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget)

from . import core

C = {"ok": "#5BE0A3", "info": "#8DB8FF", "warn": "#F7BF5A", "mute": "#B4BCC9", "bad": "#FF8A80"}
NOTE_EN = {"terkompresi, dekompres dulu": "compressed, decompress first",
           "terlalu besar, dilewati": "too large, skipped"}

QSS = """
* { font-family:'Inter','Segoe UI',sans-serif; font-size:13px; color:#E8EAEE; }
QMainWindow, QWidget#root { background:#0F1115; }
QFrame#side { background:#12151B; border-right:1px solid #262C37; }
QFrame#card { background:#161A21; border:1px solid #262C37; border-radius:14px; }
QLabel { background:transparent; }
QLabel#h1 { font-size:22px; font-weight:700; }
QLabel#muted { color:#9AA3B2; }
QLabel#cap { color:#9AA3B2; font-size:11px; font-weight:600; }
QLabel#stat { font-size:24px; font-weight:700; }
QLabel#brand { font-weight:700; font-size:14px; }
QLineEdit, QSpinBox { background:#161A21; border:1px solid #2A303B; border-radius:9px; padding:0 12px;
  min-height:38px; font-family:'JetBrains Mono',Consolas,monospace; font-size:12px; }
QLineEdit:focus, QSpinBox:focus { border-color:#FF5A4D; }
QPushButton { background:#1D222C; border:1px solid #2F3643; border-radius:9px; padding:0 14px;
  min-height:38px; font-weight:600; }
QPushButton:hover { background:#252B37; }
QPushButton:disabled { color:#6B7483; }
QPushButton#pri { background:#FF5A4D; border-color:#FF5A4D; color:#1A0B09; }
QPushButton#pri:hover { background:#FF7468; }
QPushButton#pri:disabled { background:#4A2B29; border-color:#4A2B29; color:#8C6A66; }
QPushButton#nav { background:transparent; border:0; text-align:left; padding:0 12px; color:#A3ACBA; font-weight:500; min-height:44px; }
QPushButton#nav:hover { background:#181C24; }
QPushButton#nav:checked { background:#1D222C; color:#FFFFFF; border:1px solid #2F3643; }
QFrame#seg { background:#0F1115; border:1px solid #2A303B; border-radius:10px; }
QPushButton#segbtn { min-height:30px; padding:0; border:0; border-radius:7px; background:transparent; color:#B4BCC9; font-size:12px; }
QPushButton#segbtn:checked { background:#FF5A4D; color:#1A0B09; }
QTableWidget { background:#161A21; border:1px solid #262C37; border-radius:12px; gridline-color:#20262F; outline:0; }
QTableWidget::item { padding:6px 10px; border-bottom:1px solid #20262F; }
QTableWidget::item:selected { background:#1D222C; color:#FFFFFF; }
QHeaderView::section { background:#161A21; color:#9AA3B2; border:0; border-bottom:1px solid #262C37;
  padding:9px 10px; font-size:11px; font-weight:600; }
QPlainTextEdit { background:#0F1115; border:1px solid #262C37; border-radius:10px;
  font-family:'JetBrains Mono',Consolas,monospace; font-size:12px; padding:6px; }
QProgressBar { background:#232936; border:0; border-radius:3px; max-height:6px; min-height:6px; }
QProgressBar::chunk { background:#FF5A4D; border-radius:3px; }
QCheckBox { spacing:8px; color:#B4BCC9; }
QCheckBox::indicator { width:16px; height:16px; border:1px solid #3A4252; border-radius:4px; background:#161A21; }
QCheckBox::indicator:checked { background:#FF5A4D; border-color:#FF5A4D; }
QScrollBar:vertical { background:transparent; width:10px; }
QScrollBar::handle:vertical { background:#2F3643; border-radius:5px; min-height:30px; }
QScrollBar::add-line, QScrollBar::sub-line { height:0; width:0; }
"""


class Worker(QThread):
    log = Signal(str)
    prog = Signal(int, int)
    done = Signal(object)

    def __init__(self, job):
        super().__init__()
        self.job = job

    def run(self):
        res = None
        try:
            res = self.job(self)
        except Exception as ex:  # tampilkan di log, jangan crash
            self.log.emit(f"ERROR: {ex}")
        self.done.emit(res)


def cell(text, color=None, data=None):
    it = QTableWidgetItem(str(text))
    if color:
        it.setForeground(QColor(color))
    if data is not None:
        it.setData(Qt.UserRole, data)
    return it


def make_table(n_cols, multi=True):
    t = QTableWidget(0, n_cols)
    t.verticalHeader().setVisible(False)
    t.setShowGrid(False)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setSelectionMode(QAbstractItemView.ExtendedSelection if multi else QAbstractItemView.SingleSelection)
    t.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
    for i in range(1, n_cols):
        t.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
    t.horizontalHeader().setHighlightSections(False)
    return t


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Switch Translation Helper")
        self.resize(1280, 820)
        self.lang = core.load_lang()
        self.result = {"romfs": "", "files": []}
        self.docs = []
        self.worker = None
        self._tx, self.actions = [], []
        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(self._sidebar())
        right = QVBoxLayout()
        right.setContentsMargins(26, 22, 26, 16)
        right.setSpacing(12)
        self.stack = QStackedWidget()
        for p in (self._page_scan(), self._page_extract(), self._page_import(), self._page_crc()):
            self.stack.addWidget(p)
        right.addWidget(self.stack, 1)
        right.addWidget(self._dock())
        h.addLayout(right, 1)
        self.nav[0].setChecked(True)

    # ------------------------------------------------ i18n
    def t(self, idt, en):
        return en if self.lang == "en" else idt

    def tx(self, setter, idt, en):
        self._tx.append((setter, idt, en))
        setter(self.t(idt, en))

    def set_lang(self, lang):
        self.lang = lang
        core.save_lang(lang)
        for s, i, e in self._tx:
            s(self.t(i, e))
        self.refresh_all()

    # ------------------------------------------------ pembangun UI
    def _label(self, idt, en, name=None):
        lb = QLabel()
        if name:
            lb.setObjectName(name)
        self.tx(lb.setText, idt, en)
        return lb

    def _button(self, idt, en, slot, primary=False, action=True):
        b = QPushButton()
        if primary:
            b.setObjectName("pri")
        self.tx(b.setText, idt, en)
        b.clicked.connect(slot)
        if action:
            self.actions.append(b)
        return b

    def _check(self, idt, en, checked=True, slot=None):
        c = QCheckBox()
        c.setChecked(checked)
        self.tx(c.setText, idt, en)
        if slot:
            c.toggled.connect(slot)
        return c

    def _field(self, idt, en, edit, browse=None):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        v.addWidget(self._label(idt.upper(), en.upper(), "cap"))
        row = QHBoxLayout()
        row.addWidget(edit, 1)
        if browse:
            row.addWidget(self._button("Pilih…", "Browse…", lambda: self._browse(edit), action=False))
        v.addLayout(row)
        return w

    def _card(self):
        f = QFrame(objectName="card")
        return f

    def _header(self, idt, en, sub_id, sub_en, buttons=()):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        col = QVBoxLayout()
        col.setSpacing(4)
        col.addWidget(self._label(idt, en, "h1"))
        col.addWidget(self._label(sub_id, sub_en, "muted"))
        h.addLayout(col, 1)
        for b in buttons:
            h.addWidget(b)
        return w

    def _tbl_headers(self, table, idt, en):
        self.tx(lambda s, t=table: t.setHorizontalHeaderLabels(s.split("|")), idt, en)

    def _sidebar(self):
        side = QFrame(objectName="side")
        side.setFixedWidth(232)
        v = QVBoxLayout(side)
        v.setContentsMargins(14, 20, 14, 16)
        v.setSpacing(6)
        brand = QLabel("Switch Translation\nHelper", objectName="brand")
        brand.setContentsMargins(6, 0, 0, 14)
        v.addWidget(brand)
        self.nav = []
        grp = QButtonGroup(self)
        names = [("1   Muat & Scan", "1   Load & Scan"), ("2   Extract teks", "2   Extract text"),
                 ("3   Import terjemahan", "3   Import translations"), ("4   Patch CRC", "4   Patch CRC")]
        for i, (a, b) in enumerate(names):
            btn = QPushButton(objectName="nav")
            btn.setCheckable(True)
            self.tx(btn.setText, a, b)
            btn.clicked.connect(lambda _=False, i=i: self.stack.setCurrentIndex(i))
            grp.addButton(btn)
            v.addWidget(btn)
            self.nav.append(btn)
        v.addStretch(1)
        v.addWidget(self._label("BAHASA UI", "UI LANGUAGE", "cap"))
        seg = QFrame(objectName="seg")
        sh = QHBoxLayout(seg)
        sh.setContentsMargins(3, 3, 3, 3)
        sh.setSpacing(0)
        lg = QButtonGroup(self)
        for code, name in (("id", "Indonesia"), ("en", "English")):
            b = QPushButton(name, objectName="segbtn")
            b.setCheckable(True)
            b.setChecked(self.lang == code)
            b.clicked.connect(lambda _=False, c=code: self.set_lang(c))
            lg.addButton(b)
            sh.addWidget(b, 1)
        v.addWidget(seg)
        return side

    def _dock(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        self.pb = QProgressBar()
        self.pb.setTextVisible(False)
        self.pb.setValue(0)
        v.addWidget(self.pb)
        self.logbox = QPlainTextEdit(readOnly=True)
        self.logbox.setFixedHeight(110)
        v.addWidget(self.logbox)
        return w

    # ------------------------------------------------ halaman 1: scan
    def _page_scan(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(14)
        v.addWidget(self._header(
            "Muat & Scan", "Load & Scan",
            "Cari file mana yang berisi teks untuk diterjemahkan.", "Find which files contain text to translate.",
            [self._button("Muat hasil scan", "Load scan result", self.load_scan),
             self._button("Simpan hasil scan", "Save scan result", self.save_scan)]))
        self.e_romfs, self.e_out = QLineEdit(), QLineEdit()
        self.e_kw, self.e_idx = QLineEdit(), QLineEdit()
        self.e_kw.setPlaceholderText("Press A, Start Game")
        self.e_idx.setPlaceholderText("*.crcdb, hash*.bin")
        self.sp_min, self.sp_max = QSpinBox(), QSpinBox()
        self.sp_min.setRange(2, 40)
        self.sp_min.setValue(6)
        self.sp_max.setRange(1, 2048)
        self.sp_max.setValue(64)
        self.ck_bin = self._check("Scan string di file biner", "Scan strings in binary files")
        self.ck_ident = self._check("Abaikan string mirip identifier", "Ignore identifier-like strings")
        self.ck_crc = self._check("Patch CRC otomatis", "Auto-patch CRC")
        self.ck_only = self._check("Hanya kandidat", "Candidates only", True, lambda _: self.fill_scan())

        card = self._card()
        g = QGridLayout(card)
        g.setContentsMargins(16, 16, 16, 16)
        g.setHorizontalSpacing(14)
        g.setVerticalSpacing(12)
        g.addWidget(self._field("Folder romfs", "romfs folder", self.e_romfs, True), 0, 0, 1, 2)
        g.addWidget(self._field("Folder output", "Output folder", self.e_out, True), 0, 2, 1, 2)
        g.addWidget(self._field("Keyword (pisah koma)", "Keywords (comma-separated)", self.e_kw), 1, 0, 1, 2)
        g.addWidget(self._field("File indeks CRC (glob)", "CRC index files (glob)", self.e_idx), 1, 2)
        self.b_scan = self._button("Mulai scan", "Start scan", self.start_scan, primary=True)
        g.addWidget(self.b_scan, 1, 3, Qt.AlignBottom)
        opts = QHBoxLayout()
        opts.setSpacing(18)
        for c in (self.ck_bin, self.ck_ident, self.ck_crc):
            opts.addWidget(c)
        opts.addStretch(1)
        opts.addWidget(self._label("Min string", "Min string"))
        opts.addWidget(self.sp_min)
        opts.addWidget(self._label("Batas MB", "Limit MB"))
        opts.addWidget(self.sp_max)
        g.addLayout(opts, 2, 0, 1, 4)
        v.addWidget(card)

        stats = QHBoxLayout()
        stats.setSpacing(12)
        self.st = []
        for a, b in (("File dipindai", "Files scanned"), ("Kandidat translasi", "Translation candidates"),
                     ("Format MSBT", "MSBT files"), ("CRC terdeteksi", "CRC detected")):
            f = self._card()
            fv = QVBoxLayout(f)
            fv.setContentsMargins(16, 12, 16, 12)
            fv.setSpacing(2)
            val = QLabel("0", objectName="stat")
            fv.addWidget(val)
            fv.addWidget(self._label(a, b, "muted"))
            stats.addWidget(f, 1)
            self.st.append(val)
        v.addLayout(stats)

        mid = QHBoxLayout()
        mid.setSpacing(14)
        left = QVBoxLayout()
        bar = QHBoxLayout()
        bar.addWidget(self.ck_only)
        bar.addStretch(1)
        bar.addWidget(self._button("Extract terpilih →", "Extract selected →", self.go_extract))
        left.addLayout(bar)
        self.tb_scan = make_table(5)
        self._tbl_headers(self.tb_scan, "PATH|TIPE|STRING|KEYWORD|CRC", "PATH|TYPE|STRINGS|KEYWORDS|CRC")
        self.tb_scan.itemSelectionChanged.connect(self.preview)
        left.addWidget(self.tb_scan, 1)
        mid.addLayout(left, 1)
        pv = QVBoxLayout()
        pv.addWidget(self._label("PRATINJAU EXTRACT", "EXTRACT PREVIEW", "cap"))
        self.pvbox = QPlainTextEdit(readOnly=True)
        self.pvbox.setFixedWidth(340)
        pv.addWidget(self.pvbox, 1)
        mid.addLayout(pv)
        v.addLayout(mid, 1)
        return page

    # ------------------------------------------------ halaman 2: extract
    def _page_extract(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(14)
        v.addWidget(self._header(
            "Extract teks", "Extract text",
            "Centang file yang ingin diextract menjadi JSON terjemahan.", "Tick the files to extract into translation JSON.",
            [self._button("Pilih semua", "Select all", lambda: self._check_all(True), action=False),
             self._button("Kosongkan", "Select none", lambda: self._check_all(False), action=False),
             self._button("Extract", "Extract", self.start_extract, primary=True)]))
        self.tb_ext = make_table(4)
        self._tbl_headers(self.tb_ext, "FILE|TIPE|STRING|STATUS", "FILE|TYPE|STRINGS|STATUS")
        v.addWidget(self.tb_ext, 1)
        self.lb_ext = self._label("", "", "muted")
        v.addWidget(self.lb_ext)
        return page

    # ------------------------------------------------ halaman 3: import
    def _page_import(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(14)
        v.addWidget(self._header(
            "Import terjemahan", "Import translations",
            "Tulis terjemahan kembali ke salinan romfs (file asli tidak diubah).",
            "Write translations back into a copy of romfs (originals stay untouched).",
            [self._button("Import", "Import", self.start_import, primary=True)]))
        self.e_trans = QLineEdit()
        card = self._card()
        row = QHBoxLayout(card)
        row.setContentsMargins(16, 16, 16, 16)
        row.addWidget(self._field("Folder JSON terjemahan", "Translation JSON folder", self.e_trans, True), 1)
        row.addWidget(self._button("Muat daftar", "Load list", self.load_docs, action=False), 0, Qt.AlignBottom)
        v.addWidget(card)
        self.tb_imp = make_table(5)
        self._tbl_headers(self.tb_imp, "FILE|FORMAT|ENTRI|TERJEMAH|STATUS", "FILE|FORMAT|ENTRIES|TRANSLATED|STATUS")
        v.addWidget(self.tb_imp, 1)
        return page

    # ------------------------------------------------ halaman 4: CRC
    def _page_crc(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(14)
        v.addWidget(self._header(
            "Patch CRC", "Patch CRC",
            "File yang menyimpan CRC32 (di dalam file atau di file indeks).",
            "Files that store a CRC32 (inside the file or in an index file).",
            [self._button("Patch CRC di romfs_patched", "Patch CRC in romfs_patched", self.start_patch, primary=True)]))
        self.tb_crc = make_table(4)
        self._tbl_headers(self.tb_crc, "FILE|CRC32 ASLI|TERTANAM|REFERENSI INDEKS",
                          "FILE|ORIGINAL CRC32|EMBEDDED|INDEX REFERENCES")
        v.addWidget(self.tb_crc, 1)
        self.lb_crc = self._label(
            "CRC32 standar (zlib). Referensi indeks diisi lewat kolom 'File indeks CRC' di halaman Scan.",
            "Standard CRC32 (zlib). Index references come from the 'CRC index files' field on the Scan page.", "muted")
        v.addWidget(self.lb_crc)
        return page

    # ------------------------------------------------ util
    def out(self):
        return Path(self.e_out.text() or ".")

    def _browse(self, edit):
        d = QFileDialog.getExistingDirectory(self, "", edit.text())
        if not d:
            return
        edit.setText(d)
        if edit is self.e_romfs and not self.e_out.text():
            self.e_out.setText(str(Path(d).parent / "translation_work"))
        if edit is self.e_out and not self.e_trans.text():
            self.e_trans.setText(str(Path(d) / "extracted"))

    def add_log(self, msg):
        self.logbox.appendPlainText(msg)

    def set_prog(self, i, n):
        self.pb.setMaximum(max(n, 1))
        self.pb.setValue(i)

    def run(self, job, cb=None):
        if self.worker and self.worker.isRunning():
            return
        w = Worker(job)
        w.log.connect(self.add_log)
        w.prog.connect(self.set_prog)
        w.done.connect(lambda res: cb(res) if cb else None)
        w.finished.connect(lambda: [b.setEnabled(True) for b in self.actions])
        for b in self.actions:
            b.setEnabled(False)
        self.worker = w
        w.start()

    def warn(self, idt, en):
        QMessageBox.warning(self, "Switch Translation Helper", self.t(idt, en))

    # ------------------------------------------------ scan
    def start_scan(self):
        root = Path(self.e_romfs.text())
        if not root.is_dir():
            return self.warn("Folder romfs tidak valid.", "Invalid romfs folder.")
        kws = [k.strip() for k in self.e_kw.text().split(",") if k.strip()]
        idx = [g.strip() for g in self.e_idx.text().replace(";", ",").split(",") if g.strip()]
        mn, mx = self.sp_min.value(), self.sp_max.value() * core.MB
        sb, si = self.ck_bin.isChecked(), self.ck_ident.isChecked()
        t = self.t

        def job(w):
            files = sorted(p for p in root.rglob("*") if p.is_file())
            w.log.emit(t("Memindai {n} file...", "Scanning {n} files...").format(n=len(files)))
            res = []
            for i, p in enumerate(files, 1):
                rel = p.relative_to(root).as_posix()
                try:
                    res.append(core.scan_file(p, rel, kws, mn, mx, sb, si))
                except Exception as ex:
                    w.log.emit(f"! {rel}: {ex}")
                if i % 20 == 0 or i == len(files):
                    w.prog.emit(i, len(files))
            if idx:
                w.log.emit(t("Mencari referensi CRC di file indeks...", "Looking for CRC references in index files..."))
                core.find_crc_refs(root, res, idx, mx, w.log.emit)
            return {"romfs": str(root), "files": res}

        def done(res):
            if res:
                self.result = res
                self.refresh_all()
                n = sum(1 for f in res["files"] if f["candidate"])
                self.add_log(t("Selesai. {c} kandidat dari {n} file.", "Done. {c} candidates out of {n} files.")
                             .format(c=n, n=len(res["files"])))
        self.run(job, done)

    def save_scan(self):
        d = QFileDialog.getExistingDirectory(self, self.t("Simpan hasil scan ke folder", "Save scan result to folder"))
        if d:
            p = Path(d) / "scan_result.json"
            p.write_text(json.dumps(self.result, ensure_ascii=False, indent=2), encoding="utf-8")
            self.add_log(self.t("Hasil scan disimpan: {p}", "Scan result saved: {p}").format(p=p))

    def load_scan(self):
        f, _ = QFileDialog.getOpenFileName(self, "scan_result.json", "", "JSON (*.json)")
        if f:
            self.result = json.loads(Path(f).read_text(encoding="utf-8"))
            if self.result.get("romfs") and not self.e_romfs.text():
                self.e_romfs.setText(self.result["romfs"])
            self.refresh_all()
            self.add_log(self.t("Dimuat: {f}", "Loaded: {f}").format(f=f))

    def refresh_all(self):
        self.fill_scan()
        self.fill_extract()
        self.fill_crc()
        fs = self.result["files"]
        vals = [len(fs), sum(1 for f in fs if f["candidate"]), sum(1 for f in fs if f["type"] == "msbt"),
                sum(1 for f in fs if f["crc"] or f["crc_refs"])]
        for lb, x in zip(self.st, vals):
            lb.setText(f"{x:,}")
        if self.docs:
            self.fill_docs()

    def fill_scan(self):
        t = self.tb_scan
        t.setRowCount(0)
        for f in self.result["files"]:
            if self.ck_only.isChecked() and not f["candidate"]:
                continue
            ty = f["type"]
            tc = C["info"] if ty in ("msbt", "json", "text") else C["warn"] if ty in core.COMPRESSED else C["mute"]
            hits = ", ".join(f"{k} ×{len(v)}" for k, v in f["hits"].items())
            crc = []
            if f["crc"]:
                crc.append(self.t("tertanam", "embedded"))
            if f["crc_refs"]:
                crc.append(self.t("indeks", "index") + f" ×{len(f['crc_refs'])}")
            note = f["note"]
            if note and self.lang == "en":
                note = NOTE_EN.get(note, note)
            last = (" · ".join(crc), C["ok"]) if crc else (note or "—", C["warn"] if note else None)
            r = t.rowCount()
            t.insertRow(r)
            for c, it in enumerate([cell(f["path"], None, f["path"]), cell(ty.upper(), tc),
                                    cell(f["strings"] or "—"), cell(hits or "—", C["warn"] if hits else None),
                                    cell(*last)]):
                t.setItem(r, c, it)

    def selected_rels(self):
        return [self.tb_scan.item(i.row(), 0).data(Qt.UserRole)
                for i in self.tb_scan.selectionModel().selectedRows()]

    def preview(self):
        rels = self.selected_rels()
        if not rels:
            return
        f = next((x for x in self.result["files"] if x["path"] == rels[0]), None)
        if not f:
            return
        if f["type"] in core.COMPRESSED or f["size"] > 4 * core.MB:
            self.pvbox.setPlainText(self.t("(pratinjau tidak tersedia)", "(preview not available)"))
            return
        try:
            doc = core.extract_file(Path(self.e_romfs.text()) / f["path"], f["path"], f["type"],
                                    self.sp_min.value(), self.ck_ident.isChecked())
            lines = [f"#{e['id']}  {e['original']}" for e in doc["entries"][:25]]
            more = len(doc["entries"]) - 25
            if more > 0:
                lines.append(f"… +{more}")
            self.pvbox.setPlainText("\n\n".join(lines))
        except Exception as ex:
            self.pvbox.setPlainText(str(ex))

    # ------------------------------------------------ extract
    def fill_extract(self):
        t = self.tb_ext
        t.setRowCount(0)
        for f in self.result["files"]:
            if not f["candidate"]:
                continue
            r = t.rowCount()
            t.insertRow(r)
            it = cell(f["path"], None, f["path"])
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked)
            t.setItem(r, 0, it)
            t.setItem(r, 1, cell(f["type"].upper(), C["info"] if f["type"] in ("msbt", "json", "text") else C["mute"]))
            t.setItem(r, 2, cell(f["strings"] or "—"))
            t.setItem(r, 3, cell("—"))
        self.lb_ext.setText(self.t("Output: ", "Output: ") + str(self.out() / "extracted"))

    def _check_all(self, on):
        for r in range(self.tb_ext.rowCount()):
            self.tb_ext.item(r, 0).setCheckState(Qt.Checked if on else Qt.Unchecked)

    def go_extract(self):
        sel = set(self.selected_rels())
        for r in range(self.tb_ext.rowCount()):
            it = self.tb_ext.item(r, 0)
            it.setCheckState(Qt.Checked if it.data(Qt.UserRole) in sel else Qt.Unchecked)
        self.nav[1].click()

    def start_extract(self):
        root = Path(self.e_romfs.text())
        rows = [r for r in range(self.tb_ext.rowCount()) if self.tb_ext.item(r, 0).checkState() == Qt.Checked]
        if not root.is_dir() or not rows:
            return self.warn("Pilih folder romfs dan centang minimal satu file.",
                             "Choose a romfs folder and tick at least one file.")
        rels = [self.tb_ext.item(r, 0).data(Qt.UserRole) for r in rows]
        types = {f["path"]: f["type"] for f in self.result["files"]}
        dst_root, mn, si, t = self.out() / "extracted", self.sp_min.value(), self.ck_ident.isChecked(), self.t

        def job(w):
            out = {}
            for i, rel in enumerate(rels, 1):
                try:
                    doc = core.extract_file(root / rel, rel, types.get(rel, "binary"), mn, si)
                    dst = dst_root / (rel + ".json")
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    dst.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
                    out[rel] = len(doc["entries"])
                    w.log.emit(t("Extract {rel}: {n} entri", "Extract {rel}: {n} entries").format(rel=rel, n=out[rel]))
                except Exception as ex:
                    out[rel] = -1
                    w.log.emit(f"! {rel}: {ex}")
                w.prog.emit(i, len(rels))
            return out

        def done(res):
            for r in range(self.tb_ext.rowCount()):
                rel = self.tb_ext.item(r, 0).data(Qt.UserRole)
                if res and rel in res:
                    ok = res[rel] >= 0
                    self.tb_ext.setItem(r, 3, cell(f"✓ {res[rel]}" if ok else "✗", C["ok"] if ok else C["bad"]))
            if not self.e_trans.text():
                self.e_trans.setText(str(dst_root))
        self.run(job, done)

    # ------------------------------------------------ import
    def load_docs(self):
        d = Path(self.e_trans.text())
        if not d.is_dir():
            return self.warn("Folder JSON tidak valid.", "Invalid JSON folder.")
        self.docs = []
        for p in sorted(d.rglob("*.json")):
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
                ents = doc["entries"]
                self.docs.append((p, doc["source"], doc["format"], len(ents),
                                  sum(1 for e in ents if e.get("translation"))))
            except Exception:
                continue
        self.fill_docs()

    def fill_docs(self, status=None):
        t = self.tb_imp
        t.setRowCount(0)
        for p, src, fmt, n, tr in self.docs:
            r = t.rowCount()
            t.insertRow(r)
            st = (status or {}).get(str(p))
            stx, col = ("—", None)
            if st:
                stx, col = (("✓ " + self.t("diterapkan", "applied") + f" {st[0]}", C["ok"]) if st[0] >= 0
                            else ("✗", C["bad"]))
                if st[1]:
                    stx += f" · ⚠ {st[1]}"
                    col = C["warn"]
            for c, it in enumerate([cell(src, None, str(p)), cell(fmt.upper(), C["info"]), cell(n),
                                    cell(f"{tr} / {n}", C["ok"] if tr else C["mute"]), cell(stx, col)]):
                t.setItem(r, c, it)

    def start_import(self):
        root = Path(self.e_romfs.text())
        if not self.docs or not root.is_dir():
            return self.warn("Muat daftar terjemahan dan isi folder romfs dulu.",
                             "Load the translation list and set the romfs folder first.")
        patched = self.out() / "romfs_patched"
        refs = {f["path"]: f["crc_refs"] for f in self.result["files"]}
        do_crc, docs, t = self.ck_crc.isChecked(), list(self.docs), self.t

        def job(w):
            res = {}
            for i, (p, *_rest) in enumerate(docs, 1):
                try:
                    doc = json.loads(p.read_text(encoding="utf-8"))
                    n, warns = core.import_doc(doc, root, patched)
                    for x in warns:
                        w.log.emit("  ⚠ " + x)
                    if n and do_crc:
                        core.patch_crc_for(doc["source"], root, patched, refs.get(doc["source"]), w.log.emit)
                    res[str(p)] = (n, len(warns))
                    w.log.emit(t("Import {rel}: {n} entri diterapkan", "Import {rel}: {n} entries applied")
                               .format(rel=doc["source"], n=n))
                except Exception as ex:
                    res[str(p)] = (-1, 0)
                    w.log.emit(f"! {p.name}: {ex}")
                w.prog.emit(i, len(docs))
            w.log.emit(t("Selesai. Hasil di: {d}", "Done. Output in: {d}").format(d=patched))
            return res
        self.run(job, lambda res: self.fill_docs(res))

    # ------------------------------------------------ CRC
    def fill_crc(self):
        t = self.tb_crc
        t.setRowCount(0)
        for f in self.result["files"]:
            if not (f["crc"] or f["crc_refs"]):
                continue
            r = t.rowCount()
            t.insertRow(r)
            emb = ", ".join(f"{c['kind'].replace('embedded_', '')}/{'LE' if c['endian'] == '<' else 'BE'}" for c in f["crc"])
            refs = "; ".join(f"{x['file']} @ {x['offset']:#x}" for x in f["crc_refs"])
            for c, it in enumerate([cell(f["path"]), cell(f["crc32"], None), cell(emb or "—", C["ok"] if emb else None),
                                    cell(refs or "—", C["info"] if refs else None)]):
                t.setItem(r, c, it)

    def start_patch(self):
        root, patched = Path(self.e_romfs.text()), self.out() / "romfs_patched"
        if not patched.is_dir():
            return self.warn("Belum ada folder romfs_patched. Jalankan Import dulu.",
                             "No romfs_patched folder yet. Run Import first.")
        refs = {f["path"]: f["crc_refs"] for f in self.result["files"]}

        def job(w):
            files = [p for p in sorted(patched.rglob("*")) if p.is_file()]
            for i, p in enumerate(files, 1):
                rel = p.relative_to(patched).as_posix()
                core.patch_crc_for(rel, root, patched, refs.get(rel), w.log.emit)
                w.prog.emit(i, len(files))
            w.log.emit(self.t("Patch CRC selesai.", "CRC patch finished."))
        self.run(job)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
