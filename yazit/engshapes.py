"""Mühendislik şekilleri (Seçenekler › Mühendislik şekilleri açıkken şekil menüsünde).
Hepsi iki noktalı StrokeItem türü: yol burada iki noktadan (a, b) üretilir, kayıtta "k" adıyla saklanır.
- Kutu şekilleri (BOX) a–b dikdörtgenine sığar; Shift kare yapar.
- Çizgi şekilleri (LINE) a'dan b'ye uzanır (yay, sönümleyici, ölçü, yayılı yük, zemin); Shift açıyı 45°'ye oturtur.
Saf geometri: yalnızca QPainterPath üretir, çizim kalemi / renk / çizgi türü StrokeItem'dan gelir."""
import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QPainterPath, QPainter, QPen, QColor

# menüde gruplar halinde (ayraçla)
GROUPS = (
    ("eng_g_graph", ("gauss", "axes", "sine", "grid", "iso_grid")),
    ("eng_g_machine", ("gear", "pulley", "wheel", "bearing", "hexnut", "spring", "damper", "fourbar")),
    ("eng_g_iso", ("iso_box", "iso_cyl", "iso_axes")),
    ("eng_g_statics", ("beam_ss", "beam_cant", "pin", "roller", "ground", "load", "moment", "dim", "incline")),
    ("eng_g_thermo", ("cyc_carnot", "cyc_otto", "cyc_diesel", "cyc_brayton", "cyc_rankine", "piston",
                      "compressor", "turbine", "pump", "hx", "valve", "turbojet", "turbofan")),
    ("eng_g_fluid", ("boundary", "pipe_flow", "cyl_flow", "venturi", "tank_open", "manometer")),
    ("eng_g_vehicle", ("airfoil", "car", "f1", "plane", "tank", "ship")),
)
KINDS = tuple(k for _, ks in GROUPS for k in ks)
LINE = ("spring", "damper", "dim", "load", "ground")
BOX = tuple(k for k in KINDS if k not in LINE)
FILLABLE = ("gear", "airfoil", "plane")   # kapalı şekiller (dişlinin deliği OddEven ile boş kalır)

COS30, SIN30 = math.cos(math.pi / 6), 0.5
GRID = 24.0                           # ızgara aralığı (sahne birimi)


def _head(path, tip, ang, h):
    """Ok ucu: tip noktasında, ang yönünde gelen çizginin ucu."""
    for s in (-0.45, 0.45):
        a = ang + math.pi + s
        path.moveTo(QPointF(tip.x() + h * math.cos(a), tip.y() + h * math.sin(a)))
        path.lineTo(tip)


def _arrow(path, p0, p1, h):
    path.moveTo(p0)
    path.lineTo(p1)
    _head(path, p1, math.atan2(p1.y() - p0.y(), p1.x() - p0.x()), h)


def _poly(path, pts, close=False):
    if not pts:
        return
    path.moveTo(pts[0])
    for p in pts[1:]:
        path.lineTo(p)
    if close:
        path.closeSubpath()


def _clip(p0, p1, r):
    """Liang–Barsky: p0→p1 doğru parçasının r içindeki kısmı (yoksa None)."""
    x0, y0, dx, dy = p0.x(), p0.y(), p1.x() - p0.x(), p1.y() - p0.y()
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - r.left()), (dx, r.right() - x0), (-dy, y0 - r.top()), (dy, r.bottom() - y0)):
        if abs(p) < 1e-12:
            if q < 0:
                return None
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return None
    return QPointF(x0 + t0 * dx, y0 + t0 * dy), QPointF(x0 + t1 * dx, y0 + t1 * dy)


def _hatch_lines(path, r, ang, step):
    """r dikdörtgenini ang açılı paralel çizgilerle tarar (çizgiler dikdörtgene kırpılır)."""
    d = QPointF(math.cos(ang), math.sin(ang))
    n = QPointF(-d.y(), d.x())
    c = r.center()
    big = math.hypot(r.width(), r.height())
    k = int(big / 2 / step) + 1
    for i in range(-k, k + 1):
        o = c + n * (i * step)
        seg = _clip(o - d * big, o + d * big, r)
        if seg and math.hypot(seg[1].x() - seg[0].x(), seg[1].y() - seg[0].y()) > 0.5:
            path.moveTo(seg[0])
            path.lineTo(seg[1])


# ------------------------------------------------------------------ grafikler
def _gauss(r, w):
    """Standart normal dağılım: çan eğrisi (−3,5σ … 3,5σ), yatay eksen, μ çizgisi, ±1/2/3σ çentikleri."""
    path = QPainterPath()
    base = r.bottom()
    hgt = r.height() * 0.94
    span = 3.6

    def X(z):
        return r.center().x() + z / span * r.width() / 2

    pts = []
    n = 120
    for i in range(n + 1):
        z = -span + 2 * span * i / n
        pts.append(QPointF(X(z), base - hgt * math.exp(-z * z / 2)))
    _poly(path, pts)
    path.moveTo(QPointF(r.left(), base))         # eksen
    path.lineTo(QPointF(r.right(), base))
    path.moveTo(QPointF(X(0), base))             # μ
    path.lineTo(QPointF(X(0), base - hgt))
    tick = max(4.0, w * 2.2, r.height() * 0.035)
    for z in (-3, -2, -1, 1, 2, 3):
        y = base - hgt * math.exp(-z * z / 2)
        path.moveTo(QPointF(X(z), base + tick))
        path.lineTo(QPointF(X(z), base))
        if abs(z) == 1:                          # ±1σ: eğriye kadar ince çizgi
            path.moveTo(QPointF(X(z), base))
            path.lineTo(QPointF(X(z), y))
    return path


def _axes(r, w):
    path = QPainterPath()
    h = max(10.0, w * 3.4)
    o = QPointF(r.left(), r.bottom())
    _arrow(path, o, QPointF(r.right(), r.bottom()), h)
    _arrow(path, o, QPointF(r.left(), r.top()), h)
    return path


def _sine(r, w):
    """İki tam periyot sinüs + orta eksen."""
    path = QPainterPath()
    cy, amp = r.center().y(), r.height() / 2
    n = 160
    pts = [QPointF(r.left() + r.width() * i / n, cy - amp * math.sin(4 * math.pi * i / n)) for i in range(n + 1)]
    _poly(path, pts)
    path.moveTo(QPointF(r.left(), cy))
    path.lineTo(QPointF(r.right(), cy))
    return path


def _grid(r, w):
    path = QPainterPath()
    path.addRect(r)
    x = r.left() + GRID
    while x < r.right() - 0.5:
        path.moveTo(QPointF(x, r.top()))
        path.lineTo(QPointF(x, r.bottom()))
        x += GRID
    y = r.top() + GRID
    while y < r.bottom() - 0.5:
        path.moveTo(QPointF(r.left(), y))
        path.lineTo(QPointF(r.right(), y))
        y += GRID
    return path


def _iso_grid(r, w):
    """İzometrik ızgara: düşey + ±30° çizgiler (izometrik kâğıt)."""
    path = QPainterPath()
    path.addRect(r)
    sx = GRID * COS30                     # düşey çizgiler arası
    x = r.left() + sx
    while x < r.right() - 0.5:
        path.moveTo(QPointF(x, r.top()))
        path.lineTo(QPointF(x, r.bottom()))
        x += sx
    # ±30° çizgiler: dik aralık = GRID·cos30 (üçgen kafes)
    for ang in (math.radians(-30), math.radians(30)):
        _hatch_lines(path, r, ang, GRID * COS30)
    return path


# ------------------------------------------------------------------ makine
def _inv(a):
    return math.tan(a) - a


def _gear(r, w):
    """Düz dişli, evolvent profil (kavrama açısı 20°). Modül sabit sayılır → diş sayısı çapla artar,
    aynı kalınlıkta çizilen dişliler birbirine uyar. Göbekte delik + kama yuvası."""
    path = QPainterPath()
    D = min(r.width(), r.height())
    m = max(5.0, w * 2.6)                                  # modül
    z = max(8, min(90, int(round((D / 2 - m) * 2 / m))))   # dış çap ≈ D
    rp = z * m / 2
    ra, rf = rp + m, max(rp - 1.25 * m, rp * 0.5)
    alpha = math.radians(20)
    rb = rp * math.cos(alpha)
    half = math.pi / (2 * z) + _inv(alpha)                 # temel daire yarım diş açısı (evolvent başlangıcı)
    pitch = 2 * math.pi / z
    r_lo = max(rb, rf)
    steps = 6
    pts = []
    for i in range(z):
        c = i * pitch - math.pi / 2
        left, right = [], []
        if rf < rb:                                        # temel dairenin altı: radyal
            left.append((rf, c - half))
        for k in range(steps + 1):
            rr = r_lo + (ra - r_lo) * k / steps
            a = math.acos(min(1.0, rb / rr))
            hh = half - _inv(a)
            left.append((rr, c - hh))
            right.append((rr, c + hh))
        right.reverse()
        if rf < rb:
            right.append((rf, c + half))
        pts += left + right
    sx, sy = r.width() / (2 * ra), r.height() / (2 * ra)  # kare değilse elipse yayılır (elips aracı gibi)
    cx, cy = r.center().x(), r.center().y()

    def P(rr, a):
        return QPointF(cx + rr * math.cos(a) * sx, cy + rr * math.sin(a) * sy)

    _poly(path, [P(rr, a) for rr, a in pts], close=True)
    # göbek: delik + kama yuvası
    rh = rf * 0.28
    kw, kd = rh * 0.42, rh * 0.32
    a0 = math.asin(min(0.99, kw / 2 / rh))
    hole = []
    n = 40
    for k in range(n + 1):
        a = -math.pi / 2 + a0 + (2 * math.pi - 2 * a0) * k / n
        hole.append(P(rh, a))
    top = -math.pi / 2
    hole += [P(math.hypot(rh + kd, kw / 2), top - math.atan2(kw / 2, rh + kd)),
             P(math.hypot(rh + kd, kw / 2), top + math.atan2(kw / 2, rh + kd))]
    _poly(path, hole, close=True)
    return path


def _bearing(r, w):
    """Bilyalı rulman (önden): dış bilezik, iç bilezik, bilyalar."""
    path = QPainterPath()
    c = r.center()
    R = min(r.width(), r.height()) / 2
    sx, sy = r.width() / (2 * R), r.height() / (2 * R)

    def circ(rad, cc=c):
        path.addEllipse(QRectF(cc.x() - rad * sx, cc.y() - rad * sy, 2 * rad * sx, 2 * rad * sy))

    for k in (1.0, 0.8, 0.5, 0.3):
        circ(R * k)
    rm, rball = R * 0.65, R * 0.13
    nb = max(6, int(2 * math.pi * rm / (rball * 2.6)))
    for i in range(nb):
        a = 2 * math.pi * i / nb
        circ(rball, QPointF(c.x() + rm * math.cos(a) * sx, c.y() + rm * math.sin(a) * sy))
    return path


def _hexnut(r, w):
    """Altıgen somun (üstten): altıgen, pah dairesi, diş (3/4 yay) ve delik."""
    path = QPainterPath()
    c = r.center()
    R = min(r.width(), r.height()) / 2
    sx, sy = r.width() / (2 * R), r.height() / (2 * R)

    def P(rad, a):
        return QPointF(c.x() + rad * math.cos(a) * sx, c.y() + rad * math.sin(a) * sy)

    _poly(path, [P(R, math.pi / 6 + i * math.pi / 3) for i in range(6)], close=True)
    path.addEllipse(QRectF(c.x() - R * 0.42 * sx, c.y() - R * 0.42 * sy, R * 0.84 * sx, R * 0.84 * sy))
    # diş: 3/4 yay (teknik resimdeki gibi)
    rt = R * 0.52
    arc = [P(rt, math.radians(a)) for a in range(0, 271, 6)]
    path.moveTo(arc[0])
    for p in arc[1:]:
        path.lineTo(p)
    return path


# ------------------------------------------------------------------ izometrik
def _iso_box(r, w):
    """İzometrik kutu: dikdörtgene sığan küp (en / boy oranı kutuyu uzatır). Görünen kenarlar."""
    path = QPainterPath()
    # birim küp: genişlik 2·cos30, yükseklik 2
    sx, sy = r.width() / (2 * COS30), r.height() / 2
    cx, top = r.center().x(), r.top()

    def P(u, v):          # u: yatay (cos30 birimi), v: aşağı
        return QPointF(cx + u * COS30 * sx, top + v * sy)

    outline = [P(0, 0), P(1, SIN30), P(1, 1 + SIN30), P(0, 2), P(-1, 1 + SIN30), P(-1, SIN30)]
    _poly(path, outline, close=True)
    mid = P(0, 1)
    for q in (P(-1, SIN30), P(1, SIN30), P(0, 2)):
        path.moveTo(mid)
        path.lineTo(q)
    return path


def _iso_cyl(r, w):
    """İzometrik (düşey) silindir: üst elips tam, alt elipsin önü, yan çizgiler."""
    path = QPainterPath()
    rw = r.width()
    eh = min(rw * math.tan(math.pi / 6), r.height() / 2)   # izometrik elips oranı ≈ 0,577
    top = QRectF(r.left(), r.top(), rw, eh)
    bot = QRectF(r.left(), r.bottom() - eh, rw, eh)
    path.addEllipse(top)
    path.moveTo(QPointF(r.left(), top.center().y()))
    path.lineTo(QPointF(r.left(), bot.center().y()))
    path.arcTo(bot, 180, 180)
    path.lineTo(QPointF(r.right(), top.center().y()))
    return path


def _iso_axes(r, w):
    """İzometrik eksen takımı: düşey z, ±30° x ve y."""
    path = QPainterPath()
    h = max(10.0, w * 3.4)
    o = QPointF(r.center().x(), r.top() + r.height() * 0.62)
    L = min(r.width() / (2 * COS30), r.height() * 0.62, (r.bottom() - o.y()) / SIN30)
    _arrow(path, o, QPointF(o.x(), r.top()), h)
    _arrow(path, o, QPointF(o.x() - L * COS30, o.y() + L * SIN30), h)
    _arrow(path, o, QPointF(o.x() + L * COS30, o.y() + L * SIN30), h)
    return path


# ------------------------------------------------------------------ statik / mukavemet
def _pin(r, w):
    """Sabit mesnet: üçgen, taban çizgisi, tarama."""
    path = QPainterPath()
    hb = r.height() * 0.24                       # tarama yüksekliği
    by = r.bottom() - hb
    tw = min(r.width() * 0.7, (by - r.top()) * 1.25)
    c = r.center().x()
    _poly(path, [QPointF(c, r.top()), QPointF(c + tw / 2, by), QPointF(c - tw / 2, by)], close=True)
    path.moveTo(QPointF(r.left(), by))
    path.lineTo(QPointF(r.right(), by))
    _hatch_lines(path, QRectF(r.left(), by, r.width(), hb), math.radians(45), max(6.0, hb * 0.55))
    return path


def _roller(r, w):
    """Kayar mesnet: üçgen, iki tekerlek, taban çizgisi + tarama."""
    path = QPainterPath()
    hb = r.height() * 0.18
    gy = r.bottom() - hb
    rr = r.height() * 0.1
    ty = gy - 2 * rr
    tw = min(r.width() * 0.7, (ty - r.top()) * 1.25)
    c = r.center().x()
    _poly(path, [QPointF(c, r.top()), QPointF(c + tw / 2, ty), QPointF(c - tw / 2, ty)], close=True)
    for x in (c - tw / 4, c + tw / 4):
        path.addEllipse(QPointF(x, ty + rr), rr, rr)
    path.moveTo(QPointF(r.left(), gy))
    path.lineTo(QPointF(r.right(), gy))
    _hatch_lines(path, QRectF(r.left(), gy, r.width(), hb), math.radians(45), max(6.0, hb * 0.7))
    return path


def _moment(r, w):
    """Moment: 270°'lik yay + ok ucu (saat yönünün tersi)."""
    path = QPainterPath()
    h = max(10.0, w * 3.4)
    c = r.center()
    rx, ry = r.width() / 2, r.height() / 2
    a0, a1 = math.radians(-45), math.radians(-45 - 270)
    n = 60
    pts = [QPointF(c.x() + rx * math.cos(a0 + (a1 - a0) * i / n), c.y() + ry * math.sin(a0 + (a1 - a0) * i / n))
           for i in range(n + 1)]
    _poly(path, pts)
    p, q = pts[-2], pts[-1]
    _head(path, q, math.atan2(q.y() - p.y(), q.x() - p.x()), h)
    path.addEllipse(c, max(1.5, w * 0.6), max(1.5, w * 0.6))
    return path


# ------------------------------------------------------------------ çizgi şekilleri (a → b)
def _frame(a, b):
    L = math.hypot(b.x() - a.x(), b.y() - a.y())
    if L < 1e-6:
        return L, None
    d = QPointF((b.x() - a.x()) / L, (b.y() - a.y()) / L)
    n = QPointF(-d.y(), d.x())

    def P(u, v):
        return a + d * u + n * v
    return L, P


def _spring(a, b, w):
    """Helis yay (yandan): düz uçlar + zikzak."""
    path = QPainterPath()
    L, P = _frame(a, b)
    if P is None:
        return path
    end = min(L * 0.12, 30.0)
    amp = max(6.0, min(L * 0.09, 26.0))
    coils = max(4, min(16, int((L - 2 * end) / (amp * 0.9))))
    pts = [P(0, 0), P(end, 0)]
    seg = (L - 2 * end) / (coils * 2)
    for i in range(coils * 2):
        pts.append(P(end + seg * (i + 0.5), amp if i % 2 == 0 else -amp))
    pts += [P(L - end, 0), P(L, 0)]
    _poly(path, pts)
    return path


def _damper(a, b, w):
    """Sönümleyici (amortisör): silindir + piston."""
    path = QPainterPath()
    L, P = _frame(a, b)
    if P is None:
        return path
    hw = max(6.0, min(L * 0.1, 24.0))
    c0, c1 = L * 0.3, L * 0.72                  # silindir (açık uç b'ye bakar)
    pp = L * 0.56                               # piston
    _poly(path, [P(0, 0), P(c0, 0)])
    _poly(path, [P(c1, hw), P(c0, hw), P(c0, -hw), P(c1, -hw)])
    _poly(path, [P(pp, hw * 0.75), P(pp, -hw * 0.75)])
    _poly(path, [P(pp, 0), P(L, 0)])
    return path


def _dim(a, b, w):
    """Ölçü çizgisi: iki uçlu ok + uçlarda dik uzatma çizgileri."""
    path = QPainterPath()
    L, P = _frame(a, b)
    if P is None:
        return path
    h = max(8.0, w * 3.0)
    ext = max(8.0, h * 1.2)
    _poly(path, [P(0, -ext), P(0, ext)])
    _poly(path, [P(L, -ext), P(L, ext)])
    path.moveTo(P(0, 0))
    path.lineTo(P(L, 0))
    ang = math.atan2(b.y() - a.y(), b.x() - a.x())
    _head(path, P(L, 0), ang, h)
    _head(path, P(0, 0), ang + math.pi, h)
    return path


def _load(a, b, w):
    """Yayılı yük: a→b kirişin üstüne inen eşit aralıklı oklar + üst çizgi."""
    path = QPainterPath()
    L, P = _frame(a, b)
    if P is None:
        return path
    hgt = max(14.0, min(L * 0.25, 60.0))
    h = max(7.0, w * 2.8)
    n = max(2, int(L / max(16.0, hgt * 0.6)))
    _poly(path, [P(0, -hgt), P(L, -hgt)])
    for i in range(n + 1):
        u = L * i / n
        _arrow(path, P(u, -hgt), P(u, 0), h)
    return path


def _ground(a, b, w):
    """Zemin / ankastre duvar: a→b çizgisi ve sağ yanında kısa eğik taramalar."""
    path = QPainterPath()
    L, P = _frame(a, b)
    if P is None:
        return path
    hl = max(8.0, min(L * 0.08, 18.0))
    path.moveTo(P(0, 0))
    path.lineTo(P(L, 0))
    step = max(7.0, hl * 0.8)
    u = step * 0.5
    while u <= L:
        path.moveTo(P(u, 0))
        path.lineTo(P(u - hl * 0.7, hl))
        u += step
    return path


# ------------------------------------------------------------------ makine (2)
def _pulley(r, w):
    """Kayış-kasnak: büyük ve küçük kasnak, dış teğet kayış, göbekler."""
    path = QPainterPath()
    cy = r.center().y()
    r1 = min(r.height() / 2, r.width() * 0.3)
    r2 = r1 * 0.55
    c1 = QPointF(r.left() + r1, cy)
    c2 = QPointF(r.right() - r2, cy)
    d = c2.x() - c1.x()
    for c, rr in ((c1, r1), (c2, r2)):
        path.addEllipse(c, rr, rr)
        path.addEllipse(c, rr * 0.82, rr * 0.82)       # kasnak yuvası
        path.addEllipse(c, rr * 0.18, rr * 0.18)       # mil
    if d > r1 - r2 + 1:
        phi = math.acos((r1 - r2) / d)
        for s in (-1, 1):
            n = QPointF(math.cos(phi), s * math.sin(phi))
            path.moveTo(c1 + n * r1)
            path.lineTo(c2 + n * r2)
    return path


def _wheel(r, w):
    """Tekerlek: lastik, jant, göbek, 5 kol, bijon delikleri."""
    path = QPainterPath()
    c = r.center()
    R = min(r.width(), r.height()) / 2
    sx, sy = r.width() / (2 * R), r.height() / (2 * R)

    def P(rad, a):
        return QPointF(c.x() + rad * math.cos(a) * sx, c.y() + rad * math.sin(a) * sy)

    def circ(rad, cc=None):
        cc = cc or c
        path.addEllipse(QRectF(cc.x() - rad * sx, cc.y() - rad * sy, 2 * rad * sx, 2 * rad * sy))

    circ(R)
    circ(R * 0.7)
    circ(R * 0.62)
    circ(R * 0.2)
    for i in range(5):
        a = -math.pi / 2 + 2 * math.pi * i / 5
        for da in (-0.09, 0.09):
            path.moveTo(P(R * 0.2, a + da * 2.2))
            path.lineTo(P(R * 0.62, a + da))
        circ(R * 0.035, P(R * 0.13, a + math.pi / 5))
    return path


def _fourbar(r, w):
    """Dört çubuk mekanizması: sabit uzuv (zemin mesnetleri), krank, biyel, sarkaç; mafsallar daire."""
    path = QPainterPath()

    def M(x, y):
        return QPointF(r.left() + x * r.width(), r.top() + y * r.height())

    ax, ay, dx = 0.12, 0.78, 0.82
    a, b, c = 0.26, 0.62, 0.5
    th = math.radians(70)
    bx, by = ax + a * math.cos(th), ay - a * math.sin(th)
    # C: |C−B| = b, |C−D| = c (üst çözüm)
    ex, ey = dx - bx, ay - by
    dd = math.hypot(ex, ey)
    k = (b * b - c * c + dd * dd) / (2 * dd)
    hh = math.sqrt(max(0.0, b * b - k * k))
    px, py = bx + k * ex / dd, by + k * ey / dd
    cx, cy = px + hh * ey / dd, py - hh * ex / dd
    if cy > ay:
        cx, cy = px - hh * ey / dd, py + hh * ex / dd
    A, B, C, D = M(ax, ay), M(bx, by), M(cx, cy), M(dx, ay)
    _poly(path, [A, B, C, D])
    jr = max(3.0, w * 1.6, min(r.width(), r.height()) * 0.025)
    for p in (A, B, C, D):
        path.addEllipse(p, jr, jr)
    # zemin mesnetleri: A ve D altında küçük üçgen + taramalı taban
    tw, tht = jr * 4, jr * 3.2
    for p in (A, D):
        _poly(path, [p + QPointF(0, jr), p + QPointF(tw / 2, tht), p + QPointF(-tw / 2, tht)], close=True)
        path.moveTo(p + QPointF(-tw * 0.8, tht))
        path.lineTo(p + QPointF(tw * 0.8, tht))
        _hatch_lines(path, QRectF(p.x() - tw * 0.8, p.y() + tht, tw * 1.6, jr * 1.6), math.radians(45), jr * 1.1)
    return path


# ------------------------------------------------------------------ kirişler
def _beam_ss(r, w):
    """Basit mesnetli kiriş: kiriş (dikdörtgen), solda sabit, sağda kayar mesnet."""
    path = QPainterPath()
    hb = max(4.0, min(r.height() * 0.2, r.width() * 0.06))
    path.addRect(QRectF(r.left(), r.top(), r.width(), hb))
    sw = min(r.width() * 0.14, (r.height() - hb) / 1.1)
    sh = sw * 1.1
    if sh > 4:
        path.addPath(_pin(QRectF(r.left() + sw * 0.15, r.top() + hb, sw, sh), w))
        path.addPath(_roller(QRectF(r.right() - sw * 1.15, r.top() + hb, sw, sh), w))
    return path


def _beam_cant(r, w):
    """Konsol (ankastre) kiriş: solda taramalı duvar, ondan çıkan kiriş."""
    path = QPainterPath()
    ww = max(6.0, r.width() * 0.07)
    x = r.left() + ww
    path.moveTo(QPointF(x, r.top()))
    path.lineTo(QPointF(x, r.bottom()))
    _hatch_lines(path, QRectF(r.left(), r.top(), ww, r.height()), math.radians(45), max(6.0, ww * 0.6))
    hb = max(4.0, min(r.height() * 0.22, r.width() * 0.07))
    path.addRect(QRectF(x, r.center().y() - hb / 2, r.right() - x, hb))
    return path


# ------------------------------------------------------------------ akış / araçlar
# NACA profilleri: 4 haneli (MPXX: kamburluk %M, yeri P/10, kalınlık %XX) ve 5 haneli 2X0XX
NACA = ("0006", "0009", "0012", "0015", "0018", "0024", "2412", "2415", "4412", "4415", "6409",
        "23012", "23015", "23018")
NACA_DEFAULT = "2412"
_NACA5 = {"210": (0.0580, 361.4), "220": (0.1260, 51.64), "230": (0.2025, 15.957), "240": (0.2900, 6.643),
          "250": (0.3910, 3.230)}     # standart 5 haneli ortalama kamburluk çizgisi: (m, k1)


def naca_ok(code):
    code = str(code or "")
    return code.isdigit() and (len(code) == 4 or (len(code) == 5 and code[:3] in _NACA5)) and int(code[-2:]) > 0


def naca_info(code):
    """(kamburluk %, kalınlık %) — menüde açıklama için."""
    if len(code) == 5:
        return None, int(code[-2:])
    return int(code[0]), int(code[2:])


def _camber(code):
    """x → (yc, dyc/dx)"""
    if len(code) == 5:
        m, k1 = _NACA5[code[:3]]

        def f(x):
            if x < m:
                return k1 / 6 * (x ** 3 - 3 * m * x * x + m * m * (3 - m) * x), \
                    k1 / 6 * (3 * x * x - 6 * m * x + m * m * (3 - m))
            return k1 * m ** 3 / 6 * (1 - x), -k1 * m ** 3 / 6
        return f
    m, p = int(code[0]) / 100, int(code[1]) / 10

    def g(x):
        if m == 0 or p == 0:
            return 0.0, 0.0
        if x < p:
            return m / p ** 2 * (2 * p * x - x * x), 2 * m / p ** 2 * (p - x)
        return m / (1 - p) ** 2 * (1 - 2 * p + 2 * p * x - x * x), 2 * m / (1 - p) ** 2 * (p - x)
    return g


def _airfoil(r, w, code=None):
    """NACA kanat profili (kosinüs aralıklı noktalar), oran korunur."""
    path = QPainterPath()
    code = code if naca_ok(code) else NACA_DEFAULT
    t = int(code[-2:]) / 100
    camber = _camber(code)
    n = 70
    up, lo = [], []
    for i in range(n + 1):
        x = (1 - math.cos(math.pi * i / n)) / 2
        yt = 5 * t * (0.2969 * math.sqrt(x) - 0.126 * x - 0.3516 * x * x + 0.2843 * x ** 3 - 0.1036 * x ** 4)
        yc, dy = camber(x)
        th = math.atan(dy)
        up.append((x - yt * math.sin(th), yc + yt * math.cos(th)))
        lo.append((x + yt * math.sin(th), yc - yt * math.cos(th)))
    ys = [y for _, y in up + lo]
    y0, y1 = min(ys), max(ys)
    s = min(r.width(), r.height() / (y1 - y0))           # oran korunur (ince profil)
    ox = r.center().x() - s / 2
    oy = r.center().y() + (y1 + y0) / 2 * s

    def M(x, y):
        return QPointF(ox + x * s, oy - y * s)

    _poly(path, [M(*q) for q in list(reversed(up)) + lo[1:]], close=True)
    return path


def _fit(r, aspect):
    """Araç çizimleri en/boy oranını korur: yükseklik birimli (x 0…aspect, y 0…1) → sahne."""
    s = min(r.width() / aspect, r.height())
    ox = r.center().x() - aspect * s / 2
    oy = r.center().y() - s / 2
    return (lambda x, y: QPointF(ox + x * s, oy + y * s)), s


def _shape_parts(r, aspect, polys=(), closed=(), circles=(), lines=()):
    path = QPainterPath()
    M, s = _fit(r, aspect)
    for pl in polys:
        _poly(path, [M(*q) for q in pl])
    for pl in closed:
        _poly(path, [M(*q) for q in pl], close=True)
    for (x, y, rad) in circles:
        path.addEllipse(M(x, y), rad * s, rad * s)
    for (x0, y0, x1, y1) in lines:
        path.moveTo(M(x0, y0))
        path.lineTo(M(x1, y1))
    return path


def _arch(cx, cy, rad, n=16):
    """Çamurluk kemeri: sağdan sola üstten geçen yarım daire noktaları."""
    return [(cx + rad * math.cos(-math.pi * i / n), cy + rad * math.sin(-math.pi * i / n)) for i in range(n + 1)]


def _car(r, w):
    body = ([(0.05, 0.75), (0.05, 0.52), (0.2, 0.44), (0.65, 0.38), (0.95, 0.14), (1.7, 0.12), (2.05, 0.38),
             (2.5, 0.45), (2.57, 0.58), (2.55, 0.75), (2.26, 0.75)] + _arch(2.0, 0.75, 0.26)
            + [(0.86, 0.75)] + _arch(0.6, 0.75, 0.26) + [(0.05, 0.75)])
    return _shape_parts(r, 2.6, polys=[body],
                        closed=[[(0.98, 0.38), (1.1, 0.2), (1.45, 0.19), (1.45, 0.38)],
                                [(1.55, 0.38), (1.55, 0.19), (1.68, 0.19), (1.92, 0.38)]],
                        circles=[(0.6, 0.75, 0.21), (0.6, 0.75, 0.08), (2.0, 0.75, 0.21), (2.0, 0.75, 0.08)],
                        lines=[(1.5, 0.42, 1.5, 0.7)])


def _hide(polys, circles, step=0.01):
    """Yandan görünüşte tekerleğin arkasında kalan çizgileri siler: çoklu çizgiler sık örneklenir,
    dairelerin (x, y, r) içine düşen kısımlar atılır, kalanlar ayrı parçalar olarak döner."""
    out = []
    for pl in polys:
        cur = []
        for (x0, y0), (x1, y1) in zip(pl, pl[1:]):
            n = max(1, int(math.hypot(x1 - x0, y1 - y0) / step))
            for i in range(n + 1):
                if i == 0 and cur:
                    continue
                x, y = x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n
                if any((x - cx) ** 2 + (y - cy) ** 2 < cr * cr for cx, cy, cr in circles):
                    if len(cur) > 1:
                        out.append(cur)
                    cur = []
                else:
                    cur.append((x, y))
        if len(cur) > 1:
            out.append(cur)
    return out


def _f1(r, w):
    """Formula 1 aracı (yandan, burun sağda): ön / arka kanat, burun, kokpit + halo + kask, hava kutusu,
    yan kanal, taban; tekerlekler gövdenin önünde (arkalarında kalan çizgiler gizlenir)."""
    RW, FW = (0.78, 0.63, 0.37), (4.02, 0.65, 0.35)            # arka / ön tekerlek (x, y, r)
    body = [
        # motor kapağı: arkadan hava kutusuna
        [(0.5, 0.72), (0.5, 0.6), (0.9, 0.5), (1.5, 0.34), (1.95, 0.17), (2.12, 0.1), (2.3, 0.1), (2.3, 0.25)],
        # kokpit ağzı → burun üstü → burun ucu
        [(2.3, 0.25), (2.38, 0.36), (2.78, 0.38), (3.3, 0.45), (3.9, 0.53), (4.45, 0.65), (4.64, 0.72),
         (4.6, 0.77), (4.2, 0.72), (3.6, 0.63), (3.3, 0.62), (3.25, 0.86)],
        # taban (monokok altı + zemin)
        [(3.25, 0.86), (1.05, 0.86), (0.55, 0.8), (0.5, 0.72)],
        # yan kanal (sidepod): hava girişi önde
        [(1.25, 0.84), (1.35, 0.6), (1.7, 0.5), (2.55, 0.5), (2.62, 0.52), (2.62, 0.74), (2.4, 0.8), (1.25, 0.84)],
        # halo: kokpitin üstünden öndeki dikmeye
        [(2.25, 0.18), (2.5, 0.15), (2.78, 0.2), (2.95, 0.34), (3.0, 0.44)],
        # hava kutusu ağzı
        [(2.12, 0.1), (2.12, 0.22)],
        # yan aynalar / ön süspansiyon (görünen kısımlar)
        [(3.25, 0.55), (4.02, 0.6)], [(3.25, 0.7), (4.02, 0.67)],
        [(0.9, 0.62), (1.4, 0.55)], [(0.9, 0.72), (1.35, 0.7)],
        # arka kanat dikmesi
        [(0.36, 0.5), (0.62, 0.62)],
    ]
    wings = [
        # arka kanat yan levhası
        [(0.02, 0.05), (0.42, 0.05), (0.42, 0.42), (0.3, 0.52), (0.02, 0.52), (0.02, 0.05)],
        # ana kanat ve DRS kanatçığı (eğik profiller)
        [(0.05, 0.3), (0.2, 0.26), (0.4, 0.26)], [(0.05, 0.17), (0.22, 0.12), (0.4, 0.11)],
        # ön kanat: yan levha + kanatçıklar
        [(4.38, 0.96), (4.38, 0.78), (4.66, 0.76), (4.8, 0.86), (4.8, 0.96), (4.38, 0.96)],
        [(4.36, 0.92), (4.8, 0.9)], [(4.36, 0.86), (4.72, 0.82)],
        # difüzör
        [(0.25, 0.86), (0.55, 0.8)],
    ]
    path = QPainterPath()
    M, s = _fit(r, 4.8)
    for pl in _hide(body + wings, [RW, FW]):
        _poly(path, [M(*q) for q in pl])
    for cx, cy, cr in (RW, FW):
        for k in (1.0, 0.7, 0.62, 0.16):
            path.addEllipse(M(cx, cy), cr * k * s, cr * k * s)
    path.addEllipse(M(2.53, 0.3), 0.085 * s, 0.085 * s)       # kask
    _poly(path, [M(2.47, 0.27), M(2.6, 0.27)])                  # vizör
    return path


def _plane(r, w):
    half = [(0.5, 0.0), (0.54, 0.05), (0.555, 0.15), (0.56, 0.36), (0.98, 0.56), (0.98, 0.61), (0.56, 0.53),
            (0.55, 0.8), (0.72, 0.9), (0.72, 0.94), (0.53, 0.92), (0.5, 0.99)]
    outline = half + [(1 - x, y) for x, y in reversed(half[1:-1])]
    return _shape_parts(r, 1.0, closed=[outline],
                        lines=[(0.71, 0.43, 0.71, 0.53), (0.29, 0.43, 0.29, 0.53),
                               (0.48, 0.06, 0.52, 0.06)])


def _tank(r, w):
    path = QPainterPath()
    M, s = _fit(r, 2.6)
    track = QRectF(M(0.1, 0.6), M(2.5, 0.95))
    rad = track.height() / 2
    path.addRoundedRect(track, rad, rad)
    path.addPath(_shape_parts(r, 2.6,
                              closed=[[(0.15, 0.6), (0.3, 0.45), (2.3, 0.45), (2.5, 0.6)],
                                      [(0.8, 0.45), (0.9, 0.25), (1.7, 0.22), (1.85, 0.45)],
                                      [(1.75, 0.29), (2.6, 0.29), (2.6, 0.35), (1.78, 0.35)]],
                              circles=[(0.38 + 0.368 * i, 0.775, 0.12) for i in range(6)]
                              + [(0.38 + 0.368 * i, 0.775, 0.035) for i in range(6)]))
    return path


def _ship(r, w):
    return _shape_parts(r, 2.6,
                        closed=[[(0.05, 0.58), (2.6, 0.5), (2.3, 0.95), (0.2, 0.95)],
                                [(0.45, 0.565), (0.45, 0.35), (1.3, 0.35), (1.4, 0.545)],
                                [(0.6, 0.35), (0.6, 0.2), (1.1, 0.2), (1.1, 0.35)],
                                [(1.6, 0.535), (1.66, 0.15), (1.86, 0.15), (1.9, 0.53)]],
                        circles=[(0.55 + 0.3 * i, 0.68, 0.035) for i in range(6)],
                        lines=[(0.139, 0.8, 2.4, 0.8), (0.7, 0.2, 0.7, 0.05), (0.7, 0.05, 1.0, 0.12)])


# ------------------------------------------------------------------ termodinamik
def _ah(r, w):
    """Ok ucu boyu: kalınlığa ve şeklin boyuna göre (ikonda da orantılı)."""
    return max(3.0, w * 3.2, min(r.width(), r.height()) * 0.045)


def _mid_head(path, pts, h, at=0.5):
    """Çoklu çizginin uzunluğunun 'at' kesrinde akış yönünü gösteren ok ucu."""
    if len(pts) < 2:
        return
    seg = [math.hypot(q.x() - p.x(), q.y() - p.y()) for p, q in zip(pts, pts[1:])]
    goal = sum(seg) * at
    for (p, q), L in zip(zip(pts, pts[1:]), seg):
        if goal <= L and L > 1e-9:
            t = goal / L
            tip = QPointF(p.x() + (q.x() - p.x()) * t, p.y() + (q.y() - p.y()) * t)
            ang = math.atan2(q.y() - p.y(), q.x() - p.x())
            tip = QPointF(tip.x() + h * 0.45 * math.cos(ang), tip.y() + h * 0.45 * math.sin(ang))
            _head(path, tip, ang, h)
            return
        goal -= L


def _diagram(r, w, segs, xr, yr, dome=None):
    """Durum diyagramı (P–v / T–s): sol alt köşede eksenler, segs = veri koordinatında (x, y) çoklu çizgiler
    (her birinin ortasında yön oku, uçlarında durum noktası); dome = ok/nokta olmadan çizilen eğri."""
    path = QPainterPath()
    h = _ah(r, w)
    o = QPointF(r.left(), r.bottom())
    _arrow(path, o, QPointF(r.right(), r.bottom()), h)
    _arrow(path, o, QPointF(r.left(), r.top()), h)
    x0, x1 = r.left() + r.width() * 0.1, r.right() - r.width() * 0.08
    y0, y1 = r.bottom() - r.height() * 0.1, r.top() + r.height() * 0.1

    def M(x, y):
        return QPointF(x0 + (x - xr[0]) / (xr[1] - xr[0]) * (x1 - x0), y0 + (y - yr[0]) / (yr[1] - yr[0]) * (y1 - y0))

    if dome:
        _poly(path, [M(*q) for q in dome])
    dr = max(1.4, w * 0.9, min(r.width(), r.height()) * 0.012)
    for sg in segs:
        pts = [M(*q) for q in sg]
        _poly(path, pts)
        _mid_head(path, pts, h)
        path.addEllipse(pts[0], dr, dr)
    return path


def _isen(va, pa, vb, k=1.4, n=30):
    return [(va + (vb - va) * i / n, pa * (va / (va + (vb - va) * i / n)) ** k) for i in range(n + 1)]


def _iso_t(va, pa, vb, n=30):
    return [(va + (vb - va) * i / n, pa * va / (va + (vb - va) * i / n)) for i in range(n + 1)]


def _cyc_otto(r, w):
    """Otto çevrimi (P–v): 1→2 izantropik sıkıştırma, 2→3 sabit hacimde ısı girişi, 3→4 genişleme, 4→1 ısı atma."""
    v1, v2, k = 1.0, 0.2, 1.4
    p2 = (v1 / v2) ** k
    p3 = p2 * 2.2
    p4 = p3 * (v2 / v1) ** k
    segs = [_isen(v1, 1.0, v2), [(v2, p2), (v2, p3)], _isen(v2, p3, v1), [(v1, p4), (v1, 1.0)]]
    return _diagram(r, w, segs, (0, 1.08), (0, p3 * 1.05))


def _cyc_diesel(r, w):
    """Diesel çevrimi (P–v): 2→3 sabit basınçta ısı girişi."""
    v1, v2, k = 1.0, 0.07, 1.4
    p2 = (v1 / v2) ** k
    v3 = v2 * 2.4
    p4 = p2 * (v3 / v1) ** k
    segs = [_isen(v1, 1.0, v2, n=40), [(v2, p2), (v3, p2)], _isen(v3, p2, v1, n=40), [(v1, p4), (v1, 1.0)]]
    return _diagram(r, w, segs, (0, 1.08), (0, p2 * 1.08))


def _cyc_carnot(r, w):
    """Carnot çevrimi (P–v): iki izoterm, iki izantropik."""
    th, k = 1.6, 1.4
    f = th ** (1 / (k - 1))
    v1, v2 = 0.15, 0.32
    v3, v4 = v2 * f, v1 * f
    p1, p2 = th / v1, th / v2
    p3, p4 = 1 / v3, 1 / v4
    segs = [_iso_t(v1, p1, v2), _isen(v2, p2, v3), _iso_t(v3, p3, v4), _isen(v4, p4, v1)]
    return _diagram(r, w, segs, (0, v3 * 1.06), (0, p1 * 1.06))


def _cyc_brayton(r, w):
    """Brayton çevrimi (T–s): sabit basınç eğrileri T = T₀·e^(s/cp)."""
    t1, t2, t3 = 1.0, 1.8, 4.0
    s3 = math.log(t3 / t2)
    t4 = t3 * t1 / t2
    n = 30
    segs = [[(0, t1), (0, t2)], [(s3 * i / n, t2 * math.exp(s3 * i / n)) for i in range(n + 1)],
            [(s3, t3), (s3, t4)], [(s3 * (1 - i / n), t1 * math.exp(s3 * (1 - i / n))) for i in range(n + 1)]]
    return _diagram(r, w, segs, (-0.12, s3 * 1.12), (0.6, t3 * 1.05))


def _sf(t):
    return 0.5 - 0.42 * max(0.0, 1 - t) ** 0.62


def _sg(t):
    return 0.5 + 0.42 * max(0.0, 1 - t) ** 0.42


def _cyc_rankine(r, w):
    """Rankine çevrimi (T–s): doyma eğrisi (kubbe), pompa, kazan (kızgın buhar), türbin, yoğuşturucu."""
    n = 40
    dome = ([(_sf(i / n), i / n) for i in range(n + 1)]
            + [(_sg(1 - i / n), 1 - i / n) for i in range(1, n + 1)])
    tl, th = 0.14, 0.72
    s1 = _sf(tl)
    s3 = _sg(th) + 0.13
    heat = [(s1 + 0.004, tl + 0.05)] + [(_sf(tl + 0.05 + (th - tl - 0.05) * i / 20), tl + 0.05 + (th - tl - 0.05) * i / 20)
                                        for i in range(1, 21)]
    sup = [(_sg(th) + 0.13 * (i / 12), th + 0.3 * (i / 12) ** 1.6) for i in range(13)]
    segs = [[(s1, tl), (s1 + 0.004, tl + 0.05)], heat + sup, [(s3, th + 0.3), (s3, tl)], [(s3, tl), (s1, tl)]]
    return _diagram(r, w, segs, (0, 1.0), (0, 1.08), dome=dome)


def _piston(r, w):
    """Piston-silindir düzeneği: et kalınlıklı silindir (üstü açık), piston + segmanlar, piston kolu,
    pistonun altında gaz, durdurucular ve alttan ısı girişi oku."""
    path = QPainterPath()
    h = _ah(r, w)
    W, H = r.width(), r.height()
    L, R = r.left() + W * 0.16, r.right() - W * 0.16
    t = max(2.0, W * 0.045)
    top, bot = r.top() + H * 0.12, r.bottom() - H * 0.2
    # silindir: dış ve iç çizgi
    _poly(path, [QPointF(L - t, top), QPointF(L - t, bot + t), QPointF(R + t, bot + t), QPointF(R + t, top)])
    _poly(path, [QPointF(L, top), QPointF(L, bot), QPointF(R, bot), QPointF(R, top)])
    _poly(path, [QPointF(L - t, top), QPointF(L, top)])
    _poly(path, [QPointF(R, top), QPointF(R + t, top)])
    # piston
    py, ph = top + (bot - top) * 0.36, (bot - top) * 0.18
    path.addRect(QRectF(L, py, R - L, ph))
    for f in (0.3, 0.55):
        _poly(path, [QPointF(L, py + ph * f), QPointF(R, py + ph * f)])
    # piston kolu
    cx, rw = r.center().x(), (R - L) * 0.05
    _poly(path, [QPointF(cx - rw, py), QPointF(cx - rw, r.top()), QPointF(cx + rw, r.top()), QPointF(cx + rw, py)])
    # durdurucular (pistonun üstünde)
    sw = (R - L) * 0.08
    for x0, x1 in ((L, L + sw), (R, R - sw)):
        _poly(path, [QPointF(x0, py - ph * 0.9), QPointF(x1, py - ph * 0.9), QPointF(x1, py - ph * 0.55),
                     QPointF(x0, py - ph * 0.55)])
    # ısı girişi: alttan üç ok
    for f in (0.3, 0.5, 0.7):
        x = L + (R - L) * f
        _arrow(path, QPointF(x, r.bottom()), QPointF(x, bot + t + H * 0.03), h)
    return path


def _compressor(r, w):
    """Kompresör simgesi: akış yönünde daralan yamuk + mil."""
    path = QPainterPath()
    W, H, cy = r.width(), r.height(), r.center().y()
    a, b = r.left() + W * 0.15, r.right() - W * 0.15
    _poly(path, [QPointF(a, r.top()), QPointF(b, cy - H * 0.22), QPointF(b, cy + H * 0.22), QPointF(a, r.bottom())],
          close=True)
    _poly(path, [QPointF(r.left(), cy), QPointF(a, cy)])
    _poly(path, [QPointF(b, cy), QPointF(r.right(), cy)])
    return path


def _turbine(r, w):
    """Türbin simgesi: akış yönünde genişleyen yamuk + mil."""
    path = QPainterPath()
    W, H, cy = r.width(), r.height(), r.center().y()
    a, b = r.left() + W * 0.15, r.right() - W * 0.15
    _poly(path, [QPointF(a, cy - H * 0.22), QPointF(b, r.top()), QPointF(b, r.bottom()), QPointF(a, cy + H * 0.22)],
          close=True)
    _poly(path, [QPointF(r.left(), cy), QPointF(a, cy)])
    _poly(path, [QPointF(b, cy), QPointF(r.right(), cy)])
    return path


def _pump(r, w):
    """Pompa simgesi: daire, içinde çıkışa bakan üçgen, solda giriş, üstten teğet çıkış."""
    path = QPainterPath()
    c = r.center()
    R = min(r.width() * 0.36, r.height() * 0.42)
    path.addEllipse(c, R, R)
    _poly(path, [QPointF(c.x() - R * 0.45, c.y() - R * 0.62), QPointF(c.x() + R * 0.72, c.y()),
                 QPointF(c.x() - R * 0.45, c.y() + R * 0.62)], close=True)
    _poly(path, [QPointF(r.left(), c.y()), QPointF(c.x() - R, c.y())])
    _poly(path, [QPointF(c.x(), c.y() - R), QPointF(r.right(), c.y() - R)])
    return path


def _hx(r, w):
    """Isı değiştirici / kazan / yoğuşturucu: kutu ve içinden geçen kıvrımlı boru."""
    path = QPainterPath()
    W, H, cy = r.width(), r.height(), r.center().y()
    a, b = r.left() + W * 0.14, r.right() - W * 0.14
    path.addRect(QRectF(a, r.top(), b - a, H))
    n = 5
    amp = H * 0.3
    pts = [QPointF(r.left(), cy), QPointF(a + (b - a) * 0.1, cy)]
    for i in range(2 * n):
        pts.append(QPointF(a + (b - a) * (0.1 + 0.8 * (i + 0.5) / (2 * n)), cy + (amp if i % 2 else -amp)))
    pts += [QPointF(a + (b - a) * 0.9, cy), QPointF(r.right(), cy)]
    _poly(path, pts)
    return path


def _valve(r, w):
    """Vana / kısılma vanası: uç uca iki üçgen, sap ve el çarkı."""
    path = QPainterPath()
    W, H = r.width(), r.height()
    cx, cy = r.center().x(), r.top() + H * 0.62
    hw = H * 0.36
    _poly(path, [QPointF(r.left(), cy - hw * 0.0), QPointF(r.left() + W * 0.12, cy)])
    _poly(path, [QPointF(r.right() - W * 0.12, cy), QPointF(r.right(), cy)])
    a, b = r.left() + W * 0.12, r.right() - W * 0.12
    _poly(path, [QPointF(a, cy - hw), QPointF(b, cy + hw), QPointF(b, cy - hw), QPointF(a, cy + hw)], close=True)
    _poly(path, [QPointF(cx, cy), QPointF(cx, r.top())])
    _poly(path, [QPointF(cx - W * 0.16, r.top()), QPointF(cx + W * 0.16, r.top())])
    return path


def _sym_parts(r, aspect, polys=(), closed=(), lines=()):
    """Eksene göre simetrik çizim: (x, d) noktaları, d eksenden uzaklık (0…0,5); üst ve alt yarı çizilir."""
    path = QPainterPath()
    M, s = _fit(r, aspect)
    for sgn in (-1, 1):
        def P(q):
            return M(q[0], 0.5 + sgn * q[1])
        for pl in polys:
            _poly(path, [P(q) for q in pl])
        for pl in closed:
            _poly(path, [P(q) for q in pl], close=True)
    for (x0, y0, x1, y1) in lines:
        path.moveTo(M(x0, y0))
        path.lineTo(M(x1, y1))
    return path


def _blades(x0, x1, n, hub, tip, gap=0.012):
    """Kanat sıraları: rotor ve stator dönüşümlü eğik çizgiler; hub(x) göbek yarıçapı."""
    out = []
    for i in range(n):
        x = x0 + (x1 - x0) * i / max(1, n - 1)
        dx = 0.025 if i % 2 == 0 else -0.025
        out.append([(x, hub(x) + gap), (x + dx, tip(x) - gap)])
    return out


def _lerp(xa, ya, xb, yb):
    return lambda x: ya + (yb - ya) * (x - xa) / (xb - xa)


def _turbojet(r, w):
    """Turbojet (kesit): giriş, eksenel kompresör (daralan kanal), yanma odası, türbin, egzoz lülesi, mil."""
    hub_c = _lerp(0.6, 0.16, 1.3, 0.26)
    hub_t = _lerp(2.0, 0.26, 2.3, 0.2)
    casing = lambda x: 0.38       # noqa: E731
    polys = [
        [(0.0, 0.34), (0.25, 0.38), (2.25, 0.38), (2.95, 0.27)],                       # iç cidar
        [(0.0, 0.34), (0.12, 0.42), (0.6, 0.46), (2.3, 0.46), (2.95, 0.3), (2.95, 0.27)],  # dış kaplama
        [(0.3, 0.0), (0.4, 0.09), (0.6, 0.16), (1.3, 0.26), (1.3, 0.12), (2.0, 0.12), (2.0, 0.26),
         (2.3, 0.2), (2.75, 0.0)],                                                       # burun konisi, göbek, kuyruk konisi
        [(1.28, 0.25), (1.42, 0.25)],                                                    # yakıt enjektörü
        [(0.62, 0.035), (2.28, 0.035)],                                                  # mil
    ] + _blades(0.68, 1.24, 8, hub_c, casing) + _blades(2.04, 2.26, 4, hub_t, casing)
    closed = [[(1.42, 0.22), (1.47, 0.17), (1.92, 0.17), (1.92, 0.33), (1.47, 0.33), (1.42, 0.28)]]  # yanma odası
    return _sym_parts(r, 3.0, polys=polys, closed=closed)


def _turbofan(r, w):
    """Turbofan (kesit): büyük fan, by-pass kanalı + çıkış kılavuz kanatları, çekirdek (kompresör, yanma,
    türbin), kısa nasel, kuyruk konisi."""
    hub_c = _lerp(0.85, 0.15, 1.25, 0.18)
    core_in = _lerp(0.8, 0.25, 1.65, 0.25)
    hub_t = _lerp(1.7, 0.18, 2.05, 0.15)
    core_t = _lerp(1.7, 0.245, 2.25, 0.21)
    polys = [
        [(0.0, 0.44), (0.15, 0.47), (0.55, 0.47), (1.3, 0.45), (1.55, 0.42)],           # nasel iç
        [(0.0, 0.44), (0.08, 0.49), (0.6, 0.5), (1.3, 0.47), (1.55, 0.42)],             # nasel dış
        [(0.2, 0.0), (0.3, 0.08), (0.42, 0.12), (0.55, 0.13), (0.85, 0.15), (1.25, 0.18), (1.25, 0.09),
         (1.7, 0.09), (1.7, 0.18), (2.05, 0.15), (2.5, 0.0)],                            # göbek / kuyruk konisi
        [(0.5, 0.025), (2.05, 0.025)],                                                   # mil
        [(0.85, 0.31), (0.9, 0.455)], [(0.98, 0.31), (1.03, 0.45)],                      # çıkış kılavuz kanatları
        [(1.22, 0.165), (1.34, 0.165)],                                                  # enjektör
    ] + _blades(0.88, 1.2, 5, hub_c, core_in) + _blades(1.75, 2.0, 4, hub_t, core_t)
    closed = [
        [(0.42, 0.12), (0.5, 0.12), (0.53, 0.465), (0.46, 0.465)],                       # fan kanadı
        [(0.62, 0.27), (0.8, 0.305), (1.7, 0.305), (2.3, 0.245), (2.25, 0.21), (1.65, 0.25), (0.8, 0.25)],  # çekirdek kaplaması
        [(1.34, 0.13), (1.38, 0.11), (1.62, 0.11), (1.62, 0.22), (1.38, 0.22), (1.34, 0.2)],  # yanma odası
    ]
    return _sym_parts(r, 2.6, polys=polys, closed=closed)


# ------------------------------------------------------------------ akışkanlar
def _hatch_band(path, r, step=None):
    _hatch_lines(path, r, math.radians(45), step or max(5.0, r.height() * 0.8))


def _boundary(r, w):
    """Sınır tabaka: düz levha (altı taralı), serbest akış okları, δ(x) ∝ √x sınırı, iki istasyonda
    hız profili u/U = 2η − η²."""
    path = QPainterPath()
    h = _ah(r, w)
    W, H = r.width(), r.height()
    py = r.bottom() - H * 0.1
    x0 = r.left() + W * 0.2
    _poly(path, [QPointF(x0, py), QPointF(r.right(), py)])
    _hatch_band(path, QRectF(x0, py, r.right() - x0, H * 0.1), max(5.0, H * 0.05))
    dmax = (py - r.top()) * 0.55
    Lp = r.right() - x0

    def d(x):
        return dmax * math.sqrt(max(0.0, (x - x0) / Lp))

    for f in (0.2, 0.45, 0.7):                       # serbest akış
        y = py - (py - r.top()) * f
        _arrow(path, QPointF(r.left(), y), QPointF(x0 - W * 0.04, y), h)
    _poly(path, [QPointF(x0 + Lp * i / 60, py - d(x0 + Lp * i / 60)) for i in range(61)])
    U = W * 0.11
    for f in (0.4, 0.8):
        xs = x0 + Lp * f
        dd = d(xs)
        top = py - min(dd * 1.6, py - r.top())
        _poly(path, [QPointF(xs, py), QPointF(xs, top)])
        prof = []
        for i in range(31):
            yy = (py - top) * i / 30
            eta = yy / dd if dd > 0 else 1
            u = (2 * eta - eta * eta) if eta < 1 else 1.0
            prof.append(QPointF(xs + U * u, py - yy))
        _poly(path, prof)
        for k in (0.25, 0.55, 0.85, 1.3):
            yy = dd * k
            if yy > py - top:
                continue
            eta = k
            u = (2 * eta - eta * eta) if eta < 1 else 1.0
            if U * u > h:
                _arrow(path, QPointF(xs, py - yy), QPointF(xs + U * u, py - yy), h * 0.8)
    return path


def _pipe_flow(r, w):
    """Boru akışı (laminer): taralı cidarlar, kesik eksen çizgisi, parabolik hız profili."""
    path = QPainterPath()
    h = _ah(r, w)
    W, H = r.width(), r.height()
    t = H * 0.1
    yt, yb = r.top() + t, r.bottom() - t
    for y, band in ((yt, QRectF(r.left(), r.top(), W, t)), (yb, QRectF(r.left(), yb, W, t))):
        _poly(path, [QPointF(r.left(), y), QPointF(r.right(), y)])
        _hatch_band(path, band, max(5.0, t * 0.7))
    cy, R = (yt + yb) / 2, (yb - yt) / 2
    x = r.left() + W * 0.06                          # kesik eksen
    dash = max(6.0, W * 0.04)
    while x < r.right():
        _poly(path, [QPointF(x, cy), QPointF(min(x + dash, r.right()), cy)])
        x += dash * 1.6
    xs, U = r.left() + W * 0.3, W * 0.42
    _poly(path, [QPointF(xs, yt), QPointF(xs, yb)])
    _poly(path, [QPointF(xs + U * (1 - ((cy - (yt + 2 * R * i / 40)) / R) ** 2), yt + 2 * R * i / 40)
                 for i in range(41)])
    for k in (-0.75, -0.4, 0.0, 0.4, 0.75):
        y = cy + R * k
        _arrow(path, QPointF(xs, y), QPointF(xs + U * (1 - k * k), y), h)
    return path


def _cyl_flow(r, w):
    """Silindir etrafında potansiyel akış: akım çizgileri ψ = U·y·(1 − R²/r²), durma çizgisi, oklar."""
    path = QPainterPath()
    h = _ah(r, w)
    c = r.center()
    R = min(r.height() * 0.17, r.width() * 0.12)
    path.addEllipse(c, R, R)
    for x0, x1 in ((r.left(), c.x() - R), (c.x() + R, r.right())):
        _poly(path, [QPointF(x0, c.y()), QPointF(x1, c.y())])
    _arrow(path, QPointF(r.left(), c.y()), QPointF(r.left() + (c.x() - R - r.left()) * 0.55, c.y()), h)
    H2 = r.height() / 2
    for j in range(1, 5):
        psi = H2 * (j / 4.4) * (1 - (R / max(H2, R * 1.01)) ** 2) * 0.98
        for sgn in (-1, 1):
            pts = []
            for i in range(1, 200):
                th = math.pi * (1 - i / 200)              # soldan sağa
                k = psi / math.sin(th)
                rr = (k + math.sqrt(k * k + 4 * R * R)) / 2
                p = QPointF(c.x() + rr * math.cos(th), c.y() - sgn * rr * math.sin(th))
                if r.contains(p):
                    pts.append(p)
                elif pts:
                    break
            _poly(path, pts)
            if len(pts) > 4:
                _mid_head(path, pts, h, at=0.12)
    return path


def _venturi(r, w):
    """Venturi borusu: daralan-genişleyen kanal, girişte ve boğazda piyezometre boruları (su seviyeleri)."""
    path = QPainterPath()
    W, H = r.width(), r.height()
    cy = r.top() + H * 0.72
    R0, Rt = H * 0.22, H * 0.1
    xs = [0.0, 0.25, 0.45, 0.55, 1.0]
    rs = [R0, R0, Rt, Rt, R0]

    def X(f):
        return r.left() + W * f
    for sgn in (-1, 1):
        _poly(path, [QPointF(X(f), cy + sgn * rr) for f, rr in zip(xs, rs)])
    tw = W * 0.018
    for f, rr, lvl in ((0.12, R0, 0.1), (0.5, Rt, 0.38)):
        for dx in (-tw, tw):
            _poly(path, [QPointF(X(f) + dx, cy - rr), QPointF(X(f) + dx, r.top())])
        y = r.top() + H * lvl
        _poly(path, [QPointF(X(f) - tw, y), QPointF(X(f) + tw, y)])
    h = _ah(r, w)
    _arrow(path, QPointF(X(0.02), cy), QPointF(X(0.2), cy), h)
    _arrow(path, QPointF(X(0.78), cy), QPointF(X(0.97), cy), h)
    return path


def _free_surface(path, x, y, s):
    """Serbest yüzey işareti: ucu yüzeyde ters üçgen, altında iki kısa çizgi."""
    _poly(path, [QPointF(x, y), QPointF(x - s * 0.6, y - s), QPointF(x + s * 0.6, y - s)], close=True)
    _poly(path, [QPointF(x - s * 0.7, y + s * 0.45), QPointF(x + s * 0.7, y + s * 0.45)])
    _poly(path, [QPointF(x - s * 0.35, y + s * 0.85), QPointF(x + s * 0.35, y + s * 0.85)])


def _tank_open(r, w):
    """Havaya açık su tankı: duvarlar, su yüzeyi + serbest yüzey işareti, derinlik ölçüsü h."""
    path = QPainterPath()
    W, H = r.width(), r.height()
    t = max(2.0, W * 0.03)
    L, R, B = r.left() + t, r.right() - t, r.bottom() - t
    _poly(path, [QPointF(r.left(), r.top()), QPointF(r.left(), r.bottom()), QPointF(r.right(), r.bottom()),
                 QPointF(r.right(), r.top())])
    _poly(path, [QPointF(L, r.top()), QPointF(L, B), QPointF(R, B), QPointF(R, r.top())])
    _poly(path, [QPointF(r.left(), r.top()), QPointF(L, r.top())])
    _poly(path, [QPointF(R, r.top()), QPointF(r.right(), r.top())])
    sy = r.top() + H * 0.24
    _poly(path, [QPointF(L, sy), QPointF(R, sy)])
    _free_surface(path, L + (R - L) * 0.7, sy, max(4.0, H * 0.06))
    _dim_v(path, L + (R - L) * 0.18, sy, B, _ah(r, w) * 0.8)
    return path


def _dim_v(path, x, y0, y1, h):
    """Düşey ölçü oku (iki uçlu)."""
    path.moveTo(QPointF(x, y0))
    path.lineTo(QPointF(x, y1))
    _head(path, QPointF(x, y0), -math.pi / 2, h)
    _head(path, QPointF(x, y1), math.pi / 2, h)


def _manometer(r, w):
    """U borulu manometre: kapalı basınçlı kap (A), bağlantı borusu, U boru (bir kolu havaya açık),
    manometre sıvısının seviyeleri ve aradaki yükseklik farkı h."""
    path = QPainterPath()
    W, H = r.width(), r.height()
    X = lambda f: r.left() + W * f      # noqa: E731
    Y = lambda f: r.top() + H * f       # noqa: E731
    path.addRect(QRectF(X(0.0), Y(0.1), W * 0.32, H * 0.52))            # kap
    _poly(path, [QPointF(X(0.0), Y(0.24)), QPointF(X(0.32), Y(0.24))])   # kaptaki sıvı yüzeyi
    t = W * 0.022
    xl, xr, py, yb = X(0.5), X(0.8), Y(0.48), Y(0.82)
    _poly(path, [QPointF(X(0.32), py - t), QPointF(xl + t, py - t)])     # bağlantı borusu
    _poly(path, [QPointF(X(0.32), py + t), QPointF(xl - t, py + t)])
    cxu, ro = (xl + xr) / 2, (xr - xl) / 2 + t
    ri = ro - 2 * t
    outer = [QPointF(xl - t, py + t), QPointF(xl - t, yb)]
    outer += [QPointF(cxu - ro * math.cos(math.pi * i / 24), yb + ro * math.sin(math.pi * i / 24)) for i in range(25)]
    outer += [QPointF(xr + t, Y(0.06))]
    inner = [QPointF(xl + t, py - t), QPointF(xl + t, yb)]
    inner += [QPointF(cxu - ri * math.cos(math.pi * i / 24), yb + ri * math.sin(math.pi * i / 24)) for i in range(25)]
    inner += [QPointF(xr - t, Y(0.06))]
    _poly(path, outer)
    _poly(path, inner)
    l1, l2 = Y(0.7), Y(0.4)                                               # seviyeler
    _poly(path, [QPointF(xl - t, l1), QPointF(xl + t, l1)])
    _poly(path, [QPointF(xr - t, l2), QPointF(xr + t, l2)])
    for y in (l1, l2):                                                    # ölçü uzatma çizgileri
        _poly(path, [QPointF(xr + t * 2, y), QPointF(X(0.97), y)])
    _poly(path, [QPointF(xl + t * 2, l1), QPointF(xr - t * 2, l1)])
    _dim_v(path, X(0.94), l2, l1, _ah(r, w) * 0.8)
    return path


def _incline(r, w):
    """Eğik düzlemde kayan kutu: kama (altı taralı zemin), θ açı yayı, eğime oturan kutu, hız oku."""
    path = QPainterPath()
    h = _ah(r, w)
    W, H = r.width(), r.height()
    base = r.bottom() - H * 0.1
    A, B, C = QPointF(r.left(), base), QPointF(r.right(), base), QPointF(r.right(), r.top() + H * 0.2)
    _poly(path, [A, B, C], close=True)
    _hatch_band(path, QRectF(r.left(), base, W, H * 0.1), max(5.0, H * 0.05))
    L = math.hypot(C.x() - A.x(), C.y() - A.y())
    d = QPointF((C.x() - A.x()) / L, (C.y() - A.y()) / L)
    n = QPointF(d.y(), -d.x())                       # eğime dik, yukarı
    th = math.atan2(-(C.y() - A.y()), C.x() - A.x())
    ra = W * 0.16
    _poly(path, [QPointF(A.x() + ra * math.cos(-th * i / 16), A.y() + ra * math.sin(-th * i / 16)) for i in range(17)])
    s = L * 0.2
    p0 = A + d * (L * 0.5)
    _poly(path, [p0, p0 + d * s, p0 + d * s + n * s, p0 + n * s], close=True)
    q = p0 + n * (s * 0.32) - d * (s * 0.15)          # hız: kutunun önünde, eğim boyunca aşağı
    _arrow(path, q, q - d * (s * 0.9), h)
    return path


_BOX = {"gauss": _gauss, "axes": _axes, "sine": _sine, "grid": _grid, "iso_grid": _iso_grid, "gear": _gear,
        "bearing": _bearing, "hexnut": _hexnut, "iso_box": _iso_box, "iso_cyl": _iso_cyl, "iso_axes": _iso_axes,
        "pin": _pin, "roller": _roller, "moment": _moment, "pulley": _pulley, "wheel": _wheel,
        "fourbar": _fourbar, "beam_ss": _beam_ss, "beam_cant": _beam_cant, "airfoil": _airfoil, "car": _car,
        "f1": _f1, "plane": _plane, "tank": _tank, "ship": _ship, "incline": _incline,
        "cyc_carnot": _cyc_carnot, "cyc_otto": _cyc_otto, "cyc_diesel": _cyc_diesel, "cyc_brayton": _cyc_brayton,
        "cyc_rankine": _cyc_rankine, "piston": _piston, "compressor": _compressor, "turbine": _turbine,
        "pump": _pump, "hx": _hx, "valve": _valve, "turbojet": _turbojet, "turbofan": _turbofan,
        "boundary": _boundary, "pipe_flow": _pipe_flow, "cyl_flow": _cyl_flow, "venturi": _venturi,
        "tank_open": _tank_open, "manometer": _manometer}
_LINE = {"spring": _spring, "damper": _damper, "dim": _dim, "load": _load, "ground": _ground}


def build(kind, a, b, width=2.5, var=None):
    """Şeklin yolu (yerel koordinat). var: türün seçeneği (kanat profilinde NACA kodu). Bilinmeyen tür → boş yol."""
    try:
        if kind in _LINE:
            return _LINE[kind](a, b, width)
        if kind in _BOX:
            r = QRectF(a, b).normalized()
            if r.width() < 1 or r.height() < 1:
                return QPainterPath()
            if kind == "airfoil":
                return _airfoil(r, width, var)
            return _BOX[kind](r, width)
    except (ValueError, ZeroDivisionError):
        pass
    return QPainterPath()


# --- ikon: şeklin kendisi küçük çizilir (icons.pixmap "eng_<tür>" adlarını buraya yollar)
_ICON_PTS = {"spring": ((2, 12), (22, 12)), "damper": ((2, 12), (22, 12)), "dim": ((3, 12), (21, 12)),
             "load": ((3, 17), (21, 17)), "ground": ((3, 9), (21, 9))}


def paint_icon(p: QPainter, kind, color, px):
    global GRID
    a, b = _ICON_PTS.get(kind, ((3, 3), (21, 21)))
    if kind in ("gauss", "sine", "grid", "iso_grid", "airfoil", "pulley", "beam_ss", "beam_cant", "boundary",
                "pipe_flow", "cyl_flow", "venturi", "hx", "valve", "compressor", "turbine", "incline", "manometer"):
        a, b = (2.5, 5), (21.5, 19)
    elif kind in ("turbojet", "turbofan", "car", "f1", "tank", "ship"):
        a, b = (1, 6), (23, 18)
    elif kind in ("iso_box", "iso_cyl"):
        a, b = (5, 2.5), (19, 21.5)
    s = px / 24.0
    p.scale(s, s)
    w = 1.0
    old, GRID = GRID, 4.6           # ızgara ikonda sık görünsün
    try:
        path = build(kind, QPointF(*a), QPointF(*b), 0.0)
    finally:
        GRID = old
    if kind == "gear":      # 24 px'te modül alt sınırı çok büyük: küçük dişli
        path = _gear_icon()
    pen = QPen(QColor(color), 1.5 if kind not in ("grid", "iso_grid", "bearing") else w,
               Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)


def _gear_icon():
    path = QPainterPath()
    pts = []
    z = 8
    for i in range(z):
        c = 2 * math.pi * i / z
        for rr, da in ((7.0, -0.26), (9.6, -0.15), (9.6, 0.15), (7.0, 0.26)):
            pts.append(QPointF(12 + rr * math.cos(c + da), 12 + rr * math.sin(c + da)))
    _poly(path, pts, close=True)
    path.addEllipse(QPointF(12, 12), 2.6, 2.6)
    return path
