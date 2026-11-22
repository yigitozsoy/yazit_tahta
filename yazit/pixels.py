"""Görsel pikselleri: benzer renk bölgesi (sihirli değnek), otomatik arka plan, seçimi silme / boyama.

numpy yok: her kanal bytes.translate ile (C hızında) eşiklenir, maskeler bayt başına 0/1 bytes'tır; bitişiklik
satır parçaları (run) üzerinde birleşim-bul ile bulunur. 1920×1080'lik bir görselde ~0,1–0,4 sn."""
import re
from collections import Counter

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPainter, QPolygonF, QColor, QPainterPath, QBrush

FMT = QImage.Format.Format_ARGB32     # bellekte B, G, R, A (küçük sonlu)
_RUN = re.compile(rb"\x01+")


def argb(img: QImage) -> QImage:
    return img if img.format() == FMT else img.convertToFormat(FMT)


def raw(img: QImage) -> bytes:
    img = argb(img)
    p = img.constBits()
    p.setsize(img.sizeInBytes())
    return bytes(p)


def from_raw(data, w, h) -> QImage:
    return QImage(bytes(data), w, h, w * 4, FMT).copy()


def _near_table(v, tol):
    return bytes(1 if abs(i - v) <= tol else 0 for i in range(256))


def _and(*bs):
    n = len(bs[0])
    x = int.from_bytes(bs[0], "little")
    for b in bs[1:]:
        x &= int.from_bytes(b, "little")
    return x.to_bytes(n, "little")


def _or(a, b):
    n = len(a)
    return (int.from_bytes(a, "little") | int.from_bytes(b, "little")).to_bytes(n, "little")


def similar(data, color, tol):
    """color (r, g, b) ile kanal başına en çok tol farklı pikseller → bayt başına 0/1. Saydamlar da benzer sayılır."""
    r, g, b = color
    m = _and(data[0::4].translate(_near_table(b, tol)), data[1::4].translate(_near_table(g, tol)),
             data[2::4].translate(_near_table(r, tol)))
    clear = data[3::4].translate(bytes(1 if i < 16 else 0 for i in range(256)))
    return _or(m, clear)


def components(mask, w, h, seeds):
    """mask içindeki, seeds [(x, y)] noktalarından birine 4-bitişik bağlı bölge → 0/1 bytes."""
    runs = []            # (y, x0, x1)
    row_runs = []
    for y in range(h):
        row = mask[y * w:(y + 1) * w]
        cur = [(len(runs) + k, mt.start(), mt.end()) for k, mt in enumerate(_RUN.finditer(row))]
        runs.extend((y, a, b) for _i, a, b in cur)
        row_runs.append(cur)
    parent = list(range(len(runs)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for y in range(1, h):
        up, cur = row_runs[y - 1], row_runs[y]
        i = j = 0
        while i < len(up) and j < len(cur):
            ia, a0, a1 = up[i]
            jb, b0, b1 = cur[j]
            if a0 < b1 and b0 < a1:        # üst üste biniyor
                ra, rb = find(ia), find(jb)
                if ra != rb:
                    parent[rb] = ra
            if a1 < b1:
                i += 1
            else:
                j += 1
    roots = set()
    for x, y in seeds:
        if 0 <= y < h and 0 <= x < w:
            for i, a, b in row_runs[y]:
                if a <= x < b:
                    roots.add(find(i))
                    break
    out = bytearray(w * h)
    if not roots:
        return bytes(out)
    for i, (y, a, b) in enumerate(runs):
        if find(i) in roots:
            out[y * w + a:y * w + b] = b"\x01" * (b - a)
    return bytes(out)


def pixel(data, w, x, y):
    i = (y * w + x) * 4
    return data[i + 2], data[i + 1], data[i]


def wand(img, x, y, tol=32):
    """Sihirli değnek: tıklanan noktanın rengine benzeyen, ona bağlı bölge."""
    img = argb(img)
    w, h = img.width(), img.height()
    if not (0 <= x < w and 0 <= y < h):
        return bytes(w * h)
    data = raw(img)
    if data[(y * w + x) * 4 + 3] < 16:     # saydam yere tıklandı: saydam bölge
        m = data[3::4].translate(bytes(1 if i < 16 else 0 for i in range(256)))
    else:
        m = similar(data, pixel(data, w, x, y), tol)
    return components(m, w, h, [(x, y)])


def border_colors(data, w, h, k=4):
    """Kenar piksellerinin baskın renkleri (kaba nicemlemeyle)."""
    cnt = Counter()
    pts = [(x, 0) for x in range(0, w, 2)] + [(x, h - 1) for x in range(0, w, 2)] + \
          [(0, y) for y in range(0, h, 2)] + [(w - 1, y) for y in range(0, h, 2)]
    samples = {}
    for x, y in pts:
        i = (y * w + x) * 4
        if data[i + 3] < 16:
            continue
        c = (data[i + 2], data[i + 1], data[i])
        q = (c[0] >> 4, c[1] >> 4, c[2] >> 4)
        cnt[q] += 1
        samples.setdefault(q, c)
    total = sum(cnt.values()) or 1
    out = []
    for q, n in cnt.most_common(k):
        if n / total >= 0.04:
            out.append(samples[q])
    return out, [p for p in pts]


def background(img, tol=40):
    """Otomatik arka plan: kenarlardaki baskın renklere benzeyen ve kenara bağlı bölge."""
    img = argb(img)
    w, h = img.width(), img.height()
    data = raw(img)
    cols, pts = border_colors(data, w, h)
    m = data[3::4].translate(bytes(1 if i < 16 else 0 for i in range(256)))
    for c in cols:
        m = _or(m, similar(data, c, tol))
    return components(m, w, h, pts)


def grow(mask, w, h):
    """Maskeyi 1 piksel büyütür (4-komşu)."""
    n = len(mask)
    x = int.from_bytes(mask, "little")
    bits = 8
    # satır sonundan sonrakine taşmasın diye sol / sağ kaydırmada kenar sütunları kesilir
    last_col = int.from_bytes((b"\x00" * (w - 1) + b"\x01") * h, "little")
    first_col = int.from_bytes((b"\x01" + b"\x00" * (w - 1)) * h, "little")
    full = (1 << (n * bits)) - 1
    y = x | ((x & ~last_col & full) << bits) | ((x & ~first_col & full) >> bits) | (x << (bits * w)) | (x >> (bits * w))
    return (y & int.from_bytes(b"\x01" * n, "little")).to_bytes(n, "little")


def clear(img, mask, feather=True):
    """mask'taki pikselleri saydam yapar; feather: kenardaki bir sıra yarı saydam (yumuşak kenar)."""
    img = argb(img)
    w, h = img.width(), img.height()
    data = bytearray(raw(img))
    n = w * h
    keep = mask.translate(bytes([0xFF, 0x00]) + bytes(254))
    alpha = bytes(data[3::4])
    a = int.from_bytes(alpha, "little") & int.from_bytes(keep, "little")
    if feather:
        edge = _and(grow(mask, w, h), mask.translate(bytes([1, 0]) + bytes(254)))
        em = int.from_bytes(edge.translate(bytes([0, 0xFF]) + bytes(254)), "little")
        half = int.from_bytes(alpha.translate(bytes(i * 3 // 5 for i in range(256))), "little")
        a = (a & ~em) | (half & em)
    data[3::4] = a.to_bytes(n, "little")
    return from_raw(data, w, h)


def paint_mask(img, mask, color):
    """mask'taki pikselleri renkle boyar (kova)."""
    img = argb(img)
    w, h = img.width(), img.height()
    c = QColor(color)
    data = bytearray(raw(img))
    sel = mask.translate(bytes([0, 0xFF]) + bytes(254))
    s = int.from_bytes(sel, "little")
    for off, v in ((0, c.blue()), (1, c.green()), (2, c.red()), (3, 255)):
        ch = int.from_bytes(bytes(data[off::4]), "little")
        fillv = int.from_bytes(bytes([v]) * (w * h), "little")
        data[off::4] = ((ch & ~s) | (fillv & s)).to_bytes(w * h, "little")
    return from_raw(data, w, h)


def polygon_mask(poly: QPolygonF, w, h):
    """Kement: çokgenin içi → 0/1 bytes."""
    im = QImage(w, h, QImage.Format.Format_Grayscale8)
    im.fill(0)
    p = QPainter(im)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(QColor(255, 255, 255)))
    path = QPainterPath()
    path.addPolygon(poly)
    path.closeSubpath()
    p.drawPath(path)
    p.end()
    return gray_to_mask(im)


def gray_to_mask(im: QImage):
    w, h, bpl = im.width(), im.height(), im.bytesPerLine()
    p = im.constBits()
    p.setsize(im.sizeInBytes())
    b = bytes(p)
    rows = b if bpl == w else b"".join(b[y * bpl:y * bpl + w] for y in range(h))
    return rows.translate(bytes([0]) + b"\x01" * 255)


def combine(a, b, how):
    """Seçim birleştirme: new | add | sub."""
    if how == "add" and a is not None:
        return _or(a, b)
    if how == "sub" and a is not None:
        n = len(a)
        return (int.from_bytes(a, "little") & ~int.from_bytes(b, "little")).to_bytes(n, "little")
    return b


def invert(mask):
    return mask.translate(bytes([1, 0]) + bytes(254))


def count(mask):
    return mask.count(1)


def overlay(mask, w, h, color=QColor(62, 166, 255, 110)):
    """Seçim maskesini gösterilecek yarı saydam görüntüye çevirir (Indexed8)."""
    bpl = (w + 3) & ~3
    rows = mask if bpl == w else b"".join(mask[y * w:(y + 1) * w] + bytes(bpl - w) for y in range(h))
    im = QImage(rows, w, h, bpl, QImage.Format.Format_Indexed8).copy()
    im.setColorTable([0, color.rgba()])
    return im
