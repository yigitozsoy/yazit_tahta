"""tamga ortak ayarları: tamga başlatıcısı tercih dosyasındaki tema / vurgu / dil anahtarlarını
değiştirirse, açık olan uygulama bunu fark edip temayı hemen uygular.

Bu dosya kamug, erk ve yazıt'ta birebir aynıdır (tamga deposundaki kopyayla eş tut)."""
import json
import os

from PyQt6.QtCore import QFileSystemWatcher, QTimer

SHARED = ("theme", "dark_variant", "light_variant", "accent", "language")
_THEME_KEYS = {"theme", "dark_variant", "light_variant", "accent"}
_state = {}


def install(prefs, theme_mgr):
    """prefs: uygulamanın tercih deposu (.path, .data); theme_mgr: ThemeManager örneği."""
    path = getattr(prefs, "path", None)
    if not path or _state:
        return
    folder = os.path.dirname(path)
    os.makedirs(folder, exist_ok=True)
    watcher = QFileSystemWatcher([folder])
    timer = QTimer()
    timer.setSingleShot(True)
    timer.setInterval(200)          # kaydetme (tmp + replace) bitsin

    def mtime():
        try:
            return os.stat(path).st_mtime_ns
        except OSError:
            return 0

    def check():
        m = mtime()
        if not m or m == _state.get("mtime"):
            return
        _state["mtime"] = m
        try:
            with open(path, "r", encoding="utf-8") as f:
                disk = json.load(f)
        except (OSError, ValueError):
            return
        if not isinstance(disk, dict):
            return
        diff = {k: disk[k] for k in SHARED if k in disk and disk[k] != prefs.data.get(k)}
        if not diff:
            return
        prefs.data.update(diff)
        if _THEME_KEYS & diff.keys():
            try:
                theme_mgr.apply()
            except Exception:
                pass

    watcher.directoryChanged.connect(lambda _p: timer.start())
    watcher.fileChanged.connect(lambda _p: timer.start())
    timer.timeout.connect(check)
    _state.update(watcher=watcher, timer=timer, mtime=mtime(), check=check)
