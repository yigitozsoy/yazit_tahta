"""Ortak araç durumu: seçili araç, renk, kalınlık.
Ana pencere ve "ekrana çiz" katmanı aynı durumu paylaşır (birinde kalemi seçince diğerinde de seçili)."""
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtGui import QKeySequence

from .config import prefs
from . import engshapes

BASIC_SHAPES = ("line", "arrow", "rect", "ellipse")
ENG_SHAPES = engshapes.KINDS          # mühendislik şekilleri (prefs eng_shapes açıkken menüde)
TOOLS = ("select", "pen", "hl", "laser", "eraser", "line", "arrow", "rect", "ellipse", "text", "picker",
         "fill") + ENG_SHAPES
# kalem türleri (Paint'teki fırçalar gibi): normal kalem, kaligrafi kalemi, keçeli, kurşun kalem, pastel boya,
# sprey, suluboya
BRUSHES = ("pen", "calli", "marker", "pencil", "crayon", "spray", "water")
ERASER_MODES = ("part", "object")       # parça: yalnızca geçtiği yeri siler · nesne: dokunduğu nesneyi siler
SHAPES = BASIC_SHAPES + ENG_SHAPES
DRAW_TOOLS = ("pen", "hl") + SHAPES
# Ana renkler: beyaz, siyah, mavi, kırmızı, yeşil, sarı, turuncu (Shift+1 … 7).
# Eski notlardaki "auto" renk yine temaya göre (koyuda beyaz, açıkta siyah) çizilir.
COLORS = ["#ffffff", "#000000", "#3ea6ff", "#ff453a", "#30d158", "#ffd60a", "#ff9f0a"]
COLOR_NAMES = ["col_white", "col_black", "col_blue", "col_red", "col_green", "col_yellow", "col_orange"]
SIZES = (1.5, 2.5, 5.0)
DEFAULT_WIDTH = 2.5


def default_color():
    """Varsayılan kalem rengi: koyu temada beyaz, açık temada siyah."""
    try:
        from .theme import is_dark
        return "#ffffff" if is_dark() else "#000000"
    except Exception:
        return "#ffffff"
ICON = {"select": "select", "pen": "pen", "hl": "highlighter", "laser": "laser", "eraser": "eraser",
        "line": "line", "arrow": "arrow", "rect": "rect", "ellipse": "ellipse", "text": "text",
        "picker": "colorize", "fill": "bucket", **{k: "eng_" + k for k in ENG_SHAPES}}
BRUSH_ICON = {"pen": "pen", "calli": "br_calli", "marker": "br_marker", "pencil": "br_pencil", "crayon": "br_crayon",
              "spray": "br_spray", "water": "br_water"}
# Varsayılan araç tuşları rakamlarda (harfler boşta: tahtada harfe basınca imlecin yerine hemen yazı başlar).
# Seçenekler > Tahta kısayolları'ndan değiştirilebilir (prefs "tool_keys").
KEY = {"pen": "1", "hl": "2", "arrow": "3", "line": "4", "rect": "5", "ellipse": "6", "text": "7",
       "laser": "8", "eraser": "9", "select": "0"}
TOOL_ORDER = ("pen", "hl", "arrow", "line", "rect", "ellipse", "text", "laser", "eraser", "select")


def tool_keys():
    """Geçerli araç → tuş eşlemesi (kullanıcının değiştirdikleri + varsayılanlar)."""
    keys = dict(KEY)
    user = prefs.get("tool_keys", {}) or {}
    if isinstance(user, dict):
        for tool, k in user.items():
            if tool in keys:
                keys[tool] = str(k or "")
    return keys


def tool_key(tool):
    return tool_keys().get(tool, "")


def key_name(e):
    """Tuş olayının adı: rakamlar düzenden bağımsız ("1"), diğerleri Qt adıyla ("Q", "F3", "Ö")."""
    vk = e.nativeVirtualKey()
    if 0x30 <= vk <= 0x39:
        return str(vk - 0x30)
    if 0x60 <= vk <= 0x69:
        return str(vk - 0x60)
    k = e.key()
    if vk == 0 and Qt.Key.Key_0 <= k <= Qt.Key.Key_9:
        return str(k - Qt.Key.Key_0)
    if k in (0, Qt.Key.Key_unknown, Qt.Key.Key_Shift, Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Meta):
        return ""
    txt = e.text()
    if txt and txt.isprintable() and not txt.isspace() and len(txt) == 1:
        return txt.upper() if txt.isalpha() else txt
    return QKeySequence(k).toString()


def tool_for_key(name):
    if not name:
        return None
    for tool, k in tool_keys().items():
        if k and k == name:
            return tool
    return None


def set_tool_key(tool, name):
    """Tuşu araca ata; aynı tuş başka araçtaysa oradan kaldırılır."""
    keys = tool_keys()
    for other, k in keys.items():
        if other != tool and name and k == name:
            keys[other] = ""
    keys[tool] = name
    prefs.set("tool_keys", keys)
    state.keys_changed.emit()


def reset_tool_keys():
    prefs.set("tool_keys", {})
    state.keys_changed.emit()


def eng_enabled():
    return bool(prefs.get("eng_shapes", False))


def add_eng_menu(menu, icon_fn):
    """Şekil menüsüne "Mühendislik" alt menüsü (kapalıysa hiçbir şey eklemez). icon_fn(ad) → QIcon."""
    if not eng_enabled():
        return None
    from .i18n import t
    sub = menu.addMenu(icon_fn("eng_gear"), t("eng_shapes"))
    for gname, kinds in engshapes.GROUPS:          # her grup ayrı alt menü (liste uzun)
        gm = sub.addMenu(icon_fn(ICON[kinds[0]]), t(gname) + ("	✓" if state.tool in kinds else ""))
        for k in kinds:
            if k == "airfoil":
                fill_naca_menu(gm.addMenu(icon_fn(ICON[k]), t("tool_airfoil")),
                               state.naca if state.tool == "airfoil" else None, state.set_naca)
                continue
            a = gm.addAction(icon_fn(ICON[k]), t("tool_" + k) + ("	✓" if state.tool == k else ""))
            a.triggered.connect(lambda _=False, x=k: state.set_tool(x))
    return sub


def fill_naca_menu(m, current, on_pick):
    """NACA profilleri: "NACA 2412 — %2 kamburluk, %12 kalınlık"; seçili olan ✓."""
    from .i18n import t
    for code in engshapes.NACA:
        cam, th = engshapes.naca_info(code)
        if cam is None:
            desc = t("naca_5", t=th)
        elif cam == 0:
            desc = t("naca_sym", t=th)
        else:
            desc = t("naca_cam", c=cam, t=th)
        a = m.addAction(f"NACA {code} — {desc}" + ("\t✓" if code == current else ""))
        a.triggered.connect(lambda _=False, x=code: on_pick(x))


class ToolState(QObject):
    changed = pyqtSignal()
    keys_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        t = prefs.get("tool", "pen")
        self.tool = t if t in TOOLS else "pen"
        c = str(prefs.get("color", "auto") or "auto")
        self.color = default_color() if c == "auto" else c
        try:
            self.width = float(prefs.get("width", DEFAULT_WIDTH))
        except (TypeError, ValueError):
            self.width = DEFAULT_WIDTH
        ls = prefs.get("last_shape", "arrow")
        self.last_shape = ls if ls in SHAPES else "arrow"
        if not eng_enabled():
            if self.last_shape in ENG_SHAPES:
                self.last_shape = "arrow"
            if self.tool in ENG_SHAPES:
                self.tool = "arrow"
        self.custom_color = str(prefs.get("custom_color", "#b0b0b0"))
        d = prefs.get("dash", "solid")
        self.dash = d if d in ("solid", "dash", "dot", "dashdot") else "solid"
        b = prefs.get("brush", "pen")
        self.brush = b if b in BRUSHES else "pen"
        m = prefs.get("eraser_mode", "part")
        self.eraser_mode = m if m in ERASER_MODES else "part"
        try:
            self.eraser_size = max(4.0, min(160.0, float(prefs.get("eraser_size", 22))))
        except (TypeError, ValueError):
            self.eraser_size = 22.0
        self.prev_tool = "pen"
        n = str(prefs.get("naca", engshapes.NACA_DEFAULT))
        self.naca = n if engshapes.naca_ok(n) else engshapes.NACA_DEFAULT

    def set_eng(self, on):
        """Mühendislik şekillerini aç / kapat (Seçenekler). Kapanınca seçili mühendislik aracı oka döner."""
        prefs.set("eng_shapes", bool(on))
        if not on:
            if self.last_shape in ENG_SHAPES:
                self.last_shape = "arrow"
                prefs.set("last_shape", "arrow")
            if self.tool in ENG_SHAPES:
                self.tool = "arrow"
                prefs.set("tool", "arrow")
        self.changed.emit()

    def set_naca(self, code):
        """Kanat profili seçilir ve kanat profili aracı açılır."""
        if not engshapes.naca_ok(code):
            return
        self.naca = code
        prefs.set("naca", code)
        self.set_tool("airfoil")

    def set_brush(self, b):
        if b not in BRUSHES:
            return
        self.brush = b
        prefs.set("brush", b)
        if self.tool != "pen":
            self.prev_tool = self.tool
            self.tool = "pen"
            prefs.set("tool", "pen")
        self.changed.emit()

    def set_eraser_mode(self, m):
        if m not in ERASER_MODES:
            return
        self.eraser_mode = m
        prefs.set("eraser_mode", m)
        if self.tool != "eraser":
            self.prev_tool = self.tool
            self.tool = "eraser"
            prefs.set("tool", "eraser")
        self.changed.emit()

    def set_eraser_size(self, v):
        v = max(4.0, min(160.0, round(float(v))))
        if abs(v - self.eraser_size) < 1e-6:
            return
        self.eraser_size = v
        prefs.set("eraser_size", v)
        self.changed.emit()

    def set_dash(self, d):
        if d not in ("solid", "dash", "dot", "dashdot") or d == self.dash:
            return
        self.dash = d
        prefs.set("dash", d)
        if self.tool not in ("pen", "hl") and self.tool not in SHAPES:
            self.tool = "pen"
            prefs.set("tool", "pen")
        self.changed.emit()

    def set_tool(self, t):
        if t not in TOOLS:
            return
        if t != self.tool:
            self.prev_tool = self.tool
        self.tool = t
        if t in SHAPES:
            self.last_shape = t
            prefs.set("last_shape", t)
        prefs.set("tool", t)
        self.changed.emit()

    def set_color(self, c):
        self.color = c
        if c not in COLORS:
            self.custom_color = c
            prefs.set("custom_color", c)
        prefs.set("color", c)
        # Renk seçmek, silgi/seçim/lazer açıksa kaleme döndürür (Paint'teki gibi)
        if self.tool in ("eraser", "select", "laser"):
            self.tool = "pen"
            prefs.set("tool", "pen")
        self.changed.emit()

    def set_width(self, w):
        w = max(0.5, min(60.0, round(float(w), 1)))
        if abs(w - self.width) < 1e-6:
            return
        self.width = w
        prefs.set("width", w)
        self.changed.emit()

    def nudge(self, d):
        if self.tool == "eraser":
            e = self.eraser_size
            self.set_eraser_size(e + d * (2 if e < 20 else 4 if e < 60 else 8))
            return
        w = self.width
        step = 0.5 if w < 3 else 1 if w < 6 else 2 if w < 16 else 4
        self.set_width(w + d * step)

    def width_for(self, tool):
        return self.width * 4 + 6 if tool == "hl" else self.width

    def text_px(self):
        return round(19 + self.width * 1.75)     # yazı boyutu kalınlıkla biraz büyür (2,5 → 23 px)


state = ToolState()
