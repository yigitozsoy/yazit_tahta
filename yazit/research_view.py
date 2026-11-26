"""Araştırma modu — görünüm: solda raf, ortada sekmeler (ilki araştırma sayfası), sağda hızlı notlar.

Araştırma açık değilken ana ekran: son araştırmalar + "Yeni araştırma" / "Klasör aç"."""
import math
import os
import random
import re
from urllib.parse import quote as urlquote, unquote, parse_qs

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QRectF, QSize, QPoint, QPointF
from PyQt6.QtGui import (QPainter, QPainterPath, QPen, QFontMetricsF, QTextOption, QKeySequence, QShortcut, QTextCursor,
                         QTextTableFormat, QTextFrameFormat, QTextCharFormat, QTextBlockFormat, QTextLength, QBrush,
                         QColor)
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QSplitter, QTabBar,
                             QStackedWidget, QLineEdit, QTextEdit, QPushButton, QFileDialog, QInputDialog, QMenu,
                             QFrame, QSizePolicy)

from . import kamuglink
from .config import prefs, research_root
from .i18n import t
from .research import Research, recent, remember, forget, new_research, peek
from .readers import open_reader, PdfView, TranscriptView, fmt_time
from .shelf import Shelf, rp, qc, font, ff, head, cap


def qss():
    P = rp()
    disp, body, lab, mono, hand = (ff(k, P) for k in ("f_display", "f_body", "f_label", "f_mono", "f_hand"))
    up = P["upper"]
    rad = max(8, P["r_card"] + 4) if P["r_card"] else 8
    return f"""
QWidget#Research, QWidget#RsHome, QWidget#RsCenter {{ background: {P['bg']}; }}
QWidget#RsSide {{ background: {P['panel']}; }}
QScrollArea#RsScroll {{ background: transparent; border: none; }}
QScrollArea#RsScroll > QWidget > QWidget {{ background: transparent; }}
QLabel#RsHead {{ color: {P['muted']}; font-family: {lab}; font-size: 11px; font-weight: 600;
    letter-spacing: {P['label_sp']}px; }}
QLabel#RsMeta {{ color: {P['muted']}; font-family: {lab}; font-size: 11.5px; font-weight: 500;
    letter-spacing: {1.2 if up else 0.4}px; }}
QLabel#RsBig {{ color: {P['text']}; font-family: {disp}; font-size: {P['head_px']}px; font-weight: 600;
    letter-spacing: {0.6 if up else 0}px; }}
QLabel#RsRecentTitle {{ color: {P['text']}; font-family: {disp}; font-size: {19 if up else 17}px; font-weight: {500 if up else 600};
    letter-spacing: {0.4 if up else 0}px; }}
QLabel#RsSub {{ color: {P['muted']}; font-family: {body}; font-size: 13.5px; }}
QLineEdit#RsTitle {{ background: transparent; border: none; color: {P['text']}; padding: 0;
    font-family: {disp}; font-size: {P['title_px']}px; font-weight: 600; }}
QTextEdit#RsBody {{ background: transparent; border: none; color: {P['text']}; font-family: {body};
    font-size: 17px;
    selection-background-color: {P['ink']}; selection-color: {P['on_ink']}; }}
QLineEdit#RsNoteIn {{ background: {P['bg']}; border: 1px solid {P['faint']}; border-radius: {rad}px; color: {P['ink']};
    padding: 4px 10px; font-family: {hand}; font-size: {P['hand_px']}px; font-weight: 600; }}
QLineEdit#RsNoteIn:focus {{ border-color: {P['ink']}; }}
QPushButton#RsBtn {{ background: transparent; color: {P['text']}; border: 1px solid {P['faint']}; border-radius: {rad}px;
    padding: 9px 16px; font-family: {lab}; font-size: {12 if up else 13}px; font-weight: 600;
    letter-spacing: {0.8 if up else 0}px; }}
QPushButton#RsBtn:hover {{ border-color: {P['ink']}; color: {P['ink']}; }}
QPushButton#RsBtnMain {{ background: {P['ink']}; color: {P['on_ink']}; border: none; border-radius: {rad}px;
    padding: 10px 18px; font-family: {lab}; font-size: {12 if up else 13}px; font-weight: 700;
    letter-spacing: {0.8 if up else 0}px; }}
QPushButton#RsBtnMain:hover {{ background: {qc(P['ink']).lighter(112).name()}; }}
QPushButton#RsIcon {{ background: transparent; border: none; border-radius: 6px; color: {P['muted']};
    font-family: {mono}; font-size: 15px; min-width: 26px; max-width: 26px; min-height: 26px; padding: 0; }}
QPushButton#RsIcon:hover {{ background: {P['faint']}; color: {P['text']}; }}
QLineEdit#RsFind {{ background: {P['bg']}; border: 1px solid {P['faint']}; border-radius: {rad}px; color: {P['text']};
    padding: 6px 10px; font-family: {body}; font-size: 13px; }}
QLineEdit#RsFind:focus {{ border-color: {P['ink']}; }}
QFrame#RsHit {{ background: {P['bg']}; border: 1px solid {P['faint']}; border-radius: {rad}px; }}
QFrame#RsHit:hover {{ border-color: {P['muted']}; }}
QLabel#RsHitTitle {{ color: {P['text']}; font-family: {body}; font-size: 13px; font-weight: 600; background: transparent; }}
QLabel#RsHitMeta {{ color: {P['muted']}; font-family: {body}; font-size: 11.5px; background: transparent; }}
QLabel#RsBadge {{ color: {P['muted']}; font-family: {lab}; font-size: 10px; font-weight: 600;
    letter-spacing: {P['label_sp']}px; background: transparent; }}
QPushButton#RsHitBtn {{ background: {P['ink']}; color: {P['on_ink']}; border: none; border-radius: {max(4, rad - 2)}px;
    padding: 4px 10px; font-family: {lab}; font-size: 11.5px; font-weight: 700; }}
QPushButton#RsHitBtn:hover {{ background: {qc(P['ink']).lighter(112).name()}; }}
QPushButton#RsHitBtn:disabled {{ background: transparent; color: {P['muted']}; border: 1px solid {P['faint']}; }}
QTabBar#RsTabs {{ background: {P['panel']}; }}
QTabBar#RsTabs::tab {{ background: transparent; color: {P['muted']}; padding: 9px 14px 8px 14px; border: none;
    border-bottom: 2px solid transparent; font-family: {lab}; font-size: {11.5 if up else 12.5}px; font-weight: 600; }}
QTabBar#RsTabs::tab:selected {{ color: {P['text']}; border-bottom-color: {P['ink']}; background: {P['bg']}; }}
QTabBar#RsTabs::tab:hover:!selected {{ color: {P['text']}; }}
QSplitter#RsSplit::handle {{ background: {P['faint']}; }}
QPushButton#RsRecent {{ background: {P['panel']}; border: 1px solid transparent; border-radius: {rad + 2}px; text-align: left;
    padding: 14px 16px; color: {P['text']}; }}
QPushButton#RsRecent:hover {{ border-color: {P['ink']}; }}
QPushButton#RsToc {{ background: transparent; border: none; text-align: left; color: {P['text']};
    padding: 3px 0; font-family: {body}; font-size: 14px; }}
QPushButton#RsToc:hover {{ color: {P['ink']}; }}
QWidget#RsTocBox {{ border-left: 1px solid {P['faint']}; }}
QLabel#RsPageNo {{ color: {P['muted']}; font-family: {mono}; font-size: 11px; padding: 0 12px; }}
QFrame#RsRule {{ background: {P['red']}; max-width: 56px; border: none; }}
"""


# --------------------------------------------------------------------------- notlar
class NoteCard(QWidget):
    """El yazısıyla (Caveat) sarı mürekkep not, hafif eğik."""
    removed = pyqtSignal(str)

    hovered = pyqtSignal(str, bool)

    def __init__(self, note, parent=None):
        super().__init__(parent)
        self.note = note
        self.hot = False
        self.top = 18 if note.get("anchor") else 0
        self.restyle()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._menu)

    def restyle(self):
        """Yazı tipi / eğim temadan (kamuflaj Caveat, soft Patrick Hand, yazıt düz)."""
        P = rp()
        self.f = font(P["f_hand"], P["hand_px"], 600 if P["tilt"] else 400)
        self.fa = font(P["f_label"], 9.5, 600, P["label_sp"])
        self.ang = (-1.2 if hash(self.note.get("id", "")) % 2 else 0.9) if P["tilt"] else 0.0
        if self.width():
            self.setFixedHeight(self.heightForWidth(self.width()))
        self.update()

    def _text_rect(self, w):
        fm = QFontMetricsF(self.f)
        return fm.boundingRect(QRectF(0, 0, max(40, w - 18), 4000), int(Qt.TextFlag.TextWordWrap),
                               self.note.get("text", ""))

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return int(self._text_rect(w).height() + 16 + self.top)

    def enterEvent(self, e):
        self.hovered.emit(self.note.get("id", ""), True)

    def leaveEvent(self, e):
        self.hovered.emit(self.note.get("id", ""), False)

    def set_hot(self, on):
        if on != self.hot:
            self.hot = on
            self.update()

    def sizeHint(self):
        w = self.width() or 240
        return QSize(w, self.heightForWidth(w))

    def resizeEvent(self, e):
        h = self.heightForWidth(self.width())
        if self.height() != h:
            self.setFixedHeight(h)
        super().resizeEvent(e)

    def paintEvent(self, e):
        P = rp()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        if self.hot:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(qc(P["ink"], 18))
            p.drawRoundedRect(QRectF(self.rect()).adjusted(2, 0, -2, 0), 8, 8)
        a = (self.note.get("anchor") or {}).get("text", "")
        if a:
            p.setFont(self.fa)
            p.setPen(qc(P["muted"]))
            p.drawText(QRectF(10, 4, self.width() - 20, 14), Qt.AlignmentFlag.AlignVCenter,
                       QFontMetricsF(self.fa).elidedText("↳ " + cap(a, P), Qt.TextElideMode.ElideRight,
                                                         self.width() - 20))
        p.translate(8, 6 + self.top)
        p.rotate(self.ang)
        p.setFont(self.f)
        p.setPen(qc(P["ink"]))
        r = self._text_rect(self.width())
        p.drawText(QRectF(0, 0, max(40, self.width() - 18), r.height() + 4), int(Qt.TextFlag.TextWordWrap),
                   self.note.get("text", ""))

    def _menu(self, pos):
        m = QMenu(self)
        m.addAction(t("delete_note"), lambda: self.removed.emit(self.note.get("id", "")))
        m.exec(self.mapToGlobal(pos))


class NotesColumn(QWidget):
    added = pyqtSignal(dict)           # yeni not (bağlıysa research_view kelimeyi işaretler)
    removed = pyqtSignal(str)
    hover = pyqtSignal(str, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pending = None            # bağlanacak kelime (metin)
        self.cards = {}
        self.setObjectName("RsSide")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.research = None
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 14, 0, 12)
        v.setSpacing(8)
        self.head = QLabel()
        self.head.setObjectName("RsHead")
        self.head.setContentsMargins(18, 0, 18, 0)
        v.addWidget(self.head)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("RsScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.inner = QWidget()
        self.lay = QVBoxLayout(self.inner)
        self.lay.setContentsMargins(10, 4, 10, 4)
        self.lay.setSpacing(10)
        self.lay.addStretch(1)
        self.scroll.setWidget(self.inner)
        v.addWidget(self.scroll, 1)
        self.empty = QLabel(t("rs_no_notes"))
        self.empty.setWordWrap(True)
        self.empty.setObjectName("RsSub")
        self.empty.setContentsMargins(18, 0, 18, 0)
        v.addWidget(self.empty)
        self.inp = QLineEdit()
        self.inp.setObjectName("RsNoteIn")
        self.inp.setPlaceholderText(t("rs_note_ph"))
        self.inp.returnPressed.connect(self._add)
        self.inp.installEventFilter(self)
        box = QHBoxLayout()
        box.setContentsMargins(12, 0, 12, 0)
        box.addWidget(self.inp)
        v.addLayout(box)

    def set_research(self, r):
        self.research = r
        self.refresh()

    def refresh(self):
        while self.lay.count() > 1:
            w = self.lay.takeAt(0).widget()
            if w:
                w.hide()
                w.deleteLater()
        notes = self.research.notes if self.research else []
        self.cards = {}
        for n in notes:
            c = NoteCard(n)
            c.removed.connect(self._remove)
            c.hovered.connect(self.hover.emit)
            self.cards[n.get("id", "")] = c
            self.lay.insertWidget(self.lay.count() - 1, c)
        self.head.setText(f"{head(t('rs_notes'))} · {len(notes)}")
        self.empty.setVisible(not notes)
        QTimer.singleShot(0, lambda: self.scroll.verticalScrollBar().setValue(
            self.scroll.verticalScrollBar().maximum()))

    def restyle(self):
        self.head.setText(f"{head(t('rs_notes'))} · {len(self.research.notes if self.research else [])}")
        for c in self.cards.values():
            c.restyle()

    def _add(self):
        txt = self.inp.text().strip()
        if not txt or self.research is None:
            return
        n = self.research.add_note(txt, {"text": self.pending} if self.pending else None)
        self.inp.clear()
        self.end_anchor()
        self.refresh()
        self.added.emit(n)

    def begin_anchor(self, word):
        self.pending = word
        self.inp.setPlaceholderText(t("rs_attach_ph").format(w=word[:40]))
        self.inp.setFocus()

    def end_anchor(self):
        self.pending = None
        self.inp.setPlaceholderText(t("rs_note_ph"))

    def eventFilter(self, obj, e):
        from PyQt6.QtCore import QEvent
        if obj is self.inp and e.type() == QEvent.Type.KeyPress and e.key() == Qt.Key.Key_Escape and self.pending:
            self.end_anchor()
            self.added.emit({})        # bekleyen işareti bırak
            return True
        return super().eventFilter(obj, e)

    def _remove(self, nid):
        if self.research:
            QTimer.singleShot(0, lambda: (self.research.remove_note(nid), self.refresh(), self.removed.emit(nid)))

    def show_note(self, nid):
        c = self.cards.get(nid)
        if c is not None:
            self.scroll.ensureWidgetVisible(c, 0, 40)
            c.set_hot(True)
            QTimer.singleShot(1200, lambda: c.set_hot(False) if c in self.cards.values() else None)


# --------------------------------------------------------------------------- araştırma sayfası
class GrowEdit(QTextEdit):
    """Yüksekliği içeriğe göre büyüyen metin alanı (sayfanın kendisi kayar).
    Alıntı künyesine tıklamak link_clicked; Ctrl+1 / Ctrl+2 başlık, Ctrl+0 düz metin."""
    link_clicked = pyqtSignal(str)
    attach_req = pyqtSignal()
    note_hover = pyqtSignal(str)          # üstündeki bağlı notun kimliği ("" = yok)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.viewport().setMouseTracking(True)
        self._hover_note = ""
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.document().documentLayout().documentSizeChanged.connect(self._fit)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def _fit(self, *_):
        h = int(self.document().size().height()) + 8
        self.setFixedHeight(max(220, h))

    def mouseMoveEvent(self, e):
        a = self.anchorAt(e.position().toPoint())
        self.viewport().setCursor(Qt.CursorShape.PointingHandCursor if a.startswith(("delta-src:", "delta-note:"))
                                  else Qt.CursorShape.IBeamCursor)
        nid = a[len("delta-note:"):] if a.startswith("delta-note:") else ""
        if nid != self._hover_note:
            self._hover_note = nid
            self.note_hover.emit(nid)
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        if self._hover_note:
            self._hover_note = ""
            self.note_hover.emit("")
        super().leaveEvent(e)

    def contextMenuEvent(self, e):
        m = self.createStandardContextMenu(e.pos())
        if self.textCursor().hasSelection():
            first = m.actions()[0] if m.actions() else None
            a = m.addAction(t("rs_attach") + "\tCtrl+M")
            a.triggered.connect(self.attach_req.emit)
            if first is not None:
                m.removeAction(a)
                m.insertAction(first, a)
                m.insertSeparator(first)
        m.exec(e.globalPos())

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        if e.button() == Qt.MouseButton.LeftButton and not self.textCursor().hasSelection():
            a = self.anchorAt(e.position().toPoint())
            if a.startswith(("delta-src:", "delta-note:")):
                self.link_clicked.emit(a)

    def keyPressEvent(self, e):
        if e.modifiers() == Qt.KeyboardModifier.ControlModifier and e.key() == Qt.Key.Key_M:
            if self.textCursor().hasSelection():
                self.attach_req.emit()
            return
        if e.modifiers() == Qt.KeyboardModifier.ControlModifier and e.key() in (Qt.Key.Key_0, Qt.Key.Key_1,
                                                                                  Qt.Key.Key_2):
            self.set_heading({Qt.Key.Key_0: 0, Qt.Key.Key_1: 1, Qt.Key.Key_2: 2}[e.key()])
            return
        super().keyPressEvent(e)
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):    # başlıktan sonra düz metin
            c = self.textCursor()
            if c.blockFormat().headingLevel() and not c.block().text():
                self.set_heading(0)

    def set_heading(self, level):
        c = self.textCursor()
        c.beginEditBlock()
        bf = c.blockFormat()
        bf.setHeadingLevel(level)
        bf.setTopMargin(26 if level else 0)
        bf.setBottomMargin(10 if level else 0)
        c.setBlockFormat(bf)
        cf = QTextCharFormat()
        if level:
            cf.setFontFamilies(rp()["f_display"])
            cf.setProperty(QTextCharFormat.Property.FontPixelSize, 30 if level == 1 else 23)
            cf.setFontWeight(600 if level == 1 else 500)
        else:
            cf.setFontFamilies(rp()["f_body"])
            cf.setProperty(QTextCharFormat.Property.FontPixelSize, 17)
            cf.setFontWeight(400)
        sel = QTextCursor(c.block())
        sel.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
        sel.mergeCharFormat(cf)
        c.mergeBlockCharFormat(cf)
        c.endEditBlock()
        self.setTextCursor(c)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._fit()


class ResearchPage(QScrollArea):
    """Araştırmanın kendi sayfası: büyük başlık, mono bilgi satırı, metin."""
    MAXW = 760

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RsScroll")
        self.setWidgetResizable(True)
        self.research = None
        inner = QWidget()
        inner.setObjectName("RsCenter")
        outer = QHBoxLayout(inner)
        outer.setContentsMargins(24, 0, 24, 0)
        col = QWidget()
        col.setMaximumWidth(self.MAXW)
        v = QVBoxLayout(col)
        v.setContentsMargins(0, 44, 0, 80)
        v.setSpacing(0)
        self.title = QLineEdit()
        self.title.setObjectName("RsTitle")
        self.title.setPlaceholderText(t("rs_title_ph"))
        self.title.editingFinished.connect(self._title_done)
        v.addWidget(self.title)
        self.meta = QLabel()
        self.meta.setObjectName("RsMeta")
        v.addSpacing(10)
        v.addWidget(self.meta)
        v.addSpacing(16)
        rule = QFrame()
        rule.setFixedHeight(2)
        rule.setObjectName("RsRule")
        v.addWidget(rule)
        v.addSpacing(22)
        self.toc = QWidget()
        self.toc.setObjectName("RsTocBox")
        self.toc.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.toc_lay = QVBoxLayout(self.toc)
        self.toc_lay.setContentsMargins(16, 2, 0, 2)
        self.toc_lay.setSpacing(0)
        self.toc.hide()
        v.addWidget(self.toc)
        self.toc_gap = v.count()
        v.addSpacing(26)
        self.body = GrowEdit()
        self.body.setObjectName("RsBody")
        self.body.document().setDocumentMargin(0)
        self.body.setPlaceholderText(t("rs_body_ph"))
        self._save = QTimer(self, singleShot=True, interval=500, timeout=self._save_body)
        self.body.textChanged.connect(self._save.start)
        self._toc_t = QTimer(self, singleShot=True, interval=350, timeout=self.update_toc)
        self.body.textChanged.connect(self._toc_t.start)
        self._quote_steps = -1
        v.addWidget(self.body)
        v.addStretch(1)
        outer.addStretch(1)
        outer.addWidget(col, 100)
        outer.addStretch(1)
        self.setWidget(inner)

    def set_research(self, r):
        self.research = r
        self.title.setText(r.title)
        self.body.blockSignals(True)
        self.body.setHtml(r.page.get("html", "")) if r.page.get("html") else self.body.clear()
        self.body.blockSignals(False)
        self.normalize()
        self.body.document().clearUndoRedoStacks()
        self._quote_steps = -1
        self.update_toc()
        self.update_meta()

    def words(self):
        return len(re.findall(r"\w+", self.body.toPlainText()))

    def update_meta(self):
        if self.research:
            self.meta.setText(self.research.meta_line(self.words()))

    def _title_done(self):
        if self.research:
            self.research.set_title(self.title.text())

    # ---- içindekiler
    def headings(self):
        out = []
        b = self.body.document().begin()
        while b.isValid():
            lv = b.blockFormat().headingLevel()
            if lv and b.text().strip():
                out.append((lv, b.text().strip(), b.position()))
            b = b.next()
        return out

    def update_toc(self):
        while self.toc_lay.count():
            w = self.toc_lay.takeAt(0).widget()
            if w:
                w.hide()
                w.deleteLater()
        hs = self.headings()
        self.toc.setVisible(len(hs) >= 1)
        if hs:
            hl = QLabel(head(t('rs_toc')))
            hl.setObjectName("RsHead")
            self.toc_lay.addWidget(hl)
            self.toc_lay.addSpacing(4)
        n1 = 0
        for lv, text, pos in hs:
            if lv == 1:
                n1 += 1
            b = QPushButton(("" if lv == 1 else "      ") + (f"{n1:02d}   " if lv == 1 else "") + text)
            b.setObjectName("RsToc")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(lambda _=False, pos=pos: self.scroll_to(pos))
            self.toc_lay.addWidget(b)
        if self.research is not None:
            sec = sum(1 for lv, _t, _p in hs if lv == 1)
            if self.research.page.get("sections", 0) != sec:
                self.research.page["sections"] = sec
                self.update_meta()

    def scroll_to(self, pos):
        c = QTextCursor(self.body.document())
        c.setPosition(pos)
        y = self.body.cursorRect(c).top()
        y = self.body.mapTo(self.widget(), self.body.viewport().mapTo(self.body, QPoint(0, y))).y()
        self.verticalScrollBar().setValue(max(0, y - 40))
        self.body.setTextCursor(c)
        self.body.setFocus()

    # ---- alıntı
    def add_quote(self, text, cite, href):
        """Alıntı kartı (solda kırmızı çizgi, italik metin, altında tıklanır künye). Tek geri al adımı."""
        P = rp()
        doc = self.body.document()
        c = QTextCursor(doc)
        c.movePosition(QTextCursor.MoveOperation.End)
        c.beginEditBlock()
        if not doc.isEmpty():
            c.insertBlock(QTextBlockFormat(), QTextCharFormat())
        tf = QTextTableFormat()
        tf.setBorder(0)
        tf.setBorderCollapse(True)
        tf.setCellPadding(0)
        tf.setCellSpacing(0)
        tf.setWidth(QTextLength(QTextLength.Type.PercentageLength, 100))
        tf.setTopMargin(6)
        tf.setBottomMargin(6)
        tb = c.insertTable(1, 1, tf)
        cell = tb.cellAt(0, 0)
        cf = cell.format().toTableCellFormat()
        cf.setLeftBorder(3)
        cf.setLeftBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Solid)
        cf.setLeftBorderBrush(QBrush(QColor(P["red"])))
        cf.setLeftPadding(18)
        cf.setRightPadding(16)
        cf.setTopPadding(12)
        cf.setBottomPadding(12)
        cf.setBackground(QBrush(QColor(P["panel"])))
        cell.setFormat(cf)
        cc = cell.firstCursorPosition()
        qf = QTextCharFormat()
        qf.setFontItalic(True)
        qf.setFontFamilies(P["f_quote"])
        qf.setProperty(QTextCharFormat.Property.FontPixelSize, 17)
        qf.setForeground(QBrush(QColor(P["text"])))
        cc.insertText("“" + text.strip() + "”", qf)
        bf = QTextBlockFormat()
        bf.setTopMargin(8)
        cc.insertBlock(bf)
        af = QTextCharFormat()
        af.setAnchor(True)
        af.setAnchorHref(href)
        af.setFontUnderline(False)
        af.setFontFamilies(P["f_mono"])
        af.setProperty(QTextCharFormat.Property.FontPixelSize, 11)
        af.setFontWeight(600)
        af.setFontLetterSpacingType(af.fontLetterSpacingType().AbsoluteSpacing)
        af.setFontLetterSpacing(1.0)
        af.setForeground(QBrush(QColor(P["ink"])))
        cc.insertText("— " + cap(cite, P), af)
        c.movePosition(QTextCursor.MoveOperation.End)
        c.insertBlock(QTextBlockFormat(), QTextCharFormat())
        c.endEditBlock()
        self._quote_steps = doc.availableUndoSteps()
        QTimer.singleShot(0, lambda: self.ensureVisible(0, self.widget().height(), 0, 0))
        return True

    def normalize(self):
        """HTML'den yüklenince Qt bağlantıların altını çizip mavi yapar: künye mürekkep rengi, bağlı kelime metin
        rengi, alt çizgisiz (temaya göre)."""
        P = rp()
        doc = self.body.document()
        edits = []
        b = doc.begin()
        while b.isValid():
            it = b.begin()
            while not it.atEnd():
                fr = it.fragment()
                if fr.isValid():
                    h = fr.charFormat().anchorHref()
                    if h.startswith(("delta-src:", "delta-note:")):
                        edits.append((fr.position(), fr.position() + fr.length(), h.startswith("delta-src:")))
                it += 1
            b = b.next()
        # alıntı kartları (tek hücreli tablolar): zemin / metin temaya göre
        from PyQt6.QtGui import QTextTable
        cards = []
        it = doc.rootFrame().begin()
        while not it.atEnd():
            fr = it.currentFrame()
            if isinstance(fr, QTextTable) and fr.rows() == 1 and fr.columns() == 1:
                cards.append(fr.cellAt(0, 0))
            it += 1
        blocked = self.body.blockSignals(True)
        for cell in cards:
            cf = cell.format().toTableCellFormat()
            cf.setBackground(QBrush(QColor(P["panel"])))
            cf.setLeftBorderBrush(QBrush(QColor(P["red"])))
            cell.setFormat(cf)
            # HTML'e gömülen eski tema renklerini (paragraf / yazı zemini, yazı rengi) at
            blk = cell.firstCursorPosition().block()
            last = cell.lastCursorPosition().block().blockNumber()
            while blk.isValid() and blk.blockNumber() <= last:
                bc = QTextCursor(blk)
                bf = blk.blockFormat()
                bf.clearBackground()
                bc.setBlockFormat(bf)
                frs = []
                fit = blk.begin()
                while not fit.atEnd():
                    if fit.fragment().isValid():
                        frs.append(fit.fragment())
                    fit += 1
                for fr in frs:
                    f = fr.charFormat()
                    f.clearBackground()
                    f.setForeground(QBrush(QColor(P["text"])))   # künye aşağıda yeniden mürekkep olur
                    f.setFontFamilies(P["f_mono"] if f.anchorHref().startswith("delta-src:") else P["f_quote"])
                    fc = QTextCursor(doc)
                    fc.setPosition(fr.position())
                    fc.setPosition(fr.position() + fr.length(), QTextCursor.MoveMode.KeepAnchor)
                    fc.setCharFormat(f)
                blk = blk.next()
        # kart dışı: başlıklar temanın başlık, metin temanın metin yazı tipiyle
        b = doc.begin()
        while b.isValid():
            bc = QTextCursor(b)
            if bc.currentTable() is None and b.length() > 1:
                bc.movePosition(QTextCursor.MoveOperation.EndOfBlock, QTextCursor.MoveMode.KeepAnchor)
                cf = QTextCharFormat()
                cf.setFontFamilies(P["f_display"] if b.blockFormat().headingLevel() else P["f_body"])
                bc.mergeCharFormat(cf)
            b = b.next()
        for a, z, src in edits:
            c = QTextCursor(doc)
            c.setPosition(a)
            c.setPosition(z, QTextCursor.MoveMode.KeepAnchor)
            cf = QTextCharFormat()
            cf.setFontUnderline(False)
            cf.setForeground(QBrush(QColor(P["ink"] if src else P["text"])))
            c.mergeCharFormat(cf)
        self.body.blockSignals(blocked)

    # ---- bağlı notlar
    def mark_note(self, cursor, nid):
        """Seçili kelimeyi nota bağla (görünüşü değişmez; halka + ok üst katmanda çizilir)."""
        cf = QTextCharFormat()
        cf.setAnchor(True)
        cf.setAnchorHref("delta-note:" + nid)
        cf.setFontUnderline(False)
        cf.setForeground(QBrush(QColor(rp()["text"])))
        cursor.mergeCharFormat(cf)

    def unmark_note(self, nid):
        for a, b in self.note_ranges().get(nid, []):
            c = QTextCursor(self.body.document())
            c.setPosition(a)
            c.setPosition(b, QTextCursor.MoveMode.KeepAnchor)
            cf = QTextCharFormat()
            cf.setAnchor(False)
            cf.setAnchorHref("")
            c.mergeCharFormat(cf)

    def note_ranges(self):
        """{not kimliği: [(başlangıç, bitiş)]} — gövdede bağlı kelimelerin yeri."""
        out = {}
        b = self.body.document().begin()
        while b.isValid():
            it = b.begin()
            while not it.atEnd():
                fr = it.fragment()
                if fr.isValid():
                    h = fr.charFormat().anchorHref()
                    if h.startswith("delta-note:"):
                        nid = h[len("delta-note:"):]
                        lst = out.setdefault(nid, [])
                        if lst and lst[-1][1] == fr.position():
                            lst[-1] = (lst[-1][0], fr.position() + fr.length())
                        else:
                            lst.append((fr.position(), fr.position() + fr.length()))
                it += 1
            b = b.next()
        return out

    def word_rect(self, a, b):
        """[a, b) aralığının gövdedeki dikdörtgeni (body.viewport koordinatı; ilk satır)."""
        c = QTextCursor(self.body.document())
        c.setPosition(a)
        r1 = self.body.cursorRect(c)
        c.setPosition(b)
        r2 = self.body.cursorRect(c)
        if r2.top() > r1.top() + 2:          # satır kaydı: ilk satırın sonuna kadar
            c.setPosition(a)
            c.movePosition(QTextCursor.MoveOperation.EndOfLine)
            r2 = self.body.cursorRect(c)
        return QRectF(r1.left(), r1.top(), max(6, r2.left() - r1.left()), r1.height())

    def undo_quote(self):
        """Okuyucuda Ctrl+Z: son eklenen alıntı hâlâ son adımsa geri al."""
        doc = self.body.document()
        if self._quote_steps > 0 and doc.availableUndoSteps() == self._quote_steps:
            doc.undo()
            self._quote_steps = -1
            return True
        return False

    def _save_body(self):
        if self.research is None:
            return
        doc = self.body.document()
        self.research.page["html"] = self.body.toHtml() if not doc.isEmpty() else ""
        self.research.touch()
        self.update_meta()

    def flush(self):
        if self._save.isActive():
            self._save.stop()
            self._save_body()


class NoteLinks(QWidget):
    """Araştırma sayfasındaki bağlı kelimenin çevresine elle çizilmiş halka, oradan nota kavisli ok.
    Varsayılan soluk; kelimenin ya da notun üstüne gelince belirginleşir (sitedeki kenar notları gibi)."""

    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.hot = ""
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)

    def set_hot(self, nid):
        if nid != self.hot:
            self.hot = nid
            self.update()

    @staticmethod
    def ring(r, seed):
        """Kaba, elle çizilmiş halka: biraz eğik, uçları üst üste binen elips."""
        rnd = random.Random(seed)
        cx, cy = r.center().x(), r.center().y()
        rx, ry = r.width() / 2 + 7, r.height() / 2 + 4
        tilt = math.radians(rnd.uniform(-4, 4))
        a0 = math.radians(rnd.uniform(150, 210))
        path = QPainterPath()
        n = 40
        for k in range(n + 6):
            a = a0 + k / n * 2 * math.pi
            j = 1 + 0.06 * math.sin(k * 0.9 + seed % 7) + (k / n) * 0.08
            x, y = rx * j * math.cos(a), ry * j * math.sin(a)
            px = cx + x * math.cos(tilt) - y * math.sin(tilt)
            py = cy + x * math.sin(tilt) + y * math.cos(tilt)
            path.moveTo(px, py) if k == 0 else path.lineTo(px, py)
        return path

    def paintEvent(self, e):
        v = self.view
        if v.research is None or v.pages.currentWidget() is not v.page or not v.notes.isVisible():
            return
        page = v.page
        body = page.body
        ranges = page.note_ranges()
        if not ranges:
            return
        P = rp()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pv = page.viewport()
        top_left = pv.mapTo(v, QPoint(0, 0))
        nv = v.notes.scroll.viewport()
        n_tl = nv.mapTo(v, QPoint(0, 0))
        clip = QRectF(top_left.x(), max(top_left.y(), n_tl.y()), n_tl.x() + nv.width() - top_left.x(),
                      min(pv.height(), nv.height()))
        p.setClipRect(clip)
        line = qc(P["ink"])
        for nid, rs in ranges.items():
            card = v.notes.cards.get(nid)
            hot = nid == self.hot
            col = QColor(line)
            col.setAlphaF(0.85 if hot else 0.32)
            pen = QPen(col, 1.8 if hot else 1.25)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            a, b = rs[0]
            wr = page.word_rect(a, b)
            tl = body.viewport().mapTo(v, QPoint(int(wr.left()), int(wr.top())))
            wr = QRectF(tl.x(), tl.y(), wr.width(), wr.height())
            seed = sum(ord(ch) for ch in nid)
            p.drawPath(self.ring(wr, seed))
            if card is None or not card.isVisible():
                continue
            ctl = card.mapTo(v, QPoint(0, 0))
            end = QPointF(ctl.x() + 4, ctl.y() + card.top + 16)
            start = QPointF(wr.right() + 9, wr.center().y())
            if not clip.contains(end):
                end.setY(max(clip.top() + 8, min(clip.bottom() - 8, end.y())))
            dx = end.x() - start.x()
            c1 = QPointF(start.x() + dx * 0.35, start.y() - 28 - abs(end.y() - start.y()) * 0.08)
            c2 = QPointF(end.x() - dx * 0.3, end.y() + 18)
            path = QPainterPath(start)
            path.cubicTo(c1, c2, end)
            p.drawPath(path)
            ang = math.atan2(end.y() - c2.y(), end.x() - c2.x())
            for s_ in (-1, 1):
                a2 = ang + math.pi + s_ * 0.45
                p.drawLine(end, QPointF(end.x() + 8 * math.cos(a2), end.y() + 8 * math.sin(a2)))


# --------------------------------------------------------------------------- ana ekran
class Home(QWidget):
    open_folder = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("RsHome")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        outer = QHBoxLayout(self)
        outer.addStretch(1)
        col = QWidget()
        col.setFixedWidth(620)
        self.v = QVBoxLayout(col)
        self.v.setContentsMargins(0, 60, 0, 40)
        self.v.setSpacing(0)
        self.kick = kick = QLabel()
        kick.setObjectName("RsMeta")
        self.v.addWidget(kick)
        self.v.addSpacing(8)
        self.big = big = QLabel()
        big.setObjectName("RsBig")
        self.v.addWidget(big)
        sub = QLabel(t("rs_home_sub"))
        sub.setObjectName("RsSub")
        sub.setWordWrap(True)
        self.v.addSpacing(6)
        self.v.addWidget(sub)
        self.v.addSpacing(22)
        row = QHBoxLayout()
        row.setSpacing(10)
        self.b1 = b1 = QPushButton()
        b1.setObjectName("RsBtnMain")
        b1.setCursor(Qt.CursorShape.PointingHandCursor)
        b1.clicked.connect(self._new)
        self.b2 = b2 = QPushButton()
        b2.setObjectName("RsBtn")
        b2.setCursor(Qt.CursorShape.PointingHandCursor)
        b2.clicked.connect(self._open)
        row.addWidget(b1)
        row.addWidget(b2)
        row.addStretch(1)
        self.v.addLayout(row)
        self.v.addSpacing(34)
        self.rec_head = QLabel()
        self.rec_head.setObjectName("RsHead")
        self.v.addWidget(self.rec_head)
        self.v.addSpacing(10)
        self.list = QVBoxLayout()
        self.list.setSpacing(8)
        self.v.addLayout(self.list)
        self.v.addStretch(1)
        outer.addWidget(col)
        outer.addStretch(1)

    def restyle(self):
        P = rp()
        self.kick.setText(head(t("app_name"), P) if P["upper"] else t("app_name"))   # "yazıt" ı'sı kalsın
        self.big.setText(cap(t("rs_home_title"), P))
        self.b1.setText("+  " + cap(t("rs_new"), P))
        self.b2.setText(cap(t("rs_open_folder"), P))
        self.refresh()

    def refresh(self):
        while self.list.count():
            w = self.list.takeAt(0).widget()
            if w:
                w.hide()
                w.deleteLater()
        items = recent()
        self.rec_head.setText(f"{head(t('rs_recent'))} · {len(items)}")
        if not items:
            lb = QLabel(t("rs_none"))
            lb.setObjectName("RsSub")
            self.list.addWidget(lb)
        for d in items[:8]:
            title, n = peek(d)
            b = QPushButton()
            b.setObjectName("RsRecent")
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            lay = QVBoxLayout(b)
            lay.setContentsMargins(16, 10, 16, 10)
            lay.setSpacing(2)
            a = QLabel(cap(title))
            a.setObjectName("RsRecentTitle")
            a.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            meta = d.replace(os.path.expanduser("~"), "~")
            if n is not None:
                meta = cap(t("rs_n_sources").format(n=n)) + "  ·  " + meta
            m = QLabel(QFontMetricsF(font("f_label", 11.5)).elidedText(
                meta, Qt.TextElideMode.ElideMiddle, 560))
            m.setObjectName("RsMeta")
            m.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            lay.addWidget(a)
            lay.addWidget(m)
            b.setMinimumHeight(64)
            b.clicked.connect(lambda _=False, d=d: self.open_folder.emit(d))
            b.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            b.customContextMenuRequested.connect(lambda pos, d=d, b=b: self._menu(d, b.mapToGlobal(pos)))
            self.list.addWidget(b)

    def _menu(self, d, gpos):
        m = QMenu(self)
        m.addAction(t("rs_open_in_explorer"), lambda: os.startfile(d))
        m.addAction(t("rs_forget"), lambda: (forget(d), QTimer.singleShot(0, self.refresh)))
        m.exec(gpos)

    def _new(self):
        name, ok = QInputDialog.getText(self, t("rs_new"), t("rs_new_name"))
        if ok and name.strip():
            self.open_folder.emit(new_research(name.strip()))

    def _open(self):
        d = QFileDialog.getExistingDirectory(self, t("rs_open_folder"), research_root())
        if d:
            self.open_folder.emit(os.path.normpath(d))


# --------------------------------------------------------------------------- görünüm
class ResearchView(QWidget):
    title_changed = pyqtSignal(str)
    toast = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Research")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.research = None
        self.tabs = []           # [(rel, bileşen)]  — 0: araştırma sayfası (rel None)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        lay.addWidget(self.stack)
        self.home = Home()
        self.home.open_folder.connect(self.open)
        self.stack.addWidget(self.home)

        # çalışma alanı
        self.split = QSplitter(Qt.Orientation.Horizontal)
        self.split.setObjectName("RsSplit")
        self.split.setHandleWidth(1)
        self.split.setChildrenCollapsible(False)
        # sol: raf
        left = QWidget()
        left.setObjectName("RsSide")
        left.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(0, 10, 0, 0)
        lv.setSpacing(0)
        hrow = QHBoxLayout()
        hrow.setContentsMargins(16, 0, 8, 4)
        self.shelf_head = QLabel()
        self.shelf_head.setObjectName("RsHead")
        hrow.addWidget(self.shelf_head, 1)
        for txt, tip, fn in (("+", t("rs_add_files"), self._add_files),
                             ("↗", t("rs_open_in_explorer"), lambda: self.research and os.startfile(self.research.folder)),
                             ("×", t("rs_close"), self.close_research)):
            b = QPushButton(txt)
            b.setObjectName("RsIcon")
            b.setToolTip(tip)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(fn)
            hrow.addWidget(b)
        lv.addLayout(hrow)
        self.shelf = Shelf()
        self.shelf.activated.connect(self.open_source)
        self.shelf.files_dropped.connect(self._dropped)
        sc = QScrollArea()
        sc.setObjectName("RsScroll")
        sc.setWidgetResizable(True)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        sc.setWidget(self.shelf)
        lv.addWidget(sc, 1)
        self.split.addWidget(left)
        # orta: sekmeler
        center = QWidget()
        center.setObjectName("RsCenter")
        center.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        cv = QVBoxLayout(center)
        cv.setContentsMargins(0, 0, 0, 0)
        cv.setSpacing(0)
        trow = QHBoxLayout()
        trow.setContentsMargins(0, 0, 0, 0)
        trow.setSpacing(0)
        self.tabbar = QTabBar()
        self.tabbar.setObjectName("RsTabs")
        self.tabbar.setTabsClosable(True)
        self.tabbar.setMovable(True)
        self.tabbar.setExpanding(False)
        self.tabbar.setDocumentMode(True)
        self.tabbar.setElideMode(Qt.TextElideMode.ElideNone)
        self.tabbar.setUsesScrollButtons(True)
        self.tabbar.currentChanged.connect(self._tab_changed)
        self.tabbar.tabCloseRequested.connect(self.close_tab)
        self.tabbar.tabMoved.connect(self._tab_moved)
        trow.addWidget(self.tabbar, 1)
        self.btn_export = QPushButton("⤓")
        self.btn_export.setObjectName("RsIcon")
        self.btn_export.setToolTip(t("rs_export"))
        self.btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn_export.clicked.connect(self._export_menu)
        self.page_no = QLabel()
        self.page_no.setObjectName("RsPageNo")
        trow.addWidget(self.page_no)
        trow.addWidget(self.btn_export)
        trow.addSpacing(8)
        tabwrap = QWidget()
        tabwrap.setObjectName("RsSide")
        tabwrap.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        tabwrap.setLayout(trow)
        cv.addWidget(tabwrap)
        self.pages = QStackedWidget()
        cv.addWidget(self.pages, 1)
        self.page = ResearchPage()
        self.page.body.link_clicked.connect(self.jump)
        self.page.body.attach_req.connect(self._attach)
        self.split.addWidget(center)
        # sağ: notlar
        self.notes = NotesColumn()
        # sağ sütunun üstü: internetten kaynak bul / bağlantı yapıştır (findpanel)
        from .findpanel import FindPanel
        self.finder = FindPanel()
        self.finder.toast.connect(self.toast.emit)
        self.notes.layout().insertWidget(0, self.finder, 0)
        self.notes.layout().insertSpacing(1, 8)
        self.shelf.links_dropped.connect(lambda links: [self.finder.fetch(u) for u in links])
        self.notes.added.connect(self._note_added)
        self.notes.removed.connect(self._note_removed)
        self.split.addWidget(self.notes)
        self.links = NoteLinks(self)
        self.notes.hover.connect(lambda nid, on: self.links.set_hot(nid if on else ""))
        self.page.body.note_hover.connect(self.links.set_hot)
        for sig in (self.page.verticalScrollBar().valueChanged, self.notes.scroll.verticalScrollBar().valueChanged,
                    self.page.body.textChanged, self.split.splitterMoved, self.tabbar.currentChanged):
            sig.connect(lambda *_: self._links_update())
        self._pending_cursor = None
        self.split.setStretchFactor(0, 0)
        self.split.setStretchFactor(1, 1)
        self.split.setStretchFactor(2, 0)
        self.split.splitterMoved.connect(lambda *_: prefs.set("research_split", self.split.sizes()))
        self.stack.addWidget(self.split)
        self._add_tab(None, self.page, cap(t("rs_page_tab")))
        self.tabbar.setTabButton(0, QTabBar.ButtonPosition.RightSide, None)
        self.tabbar.setTabButton(0, QTabBar.ButtonPosition.LeftSide, None)

        for seq, fn in (("Ctrl+W", lambda: self.close_tab(self.tabbar.currentIndex())),):
            s = QShortcut(QKeySequence(seq), self)
            s.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            s.activated.connect(fn)
        self.restyle()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.links.setGeometry(self.rect())
        self.links.raise_()

    def _links_update(self):
        self.links.setGeometry(self.rect())
        self.links.raise_()
        self.links.update()

    # ---- bağlı notlar
    def _attach(self):
        c = self.page.body.textCursor()
        word = c.selectedText().replace("\u2029", " ").strip()
        if not word or self.research is None:
            return
        self._pending_cursor = QTextCursor(c)
        self.notes.begin_anchor(word)

    def _note_added(self, n):
        c = self._pending_cursor
        self._pending_cursor = None
        if n and c is not None and n.get("anchor"):
            self.page.mark_note(c, n["id"])
        QTimer.singleShot(0, self._links_update)

    def _note_removed(self, nid):
        self.page.unmark_note(nid)
        QTimer.singleShot(0, self._links_update)

    def restyle(self):
        """Tema (uygulama ya da araştırma teması) değişti: yeniden başlatmadan her şeyi güncelle."""
        self.setStyleSheet(qss())
        self.home.restyle()
        self.shelf.relayout()
        self.notes.restyle()
        self.finder.restyle()
        for i, (rel, w) in enumerate(self.tabs):
            if rel is None:
                self.tabbar.setTabText(i, cap(t("rs_page_tab")))
            else:
                src = self.research.source(rel) if self.research else None
                if src is not None:
                    self.tabbar.setTabText(i, self._tab_label(src))
                if hasattr(w, "restyle"):
                    w.restyle()
        if self.research is not None:
            self._sources_changed()
            self.page.update_toc()
            self.page.normalize()
        self._links_update()

    # ---- araştırma aç / kapat
    def open(self, folder):
        if not folder or not os.path.isdir(folder):
            return
        if self.research is not None:
            if os.path.normcase(self.research.folder) == os.path.normcase(os.path.abspath(folder)):
                self.stack.setCurrentIndex(1)
                return
            self.close_research(show_home=False)
        r = Research(folder)
        self.research = r
        remember(r.folder)
        prefs.set("research_last", r.folder)
        r.sources_changed.connect(self._sources_changed)
        self.shelf.set_research(r)
        self.page.set_research(r)
        self.notes.set_research(r)
        self.finder.set_research(r)
        r.scan()
        self.stack.setCurrentIndex(1)
        sizes = prefs.get("research_split")
        if isinstance(sizes, list) and len(sizes) == 3 and all(isinstance(x, int) and x > 50 for x in sizes):
            self.split.setSizes(sizes)
        else:
            w = max(900, self.width())
            self.split.setSizes([300, w - 300 - 280, 280])
        self.title_changed.emit(r.title)
        r.changed.connect(lambda: self.title_changed.emit(r.title))

    def close_research(self, show_home=True):
        if self.research is None:
            return
        self.page.flush()
        while len(self.tabs) > 1:
            self.close_tab(len(self.tabs) - 1)
        self.research.close()
        self.research.deleteLater()
        self.research = None
        prefs.set("research_last", "")
        self.shelf.set_research(None)
        self.notes.set_research(None)
        self.finder.set_research(None)
        if show_home:
            self.home.refresh()
            self.stack.setCurrentIndex(0)
            self.title_changed.emit("")

    def flush(self):
        if self.research is not None:
            self.page.flush()
            self.research.save()

    def set_title(self, text):
        if self.research is not None:
            self.research.set_title(text)
            self.page.title.setText(self.research.title)

    def title(self):
        return self.research.title if self.research else ""

    # ---- raf
    def _sources_changed(self):
        r = self.research
        if r is None:
            return
        self.shelf.relayout()
        self.shelf_head.setText(f"{head(t('rs_sources'))} · {len(r.sources)}")
        self.page.update_meta()

    def _add_files(self):
        if self.research is None:
            return
        files, _ = QFileDialog.getOpenFileNames(self, t("rs_add_files"), os.path.expanduser("~"))
        if files:
            self._dropped(files)

    def _dropped(self, paths):
        if self.research is not None:
            self.research.add_files(paths)

    # ---- sekmeler
    def _add_tab(self, rel, w, label):
        self.tabs.append((rel, w))
        self.pages.addWidget(w)
        i = self.tabbar.addTab(label)
        return i

    def open_source(self, src):
        if (src.type == "video" or src.kind == "video") and not src.get("transcript"):
            res = kamuglink.open_link(kamuglink.make_link(src.path))
            if res == "missing":
                self.toast.emit(t("rs_cant_open"))
            return
        if src.kind == "link":
            url = src.get("url")
            if url:
                from PyQt6.QtGui import QDesktopServices
                from PyQt6.QtCore import QUrl
                QDesktopServices.openUrl(QUrl(url))
            return
        for i, (rel, _w) in enumerate(self.tabs):
            if rel == src.rel:
                self.tabbar.setCurrentIndex(i)
                return
        w = open_reader(src)
        if w is None:
            try:
                os.startfile(src.path)
            except OSError:
                self.toast.emit(t("rs_cant_open"))
            return
        if isinstance(w, PdfView):
            w.page_changed.connect(lambda n, m, w=w: self._page_no(w, n, m))
            w.set_highlights(self.research.data.setdefault("highlights", {}).setdefault(src.rel, []))
            w.highlights_changed.connect(self.research.touch)
        if isinstance(w, TranscriptView):
            w.copied_t.connect(lambda txt, sec, rel=src.rel: self.quote_t(rel, txt, sec))
            w.seek.connect(lambda sec, p=src.path: kamuglink.open_link(kamuglink.make_link(p, sec)))
        if hasattr(w, "copied"):
            w.copied.connect(lambda txt, pg, w=w, rel=src.rel: self.quote(rel, txt, pg, w, toast=True))
            w.quote_req.connect(lambda txt, pg, w=w, rel=src.rel: self.quote(rel, txt, pg, w))
            w.undo_req.connect(self.undo_quote)
        i = self._add_tab(src.rel, w, self._tab_label(src))
        self.tabbar.setTabToolTip(i, src.title + (f" — {src.author}" if src.author else ""))
        self.tabbar.setCurrentIndex(i)

    @staticmethod
    def _tab_label(src):
        label = cap(src.title)
        return label[:27].rstrip() + "…" if len(label) > 28 else label

    # ---- alıntı
    def quote(self, rel, text, page, w=None, toast=False):
        """Kaynaktan kopyalanan metin araştırma sayfasına alıntı kartı olarak düşer (künye: "Yazar · s. 42")."""
        src = self.research.source(rel) if self.research else None
        if src is None or not text.strip():
            return
        frag = {}
        if page:
            frag["p"] = page
        if isinstance(w, PdfView) and w.sel:
            ranges = w.sel_ranges()
            if ranges:
                frag["a"] = ranges[0][1]
                frag["n"] = sum(n for _pg, _a, n in ranges)
        href = "delta-src:" + urlquote(rel) + ("#" + "&".join(f"{k}={v}" for k, v in frag.items()) if frag else "")
        self.page.add_quote(text, src.cite(page or None), href)
        if toast:
            self.toast.emit(t("rs_quoted"))

    def quote_t(self, rel, text, sec):
        """Video dökümünden alıntı: künye "Yazar · 12:34", tıklayınca kamug o saniyede açar."""
        src = self.research.source(rel) if self.research else None
        if src is None or not text.strip():
            return
        who = src.short_author() or src.title
        self.page.add_quote(text, f"{who} · {fmt_time(sec)}", f"delta-src:{urlquote(rel)}#t={sec:.2f}")
        self.toast.emit(t("rs_quoted"))

    def undo_quote(self):
        if self.page.undo_quote():
            self.toast.emit(t("rs_quote_undone"))

    def jump(self, href):
        """Künyeye tıklandı: kaynağı aç, sayfaya git, alıntılanan yeri seç."""
        if self.research is not None and href.startswith("delta-note:"):
            self.notes.show_note(href[len("delta-note:"):])
            self.links.set_hot(href[len("delta-note:"):])
            return
        if self.research is None or not href.startswith("delta-src:"):
            return
        body = href[len("delta-src:"):]
        rel, _, frag = body.partition("#")
        rel = unquote(rel)
        q = {k: v[0] for k, v in parse_qs(frag).items()}
        src = self.research.source(rel)
        if src is None:
            self.toast.emit(t("rs_cant_open"))
            return
        if src.kind == "video":
            kamuglink.open_link(kamuglink.make_link(src.path, float(q.get("t", 0) or 0)))
            return
        self.open_source(src)
        w = self.pages.currentWidget()
        if isinstance(w, PdfView) and q.get("p"):
            pg = int(q["p"])
            a = int(q["a"]) if q.get("a") else None
            QTimer.singleShot(0, lambda: (w.go_to(pg, a), w.set_selection(pg - 1, a, int(q.get("n", 0)))
                                          if a is not None else None))

    # ---- dışa aktar
    def _export_menu(self):
        if self.research is None:
            return
        m = QMenu(self)
        for kind in ("html", "pdf", "md"):
            m.addAction(t("rs_export_" + kind), lambda kind=kind: self.export(kind))
        m.exec(self.btn_export.mapToGlobal(QPoint(0, self.btn_export.height())))

    def export(self, kind, path=None):
        """kind: html | pdf | md. Araştırma klasörüne kaydedilirse rafta kaynak olarak görünmez."""
        from . import research_export as X
        from .pages import safe_name
        r = self.research
        if r is None:
            return None
        self.page.flush()
        ext = {"html": ".html", "pdf": ".pdf", "md": ".md"}[kind]
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, t("rs_export"), os.path.join(r.folder, safe_name(r.title) + ext),
                                                  f"*{ext}")
            if not path:
                return None
        rel = os.path.relpath(path, r.folder).replace("\\", "/")
        if not rel.startswith(".."):
            ex = r.data.setdefault("exports", [])
            if rel not in ex:
                ex.append(rel)
                r.save()
        meta = r.meta_line(self.page.words())
        ok = {"html": X.save_site_html, "pdf": X.save_pdf, "md": X.save_markdown}[kind](r, path, meta)
        if ok:
            self.toast.emit(t("rs_exported").format(name=os.path.basename(path)))
        return path if ok else None

    def _page_no(self, w, n, m):
        if self.pages.currentWidget() is w:
            self.page_no.setText(cap(t("rs_page_of").format(n=n, m=m)))

    def _tab_changed(self, i):
        if not (0 <= i < len(self.tabs)):
            return
        rel, w = self.tabs[i]
        self.pages.setCurrentWidget(w)
        self.shelf.set_current(rel)
        if isinstance(w, PdfView):
            self._page_no(w, w.current_page() + 1, w.n)
        else:
            self.page_no.setText("")

    def _tab_moved(self, a, b):
        self.tabs.insert(b, self.tabs.pop(a))
        if self.tabs[0][0] is not None:      # araştırma sayfası hep başta
            j = next(i for i, (rel, _w) in enumerate(self.tabs) if rel is None)
            QTimer.singleShot(0, lambda j=j: self.tabbar.moveTab(j, 0))

    def close_tab(self, i):
        if i <= 0 or i >= len(self.tabs):
            return
        rel, w = self.tabs.pop(i)
        self.tabbar.removeTab(i)
        self.pages.removeWidget(w)
        if isinstance(w, PdfView):
            w.close_doc()
        w.deleteLater()
