"""Araştırmayı dışa aktarma: Markdown, PDF (açık kâğıt) ve yigitozsoy.net biçiminde tek dosya HTML
(solda kaynak rafı, ortada yazı, sağda el yazısı kenar notları; kelimeye bağlı notlarda halka + ok).

Araştırma sayfasının gövdesi (QTextDocument) önce düz bir yapıya çevrilir (`body_items`):
  ("h", düzey, parçalar) | ("p", parçalar) | ("q", alıntı metni, künye) | ("img", göreli yol, genişlik, yükseklik)
  parça = (metin, {"b", "i", "u", "note": kimlik, "src": href})"""
import html
import os
import re
from datetime import datetime
from urllib.parse import unquote

from PyQt6.QtGui import QTextDocument, QPdfWriter, QPageSize, QPageLayout, QTextTable
from PyQt6.QtCore import QMarginsF, QUrl

from .research import Research
from . import shelf as SH


# --------------------------------------------------------------------------- gövde → yapı
def _inlines(block):
    out = []
    it = block.begin()
    while not it.atEnd():
        fr = it.fragment()
        if fr.isValid():
            cf = fr.charFormat()
            h = cf.anchorHref()
            f = {"b": cf.fontWeight() >= 600, "i": cf.fontItalic(), "u": cf.fontUnderline() and not h}
            if h.startswith("delta-note:"):
                f["note"] = h[len("delta-note:"):]
            elif h.startswith("delta-src:"):
                f["src"] = h
            txt = fr.text().replace(" ", "\n").replace("￼", "")
            if txt:
                if out and out[-1][1] == f:
                    out[-1] = (out[-1][0] + txt, f)
                else:
                    out.append((txt, f))
        it += 1
    return out


def body_items(doc: QTextDocument):
    items = []

    def walk(frame):
        it = frame.begin()
        while not it.atEnd():
            child = it.currentFrame()
            blk = it.currentBlock()
            if child is not None:
                if isinstance(child, QTextTable):
                    cell = child.cellAt(0, 0)
                    texts = []
                    cite = ""
                    b = cell.firstCursorPosition().block()
                    last = cell.lastCursorPosition().block().blockNumber()
                    while b.isValid() and b.blockNumber() <= last:
                        parts = _inlines(b)
                        if parts and any("src" in f for _t, f in parts):
                            cite = "".join(t for t, _f in parts).strip().lstrip("—").strip()
                            href = next(f["src"] for _t, f in parts if "src" in f)
                            cite = (cite, href)
                        elif b.text().strip():
                            texts.append(b.text().strip())
                        b = b.next()
                    q = " ".join(texts).strip().strip("“”\"")
                    if q:
                        items.append(("q", q, cite if isinstance(cite, tuple) else (cite, "")))
                else:
                    walk(child)
            elif blk.isValid():
                bi = blk.begin()
                while not bi.atEnd():          # görseller (PDF'ten seçilen alan, yapıştırılan resim)
                    fr = bi.fragment()
                    if fr.isValid() and fr.charFormat().isImageFormat():
                        im = fr.charFormat().toImageFormat()
                        items.append(("img", im.name(), im.width(), im.height()))
                    bi += 1
                lv = blk.blockFormat().headingLevel()
                parts = _inlines(blk)
                if lv and blk.text().strip():
                    items.append(("h", lv, parts))
                elif blk.text().strip():
                    items.append(("p", parts))
            it += 1

    walk(doc.rootFrame())
    return items


def page_doc(research: Research):
    d = QTextDocument()
    d.setBaseUrl(QUrl.fromLocalFile(research.folder.rstrip("\\/") + "/"))   # görseller klasöre göre göreli
    d.setHtml(research.page.get("html", "") or "")
    return d


def img_path(research, name):
    p = unquote(name)
    return p if os.path.isabs(p) else os.path.join(research.folder, p)


def img_data_uri(research, name):
    import base64
    try:
        with open(img_path(research, name), "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode("ascii")
    except OSError:
        return ""


def notes_by_id(research):
    return {n.get("id"): n for n in research.notes}


def bib_line(s):
    bits = []
    if s.author:
        bits.append(s.author + (f" ({s.year})" if s.year else ""))
    elif s.year:
        bits.append(f"({s.year})")
    bits.append(s.title)
    if s.get("pages"):
        bits.append(f"{s.get('pages')} s.")
    if s.get("url"):
        bits.append(s.get("url"))
    return ". ".join(bits)


# --------------------------------------------------------------------------- Markdown
def _md_inline(parts):
    out = ""
    for txt, f in parts:
        t = txt.replace("*", r"\*").replace("_", r"\_")
        if f.get("b"):
            t = f"**{t}**"
        if f.get("i"):
            t = f"*{t}*"
        out += t
    return out


def to_markdown(research: Research, meta=""):
    doc = page_doc(research)
    notes = notes_by_id(research)
    lines = [f"# {research.title}", ""]
    if meta:
        lines += [f"*{meta}*", ""]
    foot = []
    for it in body_items(doc):
        if it[0] in ("h", "p"):
            parts = it[2] if it[0] == "h" else it[1]
            if it[0] == "h":
                txt = "#" * (it[1] + 1) + " " + "".join(t for t, _f in parts).strip()
            else:
                txt = _md_inline(parts)
            for _t, f in parts:
                if f.get("note") in notes:
                    foot.append(f.get("note"))
                    txt += f"[^{len(foot)}]"
            lines += [txt, ""]
        elif it[0] == "q":
            lines += ["> " + it[1], ">", f"> — {it[2][0]}", ""]
        elif it[0] == "img":
            lines += [f"![]({it[1].replace(' ', '%20')})", ""]
    if foot:
        for k, nid in enumerate(foot, 1):
            lines.append(f"[^{k}]: {notes[nid].get('text', '')}")
        lines.append("")
    free = [n for n in research.notes if n.get("id") not in foot]
    if free:
        lines += ["## Notlar", ""] + [f"- {n.get('text', '')}" for n in free] + [""]
    if research.sources:
        lines += ["## Kaynaklar", ""] + [f"- {bib_line(s)}" for s in research.sources] + [""]
    return "\n".join(lines)


def save_markdown(research, path, meta=""):
    with open(path, "w", encoding="utf-8") as f:
        f.write(to_markdown(research, meta))
    return True


# --------------------------------------------------------------------------- PDF (açık kâğıt)
def _html_inline(parts, note_cls=False):
    out = ""
    for txt, f in parts:
        t = html.escape(txt).replace("\n", "<br>")
        if f.get("b"):
            t = f"<b>{t}</b>"
        if f.get("i"):
            t = f"<i>{t}</i>"
        if f.get("u"):
            t = f"<u>{t}</u>"
        if note_cls and f.get("note"):
            t = f'<span class="sn" data-n="{html.escape(f["note"])}">{t}</span>'
        out += t
    return out


def _fam(lst):
    return ", ".join(f"'{x}'" for x in lst)


def save_pdf(research, path, meta=""):
    """Açık kâğıt; renkler ve yazı tipleri araştırma temasının açık paletinden."""
    P = SH.rp_variant(False)
    disp, mono, hand, quote = (_fam(P[k]) for k in ("f_display", "f_mono", "f_hand", "f_quote"))
    doc = page_doc(research)
    notes = research.notes
    parts = [f"<h1 style=\"font-family:{disp}; font-size:30pt; font-weight:600; margin:0;\">"
             f"{html.escape(research.title)}</h1>",
             f"<p style=\"font-family:{mono}; font-size:8pt; color:{P['muted']}; letter-spacing:1px;\">"
             f"{html.escape(meta)}</p><hr>"]
    for it in body_items(doc):
        if it[0] == "h":
            sz = 18 if it[1] == 1 else 14
            parts.append(f"<h{it[1] + 1} style=\"font-family:{disp}; font-size:{sz}pt; margin-top:16pt;\">"
                         f"{_html_inline(it[2])}</h{it[1] + 1}>")
        elif it[0] == "p":
            parts.append(f"<p style='font-size:11pt; line-height:150%;'>{_html_inline(it[1])}</p>")
        elif it[0] == "q":
            parts.append("<table width='100%' cellspacing='0' cellpadding='10' style='margin:8pt 0;'><tr>"
                         f"<td style='border-left:3px solid {P['red']}; background:{P['panel']};'>"
                         f"<p style=\"font-family:{quote}; font-style:italic; font-size:11pt;\">“{html.escape(it[1])}”</p>"
                         f"<p style=\"font-family:{mono}; font-size:8pt; color:{P['ink']};\">"
                         f"— {html.escape(SH.cap(it[2][0], P))}</p></td></tr></table>")
        elif it[0] == "img":
            w = min(it[2] or 480, 640)          # A4 sütununa sığsın
            parts.append(f'<p style="margin:8pt 0 2pt;"><img src="{html.escape(it[1])}" width="{w:.0f}"></p>')
    if notes:
        parts.append(f"<h2 style=\"font-family:{disp}; font-size:14pt; margin-top:18pt;\">Notlar</h2>")
        for n in notes:
            a = (n.get("anchor") or {}).get("text")
            parts.append(f"<p style=\"font-family:{hand}; font-size:{15 if P['tilt'] else 11}pt; color:{P['ink']};\">"
                         f"{'↳ <i>' + html.escape(a) + '</i> — ' if a else ''}{html.escape(n.get('text', ''))}</p>")
    if research.sources:
        parts.append(f"<h2 style=\"font-family:{disp}; font-size:14pt; margin-top:18pt;\">Kaynaklar</h2><ul>")
        parts += [f"<li style='font-size:10pt;'>{html.escape(bib_line(s))}</li>" for s in research.sources]
        parts.append("</ul>")
    td = QTextDocument()
    f = SH.font(P["f_body"], 11)
    f.setPointSizeF(11)
    td.setDefaultFont(f)
    td.setBaseUrl(QUrl.fromLocalFile(research.folder.rstrip("\\/") + "/"))
    td.setHtml("".join(parts))
    w = QPdfWriter(path)
    w.setTitle(research.title)
    w.setCreator("yazıt")
    w.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
    w.setPageMargins(QMarginsF(18, 18, 18, 18), QPageLayout.Unit.Millimeter)
    td.print(w)
    return os.path.isfile(path)


# --------------------------------------------------------------------------- site biçimi HTML
SITE_CSS = r"""
:root { --zirh:#121210; --grafit:#1C1B18; --kirik:#D3D1CA; --soluk:#8A877E; --cizgi:#3A3833; --ink:#EBC55E;
  --kirmizi:#C8282E; --sirt:#F1E8D2; --kagit:#F3EEE2; --murekkep:#2A2620; }
* { box-sizing: border-box; }
html, body { margin: 0; background: var(--zirh); color: var(--kirik); }
body { font: 17px/1.7 'Inter', system-ui, sans-serif; }
.mono { font-family: 'JetBrains Mono', ui-monospace, monospace; letter-spacing: .08em; text-transform: uppercase; }
.wrap { display: grid; grid-template-columns: 280px minmax(0, 760px) 280px; gap: 56px; justify-content: center;
  padding: 64px 32px 120px; }
@media (max-width: 1180px) { .wrap { grid-template-columns: minmax(0, 760px); } .raf, .kenar { display: none; } }
h1 { font: 600 clamp(40px, 6vw, 64px)/1.02 'Oswald', sans-serif; letter-spacing: .01em; margin: 0 0 14px; color: #EDEBE4; }
.meta { font-size: 12px; color: var(--soluk); }
.rule { width: 56px; height: 2px; background: var(--kirmizi); margin: 22px 0 28px; }
h2 { font: 600 30px/1.15 'Oswald', sans-serif; margin: 44px 0 12px; color: #EDEBE4; }
h3 { font: 500 23px/1.2 'Oswald', sans-serif; margin: 30px 0 10px; color: #EDEBE4; }
p { margin: 0 0 16px; }
figure { margin: 22px 0 6px; } figure img { display: block; height: auto; border-radius: 4px; background: #fff; }
.toc { border-left: 1px solid var(--cizgi); padding: 4px 0 4px 16px; margin: 0 0 30px; }
.toc .mono { font-size: 11px; color: var(--soluk); }
.toc a { display: block; color: var(--kirik); text-decoration: none; padding: 3px 0; font-size: 15px; }
.toc a:hover { color: var(--ink); }
.toc a span { font-family: 'JetBrains Mono', monospace; color: var(--soluk); margin-right: 12px; font-size: 13px; }
blockquote { margin: 22px 0; padding: 14px 20px; background: var(--grafit); border-left: 3px solid var(--kirmizi); }
blockquote p { font: italic 18px/1.6 'Lora', Georgia, serif; margin: 0 0 8px; }
blockquote cite { font: 600 11px 'JetBrains Mono', monospace; letter-spacing: .1em; color: var(--ink); font-style: normal; }
.sn { cursor: pointer; border-radius: 3px; transition: background .15s; }
.sn.on { background: rgba(235,197,94,.14); }
.kenar { position: relative; }
.kenar h4, .raf h4 { font: 600 11px 'JetBrains Mono', monospace; letter-spacing: .1em; color: var(--soluk); margin: 0 0 14px; }
aside.sn-not { font: 600 21px/1.12 'Caveat', cursive; color: var(--ink); transform: rotate(-1.2deg);
  transform-origin: left top; margin: 0 0 18px; transition: transform .2s; }
aside.sn-not.on { transform: rotate(-1.2deg) scale(1.04); }
.kenar aside.sn-not[data-n] { position: absolute; left: 0; right: 0; }
.kenar .serbest { margin-top: 0; }
svg.sn-ok { position: absolute; left: 0; top: 0; pointer-events: none; overflow: visible; z-index: 2; }
svg.sn-ok path { fill: none; stroke: var(--ink); stroke-width: 1.25; stroke-linecap: round; stroke-linejoin: round;
  opacity: .3; transition: opacity .2s, stroke-width .2s; }
svg.sn-ok g.on path { opacity: .85; stroke-width: 1.7; }
/* raf */
.raf section { margin: 0 0 34px; }
.kitap { display: block; height: 26px; margin: 0 0 2px; border-radius: 2px; color: var(--sirt); text-decoration: none;
  font: 500 12.5px/26px 'Oswald', sans-serif; letter-spacing: .04em; text-transform: uppercase; padding: 0 12px 0 18px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; position: relative;
  box-shadow: 1.5px 2.5px 0 rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.12), inset 0 -2px 0 rgba(0,0,0,.25);
  transition: transform .35s cubic-bezier(.34,1.56,.64,1); }
.kitap::before, .kitap::after { content: ''; position: absolute; top: 2px; bottom: 2px; width: 1.2px; background: rgba(217,180,90,.65); }
.kitap::before { left: 7px; box-shadow: 3px 0 0 rgba(217,180,90,.65); } .kitap::after { right: 9px; }
.kitap small { font: 500 9px 'JetBrains Mono', monospace; opacity: .6; margin-left: 8px; letter-spacing: .06em; }
.kitap:hover { transform: translateX(18px) !important; }
.tahta { height: 6px; background: linear-gradient(#3A3731, #2B2924); margin: 2px -4px 0; box-shadow: 0 3px 0 rgba(0,0,0,.45); }
.kagitlar { display: flex; flex-wrap: wrap; padding: 6px 0 0 4px; }
.kagit { width: 66px; height: 88px; margin: 0 -16px 14px 0; background: var(--kagit); color: var(--murekkep);
  padding: 6px; font: 600 7.5px/1.15 'Oswald', sans-serif; text-transform: uppercase; text-decoration: none; position: relative;
  clip-path: polygon(0 0, calc(100% - 12px) 0, 100% 12px, 100% 100%, 0 100%); box-shadow: 1.5px 2.5px 0 rgba(0,0,0,.4);
  transition: transform .3s cubic-bezier(.34,1.56,.64,1); overflow: hidden; }
.kagit::after { content: ''; position: absolute; right: 0; top: 0; border-style: solid; border-width: 0 12px 12px 0;
  border-color: transparent #D8D0BE transparent transparent; transform: rotate(180deg); transform-origin: center; }
.kagit i { display: block; font: 400 3.8px/1.4 'JetBrains Mono', monospace; text-transform: none; opacity: .6; margin-top: 4px; font-style: normal; }
.kagit:hover { transform: translateY(-10px) rotate(0deg) scale(1.07) !important; z-index: 3; }
.kaset { display: block; width: 124px; height: 78px; background: linear-gradient(#2a2925, #1B1A17); border-radius: 5px;
  position: relative; margin: 0 0 12px; text-decoration: none; box-shadow: 1.5px 3px 0 rgba(0,0,0,.45); }
.kaset .etiket { position: absolute; left: 8px; right: 8px; top: 7px; height: 30px; background: var(--kagit);
  border-top: 4px solid var(--kagit); }
.kaset .etiket::before { content: ''; display: block; height: 5px; background: var(--kirmizi); }
.kaset .etiket b { display: block; font: 600 9px/19px 'Oswald', sans-serif; color: var(--murekkep); padding: 0 5px;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; text-transform: uppercase; }
.kaset .pencere { position: absolute; left: 32px; top: 42px; width: 60px; height: 22px; background: #0B0B0A; border-radius: 8px; }
.kaset .pencere::before, .kaset .pencere::after { content: ''; position: absolute; top: 3px; width: 16px; height: 16px;
  border-radius: 50%; background: radial-gradient(#0B0B0A 30%, #E9E3D3 32%); }
.kaset .pencere::before { left: 3px; } .kaset .pencere::after { right: 3px; }
.kaset:hover .pencere::before, .kaset:hover .pencere::after { animation: don 1s linear infinite; }
@keyframes don { to { transform: rotate(360deg); } }
.polaroid { display: inline-block; width: 72px; background: #F6F3EA; padding: 5px 5px 14px; margin: 0 8px 10px 0;
  color: var(--murekkep); font: 600 11px 'Caveat', cursive; text-align: center; text-decoration: none; box-shadow: 1.5px 3px 0 rgba(0,0,0,.4); }
.polaroid span { display: block; height: 62px; background: #2A2824; margin-bottom: 2px; }
.fis { display: block; background: var(--kagit); color: var(--murekkep); padding: 4px 8px 8px; margin: 0 0 10px;
  border-top: 14px solid var(--kagit); box-shadow: 1.5px 2.5px 0 rgba(0,0,0,.4); text-decoration: none;
  font: 700 11px 'JetBrains Mono', monospace; position: relative; }
.fis::before { content: ''; position: absolute; left: 0; right: 0; top: 0; height: 1.2px; background: var(--kirmizi); }
.fis small { display: block; font-weight: 400; opacity: .65; }
.kaynakca { margin-top: 64px; border-top: 1px solid var(--cizgi); padding-top: 18px; font-size: 14px; color: var(--soluk); }
.kaynakca ol { padding-left: 20px; } .kaynakca li { margin: 0 0 6px; }
footer { text-align: center; color: var(--soluk); font-size: 11px; padding: 0 0 40px; }
"""

SITE_JS = r"""
(function(){
  var col = document.querySelector('.kenar'); if (!col) return;
  var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('class', 'sn-ok');
  document.body.appendChild(svg);
  function rnd(s){ return function(){ s = (s * 9301 + 49297) % 233280; return s / 233280; }; }
  function ring(r, seed){
    var R = rnd(seed), cx = r.left + r.width/2, cy = r.top + r.height/2, rx = r.width/2 + 7, ry = r.height/2 + 4;
    var tilt = (R()*8-4) * Math.PI/180, a0 = (150 + R()*60) * Math.PI/180, d = '';
    for (var k = 0; k <= 46; k++) { var a = a0 + k/40*2*Math.PI, j = 1 + .06*Math.sin(k*.9 + seed%7) + k/40*.08;
      var x = rx*j*Math.cos(a), y = ry*j*Math.sin(a);
      d += (k ? 'L' : 'M') + (cx + x*Math.cos(tilt) - y*Math.sin(tilt)).toFixed(1) + ' ' + (cy + x*Math.sin(tilt) + y*Math.cos(tilt)).toFixed(1); }
    return d;
  }
  function layout(){
    if (getComputedStyle(col).display === 'none') { svg.innerHTML = ''; return; }
    var top = col.getBoundingClientRect().top + scrollY, last = 0, items = [];
    document.querySelectorAll('aside.sn-not[data-n]').forEach(function(n){
      var w = document.querySelector('.sn[data-n="' + n.dataset.n + '"]'); if (!w) return;
      var y = Math.max(last, w.getBoundingClientRect().top + scrollY - top - 6);
      n.style.top = y + 'px'; last = y + n.offsetHeight + 16; items.push([w, n]); });
    var free = col.querySelector('.serbest'); if (free) free.style.marginTop = (last + 20) + 'px';
    svg.setAttribute('width', document.documentElement.scrollWidth); svg.setAttribute('height', document.documentElement.scrollHeight);
    svg.innerHTML = '';
    items.forEach(function(p){
      var w = p[0].getBoundingClientRect(), n = p[1].getBoundingClientRect(), id = p[1].dataset.n, seed = 0;
      for (var i = 0; i < id.length; i++) seed += id.charCodeAt(i);
      var r = {left: w.left + scrollX, top: w.top + scrollY, width: w.width, height: w.height};
      var g = document.createElementNS(svg.namespaceURI, 'g'); g.dataset.n = id;
      var s = [r.left + r.width + 9, r.top + r.height/2], e = [n.left + scrollX - 6, n.top + scrollY + 14];
      var dx = e[0] - s[0];
      var d = 'M' + s + 'C' + [s[0] + dx*.35, s[1] - 28] + ' ' + [e[0] - dx*.3, e[1] + 18] + ' ' + e;
      var ang = Math.atan2(-18, dx*.3), h = '';
      [-1, 1].forEach(function(k){ var a = ang + Math.PI + k*.45; h += 'M' + e + 'L' + [e[0] + 8*Math.cos(a), e[1] + 8*Math.sin(a)]; });
      g.innerHTML = '<path d="' + ring(r, seed) + '"/><path d="' + d + '"/><path d="' + h + '"/>';
      svg.appendChild(g);
    });
  }
  function hot(id, on){
    document.querySelectorAll('[data-n="' + id + '"]').forEach(function(x){ x.classList.toggle('on', on); });
  }
  document.querySelectorAll('[data-n]').forEach(function(x){
    x.addEventListener('mouseenter', function(){ hot(x.dataset.n, true); });
    x.addEventListener('mouseleave', function(){ hot(x.dataset.n, false); });
  });
  addEventListener('resize', layout); addEventListener('load', layout); document.fonts && document.fonts.ready.then(layout);
  layout();
})();
"""


def _ang(seed, k=3.0):
    return ((seed >> 9) % 7 - 3) * k * 0.12


def _shelf_html(research, P=None):
    P = P or SH.rp()
    k = P["kick"]
    by = research.by_type()
    out = [f'<h4>{k}KAYNAKLAR · %d</h4>' % len(research.sources)]

    def href(s):
        return html.escape(s.rel)
    if by["book"]:
        out.append(f'<section><h4>{k}KİTAPLAR · %d</h4>' % len(by["book"]))
        for s in by["book"]:
            w = min(100, 64 + min(30, (s.get("pages") or 150) / 12) + s.seed % 7)
            dx = (s.seed >> 5) % 18
            out.append(f'<a class="kitap" href="{href(s)}" title="{html.escape(s.title)}" style="background:{SH.spine(s, P)};'
                       f'width:{w:.0f}%;margin-left:{dx}px;transform:rotate({_ang(s.seed):.2f}deg)">'
                       f'{html.escape(s.title)}<small>{html.escape(SH.cap(s.short_author(), P))}</small></a>')
        out.append('<div class="tahta"></div></section>')
    if by["article"]:
        out.append(f'<section><h4>{k}MAKALELER · %d</h4><div class="kagitlar">' % len(by["article"]))
        for k, s in enumerate(by["article"]):
            ang = [-3, 4, -6, 2, -1, 5][k % 6]
            ex = html.escape((s.get("excerpt") or "")[:160])
            out.append(f'<a class="kagit" href="{href(s)}" title="{html.escape(s.title)}" '
                       f'style="transform:rotate({ang}deg)">{html.escape(s.title[:48])}<i>{ex}</i></a>')
        out.append('</div></section>')
    if by["video"]:
        out.append(f'<section><h4>{k}VİDEOLAR · %d</h4>' % len(by["video"]))
        for s in by["video"]:
            out.append(f'<a class="kaset" href="{href(s)}" title="{html.escape(s.title)}"><span class="etiket">'
                       f'<b>{html.escape(s.title)}</b></span><span class="pencere"></span></a>')
        out.append('</section>')
    if by["image"]:
        out.append(f'<section><h4>{k}GÖRSELLER · %d</h4>' % len(by["image"]))
        for s in by["image"]:
            out.append(f'<a class="polaroid" href="{href(s)}" style="transform:rotate({_ang(s.seed, 6):.1f}deg)">'
                       f'<span style="background:url(\'{href(s)}\') center/cover"></span>{html.escape(s.title[:18])}</a>')
        out.append('</section>')
    if by["link"]:
        out.append(f'<section><h4>{k}BAĞLANTILAR · %d</h4>' % len(by["link"]))
        for s in by["link"]:
            url = s.get("url") or s.rel
            dom = re.sub(r"^https?://(www\.)?", "", url).split("/")[0]
            out.append(f'<a class="fis" href="{html.escape(url)}">{html.escape(s.title)}'
                       f'<small>↗ {html.escape(dom)}</small></a>')
        out.append('</section>')
    return "\n".join(out)


# temanın değişkenleri SITE_CSS'teki sabitlerin yerine (kamuflaj'da değerler bugünküyle aynı)
_CSS_SUBS = [
    ("'Oswald', sans-serif", "var(--f-display)"), ("'Inter', system-ui, sans-serif", "var(--f-body)"),
    ("'JetBrains Mono', ui-monospace, monospace", "var(--f-mono)"), ("'JetBrains Mono', monospace", "var(--f-mono)"),
    ("'Caveat', cursive", "var(--f-hand)"), ("'Lora', Georgia, serif", "var(--f-quote)"),
    ("#EDEBE4", "var(--baslik)"), ("linear-gradient(#3A3731, #2B2924)", "linear-gradient(var(--tahta-hi), var(--tahta))"),
    ("#D8D0BE", "var(--kivrik)"), ("linear-gradient(#2a2925, #1B1A17)", "var(--kaset)"), ("#F6F3EA", "var(--polaroid)"),
    ("#2A2824", "var(--foto)"), ("rgba(235,197,94,.14)", "var(--parlak)"), ("rgba(217,180,90,.65)", "var(--bant)"),
    ("radial-gradient(#0B0B0A 30%, #E9E3D3 32%)", "radial-gradient(#0B0B0A 30%, var(--makara) 32%)"),
    ("text-transform: uppercase", "text-transform: var(--tt)"),
]
FONT_LINKS = {
    "kamuflaj": "family=Oswald:wght@500;600&family=Inter:wght@400;600&family=JetBrains+Mono:wght@400;600&"
                "family=Caveat:wght@500;600;700&family=Lora:ital@1",
    "soft": "family=Poppins:wght@400;600;700&family=Manrope:wght@400;600;700&family=Patrick+Hand&family=Lora:ital@1",
    "yazit": "family=Inter:wght@400;600",
}


def _rgba(c, a):
    from PyQt6.QtGui import QColor
    q = QColor(c)
    return f"rgba({q.red()},{q.green()},{q.blue()},{a})"


def site_css(P):
    """SITE_CSS + temanın :root değişkenleri."""
    css = re.sub(r":root \{[^}]*\}", "", SITE_CSS, count=1)      # renkler aşağıdaki :root'tan
    for a, b in _CSS_SUBS:
        css = css.replace(a, b)
    css = re.sub(r"(\.kitap \{[^}]*?)border-radius: 2px", r"\1border-radius: var(--r-kitap)", css)
    css = css.replace(".mono { font-family: var(--f-mono); letter-spacing: .08em; text-transform: var(--tt);",
                      ".mono { font-family: var(--f-mono); letter-spacing: .08em; text-transform: uppercase;")
    fam = {k: _fam(P[k]) for k in ("f_display", "f_body", "f_mono", "f_hand", "f_quote")}
    generic = {"f_display": "sans-serif", "f_body": "system-ui, sans-serif", "f_mono": "ui-monospace, monospace",
               "f_hand": "cursive", "f_quote": "Georgia, serif"}
    band = P["bands"]
    kamuf = P["kick"] == "// "
    root = {
        "zirh": P["bg"], "grafit": P["panel"], "kirik": P["text"], "soluk": P["muted"], "cizgi": P["faint"],
        "ink": P["ink"], "kirmizi": P["red"], "sirt": P["spine_text"], "kagit": P["paper"], "murekkep": P["paper_ink"],
        "baslik": "#EDEBE4" if kamuf else P["text"], "tahta": P["plank"], "tahta-hi": P["plank_hi"], "kivrik": P["fold"],
        "kaset": ("linear-gradient(#2a2925, #1B1A17)" if kamuf else
                  f"linear-gradient({SH.qc(P['cassette']).lighter(135).name()}, {P['cassette']})"),
        "polaroid": P["polaroid"], "foto": P["photo"], "parlak": _rgba(P["ink"], .14), "makara": P["reel"],
        "bant": f"rgba({band.red()},{band.green()},{band.blue()},.65)" if band is not None else "transparent",
        "tt": "uppercase" if P["upper"] else "none", "r-kitap": f"{P['r_book']}px",
    }
    root.update({"f-" + k[2:]: f"{fam[k]}, {generic[k]}" for k in fam})
    return ":root { " + " ".join(f"--{k}:{v};" for k, v in root.items()) + " }\n" + css


def to_site_html(research, meta=""):
    """kamuflaj: sitenin koyu görünümü (bugünkü gibi); yazıt / soft: uygulamanın açık / koyu temasına göre."""
    P = SH.DARK if SH.rtheme() == "kamuflaj" else SH.rp()
    k = P["kick"]
    doc = page_doc(research)
    items = body_items(doc)
    notes = research.notes
    anchored = set()
    body = []
    toc = []
    n1 = 0
    for it in items:
        if it[0] == "h":
            txt = "".join(t for t, _f in it[2]).strip()
            hid = "b-" + re.sub(r"\W+", "-", txt.lower()).strip("-")[:40]
            if it[1] == 1:
                n1 += 1
                toc.append(f'<a href="#{hid}"><span>{n1:02d}</span>{html.escape(txt)}</a>')
            body.append(f'<h{it[1] + 1} id="{hid}">{_html_inline(it[2], True)}</h{it[1] + 1}>')
            anchored.update(f["note"] for _t, f in it[2] if f.get("note"))
        elif it[0] == "p":
            body.append(f"<p>{_html_inline(it[1], True)}</p>")
            anchored.update(f["note"] for _t, f in it[1] if f.get("note"))
        elif it[0] == "q":
            cite, href = it[2]
            rel = unquote(href[len("delta-src:"):].split("#")[0]) if href else ""
            link = f'<a href="{html.escape(rel)}" style="color:inherit;text-decoration:none">' if rel else ""
            body.append(f'<blockquote><p>“{html.escape(it[1])}”</p><cite>{link}— {html.escape(SH.cap(cite, P))}'
                        f'{"</a>" if link else ""}</cite></blockquote>')
        elif it[0] == "img":
            uri = img_data_uri(research, it[1])      # tek dosya HTML: görsel içine gömülür
            if uri:
                body.append(f'<figure><img src="{uri}" alt="" style="max-width:100%;width:{it[2]:.0f}px"></figure>')
    side = [f'<h4>{k}NOTLAR · %d</h4>' % len(notes)]
    for n in notes:
        if n.get("id") in anchored:
            side.append(f'<aside class="sn-not" data-n="{html.escape(n["id"])}">{html.escape(n.get("text", ""))}</aside>')
    free = [n for n in notes if n.get("id") not in anchored]
    if free:
        side.append('<div class="serbest">' + "".join(f'<aside class="sn-not">{html.escape(n.get("text", ""))}</aside>'
                                                      for n in free) + "</div>")
    toc_html = (f'<nav class="toc"><div class="mono">{k}İçindekiler</div>{"".join(toc)}</nav>' if toc else "")
    bib = "".join(f"<li>{html.escape(bib_line(s))}</li>" for s in research.sources)
    fonts_link = "https://fonts.googleapis.com/css2?" + FONT_LINKS[SH.rtheme()] + "&display=swap"
    return f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(research.title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="{fonts_link}" rel="stylesheet">
<style>{site_css(P)}</style></head>
<body><div class="wrap">
<div class="raf">{_shelf_html(research, P)}</div>
<article>
<h1>{html.escape(research.title)}</h1>
<div class="meta mono">{html.escape(meta)}</div>
<div class="rule"></div>
{toc_html}
{chr(10).join(body)}
{f'<section class="kaynakca"><div class="mono">{k}Kaynakça</div><ol>{bib}</ol></section>' if bib else ''}
</article>
<div class="kenar">{"".join(side)}</div>
</div>
<footer class="mono">yazıt · {datetime.now().strftime("%d.%m.%Y")}</footer>
<script>{SITE_JS}</script>
</body></html>"""


def save_site_html(research, path, meta=""):
    with open(path, "w", encoding="utf-8") as f:
        f.write(to_site_html(research, meta))
    return True
