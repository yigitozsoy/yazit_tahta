"""Araştırma modu — sağ sütunun üstündeki "Kaynak bul" kutusu.

Bağlantı / DOI yapıştır → bulunur, PDF açıksa indirilir, değilse bağlantı olarak eklenir (hemen, sormadan).
Sözcük yaz + Enter → OpenAlex araması; sonuç kartında "İndir" (PDF var) / "Ekle" (bağlantı).
PDF'i açık olmayan kaynakta "Tarayıcıda aç": kullanıcı kendi girişiyle indirince İndirilenler'den klasöre gelir."""
import os

from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QFrame,
                             QSizePolicy)

from . import finder as F
from .i18n import t
from .shelf import head, cap


def _authors(p):
    a = p.get("authors") or []
    if not a:
        return ""
    return a[0] + (" " + t("rs_net_etal") if len(a) > 1 else "")


class Hit(QFrame):
    """Sonuç kartı: başlık, yazar · yıl · dergi, PDF / bağlantı rozeti, düğme."""
    def __init__(self, panel, p, saved=None):
        super().__init__()
        self.panel, self.p = panel, p
        self.setObjectName("RsHit")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(3)
        ti = QLabel(p.get("title") or p.get("url") or "?")
        ti.setObjectName("RsHitTitle")
        ti.setWordWrap(True)
        ti.setToolTip(p.get("url") or "")
        v.addWidget(ti)
        meta = " · ".join(x for x in (_authors(p), p.get("year"), p.get("venue")) if x)
        if meta:
            m = QLabel(meta)
            m.setObjectName("RsHitMeta")
            m.setWordWrap(True)
            v.addWidget(m)
        row = QHBoxLayout()
        row.setContentsMargins(0, 3, 0, 0)
        row.setSpacing(6)
        self.badge = QLabel()
        self.badge.setObjectName("RsBadge")
        row.addWidget(self.badge)
        row.addStretch(1)
        self.btn = QPushButton()
        self.btn.setObjectName("RsHitBtn")
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.btn.clicked.connect(self._click)
        row.addWidget(self.btn)
        v.addLayout(row)
        self.rel = None
        self.kind = None
        self.busy = False
        if saved:
            self.set_saved(*saved)
        else:
            self._idle()

    def _idle(self):
        has_pdf = bool(self.p.get("pdfs") or self.p.get("lands"))
        self.badge.setText(t("rs_net_pdf") if has_pdf else t("rs_net_link_only"))
        self.btn.setText(t("rs_net_download") if has_pdf else t("rs_net_add"))
        self.btn.setEnabled(True)

    def set_busy(self):
        self.busy = True
        self.btn.setText(t("rs_net_working"))
        self.btn.setEnabled(False)

    def set_saved(self, rel, kind):
        self.busy = False
        self.rel, self.kind = rel, kind
        if kind == "pdf":
            self.badge.setText(t("rs_net_pdf"))
            self.btn.setText("✓ " + t("rs_net_added"))
            self.btn.setEnabled(False)
        else:
            self.badge.setText(t("rs_net_link_only"))
            self.btn.setText(t("rs_net_browser"))
            self.btn.setEnabled(True)
            self.btn.setToolTip(t("rs_net_browser_tip"))

    def set_failed(self):
        self.busy = False
        self._idle()

    def _click(self):
        if self.kind == "link":
            self.panel.open_in_browser(self)
        elif not self.busy:
            self.panel.save_hit(self)


class FindPanel(QWidget):
    toast = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.research = None
        self.finder = F.Finder(self)
        self.finder.results.connect(self._results)
        self.finder.saved.connect(self._saved)
        self.finder.failed.connect(self._failed)
        self.watch = F.DownloadWatch(self)
        self.watch.arrived.connect(self._arrived)
        self.jobs = {}              # iş → ("search" | "fetch" | Hit)
        self.search_job = 0
        v = QVBoxLayout(self)
        v.setContentsMargins(12, 0, 12, 0)
        v.setSpacing(6)
        self.head = QLabel()
        self.head.setObjectName("RsHead")
        self.head.setContentsMargins(6, 0, 0, 0)
        v.addWidget(self.head)
        self.inp = QLineEdit()
        self.inp.setObjectName("RsFind")
        self.inp.setPlaceholderText(t("rs_net_ph"))
        self.inp.setClearButtonEnabled(True)
        self.inp.returnPressed.connect(self.go)
        self.inp.textEdited.connect(self._edited)
        v.addWidget(self.inp)
        self.status = QLabel()
        self.status.setObjectName("RsSub")
        self.status.setWordWrap(True)
        self.status.setContentsMargins(6, 0, 6, 0)
        self.status.hide()
        v.addWidget(self.status)
        self.box = QWidget()
        bv = QVBoxLayout(self.box)
        bv.setContentsMargins(0, 0, 0, 0)
        bv.setSpacing(4)
        hrow = QHBoxLayout()
        hrow.setContentsMargins(6, 4, 0, 0)
        self.res_head = QLabel()
        self.res_head.setObjectName("RsHead")
        hrow.addWidget(self.res_head, 1)
        x = QPushButton("×")
        x.setObjectName("RsIcon")
        x.setToolTip(t("rs_net_clear"))
        x.setCursor(Qt.CursorShape.PointingHandCursor)
        x.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        x.clicked.connect(self.clear)
        hrow.addWidget(x)
        bv.addLayout(hrow)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("RsScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        inner = QWidget()
        self.list = QVBoxLayout(inner)
        self.list.setContentsMargins(0, 0, 4, 0)
        self.list.setSpacing(6)
        self.list.addStretch(1)
        self.scroll.setWidget(inner)
        self.scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        bv.addWidget(self.scroll, 1)
        self.box.hide()
        v.addWidget(self.box, 1)
        self.restyle()

    def restyle(self):
        self.head.setText(head(t("rs_net_head")))
        self.res_head.setText(f"{head(t('rs_net_results'))} · {self.count()}")
        # sonuç varken sütunun çoğunu al (notlar altta kalır), yokken yalnızca kutu kadar
        lay = self.parentWidget().layout() if self.parentWidget() else None
        if lay is not None:
            lay.setStretchFactor(self, 3 if self.box.isVisibleTo(self) else 0)

    def set_research(self, r):
        self.research = r
        self.clear()

    # ---- giriş
    def _edited(self, txt):
        """Bağlantı yapıştırılınca (tek seferde uzun metin) beklemeden getir."""
        prev = getattr(self, "_prev", "")
        self._prev = txt
        if F.classify(txt) in ("url", "doi") and len(txt) - len(prev) > 8 and not prev.strip():
            self.go()

    def go(self):
        txt = self.inp.text().strip()
        if not txt:
            return
        if self.research is None:
            self._say(t("rs_net_no_research"))
            return
        if F.classify(txt) in ("url", "doi"):
            self.fetch(txt)
            self.inp.clear()
            self._prev = ""
        else:
            self._say(t("rs_net_searching"))
            self.search_job = self.finder.search(txt)
            self.jobs[self.search_job] = "search"

    def fetch(self, text):
        """Bağlantı / DOI (yapıştırılan ya da rafa bırakılan): bul + kaydet."""
        if self.research is None:
            return
        job = self.finder.fetch(text, self.research.folder)
        self.jobs[job] = ("fetch", text)
        self._say(t("rs_net_fetching"))

    def save_hit(self, hit):
        if self.research is None:
            return
        hit.set_busy()
        job = self.finder.save(hit.p, self.research.folder)
        self.jobs[job] = hit

    def open_in_browser(self, hit):
        url = hit.p.get("url") or ""
        if not url or self.research is None:
            return
        QDesktopServices.openUrl(QUrl(url))
        self.watch.watch(self.research.folder, hit.p, hit.rel or "")
        self._say(t("rs_net_watching"))

    # ---- sonuçlar
    def count(self):
        return self.list.count() - 1

    def clear(self):
        while self.list.count() > 1:
            w = self.list.takeAt(0).widget()
            if w:
                w.hide()
                w.deleteLater()
        self.box.hide()
        self.status.hide()
        self.search_job = -1
        self.restyle()

    def _say(self, msg):
        self.status.setText(msg)
        self.status.setVisible(bool(msg))

    def _add_hit(self, p, saved=None, top=False):
        h = Hit(self, p, saved)
        self.list.insertWidget(0 if top else self.list.count() - 1, h)
        self.box.show()
        self.restyle()
        return h

    def _results(self, job, items):
        self.jobs.pop(job, None)
        if job != self.search_job:
            return
        while self.list.count() > 1:
            w = self.list.takeAt(0).widget()
            if w:
                w.hide()
                w.deleteLater()
        for p in items:
            self._add_hit(p)
        self._say("" if items else t("rs_net_none"))
        self.box.setVisible(bool(items))
        self.scroll.verticalScrollBar().setValue(0)
        self.restyle()

    def _register(self, p, rel, kind):
        r = self.research
        if r is None:
            return
        r.set_override(rel, **F.overrides(p, kind))
        r.scan()

    def _saved(self, job, p, rel, kind):
        what = self.jobs.pop(job, None)
        if self.research is None:
            return
        self._register(p, rel, kind)
        if isinstance(what, Hit):
            what.set_saved(rel, kind)
            self._say("")
        else:
            self._add_hit(p, (rel, kind), top=True)
            self.scroll.verticalScrollBar().setValue(0)
            self._say(t("rs_net_got_pdf") if kind == "pdf" else t("rs_net_got_link"))
        title = (p.get("title") or os.path.basename(rel))[:60]
        self.toast.emit((t("rs_net_saved_pdf") if kind == "pdf" else t("rs_net_saved_link")).format(t=cap(title)))

    def _failed(self, job, msg):
        what = self.jobs.pop(job, None)
        if isinstance(what, Hit):
            what.set_failed()
        if what == "search" and job != self.search_job:
            return
        self._say(t("rs_net_offline") if msg == F.OFFLINE else t("rs_net_error").format(e=msg))

    def _arrived(self, folder, rel, p):
        if self.research is not None and os.path.normcase(self.research.folder) == os.path.normcase(folder):
            old = None
            for i in range(self.count()):
                h = self.list.itemAt(i).widget()
                if isinstance(h, Hit) and h.p.get("url") == p.get("url"):
                    old = h.rel
                    h.set_saved(rel, "pdf")
            if old:
                self.research.set_override(old, title=None, author=None, year=None, doi=None, url=None, type=None)
            self._register(p, rel, "pdf")
            self._say("")
        self.toast.emit(t("rs_net_saved_pdf").format(t=(p.get("title") or rel)[:60]))
