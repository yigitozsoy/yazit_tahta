"""Yapay zekâ istemcileri (MCP) — yazıt tarafı.

mcpserver.py (istemcinin başlattığı ayrı süreç) yazma işlerini tek örnek sunucusundan buraya gönderir
("\\x02mcp\\n" + JSON + "\\n"; app.serve). Burada:
  · McpHost   : işi alır; prefs mcp_write'a göre kullanıcıya sorar (ask), sormadan yapar (allow) ya da reddeder (off);
                araştırmayı açar, alıntı kartını / notu / kaynağı ekler, cevabı sokete yazar.
  · AskBubble : ekranın sağ altında küçük onay balonu (her zaman üstte), "Bu oturumda sorma" seçeneği.
  · Claude Desktop / Claude Code ayarı: yapılandırma dosyasına "yazit" sunucusunu ekler (Seçenekler'deki düğme).
"""
import glob
import json
import os
import shutil
import sys

from PyQt6.QtCore import Qt, QObject, QTimer
from PyQt6.QtWidgets import (QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
                             QApplication)

from .config import prefs
from .i18n import t

WRITE_MODES = ("ask", "allow", "off")
ASK_TIMEOUT_MS = 50000          # istemciler isteği ~60 sn'de keser; ondan önce kendiliğinden reddet


def client_label(name):
    n = (name or "").strip()
    if not n or "claude" in n.lower():
        return "Claude"
    return n[:40]


# --------------------------------------------------------------------------- onay balonu
class AskBubble(QWidget):
    """Sağ altta: "Claude araştırmaya alıntı eklemek istiyor" + önizleme + Ekle / Reddet."""

    def __init__(self, job, on_done):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setObjectName("McpAsk")
        self.job = job
        self.on_done = on_done
        self._done = False
        from .theme import color
        card = QFrame(self)
        card.setObjectName("McpCard")
        card.setStyleSheet(
            f"#McpCard {{ background: {color('card')}; border: 1px solid {color('surface_hover')}; border-radius: 12px; }}"
            f"#McpCard QLabel {{ background: transparent; }}"
            f"#McpWho {{ color: {color('text')}; font-weight: 600; font-size: 13px; }}"
            f"#McpSub {{ color: {color('text2')}; font-size: 11px; }}"
            f"#McpBody {{ color: {color('text')}; font-size: 12px; }}")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.addWidget(card)
        v = QVBoxLayout(card)
        v.setContentsMargins(16, 14, 16, 12)
        v.setSpacing(6)
        op = job.get("op")
        who = client_label(job.get("client"))
        head = QLabel(t("mcp_ask_" + op, who=who))
        head.setObjectName("McpWho")
        head.setWordWrap(True)
        v.addWidget(head)
        from .research import peek
        sub = QLabel(peek(job.get("research", ""))[0] if job.get("research") else "")
        sub.setObjectName("McpSub")
        sub.setVisible(bool(sub.text()))
        v.addWidget(sub)
        body = QLabel()
        body.setObjectName("McpBody")
        body.setWordWrap(True)
        body.setTextFormat(Qt.TextFormat.PlainText)
        body.setMaximumWidth(340)
        if op == "add_quote":
            txt = job.get("text", "")
            body.setText("“" + (txt if len(txt) < 360 else txt[:357] + "…") + "”\n— " + job.get("cite", ""))
        elif op == "add_note":
            txt = job.get("text", "")
            body.setText((txt if len(txt) < 360 else txt[:357] + "…") +
                         (("\n" + t("mcp_anchor", w=job["anchor"])) if job.get("anchor") else ""))
        else:
            body.setText(job.get("what", ""))
        v.addWidget(body)
        self.chk = QCheckBox(t("mcp_ask_session"))
        self.chk.setObjectName("McpSub")
        v.addWidget(self.chk)
        row = QHBoxLayout()
        row.setSpacing(8)
        row.addStretch(1)
        self.b_no = QPushButton(t("mcp_deny"))
        self.b_no.setObjectName("Flat")
        self.b_no.clicked.connect(lambda: self.finish(False))
        self.b_ok = QPushButton(t("mcp_allow"))
        self.b_ok.setObjectName("Primary")
        self.b_ok.setDefault(True)
        self.b_ok.clicked.connect(lambda: self.finish(True))
        row.addWidget(self.b_no)
        row.addWidget(self.b_ok)
        v.addLayout(row)
        self.setFixedWidth(380)
        self.adjustSize()
        self._timer = QTimer(self, singleShot=True, interval=ASK_TIMEOUT_MS, timeout=lambda: self.finish(False))
        self._timer.start()

    def place(self, anchor=None):
        scr = (anchor.screen() if anchor is not None and anchor.isVisible() else None) or QApplication.primaryScreen()
        g = scr.availableGeometry()
        self.adjustSize()
        self.move(g.right() - self.width() - 12, g.bottom() - self.height() - 12)

    def finish(self, ok):
        if self._done:
            return
        self._done = True
        self._timer.stop()
        session = self.chk.isChecked()
        self.close()
        self.on_done(self.job, ok, session)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.finish(False)
            return
        super().keyPressEvent(e)


# --------------------------------------------------------------------------- iş karşılayıcı
class McpHost(QObject):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.queue = []            # [(iş, cevap fonksiyonu)]
        self.bubble = None
        self.session_allow = False

    # ---- gelen iş
    def handle(self, raw, reply):
        try:
            job = json.loads(raw)
            if not isinstance(job, dict):
                raise ValueError
        except ValueError:
            reply({"ok": False, "msg": "bad request"})
            return
        op = job.get("op")
        if op == "ping":
            rv = self.app.win.research
            reply({"ok": True, "open": rv.research.folder if rv.research is not None else ""})
            return
        if not prefs.get("mcp_enabled", False):
            reply({"ok": False, "msg": t("mcp_off")})
            return
        if op == "reading":
            self._reading(job)
            reply({"ok": True})
            return
        if op == "flush":
            rv = self.app.win.research
            r = rv.research
            if r is not None and os.path.normcase(r.folder) == os.path.normcase(os.path.abspath(job.get("research", ""))):
                rv.flush()
            reply({"ok": True})
            return
        if op not in ("add_quote", "add_note", "add_source"):
            reply({"ok": False, "msg": f"unknown op: {op}"})
            return
        if not job.get("research") or not os.path.isdir(job["research"]):
            reply({"ok": False, "msg": t("mcp_no_research")})
            return
        mode = prefs.get("mcp_write", "ask")
        if mode == "off":
            reply({"ok": False, "msg": t("mcp_write_off")})
            return
        if mode == "allow" or self.session_allow:
            reply(self.perform(job))
            return
        self.queue.append((job, reply))
        sock = getattr(reply, "sock", None)
        if sock is not None:          # istemci vazgeçerse (zaman aşımı) iş sıradan düşer, balon kapanır
            sock.disconnected.connect(lambda r=reply: self._gone(r))
        if self.bubble is None:
            self._next()

    def _gone(self, reply):
        cur = self.queue[0][1] if self.queue else None
        self.queue = [(j, r) for j, r in self.queue if r is not reply]
        if cur is reply and self.bubble is not None:
            self.bubble._done = True
            self.bubble.close()
            self.bubble = None
            QTimer.singleShot(0, self._next)

    def _next(self):
        while self.queue and not _alive(self.queue[0][1]):
            self.queue.pop(0)
        if not self.queue:
            self.bubble = None
            return
        job, _reply = self.queue[0]
        self.bubble = AskBubble(job, self._decided)
        self.bubble.place(self.app.win)
        self.bubble.show()
        self.bubble.raise_()

    def _decided(self, job, ok, session):
        if not self.queue or self.queue[0][0] is not job:
            return
        _job, reply = self.queue.pop(0)
        if ok and session:
            self.session_allow = True
        if not _alive(reply):           # istemci beklemeyi bıraktı: eklenirse "olmadı" sanıp yeniden dener
            pass
        elif ok:
            reply(self.perform(job))
            win = self.app.win
            if not win.isVisible() or win.isMinimized():
                win.bring_front()
        else:
            reply({"ok": False, "msg": t("mcp_denied")})
        if self.session_allow:          # bekleyenler artık sorulmaz
            while self.queue:
                j, r = self.queue.pop(0)
                if _alive(r):
                    r(self.perform(j))
        QTimer.singleShot(0, self._next)

    # ---- uygula
    def _open(self, folder):
        win = self.app.win
        if not win.in_research():
            win.set_research_mode(True)
        rv = win.research
        rv.open(folder)
        r = rv.research
        if r is None or os.path.normcase(r.folder) != os.path.normcase(os.path.abspath(folder)):
            return None
        return rv

    def perform(self, job):
        try:
            rv = self._open(job["research"])
            if rv is None:
                return {"ok": False, "msg": t("mcp_no_research")}
            who = client_label(job.get("client"))
            op = job["op"]
            if op == "add_quote":
                text = str(job.get("text") or "").strip()
                if not text:
                    return {"ok": False, "msg": "empty"}
                rv.tabbar.setCurrentIndex(0)
                rv.page.add_quote(text, str(job.get("cite") or ""), str(job.get("href") or ""))
                rv.toast.emit(t("mcp_quoted", who=who))
                return {"ok": True, "msg": ""}
            if op == "add_note":
                return self._add_note(rv, job, who)
            if op == "add_source":
                rv.finder.fetch(str(job.get("what") or ""))
                return {"ok": True, "msg": t("mcp_fetching")}
        except Exception as e:      # noqa: BLE001  (istemciye hata dönsün, yazıt düşmesin)
            return {"ok": False, "msg": f"{type(e).__name__}: {e}"}
        return {"ok": False, "msg": "?"}

    def _add_note(self, rv, job, who):
        from PyQt6.QtGui import QTextCursor
        text = str(job.get("text") or "").strip()
        if not text:
            return {"ok": False, "msg": "empty"}
        anchor = str(job.get("anchor") or "").strip()
        cur = None
        if anchor:
            c = rv.page.body.document().find(anchor)
            if not c.isNull():
                cur = QTextCursor(c)
        n = rv.research.add_note(text, {"text": cur.selectedText().replace(" ", " ")} if cur else None)
        rv.notes.refresh()
        rv._pending_cursor = cur
        rv._note_added(n)
        rv.toast.emit(t("mcp_noted", who=who))
        msg = t("mcp_note_ok")
        if anchor and cur is None:
            msg = t("mcp_note_noanchor", w=anchor)
        return {"ok": True, "msg": msg}

    def _reading(self, job):
        rv = self.app.win.research
        r = rv.research
        if r is not None and os.path.normcase(r.folder) == os.path.normcase(os.path.abspath(job.get("research", ""))):
            rv.shelf.glow(job.get("rel", ""))


def _alive(reply):
    f = getattr(reply, "alive", None)
    return f() if f is not None else True


def serve_reply(sock):
    """Sokete JSON cevap yazan fonksiyon (soket kapanmışsa sessiz)."""
    from PyQt6 import sip

    def reply(obj):
        if sip.isdeleted(sock):
            return
        try:
            sock.write((json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8"))
            sock.flush()
        except RuntimeError:
            pass

    def alive():
        from PyQt6.QtNetwork import QLocalSocket
        return not sip.isdeleted(sock) and sock.state() == QLocalSocket.LocalSocketState.ConnectedState
    reply.alive = alive
    reply.sock = sock
    return reply


# --------------------------------------------------------------------------- istemci ayarı
def mcp_command():
    """İstemcinin çalıştıracağı komut → (program, argümanlar)."""
    if getattr(sys, "frozen", False):
        return os.path.join(os.path.dirname(sys.executable), "yazit-mcp.exe"), []
    py = sys.executable
    if os.path.basename(py).lower() == "pythonw.exe":       # stdio için konsollu yorumlayıcı
        alt = os.path.join(os.path.dirname(py), "python.exe")
        py = alt if os.path.isfile(alt) else py
    main = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
    return py, [main, "--mcp"]


def claude_code_command():
    cmd, args = mcp_command()
    parts = [f'"{cmd}"'] + [f'"{a}"' if " " in a else a for a in args]
    return "claude mcp add --scope user yazit -- " + " ".join(parts)


def claude_desktop_dirs():
    """Claude Desktop'un ayar klasörleri (normal kurulum + Microsoft Store kurulumu); hiçbiri yoksa normal yer."""
    out = []
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming")
    normal = os.path.join(appdata, "Claude")
    if os.path.isdir(normal):
        out.append(normal)
    local = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
    for d in glob.glob(os.path.join(local, "Packages", "Claude_*", "LocalCache", "Roaming", "Claude")):
        if os.path.isdir(d):
            out.append(d)
    return out or [normal]


def add_to_claude_desktop(dirs=None):
    """claude_desktop_config.json'a mcpServers.yazit ekler (diğer ayarlar korunur, eskisi .bak).
    → (tamam mı, yazılan dosyalar, hata)"""
    cmd, args = mcp_command()
    written, errors = [], []
    for d in dirs or claude_desktop_dirs():
        path = os.path.join(d, "claude_desktop_config.json")
        data = {}
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
            except (OSError, ValueError) as e:
                errors.append(f"{path}: {e}")
                continue
            if not isinstance(data, dict):
                errors.append(path)
                continue
            try:
                shutil.copy2(path, path + ".bak")
            except OSError:
                pass
        servers = data.get("mcpServers")
        if not isinstance(servers, dict):
            servers = {}
            data["mcpServers"] = servers
        servers["yazit"] = {"command": cmd, "args": args}
        try:
            os.makedirs(d, exist_ok=True)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
            written.append(path)
        except OSError as e:
            errors.append(f"{path}: {e}")
    return (bool(written) and not errors), written, "; ".join(errors)
