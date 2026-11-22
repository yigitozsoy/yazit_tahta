"""Tuval nesneleri: kalem / fosforlu / şekil çizgileri, yazı, görsel, tablo ve lazer izi.
Hepsi sözlüğe çevrilip (not dosyası, kopyala-yapıştır) geri okunabilir."""
import base64
import copy
import math
import time

from PyQt6.QtCore import Qt, QPointF, QRectF, QRect, QByteArray, QBuffer, QIODevice
from PyQt6.QtGui import (QPainterPath, QPen, QColor, QPainterPathStroker, QFont, QPixmap, QImage, QTextCursor,
                         QBrush, QTransform, QTextOption, QFontMetricsF)
from PyQt6.QtWidgets import (QGraphicsPathItem, QGraphicsTextItem, QGraphicsPixmapItem, QGraphicsItem,
                             QGraphicsScene, QStyle)

from .theme import color as theme_color
from . import fonts

SEL_COLOR = QColor("#3ea6ff")
Z_BASE = {"image": -3_000_000, "hl": -2_000_000}
FLAGS = QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemIsMovable
from . import engshapes
FILLABLE = ("rect", "ellipse") + engshapes.FILLABLE
TEXT_ALIGN = {"left": Qt.AlignmentFlag.AlignLeft, "center": Qt.AlignmentFlag.AlignHCenter,
              "right": Qt.AlignmentFlag.AlignRight}


def ink(name) -> QColor:
    """Renk adı: "auto" = tema metin rengi (koyu temada beyaz, açıkta siyah)."""
    if not name or name == "auto":
        return QColor(theme_color("text"))
    return QColor(name)


class YazitScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(-200000, -200000, 400000, 400000)
        self.zseq = 0

    def next_z(self, kind):
        self.zseq += 1
        return Z_BASE.get(kind, 0) + self.zseq

    def front_z(self):
        """En üst katman: türünden bağımsız, sonra çizilen her şey yine bunun üstüne gelir."""
        self.zseq += 1
        return float(self.zseq)

    def content_items(self):
        return [it for it in self.items() if isinstance(it, CONTENT)]

    def restyle(self):
        for it in self.content_items():
            it.apply_style()


def _strip_state(opt):
    sel = bool(opt.state & QStyle.StateFlag.State_Selected)
    opt.state = opt.state & ~QStyle.StateFlag.State_Selected & ~QStyle.StateFlag.State_HasFocus
    return sel


def _draw_sel(p, rect, dashed=True):
    pen = QPen(SEL_COLOR, 1.4)
    pen.setCosmetic(True)
    if dashed:
        pen.setStyle(Qt.PenStyle.DashLine)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(rect)


def simplify(pts, eps):
    """Ramer–Douglas–Peucker: çizgiyi bozmadan gereksiz noktaları atar."""
    n = len(pts)
    if n < 3:
        return list(pts)
    keep = [False] * n
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay, bx, by = pts[a].x(), pts[a].y(), pts[b].x(), pts[b].y()
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy)
        best, bi = -1.0, -1
        for i in range(a + 1, b):
            px, py = pts[i].x(), pts[i].y()
            d = math.hypot(px - ax, py - ay) if L < 1e-9 else abs(dy * px - dx * py + bx * ay - by * ax) / L
            if d > best:
                best, bi = d, i
        if best > eps:
            keep[bi] = True
            stack.append((a, bi))
            stack.append((bi, b))
    return [p for p, k in zip(pts, keep) if k]


def smooth_path(pts):
    path = QPainterPath()
    if not pts:
        return path
    path.moveTo(pts[0])
    if len(pts) == 1:
        path.lineTo(pts[0] + QPointF(0.01, 0.0))  # tek tık = nokta
        return path
    if len(pts) == 2:
        path.lineTo(pts[1])
        return path
    for i in range(1, len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        path.quadTo(a, QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2))
    path.lineTo(pts[-1])
    return path


# çizgi türleri: kalınlığın katı (yuvarlak uç her parçaya yarım kalınlık ekler → boşluklar 1'den büyük)
DASH_PATTERN = {"dash": [2.6, 2.6], "dot": [0.01, 2.3], "dashdot": [2.6, 2.3, 0.01, 2.3]}
DASHES = ("solid", "dash", "dot", "dashdot")


class StrokeItem(QGraphicsPathItem):
    """Serbest çizgi (pen / hl) ya da iki noktalı şekil (line / arrow / rect / ellipse)."""

    def __init__(self, kind, color="auto", width=4.0, pts=None):
        super().__init__()
        self.kind = kind
        self.color_name = color
        self.width = float(width)
        self.pts = list(pts or [])
        self.fill = None          # dikdörtgen / elips dolgu rengi (None = boş)
        self.dash = "solid"       # çizgi türü: solid | dash | dot | dashdot (kayıtta "ds")
        self.brush = "pen"        # kalem türü (yalnızca kind == "pen"): brushes.NAMES (kayıtta "br")
        self.var = None           # mühendislik şekli seçeneği (kanat profilinde NACA kodu; kayıtta "v")
        self.bend = None          # çizgi / ok bükülmesi: eğrinin ortasından geçtiği yerel nokta (kayıtta "bd")
        self._bc = None
        self.setFlags(FLAGS)
        self.apply_style()
        self.rebuild(smooth=True)

    def apply_style(self):
        c = ink(self.color_name)
        if self.kind == "hl":
            c.setAlpha(105)
        pen = QPen(c, self.width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        if self.dash in DASH_PATTERN:
            pen.setDashPattern(DASH_PATTERN[self.dash])
        self.setPen(pen)
        if self.fill and self.kind in FILLABLE:
            self.setBrush(QBrush(ink(self.fill)))
        else:
            self.setBrush(QBrush(Qt.BrushStyle.NoBrush))

    # --- canlı çizim
    def add_point(self, p):
        self.pts.append(p)
        path = self.path()
        if path.elementCount() == 0:
            path.moveTo(p)
        else:
            path.lineTo(p)
        self.setPath(path)

    def set_points(self, pts):
        self.pts = list(pts)
        self.rebuild()

    def finish(self, zoom=1.0):
        if self.kind in ("pen", "hl") and len(self.pts) > 2:
            self.pts = simplify(self.pts, 0.35 / max(zoom, 0.05))
        self.rebuild(smooth=True)

    def rebuild(self, smooth=True):
        pts = self.pts
        path = QPainterPath()
        if self.kind in ("pen", "hl"):
            path = smooth_path(pts)
        elif len(pts) >= 2:
            a, b = pts[0], pts[-1]
            ctrl = None
            if self.bend is not None and self.kind in ("line", "arrow"):
                mid = QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2)
                ctrl = self.bend * 2 - mid       # eğri tutamacın üstünden geçsin
            if self.kind == "line":
                path.moveTo(a)
                if ctrl is not None:
                    path.quadTo(ctrl, b)
                else:
                    path.lineTo(b)
            elif self.kind == "arrow":
                path.moveTo(a)
                if ctrl is not None:
                    path.quadTo(ctrl, b)
                else:
                    path.lineTo(b)
                src = ctrl if ctrl is not None else a
                dx, dy = b.x() - src.x(), b.y() - src.y()
                if math.hypot(dx, dy) > 1:
                    ang = math.atan2(dy, dx)
                    h = max(12.0, self.width * 3.4)
                    l_, r_ = ang + math.pi - 0.45, ang + math.pi + 0.45
                    path.moveTo(QPointF(b.x() + h * math.cos(l_), b.y() + h * math.sin(l_)))
                    path.lineTo(b)
                    path.lineTo(QPointF(b.x() + h * math.cos(r_), b.y() + h * math.sin(r_)))
            elif self.kind == "rect":
                path.addRoundedRect(QRectF(a, b).normalized(), 2, 2)
            elif self.kind == "ellipse":
                path.addEllipse(QRectF(a, b).normalized())
            elif self.kind in engshapes.KINDS:
                path = engshapes.build(self.kind, a, b, self.width, self.var)
        elif pts:
            path.moveTo(pts[0])
            path.lineTo(pts[0] + QPointF(0.01, 0))
        self.setPath(path)

    def shape(self):
        st = QPainterPathStroker()
        st.setWidth(max(self.width, 6.0))
        st.setCapStyle(Qt.PenCapStyle.RoundCap)
        st.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        out = st.createStroke(self.path())
        if self.fill and self.kind in FILLABLE:   # dolu şeklin içine tıklayınca da seçilsin
            out = out.united(self.path())
        return out

    def textured(self):
        return self.kind == "pen" and self.brush != "pen"

    def boundingRect(self):
        if self.textured():
            from . import brushes
            e = brushes.extent(self)
            return self.path().boundingRect().adjusted(-e, -e, e, e)
        return super().boundingRect()

    def paint(self, p, opt, w=None):
        sel = _strip_state(opt)
        if self.textured():
            from . import brushes
            brushes.paint(p, self, self.pen().color(), DASH_PATTERN.get(self.dash))
        else:
            super().paint(p, opt, w)
        if sel:
            _draw_sel(p, self.boundingRect())


class TextItem(QGraphicsTextItem):
    kind = "text"

    def __init__(self, text="", color="auto", size=26):
        super().__init__()
        self.color_name = color
        self.size = float(size)
        self.bold = self.italic = self.underline = False
        self.align = "left"
        self.family = ""          # "" = arayüz yazı tipi; kayıtta "ff"
        self.link = None          # kamug bağlantısı {"kamug": video, "t": sn} (eski notlarda "gamma"); kayıtta "ln" (kamuglink.py)
        self.document().setDocumentMargin(4)
        self.apply_font()
        self.setPlainText(text)
        self.setFlags(FLAGS)
        self.on_finished = None   # fn(item, önceki, sonraki, yeni_mi)
        self._before = None
        self.is_new = False
        self.apply_style()

    def apply_style(self):
        self.setDefaultTextColor(ink(self.color_name))

    def apply_font(self):
        f = fonts.font(self.family)
        f.setPixelSize(max(6, int(round(self.size))))
        f.setWeight(QFont.Weight.Bold if self.bold else (QFont.Weight.Medium if not self.family else QFont.Weight.Normal))
        f.setItalic(self.italic)
        f.setUnderline(self.underline)
        self.setFont(f)
        self.apply_layout()

    def apply_layout(self):
        """Hizalama için yazı genişliği sabitlenir (en uzun satır kadar); yazarken serbest kalır."""
        self.document().setDefaultTextOption(QTextOption(TEXT_ALIGN.get(self.align, Qt.AlignmentFlag.AlignLeft)))
        self.setTextWidth(-1)
        if self.align != "left" and not self.editing():
            self.setTextWidth(self.document().idealWidth() + 1)

    def editing(self):
        return bool(self.textInteractionFlags() & Qt.TextInteractionFlag.TextEditorInteraction)

    def start_edit(self, select_all=False):
        if not self.editing():
            self._before = self.toPlainText()
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.apply_layout()     # yazarken genişlik serbest (ortalı / sağa yaslı yazı da kaymadan uzar)
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        c = self.textCursor()
        c.movePosition(QTextCursor.MoveOperation.End)
        if select_all:
            c.select(QTextCursor.SelectionType.Document)
        self.setTextCursor(c)

    def finish_edit(self):
        if not self.editing():
            return
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        c = self.textCursor()
        c.clearSelection()
        self.setTextCursor(c)
        txt = self.toPlainText().rstrip()
        self.setPlainText(txt)  # yapıştırılan zengin metni düz metne çevirir (renk temadan gelsin)
        self.apply_layout()
        before, new = self._before, self.is_new
        self._before, self.is_new = None, False
        if self.on_finished:
            self.on_finished(self, before or "", txt, new)

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        if e.reason() != Qt.FocusReason.PopupFocusReason:
            self.finish_edit()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape or (e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                                            and e.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.clearFocus()
            return
        super().keyPressEvent(e)

    def paint(self, p, opt, w=None):
        sel = _strip_state(opt)
        super().paint(p, opt, w)
        if self.editing():
            _draw_sel(p, self.boundingRect(), dashed=True)
        elif sel:
            _draw_sel(p, self.boundingRect())


class ImageItem(QGraphicsPixmapItem):
    """Görsel. Seçiliyken köşe tutamaçlarından orantılı büyütülüp küçültülür (Board.mousePressEvent)."""
    kind = "image"
    HANDLE = 12  # ekran pikseli

    def __init__(self, png: bytes, scale=1.0):
        super().__init__()
        self.png = png
        pm = QPixmap()
        pm.loadFromData(png)
        pm.setDevicePixelRatio(1.0)
        self.full = pm            # kırpılmamış özgün görüntü
        self.crop = None          # QRect (özgün piksel), None = kırpma yok
        self.setPixmap(pm)
        self.setTransformationMode(Qt.TransformationMode.SmoothTransformation)
        self.setShapeMode(QGraphicsPixmapItem.ShapeMode.BoundingRectShape)
        self.setFlags(FLAGS)
        self.setScale(scale)
        self.color_name = None
        self.orig = None          # rötuştan önceki özgün PNG (geri getir fırçası için; kayıtta "png0")
        self.checker = False      # rötuşta saydam yerler damalı görünsün

    def set_image(self, png: bytes):
        """Pikselleri değiştirir (aynı boyutta); kırpma ve yer korunur."""
        pm = QPixmap()
        pm.loadFromData(png)
        pm.setDevicePixelRatio(1.0)
        if pm.isNull():
            return
        self.png = png
        self.full = pm
        self.set_crop(self.crop)

    def set_work_image(self, img: QImage):
        """Rötuş sırasında: PNG'ye çevirmeden ekranda göster (kırpma kapalıyken)."""
        self.full = QPixmap.fromImage(img)
        self.setPixmap(self.full if self.crop is None else self.full.copy(self.crop))

    def full_image(self):
        return self.full.toImage()

    def orig_image(self):
        if self.orig:
            img = QImage()
            img.loadFromData(self.orig)
            if not img.isNull() and img.size() == self.full.size():
                return img
        img = QImage()
        img.loadFromData(self.png)
        return img

    @classmethod
    def from_qimage(cls, img: QImage, scale=1.0):
        return cls(image_png_bytes(img), scale)

    def full_rect(self):
        return QRect(0, 0, self.full.width(), self.full.height())

    def crop_rect(self):
        return QRect(self.crop) if self.crop is not None else self.full_rect()

    def set_crop(self, r):
        """Görüntüyü kırpar (yerini korumaz; bunun için set_crop_keep)."""
        fr = self.full_rect()
        r = fr if r is None else QRect(r).intersected(fr)
        if r.isEmpty() or r == fr:
            self.crop = None
            self.setPixmap(self.full)
        else:
            self.crop = QRect(r)
            self.setPixmap(self.full.copy(r))

    def apply_style(self):
        pass

    def paint(self, p, opt, w=None):
        sel = _strip_state(opt)
        if self.checker:
            p.save()
            p.setClipRect(self.boundingRect())
            tile = max(6.0, 9.0 / (p.worldTransform().m11() or 1.0))
            r = self.boundingRect()
            p.fillRect(r, QColor(200, 200, 200))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(150, 150, 150))
            y, row = r.top(), 0
            while y < r.bottom():
                x = r.left() + (tile if row % 2 else 0)
                while x < r.right():
                    p.drawRect(QRectF(x, y, tile, tile))
                    x += 2 * tile
                y += tile
                row += 1
            p.restore()
        super().paint(p, opt, w)
        if sel:
            r = self.boundingRect()
            _draw_sel(p, r, dashed=False)
            # dört köşe tutamacı (boyutlandırmayı Board yapar, her araçta çalışır)
            s = p.worldTransform().m11() or 1.0
            hs = self.HANDLE / s
            p.setBrush(QBrush(QColor("#ffffff")))
            pen = QPen(SEL_COLOR, 1.6)
            pen.setCosmetic(True)
            p.setPen(pen)
            # kareler görselin içinde kalır (sınır dışına çizmek iz bırakır)
            for x in (r.left(), r.right() - hs):
                for y in (r.top(), r.bottom() - hs):
                    p.drawRect(QRectF(x, y, hs, hs))


class CellEditor(QGraphicsTextItem):
    """Tablo hücresinde yazarken kullanılan geçici yazı kutusu (tablonun çocuğu)."""

    def __init__(self, table):
        super().__init__(table)
        self.table = table
        self.document().setDocumentMargin(0)
        self._quiet = False
        self.document().contentsChanged.connect(self._changed)

    def editing(self):
        return self.isVisible() and bool(self.textInteractionFlags() & Qt.TextInteractionFlag.TextEditorInteraction)

    def _changed(self):
        if not self._quiet:
            self.table._editor_changed()

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key.Key_Tab:
            self.table.move_edit(1)
            return
        if k == Qt.Key.Key_Backtab:
            self.table.move_edit(-1)
            return
        if k == Qt.Key.Key_Escape or (k in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                                      and e.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.clearFocus()
            return
        super().keyPressEvent(e)

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        if e.reason() != Qt.FocusReason.PopupFocusReason:
            self.table.finish_edit()

    def paint(self, p, opt, w=None):
        _strip_state(opt)
        super().paint(p, opt, w)


class TableItem(QGraphicsItem):
    """Tablo: satır × sütun hücreler; kenarlı (dış çerçeveli) ya da kenarsız (yalnızca iç çizgiler),
    isteğe bağlı başlık satırı.
    Hücreye çift tıkla yazılır, Tab sonraki hücreye geçer (son hücrede yeni satır açar).
    Satır yüksekliği yazıya göre kendiliğinden büyür; sütun genişliği çizgisinden sürüklenir."""
    kind = "table"
    PAD = 8
    MIN_COL = 40.0

    def __init__(self, rows=3, cols=3, color="auto", size=18, border=True, header=True, colw=None, cells=None):
        super().__init__()
        self.color_name = color
        self.size = float(size)
        self.border = bool(border)
        self.header = bool(header)
        self.family = ""
        rows, cols = max(1, int(rows)), max(1, int(cols))
        self.cells = [list(r) for r in cells] if cells else [[""] * cols for _ in range(rows)]
        n = max(len(r) for r in self.cells)
        for r in self.cells:
            r += [""] * (n - len(r))
        self.colw = [float(w) for w in colw] if colw and len(colw) == n else [self.default_colw()] * n
        self.rowh = []
        self._W = self._H = 0.0
        self.edit = None          # düzenlenen hücre (satır, sütun)
        self.editor = None
        self.on_changed = None    # fn(tablo, önceki durum, sonraki durum)
        self._before = None
        self.setFlags(FLAGS)
        self.relayout()

    # --- ölçüler
    def default_colw(self):
        return round(max(90.0, self.size * 7.5))

    @property
    def rows(self):
        return len(self.cells)

    @property
    def cols(self):
        return len(self.colw)

    def font(self, bold=False):
        f = fonts.font(self.family)
        f.setPixelSize(max(6, int(round(self.size))))
        f.setWeight(QFont.Weight.Bold if bold else (QFont.Weight.Medium if not self.family else QFont.Weight.Normal))
        return f

    def _flags(self):
        return int(Qt.TextFlag.TextWordWrap.value | Qt.AlignmentFlag.AlignLeft.value | Qt.AlignmentFlag.AlignTop.value)

    def relayout(self):
        self.prepareGeometryChange()
        fms = (QFontMetricsF(self.font(False)), QFontMetricsF(self.font(True)))
        minh = fms[0].height() + 2 * self.PAD
        self.rowh = []
        for r, row in enumerate(self.cells):
            fm = fms[1 if (self.header and r == 0) else 0]
            h = minh
            for c, txt in enumerate(row):
                w = max(4.0, self.colw[c] - 2 * self.PAD)
                if self.edit == (r, c) and self.editor is not None:
                    th = self.editor.boundingRect().height()
                elif txt:
                    th = fm.boundingRect(QRectF(0, 0, w, 1e6), self._flags(), txt).height()
                else:
                    th = 0
                h = max(h, th + 2 * self.PAD)
            self.rowh.append(h)
        self._W, self._H = sum(self.colw), sum(self.rowh)
        if self.editor is not None and self.edit is not None:
            self._place_editor()
        self.update()

    def table_rect(self):
        return QRectF(0, 0, self._W, self._H)

    def boundingRect(self):
        return self.table_rect().adjusted(-3, -3, 3, 3)

    def shape(self):
        path = QPainterPath()
        path.addRect(self.table_rect())
        return path

    def col_x(self, c):
        return sum(self.colw[:c])

    def row_y(self, r):
        return sum(self.rowh[:r])

    def cell_rect(self, r, c):
        return QRectF(self.col_x(c), self.row_y(r), self.colw[c], self.rowh[r])

    def cell_at(self, lp):
        if not self.table_rect().contains(lp):
            return None
        r = c = 0
        y = 0.0
        for i, h in enumerate(self.rowh):
            if lp.y() < y + h:
                r = i
                break
            y += h
        else:
            r = self.rows - 1
        x = 0.0
        for i, w in enumerate(self.colw):
            if lp.x() < x + w:
                c = i
                break
            x += w
        else:
            c = self.cols - 1
        return r, c

    def col_border_at(self, lp, tol):
        """Sütun sağ kenarına yakınsa sütun numarası (genişlik sürüklemek için)."""
        if lp.y() < -tol or lp.y() > self._H + tol:
            return None
        x = 0.0
        for i, w in enumerate(self.colw):
            x += w
            if abs(lp.x() - x) <= tol:
                return i
        return None

    def set_col_width(self, c, w):
        self.colw[c] = max(self.MIN_COL, float(w))
        self.relayout()

    # --- durum (geri al için)
    def state(self):
        return {"cells": copy.deepcopy(self.cells), "colw": list(self.colw), "size": self.size,
                "header": self.header, "border": self.border}

    def set_state(self, st):
        self.cells = copy.deepcopy(st["cells"])
        self.colw = list(st["colw"])
        self.size, self.header, self.border = st["size"], st["header"], st["border"]
        if self.edit is not None and (self.edit[0] >= self.rows or self.edit[1] >= self.cols):
            self.edit = None
            if self.editor is not None:
                self.editor.hide()
        self.relayout()

    # --- satır / sütun
    def insert_row(self, at):
        at = max(0, min(at, self.rows))
        self.cells.insert(at, [""] * self.cols)
        self.relayout()

    def insert_col(self, at):
        at = max(0, min(at, self.cols))
        for row in self.cells:
            row.insert(at, "")
        self.colw.insert(at, self.default_colw())
        self.relayout()

    def delete_row(self, r):
        if self.rows > 1:
            del self.cells[r]
            self.relayout()

    def delete_col(self, c):
        if self.cols > 1:
            for row in self.cells:
                del row[c]
            del self.colw[c]
            self.relayout()

    # --- hücre düzenleme
    def editing(self):
        return self.editor is not None and self.editor.editing()

    def _place_editor(self):
        r, c = self.edit
        ed = self.editor
        ed.setTextWidth(max(4.0, self.colw[c] - 2 * self.PAD))
        ed.setPos(self.cell_rect(r, c).topLeft() + QPointF(self.PAD, self.PAD))

    def start_edit(self, r, c, select_all=False):
        if self._before is None:
            self._before = self.state()
        if self.editor is None:
            self.editor = CellEditor(self)
        ed = self.editor
        self.edit = (r, c)
        ed._quiet = True
        ed.setFont(self.font(self.header and r == 0))
        ed.setDefaultTextColor(ink(self.color_name))
        ed.setPlainText(self.cells[r][c])
        ed._quiet = False
        ed.show()
        ed.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.relayout()
        ed.setFocus(Qt.FocusReason.MouseFocusReason)
        cur = ed.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        if select_all:
            cur.select(QTextCursor.SelectionType.Document)
        ed.setTextCursor(cur)

    def _editor_changed(self):
        if self.edit is None:
            return
        r, c = self.edit
        self.cells[r][c] = self.editor.toPlainText()
        self.relayout()

    def move_edit(self, step):
        if self.edit is None:
            return
        r, c = self.edit
        i = r * self.cols + c + step
        if i >= self.rows * self.cols:
            self.insert_row(self.rows)          # son hücrede Tab: yeni satır
        i = max(0, i)
        self.start_edit(i // self.cols, i % self.cols)

    def finish_edit(self):
        if self.edit is None:
            return
        ed = self.editor
        if ed is not None and ed.hasFocus():
            return          # odak yine hücrede (Tab ile geçiş)
        r, c = self.edit
        if r < self.rows and c < self.cols:
            self.cells[r][c] = self.cells[r][c].rstrip()
        self.edit = None
        if ed is not None:
            ed.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            ed.hide()
        self.relayout()
        before, self._before = self._before, None
        after = self.state()
        if before is not None and before != after and self.on_changed:
            self.on_changed(self, before, after)

    def apply_style(self):
        if self.editor is not None:
            self.editor.setDefaultTextColor(ink(self.color_name))
        self.update()

    # --- çizim
    def paint(self, p, opt, w=None):
        sel = _strip_state(opt)
        R = self.table_rect()
        col = ink(self.color_name)
        p.save()
        p.setClipRect(R)
        if self.header and self.rows:
            hc = QColor(col)
            hc.setAlpha(38)
            p.fillRect(QRectF(0, 0, self._W, self.rowh[0]), hc)
        lc = QColor(col)
        lc.setAlpha(110)
        p.setPen(QPen(lc, 1.2))
        x = 0.0
        for wd in self.colw[:-1]:
            x += wd
            p.drawLine(QPointF(x, 0), QPointF(x, self._H))
        y = 0.0
        for h in self.rowh[:-1]:
            y += h
            p.drawLine(QPointF(0, y), QPointF(self._W, y))
        p.restore()
        if self.border:
            oc = QColor(col)
            oc.setAlpha(200)
            p.setPen(QPen(oc, 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(R)
        p.setPen(col)
        y = 0.0
        for r, row in enumerate(self.cells):
            p.setFont(self.font(self.header and r == 0))
            x = 0.0
            for c, txt in enumerate(row):
                if txt and self.edit != (r, c):
                    p.drawText(QRectF(x + self.PAD, y + self.PAD, self.colw[c] - 2 * self.PAD,
                                      self.rowh[r] - 2 * self.PAD), self._flags(), txt)
                x += self.colw[c]
            y += self.rowh[r]
        if self.edit is not None:
            pen = QPen(SEL_COLOR, 1.6)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.drawRect(self.cell_rect(*self.edit).adjusted(1, 1, -1, -1))
        if sel:
            _draw_sel(p, R.adjusted(-2, -2, 2, 2))


class LaserItem(QGraphicsItem):
    """Lazer işaretçi: arkasında ~0.8 sn'de kaybolan kırmızı iz bırakır. Kaydedilmez, geri alınmaz."""
    kind = "laser"
    LIFE = 0.8

    def __init__(self):
        super().__init__()
        self.pts = []  # (QPointF, zaman)
        self._rect = QRectF()
        self.active = True
        self.setZValue(9e12)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def add(self, p):
        self.prepareGeometryChange()
        self.pts.append((p, time.monotonic()))
        self._calc()

    def _calc(self):
        if not self.pts:
            self._rect = QRectF()
            return
        xs = [q.x() for q, _ in self.pts]
        ys = [q.y() for q, _ in self.pts]
        m = 80
        self._rect = QRectF(min(xs) - m, min(ys) - m, max(xs) - min(xs) + 2 * m, max(ys) - min(ys) + 2 * m)

    def tick(self, now):
        cut = now - self.LIFE
        if self.pts and self.pts[0][1] < cut:
            self.prepareGeometryChange()
            keep = [x for x in self.pts if x[1] >= cut]
            # Fare basılı ve hareketsizken son nokta (imleç ucu) kalsın
            if not keep and self.active:
                keep = [self.pts[-1]]
            self.pts = keep
            self._calc()
        self.update()
        return bool(self.pts) or self.active

    def boundingRect(self):
        return self._rect

    def paint(self, p, opt, w=None):
        n = len(self.pts)
        if not n:
            return
        now = time.monotonic()
        p.setRenderHint(p.RenderHint.Antialiasing)
        scale = p.worldTransform().m11() or 1.0
        for width, alpha in ((14, 55), (5, 255)):
            for i in range(1, n):
                (a, _), (b, tb) = self.pts[i - 1], self.pts[i]
                k = max(0.0, min(1.0, 1 - (now - tb) / self.LIFE))
                if k <= 0:
                    continue
                pen = QPen(QColor(255, 45, 45, int(alpha * k)), width * (0.55 + 0.45 * k))
                pen.setCosmetic(True)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.drawLine(a, b)
        if self.active:
            tip = self.pts[-1][0]
            r = 6 / scale
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 45, 45, 70))
            p.drawEllipse(tip, r * 2.2, r * 2.2)
            p.setBrush(QColor(255, 60, 60))
            p.drawEllipse(tip, r, r)


class FormulaItem(QGraphicsItem):
    """Formül: LaTeX kaynağı (src) kendi dizgi motorumuzla (mathtex) çizilir. Çift tık / sağ tık düzenler
    (formül paneli: canlı önizleme + sembol paleti). Kayıt: "src", "s" (yazı boyutu), "c"."""
    kind = "formula"

    def __init__(self, src="", color="auto", size=32):
        super().__init__()
        self.src = src
        self.color_name = color
        self.size = float(size)
        self.editing = False      # düzenlerken boş yuvalar kesik kare
        self._box = None
        self._rect = QRectF()
        self.setFlags(FLAGS)
        self.relayout()

    def relayout(self):
        from . import mathtex
        self.prepareGeometryChange()
        self._box = mathtex.layout_src(self.src, self.size, edit=self.editing)
        self._rect = mathtex.bounds(self._box, self.size).translated(0, self._box.a)

    def formula_rect(self):
        b = self._box
        return QRectF(0, 0, max(b.w, 1.0), max(b.a + b.d, 1.0))

    def boundingRect(self):
        return self._rect

    def apply_style(self):
        self.update()

    def paint(self, p, opt, w=None):
        sel = _strip_state(opt)
        p.setRenderHint(p.RenderHint.Antialiasing)
        p.setRenderHint(p.RenderHint.TextAntialiasing)
        self._box.draw(p, 0.0, self._box.a, ink(self.color_name))
        if sel or self.editing:
            _draw_sel(p, self._rect, dashed=not self.editing)


def formula_state(it):
    return (it.src, it.size)


def set_formula_state(it, st):
    it.src, it.size = st[0], float(st[1])
    it.relayout()


CONTENT = (StrokeItem, TextItem, ImageItem, TableItem, FormulaItem)


def body_rect(it):
    """Nesnenin yerel (kendi koordinatındaki) gövde kutusu: kenar payları olmadan."""
    if isinstance(it, ImageItem):
        return QRectF(it.offset(), it.pixmap().size().toSizeF())
    if isinstance(it, TableItem):
        return it.table_rect()
    if isinstance(it, FormulaItem):
        return it.formula_rect()
    return it.boundingRect()


def set_table_size(it, v):
    it.size = float(v)
    it.relayout()


def set_var(it, v):
    """Mühendislik şeklinin seçeneği (NACA kodu …)."""
    it.var = v or None
    it.rebuild()


def set_brush(it, b):
    from . import brushes
    it.prepareGeometryChange()
    it.brush = b if b in brushes.NAMES else "pen"
    it._bc = None
    it.update()


def bend_point(it):
    """Bükme tutamacının yerel konumu: bükülmüşse eğrinin ortası, değilse çizginin ortası."""
    if it.bend is not None:
        return QPointF(it.bend)
    a, b = it.pts[0], it.pts[-1]
    return QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2)


def set_bend(it, lp):
    a, b = it.pts[0], it.pts[-1]
    mid = QPointF((a.x() + b.x()) / 2, (a.y() + b.y()) / 2)
    straight = lp is None or math.hypot(lp.x() - mid.x(), lp.y() - mid.y()) < max(3.0, it.width)
    it.bend = None if straight else QPointF(lp)
    it.rebuild()


def bend_state(it):
    return tuple(QPointF(p) for p in it.pts), (QPointF(it.bend) if it.bend is not None else None)


def set_bend_state(it, st):
    it.pts = [QPointF(p) for p in st[0]]
    it.bend = QPointF(st[1]) if st[1] is not None else None
    it.rebuild()


def _seg_dist(p, a, b):
    dx, dy = b.x() - a.x(), b.y() - a.y()
    L = dx * dx + dy * dy
    k = 0.0 if L < 1e-12 else max(0.0, min(1.0, ((p.x() - a.x()) * dx + (p.y() - a.y()) * dy) / L))
    return math.hypot(p.x() - (a.x() + dx * k), p.y() - (a.y() + dy * k))


def cut_stroke(it, a, b, r):
    """Parça silgisi: silginin (sahnede a→b, yarıçap r) geçtiği yeri çizgiden çıkarır.
    Kalan parçalar yeni StrokeItem'lar olarak döner (kalem / fosforlu, aynı renk, kalınlık, tür, konum);
    hiç kesilmediyse None. Şekiller (dikdörtgen, ok …) kesilince serbest çizgiye dönüşür."""
    la, lb = it.mapFromScene(a), it.mapFromScene(b)
    lr = r / max(abs(it.scale()), 1e-6) + it.width / 2
    step = max(0.5, min(lr / 3, 4.0))
    runs, cut = [], False
    for pg in it.path().toSubpathPolygons():
        pl = list(pg)
        if not pl:
            continue
        dense = [pl[0]]
        for p0, p1 in zip(pl, pl[1:]):
            d = math.hypot(p1.x() - p0.x(), p1.y() - p0.y())
            n = max(1, int(d / step))
            for i in range(1, n + 1):
                dense.append(QPointF(p0.x() + (p1.x() - p0.x()) * i / n, p0.y() + (p1.y() - p0.y()) * i / n))
        gone = [_seg_dist(p, la, lb) < lr for p in dense]
        if not any(gone):
            runs.append(dense)
            continue
        cut = True
        closed = len(dense) > 2 and math.hypot(dense[0].x() - dense[-1].x(), dense[0].y() - dense[-1].y()) < 0.5
        if closed:      # kapalı şekil: kesilen yerden başlat ki iki uç birleşsin
            k = gone.index(True)
            dense, gone = dense[k:] + dense[1:k + 1], gone[k:] + gone[1:k + 1]
        cur = []
        for p, g in zip(dense, gone):
            if g:
                if len(cur) >= 2:
                    runs.append(cur)
                cur = []
            else:
                cur.append(p)
        if len(cur) >= 2:
            runs.append(cur)
    if not cut:
        return None
    kind = "hl" if it.kind == "hl" else "pen"
    out = []
    for run in runs:
        pc = StrokeItem(kind, it.color_name, it.width, simplify(run, 0.2))
        pc.dash = it.dash
        if kind == "pen":
            pc.brush = it.brush if it.kind == "pen" else "pen"
        pc.apply_style()
        pc.rebuild(smooth=True)
        pc.setZValue(it.zValue())
        set_geo_state(pc, geo_state(it))
        pc.setOpacity(it.opacity())
        if group_of(it):
            set_group(pc, group_of(it))
        out.append(pc)
    return out


def stroke_dash(it):
    return getattr(it, "dash", "solid")


def set_dash(it, d):
    it.dash = d if d in DASHES else "solid"
    it.apply_style()
    it.update()


def font_family(it):
    return getattr(it, "family", "")


def set_font_family(it, fam):
    it.family = fam or ""
    if isinstance(it, TableItem):
        it.relayout()
        if it.editor is not None and it.edit is not None:
            it.editor.setFont(it.font(it.header and it.edit[0] == 0))
    else:
        it.apply_font()


# ---------------------------------------------------------------- katman özellikleri (grup / kilit / gizli)

def group_of(it):
    return getattr(it, "group_id", None)   # "group" olmaz: QGraphicsItem.group() yöntemiyle çakışır


def is_locked(it):
    return bool(getattr(it, "locked", False))


def set_group(it, gid):
    it.group_id = gid or None


def set_locked(it, on):
    """Kilitli nesne seçilmez, taşınmaz, silgiyle silinmez (katmanlar panelinden ya da sağ tıkla açılır)."""
    it.locked = bool(on)
    it.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, not on)
    it.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, not on)
    # kilitli nesne fareyi almaz: üstünden lastik bantla seçim yapılabilsin
    it.setAcceptedMouseButtons(Qt.MouseButton.NoButton if on else Qt.MouseButton.AllButtons)
    if on:
        it.setSelected(False)


def set_hidden(it, on):
    it.setVisible(not on)
    if on:
        it.setSelected(False)


def exact_rect(it):
    """Sahnedeki gerçek kutu (görselde boundingRect'in +0,5 payı olmadan)."""
    if isinstance(it, (ImageItem, TableItem)):
        return it.mapRectToScene(body_rect(it))
    return it.sceneBoundingRect()


def _layer_extras(it, d):
    if group_of(it):
        d["g"] = group_of(it)
    if is_locked(it):
        d["lk"] = 1
    if not it.isVisible():
        d["hd"] = 1
    rot, fh, fv = geom(it)
    if rot or fh or fv:
        c = getattr(it, "geo_c", None) or local_center(it)
        d["r"], d["gc"] = round(rot, 3), [round(c.x(), 3), round(c.y(), 3)]
        if fh:
            d["fh"] = 1
        if fv:
            d["fv"] = 1
    if it.opacity() < 0.999:
        d["op"] = round(it.opacity(), 3)
    return d


# ---------------------------------------------------------------- döndür / çevir
# Döndürme ve çevirme nesnenin kendi transform()'unda, yerel merkez (geo_c) etrafında tutulur; ölçek (setScale)
# eskisi gibi sol üst köşeden işler, böylece boyutlandırma / dizme kodu değişmeden çalışır.

def local_center(it):
    return body_rect(it).center()


def build_transform(rot, fh, fv, c):
    if not rot and not fh and not fv:
        return QTransform()
    t = QTransform()
    t.translate(c.x(), c.y())
    t.rotate(rot)
    t.scale(-1.0 if fh else 1.0, -1.0 if fv else 1.0)
    t.translate(-c.x(), -c.y())
    return t


def geom(it):
    return float(getattr(it, "rot", 0.0)), bool(getattr(it, "fh", False)), bool(getattr(it, "fv", False))


def geo_state(it):
    c = getattr(it, "geo_c", None)
    rot, fh, fv = geom(it)
    return QPointF(it.pos()), it.scale(), rot, fh, fv, (QPointF(c) if c is not None else None)


def set_geo_state(it, st):
    pos, sc, rot, fh, fv, c = st
    it.rot, it.fh, it.fv = rot, fh, fv
    it.geo_c = QPointF(c) if c is not None else None
    it.setTransform(build_transform(rot, fh, fv, c) if c is not None else QTransform())
    it.setScale(sc)
    it.setPos(pos)


def set_geom(it, rot, fh, fv):
    """Döndür / çevir: nesnenin görünen merkezi yerinde kalır."""
    lc = local_center(it)
    before = it.mapToScene(lc)
    rot = round(rot % 360.0, 4) % 360.0
    ident = not rot and not fh and not fv
    it.rot, it.fh, it.fv = rot, fh, fv
    it.geo_c = None if ident else QPointF(lc)
    it.setTransform(QTransform() if ident else build_transform(rot, fh, fv, lc))
    it.setPos(it.pos() + (before - it.mapToScene(lc)))


def set_crop_keep(it, r):
    """Kırpma alanını değiştirir; görüntünün içeriği sahnede yerinde kalır (döndürülmüş olsa da)."""
    old = it.crop_rect()
    r = QRect(r).intersected(it.full_rect())
    if r.isEmpty():
        return
    ref = it.mapToScene(QPointF(r.x() - old.x(), r.y() - old.y()))
    it.set_crop(r)
    rot, fh, fv = geom(it)
    if rot or fh or fv:
        c = local_center(it)
        it.geo_c = QPointF(c)
        it.setTransform(build_transform(rot, fh, fv, c))
    it.setPos(it.pos() + (ref - it.mapToScene(QPointF(0, 0))))


def pixel_state(it):
    return it.png, it.orig


def set_pixel_state(it, st):
    it.set_image(st[0])
    it.orig = st[1]


def crop_state(it):
    return QRect(it.crop_rect()), geo_state(it)


def set_crop_state(it, st):
    r, g = st
    it.set_crop(r)
    set_geo_state(it, g)


def set_opacity(it, v):
    it.setOpacity(max(0.05, min(1.0, float(v))))


def set_fill(it, c):
    it.fill = c or None
    it.apply_style()
    it.update()


def text_style(it):
    return it.size, it.bold, it.italic, it.underline, it.align


def set_text_style(it, st):
    it.size, it.bold, it.italic, it.underline, it.align = st
    it.apply_font()


# ---------------------------------------------------------------- dönüştürme

def image_png_bytes(img: QImage) -> bytes:
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return bytes(ba)


def to_dict(it):
    pos = [round(it.pos().x(), 2), round(it.pos().y(), 2)]
    z = it.zValue()
    if isinstance(it, StrokeItem):
        d = {"t": "stroke", "k": it.kind, "c": it.color_name, "w": it.width, "pos": pos, "z": z,
             "p": [round(v, 2) for q in it.pts for v in (q.x(), q.y())]}
        if it.fill:
            d["f"] = it.fill
        if it.dash != "solid":
            d["ds"] = it.dash
        if it.kind == "pen" and it.brush != "pen":
            d["br"] = it.brush
        if it.var:
            d["v"] = it.var
        if it.bend is not None:
            d["bd"] = [round(it.bend.x(), 2), round(it.bend.y(), 2)]
        return _layer_extras(it, d)
    if isinstance(it, TextItem):
        d = {"t": "text", "c": it.color_name, "s": it.size, "txt": it.toPlainText(), "pos": pos, "z": z}
        if it.bold:
            d["b"] = 1
        if it.italic:
            d["it"] = 1
        if it.underline:
            d["u"] = 1
        if it.align != "left":
            d["al"] = it.align
        if it.family:
            d["ff"] = it.family
        if it.link:
            d["ln"] = dict(it.link)
        return _layer_extras(it, d)
    if isinstance(it, ImageItem):
        d = {"t": "image", "sc": it.scale(), "pos": pos, "z": z, "png": base64.b64encode(it.png).decode("ascii")}
        if it.orig and it.orig != it.png:
            d["png0"] = base64.b64encode(it.orig).decode("ascii")
        if it.crop is not None:
            r = it.crop
            d["cr"] = [r.x(), r.y(), r.width(), r.height()]
        return _layer_extras(it, d)
    if isinstance(it, FormulaItem):
        d = {"t": "formula", "src": it.src, "s": it.size, "c": it.color_name, "pos": pos, "z": z}
        return _layer_extras(it, d)
    if isinstance(it, TableItem):
        d = {"t": "table", "c": it.color_name, "s": it.size, "pos": pos, "z": z, "cells": copy.deepcopy(it.cells),
             "cw": [round(w, 2) for w in it.colw]}
        if not it.border:
            d["nb"] = 1
        if not it.header:
            d["nh"] = 1
        if it.family:
            d["ff"] = it.family
        return _layer_extras(it, d)
    return None


def from_dict(d):
    try:
        t = d.get("t")
        if t == "stroke":
            p = d.get("p") or []
            pts = [QPointF(p[i], p[i + 1]) for i in range(0, len(p) - 1, 2)]
            it = StrokeItem(d.get("k", "pen"), d.get("c", "auto"), d.get("w", 4), pts)
            if d.get("f"):
                set_fill(it, d["f"])
            if d.get("ds") in DASHES:
                set_dash(it, d["ds"])
            if d.get("br"):
                set_brush(it, str(d["br"]))
            if d.get("v") and it.kind in engshapes.KINDS:
                set_var(it, str(d["v"]))
            if d.get("bd") and it.kind in ("line", "arrow"):
                it.bend = QPointF(float(d["bd"][0]), float(d["bd"][1]))
                it.rebuild()
        elif t == "text":
            it = TextItem(d.get("txt", ""), d.get("c", "auto"), d.get("s", 26))
            if d.get("b") or d.get("it") or d.get("u") or d.get("al"):
                set_text_style(it, (it.size, bool(d.get("b")), bool(d.get("it")), bool(d.get("u")),
                                    d.get("al", "left") if d.get("al") in TEXT_ALIGN else "left"))
            from . import kamuglink
            if kamuglink.valid(d.get("ln")):
                it.link = kamuglink.make_link(kamuglink.video_of(d["ln"]), d["ln"].get("t"))
                from .i18n import t as tr_
                it.setToolTip(tr_("kamug_link_tip", time=kamuglink.fmt(it.link["t"])))
        elif t == "formula":
            it = FormulaItem(str(d.get("src", "")), d.get("c", "auto"), float(d.get("s", 32)))
        elif t == "image":
            it = ImageItem(base64.b64decode(d.get("png", "")), float(d.get("sc", 1.0)))
            if it.pixmap().isNull():
                return None
            if d.get("png0"):
                it.orig = base64.b64decode(d["png0"])
            if d.get("cr"):
                it.set_crop(QRect(*[int(v) for v in d["cr"]]))
        elif t == "table":
            cells = [[str(x) for x in row] for row in (d.get("cells") or [[""]])] or [[""]]
            it = TableItem(len(cells), max(len(r) for r in cells), d.get("c", "auto"), d.get("s", 18),
                           not d.get("nb"), not d.get("nh"), d.get("cw"), cells)
        else:
            return None
        if d.get("ff") and t in ("text", "table"):
            set_font_family(it, str(d["ff"]))
        pos = d.get("pos") or [0, 0]
        it.setPos(QPointF(pos[0], pos[1]))
        it.setZValue(float(d.get("z", 0)))
        if d.get("r") or d.get("fh") or d.get("fv"):
            gc = d.get("gc")
            c = QPointF(gc[0], gc[1]) if gc else local_center(it)
            set_geo_state(it, (it.pos(), it.scale(), float(d.get("r", 0)), bool(d.get("fh")), bool(d.get("fv")), c))
        if d.get("op"):
            set_opacity(it, d["op"])
        if d.get("g"):
            set_group(it, str(d["g"]))
        if d.get("lk"):
            set_locked(it, True)
        if d.get("hd"):
            set_hidden(it, True)
        return it
    except Exception:
        return None
