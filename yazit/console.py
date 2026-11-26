"""Geliştirici konsolu: yazit.cli komutlarını uygulamanın içinden yazmak için (python -m yazit.cli ile aynı kapı).

Kısayol Esc'nin altındaki, 1'in solundaki tuş (Türkçe Q klavyede "). Klavye düzeninden bağımsız olsun diye fiziksel
tuş (Windows tarama kodu 41) yakalanır:
  Shift + "   geliştirici modunu açar / kapatır (prefs dev_mode; açılınca konsol da gelir)
  "           geliştirici modu açıkken konsolu açar / kapatır (yazı alanındayken " normal yazılır; konsolun satırı
              boşken " konsolu kapatır)
Esc kapatır. ↑ / ↓ geçmiş (prefs console_history), Tab komutu / aracı / rengi / temayı tamamlar.
Konsolun kendi komutları: help, clear (cls), exit. Geri kalan her şey cli.run'a gider (go board | research | <not>
gezinmedir). Panel başlık çubuğunun altından tahtanın üstüne iner.
"""
import shlex

from PyQt6.QtCore import Qt, QEvent, QObject, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QFont, QTextCharFormat, QTextCursor
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QLineEdit, QLabel,
                             QAbstractSpinBox, QTextEdit)

from . import cli
from .config import prefs
from .i18n import t
from .theme import theme, color, qcolor

SCAN_CODE = 41                          # Esc'nin altındaki tuş (US ` / TR-Q ")
_FALLBACK_KEYS = (Qt.Key.Key_QuoteDbl, Qt.Key.Key_QuoteLeft, Qt.Key.Key_Eacute, Qt.Key.Key_AsciiTilde)
BUILTINS = ("help", "clear", "cls", "exit")
HISTORY_MAX = 100
ERROR_COLOR = "#ff6b63"
MONO = ["Cascadia Mono", "Consolas", "Courier New"]


def is_console_key(e):
    """Esc'nin altındaki tuş mu (tarama kodu; yapay olaylarda tarama kodu 0 → tuş koduna bakılır)."""
    sc = e.nativeScanCode()
    if sc:
        return (sc & 0xFF) == SCAN_CODE
    return e.key() in _FALLBACK_KEYS


def _is_text_input(w):
    return isinstance(w, (QLineEdit, QPlainTextEdit, QTextEdit, QAbstractSpinBox)) and not getattr(w, "isReadOnly", lambda: False)()


class Console(QWidget):
    """Başlık çubuğunun altından aşağı inen panel."""

    def __init__(self, app):
        win = app.win
        super().__init__(win.centralWidget())
        self.app = app
        self.win = win
        self.setObjectName("Console")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.hide()
        v = QVBoxLayout(self)
        v.setContentsMargins(14, 10, 14, 10)
        v.setSpacing(6)
        head = QHBoxLayout()
        self.title = QLabel(t("con_title"))
        self.title.setObjectName("ConsoleTitle")
        head.addWidget(self.title)
        head.addStretch(1)
        self.hint = QLabel(t("con_hint"))
        self.hint.setObjectName("ConsoleHint")
        head.addWidget(self.hint)
        v.addLayout(head)
        mono = QFont(MONO[0])
        mono.setStyleHint(QFont.StyleHint.Monospace)
        mono.setFamilies(MONO)
        mono.setPointSizeF(10)
        self.out = QPlainTextEdit()
        self.out.setObjectName("ConsoleOut")
        self.out.setReadOnly(True)
        self.out.setFont(mono)
        self.out.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.out.setMaximumBlockCount(4000)
        v.addWidget(self.out, 1)
        row = QHBoxLayout()
        row.setSpacing(8)
        self.prompt = QLabel("›")
        self.prompt.setObjectName("ConsolePrompt")
        self.prompt.setFont(mono)
        row.addWidget(self.prompt)
        self.edit = QLineEdit()
        self.edit.setObjectName("ConsoleIn")
        self.edit.setFont(mono)
        self.edit.setPlaceholderText(t("con_ph"))
        self.edit.returnPressed.connect(self._submit)
        self.edit.installEventFilter(self)
        row.addWidget(self.edit, 1)
        v.addLayout(row)
        self.history = list(prefs.get("console_history") or [])[-HISTORY_MAX:]
        self._hpos = len(self.history)
        self._anim = None
        self._open = False
        self._greeted = False
        theme.bind(self, Console._restyle)

    # ------------------------------------------------------------ görünüm
    def _restyle(self):
        mono = ", ".join(f'"{f}"' for f in MONO) + ", monospace"
        self.setStyleSheet(f"""
            #Console {{ background: {color('bg')}; border-bottom: 1px solid {color('divider')}; }}
            #ConsoleTitle {{ color: {color('text')}; font-weight: 600; }}
            #ConsoleHint {{ color: {color('text3')}; }}
            #ConsoleOut, #ConsoleIn, #ConsolePrompt {{ font-family: {mono}; font-size: 13px; }}
            #ConsoleOut {{ background: {color('bg')}; color: {color('text')}; border: none; }}
            #ConsolePrompt {{ color: {color('text2')}; font-size: 15px; }}
            #ConsoleIn {{ background: {color('input_bg')}; color: {color('text')};
                          border: 1px solid {color('input_border')}; border-radius: 6px; padding: 6px 8px; }}
        """)

    def _target_rect(self):
        root = self.win.centralWidget()
        top = self.win.titlebar.geometry().bottom() + 1 if self.win.titlebar.isVisible() else 0
        h = max(220, int((root.height() - top) * 0.45))
        return QRect(0, top, root.width(), h)

    def reposition(self):
        if self.isVisible() and (self._anim is None or self._anim.state() != QPropertyAnimation.State.Running):
            self.setGeometry(self._target_rect())

    def is_open(self):
        return self._open

    def open(self):
        if not self._greeted:
            self._greeted = True
            self._write(t("con_welcome"), "text3")
        self._open = True
        r = self._target_rect()
        self.setGeometry(QRect(r.x(), r.y(), r.width(), 0))
        self.show()
        self.raise_()
        self._animate(r)
        self.edit.setFocus()

    def close_panel(self):
        if not self._open:
            return
        self._open = False
        r = self.geometry()
        a = self._animate(QRect(r.x(), r.y(), r.width(), 0))
        a.finished.connect(lambda: (not self._open) and self.hide())
        (self.win.research if self.win.in_research() else self.win.board).setFocus()

    def toggle(self):
        self.close_panel() if self._open else self.open()

    def _animate(self, end):
        if self._anim is not None:
            self._anim.stop()
        a = QPropertyAnimation(self, b"geometry", self)
        a.setDuration(140)
        a.setEasingCurve(QEasingCurve.Type.OutCubic)
        a.setStartValue(self.geometry())
        a.setEndValue(end)
        a.start()
        self._anim = a
        return a

    # ------------------------------------------------------------ yazma
    def _write(self, text, role="text"):
        fmt = QTextCharFormat()
        if role == "bad":
            fmt.setForeground(qcolor(ERROR_COLOR))
        elif role != "text":                   # düz metin rengi sabitlenmez: tema değişince stil sayfasından gelir
            fmt.setForeground(qcolor(role))
        cur = self.out.textCursor()
        cur.movePosition(QTextCursor.MoveOperation.End)
        if not self.out.document().isEmpty():
            cur.insertText("\n")
        cur.insertText(text, fmt)
        self.out.setTextCursor(cur)
        self.out.ensureCursorVisible()

    def output_text(self):
        return self.out.toPlainText()

    # ------------------------------------------------------------ çalıştırma
    def _submit(self):
        line = self.edit.text().strip()
        self.edit.clear()
        if not line:
            return
        if not self.history or self.history[-1] != line:
            self.history.append(line)
            self.history = self.history[-HISTORY_MAX:]
            prefs.set("console_history", self.history)
        self._hpos = len(self.history)
        self.execute(line)

    def execute(self, line):
        """Bir satırı çalıştırır → (kod, çıktı). Testler de bunu çağırır."""
        self._write("› " + line, "text2")
        try:
            argv = shlex.split(line, posix=True)
        except ValueError as e:
            self._write(t("con_parse_err", e=str(e)), "bad")
            return 1, str(e)
        if not argv:
            return 0, ""
        cmd = argv[0].lower()
        if cmd in ("clear", "cls"):
            self.out.clear()
            return 0, ""
        if cmd == "exit":
            self.close_panel()
            return 0, ""
        code, text = cli.run(self.app, argv)
        if cmd in ("help", "-h", "--help") and len(argv) == 1:
            text = t("con_help") + "\n\n" + text
        if text:
            self._write(text, "bad" if code else "text")
        return code, text

    # ------------------------------------------------------------ satır: geçmiş, tamamlama, kapatma
    def _complete(self):
        text = self.edit.text()
        parts = text.split(" ")
        word = parts[-1].lower()
        if len(parts) == 1:
            pool = sorted(set(cli.COMMANDS) | set(BUILTINS))
        elif parts[0].lower() == "go" and len(parts) == 2:
            pool = list(cli.GO_TARGETS)
        elif parts[0].lower() == "export" and len(parts) == 2:
            pool = list(cli.EXPORT_FORMATS) + ["all"]
        elif parts[0].lower() == "tool" and len(parts) == 2:
            from .tools import TOOLS
            pool = list(TOOLS)
        elif parts[0].lower() == "color" and len(parts) == 2:
            pool = sorted(k for k in cli.COLOR_NAMES if k.isascii())
        elif parts[0].lower() == "theme" and len(parts) == 2:
            from .theme import VARIANTS
            pool = sorted(VARIANTS)
        elif parts[0].lower() == "pref" and len(parts) == 2:
            pool = sorted(prefs.data)
        else:
            return
        hits = [p for p in pool if p.startswith(word)]
        if len(hits) == 1:
            parts[-1] = hits[0]
            self.edit.setText(" ".join(parts) + " ")
        elif hits:
            common = hits[0]
            for h in hits[1:]:
                while not h.startswith(common):
                    common = common[:-1]
            if len(common) > len(word):
                parts[-1] = common
                self.edit.setText(" ".join(parts))
            else:
                self._write("  ".join(hits), "text3")

    def eventFilter(self, obj, e):
        if obj is self.edit and e.type() == QEvent.Type.KeyPress:
            k = e.key()
            if k == Qt.Key.Key_Escape:
                self.close_panel()
                return True
            if k == Qt.Key.Key_Tab:
                self._complete()
                return True
            if k in (Qt.Key.Key_Up, Qt.Key.Key_Down) and self.history:
                self._hpos = max(0, min(len(self.history), self._hpos + (-1 if k == Qt.Key.Key_Up else 1)))
                self.edit.setText(self.history[self._hpos] if self._hpos < len(self.history) else "")
                return True
        return super().eventFilter(obj, e)


class ConsoleKeys(QObject):
    """Uygulama düzeyinde tuş süzgeci: Shift+" geliştirici modu, " konsol."""

    def __init__(self, win, console):
        super().__init__(win)
        self.win = win
        self.console = console

    def handle(self, e):
        """Tuş olayını işler; işlediyse True (olay yutulur)."""
        if e.isAutoRepeat() or not is_console_key(e):
            return False
        mods = e.modifiers() & ~Qt.KeyboardModifier.KeypadModifier
        active = QApplication.activeWindow()
        if active is not None and active is not self.win:
            return False                        # açık bir iletişim kutusu varken dokunma
        if mods == Qt.KeyboardModifier.ShiftModifier:
            on = not prefs.get("dev_mode", False)
            prefs.set("dev_mode", on)
            self.win.board.toast(t("con_dev_on") if on else t("con_dev_off"), 1800)
            if on:
                self.console.open()
            else:
                self.console.close_panel()
            return True
        if mods != Qt.KeyboardModifier.NoModifier or not prefs.get("dev_mode", False):
            return False
        focus = QApplication.focusWidget()
        if focus is self.console.edit:
            if self.console.edit.text():
                return False                    # komutun içinde " yazılır (open "Ders notu")
            self.console.close_panel()
            return True
        if _is_text_input(focus):
            return False
        self.console.toggle()
        return True

    def eventFilter(self, obj, e):
        if e.type() == QEvent.Type.KeyPress and obj.isWidgetType() and obj.window() is self.win:
            try:
                return self.handle(e)
            except Exception:  # noqa: BLE001  (süzgeçte hata uygulamayı düşürmesin)
                import traceback
                traceback.print_exc()
                return False
        return False


def install(app):
    """app = YazitApp (komutlar yakalama / ekrana çiz gibi uygulama düzeyi işlere de ulaşsın)."""
    win = app.win
    con = Console(app)
    keys = ConsoleKeys(win, con)
    QApplication.instance().installEventFilter(keys)
    win.console = con
    win.console_keys = keys
    return con
