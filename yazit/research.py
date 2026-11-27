"""Araştırma modu — model: bir araştırma = bir klasör.

Klasördeki dosyalar kaynaklardır (alt klasörler dahil, gizli dosyalar hariç). Araştırmanın kendi bilgisi klasördeki
`araştırma.yazit-research` (JSON) dosyasında:
  {"format": "delta-research", "version": 1, "title", "created",
   "sources": {göreli yol: {"type", "title", "author", "year", ...elle değiştirilenler}},
   "probe":   {göreli yol: {"m": mtime, "s": boyut, ...dosyadan okunanlar}},   (önbellek; değişince yeniden okunur)
   "page": {...araştırma sayfası}, "notes": [...hızlı notlar], "highlights": {...}}

Tür (raf görünümü): book | article | video | image | link. PDF'de ISBN ya da çok sayfa → kitap, değilse makale.
Kullanıcı sağ tıkla türü değiştirebilir (sources[yol]["type"])."""
import hashlib
import json
import os
import re
import subprocess
import time
import zipfile
from datetime import datetime

from PyQt6.QtCore import QObject, QTimer, QFileSystemWatcher, pyqtSignal

from .config import prefs, research_root

META_FILE = "araştırma.yazit-research"
OLD_META_FILE = "araştırma.delta-research"   # eski sürümlerin dosya adı: açılınca yeni ada çevrilir
FORMAT = "delta-research"                    # iç biçim adı (dosyanın içinde), uyumluluk için değişmez


def _meta_path(folder, migrate=False):
    """Klasörün araştırma dosyası. Yalnızca eski adlı dosya varsa: migrate=True ise yeni ada çevrilir
    (olmazsa — dosya kilitli vb. — eskisi kullanılır), değilse eskisinin yolu döner."""
    new, old = os.path.join(folder, META_FILE), os.path.join(folder, OLD_META_FILE)
    if os.path.exists(new) or not os.path.exists(old):
        return new
    if migrate:
        try:
            os.rename(old, new)
            return new
        except OSError:
            pass
    return old

EXT_KIND = {}
for _k, _exts in {
    "pdf": (".pdf",),
    "doc": (".docx", ".doc", ".rtf", ".odt"),
    "epub": (".epub",),
    "text": (".txt", ".md", ".markdown"),
    "image": (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tif", ".tiff"),
    "video": (".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v", ".wmv"),
    "link": (".url", ".webloc"),
}.items():
    for _e in _exts:
        EXT_KIND[_e] = _k

TYPES = ("book", "article", "video", "image", "link")
BOOK_PAGES = 80            # bu kadar sayfadan uzun PDF kitap sayılır
BOOK_WORDS = 30000

# kitap sırtı renkleri: koyu, doygun değil (sitenin zırh / grafit / mürekkep paletine uyar; mor yok)
SPINE_COLORS = ["#6E2A26", "#2F3B33", "#3B3A35", "#5C4A2C", "#24384A", "#6A5A3C", "#4B2E29", "#1F2B2F",
                "#7E6128", "#2E4A43", "#5A2F22", "#3E4651", "#8A3A2C", "#334236"]

ISBN_RE = re.compile(r"ISBN(?:-1[03])?[:\s]*((?:97[89][\s-]?)?(?:\d[\s-]?){9}[\dXx])")


def color_for(title):
    h = int(hashlib.md5((title or "?").encode("utf-8")).hexdigest()[:8], 16)
    return SPINE_COLORS[h % len(SPINE_COLORS)]


def seed_for(key):
    return int(hashlib.md5((key or "").encode("utf-8")).hexdigest()[:8], 16)


def _clean_title(name):
    base = os.path.splitext(os.path.basename(name))[0]
    base = re.sub(r"[_]+", " ", base)
    return re.sub(r"\s+", " ", base).strip() or name


def _excerpt(text, n=320):
    text = re.sub(r"[ \t\r\f\v]+", " ", text or "")
    lines = [ln.strip() for ln in text.split("\n") if len(ln.strip()) > 2]
    return "\n".join(lines)[:n]


# --------------------------------------------------------------------------- dosyadan bilgi okuma
def probe_pdf(path):
    import pypdfium2 as pdfium
    out = {}
    doc = pdfium.PdfDocument(path)
    try:
        out["pages"] = len(doc)
        try:
            md = doc.get_metadata_dict(skip_empty=True)
        except Exception:
            md = {}
        if md.get("Title") and len(md["Title"].strip()) > 2 and not md["Title"].lower().startswith(("microsoft", "untitled")):
            out["title"] = md["Title"].strip()
        if md.get("Author"):
            out["author"] = md["Author"].strip()
        text = ""
        for i in range(min(len(doc), 6)):
            page = doc[i]
            tp = page.get_textpage()
            t = tp.get_text_range() or ""
            tp.close()
            page.close()
            if i == 0 or not text.strip():
                out["excerpt"] = _excerpt(t)
            text += t + "\n"
            mi = ISBN_RE.search(t)
            if mi:
                out["isbn"] = re.sub(r"[\s-]", "", mi.group(1))
                break
    finally:
        doc.close()
    return out


def probe_docx(path):
    out = {}
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        if "docProps/core.xml" in names:
            core = z.read("docProps/core.xml").decode("utf-8", "ignore")
            for tag, key in (("dc:title", "title"), ("dc:creator", "author")):
                m = re.search(rf"<{tag}[^>]*>([^<]+)</{tag}>", core)
                if m and m.group(1).strip():
                    out[key] = m.group(1).strip()
        if "docProps/app.xml" in names:
            app = z.read("docProps/app.xml").decode("utf-8", "ignore")
            for tag, key in (("Pages", "pages"), ("Words", "words")):
                m = re.search(rf"<{tag}>(\d+)</{tag}>", app)
                if m:
                    out[key] = int(m.group(1))
        if "word/document.xml" in names:
            xml = z.read("word/document.xml").decode("utf-8", "ignore")[:200000]
            paras = []
            for p in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
                t = "".join(re.findall(r"<w:t[^>]*>([^<]*)</w:t>", p)).strip()
                if t:
                    paras.append(t)
                if len(paras) > 8:
                    break
            out["excerpt"] = _excerpt("\n".join(paras))
            if "words" not in out:
                out["words"] = len(re.findall(r"<w:t[^>]*>", xml))
    return out


def probe_text(path):
    with open(path, "rb") as f:
        raw = f.read(4000)
    t = raw.decode("utf-8", "ignore")
    out = {"excerpt": _excerpt(t)}
    m = re.match(r"\s*#\s+(.+)", t)
    if m:
        out["title"] = m.group(1).strip()
    return out


def probe_video(path):
    out = {}
    try:
        from .recorder import find_ffmpeg
        ff = find_ffmpeg()
        if ff:
            r = subprocess.run([ff, "-hide_banner", "-nostdin", "-i", path], capture_output=True, timeout=8,
                               stdin=subprocess.DEVNULL,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            m = re.search(r"Duration: (\d+):(\d+):(\d+)", r.stderr.decode("utf-8", "ignore"))
            if m:
                out["duration"] = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    except Exception:
        pass
    # kamug'un dökümü (aynı adlı .srt / .vtt / .txt / .json) varsa alıntılar zamanlı olur
    base = os.path.splitext(path)[0]
    for ext in (".srt", ".vtt", ".transcript.json", ".json", ".txt"):
        if os.path.isfile(base + ext):
            out["transcript"] = os.path.basename(base + ext)
            break
    return out


def probe_link(path):
    out = {}
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            t = f.read(8000)
        m = re.search(r"^URL=(.+)$", t, re.M) or re.search(r"<string>(https?://[^<]+)</string>", t)
        if m:
            out["url"] = m.group(1).strip()
    except OSError:
        pass
    return out


def probe(path, kind):
    try:
        if kind == "pdf":
            return probe_pdf(path)
        if kind == "doc" and path.lower().endswith(".docx"):
            return probe_docx(path)
        if kind == "text":
            return probe_text(path)
        if kind == "video":
            return probe_video(path)
        if kind == "link":
            return probe_link(path)
    except Exception as e:      # bozuk / şifreli dosya: rafta yine görünsün
        return {"error": str(e)[:200]}
    return {}


def guess_type(kind, info):
    if kind in ("video", "image", "link"):
        return kind
    if kind == "epub":
        return "book"
    if info.get("isbn"):
        return "book"
    if (info.get("pages") or 0) >= BOOK_PAGES or (info.get("words") or 0) >= BOOK_WORDS:
        return "book"
    return "article"


# --------------------------------------------------------------------------- kaynak
class Source:
    __slots__ = ("rel", "path", "kind", "info", "over")

    def __init__(self, rel, path, kind, info, over):
        self.rel, self.path, self.kind, self.info, self.over = rel, path, kind, info, over

    def get(self, key, default=None):
        if key in self.over and self.over[key] not in (None, ""):
            return self.over[key]
        return self.info.get(key, default)

    @property
    def type(self):
        t = self.over.get("type")
        return t if t in TYPES else guess_type(self.kind, self.info)

    @property
    def title(self):
        return self.get("title") or _clean_title(self.rel)

    @property
    def author(self):
        a = self.get("author", "")
        if not a:      # "Yazar - Başlık.pdf"
            base = os.path.splitext(os.path.basename(self.rel))[0]
            if " - " in base:
                a = base.split(" - ", 1)[0].strip()
        return a

    @property
    def year(self):
        return self.get("year", "")

    @property
    def color(self):
        return self.over.get("color") or color_for(self.title)

    @property
    def seed(self):
        return seed_for(self.rel)

    def short_author(self):
        """Alıntı künyesi için: "Ogorkiewicz" (ilk yazarın soyadı)."""
        a = self.author.split(";")[0].split(",")[0].split(" and ")[0].split(" ve ")[0].strip()
        return a.split()[-1] if a.split() else ""

    def cite(self, page=None):
        who = self.short_author() or self.title
        return f"{who} · s. {page}" if page else who


# --------------------------------------------------------------------------- araştırma
class Research(QObject):
    """Bir araştırma klasörü. sources_changed: raf yenilensin; changed: başlık / sayfa / notlar."""
    sources_changed = pyqtSignal()
    changed = pyqtSignal()

    def __init__(self, folder, readonly=False):
        super().__init__()
        self.folder = os.path.abspath(folder)
        self.readonly = readonly        # MCP sunucusu: okur, hiçbir şey yazmaz / izlemez
        self.meta_path = _meta_path(self.folder, migrate=not readonly)
        self.data = {"format": FORMAT, "version": 1, "title": os.path.basename(self.folder),
                     "created": datetime.now().isoformat(timespec="seconds"),
                     "sources": {}, "probe": {}, "page": {}, "notes": [], "highlights": {}}
        self.sources = []          # [Source] sıralı
        self._pending = []         # bilgisi okunacak (rel, path, kind)
        self._save_timer = QTimer(self, singleShot=True, interval=600, timeout=self.save)
        self._probe_timer = QTimer(self, singleShot=True, interval=0, timeout=self._probe_next)
        self._scan_timer = QTimer(self, singleShot=True, interval=400, timeout=self.scan)
        self.watcher = QFileSystemWatcher(self)
        self.watcher.directoryChanged.connect(lambda _p: self._scan_timer.start())
        self.load()

    # ---- dosya
    def load(self):
        try:
            with open(self.meta_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict) and d.get("format") == FORMAT:
                for k, v in d.items():
                    self.data[k] = v
        except (OSError, ValueError):
            pass

    def save(self):
        self._save_timer.stop()
        if self.readonly:
            return
        tmp = self.meta_path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.meta_path)
            try:     # gizli: rafta / Gezgin'de göze batmasın
                import ctypes
                ctypes.windll.kernel32.SetFileAttributesW(self.meta_path, 0x2)
            except Exception:
                pass
        except OSError:
            pass

    def touch(self):
        """Bir şey değişti: kısa süre sonra kaydet."""
        self._save_timer.start()
        self.changed.emit()

    def close(self):
        if self._save_timer.isActive():
            self.save()
        self._probe_timer.stop()
        self._scan_timer.stop()
        if self.watcher.directories():
            self.watcher.removePaths(self.watcher.directories())

    # ---- başlık
    @property
    def title(self):
        return self.data.get("title") or os.path.basename(self.folder)

    def set_title(self, t):
        t = (t or "").strip()
        if t and t != self.data.get("title"):
            self.data["title"] = t
            self.touch()

    # ---- tarama
    def scan(self):
        found = []
        exports = set(self.data.get("exports") or [])
        dirs = [self.folder]
        for root, dnames, fnames in os.walk(self.folder):
            dnames[:] = sorted(d for d in dnames if not d.startswith((".", "_delta", "_yazit")))
            for d in dnames:
                dirs.append(os.path.join(root, d))
            for n in sorted(fnames, key=str.lower):
                if n.startswith((".", "~$")) or n in (META_FILE, OLD_META_FILE) or n.endswith(".tmp"):
                    continue
                if os.path.relpath(os.path.join(root, n), self.folder).replace("\\", "/") in exports:
                    continue          # yazıt'ın dışa aktardığı dosya kaynak sayılmaz
                kind = EXT_KIND.get(os.path.splitext(n)[1].lower())
                if kind is None:
                    continue
                p = os.path.join(root, n)
                found.append((os.path.relpath(p, self.folder).replace("\\", "/"), p, kind))
        old = set(self.watcher.directories())
        if old != set(dirs) and not self.readonly:
            if old:
                self.watcher.removePaths(list(old))
            self.watcher.addPaths(dirs)
        cache = self.data.setdefault("probe", {})
        over = self.data.setdefault("sources", {})
        srcs, pending = [], []
        for rel, p, kind in found:
            try:
                st = os.stat(p)
            except OSError:
                continue
            c = cache.get(rel)
            if not c or c.get("m") != int(st.st_mtime) or c.get("s") != st.st_size:
                c = {"m": int(st.st_mtime), "s": st.st_size}
                cache[rel] = c
                pending.append((rel, p, kind))
            srcs.append(Source(rel, p, kind, c, over.setdefault(rel, {})))
        gone = set(cache) - {s.rel for s in srcs}
        for rel in gone:
            cache.pop(rel, None)
        self.sources = srcs
        self._pending = pending
        if pending:
            self._probe_timer.start()
        if gone or pending:
            self._save_timer.start()
        self.sources_changed.emit()

    def _probe_next(self):
        """Bilgileri birer birer oku (arayüz donmasın); her 6 dosyada bir rafı yenile."""
        t0 = time.monotonic()
        n = 0
        while self._pending and time.monotonic() - t0 < 0.08:
            rel, p, kind = self._pending.pop(0)
            info = probe(p, kind)
            c = self.data["probe"].get(rel)
            if c is not None:
                c.update(info)
            n += 1
        if self._pending:
            self._probe_timer.start()
        self._save_timer.start()
        self.sources_changed.emit()

    def probe_all_now(self):
        """Test / dışa aktarım için: bekleyen tüm bilgileri hemen oku."""
        while self._pending:
            self._probe_next()
        self._probe_timer.stop()

    # ---- kaynaklar
    def by_type(self):
        out = {t: [] for t in TYPES}
        for s in self.sources:
            out[s.type].append(s)
        return out

    def source(self, rel):
        return next((s for s in self.sources if s.rel == rel), None)

    def set_override(self, rel, **kw):
        o = self.data.setdefault("sources", {}).setdefault(rel, {})
        for k, v in kw.items():
            if v in (None, ""):
                o.pop(k, None)
            else:
                o[k] = v
        self._save_timer.start()
        self.sources_changed.emit()

    def add_files(self, paths):
        """Dışarıdan bırakılan dosyaları klasöre kopyala (aynı ad varsa "(2)"). Eklenen göreli yollar."""
        import shutil
        added = []
        for p in paths:
            if not os.path.isfile(p) or EXT_KIND.get(os.path.splitext(p)[1].lower()) is None:
                continue
            if os.path.abspath(os.path.dirname(p)).lower().startswith(self.folder.lower()):
                continue          # zaten klasörde
            name = os.path.basename(p)
            dst = os.path.join(self.folder, name)
            b, e = os.path.splitext(name)
            i = 2
            while os.path.exists(dst):
                dst = os.path.join(self.folder, f"{b} ({i}){e}")
                i += 1
            try:
                shutil.copy2(p, dst)
                added.append(os.path.relpath(dst, self.folder).replace("\\", "/"))
            except OSError:
                pass
        if added:
            self.scan()
        return added

    # ---- notlar
    @property
    def notes(self):
        return self.data.setdefault("notes", [])

    def add_note(self, text, anchor=None):
        n = {"id": f"n{int(time.time() * 1000)}", "text": text, "t": datetime.now().isoformat(timespec="seconds")}
        if anchor:
            n["anchor"] = anchor
        self.notes.append(n)
        self.touch()
        return n

    def remove_note(self, nid):
        self.data["notes"] = [n for n in self.notes if n.get("id") != nid]
        self.touch()

    # ---- sayfa
    @property
    def page(self):
        return self.data.setdefault("page", {})

    def meta_line(self, words=None):
        """"21 KAS 2026 · 14 DK OKUMA · 3 BÖLÜM · 6 KAYNAK" """
        months = ["OCA", "ŞUB", "MAR", "NİS", "MAY", "HAZ", "TEM", "AĞU", "EYL", "EKİ", "KAS", "ARA"]
        try:
            d = datetime.fromisoformat(self.data.get("created"))
        except (TypeError, ValueError):
            d = datetime.now()
        parts = [f"{d.day} {months[d.month - 1]} {d.year}"]
        if words is not None:
            parts.append(f"{max(1, round(words / 220))} DK OKUMA")
        h = self.page.get("sections")
        if h:
            parts.append(f"{h} BÖLÜM")
        parts.append(f"{len(self.sources)} KAYNAK")
        return " · ".join(parts)


# --------------------------------------------------------------------------- son açılanlar
def recent():
    out = []
    for p in prefs.get("research_recent", []) or []:
        if isinstance(p, str) and os.path.isdir(p) and p not in out:
            out.append(p)
    return out


def remember(folder):
    lst = [folder] + [p for p in recent() if os.path.normcase(p) != os.path.normcase(folder)]
    prefs.set("research_recent", lst[:12])


def forget(folder):
    prefs.set("research_recent", [p for p in recent() if os.path.normcase(p) != os.path.normcase(folder)])


def new_research(name):
    """Belgeler\\yazit\\Araştırmalar\\<ad> klasörünü aç (varsa "ad (2)")."""
    from .pages import safe_name
    base = safe_name(name or "Yeni araştırma")
    root = research_root()
    d = os.path.join(root, base)
    i = 2
    while os.path.exists(d):
        d = os.path.join(root, f"{base} ({i})")
        i += 1
    os.makedirs(d)
    r = Research(d)
    r.data["title"] = (name or "").strip() or base
    r.save()
    r.close()
    return d


def peek(folder):
    """Ana ekran listesi için: (başlık, kaynak sayısı) — klasörü taramadan."""
    title = os.path.basename(folder)
    n = None
    try:
        with open(_meta_path(folder), "r", encoding="utf-8") as f:
            d = json.load(f)
        title = d.get("title") or title
        n = len(d.get("probe") or {})
    except (OSError, ValueError):
        pass
    return title, n
