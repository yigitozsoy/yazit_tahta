"""Araştırma rafı: kaynaklar türüne göre çizilir (yigitozsoy.net kaynak rafı tarzı).

  kitap    → üst üste yığılmış sırtlar (başlık + yazar), genişlik sayfa sayısından, renk başlıktan;
             üstüne gelince sırt raftan dışarı kayar
  makale   → köşesi kıvrık krem kâğıtlar, ilk satırları üstünde; üstüne gelince kalkar, hafifçe sallanır
  video    → VHS kaset, kırmızı şeritli etiket; üstüne gelince makaralar döner
  görsel   → polaroid,  bağlantı → fiş kartı

Tıkla: aç (activated). Sağ tık: tür / başlık / yazar / Gezgin'de göster. Dosya bırak: klasöre kopyalar."""
import math
import os
from urllib.parse import urlparse

from PyQt6.QtCore import Qt, QRectF, QPointF, QTimer, QElapsedTimer, pyqtSignal, QSize
from PyQt6.QtGui import (QPainter, QColor, QPen, QLinearGradient, QPainterPath, QFontMetricsF, QImageReader,
                         QPixmap, QPolygonF)
from PyQt6.QtWidgets import QWidget, QMenu, QInputDialog, QToolTip

from . import fonts, theme
from .config import prefs
from .i18n import t

# ---- araştırma temaları (prefs research_theme): yazit (varsayılan) | kamuflaj | soft
# Her palet renkler + yazı tipi rolleri (aile listesi) + raf şekli ayrıntıları taşır.
#   f_display başlık · f_body metin · f_label küçük etiket · f_mono künye / sayı · f_hand not · f_quote alıntı
#   kick: bölüm başlığı öneki · upper: başlık / sırt / sekme büyük harf · tilt: notlar eğik
#   r_book / r_card / r_tape: köşe yarıçapı · bands: kitap sırtı bantları (None = yok) · edge: kâğıt kenar çizgisi
RTHEMES = ("yazit", "kamuflaj", "soft")

# kamuflaj = yigitozsoy.net'in paleti (zırh / grafit / kırık beyaz / mürekkep / kırmızı) ve yazı tipleri
_KAMUFLAJ_COMMON = {
    "f_display": ["Oswald"], "f_body": ["Inter"], "f_label": ["JetBrains Mono"], "f_mono": ["JetBrains Mono"],
    "f_hand": ["Caveat"], "f_quote": ["Lora", "Georgia"], "kick": "// ", "upper": True, "tilt": True,
    "label_sp": 0.7, "r_book": 2.5, "r_card": 0, "r_tape": 5, "bands": QColor(217, 180, 90, 170), "edge": None,
    "fold": "#D8D0BE", "rule_line": "#C9C0AC", "card_line": "#C9D3DA", "polaroid": "#F6F3EA", "photo": "#2A2824",
    "reel": "#E9E3D3", "hand_px": 21, "head_px": 54, "title_px": 46,
    "spines": None,           # None = research.SPINE_COLORS (bugünkü renkler)
}
DARK = dict(_KAMUFLAJ_COMMON, **{
    "bg": "#121210", "panel": "#1C1B18", "text": "#D3D1CA", "muted": "#8A877E", "faint": "#3A3833",
    "ink": "#EBC55E", "on_ink": "#121210", "red": "#C8282E", "spine_text": "#F1E8D2", "paper": "#F3EEE2",
    "paper_ink": "#2A2620", "plank": "#2B2924", "plank_hi": "#3A3731", "shadow": QColor(0, 0, 0, 120),
    "cassette": "#1B1A17"})
LIGHT = dict(_KAMUFLAJ_COMMON, **{
    "bg": "#EEEBE3", "panel": "#E4E0D5", "text": "#1C1B18", "muted": "#6E6A60", "faint": "#CFCABD",
    "ink": "#A8781C", "on_ink": "#121210", "red": "#C8282E", "spine_text": "#F1E8D2", "paper": "#FBF8F0",
    "paper_ink": "#2A2620", "plank": "#C9C2B2", "plank_hi": "#D9D3C4", "shadow": QColor(60, 50, 30, 70),
    "cassette": "#24231F"})

# soft: pastel, yumuşak köşeler, yuvarlak yazı tipleri (gömülü: Poppins, Manrope, Patrick Hand, Lora)
_SOFT_COMMON = {
    "f_display": ["Poppins"], "f_body": ["Manrope"], "f_label": ["Manrope"], "f_mono": ["Manrope"],
    "f_hand": ["Patrick Hand"], "f_quote": ["Lora", "Georgia"], "kick": "", "upper": False, "tilt": True,
    "label_sp": 0.9, "r_book": 7, "r_card": 7, "r_tape": 12, "bands": QColor(255, 255, 255, 120), "edge": None,
    "hand_px": 22, "head_px": 50, "title_px": 42,
    "spines": ["#F2C4BE", "#BFDCCB", "#F6DFA8", "#BCD3E8", "#F4CBAE", "#CFE3BA", "#EFC9C3", "#BEE0DC",
               "#E8D5AE", "#C9D8E8", "#F5D6BE", "#D4E2C6", "#F0D0C8", "#C4D9CF"],
}
SOFT_LIGHT = dict(_SOFT_COMMON, **{
    "bg": "#FBF7F2", "panel": "#F3EDE6", "text": "#4A4440", "muted": "#9A918A", "faint": "#E6DDD3",
    "ink": "#D98C7A", "on_ink": "#FFFFFF", "red": "#E9A99A", "spine_text": "#5A514B", "paper": "#FFFDF9",
    "paper_ink": "#5A514B", "plank": "#E7DCCF", "plank_hi": "#F0E7DC", "shadow": QColor(150, 120, 100, 45),
    "cassette": "#B9C7CF", "fold": "#EFE5D8", "rule_line": "#EDE3D7", "card_line": "#DCE7EC",
    "polaroid": "#FFFFFF", "photo": "#E6DDD3", "reel": "#FFFDF9"})
SOFT_DARK = dict(_SOFT_COMMON, **{
    "bg": "#24212A", "panel": "#2C2832", "text": "#ECE4DC", "muted": "#A49A93", "faint": "#3E3944",
    "ink": "#F2B8A8", "on_ink": "#2A2420", "red": "#E9A99A", "spine_text": "#4E4640", "paper": "#F6EFE7",
    "paper_ink": "#5A514B", "plank": "#3A3540", "plank_hi": "#47414D", "shadow": QColor(0, 0, 0, 70),
    "cassette": "#8A9AA6", "fold": "#E4D8CA", "rule_line": "#E9DFD3", "card_line": "#D3E0E6",
    "polaroid": "#FBF7F2", "photo": "#3E3944", "reel": "#F6EFE7"})
# koyu soft'ta zemin morumsu olmasın: sıcak gri-kahve
SOFT_DARK.update({"bg": "#26221F", "panel": "#2F2A26", "faint": "#423B35", "plank": "#3B3530", "plank_hi": "#48413A",
                  "photo": "#423B35"})

_YAZIT_SPINES_DARK = ["#3A3A3C", "#2E3236", "#4A4743", "#34383B", "#45403A", "#2F3530", "#505052", "#3D4044",
                      "#2A2A2A", "#57524A", "#3B4045", "#474747", "#36312C", "#404544"]
_YAZIT_SPINES_LIGHT = ["#5F6368", "#4E5256", "#6E6A64", "#55595C", "#6A645C", "#525A54", "#737376", "#5D6166",
                       "#48484A", "#7A746A", "#5A6066", "#666666", "#5C5650", "#5E6563"]


def _yazit(dark=None):
    """Uygulamanın kendi teması (theme.py paleti + vurgu rengi): sade, gri, Segoe UI / Inter.
    dark=False: açık palet zorla (PDF kâğıdı)."""
    if dark is None:
        c, dark = theme.pal(), theme.is_dark()
    else:
        c = theme.pal() if theme.is_dark() == dark else dict(theme.PALETTES["dark" if dark else "light"])
    ink = QColor(theme.accent())
    if not dark and ink.lightnessF() > 0.6:          # açık vurgu açık zeminde okunmaz → koyulaştır
        ink = ink.darker(250)
    elif dark and ink.lightnessF() < 0.35:
        ink = ink.lighter(180)
    on_ink = "#0f0f0f" if ink.lightnessF() > 0.55 else "#ffffff"
    return {
        "bg": c["bg"], "panel": c["card"] if dark else c["bg2"], "text": c["text"], "muted": c["text2"],
        "faint": c["input_border"], "ink": ink.name(), "on_ink": on_ink, "red": ink.name(),
        "spine_text": "#F1F1F1", "paper": "#F5F5F5" if dark else "#FFFFFF", "paper_ink": "#1F1F1F",
        "plank": c["surface_hover"], "plank_hi": c["surface"],
        "shadow": QColor(0, 0, 0, 110) if dark else QColor(0, 0, 0, 40),
        "cassette": "#2A2A2A" if dark else "#3A3A3A",
        "f_display": ["Segoe UI Variable Display", "Segoe UI", "Inter"],
        "f_body": [fonts.UI, "Segoe UI", "Inter"], "f_label": [fonts.UI, "Segoe UI", "Inter"],
        "f_mono": ["Cascadia Mono", "Consolas", "JetBrains Mono"], "f_hand": [fonts.UI, "Segoe UI", "Inter"],
        "f_quote": [fonts.UI, "Segoe UI", "Inter"], "kick": "", "upper": False, "tilt": False, "label_sp": 0.6,
        "r_book": 3, "r_card": 4, "r_tape": 6, "bands": None, "edge": None if dark else QColor(0, 0, 0, 40),
        "fold": "#DADADA", "rule_line": "#E4E4E4", "card_line": "#E4E4E4", "polaroid": "#FFFFFF",
        "photo": "#3A3A3A", "reel": "#E6E6E6", "hand_px": 16, "head_px": 46, "title_px": 40,
        "spines": _YAZIT_SPINES_DARK if dark else _YAZIT_SPINES_LIGHT,
    }


def rtheme():
    v = prefs.get("research_theme", "yazit")
    return v if v in RTHEMES else "yazit"


def rp():
    k = rtheme()
    if k == "kamuflaj":
        return DARK if theme.is_dark() else LIGHT
    if k == "soft":
        return SOFT_DARK if theme.is_dark() else SOFT_LIGHT
    return _yazit()


def rp_variant(dark):
    """Seçili araştırma temasının koyu / açık paleti (dışa aktarma: site HTML'i, PDF kâğıdı)."""
    k = rtheme()
    if k == "kamuflaj":
        return DARK if dark else LIGHT
    if k == "soft":
        return SOFT_DARK if dark else SOFT_LIGHT
    return _yazit(dark)


def ff(role, P=None):
    """QSS font-family değeri: temanın ailesi + uygulamanın yedek zinciri."""
    fams = (P or rp())[role]
    out = list(fams) + [f for f in fonts.chain() if f not in fams]
    return ", ".join("'%s'" % f for f in out[:6])


def head(txt, P=None):
    """Bölüm başlığı: kamuflaj "// KİTAPLAR", diğerleri "KİTAPLAR"."""
    return (P or rp())["kick"] + txt.upper()


def cap(txt, P=None):
    """Başlık / sırt / sekme yazısı: kamuflaj büyük harf, diğerleri olduğu gibi."""
    return txt.upper() if (P or rp())["upper"] else txt


def spine(s, P=None):
    """Kitap sırtı rengi: elle seçilmişse o, yoksa başlıktan temanın paletinden."""
    P = P or rp()
    if s.over.get("color") or not P.get("spines"):
        return s.color
    from .research import SPINE_COLORS, color_for
    base = color_for(s.title)
    i = SPINE_COLORS.index(base) if base in SPINE_COLORS else s.seed
    return P["spines"][i % len(P["spines"])]


def qc(v, a=None):
    c = QColor(v) if not isinstance(v, QColor) else QColor(v)
    if a is not None:
        c.setAlpha(a)
    return c


def font(family, px, weight=None, spacing=None, italic=False):
    """family: aile adı, aile listesi ya da temanın rolü ("f_display", "f_mono" …)."""
    if isinstance(family, str) and family.startswith("f_"):
        family = rp()[family]
    if isinstance(family, (list, tuple)):
        f = fonts.font(family[0])
        f.setFamilies(list(family) + [x for x in fonts.chain() if x not in family])
    else:
        f = fonts.font(family)
    f.setPixelSize(max(1, round(px)))
    if weight is not None:
        f.setWeight(weight)
    if spacing is not None:
        f.setLetterSpacing(f.SpacingType.AbsoluteSpacing, spacing)
    f.setItalic(italic)
    return f


def out_back(x):
    c1 = 1.70158
    c3 = c1 + 1
    x = max(0.0, min(1.0, x))
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


SECTION_KEYS = {"book": "rs_books", "article": "rs_articles", "video": "rs_videos", "image": "rs_images",
                "link": "rs_links"}
PAD = 16


class Slot:
    """Rafta bir kaynağın yeri."""
    __slots__ = ("src", "rect", "z", "extra")

    def __init__(self, src, rect, z=0, extra=None):
        self.src, self.rect, self.z, self.extra = src, rect, z, extra or {}


class Shelf(QWidget):
    activated = pyqtSignal(object)          # Source
    files_dropped = pyqtSignal(list)
    links_dropped = pyqtSignal(list)       # web adresleri (tarayıcıdan sürüklenen bağlantı)
    changed_type = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)
        self.research = None
        self.slots = []
        self.heads = []            # (y, metin)
        self.planks = []           # QRectF
        self.hover = None          # rel
        self.current = None        # açık sekmedeki kaynak
        self._h = {}               # rel → 0..1 (üstüne gelme animasyonu)
        self._ph = {}              # rel → faz (makara / sallanma)
        self._press = None
        self._drag_on = False
        self._thumbs = {}
        self._clock = QElapsedTimer()
        self._clock.start()
        self._last = 0
        self._anim = QTimer(self, interval=16, timeout=self._tick)
        self._content_h = 200

    # ---- veri
    def set_research(self, r):
        self.research = r
        self._thumbs.clear()
        self.relayout()

    def set_current(self, rel):
        if rel != self.current:
            self.current = rel
            self.update()

    def sizeHint(self):
        return QSize(280, self._content_h)

    def minimumSizeHint(self):
        return QSize(200, self._content_h)

    def resizeEvent(self, e):
        if e.oldSize().width() != e.size().width():
            self.relayout()
        super().resizeEvent(e)

    # ---- yerleşim
    def relayout(self):
        self.slots, self.heads, self.planks = [], [], []
        W = max(200, self.width())
        y = PAD
        if self.research is None or not self.research.sources:
            self._content_h = 260
            self.setMinimumHeight(self._content_h)
            self.update()
            return
        groups = self.research.by_type()
        for typ in ("book", "article", "video", "image", "link"):
            items = groups[typ]
            if not items:
                continue
            self.heads.append((y, f"{head(t(SECTION_KEYS[typ]))} · {len(items)}"))
            y += 26
            y = getattr(self, "_lay_" + typ)(items, y, W) + 22
        self._content_h = int(y)
        self.setMinimumHeight(self._content_h)
        self.updateGeometry()
        self.update()

    def _lay_book(self, items, y, W):
        avail = W - 2 * PAD - 26
        per = 9
        for i, s in enumerate(items):
            if i and i % per == 0:          # yeni yığın
                self.planks.append(QRectF(PAD - 4, y + 1, W - 2 * PAD + 8, 6))
                y += 18
            seed = s.seed
            pages = s.get("pages") or (s.get("words") or 0) / 300 or 150
            w = min(avail, 172 + min(80, pages / 4) + seed % 17)
            h = 22 + seed % 6
            dx = (seed >> 5) % 18
            ang = (((seed >> 9) % 7) - 3) * 0.35
            self.slots.append(Slot(s, QRectF(PAD + dx, y, w, h), 0, {"ang": ang}))
            y += h + 2
        self.planks.append(QRectF(PAD - 4, y + 1, W - 2 * PAD + 8, 6))
        return y + 8

    def _grid(self, items, y, W, cw, ch, step_x, step_y, kind):
        cols = max(1, int((W - 2 * PAD - cw) // step_x) + 1)
        used = (cols - 1) * step_x + cw if len(items) >= cols else (len(items) - 1) * step_x + cw
        x0 = PAD + max(0, (W - 2 * PAD - used) / 2)
        rows = 0
        for i, s in enumerate(items):
            r, c = divmod(i, cols)
            rows = r + 1
            seed = s.seed
            jx = (seed >> 3) % 7 - 3
            jy = (seed >> 7) % 7 - 3
            ang = ((seed >> 11) % 13 - 6) * (1.0 if kind != "video" else 0.35)
            if kind == "article":
                ang = [-3, 4, -6, 2, -1, 5][i % 6] + ((seed >> 4) % 3 - 1)
            self.slots.append(Slot(s, QRectF(x0 + c * step_x + jx, y + r * step_y + jy, cw, ch), i, {"ang": ang}))
        return y + (rows - 1) * step_y + ch + 6

    def _lay_article(self, items, y, W):
        return self._grid(items, y + 6, W, 66, 88, 50, 74, "article")

    def _lay_video(self, items, y, W):
        return self._grid(items, y, W, 124, 78, 134, 90, "video")

    def _lay_image(self, items, y, W):
        return self._grid(items, y + 4, W, 72, 86, 62, 80, "image")

    def _lay_link(self, items, y, W):
        return self._grid(items, y, W, 118, 66, 128, 74, "link")

    # ---- animasyon
    def _tick(self):
        now = self._clock.elapsed()
        dt = min(0.05, (now - self._last) / 1000.0) if self._last else 0.016
        self._last = now
        busy = False
        for rel in set(self._h) | ({self.hover} if self.hover else set()):
            target = 1.0 if rel == self.hover else 0.0
            v = self._h.get(rel, 0.0)
            if v != target:
                v = min(target, v + dt / 0.26) if target > v else max(target, v - dt / 0.2)
                busy = True
            self._h[rel] = v
            if rel == self.hover:
                self._ph[rel] = self._ph.get(rel, 0.0) + dt
                busy = True
            if v == 0.0 and rel != self.hover:
                self._h.pop(rel, None)
                self._ph.pop(rel, None)
        if not busy:
            self._anim.stop()
            self._last = 0
        self.update()

    def _kick(self):
        if not self._anim.isActive():
            self._last = 0
            self._anim.start()

    # ---- fare
    def slot_at(self, pos):
        best = None
        for sl in self.slots:
            r = sl.rect
            if sl.src.type == "book":
                r = r.adjusted(0, 0, 18, 0)
            if r.contains(QPointF(pos)):
                if best is None or sl.z >= best.z or sl.src.rel == self.hover:
                    best = sl
        return best

    def mouseMoveEvent(self, e):
        sl = self.slot_at(e.position())
        rel = sl.src.rel if sl else None
        if rel != self.hover:
            self.hover = rel
            self.setCursor(Qt.CursorShape.PointingHandCursor if rel else Qt.CursorShape.ArrowCursor)
            if sl:
                QToolTip.showText(e.globalPosition().toPoint(), self._tip(sl.src), self)
            else:
                QToolTip.hideText()
            self._kick()

    def leaveEvent(self, e):
        if self.hover:
            self.hover = None
            self._kick()
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        sl = self.slot_at(e.position())
        self._press = sl.src.rel if sl else None
        if e.button() == Qt.MouseButton.RightButton and sl:
            self._menu(sl.src, e.globalPosition().toPoint())

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton:
            return
        sl = self.slot_at(e.position())
        if sl and sl.src.rel == self._press:
            self.activated.emit(sl.src)
        self._press = None

    def _tip(self, s):
        bits = [f"<b>{_esc(s.title)}</b>"]
        sub = " · ".join(x for x in (s.author, s.year) if x)
        if sub:
            bits.append(_esc(sub))
        more = []
        if s.get("pages"):
            more.append(t("rs_pages").format(n=s.get("pages")))
        if s.get("duration"):
            d = s.get("duration")
            more.append(f"{d // 60}:{d % 60:02d}")
        if s.get("isbn"):
            more.append("ISBN " + s.get("isbn"))
        if s.get("url"):
            more.append(_esc(s.get("url")))
        if more:
            bits.append(f"<span style='color:{rp()['muted']}'>" + " · ".join(more) + "</span>")
        bits.append(f"<span style='color:{rp()['muted']}'>" + _esc(s.rel) + "</span>")
        return "<br>".join(bits)

    def _menu(self, s, gpos):
        m = QMenu(self)
        m.addAction(t("rs_open"), lambda: self.activated.emit(s))
        sub = m.addMenu(t("rs_type"))
        for typ in ("book", "article", "video", "image", "link"):
            a = sub.addAction(t("rs_t_" + typ), lambda typ=typ: self._set_type(s, typ))
            a.setCheckable(True)
            a.setChecked(s.type == typ)
        sub.addSeparator()
        sub.addAction(t("rs_type_auto"), lambda: self._set_type(s, None))
        m.addAction(t("rs_edit_title"), lambda: self._edit(s, "title"))
        m.addAction(t("rs_edit_author"), lambda: self._edit(s, "author"))
        m.addSeparator()
        m.addAction(t("rs_reveal"), lambda: reveal(s.path))
        m.exec(gpos)

    def _set_type(self, s, typ):
        self.research.set_override(s.rel, type=typ)
        self.changed_type.emit()

    def _edit(self, s, key):
        cur = s.title if key == "title" else s.author
        txt, ok = QInputDialog.getText(self, t("rs_edit_" + key), t("rs_edit_" + key), text=cur)
        if ok:
            self.research.set_override(s.rel, **{key: txt.strip()})

    # ---- sürükle bırak
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():          # dosya ya da web bağlantısı
            e.acceptProposedAction()
            self._drag_on = True
            self.update()

    def dragMoveEvent(self, e):
        e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self._drag_on = False
        self.update()

    def dropEvent(self, e):
        self._drag_on = False
        urls = e.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if u.isLocalFile()]
        links = [u.toString() for u in urls if u.scheme() in ("http", "https")]
        e.acceptProposedAction()
        self.update()
        if paths:
            self.files_dropped.emit(paths)
        if links:
            self.links_dropped.emit(links)

    # ---- çizim
    def paintEvent(self, e):
        P = rp()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if not self.slots:
            self._paint_empty(p, P)
        p.setFont(font(P["f_label"], 10, 600, P["label_sp"]))
        p.setPen(qc(P["muted"]))
        for y, txt in self.heads:
            p.drawText(QRectF(PAD, y, self.width() - 2 * PAD, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, txt)
        for r in self.planks:
            g = QLinearGradient(r.topLeft(), r.bottomLeft())
            g.setColorAt(0, qc(P["plank_hi"]))
            g.setColorAt(1, qc(P["plank"]))
            p.fillRect(r, g)
            p.fillRect(QRectF(r.x(), r.bottom(), r.width(), 3), qc(P["shadow"]))
        order = sorted(self.slots, key=lambda sl: (sl.src.rel == self.hover, sl.z))
        for sl in order:
            getattr(self, "_paint_" + sl.src.type)(p, P, sl)
        if self._drag_on:
            p.setPen(QPen(qc(P["ink"]), 1.5, Qt.PenStyle.DashLine))
            p.setBrush(qc(P["ink"], 22))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(6, 6, -6, -6), 10, 10)

    def _paint_empty(self, p, P):
        r = QRectF(PAD, PAD, self.width() - 2 * PAD, 200)
        p.setPen(QPen(qc(P["faint"]), 1.2, Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, 10, 10)
        p.setPen(qc(P["muted"]))
        p.setFont(font(P["f_display"], 17, 500, 0.6 if P["upper"] else None))
        p.drawText(r.adjusted(16, 40, -16, 0), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                   cap(t("rs_empty"), P))
        p.setFont(font(P["f_label"], 10))
        p.drawText(r.adjusted(18, 80, -18, -10), Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop |
                   Qt.TextFlag.TextWordWrap, t("rs_empty_hint"))

    def _h_of(self, sl):
        return self._h.get(sl.src.rel, 0.0)

    def _paint_book(self, p, P, sl):
        s = sl.src
        h = self._h_of(sl)
        r = QRectF(sl.rect)
        r.translate(18 * out_back(h) if h else 0, 0)
        p.save()
        c = r.center()
        p.translate(c)
        p.rotate(sl.extra["ang"] * (1 - h))
        p.translate(-c)
        # gölge
        rb = P["r_book"]
        sh = QPainterPath()
        sh.addRoundedRect(r.translated(1.5, 2.5), rb, rb)
        p.fillPath(sh, qc(P["shadow"]))
        base = qc(spine(s, P))
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0, base.lighter(128))
        g.setColorAt(0.18, base.lighter(108))
        g.setColorAt(0.8, base)
        g.setColorAt(1, base.darker(135))
        path = QPainterPath()
        path.addRoundedRect(r, rb, rb)
        p.fillPath(path, g)
        # sırt bantları (kamuflaj altın, soft yumuşak beyaz noktalar, yazıt yok)
        gold = P["bands"]
        if gold is not None and rb >= 5:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(gold)
            for bx in (r.left() + 8, r.right() - 8):
                p.drawEllipse(QPointF(bx, r.center().y()), 2, 2)
        elif gold is not None:
            for bx in (r.left() + 7, r.left() + 10):
                p.fillRect(QRectF(bx, r.top() + 2, 1.2, r.height() - 4), gold)
            p.fillRect(QRectF(r.right() - 9, r.top() + 2, 1.2, r.height() - 4), gold)
        else:
            p.fillRect(QRectF(r.left() + 6, r.top() + 3, 2, r.height() - 6), qc(P["spine_text"], 60))
        # yazı
        auth = cap(s.short_author(), P)
        fa = font(P["f_mono"] if P["upper"] else P["f_label"], 8.5, 500, 0.6 if P["upper"] else None)
        aw = min(QFontMetricsF(fa).horizontalAdvance(auth) + 8, r.width() * 0.34) if auth else 0
        ft = font(P["f_display"], min(13, r.height() * 0.52), 500 if P["upper"] else 600,
                  0.5 if P["upper"] else None)
        tr = QRectF(r.left() + 16, r.top(), r.width() - 30 - aw, r.height())
        p.setFont(ft)
        p.setPen(qc(P["spine_text"]))
        title = QFontMetricsF(ft).elidedText(cap(s.title, P), Qt.TextElideMode.ElideRight, tr.width())
        p.drawText(tr, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, title)
        if auth:
            p.setFont(fa)
            p.setPen(qc(P["spine_text"], 150))
            p.drawText(QRectF(r.right() - 14 - aw, r.top(), aw, r.height()),
                       Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                       QFontMetricsF(fa).elidedText(auth, Qt.TextElideMode.ElideRight, aw - 4))
        if s.rel == self.current:
            p.fillRect(QRectF(r.left() - 6, r.top() + 4, 3, r.height() - 8), qc(P["ink"]))
        p.restore()

    def _paint_article(self, p, P, sl):
        s = sl.src
        h = self._h_of(sl)
        r = QRectF(sl.rect)
        ph = self._ph.get(s.rel, 0.0)
        ang = sl.extra["ang"] * (1 - 0.7 * h) + math.sin(ph * 9) * 2.2 * h * math.exp(-ph * 2.2)
        lift = 10 * out_back(h) if h else 0
        p.save()
        c = r.center()
        p.translate(c.x(), c.y() - lift)
        p.rotate(ang)
        sc = 1 + 0.07 * h
        p.scale(sc, sc)
        p.translate(-c)
        fold = 12
        path = QPainterPath()
        rc = min(P["r_card"], 6)
        if rc:
            path.moveTo(r.left() + rc, r.top())
            path.lineTo(r.right() - fold, r.top())
            path.lineTo(r.right(), r.top() + fold)
            path.lineTo(r.right(), r.bottom() - rc)
            path.quadTo(r.right(), r.bottom(), r.right() - rc, r.bottom())
            path.lineTo(r.left() + rc, r.bottom())
            path.quadTo(r.left(), r.bottom(), r.left(), r.bottom() - rc)
            path.lineTo(r.left(), r.top() + rc)
            path.quadTo(r.left(), r.top(), r.left() + rc, r.top())
        else:
            path.moveTo(r.topLeft())
            path.lineTo(r.right() - fold, r.top())
            path.lineTo(r.right(), r.top() + fold)
            path.lineTo(r.bottomRight())
            path.lineTo(r.bottomLeft())
        path.closeSubpath()
        p.fillPath(path.translated(1.5 + 2 * h, 2.5 + 4 * h), qc(P["shadow"]))
        p.fillPath(path, qc(P["paper"]))
        if P["edge"] is not None:
            p.setPen(QPen(P["edge"], 0.8))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
        # kıvrık köşe
        tri = QPolygonF([QPointF(r.right() - fold, r.top()), QPointF(r.right() - fold, r.top() + fold),
                         QPointF(r.right(), r.top() + fold)])
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qc(P["fold"]))
        p.drawPolygon(tri)
        ink = qc(P["paper_ink"])
        # başlık
        p.setPen(ink)
        ft = font(P["f_display"], 7.6, 600, 0.2 if P["upper"] else None)
        p.setFont(ft)
        tr = QRectF(r.left() + 6, r.top() + 6, r.width() - 12 - fold * 0.6, 28)
        p.drawText(tr, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
                   _clip_lines(cap(s.title, P), ft, tr.width(), 3))
        # ilk satırlar (küçük)
        fe = font(P["f_mono"], 3.6)
        p.setFont(fe)
        p.setPen(qc(P["paper_ink"], 150))
        ex = (s.get("excerpt") or "").replace("\n", " ")
        y = r.top() + 34
        fm = QFontMetricsF(fe)
        words = ex.split()
        line = ""
        while words and y < r.bottom() - 14:
            wd = words.pop(0)
            if fm.horizontalAdvance(line + " " + wd) > r.width() - 12 and line:
                p.drawText(QPointF(r.left() + 6, y), line)
                y += 5.2
                line = wd
            else:
                line = (line + " " + wd).strip()
        if line and y < r.bottom() - 14:
            p.drawText(QPointF(r.left() + 6, y), line)
            y += 5.2
        # çizgiler
        p.setPen(QPen(qc(P["rule_line"]), 0.6))
        while y < r.bottom() - 10:
            p.drawLine(QPointF(r.left() + 6, y), QPointF(r.right() - 6, y))
            y += 5.2
        # alt: yazar / sayfa
        foot = " · ".join(x for x in (s.short_author(), s.year) if x)
        if foot:
            p.setFont(font(P["f_mono"], 4.6, 600))
            p.setPen(qc(P["red"]))
            p.drawText(QRectF(r.left() + 6, r.bottom() - 10, r.width() - 12, 8),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, cap(foot, P))
        if s.rel == self.current:
            p.setPen(QPen(qc(P["ink"]), 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
        p.restore()

    def _paint_video(self, p, P, sl):
        s = sl.src
        h = self._h_of(sl)
        r = QRectF(sl.rect)
        ph = self._ph.get(s.rel, 0.0)
        p.save()
        c = r.center()
        p.translate(c.x(), c.y() - 3 * h)
        p.rotate(sl.extra["ang"] * (1 - h))
        p.translate(-c)
        body = QPainterPath()
        body.addRoundedRect(r, P["r_tape"], P["r_tape"])
        p.fillPath(body.translated(1.5, 3), qc(P["shadow"]))
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0, qc(P["cassette"]).lighter(135))
        g.setColorAt(1, qc(P["cassette"]))
        p.fillPath(body, g)
        p.setPen(QPen(qc("#000000", 140), 1))
        p.drawPath(body)
        # etiket
        lab = QRectF(r.left() + 8, r.top() + 7, r.width() - 16, 30)
        lp = QPainterPath()
        lr = min(P["r_card"], 5)
        lp.addRoundedRect(lab, lr, lr)
        p.fillPath(lp, qc(P["paper"]))
        p.fillRect(QRectF(lab.left() + lr, lab.top() + 4, lab.width() - 2 * lr, 5), qc(P["red"]))
        ft = font(P["f_display"], 9, 600, 0.4 if P["upper"] else None)
        p.setFont(ft)
        p.setPen(qc(P["paper_ink"]))
        p.drawText(QRectF(lab.left() + 5, lab.top() + 10, lab.width() - 10, 19),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                   QFontMetricsF(ft).elidedText(cap(s.title, P), Qt.TextElideMode.ElideRight, lab.width() - 10))
        d = s.get("duration")
        if d:
            p.setFont(font(P["f_mono"], 6.5, 600))
            p.setPen(qc(P["red"]))
            dur = f"{d // 3600}:{d // 60 % 60:02d}:{d % 60:02d}" if d >= 3600 else f"{d // 60}:{d % 60:02d}"
            p.drawText(QRectF(r.left() + 8, r.bottom() - 13, r.width() - 16, 10),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, dur)
        # pencere + makaralar
        win = QRectF(r.center().x() - 30, r.top() + 42, 60, 22)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qc("#0B0B0A"))
        p.drawRoundedRect(win, 8, 8)
        p.setBrush(qc("#4A3A2A", 200))
        p.drawRect(QRectF(win.left() + 14, win.top() + 6, win.width() - 28, win.height() - 12))
        for i, cx in enumerate((win.left() + 11, win.right() - 11)):
            self._reel(p, QPointF(cx, win.center().y()), 8.2, ph * (6.5 if i == 0 else 5.5) * (1 if h else 0), P)
        # vida delikleri
        p.setBrush(qc("#000000", 120))
        for x in (r.left() + 6, r.right() - 6):
            p.drawEllipse(QPointF(x, r.bottom() - 6), 1.6, 1.6)
        if s.rel == self.current:
            p.setPen(QPen(qc(P["ink"]), 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(body)
        p.restore()

    def _reel(self, p, c, rad, ang, P):
        p.save()
        p.translate(c)
        p.rotate(math.degrees(ang))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qc(P["reel"]))
        p.drawEllipse(QPointF(0, 0), rad, rad)
        p.setBrush(qc("#0B0B0A"))
        p.drawEllipse(QPointF(0, 0), rad * 0.42, rad * 0.42)
        p.setBrush(qc(P["reel"]))
        for k in range(6):
            a = k * math.pi / 3
            p.drawRect(QRectF(rad * 0.18 * math.cos(a) - 1, rad * 0.18 * math.sin(a) - 1, 2, 2))
        p.setPen(QPen(qc("#0B0B0A"), 1.2))
        for k in range(3):
            a = k * 2 * math.pi / 3
            p.drawLine(QPointF(rad * 0.5 * math.cos(a), rad * 0.5 * math.sin(a)),
                       QPointF(rad * 0.85 * math.cos(a), rad * 0.85 * math.sin(a)))
        p.restore()

    def _thumb(self, s, w, h):
        key = (s.rel, w, h)
        if key not in self._thumbs:
            rd = QImageReader(s.path)
            rd.setAutoTransform(True)
            sz = rd.size()
            pm = QPixmap()
            if sz.isValid() and sz.width() > 0:
                dpr = self.devicePixelRatioF()
                k = max(w * dpr / sz.width(), h * dpr / sz.height())
                rd.setScaledSize(QSize(max(1, round(sz.width() * k)), max(1, round(sz.height() * k))))
                img = rd.read()
                if not img.isNull():
                    pm = QPixmap.fromImage(img)
                    pm.setDevicePixelRatio(dpr)
            self._thumbs[key] = pm
        return self._thumbs[key]

    def _paint_image(self, p, P, sl):
        s = sl.src
        h = self._h_of(sl)
        r = QRectF(sl.rect)
        p.save()
        c = r.center()
        p.translate(c.x(), c.y() - 6 * out_back(h) if h else c.y())
        p.rotate(sl.extra["ang"] * (1 - h))
        sc = 1 + 0.08 * h
        p.scale(sc, sc)
        p.translate(-c)
        rc = min(P["r_card"], 5)
        fr = QPainterPath()
        fr.addRoundedRect(r, rc, rc)
        p.fillPath(fr.translated(1.5, 3), qc(P["shadow"]))
        p.fillPath(fr, qc(P["polaroid"]))
        if P["edge"] is not None:
            p.setPen(QPen(P["edge"], 0.8))
            p.drawPath(fr)
        ph = QRectF(r.left() + 5, r.top() + 5, r.width() - 10, r.width() - 10)
        pm = self._thumb(s, round(ph.width()), round(ph.height()))
        if not pm.isNull():
            pw, phh = pm.width() / pm.devicePixelRatio(), pm.height() / pm.devicePixelRatio()
            src = QRectF((pw - ph.width()) / 2 * pm.devicePixelRatio(), (phh - ph.height()) / 2 * pm.devicePixelRatio(),
                         ph.width() * pm.devicePixelRatio(), ph.height() * pm.devicePixelRatio())
            p.drawPixmap(ph, pm, src)
        else:
            p.fillRect(ph, qc(P["photo"]))
        p.setFont(font(P["f_hand"], 10.5 if P["tilt"] else 8.5, 600))
        p.setPen(qc(P["paper_ink"]))
        cap = QRectF(r.left() + 4, ph.bottom() + 1, r.width() - 8, r.bottom() - ph.bottom() - 2)
        p.drawText(cap, Qt.AlignmentFlag.AlignCenter,
                   QFontMetricsF(p.font()).elidedText(s.title, Qt.TextElideMode.ElideRight, cap.width()))
        if s.rel == self.current:
            p.setPen(QPen(qc(P["ink"]), 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r)
        p.restore()

    def _paint_link(self, p, P, sl):
        s = sl.src
        h = self._h_of(sl)
        r = QRectF(sl.rect)
        p.save()
        c = r.center()
        p.translate(c.x(), c.y() - 5 * out_back(h) if h else c.y())
        p.rotate(sl.extra["ang"] * 0.4 * (1 - h))
        p.translate(-c)
        rc = min(P["r_card"], 6)
        cp = QPainterPath()
        cp.addRoundedRect(r, rc, rc)
        p.fillPath(cp.translated(1.5, 2.5), qc(P["shadow"]))
        p.fillPath(cp, qc(P["paper"]))
        if P["edge"] is not None:
            p.setPen(QPen(P["edge"], 0.8))
            p.drawPath(cp)
        p.fillRect(QRectF(r.left(), r.top() + 15, r.width(), 1.2), qc(P["red"], 200))
        p.setPen(QPen(qc(P["card_line"]), 0.6))
        y = r.top() + 26
        while y < r.bottom() - 4:
            p.drawLine(QPointF(r.left() + 2, y), QPointF(r.right() - 2, y))
            y += 8
        ft = font(P["f_mono"], 7.4, 700)
        p.setFont(ft)
        p.setPen(qc(P["paper_ink"]))
        p.drawText(QRectF(r.left() + 6, r.top() + 2, r.width() - 12, 13), Qt.AlignmentFlag.AlignVCenter,
                   QFontMetricsF(ft).elidedText(s.title, Qt.TextElideMode.ElideRight, r.width() - 12))
        dom = urlparse(s.get("url") or "").netloc.replace("www.", "")
        if dom:
            p.setFont(font(P["f_mono"], 6.5))
            p.setPen(qc(P["paper_ink"], 160))
            p.drawText(QRectF(r.left() + 6, r.top() + 18, r.width() - 12, 10), Qt.AlignmentFlag.AlignVCenter,
                       "↗ " + dom)
        if s.rel == self.current:
            p.setPen(QPen(qc(P["ink"]), 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(r)
        p.restore()


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _clip_lines(text, f, width, n):
    """Metni en çok n satıra sığdır (son satır üç nokta)."""
    fm = QFontMetricsF(f)
    words, lines, cur = text.split(), [], ""
    while words:
        w = words[0]
        if fm.horizontalAdvance((cur + " " + w).strip()) <= width or not cur:
            cur = (cur + " " + w).strip()
            words.pop(0)
        else:
            lines.append(cur)
            cur = ""
            if len(lines) == n:
                break
    if cur and len(lines) < n:
        lines.append(cur)
    if words and lines:
        lines[-1] = fm.elidedText(lines[-1] + " " + " ".join(words), Qt.TextElideMode.ElideRight, width)
    return "\n".join(lines[:n])


def reveal(path):
    import subprocess
    try:
        subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
    except OSError:
        pass
