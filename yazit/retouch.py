"""Görsel rötuşu: arka planı otomatik sil, sihirli değnek / kement ile piksel seç, seçileni sil,
silgi ve geri getir fırçasıyla ince düzelt. Board._retouch bu oturumu tutar; fare / klavye / çizim buraya gelir.
Oturum boyunca değişiklikler kendi geri al yığınında; bitince tek bir geri al adımı (AttrCmd, pixel_state) olur."""
from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QPainter, QPainterPath, QPen, QColor, QPolygonF, QPainterPathStroker
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QSlider, QLabel, QVBoxLayout

from . import items as I
from . import pixels as P
from .config import prefs
from .i18n import t
from .theme import qcolor
from .widgets import IconButton

TOOLS = ("wand", "lasso", "erase", "restore")


class Retouch:
    def __init__(self, board, it):
        self.board, self.it = board, it
        self.before_px = I.pixel_state(it)
        self.before_crop = I.crop_state(it)
        I.set_crop_keep(it, it.full_rect())        # rötuşta görüntünün tamamı
        self.img = P.argb(it.full_image())
        self.orig = P.argb(it.orig_image())
        self.mask = None
        self._ov = None
        self.hist = []
        self.tool = prefs.get("rt_tool", "wand") if prefs.get("rt_tool", "wand") in TOOLS else "wand"
        self.tol = int(prefs.get("rt_tol", 40) or 40)
        self.size = int(prefs.get("rt_size", 28) or 28)
        self.lasso = None
        self.last = None
        self.changed = False
        it.checker = True
        it.update()

    # ------------------------------------------------------------ yardımcılar
    def img_pt(self, sp):
        return self.it.mapFromScene(sp) - self.it.offset()

    def wh(self):
        return self.img.width(), self.img.height()

    def _push(self):
        self.hist.append((self.img, self.mask))
        del self.hist[:-25]

    def _show(self):
        self.it.set_work_image(self.img)
        self.board.viewport().update()

    def _set_mask(self, m):
        self.mask = m if m is not None and P.count(m) else None
        self._ov = None
        self.board.viewport().update()
        self.board.retouch_bar.sync()

    def undo(self):
        if not self.hist:
            return False
        self.img, mask = self.hist.pop()
        self._set_mask(mask)
        self._show()
        return True

    def set_tool(self, tl):
        if tl in TOOLS:
            self.tool = tl
            prefs.set("rt_tool", tl)
            self.board._update_cursor()
            self.board.retouch_bar.sync()

    # ------------------------------------------------------------ işlemler
    def auto_bg(self):
        m = P.background(self.img, self.tol)
        if not P.count(m):
            self.board.toast(t("rt_no_bg"), 2200)
            return
        self._push()
        self.img = P.clear(self.img, m)
        self.changed = True
        self._set_mask(None)
        self._show()

    def delete_sel(self):
        if self.mask is None:
            return
        self._push()
        self.img = P.clear(self.img, self.mask)
        self.changed = True
        self._set_mask(None)
        self._show()

    def invert_sel(self):
        w, h = self.wh()
        self._set_mask(P.invert(self.mask) if self.mask is not None else bytes([1]) * (w * h))

    def clear_sel(self):
        self._set_mask(None)

    def _how(self, mods):
        if mods & Qt.KeyboardModifier.ShiftModifier:
            return "add"
        if mods & (Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.ControlModifier):
            return "sub"
        return "new"

    def brush_px(self):
        """Ekran pikselindeki fırça çapı → görüntü pikseli."""
        k = max(self.board.zoom() * abs(self.it.scale()), 1e-6)
        return max(1.0, self.size / k)

    def _paint_brush(self, a, b):
        pen_w = self.brush_px()
        p = QPainter(self.img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.tool == "erase":
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            p.setPen(QPen(QColor(0, 0, 0, 255), pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.drawLine(a, b + QPointF(0.01, 0))
        else:      # geri getir: özgün görüntüden fırçanın altını kopyala
            path = QPainterPath(a)
            path.lineTo(b + QPointF(0.01, 0))
            st = QPainterPathStroker()
            st.setWidth(pen_w)
            st.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setClipPath(st.createStroke(path))
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            p.drawImage(0, 0, self.orig)
        p.end()
        self.changed = True
        self._show()

    # ------------------------------------------------------------ fare
    def press(self, pos, sp, mods):
        ip = self.img_pt(sp)
        w, h = self.wh()
        if self.tool == "wand":
            x, y = int(ip.x()), int(ip.y())
            if not (0 <= x < w and 0 <= y < h):
                if self._how(mods) == "new":
                    self._set_mask(None)
                return
            self._set_mask(P.combine(self.mask, P.wand(self.img, x, y, self.tol), self._how(mods)))
        elif self.tool == "lasso":
            self.lasso = ([ip], self._how(mods))
        else:
            self._push()
            self.last = ip
            self._paint_brush(ip, ip)

    def move(self, pos, sp):
        ip = self.img_pt(sp)
        if self.lasso is not None:
            pts = self.lasso[0]
            if (ip - pts[-1]).manhattanLength() * self.board.zoom() * abs(self.it.scale()) >= 2:
                pts.append(ip)
                self.board.viewport().update()
        elif self.last is not None:
            self._paint_brush(self.last, ip)
            self.last = ip

    def release(self):
        if self.lasso is not None:
            pts, how = self.lasso
            self.lasso = None
            if len(pts) >= 3:
                w, h = self.wh()
                self._set_mask(P.combine(self.mask, P.polygon_mask(QPolygonF(pts), w, h), how))
            self.board.viewport().update()
        self.last = None

    def key(self, e):
        k = e.key()
        ctrl = bool(e.modifiers() & Qt.KeyboardModifier.ControlModifier)
        K = Qt.Key
        if k in (K.Key_Delete, K.Key_Backspace):
            self.delete_sel()
        elif k in (K.Key_Return, K.Key_Enter):
            self.board.end_retouch(True)
        elif k == K.Key_Escape:
            if self.mask is not None:
                self.clear_sel()
            else:
                self.board.end_retouch(True)
        elif ctrl and k == K.Key_Z:
            self.undo()
        elif ctrl and k == K.Key_I:
            self.invert_sel()
        elif ctrl and k == K.Key_D:
            self.clear_sel()
        elif ctrl and k == K.Key_A:
            self.invert_sel() if self.mask is None else self._set_mask(bytes([1]) * (self.wh()[0] * self.wh()[1]))
        elif not ctrl and e.text() in ("w", "l", "e", "r"):
            self.set_tool({"w": "wand", "l": "lasso", "e": "erase", "r": "restore"}[e.text()])

    # ------------------------------------------------------------ çizim (drawForeground, sahne koordinatı)
    def draw(self, p, z):
        it = self.it
        p.save()
        p.setWorldTransform(it.sceneTransform(), True)
        p.translate(it.offset())
        if self.mask is not None:
            if self._ov is None:
                w, h = self.wh()
                self._ov = P.overlay(self.mask, w, h)
            p.drawImage(0, 0, self._ov)
        if self.lasso is not None and len(self.lasso[0]) > 1:
            pen = QPen(QColor("#3ea6ff"), 1.6)
            pen.setCosmetic(True)
            p.setPen(pen)
            p.drawPolyline(QPolygonF(self.lasso[0]))
        pen = QPen(QColor(255, 255, 255, 160), 1.2, Qt.PenStyle.DashLine)
        pen.setCosmetic(True)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(0, 0, *self.wh()))
        p.restore()

    # ------------------------------------------------------------ bitir
    def finish(self, apply):
        it = self.it
        it.checker = False
        if apply and self.changed:
            png = I.image_png_bytes(self.img)
            after = (png, self.before_px[1] or self.before_px[0])
            I.set_pixel_state(it, after)
            I.set_crop_keep(it, self.before_crop[0])
            return after
        I.set_pixel_state(it, self.before_px)
        I.set_crop_keep(it, self.before_crop[0])
        it.update()
        return None


class _Slider(QWidget):
    def __init__(self, title, lo, hi, val, fn, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 0, 4, 0)
        lay.setSpacing(0)
        self.lab = QLabel()
        self.lab.setObjectName("Muted")
        self.title = title
        self.s = QSlider(Qt.Orientation.Horizontal)
        self.s.setRange(lo, hi)
        self.s.setValue(val)
        self.s.setFixedWidth(96)
        self.s.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.s.valueChanged.connect(lambda v: (fn(v), self._lab(v)))
        lay.addWidget(self.lab)
        lay.addWidget(self.s)
        self._lab(val)

    def _lab(self, v):
        self.lab.setText(f"{self.title}  {v}")


class RetouchBar(QWidget):
    """Rötuşta görünümün üstünde duran çubuk: araçlar, tolerans, fırça boyu, seçim işlemleri, bitti / iptal."""

    def __init__(self, board):
        super().__init__(board)
        self.board = board
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 4, 8, 4)
        lay.setSpacing(2)

        def btn(name, tip, fn, check=False):
            b = IconButton(name, tip, 36, 20, parent=self, checkable=check, obj="ToolBtn")
            b.clicked.connect(fn)
            lay.addWidget(b)
            return b

        def sess():
            return board._retouch
        self.b_auto = btn("bg_remove", t("rt_auto"), lambda: sess() and sess().auto_bg())
        lay.addSpacing(6)
        self.tools = {}
        for tl, ic in (("wand", "wand"), ("lasso", "lasso"), ("erase", "eraser"), ("restore", "restore")):
            self.tools[tl] = btn(ic, t("rt_" + tl), lambda _=False, x=tl: sess() and sess().set_tool(x), True)
        lay.addSpacing(6)
        self.tol = _Slider(t("rt_tol"), 0, 160, int(prefs.get("rt_tol", 40) or 40), self._tol, self)
        lay.addWidget(self.tol)
        self.size = _Slider(t("rt_size"), 2, 160, int(prefs.get("rt_size", 28) or 28), self._size, self)
        lay.addWidget(self.size)
        lay.addSpacing(6)
        self.b_del = btn("delete", t("rt_delete") + " (Delete)", lambda: sess() and sess().delete_sel())
        self.b_inv = btn("sel_invert", t("rt_invert") + " (Ctrl+I)", lambda: sess() and sess().invert_sel())
        self.b_none = btn("sel_none", t("rt_none") + " (Esc)", lambda: sess() and sess().clear_sel())
        self.b_undo = btn("undo", t("undo") + " (Ctrl+Z)", lambda: sess() and sess().undo())
        lay.addSpacing(6)
        self.b_cancel = btn("close", t("rt_cancel"), lambda: board.end_retouch(False))
        self.b_done = btn("check", t("rt_done") + " (Enter)", lambda: board.end_retouch(True))
        self.hide()

    def _tol(self, v):
        prefs.set("rt_tol", int(v))
        if self.board._retouch:
            self.board._retouch.tol = int(v)

    def _size(self, v):
        prefs.set("rt_size", int(v))
        if self.board._retouch:
            self.board._retouch.size = int(v)
            self.board._update_cursor()

    def sync(self):
        s = self.board._retouch
        if s is None:
            return
        for tl, b in self.tools.items():
            b.setChecked(s.tool == tl)
        has = s.mask is not None
        self.b_del.setEnabled(has)
        self.b_none.setEnabled(has)
        self.size.setEnabled(s.tool in ("erase", "restore"))

    def place(self):
        self.adjustSize()
        vp = self.board.viewport().geometry()
        self.move(vp.x() + max(6, (vp.width() - self.width()) // 2), vp.y() + 58)   # ipucu balonunun altında
        self.raise_()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(r, r.height() / 2, r.height() / 2)
        p.fillPath(path, qcolor("dock"))
        p.setPen(QPen(qcolor("divider"), 1))
        p.drawPath(path)
