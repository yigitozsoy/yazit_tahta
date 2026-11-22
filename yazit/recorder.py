"""Ekran videosu: seçilen alan / tüm ekran ffmpeg (gdigrab) ile MP4'e kaydedilir.

Ayarlar (Kayıt paneli, recpanel.py): kamera (köşede yuvarlak), mikrofon, bilgisayar sesi (loopback.py),
çözünürlük, kare hızı, geri sayım. Hepsi prefs'te; `rec_config()` okur, `build_args()` ffmpeg komutunu kurar.

Kayıt sırasında alanın çevresinde kırmızı çerçeve ve küçük bir kontrol çubuğu (süre · durdur · vazgeç) durur.
İkisi de WDA_EXCLUDEFROMCAPTURE ile videoya girmez. "Ekrana çiz" katmanı ise bilerek videoya girer:
kayıt sırasında ekrana çizip anlatılabilir.
"""
import ctypes
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime

from PyQt6.QtCore import Qt, QObject, pyqtSignal, QProcess, QTimer, QRect, QRectF, QPoint, QPointF, QSize
from PyQt6.QtGui import QPainter, QColor, QPen, QPainterPath
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QPushButton, QLabel

from . import icons
from .config import prefs, video_dir
from .i18n import t

WDA_EXCLUDEFROMCAPTURE = 0x11
CREATE_NO_WINDOW = 0x08000000


def find_ffmpeg():
    """Donmuş exe'de yanındaki ffmpeg, kaynaktan çalışırken imageio-ffmpeg ya da PATH."""
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
        for name in ("ffmpeg.exe",):
            p = os.path.join(base, name)
            if os.path.exists(p):
                return p
    try:
        import imageio_ffmpeg
        p = imageio_ffmpeg.get_ffmpeg_exe()
        if p and os.path.exists(p):
            return p
    except Exception:
        pass
    return shutil.which("ffmpeg")


_devs = None


def list_devices(refresh=False):
    """DirectShow aygıtları: (kameralar, mikrofonlar) adları."""
    global _devs
    if _devs is not None and not refresh:
        return _devs
    ff = find_ffmpeg()
    cams, mics = [], []
    if ff:
        try:
            r = subprocess.run([ff, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                               capture_output=True, timeout=8, creationflags=CREATE_NO_WINDOW)
            txt = (r.stderr or b"").decode("utf-8", errors="ignore")
            cams = re.findall(r'"([^"]+)"\s*\(video\)', txt)
            mics = re.findall(r'"([^"]+)"\s*\(audio\)', txt)
        except Exception:
            pass
    _devs = (cams, mics)
    return _devs


def list_mics(refresh=False):
    return list_devices(refresh)[1]


def list_cams(refresh=False):
    return list_devices(refresh)[0]


RESOLUTIONS = ("src", "1080", "720", "480")
FPS_CHOICES = (24, 30, 60)
COUNTDOWNS = (0, 3, 5, 10)
CAM_CORNERS = ("tl", "tr", "bl", "br")
CAM_SHAPES = ("circle", "square", "rect")
CAM_BORDERS = ("none", "shadow", "#ffffff", "#000000", "#ff3b30")   # shadow: gölge + ince açık kenar


def _pick(v, choices):
    return v if v in choices else choices[0]


def rec_config():
    """Kayıt ayarları (prefs). Mikrofon adı record_mic'te kalır; açık / kapalı ayrı (rec_mic_on)."""
    mic = prefs.get("record_mic", "") or ""
    fps = int(prefs.get("record_fps", 30) or 30)
    cd = int(prefs.get("rec_countdown", 3) or 0)
    return {
        "scene": prefs.get("rec_scene", "area") if prefs.get("rec_scene", "area") in ("area", "screen") else "area",
        "screen": prefs.get("rec_screen", "") or "",
        "cam": bool(prefs.get("rec_cam", False)),
        "cam_dev": prefs.get("rec_cam_dev", "") or "",
        "cam_pos": prefs.get("rec_cam_pos", "br") if prefs.get("rec_cam_pos", "br") in CAM_CORNERS else "br",
        "cam_shape": _pick(prefs.get("rec_cam_shape", "circle"), CAM_SHAPES),
        "cam_border": _pick(prefs.get("rec_cam_border", "none"), CAM_BORDERS),
        "cam_gray": bool(prefs.get("rec_cam_gray", False)),
        "mic": bool(prefs.get("rec_mic_on", bool(mic))),
        "mic_dev": mic,
        "sys": bool(prefs.get("rec_sys", False)),
        "res": prefs.get("rec_res", "src") if prefs.get("rec_res", "src") in RESOLUTIONS else "src",
        "fps": fps if fps in FPS_CHOICES else 30,
        "countdown": cd if cd in COUNTDOWNS else 3,
    }


def active_sources(cfg):
    """Gerçekten kullanılacak kaynaklar (aygıt takılı değilse düşer): {"cam": ad, "mic": ad, "sys": bool}."""
    cams, mics = list_devices()
    cam = cfg.get("cam_dev") or (cams[0] if cams else "")
    mic = cfg.get("mic_dev") or (mics[0] if mics else "")
    return {"cam": cam if cfg.get("cam") and cam in cams else "",
            "mic": mic if cfg.get("mic") and mic in mics else "",
            "sys": bool(cfg.get("sys"))}


def summary(cfg):
    """Kısa özet: "Mikrofon · Bilgisayar sesi · Kamera" ya da "Sessiz"."""
    src = active_sources(cfg)
    parts = []
    if src["mic"]:
        parts.append(t("rec_mic_on"))
    if src["sys"]:
        parts.append(t("rp_sys_short"))
    if src["cam"]:
        parts.append(t("rp_cam"))
    if not (src["mic"] or src["sys"]):
        parts.insert(0, t("rec_silent"))
    return "  ·  ".join(parts)


def out_size(w, h, res):
    """Çıkış boyutu: yalnızca küçültür (en-boy oranı korunur), çift sayı."""
    target = {"1080": 1080, "720": 720, "480": 480}.get(res)
    if target and h > target:
        w, h = round(w * target / h), target
    return max(2, w // 2 * 2), max(2, h // 2 * 2)


def cam_size(shape, ow, oh):
    """Videodaki kamera kutusunun boyutu (çift sayı): daire / kare d×d, dikdörtgen 16:9."""
    base = min(ow, oh) * 0.26
    if shape == "rect":
        ch = max(54, round(base * 0.82) // 2 * 2)
        return max(96, round(ch * 16 / 9) // 2 * 2), ch
    d = max(64, round(base) // 2 * 2)
    return d, d


def cam_crop(shape):
    """Kamera görüntüsünden şeklin en-boy oranında orta parça (ffmpeg crop)."""
    if shape == "rect":
        return "crop='min(iw,ih*16/9)':'min(ih,iw*9/16)'"
    return "crop='min(iw,ih)':'min(iw,ih)'"


def border_width(w, h):
    return max(3.0, min(w, h) * 0.03)


def cam_path(shape, w, h, inset=0.0):
    """Şeklin yolu (w×h kutuda, kenardan inset kadar içeride). Kayıt maskesi, kenarlık ve önizleme aynısını kullanır."""
    r = QRectF(inset, inset, w - 2 * inset, h - 2 * inset)
    path = QPainterPath()
    if shape == "circle":
        path.addEllipse(r)
    else:
        rad = max(0.0, min(w, h) * 0.12 - inset)
        path.addRoundedRect(r, rad, rad)
    return path


def shadow_pad(w, h):
    """Gölge resminin kameradan taşma payı ve aşağı kayması (piksel)."""
    s = min(w, h)
    return round(s * 0.18) + 4, round(s * 0.06) + 2


def shadow_image(shape, w, h):
    """Kameranın altına düşen yumuşak gölge (ARGB, kenarlardan pad kadar büyük). Bulanıklık: küçült-büyüt."""
    from PyQt6.QtGui import QImage
    pad, dy = shadow_pad(w, h)
    W, H = w + 2 * pad, h + 2 * pad
    img = QImage(W, H, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 0, 0, 150))
    p.translate(pad, pad + dy)
    p.drawPath(cam_path(shape, w, h, 0))
    p.end()
    k = max(2, pad // 4)
    smooth = Qt.TransformationMode.SmoothTransformation
    ign = Qt.AspectRatioMode.IgnoreAspectRatio
    for _ in range(3):
        img = img.scaled(max(1, W // k), max(1, H // k), ign, smooth).scaled(W, H, ign, smooth)
    return img


def cam_images(shape, w, h, border):
    """(maske PNG yolu, kenarlık PNG yolu ya da None), geçici klasörde. ffmpeg'in geq'i her karede piksel piksel
    hesapladığı için gerçek zamana yetişmiyordu; hazır resim + alphamerge / overlay neredeyse bedava."""
    import tempfile
    from PyQt6.QtGui import QImage
    tmp = tempfile.gettempdir()
    mask = os.path.join(tmp, f"yazit-cam-mask-{shape}-{w}x{h}.png")
    if not os.path.exists(mask):
        img = QImage(w, h, QImage.Format.Format_Grayscale8)
        img.fill(0)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255))
        p.drawPath(cam_path(shape, w, h, 0.5))
        p.end()
        img.save(mask)
    frame = shadow = None
    if border and border != "none":
        frame = os.path.join(tmp, f"yazit-cam-frame-{shape}-{w}x{h}-{border.lstrip('#')}.png")
        if not os.path.exists(frame):
            img = QImage(w, h, QImage.Format.Format_ARGB32)
            img.fill(0)
            p = QPainter(img)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            col, bw = rim_style(border, w, h)
            p.setPen(QPen(col, bw))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(cam_path(shape, w, h, bw / 2 + 0.25))
            p.end()
            img.save(frame)
    if border == "shadow":
        shadow = os.path.join(tmp, f"yazit-cam-shadow-{shape}-{w}x{h}.png")
        if not os.path.exists(shadow):
            shadow_image(shape, w, h).save(shadow)
    return mask, frame, shadow


def rim_style(border, w, h):
    """Kenar çizgisinin rengi ve kalınlığı: gölge seçeneğinde ince yarı saydam açık çizgi."""
    if border == "shadow":
        return QColor(255, 255, 255, 70), max(1.5, min(w, h) * 0.008)
    return QColor(border), border_width(w, h)


def cam_rect(ow, oh, cfg):
    """Videoda kameranın kutusu (çıkış pikseli): (x, y, genişlik, yükseklik)."""
    cw, ch = cam_size(cfg.get("cam_shape", "circle"), ow, oh)
    m = max(8, round(min(ow, oh) * 0.03))
    pos = cfg.get("cam_pos", "br")
    ox = m if pos[1] == "l" else ow - cw - m
    oy = m if pos[0] == "t" else oh - ch - m
    return ox, oy, cw, ch


def build_args(x, y, w, h, cfg, src, path, sys_input=None, preview=None):
    """preview=(pw, ph): kamera açıksa ikinci çıktı — kayda giren kamera görüntüsü küçük ham RGB kareler olarak
    stdout'a (kayıt sırasında kendini görmek için; kamera aynı anda iki programa açılamıyor)."""
    """ffmpeg argümanları. Girişler: [dshow kamera+mikrofon] [bilgisayar sesi borusu] [ekran].
    Yavaş açılan aygıtlar önce: hepsi açıldıktan hemen sonra ekran yakalaması başlar, kaymalar küçük kalır.
    Kamera ile mikrofon aynı dshow girişinde → dudak ile ses kendi aralarında eş."""
    fps = int(cfg.get("fps", 30))
    args = ["-hide_banner", "-loglevel", "error", "-y"]
    idx = 0
    dsh = sysi = None
    if src["cam"] or src["mic"]:
        spec = []
        if src["cam"]:
            spec.append(f"video={src['cam']}")
        if src["mic"]:
            spec.append(f"audio={src['mic']}")
        args += ["-thread_queue_size", "1024", "-rtbufsize", "256M", "-f", "dshow"]
        if src["mic"]:
            args += ["-audio_buffer_size", "50"]
        args += ["-i", ":".join(spec)]
        dsh, idx = idx, idx + 1
    if sys_input:
        args += sys_input
        sysi, idx = idx, idx + 1
    args += ["-thread_queue_size", "1024", "-f", "gdigrab", "-framerate", str(fps), "-draw_mouse", "1",
             "-offset_x", str(x), "-offset_y", str(y), "-video_size", f"{w}x{h}", "-i", "desktop"]
    scr, idx = idx, idx + 1
    ow, oh = out_size(w, h, cfg.get("res", "src"))
    shape = cfg.get("cam_shape", "circle")
    ox, oy, cw, ch = cam_rect(ow, oh, cfg)
    frame = shadow = None
    if src["cam"]:
        mpath, fpath, spath = cam_images(shape, cw, ch, cfg.get("cam_border", "none"))
        args += ["-loop", "1", "-framerate", str(fps), "-i", mpath]
        mask, idx = idx, idx + 1
        if spath:
            args += ["-loop", "1", "-framerate", str(fps), "-i", spath]
            shadow, idx = idx, idx + 1
        if fpath:
            args += ["-loop", "1", "-framerate", str(fps), "-i", fpath]
            frame, idx = idx, idx + 1
    filters = []
    vout = f"{scr}:v"
    if (ow, oh) != (w, h) or src["cam"]:
        base = f"[{scr}:v]" + (f"scale={ow}:{oh}:flags=bicubic" if (ow, oh) != (w, h) else "null")
        if src["cam"]:
            filters.append(base + "[bg]")
            gray = ",hue=s=0" if cfg.get("cam_gray") else ""
            cam_in = f"[{dsh}:v]{cam_crop(shape)},scale={cw}:{ch},setsar=1{gray}"
            if preview:
                pw, ph = preview
                filters.append(cam_in + ",split=2[c0r][pvr]")
                filters.append("[c0r]format=yuv420p[c0]")
                filters.append(f"[pvr]scale={pw}:{ph},fps=20,format=rgb24[pv]")
            else:
                filters.append(cam_in + ",format=yuv420p[c0]")
            filters.append(f"[{mask}:v]format=gray[mk]")
            filters.append("[c0][mk]alphamerge[cam]")
            cur = "[bg]"
            if shadow is not None:
                pad, _dy = shadow_pad(cw, ch)
                filters.append(f"[{shadow}:v]format=rgba[sh]")
                filters.append(f"{cur}[sh]overlay={ox - pad}:{oy - pad}:shortest=0[b1]")
                cur = "[b1]"
            if frame is None:
                filters.append(f"{cur}[cam]overlay={ox}:{oy}:eof_action=pass:shortest=0,format=yuv420p[v]")
            else:
                filters.append(f"{cur}[cam]overlay={ox}:{oy}:eof_action=pass:shortest=0[o1]")
                filters.append(f"[{frame}:v]format=rgba[fr]")
                filters.append(f"[o1][fr]overlay={ox}:{oy}:shortest=0,format=yuv420p[v]")
        else:
            filters.append(base + ",format=yuv420p[v]")
        vout = "[v]"
    auds = []
    if src["mic"]:
        auds.append(f"{dsh}:a")
    if sysi is not None:
        auds.append(f"{sysi}:a")
    aout = None
    if len(auds) == 2:
        filters.append(f"[{auds[0]}][{auds[1]}]amix=inputs=2:duration=longest:normalize=0[a]")
        aout = "[a]"
    elif auds:
        aout = auds[0]
    if filters:
        args += ["-filter_complex", ";".join(filters)]
    args += ["-map", vout]
    if aout:
        args += ["-map", aout]
    args += ["-r", str(fps), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-pix_fmt", "yuv420p"]
    if aout:
        args += ["-c:a", "aac", "-b:a", "160k"]
    args += ["-movflags", "+faststart", path]
    if preview and src["cam"]:
        args += ["-map", "[pv]", "-f", "rawvideo", "-pix_fmt", "rgb24", "pipe:1"]
    return args


def exclude_from_capture(widget):
    try:
        ctypes.windll.user32.SetWindowDisplayAffinity(int(widget.winId()), WDA_EXCLUDEFROMCAPTURE)
    except Exception:
        pass


def _fmt(sec):
    sec = int(sec)
    return f"{sec // 3600}:{sec // 60 % 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60:02d}:{sec % 60:02d}"


class RecordFrame(QWidget):
    """Kaydedilen alanın dışında kırmızı çerçeve; fareye geçirgen, videoya girmez."""
    M = 4

    def __init__(self, rect: QRect):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.Tool | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setGeometry(rect.adjusted(-self.M, -self.M, self.M, self.M))

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(255, 48, 48, 230), 2.5, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawRect(QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5))


BAR_QSS = """
QPushButton { background: transparent; color: #f1f1f1; border: none; border-radius: 15px;
              padding: 0px 12px; min-height: 30px; max-height: 30px; font-size: 13px; font-weight: 500; }
QPushButton:hover { background: rgba(255,255,255,0.12); }
QPushButton#RecStop { background: #f1f1f1; color: #0f0f0f; font-weight: 600; }
QPushButton#RecStop:hover { background: #d9d9d9; }
QLabel { color: #f1f1f1; font-size: 13px; font-weight: 600; }
QLabel#RecMic { color: #aaaaaa; font-weight: 500; font-size: 12px; }
QPushButton#RecSelf { padding: 0px; min-width: 30px; max-width: 30px; }
QPushButton#RecSelf:checked { background: rgba(255,255,255,0.16); }
"""


class RecordBar(QWidget):
    """Kayıt sırasında: ● süre · Durdur · Vazgeç. Sürüklenerek taşınabilir."""

    def __init__(self, rec):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.Tool)
        self.rec = rec
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet(BAR_QSS)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 6, 6, 6)
        lay.setSpacing(6)
        # yanıp sönme: nokta hiç gizlenmez, yalnız rengi söner — yoksa süre ve düğmeler kayar
        self.dot = QLabel("●")
        self.set_blink(True)
        self.dot.setFixedSize(self.dot.sizeHint() + QSize(2, 0))
        self.dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.dot)
        self.time = QLabel("00:00")
        self.time.setMinimumWidth(44)
        lay.addWidget(self.time)
        self.mic = QLabel("")          # (eski ad) etkin kaynakların simgeleri
        self.mic.setObjectName("RecMic")
        lay.addWidget(self.mic)
        self.src_icons = []
        b = QPushButton(icons.icon("stop", "#0f0f0f", 18), " " + t("rec_stop"))
        b.setObjectName("RecStop")
        b.setToolTip(t("rec_stop_tip"))
        b.clicked.connect(rec.stop)
        lay.addWidget(b)
        c = QPushButton(icons.icon("close", "#f1f1f1", 18), "")
        c.setToolTip(t("rec_discard"))
        c.clicked.connect(rec.discard)
        lay.addWidget(c)
        for w in self.findChildren(QPushButton):
            w.setCursor(Qt.CursorShape.PointingHandCursor)
            w.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._drag = None

    def set_sources(self, src):
        for w in self.src_icons:
            w.deleteLater()
        self.src_icons = []
        lay = self.layout()
        at = lay.indexOf(self.mic)
        tips = {"mic": src.get("mic", ""), "volume": t("rp_sys"), "videocam": src.get("cam", "")}
        for name, on in (("mic", src.get("mic")), ("volume", src.get("sys")), ("videocam", src.get("cam"))):
            if on and name == "videocam" and self.rec.selfview is not None:
                lb = QPushButton(icons.icon("videocam", "#f1f1f1", 17), "")
                lb.setObjectName("RecSelf")
                lb.setCheckable(True)
                lb.setChecked(self.rec.selfview.isVisible())
                lb.setToolTip(t("rec_selfview"))
                lb.setCursor(Qt.CursorShape.PointingHandCursor)
                lb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                lb.toggled.connect(self.rec.set_selfview)
                at += 1
                lay.insertWidget(at, lb)
                self.src_icons.append(lb)
                continue
            if on:
                lb = QLabel()
                lb.setPixmap(icons.pixmap(name, "#aaaaaa", 16))
                lb.setToolTip(tips[name])
                at += 1
                lay.insertWidget(at, lb)
                self.src_icons.append(lb)
        self.mic.setVisible(False)

    def set_blink(self, on):
        c = "#ff3030" if on else "rgba(255,48,48,0.25)"
        self.dot.setStyleSheet(f"color: {c}; font-size: 14px;")

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        path.addRoundedRect(r, r.height() / 2, r.height() / 2)
        p.fillPath(path, QColor(28, 28, 28, 240))
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.drawPath(path)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None


class Recorder(QObject):
    started = pyqtSignal()
    saved = pyqtSignal(str)
    failed = pyqtSignal(str)
    stopped = pyqtSignal()   # her durumda (kaydedildi / vazgeçildi / hata)

    def __init__(self):
        super().__init__()
        self.proc = None
        self.path = None
        self.frame = None
        self.bar = None
        self._t0 = 0.0
        self._discard = False
        self._err = b""
        self._lb = None            # bilgisayar sesi (Loopback)
        self.selfview = None       # kayıt sırasında kendini gör (SelfView)
        self.src = {}
        self.warning = ""
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._tick)

    def active(self):
        return self.proc is not None

    def start(self, screen, sel: QRect, dpr: float, cfg=None):
        """sel: ekranın içindeki mantıksal seçim; ffmpeg fiziksel piksel ister. cfg: rec_config() (varsayılan)."""
        if self.proc is not None:
            return
        ff = find_ffmpeg()
        if not ff:
            self.failed.emit(t("rec_no_ffmpeg"))
            self.stopped.emit()
            return
        geo = screen.geometry()
        # Qt (Windows) ekranın sol üst köşesini yerel pikselde tutar, boyutu ölçekler
        x = geo.x() + round(sel.x() * dpr)
        y = geo.y() + round(sel.y() * dpr)
        w = round(sel.width() * dpr) // 2 * 2   # H.264 çift boyut ister
        h = round(sel.height() * dpr) // 2 * 2
        if w < 16 or h < 16:
            self.failed.emit(t("rec_too_small"))
            self.stopped.emit()
            return
        cfg = cfg or rec_config()
        src = active_sources(cfg)
        name = "yazit " + datetime.now().strftime("%Y-%m-%d %H.%M.%S") + ".mp4"
        self.path = os.path.join(video_dir(), name)
        self.warning = ""
        sys_input = None
        if src["sys"]:
            from .loopback import Loopback
            lb = Loopback()
            if lb.open() is not None:
                self._lb = lb
                sys_input = lb.input_args()
            else:
                lb.close()
                src["sys"] = False
                self.warning = t("rp_sys_fail")
        self.src = src
        preview = None
        sv_rect = None
        if src["cam"]:
            ow, oh = out_size(w, h, cfg.get("res", "src"))
            cx, cy, cw, ch = cam_rect(ow, oh, cfg)
            s = w / ow                       # çıkış pikseli → fiziksel piksel
            pw = min(480, max(32, round(cw * s) // 2 * 2))
            ph = min(480, max(32, round(pw * ch / cw) // 2 * 2))
            preview = (pw, ph)
            # videoda kameranın göründüğü yer, ekranın mantıksal koordinatında
            sv_rect = QRectF(geo.x() + sel.x() + cx * s / dpr, geo.y() + sel.y() + cy * s / dpr,
                             cw * s / dpr, ch * s / dpr)
        args = build_args(x, y, w, h, cfg, src, self.path, sys_input, preview)
        self._err = b""
        self._discard = False
        p = QProcess(self)
        p.setProgram(ff)
        p.setArguments(args)
        p.readyReadStandardError.connect(lambda: self._read_err(p))
        if preview:
            self.selfview = SelfView(sv_rect, preview, cfg)
            p.readyReadStandardOutput.connect(lambda: self.selfview is not None and
                                              self.selfview.feed(bytes(p.readAllStandardOutput())))
        p.finished.connect(self._finished)
        p.errorOccurred.connect(self._error)
        self.proc = p
        p.start()
        if not p.waitForStarted(3000):
            return
        self._t0 = time.monotonic()
        lrect = QRect(geo.x() + sel.x(), geo.y() + sel.y(), sel.width(), sel.height())
        self.frame = RecordFrame(lrect)
        self.frame.show()
        exclude_from_capture(self.frame)
        if self.selfview is not None and prefs.get("rec_selfview", True):
            self.selfview.show()
            exclude_from_capture(self.selfview)
        self.bar = RecordBar(self)
        self.bar.set_sources(src)
        self.bar.adjustSize()
        bx = lrect.center().x() - self.bar.width() // 2
        by = lrect.bottom() + 12
        if by + self.bar.height() > geo.y() + geo.height() - 8:   # alttan taşarsa ekranın üstüne
            by = geo.y() + 12 if lrect.top() - geo.y() > self.bar.height() + 24 else lrect.top() + 12
        bx = max(geo.x() + 8, min(bx, geo.x() + geo.width() - self.bar.width() - 8))
        self.bar.move(QPoint(bx, by))
        self.bar.show()
        exclude_from_capture(self.bar)
        self._timer.start()
        self.started.emit()

    def set_selfview(self, on):
        """Kayıt çubuğundaki kamera düğmesi: kendini görmeyi aç / kapat (hatırlanır; videoyu etkilemez)."""
        prefs.set("rec_selfview", bool(on))
        if self.selfview is None:
            return
        if on:
            self.selfview.show()
            exclude_from_capture(self.selfview)
        else:
            self.selfview.hide()

    def _read_err(self, p):
        self._err += bytes(p.readAllStandardError())

    def _tick(self):
        if self.bar is not None:
            el = time.monotonic() - self._t0
            self.bar.time.setText(_fmt(el))
            self.bar.set_blink(int(el * 2) % 2 == 0)

    def stop(self):
        """ffmpeg'e 'q' gönderilir: dosyayı düzgün kapatıp çıkar."""
        if self.proc is None:
            return
        self._hide_ui()
        self.proc.write(b"q")
        self.proc.closeWriteChannel()
        QTimer.singleShot(8000, self._force_kill)

    def discard(self):
        self._discard = True
        self.stop()

    def _force_kill(self):
        if self.proc is not None and self.proc.state() != QProcess.ProcessState.NotRunning:
            self.proc.kill()

    def _hide_ui(self):
        self._timer.stop()
        for w in (self.frame, self.bar, self.selfview):
            if w is not None:
                w.close()
                w.deleteLater()
        self.frame = self.bar = self.selfview = None

    def _close_loopback(self):
        if self._lb is not None:
            self._lb.close()
            self._lb = None

    def _error(self, err):
        if err == QProcess.ProcessError.FailedToStart:
            self._close_loopback()
            self._hide_ui()
            self.proc = None
            self.failed.emit(t("rec_no_ffmpeg"))
            self.stopped.emit()

    def _finished(self, code, _status):
        self._close_loopback()
        self._hide_ui()
        self.proc = None
        path = self.path
        ok = path and os.path.exists(path) and os.path.getsize(path) > 1000
        if self._discard:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        elif ok:
            self.saved.emit(path)
        else:
            msg = self._err.decode("utf-8", errors="ignore").strip().splitlines()
            self.failed.emit(msg[-1] if msg else t("rec_failed"))
        self.stopped.emit()


class SelfView(QWidget):
    """Kayıt sırasında kamerada kendini gör: videoda kameranın göründüğü yerde, aynı şekil / kenarlık / gölgeyle.
    Kareler ffmpeg'in ikinci çıktısından gelir. Fareye geçirgen, videoya girmez (WDA_EXCLUDEFROMCAPTURE)."""

    def __init__(self, rect: QRectF, size, cfg):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.Tool | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.pw, self.ph = size
        self.shape = cfg.get("cam_shape", "circle")
        self.border = cfg.get("cam_border", "none")
        self.cw, self.ch = rect.width(), rect.height()
        self.pad, _dy = shadow_pad(round(self.cw), round(self.ch))
        self.shadow = shadow_image(self.shape, round(self.cw), round(self.ch)) if self.border == "shadow" else None
        self.setGeometry(round(rect.x()) - self.pad, round(rect.y()) - self.pad,
                         round(self.cw) + 2 * self.pad, round(self.ch) + 2 * self.pad)
        self.buf = bytearray()
        self.img = None

    def feed(self, data):
        self.buf += data
        n = self.pw * self.ph * 3
        if len(self.buf) >= n:
            k = len(self.buf) // n
            frame = bytes(self.buf[(k - 1) * n:k * n])
            del self.buf[:k * n]
            from PyQt6.QtGui import QImage
            self.img = QImage(frame, self.pw, self.ph, self.pw * 3, QImage.Format.Format_RGB888).copy()
            if self.isVisible():
                self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.translate(self.pad, self.pad)
        w, h = self.cw, self.ch
        if self.shadow is not None:
            p.drawImage(QPointF(-self.pad, -self.pad), self.shadow)
        path = cam_path(self.shape, w, h)
        if self.img is not None:
            p.save()
            p.setClipPath(path)
            p.drawImage(QRectF(0, 0, w, h), self.img)
            p.restore()
        else:
            p.fillPath(path, QColor(30, 30, 30, 200))
        if self.border != "none":
            col, bw = rim_style(self.border, w, h)
            p.setPen(QPen(col, bw))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(cam_path(self.shape, w, h, bw / 2 + 0.25))


class Countdown(QWidget):
    """Kayıttan önce kaydedilecek alanın ortasında büyük 5…1 sayacı. Videoya girmez.
    Esc: vazgeç · tıkla / Enter: hemen başla."""
    done = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, rect: QRect, seconds: int):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint |
                         Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setGeometry(rect)
        self.n = int(seconds)
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)
        self._over = False

    def start(self):
        self.show()
        exclude_from_capture(self)
        self.raise_()
        self.activateWindow()
        self.setFocus()
        self._timer.start()

    def _tick(self):
        self.n -= 1
        if self.n <= 0:
            self._finish(True)
        else:
            self.update()

    def _finish(self, ok):
        if self._over:
            return
        self._over = True
        self._timer.stop()
        self.hide()
        # pencere ekrandan kalksın, sonra kayıt başlasın; nesne sinyalden SONRA silinir
        QTimer.singleShot(60, lambda: self._emit(ok))

    def _emit(self, ok):
        (self.done if ok else self.cancelled).emit()
        self.deleteLater()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self._finish(False)
        elif e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self._finish(True)

    def mousePressEvent(self, e):
        self._finish(True)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(0, 0, 0, 70))
        c = QRectF(self.rect()).center()
        rad = 78
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(20, 20, 20, 225))
        p.drawEllipse(c, rad, rad)
        p.setPen(QPen(QColor(255, 48, 48, 230), 4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(c, rad - 2, rad - 2)
        f = self.font()
        f.setPixelSize(84)
        f.setWeight(f.Weight.DemiBold)
        p.setFont(f)
        p.setPen(QColor("#f1f1f1"))
        p.drawText(QRectF(c.x() - rad, c.y() - rad, 2 * rad, 2 * rad), Qt.AlignmentFlag.AlignCenter, str(max(1, self.n)))
        f.setPixelSize(13)
        f.setWeight(f.Weight.Medium)
        p.setFont(f)
        tr = QRectF(c.x() - 200, c.y() + rad + 14, 400, 28)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(20, 20, 20, 210))
        tw = p.fontMetrics().horizontalAdvance(t("rp_cd_hint")) + 28
        p.drawRoundedRect(QRectF(c.x() - tw / 2, tr.y(), tw, 28), 14, 14)
        p.setPen(QColor("#cfcfcf"))
        p.drawText(tr, Qt.AlignmentFlag.AlignCenter, t("rp_cd_hint"))
