"""Yazı tipleri: her alfabe için yedek zinciri, yazıt ile gelen ücretsiz yazı tipleri, kullanıcının eklediği yazı tipleri.

Yedek zinciri: seçilen yazı tipinde olmayan harf sıradaki yazı tipinden çizilir (Göktürk, Gotik, çivi yazısı,
hiyeroglif → Segoe UI Historic; Çince → Microsoft YaHei UI; Hintçe → Nirmala UI …). Windows 10/11'le gelir."""
import os
import shutil

from PyQt6.QtGui import QFont, QFontDatabase

from .config import DATA_DIR, asset

UI = "Segoe UI Variable Text"
FALLBACK = [
    "Segoe UI", "Segoe UI Historic", "Segoe UI Symbol", "Segoe UI Emoji",
    "Nirmala UI", "Microsoft YaHei UI", "Yu Gothic UI", "Malgun Gothic", "Microsoft JhengHei UI",
    "Leelawadee UI", "Ebrima", "Gadugi", "Mongolian Baiti", "Myanmar Text", "Microsoft Himalaya",
    "Javanese Text", "Sylfaen", "Cambria Math", "Noto Sans Linear B",
]
BUNDLED_DIR = asset("fonts")
USER_DIR = os.path.join(DATA_DIR, "fonts")
FONT_EXT = (".ttf", ".otf", ".ttc")

_bundled = []      # yazıt ile gelen aileler (sıralı)
_user = []         # kullanıcının eklediği aileler
_loaded = False
_app_names = set()   # yazıt'ın yüklediği dosyaların tüm aile adları (sistem listesine karışmasın)


def chain(family=None):
    """Aile + yedekler (tekrarsız)."""
    out = [family or UI]
    for f in [UI] + FALLBACK:
        if f not in out:
            out.append(f)
    return out


def font(family=None):
    load()     # yedek zincirindeki Noto Sans Linear B yazıt ile gelir
    f = QFont(family or UI)
    f.setFamilies(chain(family))
    return f


def qss_families():
    return ", ".join('"%s"' % f for f in chain())


def add_font_file(path):
    """QFontDatabase.addApplicationFont; yol ASCII dışı harf içerince (ör. "yazıt" klasörü) Qt dosyayı açamayabiliyor
    → dosyanın içeriğinden yükle."""
    fid = QFontDatabase.addApplicationFont(path)
    if fid < 0:
        try:
            from PyQt6.QtCore import QByteArray
            with open(path, "rb") as f:
                fid = QFontDatabase.addApplicationFontFromData(QByteArray(f.read()))
        except OSError:
            fid = -1
    return fid


def _load_dir(d):
    fams = []
    try:
        names = sorted(os.listdir(d))
    except OSError:
        return fams
    for n in names:
        if n.lower().endswith(FONT_EXT):
            fid = add_font_file(os.path.join(d, n))
            fnames = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
            _app_names.update(fnames)
            fam = _main_family(n, fnames)
            if fam and fam not in fams:
                fams.append(fam)
    return fams


def _main_family(fname, names):
    """Değişken yazı tipleri her kalınlığı ayrı aile adıyla da kaydeder ("Inter Thin", "Inter Light" …);
    listede yalnızca ana aile görünsün: dosya adına uyan ("ArchivoBlack-…" → "Archivo Black"), yoksa en kısası."""
    if not names:
        return ""
    stem = os.path.splitext(fname)[0].split("[")[0].split("-")[0].replace(" ", "").lower()
    for f in names:
        if f.replace(" ", "").lower() == stem:
            return f
    return min(names, key=len)


def load():
    """Uygulama açılırken (QApplication'dan sonra) bir kez çağrılır."""
    global _loaded
    if _loaded:
        return
    _loaded = True
    _bundled[:] = [f for f in _load_dir(BUNDLED_DIR) if not f.startswith("Noto Sans Linear")]
    _user[:] = _load_dir(USER_DIR)


def bundled():
    load()
    return sorted(_bundled, key=str.lower)


def user_fonts():
    load()
    return sorted(_user, key=str.lower)


def system_fonts():
    load()
    return [f for f in QFontDatabase.families()
            if not f.startswith("@") and f not in _app_names and not QFontDatabase.isPrivateFamily(f)]


def add_user_font(path):
    """.ttf / .otf dosyasını %LOCALAPPDATA%\\yazit\\fonts'a kopyalar, yükler; eklenen aileleri döndürür."""
    load()
    if not path.lower().endswith(FONT_EXT):
        return []
    try:
        os.makedirs(USER_DIR, exist_ok=True)
        dst = os.path.join(USER_DIR, os.path.basename(path))
        if os.path.normcase(os.path.abspath(path)) != os.path.normcase(dst):
            shutil.copy2(path, dst)
    except OSError:
        return []
    fid = add_font_file(dst)
    names = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
    _app_names.update(names)
    fams = [_main_family(os.path.basename(dst), names)] if names else []
    if not fams:
        try:
            os.remove(dst)
        except OSError:
            pass
        return []
    for f in fams:
        if f not in _user:
            _user.append(f)
    return list(fams)


def available(family):
    return not family or family in QFontDatabase.families()
