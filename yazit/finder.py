"""Araştırma modu — internetten kaynak bulma ve indirme (araştırma klasörüne).

  bağlantı  → ScienceDirect (pii → Crossref → DOI), doi.org, arXiv, doğrudan PDF, ya da herhangi bir makale sayfası
              (citation_doi / citation_pdf_url / citation_title meta etiketleri)
  DOI       → OpenAlex (başlık, yazarlar, yıl, açık erişim PDF adresleri); bulunamazsa Crossref
  arama     → OpenAlex works?search=

İndirme yalnızca herkese açık PDF'leri dener (açık erişim kopyası, arXiv, yayıncının serbest PDF'i). PDF yoksa
(abonelik gerekiyorsa) kaynak bağlantı (.url) olarak eklenir; başlık / yazar / yıl / DOI yine kaynağın bilgisine yazılır.
Ağ işleri arka plan iş parçacığında; sonuç Qt sinyaliyle ana iş parçacığına döner (`Finder`)."""
import html
import json
import os
import re
import threading
import urllib.error
import urllib.parse
import urllib.request

from PyQt6.QtCore import QObject, pyqtSignal

from . import __version__, REPO

UA_API = f"yazit/{__version__} (+https://github.com/{REPO})"
UA_WEB = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
          "Chrome/130.0 Safari/537.36")
TIMEOUT = 20
MAX_PDF = 200 * 1024 * 1024
OPENALEX = "https://api.openalex.org/works"
CROSSREF = "https://api.crossref.org/works"
OFFLINE = "offline"          # FetchError metni: internete ulaşılamadı (panel çevirir)

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>]+)", re.I)
ARXIV_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/[0-9]{7})(?:v\d+)?", re.I)
PII_RE = re.compile(r"/pii/([A-Z0-9()\-]{15,})", re.I)


class FetchError(Exception):
    pass


# --------------------------------------------------------------------------- HTTP
def _get(url, accept=None, web=False, limit=None):
    """(bayt, içerik türü, son adres)."""
    req = urllib.request.Request(url, headers={
        "User-Agent": UA_WEB if web else UA_API,
        "Accept": accept or "*/*",
        "Accept-Language": "tr,en;q=0.8",
    })
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            data = r.read(limit + 1) if limit else r.read()
            return data, r.headers.get("Content-Type", ""), r.geturl()
    except urllib.error.HTTPError as e:
        raise FetchError(f"HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise FetchError(OFFLINE) from e        # DNS / bağlantı / zaman aşımı


def _json(url):
    data, _ct, _u = _get(url, "application/json")
    try:
        return json.loads(data.decode("utf-8"))
    except ValueError as e:
        raise FetchError("JSON") from e


# --------------------------------------------------------------------------- kaynak bilgisi
def empty():
    return {"title": "", "authors": [], "year": "", "doi": "", "url": "", "venue": "", "pdfs": [], "lands": [],
            "kind": "article"}


def _clean_doi(d):
    d = urllib.parse.unquote(d or "").strip().rstrip(".,;)")
    d = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", d, flags=re.I)
    d = re.sub(r"^doi:\s*", "", d, flags=re.I)
    return d.lower()


def _from_openalex(w):
    p = empty()
    p["title"] = (w.get("title") or w.get("display_name") or "").strip()
    p["authors"] = [a.get("author", {}).get("display_name", "") for a in (w.get("authorships") or [])][:12]
    p["authors"] = [a for a in p["authors"] if a]
    p["year"] = str(w.get("publication_year") or "")
    p["doi"] = _clean_doi(w.get("doi") or "")
    loc = w.get("primary_location") or {}
    p["venue"] = ((loc.get("source") or {}).get("display_name") or "")
    p["url"] = ("https://doi.org/" + p["doi"]) if p["doi"] else (loc.get("landing_page_url") or w.get("id") or "")
    pdfs = []
    for l in [w.get("best_oa_location") or {}] + list(w.get("locations") or []):
        u = (l or {}).get("pdf_url")
        if u and u not in pdfs:
            pdfs.append(u)
    oa = (w.get("open_access") or {}).get("oa_url")
    if oa and oa not in pdfs and oa.lower().endswith(".pdf"):
        pdfs.append(oa)
    p["pdfs"] = pdfs
    # PDF adresi vermeyen açık kopyalar (PMC, üniversite deposu …): indirirken sayfasından PDF aranır
    p["lands"] = [l.get("landing_page_url") for l in (w.get("locations") or [])
                  if l and l.get("is_oa") and l.get("landing_page_url") and not l.get("pdf_url")]
    p["kind"] = "book" if w.get("type") in ("book", "monograph") else "article"
    p["oa"] = bool((w.get("open_access") or {}).get("is_oa")) or bool(pdfs)
    return p


def _from_crossref(m):
    p = empty()
    p["title"] = " ".join((m.get("title") or [""])[:1]).strip()
    p["authors"] = [" ".join(x for x in (a.get("given"), a.get("family")) if x) for a in (m.get("author") or [])][:12]
    p["authors"] = [a for a in p["authors"] if a]
    parts = ((m.get("issued") or {}).get("date-parts") or [[None]])[0]
    p["year"] = str(parts[0]) if parts and parts[0] else ""
    p["doi"] = _clean_doi(m.get("DOI") or "")
    p["url"] = "https://doi.org/" + p["doi"] if p["doi"] else (m.get("URL") or "")
    p["venue"] = " ".join((m.get("container-title") or [""])[:1])
    for l in m.get("link") or []:
        if "pdf" in (l.get("content-type") or "") and l.get("URL"):      # indirilince %PDF denetlenir
            p["pdfs"].append(l["URL"])
    p["kind"] = "book" if m.get("type") in ("book", "monograph", "edited-book") else "article"
    return p


def by_doi(doi):
    doi = _clean_doi(doi)
    try:
        return _from_openalex(_json(f"{OPENALEX}/doi:{urllib.parse.quote(doi, safe='/')}"))
    except FetchError:
        pass
    m = _json(f"{CROSSREF}/{urllib.parse.quote(doi, safe='/')}").get("message") or {}
    if not m:
        raise FetchError("DOI bulunamadı")
    return _from_crossref(m)


def doi_from_pii(pii):
    """ScienceDirect PII (S0001457517300000) → DOI (Crossref alternative-id)."""
    pii = re.sub(r"[^A-Za-z0-9]", "", pii).upper()
    d = _json(f"{CROSSREF}?filter=alternative-id:{pii}&rows=1&select=DOI")
    items = (d.get("message") or {}).get("items") or []
    return items[0].get("DOI", "") if items else ""


def _meta_tags(page):
    """HTML'deki <meta name=… content=…> (çoklu değer listede)."""
    out = {}
    for m in re.finditer(r"<meta\s+[^>]*>", page, re.I):
        tag = m.group(0)
        n = re.search(r"(?:name|property)\s*=\s*[\"']([^\"']+)", tag, re.I)
        c = re.search(r"content\s*=\s*[\"']([^\"']*)", tag, re.I)
        if n and c:
            out.setdefault(n.group(1).lower(), []).append(html.unescape(c.group(1)).strip())
    return out


def from_page(url):
    """Herhangi bir makale sayfası: PDF ise doğrudan, değilse citation_* meta etiketleri (DOI varsa OpenAlex)."""
    data, ct, final = _get(url, web=True, limit=MAX_PDF)
    if data[:5] == b"%PDF-" or "application/pdf" in ct:
        p = empty()
        p["url"], p["pdfs"], p["oa"] = final, [final], True
        p["title"] = re.sub(r"\.pdf$", "", urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(final).path)),
                            flags=re.I) or "belge"
        p["_data"] = data
        return p
    page = data[:600000].decode("utf-8", errors="ignore")
    mt = _meta_tags(page)
    doi = next((v[0] for k, v in mt.items() if k in ("citation_doi", "dc.identifier", "prism.doi", "bepress_citation_doi")
                and DOI_RE.search(v[0])), "")
    if not doi:
        m = DOI_RE.search(page[:200000])
        doi = m.group(1) if m and "doi" in page[max(0, m.start() - 40):m.start()].lower() else ""
    p = None
    if doi:
        try:
            p = by_doi(DOI_RE.search(doi).group(1))
        except FetchError:
            p = None
    if p is None:
        p = empty()
        p["title"] = (mt.get("citation_title") or mt.get("og:title") or mt.get("dc.title") or [""])[0]
        if not p["title"]:
            m = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
            p["title"] = html.unescape(re.sub(r"\s+", " ", m.group(1))).strip() if m else final
        p["authors"] = (mt.get("citation_author") or mt.get("dc.creator") or [])[:12]
        dt = (mt.get("citation_publication_date") or mt.get("citation_date") or mt.get("dc.date") or [""])[0]
        y = re.search(r"(1[5-9]|20)\d\d", dt)
        p["year"] = y.group(0) if y else ""
        p["venue"] = (mt.get("citation_journal_title") or [""])[0]
        p["url"] = final
    for u in mt.get("citation_pdf_url") or []:
        u = urllib.parse.urljoin(final, u)
        if u not in p["pdfs"]:
            p["pdfs"].append(u)
    if not p.get("url"):
        p["url"] = final
    return p


def classify(text):
    """'url' | 'doi' | 'query'"""
    s = (text or "").strip()
    if re.match(r"^(https?://|www\.)", s, re.I):
        return "url"
    if re.match(r"^(doi:\s*)?10\.\d{4,9}/\S+$", s, re.I):
        return "doi"
    return "query"


def resolve(text):
    """Bağlantı / DOI → kaynak bilgisi (pdfs: denenecek PDF adresleri)."""
    s = text.strip()
    kind = classify(s)
    if kind == "doi":
        return by_doi(s)
    if s.lower().startswith("www."):
        s = "https://" + s
    m = ARXIV_RE.search(s)
    if m:
        aid = m.group(1)
        try:
            p = by_doi("10.48550/arxiv." + aid)
        except FetchError:
            p = empty()
            p["title"], p["url"] = "arXiv " + aid, "https://arxiv.org/abs/" + aid
        p["pdfs"] = [f"https://arxiv.org/pdf/{aid}"] + [u for u in p["pdfs"] if "arxiv.org" not in u]
        p["oa"] = True
        return p
    m = PII_RE.search(s)
    if m and "sciencedirect" in s.lower():
        doi = doi_from_pii(m.group(1))
        if doi:
            p = by_doi(doi)
            if not p.get("url") or "doi.org" in p["url"]:
                p["url"] = s.split("?")[0] if "/pdf" not in s else p["url"]
            return p
    m = re.search(r"doi\.org/(10\.\d{4,9}/\S+)", s, re.I)
    if m:
        return by_doi(m.group(1))
    m = re.search(r"/doi/(?:abs/|full/|pdf/|epdf/)?(10\.\d{4,9}/[^?#\s]+)", s, re.I)    # Wiley, T&F, ACS, SAGE …
    if m:
        try:
            p = by_doi(m.group(1))
            p["url"] = s
            return p
        except FetchError:
            pass
    return from_page(s)


def search(q, n=15, oa_only=False):
    """OpenAlex araması: en ilgili n kaynak."""
    params = {"search": q.strip(), "per_page": str(n),
              "select": "id,doi,title,display_name,publication_year,authorships,primary_location,"
                        "best_oa_location,locations,open_access,type"}
    if oa_only:
        params["filter"] = "is_oa:true"
    d = _json(OPENALEX + "?" + urllib.parse.urlencode(params))
    return [_from_openalex(w) for w in d.get("results") or [] if (w.get("title") or w.get("display_name"))]


# --------------------------------------------------------------------------- dosyaya
def file_stem(p):
    """'Soyad 2019 - Başlık' (Windows'ta geçerli, kısa)."""
    au = p.get("authors") or []
    sur = au[0].split()[-1] if au and au[0].split() else ""
    title = re.sub(r"\s+", " ", p.get("title") or "kaynak").strip()
    stem = " ".join(x for x in (sur, p.get("year")) if x)
    stem = (stem + " - " if stem else "") + title
    stem = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", stem).replace("  ", " ").strip(" .")
    return stem[:90].rstrip(" .-") or "kaynak"


def _unique(folder, stem, ext):
    path = os.path.join(folder, stem + ext)
    i = 2
    while os.path.exists(path):
        path = os.path.join(folder, f"{stem} ({i}){ext}")
        i += 1
    return path


def _try_pdf(u):
    try:
        d, _ct, _f = _get(u, "application/pdf,*/*;q=0.8", web=True, limit=MAX_PDF)
    except FetchError:
        return None
    return d if d[:1024].lstrip()[:5] == b"%PDF-" else None


def _land_pdfs(u):
    """Açık kopyanın sayfası → PDF adresleri (PMC → Europe PMC, yoksa citation_pdf_url)."""
    m = re.search(r"(PMC\d+)", u)
    if m:
        return [f"https://europepmc.org/articles/{m.group(1)}?pdf=render"]
    if re.search(r"pubmed|doaj\.org|doi\.org/10\.(?!3929|5281|48550)", u):   # künye sayfaları: PDF yok
        return []
    try:
        data, ct, final = _get(u, web=True, limit=MAX_PDF)
    except FetchError:
        return []
    if data[:5] == b"%PDF-":
        return [final]
    mt = _meta_tags(data[:600000].decode("utf-8", errors="ignore"))
    return [urllib.parse.urljoin(final, x) for x in mt.get("citation_pdf_url") or []]


def download(p, folder):
    """PDF'i dene (açık adresler sırayla, sonra açık kopyaların sayfaları), olmazsa .url bağlantısı yaz.
    → (göreli yol, 'pdf' | 'link')."""
    os.makedirs(folder, exist_ok=True)
    data = p.pop("_data", None)
    tried = set()
    for u in (p.get("pdfs") or [])[:5]:         # her biri 20 sn'ye kadar: sınırlı tut
        if data is not None:
            break
        tried.add(u)
        data = _try_pdf(u)
    for land in (p.get("lands") or [])[:3]:
        if data is not None:
            break
        for u in _land_pdfs(land):
            if u not in tried:
                tried.add(u)
                data = _try_pdf(u)
                if data is not None:
                    break
    if data is not None and len(data) <= MAX_PDF:
        path = _unique(folder, file_stem(p), ".pdf")
        with open(path, "wb") as f:
            f.write(data)
        return os.path.relpath(path, folder).replace("\\", "/"), "pdf"
    url = p.get("url") or (p.get("pdfs") or [""])[0]
    if not url:
        raise FetchError("adres yok")
    path = _unique(folder, file_stem(p), ".url")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"[InternetShortcut]\nURL={url}\n")
    return os.path.relpath(path, folder).replace("\\", "/"), "link"


def overrides(p, saved_kind):
    """Rafta görünecek bilgiler (Research.set_override)."""
    o = {"title": p.get("title") or None, "author": "; ".join(p.get("authors") or []) or None,
         "year": p.get("year") or None, "doi": p.get("doi") or None, "url": p.get("url") or None}
    if saved_kind == "link":
        o["type"] = p.get("kind") or "article"      # bağlantı da makale / kitap olarak dursun
    return o


# --------------------------------------------------------------------------- tarayıcıdan indirileni yakala
class DownloadWatch(QObject):
    """PDF'i açık olmayan kaynak tarayıcıda açılınca (kullanıcı kendi girişiyle indirir) İndirilenler'e yeni düşen
    PDF araştırma klasörüne kopyalanır, kaynağın .url yer tutucusunun yerini alır. 15 dakika bekler."""
    arrived = pyqtSignal(str, str, dict)      # araştırma klasörü, yeni göreli yol, kaynak
    WAIT_MS = 15 * 60 * 1000

    def __init__(self, parent=None):
        super().__init__(parent)
        from PyQt6.QtCore import QTimer, QStandardPaths
        self.dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        self.pending = []          # [(klasör, kaynak, .url göreli yolu, başlangıç ms)]
        self.seen = {}
        self.sizes = {}
        self.timer = QTimer(self, interval=1500, timeout=self._poll)
        from PyQt6.QtCore import QElapsedTimer
        self.clock = QElapsedTimer()
        self.clock.start()

    def _pdfs(self):
        out = {}
        try:
            for n in os.listdir(self.dir):
                if n.lower().endswith(".pdf"):
                    p = os.path.join(self.dir, n)
                    try:
                        st = os.stat(p)
                    except OSError:
                        continue
                    out[p] = (st.st_mtime, st.st_size)
        except OSError:
            pass
        return out

    def watch(self, folder, p, url_rel):
        if not self.dir:
            return
        if not self.timer.isActive():
            self.seen = self._pdfs()
            self.sizes = {}
        self.pending = [x for x in self.pending if x[2] != url_rel or x[0] != folder]
        self.pending.append((folder, dict(p), url_rel, self.clock.elapsed()))
        self.timer.start()

    def _poll(self):
        now = self.clock.elapsed()
        self.pending = [x for x in self.pending if now - x[3] < self.WAIT_MS]
        if not self.pending:
            self.timer.stop()
            return
        cur = self._pdfs()
        for path, (mt, size) in cur.items():
            if self.seen.get(path) == (mt, size):
                continue
            if self.sizes.get(path) != size or size == 0:      # hâlâ yazılıyor: bir tur daha bekle
                self.sizes[path] = size
                continue
            try:
                with open(path, "rb") as f:
                    ok = f.read(1024).lstrip()[:5] == b"%PDF-"
            except OSError:
                continue
            self.seen[path] = (mt, size)
            if not ok:
                continue
            folder, p, url_rel, _t = self.pending.pop()          # en son açılan kaynağa
            import shutil
            dst = _unique(folder, file_stem(p), ".pdf")
            try:
                shutil.copy2(path, dst)
            except OSError:
                continue
            old = os.path.join(folder, url_rel)
            try:
                if url_rel.lower().endswith(".url") and os.path.isfile(old):
                    os.remove(old)          # kendi yazdığımız yer tutucu
            except OSError:
                pass
            self.arrived.emit(folder, os.path.relpath(dst, folder).replace("\\", "/"), p)
            if not self.pending:
                self.timer.stop()
                return


# --------------------------------------------------------------------------- arka plan
class Finder(QObject):
    """İşler arka planda; sonuçlar sinyalle (iş kimliğiyle: eski aramanın sonucu yenisini ezmesin)."""
    results = pyqtSignal(int, list)           # iş, [kaynak]
    saved = pyqtSignal(int, dict, str, str)   # iş, kaynak, göreli yol, 'pdf' | 'link'
    failed = pyqtSignal(int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._n = 0

    def _run(self, fn):
        self._n += 1
        job = self._n

        def go():
            try:
                fn(job)
            except FetchError as e:
                self.failed.emit(job, str(e))
            except Exception as e:      # ağ / ayrıştırma: uygulamayı düşürme
                self.failed.emit(job, type(e).__name__ + ": " + str(e)[:160])
        threading.Thread(target=go, daemon=True).start()
        return job

    def search(self, q, oa_only=False):
        return self._run(lambda job: self.results.emit(job, search(q, oa_only=oa_only)))

    def fetch(self, text, folder):
        """Bağlantı / DOI: bul ve hemen klasöre kaydet."""
        def go(job):
            p = resolve(text)
            rel, kind = download(p, folder)
            self.saved.emit(job, p, rel, kind)
        return self._run(go)

    def save(self, p, folder):
        """Arama sonucunu kaydet."""
        def go(job):
            q = dict(p)
            rel, kind = download(q, folder)
            self.saved.emit(job, q, rel, kind)
        return self._run(go)
