"""Yüzen araç çubuğu: araçlar, renkler, kalınlık, geri al / yinele (+ isteğe bağlı ek düğmeler).
Konumu değiştirilebilir: alt / üst (yatay) ya da sol / sağ (dikey). Boş yerinden tutup bir kenara sürükle,
sağ tıkla ya da Seçenekler'den seç."""
from PyQt6.QtCore import Qt, QRectF, QPointF, QPoint, QSize, QObject, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen, QPainterPath, QConicalGradient, QBrush
from PyQt6.QtWidgets import QWidget, QBoxLayout, QAbstractButton, QMenu, QColorDialog, QToolTip

from . import icons
from . import items as I
from .config import prefs
from .i18n import t
from .theme import theme, qcolor, color as tcolor
from .tools import state, COLORS, COLOR_NAMES, SHAPES, BASIC_SHAPES, add_eng_menu, ICON, BRUSHES, BRUSH_ICON, ERASER_MODES, tool_key
from .widgets import IconButton

POSITIONS = ("bottom", "top", "left", "right")


class _Bus(QObject):
    position_changed = pyqtSignal()   # tüm araç çubukları (ana pencere + ekrana çiz) yeniden yerleşsin


bus = _Bus()


def set_position(pos):
    if pos in POSITIONS and pos != prefs.get("toolbar_pos", "bottom"):
        prefs.set("toolbar_pos", pos)
        bus.position_changed.emit()


class Swatch(QAbstractButton):
    def __init__(self, col, parent=None):
        super().__init__(parent)
        self.col = col
        self.setFixedSize(28, 36)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2)
        if self.isChecked():
            pen = QPen(qcolor("text"), 2)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(c, 12, 12)
        elif self.underMouse():
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(qcolor("hover"))
            p.drawEllipse(c, 13, 13)
        # beyaz / siyah zeminle karışmasın: uçtaki renklerde kenar belirgin
        extreme = I.ink(self.col).lightness() in range(0, 40) or I.ink(self.col).lightness() > 225
        p.setPen(QPen(qcolor("text3") if extreme else qcolor("divider"), 1.2 if extreme else 1))
        p.setBrush(I.ink(self.col))
        p.drawEllipse(c, 8.5, 8.5)


class WheelSwatch(Swatch):
    """Özel renk: gökkuşağı halkası, ortasında seçilen özel renk (Paint'teki renk tekerleği gibi)."""

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2)
        if self.isChecked():
            p.setPen(QPen(qcolor("text"), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(c, 12, 12)
        elif self.underMouse():
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(qcolor("hover"))
            p.drawEllipse(c, 13, 13)
        g = QConicalGradient(c, 90)
        for i, h in enumerate((0, 60, 120, 180, 240, 300, 360)):
            g.setColorAt(i / 6, QColor.fromHsv(h % 360, 230, 255))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(c, 9, 9)
        p.setBrush(qcolor("dock"))
        p.drawEllipse(c, 5.2, 5.2)
        p.setBrush(I.ink(self.col))
        p.drawEllipse(c, 4, 4)


def w_to_t(w):
    """Kalınlık → kaydırıcı konumu (0–1). Karekök ölçek: ince kalınlıklar geniş yer kaplar."""
    return max(0.0, min(1.0, ((w - MIN_W) / (MAX_W - MIN_W)) ** 0.5))


def t_to_w(x):
    x = max(0.0, min(1.0, x))
    w = MIN_W + (MAX_W - MIN_W) * x * x
    return round(w * 2) / 2 if w < 10 else round(w)


MIN_W, MAX_W = 0.5, 30.0


class WidthSlider(QWidget):
    """Araç çubuğundaki kalınlık çubuğu: incelen-kalınlaşan kama, tutamaç sürüklenir / tıklanır, tekerlek ince ayar."""
    LONG, SHORT = 104, 36

    def __init__(self, parent=None):
        super().__init__(parent)
        self.vertical = False
        self.setFixedSize(self.LONG, self.SHORT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._drag = False

    def set_vertical(self, v):
        self.vertical = v
        # dikey çubukta yer dar: biraz kısa
        self.setFixedSize(self.SHORT, self.LONG - 28) if v else self.setFixedSize(self.LONG, self.SHORT)

    def _span(self):
        pad = 12
        n = (self.height() if self.vertical else self.width()) - 2 * pad
        return pad, n

    def _set_from(self, pos):
        pad, n = self._span()
        v = (self.height() - pos.y()) if self.vertical else pos.x()   # dikeyde aşağısı ince
        x = (v - pad) / max(1, n)
        if state.tool == "eraser":
            state.set_eraser_size(4 + 156 * max(0.0, min(1.0, x)) ** 2)
        else:
            state.set_width(t_to_w(x))
        self._tip()

    def _tip(self):
        v = state.eraser_size if state.tool == "eraser" else state.width
        QToolTip.showText(self.mapToGlobal(QPoint(self.width() // 2, -8)), f"{v:g} px", self)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = True
            self._set_from(e.position())

    def mouseMoveEvent(self, e):
        if self._drag:
            self._set_from(e.position())

    def mouseReleaseEvent(self, e):
        self._drag = False

    def wheelEvent(self, e):
        d = e.angleDelta().y() or e.angleDelta().x()
        if d:
            state.nudge(1 if d > 0 else -1)
            self._tip()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pad, n = self._span()
        mid = (self.width() if self.vertical else self.height()) / 2

        def pt(a, off):       # a: uzunluk boyunca konum, off: ortadan sapma
            return QPointF(mid + off, self.height() - a) if self.vertical else QPointF(a, mid + off)
        # kama: soldan (ince) sağa (kalın)
        path = QPainterPath()
        path.moveTo(pt(pad, -0.8))
        path.lineTo(pt(pad + n, -5.5))
        path.lineTo(pt(pad + n, 5.5))
        path.lineTo(pt(pad, 0.8))
        path.closeSubpath()
        p.fillPath(path, qcolor("divider"))
        if state.tool == "eraser":
            k = max(0.0, (state.eraser_size - 4) / 156) ** 0.5
        else:
            k = w_to_t(state.width)
        filled = QPainterPath()
        a1 = pad + n * k
        filled.moveTo(pt(pad, -0.8))
        filled.lineTo(pt(a1, -(0.8 + 4.7 * k)))
        filled.lineTo(pt(a1, 0.8 + 4.7 * k))
        filled.lineTo(pt(pad, 0.8))
        filled.closeSubpath()
        p.fillPath(filled, qcolor("text2"))
        c = pt(a1, 0)
        p.setPen(QPen(qcolor("dock"), 2))
        p.setBrush(qcolor("text"))
        p.drawEllipse(c, 6.5, 6.5)


class Sep(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(13, 36)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setPen(QPen(qcolor("divider"), 1))
        if self.width() >= self.height():   # dikey çubukta yatay çizgi
            y = self.height() // 2
            p.drawLine(9, y, self.width() - 9, y)
        else:
            x = self.width() // 2
            p.drawLine(x, 9, x, self.height() - 9)


class ToolBar(QWidget):
    """board_fn(): işlemlerin uygulanacağı tuvali döndürür."""
    placed = pyqtSignal()

    def __init__(self, parent, board_fn, extras=None):
        super().__init__(parent)
        self.board_fn = board_fn
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.vertical = False
        self._drag = None
        self.margin = 16
        lay = QBoxLayout(QBoxLayout.Direction.LeftToRight, self)
        lay.setContentsMargins(10, 6, 10, 6)
        lay.setSpacing(2)
        self.tool_btns = {}
        for tool in ("select", "pen", "hl", "laser", "eraser"):
            b = self._tool_btn(tool)
            lay.addWidget(b)
        self.tool_btns["pen"].clicked.disconnect()
        self.tool_btns["pen"].clicked.connect(lambda: self._menu_tool("pen", self._brush_menu))
        self.tool_btns["eraser"].clicked.disconnect()
        self.tool_btns["eraser"].clicked.connect(lambda: self._menu_tool("eraser", self._eraser_menu))
        self.shape_btn = IconButton(ICON[state.last_shape], "", 36, 20, checkable=True, obj="ToolBtn")
        self.shape_btn.clicked.connect(self._shape_menu)
        self._width_on_right_click(self.shape_btn, "shape")
        lay.addWidget(self.shape_btn)
        lay.addWidget(self._tool_btn("text"))
        b = IconButton("image", t("insert_image") + " (Ctrl+I) · Ctrl+V", 36, 20, obj="ToolBtn")
        b.clicked.connect(lambda: self.board_fn().insert_image_dialog())
        lay.addWidget(b)
        self.table_btn = IconButton("table", t("insert_table"), 36, 20, obj="ToolBtn")
        self.table_btn.clicked.connect(self._table_menu)
        lay.addWidget(self.table_btn)
        self.formula_btn = IconButton("formula", t("insert_formula") + " (Ctrl+E)", 36, 20, obj="ToolBtn")
        self.formula_btn.clicked.connect(lambda: self.board_fn().insert_formula())
        lay.addWidget(self.formula_btn)
        lay.addWidget(self._tool_btn("picker"))
        lay.addWidget(self._tool_btn("fill"))
        lay.addWidget(Sep())
        self.swatches = []
        for i, c in enumerate(COLORS):
            s = Swatch(c)
            s.setToolTip(f"{t(COLOR_NAMES[i])} · Shift+{i + 1}")
            s.clicked.connect(lambda _=False, col=c: self.board_fn().apply_color(col))
            self.swatches.append(s)
            lay.addWidget(s)
        self.custom = WheelSwatch(state.custom_color)
        self.custom.setToolTip(t("color_custom"))
        self.custom.clicked.connect(self._pick_color)
        lay.addWidget(self.custom)
        lay.addWidget(Sep())
        self.width_slider = WidthSlider()
        self.width_slider.setToolTip(t("size_tip"))
        lay.addWidget(self.width_slider)
        self.dash_btn = IconButton("dash_" + state.dash, t("dash_title"), 36, 20, obj="ToolBtn")
        self.dash_btn.clicked.connect(self._dash_menu)
        lay.addWidget(self.dash_btn)
        lay.addWidget(Sep())
        self.btn_undo = IconButton("undo", t("undo") + " (Ctrl+Z)", 36, 20, obj="ToolBtn")
        self.btn_undo.clicked.connect(lambda: self.board_fn().undo())
        self.btn_redo = IconButton("redo", t("redo") + " (Ctrl+Y)", 36, 20, obj="ToolBtn")
        self.btn_redo.clicked.connect(lambda: self.board_fn().redo())
        lay.addWidget(self.btn_undo)
        lay.addWidget(self.btn_redo)
        self.extra_btns = {}
        if extras:
            lay.addWidget(Sep())
            for key, icon, tip, fn, checkable in extras:
                b = IconButton(icon, tip, 36, 20, checkable=checkable, obj="ToolBtn")
                b.clicked.connect(fn)
                self.extra_btns[key] = b
                lay.addWidget(b)
        state.changed.connect(self.sync)
        state.keys_changed.connect(self.update_tips)
        theme.changed.connect(lambda _: self.update())
        bus.position_changed.connect(self.place)
        self.update_tips()
        self.sync()
        self.adjustSize()

    def _tool_btn(self, tool):
        b = IconButton(ICON[tool], "", 36, 20, checkable=True, obj="ToolBtn")
        b.clicked.connect(lambda _=False, x=tool: state.set_tool(x))
        if tool in ("pen", "hl"):
            self._width_on_right_click(b, tool)
        self.tool_btns[tool] = b
        return b

    def _width_on_right_click(self, b, tool):
        """Araç düğmesine sağ tık: kalınlık kaydırıcısı (araç da seçilir)."""
        from .widthmenu import build_width_menu
        b.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        def show(_pos):
            state.set_tool(tool if tool != "shape" else state.last_shape)
            m = QMenu(self)
            build_width_menu(m)
            self._popup(m, b)
        b.customContextMenuRequested.connect(show)

    def _menu_tool(self, tool, build):
        """Kalem / silgi: seçili değilse seçer, zaten seçiliyse türlerini açar (Paint'teki gibi)."""
        b = self.tool_btns[tool]
        if state.tool != tool:
            state.set_tool(tool)
            return
        b.setChecked(True)
        m = QMenu(self)
        build(m)
        self._popup(m, b)

    def _brush_menu(self, m):
        from .widthmenu import build_width_menu
        build_width_menu(m, presets=False)
        m.addSeparator()
        for br in BRUSHES:
            # temada onay kutusu gizli: seçili olan sağda ✓ ile
            a = m.addAction(icons.icon(BRUSH_ICON[br], tcolor("text"), 18),
                            t("br_" + br) + ("	✓" if state.brush == br else ""))
            a.triggered.connect(lambda _=False, x=br: state.set_brush(x))

    def _eraser_menu(self, m):
        for md in ERASER_MODES:
            a = m.addAction(icons.icon("er_" + md, tcolor("text"), 18),
                            t("er_" + md) + ("	✓" if state.eraser_mode == md else ""))
            a.triggered.connect(lambda _=False, x=md: state.set_eraser_mode(x))
        m.addSeparator()
        m.addAction(t("er_size_hint")).setEnabled(False)

    def update_tips(self):
        for tool, b in self.tool_btns.items():
            k = tool_key(tool)
            extra = {"pen": t("br_tip"), "eraser": t("er_tip")}.get(tool, "")
            b.setToolTip(t("tool_" + tool) + (f" ({k})" if k else "") + (f" · {extra}" if extra else ""))
        ks = [k for k in (tool_key(x) for x in BASIC_SHAPES) if k]
        self.shape_btn.setToolTip(t("shapes") + (" (" + ", ".join(ks) + ")" if ks else ""))

    # ------------------------------------------------------------ konum / yön
    def set_vertical(self, v):
        if v == self.vertical:
            return
        self.vertical = v
        lay = self.layout()
        lay.setDirection(QBoxLayout.Direction.TopToBottom if v else QBoxLayout.Direction.LeftToRight)
        if v:
            lay.setContentsMargins(6, 10, 6, 10)
        else:
            lay.setContentsMargins(10, 6, 10, 6)
        self.width_slider.set_vertical(v)
        for w in self.findChildren(QWidget):
            if isinstance(w, (Swatch, Sep)):
                a, b = w.width(), w.height()
                if (a < b) == v:      # yatayda dar-uzun, dikeyde geniş-kısa
                    w.setFixedSize(b, a)
        self.adjustSize()
        self.update()

    def place(self, margin=None):
        """Ebeveynin içinde tercih edilen kenara yerleşir."""
        if margin is not None:
            self.margin = margin
        par = self.parentWidget()
        if par is None:
            return
        pos = prefs.get("toolbar_pos", "bottom")
        if pos not in POSITIONS:
            pos = "bottom"
        self.set_vertical(pos in ("left", "right"))
        self.adjustSize()
        sh = self.sizeHint()
        m = self.margin
        if self.vertical:
            h = min(sh.height(), par.height() - 16)
            self.resize(sh.width(), h)
            x = m if pos == "left" else par.width() - sh.width() - m
            self.move(x, max(8, (par.height() - h) // 2))
        else:
            w = min(sh.width(), par.width() - 16)
            self.resize(w, sh.height())
            y = m if pos == "top" else par.height() - sh.height() - m
            self.move(max(8, (par.width() - w) // 2), y)
        self.raise_()
        self.placed.emit()

    def contextMenuEvent(self, e):
        m = QMenu(self)
        cur = prefs.get("toolbar_pos", "bottom")
        for pos in POSITIONS:
            a = m.addAction(t("tb_" + pos))
            a.setCheckable(True)
            a.setChecked(pos == cur)
            a.triggered.connect(lambda _=False, x=pos: set_position(x))
        m.addSeparator()
        m.addAction(t("tb_drag_hint")).setEnabled(False)
        m.exec(e.globalPos())

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            e.accept()
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            par = self.parentWidget()
            p = self.mapToParent(e.position().toPoint()) - self._drag
            if par is not None:
                p.setX(max(0, min(par.width() - self.width(), p.x())))
                p.setY(max(0, min(par.height() - self.height(), p.y())))
            self.move(p)
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._drag is not None and e.button() == Qt.MouseButton.LeftButton:
            self._drag = None
            self.unsetCursor()
            par = self.parentWidget()
            if par is not None:
                c = self.mapToParent(e.position().toPoint())
                d = {"left": c.x(), "right": par.width() - c.x(), "top": c.y(), "bottom": par.height() - c.y()}
                pos = min(d, key=d.get)
                if pos == prefs.get("toolbar_pos", "bottom"):
                    self.place()
                else:
                    set_position(pos)
            return
        super().mouseReleaseEvent(e)

    def _shape_menu(self):
        self.sync()
        m = QMenu(self)
        col = tcolor("text")
        for tool in BASIC_SHAPES:
            a = m.addAction(icons.icon(ICON[tool], col, 18), f"{t('tool_' + tool)}\t{tool_key(tool)}")
            a.triggered.connect(lambda _=False, x=tool: state.set_tool(x))
        add_eng_menu(m, lambda n: icons.icon(n, col, 18))
        m.addSeparator()
        m.addAction(t("shift_hint")).setEnabled(False)
        self._popup(m, self.shape_btn)

    def _table_menu(self):
        m = QMenu(self)
        self.board_fn().build_table_insert_menu(m)
        self._popup(m, self.table_btn)

    def _popup(self, m, btn):
        """Menüyü düğmenin yanında, araç çubuğunun dışına doğru açar."""
        r = btn.rect()
        pos = prefs.get("toolbar_pos", "bottom")
        sh = m.sizeHint()
        if pos == "left":
            g = btn.mapToGlobal(QPoint(r.right() + 8, r.top()))
        elif pos == "right":
            g = btn.mapToGlobal(QPoint(r.left() - sh.width() - 8, r.top()))
        elif pos == "top":
            g = btn.mapToGlobal(QPoint(r.left(), r.bottom() + 6))
        else:
            g = btn.mapToGlobal(QPoint(r.left(), r.top() - sh.height() - 6))
        m.exec(g)

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(state.custom_color), self.window(), t("color_custom"))
        if c.isValid():
            self.custom.col = c.name()
            self.board_fn().apply_color(c.name())

    def sync(self):
        for tool, b in self.tool_btns.items():
            b.setChecked(state.tool == tool)
        self.shape_btn.set_icon_name(ICON[state.last_shape])
        self.shape_btn.setChecked(state.tool in SHAPES)
        for s in self.swatches:
            s.setChecked(s.col == state.color)
        self.custom.col = state.custom_color
        self.custom.setChecked(state.color not in COLORS)
        self.width_slider.update()
        self.width_slider.setToolTip(t("er_size") if state.tool == "eraser" else t("size_tip"))
        self.dash_btn.set_icon_name("dash_" + state.dash)
        self.tool_btns["pen"].set_icon_name(BRUSH_ICON.get(state.brush, "pen"))
        self.tool_btns["eraser"].set_icon_name("er_" + state.eraser_mode)
        self.update()

    def _dash_menu(self):
        m = QMenu(self)
        self.board_fn().build_dash_menu(m)
        self._popup(m, self.dash_btn)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        rad = min(r.width(), r.height()) / 2
        path.addRoundedRect(r, rad, rad)
        p.fillPath(path, qcolor("dock"))
        p.setPen(QPen(qcolor("divider"), 1))
        p.drawPath(path)

    def sizeHint(self):
        return self.layout().sizeHint() if self.layout() else QSize(600, 48)
