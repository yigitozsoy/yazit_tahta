"""kamug bağlantıları (kamug: aynı ailenin medya oynatıcısı).

kamug'un transkriptten ürettiği notlarda yazının "ln" alanı {"kamug": video yolu, "t": saniye}; eski sürüm notlarındaki
anahtar da (LINK_KEYS) okunur.
Ctrl+tık ya da sağ tık › "kamug'da aç" → kamug videoyu o saniyede açar (kamug.exe "video" --at=SANİYE).
kamug yoksa eski sürümü denenir; o da yoksa video varsayılan programla açılır (zamansız)."""
import os
import sys

LINK_KEYS = ("kamug", "gamma")      # okuma sırası; yeni bağlantılar "kamug" ile yazılır


def video_of(link):
    """Bağlantının video yolu ("kamug", yoksa eski sürümün anahtarı) ya da ""."""
    if not isinstance(link, dict):
        return ""
    for k in LINK_KEYS:
        v = link.get(k)
        if isinstance(v, str) and v:
            return v
    return ""


def valid(link):
    return bool(video_of(link))


def make_link(video, sec=0.0):
    return {"kamug": video, "t": float(sec or 0)}


def fmt(sec):
    s = max(0, int(float(sec or 0)))
    h, m, s = s // 3600, s // 60 % 60, s % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _uninstall_locations(prefix, exe):
    """Kayıt defterindeki kurulumlar (DisplayName "prefix" ile başlayan) → InstallLocation\\exe adayları."""
    out = []
    try:
        import winreg
    except ImportError:
        return out
    base = r"Software\Microsoft\Windows\CurrentVersion\Uninstall"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, base) as k:
                for i in range(winreg.QueryInfoKey(k)[0]):
                    try:
                        with winreg.OpenKey(k, winreg.EnumKey(k, i)) as sk:
                            name = str(winreg.QueryValueEx(sk, "DisplayName")[0]).lower()
                            if name.startswith(prefix):
                                loc = str(winreg.QueryValueEx(sk, "InstallLocation")[0])
                                out.append(os.path.join(loc, exe))
                    except OSError:
                        continue
        except OSError:
            continue
    return out


def find_kamug():
    """Kurulu kamug.exe (kullanıcı başına kurulum, kayıt defterindeki kurulum yeri); yoksa eski sürümü; ya da None."""
    local = os.environ.get("LOCALAPPDATA", "")
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    cands = [os.path.join(local, "Programs", "kamug", "kamug.exe"), os.path.join(pf, "kamug", "kamug.exe")]
    cands += _uninstall_locations("kamug", "kamug.exe")
    cands += [os.path.join(local, "Programs", "gamma", "gamma.exe"), os.path.join(pf, "gamma", "gamma.exe")]
    cands += _uninstall_locations("gamma", "gamma.exe")
    return next((c for c in cands if c and os.path.isfile(c)), None)


def open_link(link):
    """Döndürür: "ok" | "missing" (video yok) | "fallback" (kamug yok, varsayılan programla açıldı)."""
    video = video_of(link)
    if not video or not os.path.exists(video):
        return "missing"
    sec = float(link.get("t") or 0)
    from PyQt6.QtCore import QProcess
    exe = find_kamug()
    if exe and QProcess.startDetached(exe, [video, f"--at={sec:.2f}"])[0]:
        return "ok"
    if sys.platform == "win32":
        os.startfile(video)      # noqa: S606 — kullanıcının kendi dosyası
        return "fallback"
    return "missing"
