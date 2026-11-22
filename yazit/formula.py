"""Formül paneli (Word'ün denklem düzenleyicisi gibi): LaTeX yazarken tahtadaki formül anında düzelir.
Üstte önizleme, kategorili sembol / yapı paleti (tıklayınca imlecin yerine girer; seçili yazı ilk yuvaya
sarılır), altta LaTeX satırı: "\\" ile komut tamamlama, Tab sonraki boş yuva {}, "{" kendiliğinden kapanır.
Enter bitir · Shift+Enter yeni satır (\\\\) · Esc vazgeç."""
import re

from PyQt6.QtCore import Qt, QSize, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QIcon, QPainter, QPainterPath, QPen, QTextCursor
from PyQt6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QToolButton, QLabel, QGridLayout,
                             QWidget, QStackedWidget, QButtonGroup, QCompleter, QScrollArea, QSizePolicy)

from . import mathtex
from .i18n import t
from .theme import pal, qcolor
from .widgets import IconButton

CURSOR = "‸"      # parçacıkta imlecin konacağı yer

# (önizleme, eklenecek, ipucu)  — önizleme boşsa eklenecek gösterilir
STRUCT = [
    (r"\frac{a}{b}", r"\frac{‸}{}", "\\frac{}{}"),
    (r"\square^{n}", r"^{‸}", "^{}"),
    (r"\square_{i}", r"_{‸}", "_{}"),
    (r"\square_{i}^{n}", r"_{‸}^{}", "_{}^{}"),
    (r"\sqrt{x}", r"\sqrt{‸}", "\\sqrt{}"),
    (r"\sqrt[n]{x}", r"\sqrt[‸]{}", "\\sqrt[]{}"),
    (r"\int_{a}^{b}", r"\int_{‸}^{} ", "\\int_{}^{}"),
    (r"\iint", r"\iint ", "\\iint"),
    (r"\oint", r"\oint ", "\\oint"),
    (r"\sum_{i=1}^{n}", r"\sum_{‸}^{} ", "\\sum_{}^{}"),
    (r"\prod_{i}", r"\prod_{‸}^{} ", "\\prod_{}^{}"),
    (r"\lim_{x\to a}", r"\lim_{‸ \to } ", "\\lim_{x \\to a}"),
    (r"\left(x\right)", r"\left( ‸ \right)", "\\left( \\right)"),
    (r"\left[x\right]", r"\left[ ‸ \right]", "\\left[ \\right]"),
    (r"\left\{x\right\}", r"\left\{ ‸ \right\}", "\\left\\{ \\right\\}"),
    (r"\left|x\right|", r"\left| ‸ \right|", "\\left| \\right|"),
    (r"\vec{a}", r"\vec{‸}", "\\vec{}"),
    (r"\hat{n}", r"\hat{‸}", "\\hat{}"),
    (r"\bar{x}", r"\bar{‸}", "\\bar{}"),
    (r"\dot{x}", r"\dot{‸}", "\\dot{}"),
    (r"\ddot{x}", r"\ddot{‸}", "\\ddot{}"),
    (r"\tilde{a}", r"\tilde{‸}", "\\tilde{}"),
    (r"\overline{AB}", r"\overline{‸}", "\\overline{}"),
    (r"\frac{d}{dx}", r"\frac{d‸}{dx}", "\\frac{d}{dx}"),
    (r"\frac{\partial}{\partial x}", r"\frac{\partial ‸}{\partial }", "\\frac{\\partial}{\\partial x}"),
    (r"e^{x}", r"e^{‸}", "e^{}"),
    (r"\log_{a}", r"\log_{‸} ", "\\log_{}"),
    (r"\sin\theta", r"\sin ‸", "\\sin"),
    (r"\cos\theta", r"\cos ‸", "\\cos"),
    (r"\tan\theta", r"\tan ‸", "\\tan"),
    (r"\begin{pmatrix}a&b\\c&d\end{pmatrix}", r"\begin{pmatrix} ‸ &  \\  &  \end{pmatrix}", "pmatrix"),
    (r"\begin{bmatrix}a&b\\c&d\end{bmatrix}", r"\begin{bmatrix} ‸ &  \\  &  \end{bmatrix}", "bmatrix"),
    (r"\begin{vmatrix}a&b\\c&d\end{vmatrix}", r"\begin{vmatrix} ‸ &  \\  &  \end{vmatrix}", "vmatrix"),
    (r"\begin{pmatrix}x\\y\\z\end{pmatrix}", r"\begin{pmatrix} ‸ \\  \\  \end{pmatrix}", "pmatrix"),
    (r"\begin{cases}a&x>0\\b&x<0\end{cases}", r"\begin{cases} ‸ &  \\  &  \end{cases}", "cases"),
    (r"\text{abc}", r"\text{‸}", "\\text{}"),
    (r"\mathbf{F}", r"\mathbf{‸}", "\\mathbf{}"),
    (r"\mathbb{R}", r"\mathbb{‸}", "\\mathbb{}"),
]
_G = ("alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa lambda mu nu xi pi rho sigma "
      "tau upsilon phi varphi chi psi omega Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega").split()
GREEK = [("\\" + g, "\\" + g + " ", "\\" + g) for g in _G]
_O = ("pm mp times div cdot circ ast leq geq neq approx equiv sim simeq cong propto ll gg infty partial nabla "
      "in notin subset subseteq supset cup cap setminus forall exists emptyset angle perp parallel degree prime "
      "hbar ell therefore because ldots cdots vdots ddots neg wedge vee oplus otimes").split()
OPS = [("\\" + o, "\\" + o + " ", "\\" + o) for o in _O] + [
    (r"\mathbb{R}", r"\mathbb{R}", "\\mathbb{R}"), (r"\mathbb{N}", r"\mathbb{N}", "\\mathbb{N}"),
    (r"\mathbb{Z}", r"\mathbb{Z}", "\\mathbb{Z}"), (r"\mathbb{C}", r"\mathbb{C}", "\\mathbb{C}")]
_A = ("to leftarrow leftrightarrow Rightarrow Leftarrow Leftrightarrow mapsto uparrow downarrow longrightarrow "
      "rightleftharpoons implies iff").split()
ARROWS = [("\\" + a, "\\" + a + " ", "\\" + a) for a in _A]
FORMULAS = [
    r"\sigma = \frac{F}{A}",
    r"\tau = \frac{T r}{J}",
    r"\sigma = \frac{M y}{I}",
    r"\varepsilon = \frac{\Delta L}{L_0}",
    r"\sigma = E \varepsilon",
    r"\tau = G \gamma",
    r"P_{cr} = \frac{\pi^2 E I}{(K L)^2}",
    r"\sigma_{1,2} = \frac{\sigma_x + \sigma_y}{2} \pm \sqrt{\left(\frac{\sigma_x - \sigma_y}{2}\right)^2 + \tau_{xy}^2}",
    r"\sum F_x = 0,\ \sum F_y = 0,\ \sum M = 0",
    r"\sum F_x = m a_x",
    r"\sum F_y = m a_y",
    r"\sum M_G = I_G \alpha",
    r"\sum F_x &= m a_x \\ \sum F_y &= m a_y \\ \sum M_G &= I_G \alpha",
    r"\sum \vec{M}_O = \vec{r} \times \vec{F}",
    r"\sum \vec{F} = m \vec{a}",
    r"\vec{F} = m \vec{a}",
    r"E I \frac{d^2 y}{dx^2} = M(x)",
    r"\delta_{max} = \frac{P L^3}{3 E I}",
    r"\omega_n = \sqrt{\frac{k}{m}}",
    r"m\ddot{x} + c\dot{x} + k x = F(t)",
    r"T = 2\pi\sqrt{\frac{L}{g}}",
    r"Re = \frac{\rho V D}{\mu}",
    r"P + \frac{1}{2}\rho V^2 + \rho g h = \text{sabit}",
    r"C_L = \frac{2 L}{\rho V^2 S}",
    r"Q = \dot{m} c_p \Delta T",
    r"\eta = 1 - \frac{T_C}{T_H}",
    r"\mathrm{C}_x \mathrm{H}_y + a_{th} (\mathrm{O_2} + 3.76\,\mathrm{N_2}) \to x\,\mathrm{CO_2} + \frac{y}{2}\,\mathrm{H_2O} + 3.76\,a_{th}\,\mathrm{N_2}",
    r"a_{th} = x + \frac{y}{4}",
    r"AF = \frac{m_{\text{hava}}}{m_{\text{yakıt}}} = \frac{N_{\text{hava}} M_{\text{hava}}}{N_C M_C + N_H M_H}",
    r"Q_{in} - W_{out} = \Delta U",
    r"\dot{Q} - \dot{W} = \sum \dot{m}_e \left(h_e + \frac{V_e^2}{2} + g z_e\right) - \sum \dot{m}_i \left(h_i + \frac{V_i^2}{2} + g z_i\right)",
    r"P v = R T",
    r"P V^n = \text{sabit}",
    r"\eta_{Otto} = 1 - \frac{1}{r^{k-1}}",
    r"\eta_{Brayton} = 1 - \frac{1}{r_p^{(k-1)/k}}",
    r"\Delta s = c_p \ln\frac{T_2}{T_1} - R \ln\frac{P_2}{P_1}",
    r"P = P_{atm} + \rho g h",
    r"P_A + \rho_1 g h_1 - \rho_2 g h_2 = P_{atm}",
    r"\frac{\delta}{x} = \frac{5.0}{\sqrt{Re_x}}",
    r"\tau_w = \mu \left.\frac{\partial u}{\partial y}\right|_{y=0}",
    r"F_D = \frac{1}{2} C_D \rho V^2 A",
    r"h_L = f \frac{L}{D} \frac{V^2}{2g}",
    r"F_B = \rho_f g V_{sub}",
    r"\frac{\partial T}{\partial t} = \alpha \nabla^2 T",
    r"f(x) = \frac{1}{\sigma\sqrt{2\pi}} e^{-\frac{(x-\mu)^2}{2\sigma^2}}",
    r"z = \frac{x - \mu}{\sigma}",
    r"\bar{x} = \frac{1}{n}\sum_{i=1}^{n} x_i",
    r"s = \sqrt{\frac{1}{n-1}\sum_{i=1}^{n}(x_i - \bar{x})^2}",
    r"x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}",
]
CATS = (("fx_struct", STRUCT), ("fx_greek", GREEK), ("fx_ops", OPS), ("fx_arrows", ARROWS),
        ("fx_formulas", [(f, f, f) for f in FORMULAS]))

# komut tamamlama: ad → arkasına eklenen
ARGS = {"frac": "{‸}{}", "dfrac": "{‸}{}", "sqrt": "{‸}", "vec": "{‸}", "hat": "{‸}", "bar": "{‸}", "dot": "{‸}",
        "ddot": "{‸}", "tilde": "{‸}", "overline": "{‸}", "underline": "{‸}", "text": "{‸}", "mathbf": "{‸}",
        "mathbb": "{‸}", "mathrm": "{‸}", "operatorname": "{‸}", "binom": "{‸}{}", "widehat": "{‸}",
        "left": "( ‸ \\right)", "begin": "{‸}", "overset": "{‸}{}", "underset": "{‸}{}"}


def _commands():
    names = set(mathtex.GREEK) | set(mathtex.BIN) | set(mathtex.REL) | set(mathtex.ORD) | set(mathtex.BIGOP)
    names |= set(mathtex.INTEGRAL) | set(mathtex.FUNCS) | set(mathtex.ACCENTS) | set(ARGS) | {"quad", "qquad"}
    return sorted("\\" + n for n in names if n.isalpha())


class SourceEdit(QPlainTextEdit):
    done = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabChangesFocus(False)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        f = QFont()
        f.setFamilies(["Cascadia Mono", "Consolas", "JetBrains Mono", "Courier New"])
        f.setPixelSize(15)
        self.setFont(f)
        self.comp = QCompleter(_commands(), self)
        self.comp.setCaseSensitivity(Qt.CaseSensitivity.CaseSensitive)
        self.comp.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.comp.setMaxVisibleItems(9)
        self.comp.setWidget(self)
        self.comp.activated.connect(self._complete)

    # --- komut tamamlama
    def _prefix(self):
        c = self.textCursor()
        line = c.block().text()[:c.positionInBlock()]
        m = re.search(r"\\[A-Za-z]+$", line)
        return m.group(0) if m else ""

    def _complete(self, text):
        pre = self._prefix()
        c = self.textCursor()
        c.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, len(pre))
        self.setTextCursor(c)
        self.insert_snippet(text + ARGS.get(text[1:], " "))

    def _update_completer(self):
        pre = self._prefix()
        if len(pre) < 2:
            self.comp.popup().hide()
            return
        self.comp.setCompletionPrefix(pre)
        if self.comp.completionCount() == 0 or (self.comp.completionCount() == 1 and
                                                 self.comp.currentCompletion() == pre):
            self.comp.popup().hide()
            return
        r = self.cursorRect()
        r.setWidth(220)
        self.comp.complete(r)
        self.comp.popup().setCurrentIndex(self.comp.completionModel().index(0, 0))

    # --- parçacık
    def insert_snippet(self, snip):
        """CURSOR imlecin yeri; seçili yazı varsa ilk yuvaya (CURSOR'un yerine) girer."""
        c = self.textCursor()
        sel = c.selectedText().replace(" ", "\n")
        if CURSOR not in snip:
            snip += CURSOR
        if sel:
            snip = snip.replace(CURSOR, sel + CURSOR, 1) if "{" + CURSOR + "}" in snip or "[" + CURSOR in snip \
                else sel + snip
        start = c.selectionStart()
        k = snip.index(CURSOR)
        c.insertText(snip.replace(CURSOR, "", 1))
        c.setPosition(start + k)
        self.setTextCursor(c)
        self.setFocus()

    def jump_slot(self, back=False):
        """Sonraki (önceki) boş yuva {} / [] — Word'deki gibi Tab ile yuvadan yuvaya."""
        s = self.toPlainText()
        pos = self.textCursor().position()
        slots = [m.start() + 1 for m in re.finditer(r"\{\}|\[\]", s)]
        if back:
            cand = [p for p in slots if p < pos - 1]
            target = cand[-1] if cand else None
        else:
            cand = [p for p in slots if p > pos]
            target = cand[0] if cand else len(s)
        if target is not None:
            c = self.textCursor()
            c.setPosition(target)
            self.setTextCursor(c)

    def keyPressEvent(self, e):
        k = e.key()
        if self.comp.popup().isVisible() and k in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab,
                                                   Qt.Key.Key_Escape, Qt.Key.Key_Up, Qt.Key.Key_Down):
            if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
                idx = self.comp.popup().currentIndex()
                txt = idx.data() if idx.isValid() else self.comp.currentCompletion()
                self.comp.popup().hide()
                if txt:
                    self._complete(txt)
                return
            if k == Qt.Key.Key_Escape:
                self.comp.popup().hide()
                return
            e.ignore()
            return
        mods = e.modifiers()
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if mods & Qt.KeyboardModifier.ShiftModifier:
                self.textCursor().insertText(" \\\\\n")
            else:
                self.done.emit(True)
            return
        if k == Qt.Key.Key_Escape:
            self.done.emit(False)
            return
        if k == Qt.Key.Key_Tab:
            self.jump_slot()
            return
        if k == Qt.Key.Key_Backtab:
            self.jump_slot(back=True)
            return
        txt = e.text()
        c = self.textCursor()
        if txt == "{" and not c.hasSelection():
            c.insertText("{}")
            c.movePosition(QTextCursor.MoveOperation.Left)
            self.setTextCursor(c)
            return
        if txt == "{" and c.hasSelection():
            self.insert_snippet("{" + CURSOR + "}")
            return
        if txt == "}" and not c.hasSelection():
            nxt = self.toPlainText()[c.position():c.position() + 1]
            if nxt == "}":
                c.movePosition(QTextCursor.MoveOperation.Right)
                self.setTextCursor(c)
                return
        if k == Qt.Key.Key_Backspace and not c.hasSelection():
            s = self.toPlainText()
            p = c.position()
            if 0 < p < len(s) and s[p - 1:p + 1] == "{}":     # boş çifti birlikte sil
                c.movePosition(QTextCursor.MoveOperation.Right)
                c.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.KeepAnchor, 2)
                c.removeSelectedText()
                return
        super().keyPressEvent(e)
        if txt and (txt.isalpha() or txt == "\\"):
            self._update_completer()
        elif txt:
            self.comp.popup().hide()


class FormulaPanel(QFrame):
    """board: Board · changed(src, size) · finished(ok)."""
    changed = pyqtSignal(str, float)
    finished = pyqtSignal(bool)

    def __init__(self, board, src, size):
        super().__init__(board)
        self.board = board
        self._size = float(size)
        self._closed = False
        self.setObjectName("FormulaPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setFixedWidth(560)
        c = pal()
        self.setStyleSheet(f"""
            QToolButton#Pal {{ background: transparent; border: none; border-radius: 6px; padding: 2px; }}
            QToolButton#Pal:hover {{ background: {c['hover']}; }}
            QToolButton#Tab {{ background: transparent; border: none; border-radius: 12px; padding: 3px 10px;
                               color: {c['text2']}; }}
            QToolButton#Tab:hover {{ background: {c['hover']}; }}
            QToolButton#Tab:checked {{ background: {c['chip_active_bg']}; color: {c['chip_active_fg']}; }}
            QPlainTextEdit {{ background: {c['input_bg']}; border: 1px solid {c['input_border']};
                              border-radius: 8px; padding: 4px; color: {c['text']}; }}
            QLabel#Hint {{ color: {c['text3']}; }}
            QScrollArea {{ background: transparent; border: none; }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(8)

        # sekmeler + boyut + kapat
        top = QHBoxLayout()
        top.setSpacing(2)
        self.tabs = QButtonGroup(self)
        self.stack = QStackedWidget(self)
        self._built = {}
        for i, (key, _items) in enumerate(CATS):
            b = QToolButton(self)
            b.setObjectName("Tab")
            b.setText(t(key))
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            self.tabs.addButton(b, i)
            top.addWidget(b)
            ph = QWidget()
            self.stack.addWidget(ph)
        self.tabs.idClicked.connect(self._show_cat)
        top.addStretch(1)
        self.b_small = IconButton("text_smaller", t("txt_smaller"), 28, 18, parent=self)
        self.b_big = IconButton("text_bigger", t("txt_bigger"), 28, 18, parent=self)
        self.b_small.clicked.connect(lambda: self._resize(1 / 1.15))
        self.b_big.clicked.connect(lambda: self._resize(1.15))
        self.b_ok = IconButton("check", t("fx_done"), 28, 18, parent=self)
        self.b_ok.clicked.connect(lambda: self.finish(True))
        self.b_x = IconButton("close", t("fx_cancel"), 28, 18, parent=self)
        self.b_x.clicked.connect(lambda: self.finish(False))
        for b in (self.b_small, self.b_big, self.b_ok, self.b_x):
            top.addWidget(b)
        lay.addLayout(top)

        self.stack.setFixedHeight(128)
        lay.addWidget(self.stack)

        self.preview = QLabel(self)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(44)
        lay.addWidget(self.preview)

        self.edit = SourceEdit(self)
        self.edit.setPlaceholderText(t("fx_placeholder"))
        self.edit.setFixedHeight(64)
        self.edit.setPlainText(src)
        self.edit.moveCursor(QTextCursor.MoveOperation.End)
        self.edit.textChanged.connect(self._on_text)
        self.edit.done.connect(self.finish)
        lay.addWidget(self.edit)
        hint = QLabel(t("fx_hint"), self)
        hint.setObjectName("Hint")
        hint.setWordWrap(True)
        f = hint.font()
        f.setPixelSize(11)
        hint.setFont(f)
        lay.addWidget(hint)

        from .config import prefs
        cat = prefs.get("fx_cat", 0)
        cat = cat if isinstance(cat, int) and 0 <= cat < len(CATS) else 0
        self.tabs.button(cat).setChecked(True)
        self._show_cat(cat)
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(30)
        self._preview_timer.timeout.connect(self._render_preview)
        self._render_preview()
        self.adjustSize()

    # --- palet
    def _show_cat(self, i):
        from .config import prefs
        prefs.set("fx_cat", i)
        if i not in self._built:
            self._built[i] = self._build_cat(i)
            old = self.stack.widget(i)
            self.stack.insertWidget(i, self._built[i])
            self.stack.removeWidget(old)
            old.deleteLater()
        self.stack.setCurrentIndex(i)

    def _build_cat(self, i):
        key, items = CATS[i]
        col = pal()["text"]
        wide = key == "fx_formulas"
        inner = QWidget()
        grid = QGridLayout(inner)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(2)
        ncol = 2 if wide else 12
        for n, (prev, ins, tip) in enumerate(items):
            b = QToolButton(inner)
            b.setObjectName("Pal")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            pm = mathtex.render_pixmap(prev, 13 if wide else 17, col, pad=2, max_w=250 if wide else 34)
            b.setIcon(QIcon(pm))
            b.setIconSize(QSize(int(pm.width() / pm.devicePixelRatio()), int(pm.height() / pm.devicePixelRatio())))
            if wide:
                b.setFixedSize(258, 40)
            else:
                b.setFixedSize(40, 38)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, s=ins: self.edit.insert_snippet(s))
            grid.addWidget(b, n // ncol, n % ncol)
        grid.setRowStretch(len(items) // ncol + 1, 1)
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sa.setWidget(inner)
        inner.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        return sa

    # --- durum
    def src(self):
        return self.edit.toPlainText()

    def fsize(self):
        return self._size

    def _resize(self, k):
        self._size = max(10.0, min(300.0, round(self._size * k, 1)))
        self.changed.emit(self.src(), self._size)

    def _on_text(self):
        self.changed.emit(self.src(), self._size)
        self._preview_timer.start()

    def _render_preview(self):
        src = self.src()
        if not src.strip():
            self.preview.setPixmap(mathtex.render_pixmap("", 26, pal()["text3"], pad=4))
            return
        self.preview.setPixmap(mathtex.render_pixmap(src, 26, pal()["text"], pad=4, max_w=self.width() - 30))

    def finish(self, ok=True):
        if self._closed:
            return
        self._closed = True
        self.edit.comp.popup().hide()
        self.hide()
        self.finished.emit(bool(ok))
        self.deleteLater()

    def focus(self):
        self.edit.setFocus()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.finish(False)
            return
        super().keyPressEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect().toRectF().adjusted(0.5, 0.5, -0.5, -0.5)
        path = QPainterPath()
        path.addRoundedRect(r, 14, 14)
        p.fillPath(path, qcolor("dock"))
        p.setPen(QPen(qcolor("divider"), 1))
        p.drawPath(path)
