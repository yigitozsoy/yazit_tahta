"""Yazı tipi seçici: arama kutusu + her adı kendi yazı tipiyle gösteren liste.
Sıra: varsayılan, yazıt ile gelenler, kullanıcının eklediği, bilgisayarda kurulu olanlar.
Menüye QWidgetAction olarak konur; seçilince picked(aile) yayar ("" = varsayılan), "Yazı tipi ekle…" add_font yayar."""
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QPushButton

from . import fonts, icons
from .i18n import t
from .theme import qcolor

ROLE_FAM = Qt.ItemDataRole.UserRole
ROLE_HEAD = Qt.ItemDataRole.UserRole + 1


class FontPicker(QWidget):
    picked = pyqtSignal(str)
    add_font = pyqtSignal()

    def __init__(self, current="", parent=None):
        super().__init__(parent)
        self.setObjectName("FontPicker")
        self.current = current or ""
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(6)
        self.search = QLineEdit()
        self.search.setObjectName("FontSearch")
        self.search.setPlaceholderText(t("font_search"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        self.search.returnPressed.connect(self._enter)
        lay.addWidget(self.search)
        self.list = QListWidget()
        self.list.setObjectName("FontList")
        self.list.setFixedSize(280, 340)
        self.list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.itemClicked.connect(self._clicked)
        lay.addWidget(self.list)
        add = QPushButton(t("font_add"))
        add.setObjectName("FontAdd")
        add.setIcon(icons.icon("add", qcolor("text2").name(), 18))
        add.setCursor(Qt.CursorShape.PointingHandCursor)
        add.clicked.connect(self.add_font.emit)
        lay.addWidget(add)
        self._fill()
        QTimer.singleShot(0, self.search.setFocus)

    def _head(self, text):
        it = QListWidgetItem(text)
        it.setFlags(Qt.ItemFlag.NoItemFlags)
        it.setData(ROLE_HEAD, True)
        f = QFont(self.font())
        f.setPixelSize(11)
        f.setWeight(QFont.Weight.DemiBold)
        it.setFont(f)
        it.setForeground(qcolor("text3"))
        self.list.addItem(it)

    def _row(self, fam, label=None):
        it = QListWidgetItem(label or fam)
        it.setIcon(icons.icon("check" if fam == self.current else "blank", qcolor("text").name(), 16))
        it.setData(ROLE_FAM, fam)
        it.setToolTip(fam or t("font_default"))
        f = fonts.font(fam) if fam else QFont(self.font())
        f.setPixelSize(16)
        it.setFont(f)
        self.list.addItem(it)
        if fam == self.current:
            self.list.setCurrentItem(it)
        return it

    def _fill(self):
        self.list.clear()
        self._row("", t("font_default"))
        for title, fams in ((t("font_bundled"), fonts.bundled()), (t("font_user"), fonts.user_fonts()),
                            (t("font_system"), fonts.system_fonts())):
            if fams:
                self._head(title)
                for fam in fams:
                    self._row(fam)
        cur = self.list.currentItem()
        if cur is not None:
            QTimer.singleShot(0, lambda: self.list.scrollToItem(cur, QListWidget.ScrollHint.PositionAtCenter))

    def _filter(self, q):
        q = q.strip().lower()
        last_head = None
        visible_in_section = False
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.data(ROLE_HEAD):
                if last_head is not None:
                    last_head.setHidden(bool(q) and not visible_in_section)
                last_head, visible_in_section = it, False
                continue
            fam = it.data(ROLE_FAM) or ""
            show = not q or q in (fam or t("font_default")).lower()
            it.setHidden(not show)
            visible_in_section = visible_in_section or show
        if last_head is not None:
            last_head.setHidden(bool(q) and not visible_in_section)

    def first_visible(self):
        for i in range(self.list.count()):
            it = self.list.item(i)
            if not it.isHidden() and not it.data(ROLE_HEAD):
                return it
        return None

    def _enter(self):
        it = self.first_visible()
        if it is not None:
            self.picked.emit(it.data(ROLE_FAM) or "")

    def _clicked(self, it):
        if not it.data(ROLE_HEAD):
            self.picked.emit(it.data(ROLE_FAM) or "")
