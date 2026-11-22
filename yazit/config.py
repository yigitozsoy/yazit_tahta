"""Uygulama yolları ve kalıcı tercihler (%LOCALAPPDATA%\\yazit\\preferences.json).

Ad değişikliği (delta → yazıt): eski klasörler bir kez yeni ada taşınır (os.rename; hiçbir şey silinmez,
üzerine yazılmaz). Taşıma olmazsa o açılışta eski klasör kullanılır."""
import json
import os
import sys
import threading

if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

NOTE_EXT = ".yazit"             # yeni notların uzantısı
NOTE_EXTS = (".yazit", ".delta")   # açılan / listelenen not uzantıları (eski .delta notları da)


def is_note_file(path) -> bool:
    return isinstance(path, str) and path.lower().endswith(NOTE_EXTS)


APP_DIR_NAME = "yazit"          # klasör / kayıt adları (ASCII); görünen ad "yazıt"
OLD_DIR_NAME = "delta"          # eski ad: klasörler bir kez taşınır
_renamed = {}                   # bu açılışta taşınan klasörler: eski yol → yeni yol (eski yolla gelen dosyalar için)


def _migrate_dir(old, new, both="new"):
    """old varsa ve new yoksa old → new taşır. Kullanılacak klasörü döndürür (taşınamadıysa old).
    new boş bir klasörse (ör. başka bir program erken oluşturduysa) önce o kaldırılır — yalnızca boşsa.
    İkisi de doluysa hiçbirine dokunulmaz; both="new" yeniyi, both="old" eskiyi döndürür."""
    try:
        if not os.path.isdir(old):
            return new
        if os.path.isdir(new):
            try:
                os.rmdir(new)            # yalnızca boşsa başarılı olur; içi doluysa dokunulmaz
            except OSError:
                return old if both == "old" else new
        os.rename(old, new)
        _renamed[os.path.normcase(os.path.abspath(old))] = new
        return new
    except OSError:
        return old if os.path.isdir(old) else new


def remap_old_path(path):
    """Taşınan bir klasörün eski yolundaki dosya yolunu yeni yola çevirir (ör. kamug eski klasöre not yazıp açtıysa)."""
    if not path or os.path.exists(path):
        return path
    n = os.path.normcase(os.path.abspath(path))
    for old, new in _renamed.items():
        if n.startswith(old + os.sep):
            cand = os.path.join(new, os.path.abspath(path)[len(old) + 1:])
            if os.path.exists(cand):
                return cand
    return path


_LOCAL = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
DATA_DIR = _migrate_dir(os.path.join(_LOCAL, OLD_DIR_NAME), os.path.join(_LOCAL, APP_DIR_NAME))
NOTES_DIR = os.path.join(DATA_DIR, "notes")
TRASH_DIR = os.path.join(DATA_DIR, "trash")
PREFS_FILE = os.path.join(DATA_DIR, "preferences.json")

for _d in (DATA_DIR, NOTES_DIR, TRASH_DIR):
    os.makedirs(_d, exist_ok=True)


def asset(name: str) -> str:
    return os.path.join(ASSETS_DIR, name)


DEFAULTS = {
    "language": "tr",
    "theme": "amoled",
    "research_theme": "yazit",      # araştırma modu: yazit | kamuflaj (yigitozsoy.net) | soft (pastel)
    "accent": "gray",
    "grid": "dots",                 # dots | lines | none
    "save_format": "png",           # Ctrl+S biçimi: png | jpg | pdf
    "toolbar_pos": "bottom",        # bottom | top | left | right
    "tool_keys": {},                # kullanıcının değiştirdiği araç tuşları (boş = varsayılan rakamlar)
    "check_updates": True,
    "last_update_check": 0,
    "wheel": "zoom",                # zoom | scroll  (fare tekerleği)
    "sidebar_visible": True,
    "notes_dir": "",                # boş = Resimler\yazit (anahtar adı değişmez: kamug da okur)
    "pinned": False,
    "close_to_tray": True,
    "autostart": False,
    "tray_hint_shown": False,
    "capture_autocopy": True,
    "capture_target": "new",        # new | current  (alıntı yazıt'a hangi nota gider)
    "hotkey_capture": "Win+Shift+X",       # Win+Shift+A Windows 11 tarafından kullanılıyor
    "hotkey_annotate": "Win+Shift+D",
    "hotkey_note": "Win+Shift+N",
    "hotkey_record": "Win+Shift+E",        # Win+Shift+R Windows 11 Ekran Alıntısı Aracı'nın
    "record_mic": "",               # "" = sessiz, yoksa DirectShow mikrofon adı
    "record_fps": 30,
    "snapshot_dir": "",
    "video_dir": "",
    "window_geometry": None,
    "last_note": None,
    # araç durumu
    "tool": "pen",
    "color": "auto",
    "width": 2.5,
    "last_shape": "arrow",
    "eng_shapes": False,      # şekil menüsünde mühendislik şekilleri (Seçenekler)
    "custom_color": "#b0b0b0",
}


class Prefs:
    def __init__(self, path=PREFS_FILE):
        self.path = path
        self.data = {}
        self._lock = threading.Lock()
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                self.data.update(loaded)
        except (OSError, ValueError):
            pass

    def get(self, key, default=None):
        if key in self.data:
            return self.data[key]
        return DEFAULTS.get(key, default)

    def set(self, key, value):
        if self.data.get(key) == value and key in self.data:
            return
        self.data[key] = value
        self.save()

    def save(self):
        with self._lock:
            tmp = self.path + ".tmp"
            try:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(self.data, f, ensure_ascii=False, indent=1)
                os.replace(tmp, self.path)
            except OSError:
                pass


prefs = Prefs()

# kullanıcının seçebildiği klasörler: biri eski varsayılan klasörün içini gösteriyorsa o klasör taşınmaz
_PATH_PREFS = ("notes_dir", "snapshot_dir", "video_dir", "research_dir")
# taşınan klasörün içindeki yolları tutan tercihler (yeni yola çevrilir)
_RECENT_PREFS = ("research_recent", "research_last", "external_notes")
_defaults = {}                  # (konum, alt yol) → bu açılışta kullanılan varsayılan klasör


def _inside(path, folder):
    p, f = os.path.normcase(os.path.abspath(path)), os.path.normcase(os.path.abspath(folder))
    return p == f or p.startswith(f + os.sep)


def _rewrite_paths(old, new):
    """Taşınan klasörün içindeki kayıtlı yolları (son araştırmalar vb.) yeni klasöre çevirir."""
    old = os.path.abspath(old)

    def fix(v):
        if not (isinstance(v, str) and v and _inside(v, old)):
            return v
        rest = os.path.abspath(v)[len(old):].lstrip("\\/")
        return os.path.join(new, rest) if rest else new
    for key in _RECENT_PREFS:
        v = prefs.data.get(key)
        nv = [fix(x) for x in v] if isinstance(v, list) else fix(v)
        if nv != v:
            prefs.set(key, nv)


def _std_location(kind):
    try:
        from PyQt6.QtCore import QStandardPaths
        loc = getattr(QStandardPaths.StandardLocation, kind)
        return QStandardPaths.writableLocation(loc) or os.path.expanduser("~")
    except Exception:
        return os.path.expanduser("~")


def default_dir(kind, *sub):
    r"""Varsayılan kullanıcı klasörü: <Resimler|Videolar|Belgeler>\yazit[\sub]. Eski <…>\delta varsa bir kez
    yazit'e taşınır (hiçbir tercih onun içini göstermiyorsa). Taşınamazsa o açılışta eskisi kullanılır;
    ikisi de doluysa eski klasör kullanılmaya devam eder (notlar listede kaybolmasın)."""
    key = (kind, sub)
    if key not in _defaults:
        base = _std_location(kind)
        old, new = os.path.join(base, OLD_DIR_NAME), os.path.join(base, APP_DIR_NAME)
        if any(prefs.data.get(k) and _inside(prefs.data[k], old) for k in _PATH_PREFS):
            root = old if os.path.isdir(old) else new     # kullanıcı eski klasörü elle seçmiş: dokunma
        else:
            root = _migrate_dir(old, new, both="old")
            if os.path.normcase(os.path.abspath(old)) in _renamed:
                _rewrite_paths(old, new)
        _defaults[key] = os.path.join(root, *sub)
    return _defaults[key]


def migrate_user_dirs():
    """Açılışta bir kez: varsayılan not / alıntı, video ve araştırma klasörlerini yeni ada taşır."""
    default_dir("PicturesLocation")
    default_dir("MoviesLocation")
    default_dir("DocumentsLocation", "Araştırmalar")


def video_dir() -> str:
    """Ekran videolarının kaydedildiği klasör (varsayılan Videolar\\yazit)."""
    d = prefs.get("video_dir") or default_dir("MoviesLocation")
    os.makedirs(d, exist_ok=True)
    return d


def notes_root() -> str:
    """Notların (.yazit; eski .delta da okunur) klasörü: varsayılan Resimler\\yazit (alıntılarla aynı yer).
    Alt klasörler not klasörleridir."""
    d = prefs.get("notes_dir") or default_dir("PicturesLocation")
    os.makedirs(d, exist_ok=True)
    return d


def snapshot_dir() -> str:
    """Ekran alıntılarının / PNG dışa aktarımlarının kaydedildiği klasör (varsayılan Resimler\\yazit)."""
    d = prefs.get("snapshot_dir") or default_dir("PicturesLocation")
    os.makedirs(d, exist_ok=True)
    return d


def research_root() -> str:
    r"""Araştırma klasörlerinin varsayılan yeri: Belgeler\yazit\Araştırmalar (prefs research_dir)."""
    d = prefs.get("research_dir") or default_dir("DocumentsLocation", "Araştırmalar")
    os.makedirs(d, exist_ok=True)
    return d
