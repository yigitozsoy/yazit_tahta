"""Komut kapısı: notları ve tahtayı yazıyla yönetmek için (geliştirici konsolu + komut satırı aynı fonksiyonu kullanır).

    run(app, argv) -> (kod, metin)     app = çalışan YazitApp (konsol bunu çağırır)

Komut satırından:  python -m yazit.cli notes | open 3 | export pdf "D:\\not.pdf" | help
Çalışan yazıt varsa istek tek örnek sunucusuna gider (app.serve, "\\x02cli" iletisi), cevabı geri yazılır. yazıt
kapalıysa yalnızca help / version çalışır; open <dosya.yazit> yazıt'ı o notla başlatır.
"""
import json
import os
import sys
from datetime import datetime

from .config import prefs
from .i18n import t

COMMANDS = {
    "status": "cli_h_status", "notes": "cli_h_notes", "open": "cli_h_open", "new": "cli_h_new",
    "rename": "cli_h_rename", "folders": "cli_h_folders", "go": "cli_h_go", "export": "cli_h_export",
    "tool": "cli_h_tool", "color": "cli_h_color", "width": "cli_h_width", "undo": "cli_h_undo", "redo": "cli_h_redo",
    "fit": "cli_h_fit", "snip": "cli_h_snip", "draw": "cli_h_draw", "panel": "cli_h_panel", "pin": "cli_h_pin",
    "full": "cli_h_full", "theme": "cli_h_theme", "pref": "cli_h_pref", "version": "cli_h_version",
    "help": "cli_h_help",
}
OFFLINE = ("help", "version")
GO_TARGETS = ("board", "research")
EXPORT_FORMATS = ("png", "jpg", "pdf")
# renk adları (İngilizce + Türkçe) → tools.COLORS sırası
COLOR_NAMES = {"white": 0, "beyaz": 0, "black": 1, "siyah": 1, "blue": 2, "mavi": 2, "red": 3, "kırmızı": 3,
               "kirmizi": 3, "green": 4, "yeşil": 4, "yesil": 4, "yellow": 5, "sarı": 5, "sari": 5,
               "orange": 6, "turuncu": 6}


class _Fail(Exception):
    pass


def help_text():
    rows = []
    for k, v in COMMANDS.items():
        text = t(v)
        use, _, desc = text.partition("  ") if "  " in text and text.startswith(k + " ") else (k, "", text)
        rows.append((use, desc))
    w = max(len(u) for u, _ in rows)
    return "\n".join(f"{u.ljust(w)}  {d}" for u, d in rows)


def _pages(store):
    return list(store.sorted())


def _title(p):
    return p.display_title()


def _find_page(store, q):
    """Not: sıra numarası (notes listesindeki), başlık parçası ya da kimlik."""
    pages = _pages(store)
    if q.isdigit():
        n = int(q)
        if not 1 <= n <= len(pages):
            raise _Fail(t("cli_out_of_range", n=n, m=len(pages)))
        return pages[n - 1]
    p = store.get(q)
    if p is not None:
        return p
    ql = q.lower()
    hits = [p for p in pages if _title(p).lower() == ql] or [p for p in pages if ql in _title(p).lower()]
    if not hits:
        raise _Fail(t("cli_no_note", q=q))
    return hits[0]


def _status(app):
    win = app.win
    if win.in_research():
        r = win.research.research
        return t("cli_st_research") + (f": {r.title}  ({r.folder})" if r is not None else "")
    p = win.page
    if p is None:
        return ""
    n = len(win.board.scene().content_items()) if win.board.scene() else 0
    lines = [f"{_title(p)}", f"{t('cli_st_items')}: {n}"]
    if p.folder:
        lines.append(f"{t('cli_st_folder')}: {p.folder}")
    lines.append(f"{t('cli_st_file')}: {p.file or t('cli_st_unsaved')}")
    lines.append(f"{t('cli_st_tool')}: {_tool_state()}")
    return "\n".join(lines)


def _tool_state():
    from .tools import state
    return f"{state.tool}  {state.color}  {state.width:g}"


def _notes(app, args):
    q = " ".join(args).lower()
    rows = []
    for n, p in enumerate(_pages(app.store), 1):
        title = _title(p)
        if q and q not in title.lower() and q not in (p.folder or "").lower():
            continue
        mark = "▶" if p is app.win.page else " "
        folder = f"  [{p.folder}]" if p.folder else ""
        rows.append(f"{mark} {n:>3}  {title}{folder}")
    return "\n".join(rows) if rows else (t("cli_list_none", q=q) if q else t("cli_list_empty"))


def _export(app, args):
    from .canvas import render_scene
    from .config import snapshot_dir
    from .export import save_image, export_pdf
    from .theme import qcolor
    win = app.win
    fmt = (args[0].lower() if args else prefs.get("save_format", "png")).lstrip(".")
    if fmt == "jpeg":
        fmt = "jpg"
    if fmt == "all":                                   # tüm notlar tek PDF
        path = args[1] if len(args) > 1 else os.path.join(
            snapshot_dir(), "yazit " + datetime.now().strftime("%Y-%m-%d") + ".pdf")
        imgs = []
        for p in app.store.pages.values():
            p.ensure_loaded()
            img = render_scene(p.scene)
            if img is not None:
                imgs.append(img)
        if not imgs:
            raise _Fail(t("nothing_to_copy"))
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        if not export_pdf(imgs, os.path.abspath(path)):
            raise _Fail(t("save_failed"))
        return os.path.abspath(path)
    if fmt not in EXPORT_FORMATS:
        raise _Fail(t("cli_usage", u="export [png | jpg | pdf | all] [yol]"))
    img = render_scene(win.board.scene())
    if img is None:
        raise _Fail(t("nothing_to_copy"))
    if len(args) > 1:
        path = os.path.abspath(args[1])
        if not os.path.splitext(path)[1]:
            path += "." + fmt
    else:
        from .window import _safe
        name = _safe(win.page.display_title()) + " " + datetime.now().strftime("%H.%M.%S")
        path = os.path.join(snapshot_dir(), name + "." + fmt)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if not save_image(img, path, qcolor("bg")):
        raise _Fail(t("save_failed"))
    return path


def _pref(args):
    if not args:
        skip = ("console_history", "window_geometry", "research_recent", "external_notes", "migrated_ids")
        return "\n".join(f"{k} = {json.dumps(v, ensure_ascii=False)}" for k, v in sorted(prefs.data.items())
                         if k not in skip)
    key = args[0]
    if len(args) == 1:
        if key not in prefs.data:
            raise _Fail(t("cli_no_pref", k=key))
        return json.dumps(prefs.get(key), ensure_ascii=False)
    raw = " ".join(args[1:])
    try:
        val = json.loads(raw)
    except ValueError:
        val = raw
    prefs.set(key, val)
    return f"{key} = {json.dumps(val, ensure_ascii=False)}"


def run(app, argv):
    """Bir komutu çalıştırır → (kod, metin). Kod 0 = tamam, 1 = hata, 2 = bilinmeyen komut."""
    if not argv:
        return 0, help_text()
    cmd, args = argv[0].lower(), argv[1:]
    try:
        if cmd in ("help", "-h", "--help"):
            return 0, help_text()
        if cmd == "version":
            from . import __version__
            return 0, f"yazıt {__version__}"
        if cmd not in COMMANDS:
            return 2, t("cli_unknown", c=cmd)
        if app is None:
            return 1, t("cli_not_running")
        return 0, _run_ui(app, cmd, args)
    except _Fail as e:
        return 1, str(e)
    except ValueError as e:
        return 1, t("cli_bad_value", v=str(e))


def _run_ui(app, cmd, args):
    win, store = app.win, app.store
    from .tools import state, TOOLS, COLORS
    if cmd == "status":
        return _status(app)
    if cmd == "notes":
        return _notes(app, args)
    if cmd == "open":
        if not args:
            raise _Fail(t("cli_usage", u="open <n | başlık | dosya.yazit>"))
        q = " ".join(args)
        from .config import is_note_file
        if is_note_file(q) and os.path.isfile(q):
            p = win.open_file(os.path.abspath(q))
            if p is None:
                raise _Fail(t("open_failed"))
        else:
            win.set_research_mode(False)
            p = _find_page(store, q)
            win.open_page(p)
        return _title(p)
    if cmd == "new":
        win.set_research_mode(False)
        folder = " ".join(args).strip()
        if folder and store.folder(folder) is None:
            raise _Fail(t("cli_no_folder", f=folder))
        p = win.new_note(folder)
        return _title(p) if p is not None else ""
    if cmd == "rename":
        title = " ".join(args).strip()
        if not title or win.page is None:
            raise _Fail(t("cli_usage", u="rename <yeni başlık>"))
        win._title_edited(title)
        return _title(win.page)
    if cmd == "folders":
        rows = [f"{f['name']}  ({len(store.folder_pages(f['id']))})" for f in store.folders]
        return "\n".join(rows) if rows else t("cli_list_empty")
    if cmd == "go":
        q = " ".join(args).strip().lower()
        if not q:
            return t("cli_go_targets") + " " + ", ".join(GO_TARGETS)
        if q in ("board", "tahta"):
            win.set_research_mode(False)
            return "board"
        if q in ("research", "araştırma", "arastirma"):
            win.set_research_mode(True)
            return "research"
        win.set_research_mode(False)
        p = _find_page(store, " ".join(args))
        win.open_page(p)
        return _title(p)
    if cmd == "export":
        return _export(app, args)
    if cmd == "tool":
        if args:
            name = args[0].lower()
            if name not in TOOLS:
                raise _Fail(t("cli_tools") + " " + ", ".join(TOOLS[:12]) + " …")
            state.set_tool(name)
        return state.tool
    if cmd == "color":
        if args:
            c = args[0].lower()
            if c in COLOR_NAMES:
                c = COLORS[COLOR_NAMES[c]]
            elif c.isdigit() and 1 <= int(c) <= len(COLORS):
                c = COLORS[int(c) - 1]
            elif not (c.startswith("#") and len(c) in (4, 7)):
                raise _Fail(t("cli_colors") + " " + ", ".join(k for k in COLOR_NAMES if k.isascii()) + ", #rrggbb")
            state.set_color(c)
        return state.color
    if cmd == "width":
        if args:
            state.set_width(float(args[0].replace(",", ".")))
        return f"{state.width:g}"
    if cmd in ("undo", "redo"):
        win.board.undo() if cmd == "undo" else win.board.redo()
        u = win.page.undo if win.page is not None else None
        return f"{u.index()}/{u.count()}" if u is not None else ""
    if cmd == "fit":
        win.board.fit_all()
        return t("cli_done")
    if cmd == "snip":
        app._close_annotate_for_capture()
        app.capture.start(250)
        return t("cli_done")
    if cmd == "draw":
        app.start_annotate_from_window()
        return t("cli_done")
    if cmd == "panel":
        win.set_panel(not win.panel.isVisible())
        return t("cli_on") if win.panel.isVisible() else t("cli_off")
    if cmd == "pin":
        win.set_pinned(not prefs.get("pinned", False))
        return t("cli_on") if prefs.get("pinned", False) else t("cli_off")
    if cmd == "full":
        win.toggle_fullscreen()
        return t("cli_done")
    if cmd == "theme":
        from .theme import theme, VARIANTS, current_variant
        if args:
            if args[0] not in VARIANTS and args[0] not in ("dark", "light"):
                raise _Fail(t("cli_themes") + " " + ", ".join(VARIANTS))
            theme.apply(args[0])
        else:
            win.toggle_theme()
        return current_variant()
    if cmd == "pref":
        return _pref(args)
    return ""


# ------------------------------------------------------------------ komut satırı (python -m yazit.cli)
CLI_TAG = "\x02cli\n"


def send(argv, timeout_ms=5000, name=None):
    """Çalışan yazıt'a komut gönderir → (kod, metin) ya da yazıt kapalıysa None. name: sunucu adı (test)."""
    from PyQt6.QtNetwork import QLocalSocket
    from .app import SERVER_NAME
    sock = QLocalSocket()
    sock.connectToServer(name or SERVER_NAME)
    if not sock.waitForConnected(300):
        return None
    sock.write((CLI_TAG + json.dumps(argv, ensure_ascii=False)).encode("utf-8"))
    sock.flush()
    sock.waitForBytesWritten(1000)
    buf = b""
    while sock.waitForReadyRead(timeout_ms):
        buf += bytes(sock.readAll())
        if buf.endswith(b"\n"):
            break
    sock.disconnectFromServer()
    try:
        r = json.loads(buf.decode("utf-8"))
        return int(r["code"]), r["out"]
    except (ValueError, KeyError, TypeError):
        return 1, t("cli_no_reply")


def handle_request(app, payload):
    """app.serve: "\\x02cli\\n<json argv>" → cevap baytları."""
    try:
        argv = json.loads(payload)
        code, out = run(app, [str(a) for a in argv])
    except Exception as e:  # noqa: BLE001  (istemciye hata dönsün, uygulama düşmesin)
        code, out = 1, f"{type(e).__name__}: {e}"
    return (json.dumps({"code": code, "out": out}, ensure_ascii=False) + "\n").encode("utf-8")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    from PyQt6.QtCore import QCoreApplication
    main.app = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])   # QLocalSocket için
    res = send(argv) if argv and argv[0].lower() not in OFFLINE else None
    if res is None:
        if argv and argv[0].lower() == "open" and len(argv) > 1 and os.path.isfile(argv[1]):
            import subprocess
            args = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, "-m", "yazit"]
            subprocess.Popen(args + [os.path.abspath(argv[1])], close_fds=True)
            print(t("cli_started"))
            return 0
        res = run(None, argv)
    code, out = res
    if out:
        print(out, file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":
    sys.exit(main())
