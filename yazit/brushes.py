"""Kalem türleri (Paint'teki fırçalar gibi): kaligrafi kalemi, keçeli, kurşun kalem, pastel boya, sprey, suluboya.
Hepsi aynı vektör çizgiden (StrokeItem.path) çizilir: kayıt, geri al, silgi, döndürme her türde aynı çalışır.
Rastgelelik çizginin ilk noktasından tohumlanır: aynı çizgi her açılışta aynı görünür."""
import math
import random

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPainterPath, QPen, QColor, QPixmap, QImage, QBrush, QPolygonF, QPainterPathStroker

NAMES = ("pen", "calli", "marker", "pencil", "crayon", "spray", "water")
_tex_cache = {}


def _texture(color: QColor, kind):
    key = (color.rgba(), kind)
    if key in _tex_cache:
        return _tex_cache[key]
    n = 40 if kind == "pencil" else 56
    img = QImage(n, n, QImage.Format.Format_ARGB32)
    img.fill(0)
    rnd = random.Random(7 if kind == "pencil" else 11)
    for y in range(n):
        for x in range(n):
            if kind == "pencil":
                a = rnd.randint(60, 235)
            else:     # pastel boya: kâğıdın dokusu delik delik görünür
                a = 0 if rnd.random() < 0.28 else rnd.randint(150, 255)
            c = QColor(color)
            c.setAlpha(int(a * color.alphaF()))
            img.setPixelColor(x, y, c)
    pm = QPixmap.fromImage(img)
    _tex_cache[key] = pm
    if len(_tex_cache) > 64:
        _tex_cache.pop(next(iter(_tex_cache)))
    return pm


def polylines(it):
    return [list(pg) for pg in it.path().toSubpathPolygons()]


def extent(it):
    """Çizginin yolundan ne kadar taşabileceği (sınır kutusu için)."""
    w = it.width
    return {"calli": w * 1.3, "marker": w * 0.9, "crayon": w * 1.0, "spray": w * 2.4 + 4, "water": w * 1.3}.get(
        it.brush, w / 2) + 2


def _seed(it):
    p = it.pts[0] if it.pts else QPointF()
    return int(p.x() * 131 + p.y() * 17 + len(it.pts) * 7) & 0xFFFFFFFF


def _calli_path(it):
    w = it.width
    ang = math.radians(-45)
    n = QPointF(math.cos(ang) * w * 1.1, math.sin(ang) * w * 1.1)
    out = QPainterPath()
    out.setFillRule(Qt.FillRule.WindingFill)
    for pl in polylines(it):
        if len(pl) == 1:
            pl = [pl[0], pl[0] + QPointF(0.01, 0)]
        for a, b in zip(pl, pl[1:]):
            out.addPolygon(QPolygonF([a + n, b + n, b - n, a - n]))
            out.closeSubpath()
    return out


def _spray_path(it):
    w = it.width
    R = w * 2.2 + 3
    dot = 0.45 + w * 0.05
    rnd = random.Random(_seed(it))
    out = QPainterPath()
    for pl in polylines(it):
        if len(pl) == 1:
            pl = [pl[0], pl[0] + QPointF(0.01, 0)]
        carry = 0.0
        step = max(1.0, R * 0.45)
        for a, b in zip(pl, pl[1:]):
            d = math.hypot(b.x() - a.x(), b.y() - a.y())
            t = carry
            while t <= d:
                k = t / d if d > 1e-9 else 0
                c = QPointF(a.x() + (b.x() - a.x()) * k, a.y() + (b.y() - a.y()) * k)
                for _ in range(int(R * 0.8) + 4):
                    rr = R * math.sqrt(rnd.random())
                    th = rnd.random() * math.tau
                    out.addEllipse(QPointF(c.x() + rr * math.cos(th), c.y() + rr * math.sin(th)), dot, dot)
                t += step
            carry = t - d
    return out


def cache(it):
    """Ağır hesaplananlar (kaligrafi kalıbı, sprey noktaları) çizgi değişene kadar saklanır."""
    c = getattr(it, "_bc", None)
    if c is not None and c[0] == (it.brush, it.width, it.path().elementCount()):
        return c[1]
    if it.brush == "calli":
        v = _calli_path(it)
    elif it.brush == "spray":
        v = _spray_path(it)
    elif it.brush == "water":
        st = QPainterPathStroker()
        st.setWidth(it.width * 2.2)
        st.setCapStyle(Qt.PenCapStyle.RoundCap)
        st.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        v = st.createStroke(it.path()).simplified()
    else:
        v = None
    it._bc = ((it.brush, it.width, it.path().elementCount()), v)
    return v


def paint(p, it, color: QColor, dash_pattern=None):
    b = it.brush
    w = it.width
    path = it.path()
    p.save()
    p.setRenderHint(p.RenderHint.Antialiasing)
    if b == "calli":
        p.fillPath(cache(it), color)
        p.setPen(QPen(color, max(0.8, w * 0.18), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                      Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
    elif b == "spray":
        c = QColor(color)
        c.setAlpha(int(175 * color.alphaF()))
        p.fillPath(cache(it), c)
    elif b == "water":
        area = cache(it)
        c = QColor(color)
        c.setAlpha(int(70 * color.alphaF()))
        p.fillPath(area, c)
        e = QColor(color)
        e.setAlpha(int(120 * color.alphaF()))
        p.setPen(QPen(e, 0.7 + w * 0.12))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(area)
    else:
        if b == "marker":
            c = QColor(color)
            c.setAlpha(int(205 * color.alphaF()))
            pen = QPen(c, w * 1.7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.SquareCap, Qt.PenJoinStyle.BevelJoin)
        elif b == "pencil":
            pen = QPen(QBrush(_texture(color, "pencil")), max(1.0, w * 0.9), Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        else:   # crayon
            pen = QPen(QBrush(_texture(color, "crayon")), w * 1.9, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        if dash_pattern:
            pen.setDashPattern(dash_pattern)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
    p.restore()
