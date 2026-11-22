"""Küçük LaTeX dizgi motoru (formül öğesi için; matplotlib / TeX gerekmez).
Word'ün denklem düzenleyicisi gibi Cambria Math ile çizer: harfler matematik italik (Unicode 𝑥), sayılar dik.

Desteklenen: x^2 x_i x_i^2 f' · \\frac \\dfrac \\sqrt[n]{} · \\sum \\prod \\int \\iint \\oint \\lim (sınırlar)
· \\left( \\right) ve kendiliğinden büyüyen ( ) [ ] \\{ \\} · \\vec \\hat \\bar \\overline \\underline \\dot
\\ddot \\tilde · \\text{} \\mathrm{} \\mathbf{} \\mathbb{} \\operatorname{} · \\sin \\cos … · Yunan harfleri,
işlemler, oklar · \\begin{pmatrix|bmatrix|vmatrix|matrix|cases|aligned} · üst düzeyde \\\\ (satır) ve & (hizalama)
· \\, \\; \\quad boşluklar · Word kolaylıkları: <= >= != -> => ~= * (·), "3,14" ondalık virgülü boşluksuz.

Yazarken hiçbir girişte hata vermez: eksik argüman boş kutu (düzenlerken kesik kare), bilinmeyen komut düz yazı.
Kullanım: layout(kaynak, boyut, düzenleme=False) → Box (w, a, d; draw(p, x, taban_y, renk))."""
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QFont, QFontMetricsF, QPainterPath, QPen, QColor, QPainter, QPixmap, QGuiApplication

MATH_FAMILIES = ["Cambria Math", "STIX Two Math", "Segoe UI Symbol", "Segoe UI"]
TEXT_FAMILIES = ["Cambria", "Times New Roman", "Segoe UI"]

# ------------------------------------------------------------------ semboller
GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ϵ", "varepsilon": "ε", "zeta": "ζ",
    "eta": "η", "theta": "θ", "vartheta": "ϑ", "iota": "ι", "kappa": "κ", "lambda": "λ", "mu": "μ", "nu": "ν",
    "xi": "ξ", "pi": "π", "varpi": "ϖ", "rho": "ρ", "varrho": "ϱ", "sigma": "σ", "varsigma": "ς", "tau": "τ",
    "upsilon": "υ", "phi": "ϕ", "varphi": "φ", "chi": "χ", "psi": "ψ", "omega": "ω",
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ", "Xi": "Ξ", "Pi": "Π", "Sigma": "Σ",
    "Upsilon": "Υ", "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
}
BIN = {"pm": "±", "mp": "∓", "times": "×", "div": "÷", "cdot": "·", "ast": "∗", "star": "⋆", "circ": "∘",
       "bullet": "∙", "oplus": "⊕", "otimes": "⊗", "cup": "∪", "cap": "∩", "setminus": "∖", "wedge": "∧",
       "vee": "∨", "land": "∧", "lor": "∨"}
REL = {"leq": "≤", "le": "≤", "geq": "≥", "ge": "≥", "neq": "≠", "ne": "≠", "approx": "≈", "equiv": "≡",
       "sim": "∼", "simeq": "≃", "cong": "≅", "propto": "∝", "ll": "≪", "gg": "≫", "in": "∈", "notin": "∉",
       "ni": "∋", "subset": "⊂", "supset": "⊃", "subseteq": "⊆", "supseteq": "⊇", "perp": "⊥",
       "parallel": "∥", "mid": "∣", "to": "→", "rightarrow": "→", "leftarrow": "←", "gets": "←",
       "leftrightarrow": "↔", "Rightarrow": "⇒", "Leftarrow": "⇐", "Leftrightarrow": "⇔", "implies": "⟹",
       "iff": "⟺", "mapsto": "↦", "uparrow": "↑", "downarrow": "↓", "longrightarrow": "⟶",
       "rightleftharpoons": "⇌", "coloneqq": "≔", "doteq": "≐", "triangleq": "≜"}
ORD = {"infty": "∞", "partial": "∂", "nabla": "∇", "forall": "∀", "exists": "∃", "nexists": "∄",
       "emptyset": "∅", "varnothing": "∅", "angle": "∠", "measuredangle": "∡", "degree": "°", "circ_": "°",
       "prime": "′", "hbar": "ℏ", "ell": "ℓ", "Re": "ℜ", "Im": "ℑ", "aleph": "ℵ", "therefore": "∴",
       "because": "∵", "ldots": "…", "cdots": "⋯", "vdots": "⋮", "ddots": "⋱", "dots": "…", "neg": "¬",
       "lnot": "¬", "top": "⊤", "bot": "⊥", "triangle": "△", "square": "□", "checkmark": "✓",
       "dagger": "†", "percent": "%", "%": "%", "#": "#", "&": "&", "$": "$", "_": "_",
       "Box": "□", "diameter": "⌀", "ohm": "Ω"}
BIGOP = {"sum": "∑", "prod": "∏", "coprod": "∐", "bigcup": "⋃", "bigcap": "⋂", "bigoplus": "⨁",
         "bigotimes": "⨂"}
INTEGRAL = {"int": "∫", "iint": "∬", "iiint": "∭", "oint": "∮", "oiint": "∯"}
FUNCS = ("sin", "cos", "tan", "cot", "sec", "csc", "arcsin", "arccos", "arctan", "sinh", "cosh", "tanh",
         "coth", "log", "ln", "lg", "exp", "det", "dim", "ker", "deg", "arg", "gcd", "sgn", "Tr", "tr", "rank",
         "mod", "max", "min", "sup", "inf", "lim", "limsup", "liminf", "Pr", "erf")
LIMFUNCS = ("lim", "max", "min", "sup", "inf", "limsup", "liminf", "det", "gcd", "Pr")
ACCENTS = ("vec", "hat", "widehat", "bar", "overline", "underline", "dot", "ddot", "tilde", "widetilde",
           "overrightarrow", "check", "breve", "acute", "grave")
DELIMS = {"(": "(", ")": ")", "[": "[", "]": "]", "\\{": "{", "\\}": "}", "|": "|", "\\|": "‖",
          "\\lbrace": "{", "\\rbrace": "}", "\\langle": "⟨", "\\rangle": "⟩", "\\lfloor": "⌊", "\\rfloor": "⌋",
          "\\lceil": "⌈", "\\rceil": "⌉", "\\vert": "|", "\\Vert": "‖", "\\lvert": "|", "\\rvert": "|",
          "\\lVert": "‖", "\\rVert": "‖", ".": ""}
SPACES = {",": 0.17, ":": 0.22, ">": 0.22, ";": 0.28, "!": -0.17, " ": 0.25, "quad": 1.0, "qquad": 2.0,
          "enspace": 0.5, "thinspace": 0.17, "medspace": 0.22, "thickspace": 0.28}
ENVS = {"matrix": ("", ""), "pmatrix": ("(", ")"), "bmatrix": ("[", "]"), "Bmatrix": ("{", "}"),
        "vmatrix": ("|", "|"), "Vmatrix": ("‖", "‖"), "smallmatrix": ("", ""), "cases": ("{", ""),
        "aligned": ("", ""), "align": ("", ""), "align*": ("", ""), "gathered": ("", ""), "array": ("", ""),
        "split": ("", "")}
# Word gibi: yazarken birleşen işaretler
COMBOS = (("<=>", "⇔", "rel"), ("<->", "↔", "rel"), ("<=", "≤", "rel"), (">=", "≥", "rel"),
          ("!=", "≠", "rel"), ("->", "→", "rel"), ("=>", "⇒", "rel"), ("~=", "≅", "rel"), ("+-", "±", "bin"),
          ("-+", "∓", "bin"), ("...", "…", "ord"), ("<<", "≪", "rel"), (">>", "≫", "rel"))
CHAR_CLASS = {"+": "bin", "-": "bin", "*": "bin", "/": "ord", "=": "rel", "<": "rel", ">": "rel", ":": "rel",
              ",": "punct", ";": "punct", "!": "ord", "?": "ord", ".": "ord"}
CHAR_MAP = {"-": "−", "*": "·", "'": "′"}
for _d in (BIN,):
    for _v in _d.values():
        CHAR_CLASS.setdefault(_v, "bin")
for _v in REL.values():
    CHAR_CLASS.setdefault(_v, "rel")


def _italic(ch):
    """Latin / küçük Yunan harfi → Unicode matematik italik."""
    o = ord(ch)
    if ch == "h":
        return "ℎ"
    if 0x61 <= o <= 0x7A:
        return chr(0x1D44E + o - 0x61)
    if 0x41 <= o <= 0x5A:
        return chr(0x1D434 + o - 0x41)
    if 0x3B1 <= o <= 0x3C9:
        return chr(0x1D6FC + o - 0x3B1)
    return {"ϵ": chr(0x1D716), "ϑ": chr(0x1D717), "ϕ": chr(0x1D719), "ϱ": chr(0x1D71A),
            "ϖ": chr(0x1D71B)}.get(ch, ch)


def _bold(ch):
    o = ord(ch)
    if 0x61 <= o <= 0x7A:
        return chr(0x1D41A + o - 0x61)
    if 0x41 <= o <= 0x5A:
        return chr(0x1D400 + o - 0x41)
    if 0x30 <= o <= 0x39:
        return chr(0x1D7CE + o - 0x30)
    if 0x3B1 <= o <= 0x3C9:
        return chr(0x1D6C2 + o - 0x3B1)
    if 0x391 <= o <= 0x3A9:
        return chr(0x1D6A8 + o - 0x391)
    return ch


_BB_SPECIAL = {"C": "ℂ", "H": "ℍ", "N": "ℕ", "P": "ℙ", "Q": "ℚ", "R": "ℝ", "Z": "ℤ"}


def _bb(ch):
    if ch in _BB_SPECIAL:
        return _BB_SPECIAL[ch]
    o = ord(ch)
    if 0x41 <= o <= 0x5A:
        return chr(0x1D538 + o - 0x41)
    if 0x61 <= o <= 0x7A:
        return chr(0x1D552 + o - 0x61)
    if 0x30 <= o <= 0x39:
        return chr(0x1D7D8 + o - 0x30)
    return ch


def _is_letter(ch):
    return ch.isalpha() and (ch.isascii() or 0x370 <= ord(ch) <= 0x3FF)


# ------------------------------------------------------------------ ayrıştırma (düğümler: tuple)
# ("sym", metin, sınıf, yazı)   yazı: "it" | "rm" | "bf" | "bb" | "text"
# ("group", [düğüm])  ("scripts", taban, alt, üst)  ("frac", pay, payda)  ("sqrt", gövde, derece)
# ("delim", sol, [düğüm], sağ, otomatik)  ("op", metin, sınıf, sınırlı)  ("acc", tür, gövde)
# ("space", em)  ("env", ad, [[hücre düğümleri]])  ("empty",)  ("bad", metin)

class _Parser:
    def __init__(self, src):
        self.s = src
        self.i = 0

    def peek(self, k=0):
        j = self.i + k
        return self.s[j] if j < len(self.s) else ""

    def skip_ws(self):
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def read_cmd(self):
        """'\\' konumunda: komut adı (harfler) ya da tek işaret."""
        self.i += 1
        if self.i >= len(self.s):
            return ""
        if self.s[self.i].isalpha():
            j = self.i
            while j < len(self.s) and self.s[j].isalpha():
                j += 1
            name = self.s[self.i:j]
            self.i = j
            if name == "align" and self.peek() == "*":
                self.i += 1
                name = "align*"
            return name
        c = self.s[self.i]
        self.i += 1
        return c

    def raw_group(self):
        """{ … } içeriğini olduğu gibi (iç içe süslü parantezlerle) okur."""
        self.skip_ws()
        if self.peek() != "{":
            if self.i < len(self.s) and self.peek() not in "\\}":
                c = self.s[self.i]
                self.i += 1
                return c
            return ""
        self.i += 1
        depth, j = 1, self.i
        while j < len(self.s):
            if self.s[j] == "\\":
                j += 2
                continue
            if self.s[j] == "{":
                depth += 1
            elif self.s[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out = self.s[self.i:j]
        self.i = min(j + 1, len(self.s))
        return out

    # --- listeler
    def parse_list(self, font="it", stop=()):
        """stop: "}" , ")" , "]" , "right", "end", "&", "\\\\" kümesinden durduranlar."""
        out = []
        while self.i < len(self.s):
            self.skip_ws()
            if self.i >= len(self.s):
                break
            c = self.peek()
            if c == "}" and "}" in stop:
                break
            if c in ")]" and c in stop:
                break
            if c == "&" and "&" in stop:
                break
            if c == "\\":
                nxt = self.s[self.i + 1:self.i + 6]
                if nxt.startswith("\\") and "\\\\" in stop:
                    break
                if nxt.startswith("right") and "right" in stop and not self.s[self.i + 6:self.i + 7].isalpha():
                    break
                if nxt.startswith("end") and "end" in stop and not self.s[self.i + 4:self.i + 5].isalpha():
                    break
            if c in "^_" or c == "'":
                base = out.pop() if out and out[-1][0] not in ("space",) else ("empty",)
                out.append(self.scripts(base, font))
                continue
            node = self.atom(font, stop)
            if node is None:
                continue
            # \sum, \int, \lim: arkasından gelen ^ _ sınır olur
            self.skip_ws()
            if self.peek() in "^_'" and self.i < len(self.s):
                node = self.scripts(node, font)
            out.append(node)
        return out

    def scripts(self, base, font):
        sub = sup = None
        primes = ""
        while True:
            self.skip_ws()
            c = self.peek()
            if c == "'":
                primes += "′"
                self.i += 1
            elif c == "^" and sup is None:
                self.i += 1
                sup = self.arg(font)
            elif c == "_" and sub is None:
                self.i += 1
                sub = self.arg(font)
            else:
                break
        if primes:          # ′ yazı tipinde zaten yukarıda: üst indis yapılmaz, tabana eklenir
            base = ("group", [base, ("sym", primes, "ord", "rm")])
            if sub is None and sup is None:
                return base
        if base[0] == "scripts" and base[2] is None and base[3] is not None and sub is not None and sup is None:
            return ("scripts", base[1], sub, base[3])
        return ("scripts", base, sub, sup)

    def arg(self, font):
        """Tek argüman: { … } ya da tek simge (yoksa boş kutu)."""
        self.skip_ws()
        c = self.peek()
        if not c or c in "}&^_" or (c == "\\" and self.s[self.i + 1:self.i + 2] == "\\"):
            return ("empty",)
        if c == "{":
            self.i += 1
            lst = self.parse_list(font, stop=("}",))
            if self.peek() == "}":
                self.i += 1
            return ("group", lst) if lst else ("empty",)
        if c == "\\":
            node = self.atom(font, ())
            return node if node is not None else ("empty",)
        self.i += 1
        return self.char_node(c, font)

    def opt_arg(self, font):
        self.skip_ws()
        if self.peek() != "[":
            return None
        self.i += 1
        lst = self.parse_list(font, stop=("]",))
        if self.peek() == "]":
            self.i += 1
        return ("group", lst)

    def char_node(self, c, font):
        if font == "text":
            return ("sym", c, "ord", "text")
        if _is_letter(c):
            if font == "bf":
                return ("sym", _bold(c), "ord", "rm")
            if font == "bb":
                return ("sym", _bb(c), "ord", "rm")
            if font == "rm" or (0x391 <= ord(c) <= 0x3A9):
                return ("sym", c, "ord", "rm")
            return ("sym", _italic(c), "ord", "rm")
        if c.isdigit():
            return ("sym", _bold(c) if font == "bf" else (_bb(c) if font == "bb" else c), "ord", "rm")
        return ("sym", CHAR_MAP.get(c, c), CHAR_CLASS.get(c, "ord"), "rm")

    def read_delim(self):
        self.skip_ws()
        c = self.peek()
        if c == "\\":
            j = self.i
            name = self.read_cmd()
            key = "\\" + name
            if key in DELIMS:
                return DELIMS[key]
            self.i = j + 1
            return ""
        if c:
            self.i += 1
            return DELIMS.get(c, c)
        return ""

    def atom(self, font, stop):
        c = self.peek()
        if c == "{":
            self.i += 1
            lst = self.parse_list(font, stop=("}",))
            if self.peek() == "}":
                self.i += 1
            return ("group", lst) if lst else ("empty",)
        if c == "}":            # fazladan kapanan: yok say
            self.i += 1
            return None
        if c == "&" or (c == "\\" and self.peek(1) == "\\"):   # beklenmeyen yerde: atla
            self.i += 2 if c == "\\" else 1
            return None
        if c == "\\":
            return self.command(font)
        # Word kolaylıkları: <= >= != -> …
        if font != "text":
            for k, v, cls in COMBOS:
                if self.s.startswith(k, self.i):
                    self.i += len(k)
                    return ("sym", v, cls, "rm")
        self.i += 1
        if c in "([" and font != "text":
            close = ")" if c == "(" else "]"
            save = self.i
            inner = self.parse_list(font, stop=(close, "}", "&", "\\\\", "right", "end"))
            if self.peek() == close:
                self.i += 1
                return ("delim", c, inner, close, True)
            self.i = save           # eşi yok: düz karakter
            return ("sym", c, "open", "rm")
        if c in ")]":
            return ("sym", c, "close", "rm")
        if c == "," and font != "text":    # 3,14: ondalık virgülü (boşluksuz)
            prev = self.s[self.i - 2:self.i - 1]
            if prev.isdigit() and self.peek().isdigit():
                return ("sym", ",", "ord", "rm")
        if c == "." and font != "text":    # m.a → m·a (harfler arasında nokta çarpım; 2.5 ondalık kalır)
            prev, nxt = self.s[self.i - 2:self.i - 1], self.peek()
            if (prev.isalpha() or prev in ")}") and (nxt.isalpha() or nxt == "\\"):
                return ("sym", "·", "bin", "rm")
        return self.char_node(c, font)

    def command(self, font):
        name = self.read_cmd()
        if not name:
            return ("sym", "\\", "ord", "rm")
        if name in SPACES:
            return ("space", SPACES[name])
        if name in ("frac", "dfrac", "tfrac", "cfrac"):
            return ("frac", self.arg(font), self.arg(font))
        if name == "binom":
            return ("delim", "(", [("frac", self.arg(font), self.arg(font), "nobar")], ")", True)
        if name == "sqrt":
            idx = self.opt_arg(font)
            return ("sqrt", self.arg(font), idx)
        if name == "left":
            l_ = self.read_delim()
            inner = self.parse_list(font, stop=("right", "}", "end", "&", "\\\\"))
            r_ = ""
            if self.s.startswith("\\right", self.i):
                self.i += 6
                r_ = self.read_delim()
            return ("delim", l_, inner, r_, True)
        if name in ("right", "big", "Big", "bigg", "Bigg", "bigl", "bigr", "Bigl", "Bigr"):
            d = self.read_delim()
            return ("sym", d, "ord", "rm") if d else None
        if name in ACCENTS:
            return ("acc", name, self.arg(font))
        if name in ("text", "textrm", "mbox", "textnormal"):
            return ("group", [("sym", ch, "ord", "text") for ch in self.raw_group()]) or ("empty",)
        if name in ("textit",):
            return ("group", [("sym", ch, "ord", "textit") for ch in self.raw_group()])
        if name in ("textbf",):
            return ("group", [("sym", ch, "ord", "textbf") for ch in self.raw_group()])
        if name in ("mathrm", "rm", "mathsf", "mathtt"):
            return self.arg("rm")
        if name in ("mathbf", "boldsymbol", "bm", "bf"):
            return self.arg("bf")
        if name in ("mathbb",):
            return self.arg("bb")
        if name in ("mathit", "mathcal", "mathscr"):
            return self.arg("it")
        if name == "operatorname":
            return ("op", self.raw_group(), "op", False)
        if name in FUNCS:
            return ("op", name, "op", name in LIMFUNCS)
        if name in BIGOP:
            return ("op", BIGOP[name], "big", True)
        if name in INTEGRAL:
            return ("op", INTEGRAL[name], "int", False)
        if name == "begin":
            return self.env(self.raw_group())
        if name == "end":
            self.raw_group()
            return None
        if name in GREEK:
            ch = GREEK[name]
            return ("sym", ch if name[0].isupper() or font == "rm" else (_bold(ch) if font == "bf" else _italic(ch)),
                    "ord", "rm")
        if name in BIN:
            return ("sym", BIN[name], "bin", "rm")
        if name in REL:
            return ("sym", REL[name], "rel", "rm")
        if name in ORD:
            return ("sym", ORD[name], "ord", "rm")
        if name in ("{", "}", "|"):
            return ("sym", {"{": "{", "}": "}", "|": "‖"}[name], "open" if name == "{" else "close", "rm")
        if name in ("langle", "rangle", "lfloor", "rfloor", "lceil", "rceil", "lbrace", "rbrace"):
            return ("sym", DELIMS["\\" + name], "open" if name[0] == "l" else "close", "rm")
        if name in ("displaystyle", "textstyle", "limits", "nolimits", "nonumber", "notag", "label"):
            if name == "label":
                self.raw_group()
            return None
        if name == "not":
            nxt = self.atom(font, ())
            if nxt and nxt[0] == "sym":
                return ("sym", nxt[1] + "̸", nxt[2], nxt[3])
            return nxt
        if name == "overset" or name == "stackrel":
            top = self.arg(font)
            base = self.arg(font)
            return ("op", base, "over", top)
        if name == "underset":
            bot = self.arg(font)
            base = self.arg(font)
            return ("op", base, "under", bot)
        return ("bad", "\\" + name)

    def env(self, name):
        if name == "array":
            self.raw_group()          # sütun tanımı (yok sayılır)
        rows = self.rows(stop_end=True)
        if self.s.startswith("\\end", self.i):
            self.i += 4
            self.raw_group()
        return ("env", name if name in ENVS else "matrix", rows)

    def rows(self, stop_end=False):
        rows, row = [], []
        stop = ("&", "\\\\", "end", "right") if stop_end else ("&", "\\\\")
        while True:
            cell = self.parse_list("it", stop=stop + (("}",) if stop_end else ()))
            row.append(cell)
            if self.peek() == "&":
                self.i += 1
                continue
            if self.s.startswith("\\\\", self.i):
                self.i += 2
                self.opt_arg("it") if self.peek() == "[" else None
                rows.append(row)
                row = []
                continue
            if not stop_end and self.peek() == "}":     # üst düzeyde fazla '}'
                self.i += 1
                continue
            break
        rows.append(row)
        while len(rows) > 1 and rows[-1] == [[]]:
            rows.pop()
        return rows


def parse(src):
    p = _Parser(src or "")
    rows = p.rows(stop_end=False)
    if len(rows) == 1 and len(rows[0]) == 1:
        return ("group", rows[0][0])
    return ("env", "top", rows)


# ------------------------------------------------------------------ kutular
class Box:
    """w genişlik, a taban üstü, d taban altı. parts: (kutu, dx, dy) · lines: (x1, y1, x2, y2, kalınlık)
    · paths: (QPainterPath, kalınlık, dolu)."""
    __slots__ = ("w", "a", "d", "parts", "lines", "paths", "glyph", "font", "alpha", "dash", "italic")

    def __init__(self, w=0.0, a=0.0, d=0.0):
        self.w, self.a, self.d = w, a, d
        self.parts, self.lines, self.paths = [], [], []
        self.glyph = None
        self.font = None
        self.alpha = 255
        self.dash = False
        self.italic = False

    def draw(self, p, x, y, color):
        if self.glyph is not None:
            c = QColor(color)
            if self.alpha < 255:
                c.setAlpha(self.alpha)
            p.setFont(self.font)
            p.setPen(c)
            p.drawText(QPointF(x, y), self.glyph)
        if self.lines or self.paths:
            c = QColor(color)
            if self.alpha < 255:
                c.setAlpha(self.alpha)
            for (x1, y1, x2, y2, t) in self.lines:
                pen = QPen(c, t, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap)
                if self.dash:
                    pen.setStyle(Qt.PenStyle.DashLine)
                p.setPen(pen)
                p.drawLine(QPointF(x + x1, y + y1), QPointF(x + x2, y + y2))
            for path, t, filled in self.paths:
                pp = path.translated(x, y)
                if filled:
                    p.fillPath(pp, c)
                else:
                    pen = QPen(c, t, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
                    if self.dash:
                        pen.setStyle(Qt.PenStyle.DashLine)
                    p.setPen(pen)
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawPath(pp)
        for b, dx, dy in self.parts:
            b.draw(p, x + dx, y + dy, color)


_font_cache = {}


def _font(px, kind="math"):
    key = (round(px * 4) / 4, kind)
    f = _font_cache.get(key)
    if f is None:
        f = QFont()
        f.setFamilies(TEXT_FAMILIES if kind.startswith("text") else MATH_FAMILIES)
        f.setPixelSize(max(1, int(round(px))))
        if kind == "textit":
            f.setItalic(True)
        if kind == "textbf":
            f.setBold(True)
        f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        fm = QFontMetricsF(f)
        _font_cache[key] = f = (f, fm)
    return f


def glyph(text, size, kind="math", alpha=255):
    f, fm = _font(size, kind)
    b = Box()
    b.glyph, b.font, b.alpha = text, f, alpha
    b.w = fm.horizontalAdvance(text)
    if text.strip():
        r = fm.tightBoundingRect(text)
        b.a = max(-r.top(), 0.0)
        b.d = max(r.bottom(), 0.0)
        b.w = max(b.w, r.right())
    else:
        b.a, b.d = size * 0.5, 0.0
    b.italic = kind == "math" and len(text) == 1 and (0x1D434 <= ord(text) <= 0x1D71B or text == "ℎ")
    return b


def hbox(items):
    """[(kutu, dx_önce)] yan yana."""
    b = Box()
    x = 0.0
    for bx, gap in items:
        x += gap
        b.parts.append((bx, x, 0.0))
        x += bx.w
        b.a = max(b.a, bx.a)
        b.d = max(b.d, bx.d)
    b.w = x
    return b


def placeholder(size, edit):
    b = Box(size * 0.55, size * 0.68, size * 0.04)
    if edit:
        b.lines = [(0, -b.a, b.w, -b.a, 1.0), (b.w, -b.a, b.w, 0, 1.0), (b.w, 0, 0, 0, 1.0), (0, 0, 0, -b.a, 1.0)]
        b.dash = True
        b.alpha = 140
    return b


SPACE_TABLE = {   # (önceki, sonraki) → em
    ("ord", "op"): 0.17, ("op", "ord"): 0.17, ("close", "op"): 0.17, ("op", "op"): 0.17,
    ("ord", "bin"): 0.22, ("bin", "ord"): 0.22, ("close", "bin"): 0.22, ("bin", "open"): 0.22, ("bin", "op"): 0.22,
    ("ord", "rel"): 0.28, ("rel", "ord"): 0.28, ("close", "rel"): 0.28, ("rel", "open"): 0.28, ("rel", "op"): 0.28,
    ("op", "rel"): 0.28, ("rel", "bin"): 0.28, ("punct", "ord"): 0.17, ("punct", "open"): 0.17,
    ("punct", "op"): 0.17, ("punct", "rel"): 0.17, ("close", "ord"): 0.0, ("ord", "open"): 0.0,
    ("op", "open"): 0.0, ("bin", "bin"): 0.0,
}


class Ctx:
    __slots__ = ("size", "disp", "base", "edit")

    def __init__(self, size, disp, base, edit):
        self.size, self.disp, self.base, self.edit = size, disp, base, edit

    def script(self):
        return Ctx(max(self.size * 0.7, self.base * 0.48), False, self.base, self.edit)

    def frac(self):
        if self.disp:
            return Ctx(self.size, False, self.base, self.edit)
        return Ctx(max(self.size * 0.75, self.base * 0.48), False, self.base, self.edit)

    def inner(self):
        return Ctx(self.size, False, self.base, self.edit)

    def axis(self):
        return self.size * 0.25

    def rule(self):
        return max(0.7, self.size * 0.048)


def _cls(node):
    k = node[0]
    if k == "sym":
        return node[2]
    if k == "op":
        return "op" if node[2] in ("op", "big", "int") else "ord"
    if k == "scripts":
        return _cls(node[1]) if node[1][0] in ("op",) else ("ord" if _cls(node[1]) not in ("rel", "bin") else
                                                            _cls(node[1]))
    if k == "delim":
        return "inner"
    if k == "space":
        return "space"
    return "ord"


def layout_list(nodes, ctx):
    items = []
    prev = None
    for i, n in enumerate(nodes):
        if n[0] == "space":
            items.append((Box(n[1] * ctx.size, 0, 0), 0.0))
            continue
        c = _cls(n)
        if c == "bin" and (prev in (None, "bin", "rel", "open", "punct", "op") or i == len(nodes) - 1):
            c = "ord"              # tekli eksi / sondaki işaret
        b = layout(n, ctx)
        gap = 0.0
        if prev is not None:
            pc, cc = ("ord" if prev == "inner" else prev), ("ord" if c == "inner" else c)
            if ctx.size >= ctx.base * 0.9 or cc not in ("bin", "rel") and pc not in ("bin", "rel"):
                gap = SPACE_TABLE.get((pc, cc), 0.0) * ctx.size
            else:
                gap = SPACE_TABLE.get((pc, cc), 0.0) * ctx.size * 0.5
        items.append((b, gap))
        prev = c
    if not items:
        return Box(0, ctx.size * 0.5, 0)
    return hbox(items)


def layout(node, ctx):
    k = node[0]
    s = ctx.size
    if k == "group":
        return layout_list(node[1], ctx)
    if k == "empty":
        return placeholder(s, ctx.edit)
    if k == "sym":
        kind = {"text": "text", "textit": "textit", "textbf": "textbf"}.get(node[3], "math")
        g = glyph(node[1], s, kind)
        if node[2] in ("bin", "rel") and node[1] in "−+=":
            g.a = max(g.a, ctx.axis() * 1.6)
        return g
    if k == "bad":
        b = glyph(node[1], s, "text", alpha=150 if ctx.edit else 255)
        return b
    if k == "space":
        return Box(node[1] * s, 0, 0)
    if k == "scripts":
        return _scripts(node, ctx)
    if k == "frac":
        return _frac(node, ctx)
    if k == "sqrt":
        return _sqrt(node, ctx)
    if k == "delim":
        inner = layout_list(node[2], ctx)
        return _delimited(node[1], inner, node[3], ctx)
    if k == "acc":
        return _accent(node[1], layout(node[2], ctx), ctx)
    if k == "op":
        return _op(node, ctx)
    if k == "env":
        return _env(node, ctx)
    return Box()


def _op_box(node, ctx):
    """Büyük işleç / fonksiyon adı kutusu (sınırsız)."""
    _, text, kind, _lim = node[:4]
    s = ctx.size
    if kind == "op":
        return glyph(text, s, "text")
    if kind in ("over", "under"):
        return layout(text, ctx)
    scale = (2.0 if ctx.disp else 1.3) if kind == "big" else (1.9 if ctx.disp else 1.3)
    g = glyph(text, s * scale)
    # işleci matematik eksenine ortala
    mid = (g.a - g.d) / 2
    shift = mid - ctx.axis()
    holder = Box(g.w, g.a - shift, g.d + shift)
    holder.parts.append((g, 0.0, shift))
    return holder


def _op(node, ctx):
    kind = node[2]
    if kind in ("over", "under"):
        base = layout(node[1], ctx)
        lim = layout(node[3], ctx.script())
        return _limits(base, lim if kind == "under" else None, lim if kind == "over" else None, ctx)
    return _op_box(node, ctx)


def _limits(base, sub, sup, ctx):
    s = ctx.size
    gap = s * 0.12
    w = max(base.w, sub.w if sub else 0, sup.w if sup else 0)
    b = Box(w, base.a, base.d)
    b.parts.append((base, (w - base.w) / 2, 0.0))
    if sup is not None:
        y = -base.a - gap - sup.d
        b.parts.append((sup, (w - sup.w) / 2, y))
        b.a = -y + sup.a
    if sub is not None:
        y = base.d + gap + sub.a
        b.parts.append((sub, (w - sub.w) / 2, y))
        b.d = y + sub.d
    return b


def _scripts(node, ctx):
    _, base_n, sub_n, sup_n = node
    s = ctx.size
    sc = ctx.script()
    if base_n[0] == "op":
        kind = base_n[2]
        lim = base_n[3] if len(base_n) > 3 else False
        if (kind == "big" and ctx.disp) or (kind == "op" and lim is True and ctx.disp):
            base = _op_box(base_n, ctx)
            return _limits(base, layout(sub_n, sc) if sub_n else None, layout(sup_n, sc) if sup_n else None, ctx)
    base = layout(base_n, ctx)
    sub = layout(sub_n, sc) if sub_n is not None else None
    sup = layout(sup_n, sc) if sup_n is not None else None
    is_int = base_n[0] == "op" and base_n[2] == "int"
    b = Box(base.w, base.a, base.d)
    b.parts.append((base, 0.0, 0.0))
    x_sup = base.w + (s * 0.05 if base.italic else s * 0.02)
    x_sub = base.w + (-s * 0.06 if base.italic else s * 0.02)
    if is_int:
        x_sup = base.w + s * 0.02
        x_sub = base.w - s * 0.28 * (1.4 if ctx.disp else 1.0)
    single = base.glyph is not None and base.a < s * 0.8
    up = max(s * 0.4, (base.a - sc.size * 0.35) if not single else s * 0.36)
    down = max(s * 0.2, (base.d + sc.size * 0.25) if not single else s * 0.2)
    if is_int:
        up, down = base.a - sup.a * 0.55 if sup else 0, base.d - (sub.d if sub else 0) * 0.2
    if sup is not None:
        up = max(up, sup.d + s * 0.25)
    if sub is not None:
        down = max(down, sub.a - s * 0.4)
    if sup is not None and sub is not None:
        gapv = (up - sup.d) - (sub.a - down)
        need = s * 0.16
        if gapv < need:
            down += need - gapv
    w = base.w
    if sup is not None:
        b.parts.append((sup, x_sup, -up))
        b.a = max(b.a, up + sup.a)
        w = max(w, x_sup + sup.w)
    if sub is not None:
        b.parts.append((sub, x_sub, down))
        b.d = max(b.d, down + sub.d)
        w = max(w, x_sub + sub.w)
    b.w = w + s * 0.04
    return b


def _frac(node, ctx):
    fc = ctx.frac()
    num, den = layout(node[1], fc), layout(node[2], fc)
    bar = len(node) < 4
    s = ctx.size
    ax, t = ctx.axis(), ctx.rule()
    gap = s * (0.16 if ctx.disp else 0.1)
    pad = s * 0.12
    w = max(num.w, den.w) + 2 * pad
    b = Box(w)
    yn = -(ax + t / 2 + gap + num.d)
    yd = -ax + t / 2 + gap + den.a
    b.parts.append((num, (w - num.w) / 2, yn))
    b.parts.append((den, (w - den.w) / 2, yd))
    if bar:
        b.lines.append((pad * 0.4, -ax, w - pad * 0.4, -ax, t))
    b.a = -yn + num.a
    b.d = yd + den.d
    return b


def _sqrt(node, ctx):
    body = layout(node[1], ctx)
    s = ctx.size
    t = ctx.rule()
    top = -(max(body.a, s * 0.62) + s * 0.14)
    bot = max(body.d, s * 0.05) + s * 0.08
    h = bot - top
    hook = min(h, s * 1.4)
    rw = s * 0.5 + h * 0.06
    idx = None
    shift = 0.0
    if node[2] is not None:
        idx = layout(node[2], Ctx(max(s * 0.5, ctx.base * 0.42), False, ctx.base, ctx.edit))
        shift = max(0.0, idx.w - rw * 0.55)
    path = QPainterPath()
    mid = bot - hook * 0.45
    path.moveTo(shift + 0.0, mid + s * 0.04)
    path.lineTo(shift + rw * 0.22, mid - s * 0.04)
    path.lineTo(shift + rw * 0.55, bot)
    path.lineTo(shift + rw, top)
    path.lineTo(shift + rw + body.w + s * 0.1, top)
    b = Box(shift + rw + body.w + s * 0.16, -top + t, bot)
    b.paths.append((path, t * 1.1, False))
    b.parts.append((body, shift + rw + s * 0.05, 0.0))
    if idx is not None:
        y = mid - s * 0.12 - idx.d
        b.parts.append((idx, max(0.0, shift + rw * 0.45 - idx.w), y))
        b.a = max(b.a, -y + idx.a)
    return b


def _delim_box(ch, h_need, ctx, left):
    """Ayraç kutusu: küçükse yazı tipinden, büyükse çizilir (eksene ortalı)."""
    s = ctx.size
    if not ch:
        return Box(s * 0.05, 0, 0)
    if h_need <= s * 1.18:
        g = glyph(ch, s)
        g.w += s * 0.03
        return g
    ax = ctx.axis()
    t = ctx.rule() * 1.15
    top, bot = -ax - h_need / 2, -ax + h_need / 2
    w = s * 0.34 + h_need * 0.05
    if ch in ("|", "‖"):
        w = s * (0.28 if ch == "|" else 0.42)
    b = Box(w, -top, bot)
    path = QPainterPath()
    m = (top + bot) / 2
    if ch in "()":
        x1, x0 = (w * 0.85, w * 0.15) if ch == "(" else (w * 0.15, w * 0.85)
        path.moveTo(x1, top)
        path.cubicTo(x0, top + h_need * 0.22, x0, bot - h_need * 0.22, x1, bot)
    elif ch in "[]⌊⌋⌈⌉":
        xo, xi = (w * 0.25, w * 0.85) if ch in "[⌊⌈" else (w * 0.75, w * 0.15)
        if ch in "[]⌈⌉":
            path.moveTo(xi, top)
            path.lineTo(xo, top)
        else:
            path.moveTo(xo, top)
        path.lineTo(xo, bot)
        if ch in "[]⌊⌋":
            path.lineTo(xi, bot)
    elif ch in "{}":
        xm, xe = (w * 0.5, w * 0.9) if ch == "{" else (w * 0.5, w * 0.1)
        xp = w * 0.1 if ch == "{" else w * 0.9
        q = h_need / 4
        path.moveTo(xe, top)
        path.cubicTo(xm, top, xm, top, xm, top + q * 0.5)
        path.lineTo(xm, m - q * 0.5)
        path.cubicTo(xm, m, xm, m, xp, m)
        path.cubicTo(xm, m, xm, m, xm, m + q * 0.5)
        path.lineTo(xm, bot - q * 0.5)
        path.cubicTo(xm, bot, xm, bot, xe, bot)
    elif ch == "|":
        path.moveTo(w / 2, top)
        path.lineTo(w / 2, bot)
    elif ch == "‖":
        path.moveTo(w * 0.32, top)
        path.lineTo(w * 0.32, bot)
        path.moveTo(w * 0.68, top)
        path.lineTo(w * 0.68, bot)
    elif ch in "⟨⟩":
        xo, xi = (w * 0.85, w * 0.15) if ch == "⟨" else (w * 0.15, w * 0.85)
        path.moveTo(xo, top)
        path.lineTo(xi, m)
        path.lineTo(xo, bot)
    else:
        g = glyph(ch, s)
        return g
    b.paths.append((path, t, False))
    return b


def _delimited(lch, inner, rch, ctx):
    s = ctx.size
    ax = ctx.axis()
    h_need = 2 * max(inner.a - ax, inner.d + ax) + s * 0.12
    lb = _delim_box(lch, h_need, ctx, True)
    rb = _delim_box(rch, h_need, ctx, False)
    pad = s * 0.04 if h_need > s * 1.18 else 0.0
    return hbox([(lb, 0.0), (inner, pad), (rb, pad)])


def _accent(name, body, ctx):
    s = ctx.size
    t = ctx.rule()
    w = body.w
    b = Box(w, body.a, body.d)
    b.parts.append((body, 0.0, 0.0))
    top = -max(body.a, s * 0.5) - s * 0.1
    cx = w / 2 + (s * 0.06 if body.italic else 0.0)
    path = QPainterPath()
    if name in ("vec", "overrightarrow"):
        y = top - s * 0.1
        x0 = cx - max(w / 2, s * 0.22) if name == "overrightarrow" or w > s * 0.8 else cx - s * 0.22
        x1 = cx + max(w / 2, s * 0.22) if name == "overrightarrow" or w > s * 0.8 else cx + s * 0.22
        hh = s * 0.11
        path.moveTo(x0, y)
        path.lineTo(x1, y)
        path.moveTo(x1 - hh, y - hh * 0.8)
        path.lineTo(x1, y)
        path.lineTo(x1 - hh, y + hh * 0.8)
        b.paths.append((path, t, False))
        b.a = -y + hh
    elif name in ("hat", "widehat", "check"):
        hw = max(s * 0.18, w * 0.42) if name == "widehat" else s * 0.18
        hh = s * 0.14
        y = top
        sign = 1 if name == "check" else -1
        path.moveTo(cx - hw, y)
        path.lineTo(cx, y + sign * hh)
        path.lineTo(cx + hw, y)
        b.paths.append((path, t, False))
        b.a = -y + hh + t
    elif name in ("bar", "overline"):
        y = top
        x0, x1 = (0.0, w) if name == "overline" or w > s * 0.8 else (cx - s * 0.2, cx + s * 0.2)
        b.lines.append((x0, y, x1, y, t))
        b.a = -y + t
    elif name == "underline":
        y = max(body.d, 0.0) + s * 0.12
        b.lines.append((0.0, y, w, y, t))
        b.d = y + t
    elif name in ("dot", "ddot"):
        r = s * 0.045
        y = top - r
        xs = (cx,) if name == "dot" else (cx - s * 0.12, cx + s * 0.12)
        for x in xs:
            path.addEllipse(QPointF(x, y), r, r)
        b.paths.append((path, 0, True))
        b.a = -y + r
    elif name in ("tilde", "widetilde"):
        hw = max(s * 0.2, w * 0.42) if name == "widetilde" else s * 0.2
        y = top - s * 0.04
        path.moveTo(cx - hw, y + s * 0.04)
        path.cubicTo(cx - hw / 2, y - s * 0.1, cx + hw / 2, y + s * 0.1, cx + hw, y - s * 0.04)
        b.paths.append((path, t, False))
        b.a = -y + s * 0.1
    else:   # acute / grave / breve: basitçe kısa çizgi
        y = top
        path.moveTo(cx - s * 0.08, y + s * 0.06)
        path.lineTo(cx + s * 0.08, y - s * 0.06)
        b.paths.append((path, t, False))
        b.a = -y + s * 0.08
    return b


def _env(node, ctx):
    name, rows = node[1], node[2]
    s = ctx.size
    top_level = name == "top"
    cctx = ctx if top_level else (Ctx(s * (0.72 if name == "smallmatrix" else 1.0), False, ctx.base, ctx.edit))
    if not top_level:
        cctx = Ctx(cctx.size, False, ctx.base, ctx.edit)
    al = name in ("aligned", "align", "align*", "split") or (top_level and max(len(r) for r in rows) > 1)
    # hizalamada sağ hücre "=" ile başlarsa önünde boşluk kalsın (boş bir sıradan öğe ekle)
    grid = [[layout_list(([("sym", "", "ord", "rm")] if al and j % 2 == 1 else []) + cell, cctx)
             for j, cell in enumerate(row)] for row in rows]
    ncol = max(len(r) for r in grid)
    colw = [0.0] * ncol
    for r in grid:
        for j, c in enumerate(r):
            colw[j] = max(colw[j], c.w)
    aligned = name in ("aligned", "align", "align*", "split") or (top_level and ncol > 1)
    left = name == "cases" or (top_level and ncol == 1)
    colgap = s * (0.0 if aligned else (0.9 if name != "cases" else 1.0))
    rowgap = s * (0.42 if top_level or aligned else 0.3)
    xs, x = [], 0.0
    for j, w in enumerate(colw):
        xs.append(x)
        x += w + (colgap if j < ncol - 1 else 0.0)
    W = x
    b = Box(W)
    y = 0.0
    heights = []
    for i, r in enumerate(grid):
        ra = max([c.a for c in r] + [s * 0.7])
        rd = max([c.d for c in r] + [s * 0.2])
        heights.append((ra, rd))
    total = sum(a + d for a, d in heights) + rowgap * (len(grid) - 1)
    y = -heights[0][0] if top_level else (-ctx.axis() - total / 2)
    first = None
    for i, r in enumerate(grid):
        ra, rd = heights[i]
        base = y + ra
        if first is None:
            first = base
        for j, c in enumerate(r):
            if aligned:
                dx = xs[j] + (colw[j] - c.w if j % 2 == 0 else 0.0)
                if j % 2 == 1 and c.w > 0:
                    dx += 0.0
            elif left:
                dx = xs[j]
            else:
                dx = xs[j] + (colw[j] - c.w) / 2
            b.parts.append((c, dx, base))
        y = base + rd + rowgap
    end = y - rowgap
    if top_level:
        # taban çizgisi ilk satırda
        for k, (c, dx, dy) in enumerate(b.parts):
            b.parts[k] = (c, dx, dy - first)
        b.a = heights[0][0]
        b.d = end - first
        return b
    b.a = -(-ctx.axis() - total / 2)
    b.d = end
    lch, rch = ENVS.get(name, ("", ""))
    if not lch and not rch:
        return b
    inner_pad = Box(s * 0.12, 0, 0)
    inner = hbox([(inner_pad, 0.0), (b, 0.0), (Box(s * 0.12, 0, 0), 0.0)])
    return _delimited(lch, inner, rch, ctx)


# ------------------------------------------------------------------ dış arayüz
def layout_src(src, size, edit=False):
    """Kaynaktan kutu. Boş kaynak düzenlerken boş kutu, değilse sıfır genişlik."""
    size = max(4.0, float(size))
    if not (src or "").strip():
        return placeholder(size, edit) if edit else Box(0, size * 0.7, size * 0.2)
    try:
        return layout(parse(src), Ctx(size, True, size, edit))
    except (RecursionError, IndexError, ValueError, TypeError) as e:     # asla düşmesin
        return glyph(src + "  ⚠ " + type(e).__name__, size, "text", alpha=160)


def render_pixmap(src, size, color, pad=4, max_w=None, dpr=None):
    """Palet düğmeleri / önizleme için küçük resim."""
    if dpr is None:
        app = QGuiApplication.instance()
        dpr = app.devicePixelRatio() if app else 1.0
    b = layout_src(src, size, edit=True)
    w, h = b.w + 2 * pad, b.a + b.d + 2 * pad
    k = 1.0
    if max_w and w > max_w:
        k = max_w / w
    pm = QPixmap(max(1, int((w * k) * dpr + 1)), max(1, int((h * k) * dpr + 1)))
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    p.scale(k * dpr, k * dpr)
    b.draw(p, pad, pad + b.a, QColor(color))
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def bounds(box, size):
    """Kutunun çizim alanı (taban = 0, sol = 0), italik taşmalar için pay."""
    pad = size * 0.12
    return QRectF(-pad, -box.a - pad, box.w + 2 * pad, box.a + box.d + 2 * pad)
