"""Araştırma modu — kaynak okuyucuları (sekmede açılır).

  PDF        → pypdfium2 ile sayfa sayfa çizim (sürekli kaydırma, Ctrl+tekerlek yakınlaştırma)
  .docx      → kendi dönüştürücümüz (zipfile → HTML), QTextBrowser
  .doc/.rtf/.odt → Word kuruluysa COM ile .docx'e çevrilip açılır, yoksa varsayılan programla
  txt / md   → QTextBrowser (md: Markdown)
  görsel     → sığdırılmış görüntü
Video / bağlantı sekmede açılmaz: video kamug'da, bağlantı tarayıcıda (research_view)."""
import html
import os
import re
import zipfile

from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QImage, QColor, QPixmap, QImageReader
from PyQt6.QtWidgets import QWidget, QScrollArea, QTextBrowser, QLabel

from .i18n import t
from .shelf import rp, qc, ff, font

PDF_GAP = 14


# --------------------------------------------------------------------------- docx → HTML
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_to_html(path):
    """Başlıklar, kalın / italik / altı çizili, listeler, tablolar, dipnot işaretleri. Görseller atlanır."""
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        styles = {}
        if "word/styles.xml" in z.namelist():
            sr = ET.fromstring(z.read("word/styles.xml"))
            for st in sr.iter(W + "style"):
                sid = st.get(W + "styleId")
                nm = st.find(W + "name")
                if sid and nm is not None:
                    styles[sid] = (nm.get(W + "val") or "").lower()
    body = root.find(W + "body")
    out = []

    def run_html(r):
        txt = ""
        for ch in r:
            if ch.tag == W + "t":
                txt += html.escape(ch.text or "")
            elif ch.tag == W + "tab":
                txt += "&emsp;"
            elif ch.tag in (W + "br", W + "cr"):
                txt += "<br>"
        if not txt:
            return ""
        rp_ = r.find(W + "rPr")
        if rp_ is not None:
            if rp_.find(W + "b") is not None and rp_.find(W + "b").get(W + "val") not in ("0", "false"):
                txt = f"<b>{txt}</b>"
            if rp_.find(W + "i") is not None and rp_.find(W + "i").get(W + "val") not in ("0", "false"):
                txt = f"<i>{txt}</i>"
            if rp_.find(W + "u") is not None and rp_.find(W + "u").get(W + "val") not in ("none", None):
                txt = f"<u>{txt}</u>"
            va = rp_.find(W + "vertAlign")
            if va is not None and va.get(W + "val") == "superscript":
                txt = f"<sup>{txt}</sup>"
        return txt

    def para(p):
        inner = ""
        for ch in p:
            if ch.tag == W + "r":
                inner += run_html(ch)
            elif ch.tag == W + "hyperlink":
                inner += "".join(run_html(r) for r in ch.iter(W + "r"))
        ppr = p.find(W + "pPr")
        tag = "p"
        li = False
        if ppr is not None:
            ps = ppr.find(W + "pStyle")
            if ps is not None:
                name = styles.get(ps.get(W + "val"), ps.get(W + "val", "").lower())
                m = re.match(r"(?:heading|başlık)\s*(\d)", name)
                if m:
                    tag = f"h{min(4, int(m.group(1)) + 1)}"
                elif name in ("title", "konu başlığı"):
                    tag = "h1"
                elif "quote" in name or "alıntı" in name:
                    tag = "blockquote"
            if ppr.find(W + "numPr") is not None:
                li = True
        if not inner.strip():
            return ""
        if li:
            return f"<li>{inner}</li>"
        return f"<{tag}>{inner}</{tag}>"

    in_list = False
    for el in body:
        if el.tag == W + "p":
            h = para(el)
            if h.startswith("<li>") and not in_list:
                out.append("<ul>")
                in_list = True
            elif not h.startswith("<li>") and in_list and h:
                out.append("</ul>")
                in_list = False
            if h:
                out.append(h)
        elif el.tag == W + "tbl":
            if in_list:
                out.append("</ul>")
                in_list = False
            rows = []
            for tr in el.iter(W + "tr"):
                cells = []
                for tc in tr.iter(W + "tc"):
                    cells.append("<td>" + "<br>".join(filter(None, (para(p) for p in tc.iter(W + "p")))) + "</td>")
                rows.append("<tr>" + "".join(cells) + "</tr>")
            out.append('<table cellspacing="0" cellpadding="6" border="1">' + "".join(rows) + "</table>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def convert_with_word(path):
    """Word kuruluysa .doc / .rtf / .odt → geçici .docx. Olmazsa None."""
    import tempfile
    import subprocess
    dst = os.path.join(tempfile.gettempdir(), "yazit_doc_" + re.sub(r"\W+", "_", os.path.basename(path)) + ".docx")
    if os.path.isfile(dst) and os.path.getmtime(dst) >= os.path.getmtime(path):
        return dst
    ps = ("$ErrorActionPreference='Stop';$w=New-Object -ComObject Word.Application;$w.Visible=$false;"
          f"$d=$w.Documents.Open('{path.replace(chr(39), chr(39) * 2)}',$false,$true);"
          f"$d.SaveAs2('{dst.replace(chr(39), chr(39) * 2)}',16);$d.Close($false);$w.Quit()")
    try:
        subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], capture_output=True,
                       timeout=60, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), stdin=subprocess.DEVNULL)
    except Exception:
        return None
    return dst if os.path.isfile(dst) else None


# --------------------------------------------------------------------------- ortak
def reader_qss():
    P = rp()
    return f"""
QTextBrowser#Reader {{ background: {P['bg']}; color: {P['text']}; border: none; font-family: {ff('f_body', P)};
    font-size: 16px; selection-background-color: {QColor(P['ink']).name()}; selection-color: {P['on_ink']}; }}
QScrollArea#PdfArea {{ background: {P['bg']}; border: none; }}
QWidget#PdfPages {{ background: {P['bg']}; }}
QLabel#ImgView {{ background: {P['bg']}; }}
"""


def prose_css():
    P = rp()
    disp, mono = ff("f_display", P), ff("f_mono", P)
    return f"""
body {{ color: {P['text']}; }}
p {{ margin: 0 0 14px 0; line-height: 165%; }}
h1 {{ font-family: {disp}; font-size: 34px; font-weight: 600; margin: 8px 0 18px 0; color: {P['text']}; }}
h2 {{ font-family: {disp}; font-size: 25px; font-weight: 500; margin: 26px 0 12px 0; color: {P['text']}; }}
h3 {{ font-family: {disp}; font-size: 20px; font-weight: 500; margin: 20px 0 10px 0; }}
h4 {{ font-size: 16px; font-weight: 700; margin: 16px 0 8px 0; }}
blockquote {{ margin: 10px 24px; color: {P['muted']}; font-style: italic; }}
a {{ color: {P['ink']}; }}
code, pre {{ font-family: {mono}; font-size: 13px; color: {P['ink']}; }}
td {{ border-color: {P['faint']}; }}
"""


class ProseView(QTextBrowser):
    """docx / txt / md okuyucu: ortada okunaklı bir sütun."""
    MAXW = 760

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Reader")
        self.setOpenExternalLinks(True)
        self._content = None           # (tür, metin): tema değişince yeniden çizmek için
        self.document().setDocumentMargin(36)
        self._style()

    def _style(self):
        self.setFont(font("f_body", 16))
        self.document().setDefaultStyleSheet(prose_css())
        self.setStyleSheet(reader_qss())

    def set_content(self, kind, text):
        """kind: html | md | plain"""
        self._content = (kind, text)
        if kind == "md":
            self.setMarkdown(text)
            self.document().setDefaultStyleSheet(prose_css())
            self.setHtml(self.toHtml())
        elif kind == "plain":
            self.setPlainText(text)
        else:
            self.setHtml(text)

    def restyle(self):
        """Araştırma teması değişti: biçim ve yazı tipleri yeniden (kaydırma yeri korunur)."""
        sb = self.verticalScrollBar()
        frac = sb.value() / max(1, sb.maximum())
        self._style()
        if self._content is not None:
            self.set_content(*self._content)
        QTimer.singleShot(0, lambda: sb.setValue(int(frac * sb.maximum())))

    copied = pyqtSignal(str, int)
    quote_req = pyqtSignal(str, int)
    undo_req = pyqtSignal()

    def selected(self):
        return self.textCursor().selectedText().replace("\u2029", "\n").replace("\u2028", "\n").strip()

    def keyPressEvent(self, e):
        from PyQt6.QtGui import QKeySequence
        if e.matches(QKeySequence.StandardKey.Copy):
            super().keyPressEvent(e)
            if self.selected():
                self.copied.emit(clean_quote(self.selected()), 0)
            return
        if e.matches(QKeySequence.StandardKey.Undo):
            self.undo_req.emit()
            return
        super().keyPressEvent(e)

    def contextMenuEvent(self, e):
        m = self.createStandardContextMenu(e.pos())
        txt = self.selected()
        if txt:
            first = m.actions()[0] if m.actions() else None
            a = m.addAction(t("rs_quote_add"))
            a.triggered.connect(lambda: self.quote_req.emit(clean_quote(txt), 0))
            if first is not None:
                m.removeAction(a)
                m.insertAction(first, a)
                m.insertSeparator(first)
        m.exec(e.globalPos())

    def resizeEvent(self, e):
        side = max(0, (self.width() - self.MAXW) // 2)
        self.setViewportMargins(side, 0, side, 0)
        super().resizeEvent(e)


def parse_transcript(path):
    """kamug / altyazı dökümü → [(saniye, metin)]. .srt, .vtt, .json (liste ya da {"segments": [...]}),
    .txt ("[12:34] metin" ya da "12:34 metin" satırları)."""
    import json
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()
    out = []

    def secs(h, m, s):
        return int(h or 0) * 3600 + int(m) * 60 + float(str(s).replace(",", "."))
    if path.lower().endswith(".json"):
        try:
            d = json.loads(raw)
        except ValueError:
            return out
        segs = d.get("segments") if isinstance(d, dict) else d
        for sg in segs or []:
            if isinstance(sg, dict) and str(sg.get("text", "")).strip():
                out.append((float(sg.get("start", sg.get("t", 0)) or 0), str(sg["text"]).strip()))
        return out
    if path.lower().endswith((".srt", ".vtt")):
        for blk in re.split(r"\n\s*\n", raw.replace("\r\n", "\n")):
            m = re.search(r"(?:(\d+):)?(\d+):(\d+(?:[.,]\d+)?)\s*-->", blk)
            if not m:
                continue
            lines = blk.split("\n")
            k = next(i for i, ln in enumerate(lines) if "-->" in ln)
            txt = " ".join(re.sub(r"<[^>]+>", "", ln).strip() for ln in lines[k + 1:] if ln.strip())
            if txt:
                out.append((secs(m.group(1), m.group(2), m.group(3)), txt))
        return out
    for ln in raw.splitlines():
        m = re.match(r"\s*\[?(?:(\d+):)?(\d{1,2}):(\d{2}(?:\.\d+)?)\]?\s+(.+)", ln)
        if m:
            out.append((secs(m.group(1), m.group(2), m.group(3)), m.group(4).strip()))
    return out


def fmt_time(sec):
    s = int(sec)
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


class TranscriptView(ProseView):
    """Videonun dökümü: her satırın başında zaman (tıkla → kamug o saniyede açar). Kopyalanan satırın zamanı
    alıntının künyesine girer (copied_t)."""
    copied_t = pyqtSignal(str, float)
    seek = pyqtSignal(float)

    def __init__(self, video, cues, parent=None):
        super().__init__(parent)
        self.video = video
        self.cues = cues
        self.setOpenLinks(False)
        self.anchorClicked.connect(self._clicked)
        self._build()

    def _build(self):
        P = rp()
        mono = P["f_mono"][0]
        rows = []
        for i, (sec, txt) in enumerate(self.cues):
            rows.append(f'<p><a name="c{i}"></a><a href="yazit-t:{sec:.2f}" style="color:{P["ink"]}; '
                        f'text-decoration:none; font-family:{mono}; font-size:12px; font-weight:600;">'
                        f'{fmt_time(sec)}</a>&nbsp;&nbsp;&nbsp;{html.escape(txt)}</p>')
        self.set_content("html", "".join(rows))

    def restyle(self):
        sb = self.verticalScrollBar()
        v = sb.value()
        self._style()
        self._build()
        QTimer.singleShot(0, lambda: sb.setValue(v))

    def _clicked(self, url):
        s = url.toString()
        if s.startswith("yazit-t:"):
            self.seek.emit(float(s[8:]))

    def sel_time(self):
        """Seçimin başladığı satırın zamanı."""
        c = self.textCursor()
        b = self.document().findBlock(c.selectionStart())
        i = b.blockNumber()
        return self.cues[i][0] if 0 <= i < len(self.cues) else 0.0

    def selected(self):
        txt = super().selected()
        return re.sub(r"(?m)^\s*(?:\d+:)?\d{1,2}:\d{2}\s+", "", txt)

    def keyPressEvent(self, e):
        from PyQt6.QtGui import QKeySequence
        if e.matches(QKeySequence.StandardKey.Copy):
            QTextBrowser.keyPressEvent(self, e)
            if self.selected():
                self.copied_t.emit(clean_quote(self.selected()), self.sel_time())
            return
        super().keyPressEvent(e)

    def contextMenuEvent(self, e):
        m = self.createStandardContextMenu(e.pos())
        txt = self.selected()
        if txt:
            a = m.addAction(t("rs_quote_add"))
            sec = self.sel_time()
            a.triggered.connect(lambda: self.copied_t.emit(clean_quote(txt), sec))
        m.exec(e.globalPos())


def transcript_for(src):
    tr = src.get("transcript")
    if not tr:
        return None
    p = os.path.join(os.path.dirname(src.path), tr)
    if not os.path.isfile(p):
        return None
    try:
        cues = parse_transcript(p)
    except Exception:
        return None
    return cues or None


def open_reader(src):
    """Kaynak için okuyucu bileşeni ya da hata metni."""
    kind = src.kind
    p = src.path
    try:
        if kind == "pdf":
            return PdfView(p)
        if kind == "doc":
            if not p.lower().endswith(".docx"):
                p2 = convert_with_word(p)
                if not p2:
                    return None
                p = p2
            v = ProseView()
            v.set_content("html", docx_to_html(p))
            return v
        if kind == "text":
            v = ProseView()
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                txt = f.read()
            v.set_content("md" if p.lower().endswith((".md", ".markdown")) else "plain", txt)
            return v
        if kind == "image":
            return ImageView(p)
        if kind == "video":
            cues = transcript_for(src)
            return TranscriptView(p, cues) if cues else None
    except Exception:
        import traceback
        traceback.print_exc()
        return None
    return None


# --------------------------------------------------------------------------- görsel
class ImageView(QScrollArea):
    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.setObjectName("PdfArea")
        self.setStyleSheet(reader_qss())
        self.setWidgetResizable(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rd = QImageReader(path)
        rd.setAutoTransform(True)
        self.img = rd.read()
        self.lbl = QLabel()
        self.lbl.setObjectName("ImgView")
        self.lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWidget(self.lbl)
        QTimer.singleShot(0, self._fit)

    def restyle(self):
        self.setStyleSheet(reader_qss())

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit()

    def _fit(self):
        if self.img.isNull():
            return
        dpr = self.devicePixelRatioF()
        vw, vh = self.viewport().width() - 40, self.viewport().height() - 40
        k = min(1.0, vw / max(1, self.img.width()), vh / max(1, self.img.height())) if vw > 0 and vh > 0 else 1.0
        pm = QPixmap.fromImage(self.img.scaled(round(self.img.width() * k * dpr), round(self.img.height() * k * dpr),
                                               Qt.AspectRatioMode.KeepAspectRatio,
                                               Qt.TransformationMode.SmoothTransformation))
        pm.setDevicePixelRatio(dpr)
        self.lbl.setPixmap(pm)


# --------------------------------------------------------------------------- PDF
HL_COLORS = {"yellow": "#FFE066", "green": "#A6E39A", "red": "#FF9F8F"}
WORD_CH = "'’-"


def clean_quote(text):
    """PDF'den gelen metin: satır sonu tirelerini birleştir, satırları tek boşluğa indir."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").replace("­", "")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    text = re.sub(r"[ \t]*\n[ \t]*", " ", text)
    return re.sub(r"\s{2,}", " ", text).strip()


class PdfPages(QWidget):
    """Sayfaların hepsi tek bileşende; yalnızca görünenler çizilir. Fare olayları PdfView'a gider."""

    def __init__(self, view):
        super().__init__()
        self.setObjectName("PdfPages")
        self.view = view
        self.setMouseTracking(True)

    def paintEvent(self, e):
        v = self.view
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        clip = QRectF(e.rect())
        P = rp()
        for i, r in enumerate(v.rects):
            if not r.intersects(clip):
                continue
            p.fillRect(r.translated(2, 3), qc("#000000", 90))
            img = v.page_image(i)
            if img is not None:
                p.drawImage(r, img)
            else:
                p.fillRect(r, qc(P["paper"]))
            v.paint_overlay(p, i, r)

    def mousePressEvent(self, e):
        self.view.press(e)

    def mouseMoveEvent(self, e):
        self.view.move(e)

    def mouseReleaseEvent(self, e):
        self.view.release(e)

    def mouseDoubleClickEvent(self, e):
        self.view.double(e)

    def contextMenuEvent(self, e):
        self.view.context(e)


class FindBar(QWidget):
    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.setObjectName("FindBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        from PyQt6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 6, 6)
        lay.setSpacing(4)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText(t("rs_find"))
        self.edit.setFixedWidth(200)
        self.count = QLabel("")
        self.count.setObjectName("FindCount")
        lay.addWidget(self.edit)
        lay.addWidget(self.count)
        for txt, d in (("↑", -1), ("↓", 1), ("×", 0)):
            b = QPushButton(txt)
            b.setObjectName("FindBtn")
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect((lambda _=False, d=d: view.find_step(d)) if d else (lambda _=False: view.close_find()))
            lay.addWidget(b)
        self._t = QTimer(self, singleShot=True, interval=220, timeout=lambda: view.find(self.edit.text()))
        self.edit.textChanged.connect(lambda _s: self._t.start())
        self.edit.returnPressed.connect(self._enter)
        self.restyle()

    def restyle(self):
        P = rp()
        self.setStyleSheet(f"""
QWidget#FindBar {{ background: {P['panel']}; border: 1px solid {P['faint']}; border-radius: 10px; }}
QLineEdit {{ background: {P['bg']}; color: {P['text']}; border: 1px solid {P['faint']}; border-radius: 6px;
    padding: 4px 8px; font-size: 13px; }}
QLabel#FindCount {{ color: {P['muted']}; font-family: {ff('f_mono', P)}; font-size: 11px; min-width: 52px; }}
QPushButton#FindBtn {{ background: transparent; border: none; color: {P['text']}; min-width: 24px; max-width: 24px;
    min-height: 24px; padding: 0; font-size: 14px; border-radius: 5px; }}
QPushButton#FindBtn:hover {{ background: {P['faint']}; }}
""")
        self.adjustSize()

    def _enter(self):
        from PyQt6.QtWidgets import QApplication
        if self._t.isActive():
            self._t.stop()
            self.view.find(self.edit.text())
        else:
            back = QApplication.keyboardModifiers() & Qt.KeyboardModifier.ShiftModifier
            self.view.find_step(-1 if back else 1)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.view.close_find()
            return
        super().keyPressEvent(e)


class PdfView(QScrollArea):
    """PDF okuyucu: sürekli kaydırma, Ctrl+tekerlek yakınlaştırma, metin seçme (sürükle / çift tık sözcük /
    Ctrl+A sayfa), Ctrl+C (copied sinyali → alıntı), Ctrl+F arama, sağ tık vurgula.

    highlights: [{"p": sayfa (0'dan), "a": ilk karakter, "n": karakter sayısı, "c": renk adı, "t": metin}]
    (araştırma dosyasında kaynağa göre saklanır; değişince highlights_changed)."""
    page_changed = pyqtSignal(int, int)
    copied = pyqtSignal(str, int)            # metin, sayfa (1'den)
    quote_req = pyqtSignal(str, int)         # sağ tık › alıntı olarak ekle
    image_req = pyqtSignal(QImage, int)      # seçilen alan (görsel / grafik) → araştırma sayfası; sayfa (1'den)
    undo_req = pyqtSignal()
    highlights_changed = pyqtSignal()

    def __init__(self, path, parent=None):
        super().__init__(parent)
        import pypdfium2 as pdfium
        self.setObjectName("PdfArea")
        self.setStyleSheet(reader_qss())
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.path = path
        self.doc = pdfium.PdfDocument(path)
        self.n = len(self.doc)
        self.sizes = [self.doc.get_page_size(i) for i in range(self.n)]
        self.zoom = 0.0            # 0 = genişliğe sığdır (en çok 1,6)
        self.rects = []
        self._cache = {}
        self._tp = {}              # sayfa → PdfTextPage
        self.sel = None            # (p1, i1, p2, i2) — i2 dahil
        self._anchor = None
        self._dragging = False
        self._moved = False
        self._drag_vp = None       # seçerken farenin görünür alandaki yeri
        # alan seçimi (görsel / grafik): Alt+sürükle, resmin üstünden sürükle ya da sağ tık › Alan seç
        self.region = None         # (sayfa, QRectF bileşen koordinatı)
        self._rstart = None        # sürükleme başı (sayfa, QPointF)
        self._area_mode = False    # bir sonraki sürükleme alan seçer
        self._figs = {}            # sayfa → [(sol, alt, sağ, üst)] PDF noktası: sayfadaki gömülü resimler
        self._scroll_t = QTimer(self, interval=30, timeout=self._autoscroll_tick)
        self.matches = []          # [(sayfa, ilk, sayı)]
        self.mi = -1
        self.highlights = []
        self.pages = PdfPages(self)
        self.setWidget(self.pages)
        self.setWidgetResizable(False)
        self.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.verticalScrollBar().valueChanged.connect(self._scrolled)
        self._cur = -1
        self.findbar = None

    def restyle(self):
        self.setStyleSheet(reader_qss())
        if self.findbar is not None:
            self.findbar.restyle()
        self.pages.update()

    # ---- belge
    def close_doc(self):
        for tp in self._tp.values():
            try:
                tp.close()
            except Exception:
                pass
        self._tp.clear()
        try:
            self.doc.close()
        except Exception:
            pass

    def textpage(self, i):
        tp = self._tp.get(i)
        if tp is None:
            tp = self.doc[i].get_textpage()
            self._tp[i] = tp
            if len(self._tp) > 40:
                for k in list(self._tp)[:10]:
                    if k != i:
                        try:
                            self._tp.pop(k).close()
                        except Exception:
                            pass
        return tp

    def page_text(self, i):
        tp = self.textpage(i)
        return tp.get_text_range(0, tp.count_chars())

    # ---- yerleşim
    def scale(self):
        if self.zoom:
            return self.zoom
        if not self.sizes:
            return 1.0
        vw = self.viewport().width() - 48
        return max(0.4, min(1.6, vw / max(w for w, _ in self.sizes)))

    def relayout(self):
        s = self.scale()
        y = PDF_GAP
        maxw = max((w for w, _ in self.sizes), default=600) * s
        W = max(self.viewport().width(), maxw + 48)
        self.rects = []
        for w, h in self.sizes:
            self.rects.append(QRectF((W - w * s) / 2, y, w * s, h * s))
            y += h * s + PDF_GAP
        self.pages.resize(int(W), int(y + PDF_GAP))
        self.region = None                 # bileşen koordinatında: ölçek değişince geçersiz
        self.pages.update()
        self._place_find()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        frac = self.verticalScrollBar().value() / max(1, self.pages.height())
        self.relayout()
        self.verticalScrollBar().setValue(int(frac * self.pages.height()))

    def page_image(self, i):
        s = self.scale() * self.devicePixelRatioF()
        c = self._cache.get(i)
        if c is not None and abs(c[0] - s) < 1e-3:
            return c[1]
        try:
            page = self.doc[i]
            bmp = page.render(scale=s, may_draw_forms=True, rev_byteorder=True)
            fmt = QImage.Format.Format_RGB888 if bmp.n_channels == 3 else QImage.Format.Format_RGBA8888
            img = QImage(bytes(bmp.buffer), bmp.width, bmp.height, bmp.stride, fmt).copy()
            page.close()
        except Exception:
            return None
        img.setDevicePixelRatio(self.devicePixelRatioF())
        self._cache[i] = (s, img)
        if len(self._cache) > 12:            # bellekte en çok 12 sayfa
            cur = self.current_page()
            for k in sorted(self._cache, key=lambda k: -abs(k - cur))[:len(self._cache) - 12]:
                self._cache.pop(k, None)
        return img

    def current_page(self):
        y = self.verticalScrollBar().value() + self.viewport().height() * 0.35
        for i, r in enumerate(self.rects):
            if r.bottom() + PDF_GAP >= y:
                return i
        return max(0, self.n - 1)

    def _scrolled(self, _v):
        c = self.current_page()
        if c != self._cur:
            self._cur = c
            self.page_changed.emit(c + 1, self.n)

    def go_to(self, page, char=None):
        """page 1'den. char verilirse o karakterin satırı görünür olur."""
        if not (0 <= page - 1 < len(self.rects)):
            return
        y = self.rects[page - 1].top() - PDF_GAP
        if char is not None:
            rs = self.range_rects(page - 1, char, 1)
            if rs:
                y = rs[0].top() - self.viewport().height() * 0.3
        self.verticalScrollBar().setValue(int(y))

    def wheelEvent(self, e):
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            cur = self.current_page()
            z = self.scale() * (1.12 if e.angleDelta().y() > 0 else 1 / 1.12)
            self.zoom = max(0.3, min(4.0, z))
            self.relayout()
            self.go_to(cur + 1)
            e.accept()
            return
        super().wheelEvent(e)

    # ---- koordinatlar
    def page_at(self, pos, clamp=False):
        for i, r in enumerate(self.rects):
            if r.top() - PDF_GAP / 2 <= pos.y() <= r.bottom() + PDF_GAP / 2:
                return i
        if clamp and self.rects:
            return 0 if pos.y() < self.rects[0].top() else len(self.rects) - 1
        return None

    def char_at(self, i, pos, tols=(3, 10)):
        r = self.rects[i]
        s = self.scale()
        x = (pos.x() - r.left()) / s
        y = self.sizes[i][1] - (pos.y() - r.top()) / s
        tp = self.textpage(i)
        for tol in tols:
            k = tp.get_index(x, y, tol, tol)
            if k is not None and k >= 0:
                return k
        return -1

    def char_near(self, i, pos):
        """Sürüklerken: en yakın karakter (sayfanın üstü / altı → ilk / son karakter)."""
        k = self.char_at(i, pos, (3, 12, 40, 120))
        if k >= 0:
            return k
        n = self.textpage(i).count_chars()
        if n == 0:
            return 0
        return 0 if pos.y() < self.rects[i].center().y() else n - 1

    def range_rects(self, i, a, n):
        """Karakter aralığının sayfadaki dikdörtgenleri (bileşen koordinatı)."""
        tp = self.textpage(i)
        r = self.rects[i]
        s = self.scale()
        H = self.sizes[i][1]
        out = []
        try:
            cnt = tp.count_rects(a, n)
            for k in range(cnt):
                lft, bot, rgt, top = tp.get_rect(k)
                out.append(QRectF(r.left() + lft * s, r.top() + (H - top) * s, (rgt - lft) * s, (top - bot) * s))
        except Exception:
            pass
        return out

    # ---- seçim
    def sel_ranges(self):
        """[(sayfa, ilk, sayı)]"""
        if not self.sel:
            return []
        p1, i1, p2, i2 = self.sel
        out = []
        for pg in range(p1, p2 + 1):
            a = i1 if pg == p1 else 0
            b = i2 if pg == p2 else self.textpage(pg).count_chars() - 1
            if b >= a:
                out.append((pg, a, b - a + 1))
        return out

    def selected_text(self):
        return "\n".join(self.textpage(pg).get_text_range(a, n) for pg, a, n in self.sel_ranges())

    def set_selection(self, page, a, n):
        self.sel = (page, a, page, a + n - 1) if n > 0 else None
        self.pages.update()

    # ---- alan seçimi (görsel / grafik)
    def figure_rects(self, i):
        """Sayfadaki gömülü resimlerin dikdörtgenleri (bileşen koordinatı). Çok küçükler (simge, çizgi) yok."""
        if i not in self._figs:
            out = []
            try:
                import pypdfium2.raw as pr
                page = self.doc[i]
                for ob in page.get_objects(filter=[pr.FPDF_PAGEOBJ_IMAGE], max_depth=4):
                    lft, bot, rgt, top = ob.get_bounds()
                    if rgt - lft >= 40 and top - bot >= 30:
                        out.append((lft, bot, rgt, top))
                page.close()
            except Exception:
                pass
            self._figs[i] = out
        r = self.rects[i]
        s = self.scale()
        H = self.sizes[i][1]
        return [QRectF(r.left() + a * s, r.top() + (H - d) * s, (c - a) * s, (d - b) * s).intersected(r)
                for a, b, c, d in self._figs[i]]

    def figure_at(self, pos):
        i = self.page_at(pos)
        if i is None:
            return None
        hits = [fr for fr in self.figure_rects(i) if fr.contains(pos)]
        return (i, min(hits, key=lambda fr: fr.width() * fr.height())) if hits else None

    def set_area_mode(self, on=True):
        self._area_mode = on
        self.pages.setCursor(Qt.CursorShape.CrossCursor if on else Qt.CursorShape.ArrowCursor)

    def clear_region(self):
        if self.region is not None:
            self.region = None
            self.pages.update()

    def region_image(self, max_w=2400):
        """Seçili alanın yüksek çözünürlüklü görüntüsü (sayfa ekrandakinden bağımsız, ~200 dpi)."""
        if self.region is None:
            return None
        i, rr = self.region
        r = self.rects[i]
        s = self.scale()
        w_pt = rr.width() / s
        k = max(1.0, min(200 / 72, max_w / max(1.0, w_pt)))      # nokta başına piksel
        pw, ph = self.sizes[i]
        crop = ((rr.left() - r.left()) / s, ph - (rr.bottom() - r.top()) / s,
                pw - (rr.right() - r.left()) / s, (rr.top() - r.top()) / s)    # sol, alt, sağ, üst kesilecek pay
        crop = tuple(max(0.0, c) for c in crop)
        try:
            page = self.doc[i]
            bmp = page.render(scale=k, crop=crop, may_draw_forms=True, rev_byteorder=True)
            fmt = QImage.Format.Format_RGB888 if bmp.n_channels == 3 else QImage.Format.Format_RGBA8888
            img = QImage(bytes(bmp.buffer), bmp.width, bmp.height, bmp.stride, fmt).copy()
            page.close()
        except Exception:
            return None
        return img.convertToFormat(QImage.Format.Format_RGB32)

    def region_menu(self, gpos):
        """Alan seçilince: araştırma sayfasına ekle / kopyala."""
        from PyQt6.QtWidgets import QMenu
        if self.region is None:
            return
        m = QMenu(self)
        m.addAction(t("rs_fig_add"), self.add_region)
        m.addAction(t("rs_fig_copy") + "\tCtrl+C", self.copy_region)
        m.addSeparator()
        m.addAction(t("rs_fig_cancel"), self.clear_region)
        m.exec(gpos)

    def add_region(self):
        img = self.region_image()
        if img is not None and not img.isNull():
            self.image_req.emit(img, self.region[0] + 1)
        self.clear_region()

    def copy_region(self):
        img = self.region_image()
        if img is None or img.isNull():
            return False
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setImage(img)
        return True

    def press(self, e):
        self.setFocus()
        if e.button() != Qt.MouseButton.LeftButton:
            return
        pos = e.position()
        i = self.page_at(pos)
        self.clear_region()
        if i is not None and (self._area_mode or e.modifiers() & Qt.KeyboardModifier.AltModifier
                              or (self.figure_at(pos) is not None and self.char_at(i, pos, (2,)) < 0)):
            if self.sel:
                self.sel = None
            p = QPointF(min(max(pos.x(), self.rects[i].left()), self.rects[i].right()), pos.y())
            self._rstart = (i, p)
            self._dragging = False
            return
        if i is None:
            self.sel = None
            self.pages.update()
            return
        k = self.char_at(i, pos)
        if k < 0:
            k = self.char_near(i, pos)
        self._anchor = (i, k)
        self._dragging = True
        self._moved = False
        if self.sel:
            self.sel = None
            self.pages.update()

    def _drag_to(self, pos):
        i = self.page_at(pos, clamp=True)
        b = (i, self.char_near(i, pos))
        a = self._anchor
        if a != b:
            self._moved = True
        lo, hi = (a, b) if a <= b else (b, a)
        sel = (lo[0], lo[1], hi[0], hi[1])
        if sel != self.sel:
            self.sel = sel
            self.pages.update()

    def _autoscroll_tick(self):
        """Seçerken fare görünür alanın DIŞINDAYSA kaydır (uzaklaştıkça hızlanır); içerideyken hiç kaydırma."""
        from PyQt6.QtWidgets import QApplication
        if not self._dragging or not (QApplication.mouseButtons() & Qt.MouseButton.LeftButton):
            self._scroll_t.stop()
            return
        vp = self._drag_vp
        h = self.viewport().height()
        d = vp.y() if vp.y() < 0 else vp.y() - h if vp.y() > h else 0
        if not d:
            self._scroll_t.stop()
            return
        step = max(4, min(60, abs(d) // 2)) * (1 if d > 0 else -1)
        sb = self.verticalScrollBar()
        sb.setValue(sb.value() + step)
        self._drag_to(QPointF(self.pages.mapFrom(self.viewport(), vp)))

    def move(self, e):
        pos = e.position()
        if self._rstart is not None and e.buttons() & Qt.MouseButton.LeftButton:
            i, a = self._rstart
            r = self.rects[i]
            b = QPointF(min(max(pos.x(), r.left()), r.right()), min(max(pos.y(), r.top()), r.bottom()))
            self.region = (i, QRectF(a, b).normalized())
            self.pages.update()
            return
        if self._dragging and e.buttons() & Qt.MouseButton.LeftButton:
            self._drag_to(pos)
            # pages → viewport: mapTo (viewport.mapFrom(pages) yanlış: mapFrom'un hedefi ata olmalı; eskiden
            # yanlış çıkan y "alt kenardasın" sanıp her harekette sayfayı aşağı kaydırıyordu)
            self._drag_vp = self.pages.mapTo(self.viewport(), pos.toPoint())
            out = self._drag_vp.y() < 0 or self._drag_vp.y() > self.viewport().height()
            if out and not self._scroll_t.isActive():
                self._scroll_t.start()
            elif not out:
                self._scroll_t.stop()
            return
        i = self.page_at(pos)
        if self._area_mode:
            return
        over = i is not None and self.rects[i].contains(pos) and self.char_at(i, pos, (3,)) >= 0
        fig = not over and i is not None and self.figure_at(pos) is not None
        self.pages.setCursor(Qt.CursorShape.IBeamCursor if over else Qt.CursorShape.CrossCursor if fig
                             else Qt.CursorShape.ArrowCursor)

    def release(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self._rstart is not None:
            start = self._rstart
            self._rstart = None
            self.set_area_mode(False)
            if self.region is None or self.region[1].width() < 8 or self.region[1].height() < 8:
                fig = self.figure_at(start[1])       # tık (sürüklemeden): resmin tamamı
                self.region = fig
                self.pages.update()
            if self.region is not None:
                self.region_menu(e.globalPosition().toPoint())
            return
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self._scroll_t.stop()
            if not self._moved:
                self.sel = None
                self.pages.update()

    def double(self, e):
        pos = e.position()
        i = self.page_at(pos)
        if i is None:
            return
        k = self.char_at(i, pos)
        if k < 0:
            return
        tp = self.textpage(i)
        n = tp.count_chars()
        lo = max(0, k - 60)
        txt = tp.get_text_range(lo, min(n, k + 60) - lo)
        j = k - lo
        if j >= len(txt) or not (txt[j].isalnum() or txt[j] in WORD_CH):
            return
        a = j
        while a > 0 and (txt[a - 1].isalnum() or txt[a - 1] in WORD_CH):
            a -= 1
        b = j
        while b + 1 < len(txt) and (txt[b + 1].isalnum() or txt[b + 1] in WORD_CH):
            b += 1
        self.sel = (i, lo + a, i, lo + b)
        self._dragging = False
        self._moved = True
        self.pages.update()

    def select_page(self):
        i = self.current_page()
        n = self.textpage(i).count_chars()
        if n:
            self.sel = (i, 0, i, n - 1)
            self.pages.update()

    def copy(self):
        txt = clean_quote(self.selected_text())
        if not txt:
            return False
        from PyQt6.QtWidgets import QApplication
        QApplication.clipboard().setText(txt)
        self.copied.emit(txt, self.sel[0] + 1)
        return True

    # ---- vurgular
    def set_highlights(self, lst):
        self.highlights = lst
        self.pages.update()

    def add_highlight(self, color):
        for pg, a, n in self.sel_ranges():
            self.highlights.append({"p": pg, "a": a, "n": n, "c": color,
                                    "t": clean_quote(self.textpage(pg).get_text_range(a, n))[:400]})
        self.sel = None
        self.pages.update()
        self.highlights_changed.emit()

    def highlight_at(self, pos):
        i = self.page_at(pos)
        if i is None:
            return None
        for h in self.highlights:
            if h.get("p") == i and any(r.contains(pos) for r in self.range_rects(i, h["a"], h["n"])):
                return h
        return None

    def remove_highlight(self, h):
        if h in self.highlights:
            self.highlights.remove(h)
            self.pages.update()
            self.highlights_changed.emit()

    def context(self, e):
        from PyQt6.QtWidgets import QMenu
        pos = QPointF(e.pos())
        m = QMenu(self)
        if self.sel:
            txt = clean_quote(self.selected_text())
            pg = self.sel[0] + 1
            m.addAction(t("rs_quote_add"), lambda: self.quote_req.emit(txt, pg))
            m.addAction(t("copy") + "\tCtrl+C", self.copy)
            sub = m.addMenu(t("rs_highlight"))
            for name in HL_COLORS:
                sub.addAction(swatch(HL_COLORS[name]), t("rs_hl_" + name), lambda name=name: self.add_highlight(name))
        h = self.highlight_at(pos)
        if h is not None:
            m.addAction(t("rs_hl_remove"), lambda: self.remove_highlight(h))
        if self.region is not None and self.region[1].contains(pos):
            m.addSeparator()
            m.addAction(t("rs_fig_add"), self.add_region)
            m.addAction(t("rs_fig_copy") + "\tCtrl+C", self.copy_region)
        else:
            fig = self.figure_at(pos)
            if fig is not None:
                m.addSeparator()
                m.addAction(t("rs_fig_add_img"), lambda: (setattr(self, "region", fig), self.add_region()))
        m.addSeparator()
        m.addAction(t("rs_fig_area") + "\tAlt+" + t("rs_drag"), self.set_area_mode)
        m.addAction(t("rs_find") + "\tCtrl+F", self.open_find)
        m.exec(e.globalPos())

    # ---- arama
    def open_find(self):
        if self.findbar is None:
            self.findbar = FindBar(self)
        self.findbar.show()
        self._place_find()
        self.findbar.raise_()
        if self.sel:
            txt = clean_quote(self.selected_text())
            if 0 < len(txt) < 80:
                self.findbar.edit.setText(txt)
        self.findbar.edit.setFocus()
        self.findbar.edit.selectAll()

    def close_find(self):
        if self.findbar is not None:
            self.findbar.hide()
        self.matches = []
        self.mi = -1
        self.pages.update()
        self.setFocus()

    def _place_find(self):
        if self.findbar is not None:
            self.findbar.adjustSize()
            self.findbar.move(self.viewport().width() - self.findbar.width() - 14, 10)

    def find(self, q):
        self.matches = []
        self.mi = -1
        q = (q or "").strip()
        if len(q) >= 2:
            for i in range(self.n):
                try:
                    srch = self.textpage(i).search(q, match_case=False)
                except Exception:
                    continue
                while len(self.matches) < 2000:
                    r = srch.get_next()
                    if not r:
                        break
                    self.matches.append((i, r[0], r[1]))
                try:
                    srch.close()
                except Exception:
                    pass
        if self.matches:
            cur = self.current_page()
            self.mi = next((k for k, m in enumerate(self.matches) if m[0] >= cur), 0)
            self._show_match()
        self._count()
        self.pages.update()

    def find_step(self, d):
        if not self.matches:
            return
        self.mi = (self.mi + d) % len(self.matches)
        self._show_match()
        self._count()
        self.pages.update()

    def _count(self):
        if self.findbar is not None:
            q = self.findbar.edit.text().strip()
            self.findbar.count.setText(f"{self.mi + 1}/{len(self.matches)}" if self.matches else ("0" if q else ""))

    def _show_match(self):
        i, a, n = self.matches[self.mi]
        rs = self.range_rects(i, a, n)
        if rs:
            self.ensureVisible(int(rs[0].center().x()), int(rs[0].center().y()), 60,
                               int(self.viewport().height() * 0.3))

    # ---- çizim (vurgu, arama, seçim)
    def paint_overlay(self, p, i, r):
        if self.region is not None and self.region[0] == i:
            rr = self.region[1]
            p.save()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 70))            # alanın dışı hafif kararır
            for part in (QRectF(r.left(), r.top(), r.width(), rr.top() - r.top()),
                         QRectF(r.left(), rr.bottom(), r.width(), r.bottom() - rr.bottom()),
                         QRectF(r.left(), rr.top(), rr.left() - r.left(), rr.height()),
                         QRectF(rr.right(), rr.top(), r.right() - rr.right(), rr.height())):
                if part.width() > 0 and part.height() > 0:
                    p.drawRect(part)
            from PyQt6.QtGui import QPen
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor("#2D7FF9"), 1.6, Qt.PenStyle.DashLine))
            p.drawRect(rr)
            p.restore()
        if not (self.highlights or self.matches or self.sel):
            return
        p.save()
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
        for h in self.highlights:
            if h.get("p") == i:
                for rr in self.range_rects(i, h["a"], h["n"]):
                    p.fillRect(rr.adjusted(-1, -1, 1, 1), QColor(HL_COLORS.get(h.get("c"), "#FFE066")))
        for k, (pg, a, n) in enumerate(self.matches):
            if pg == i:
                col = QColor("#FFB347") if k == self.mi else QColor("#FFE2B0")
                for rr in self.range_rects(i, a, n):
                    p.fillRect(rr.adjusted(-1, -1, 1, 1), col)
        for pg, a, n in self.sel_ranges():
            if pg == i:
                for rr in self.range_rects(i, a, n):
                    p.fillRect(rr.adjusted(-0.5, -1, 0.5, 1), QColor("#B9C3CF"))
        p.restore()
        if self.matches and 0 <= self.mi < len(self.matches) and self.matches[self.mi][0] == i:
            pg, a, n = self.matches[self.mi]
            p.setPen(QColor("#C8282E"))
            for rr in self.range_rects(i, a, n):
                p.drawRect(rr.adjusted(-1.5, -1.5, 1.5, 1.5))

    # ---- klavye
    def keyPressEvent(self, e):
        from PyQt6.QtGui import QKeySequence
        if e.matches(QKeySequence.StandardKey.Copy):
            if self.region is not None:
                self.copy_region()
            else:
                self.copy()
            return
        if e.matches(QKeySequence.StandardKey.Find):
            self.open_find()
            return
        if e.matches(QKeySequence.StandardKey.SelectAll):
            self.select_page()
            return
        if e.matches(QKeySequence.StandardKey.Undo):
            self.undo_req.emit()
            return
        if e.key() == Qt.Key.Key_Escape:
            if self.findbar is not None and self.findbar.isVisible():
                self.close_find()
            elif self.region is not None or self._area_mode:
                self.clear_region()
                self.set_area_mode(False)
            elif self.sel:
                self.sel = None
                self.pages.update()
            return
        if e.key() == Qt.Key.Key_F3:
            self.find_step(-1 if e.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1)
            return
        super().keyPressEvent(e)


def swatch(col):
    from PyQt6.QtGui import QIcon
    pm = QPixmap(14, 14)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(col))
    p.setPen(QColor(0, 0, 0, 60))
    p.drawRoundedRect(QRectF(1, 1, 12, 12), 3, 3)
    p.end()
    return QIcon(pm)
