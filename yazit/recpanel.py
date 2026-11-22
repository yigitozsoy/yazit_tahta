"""Kayıt paneli: video kaydından önce temel ayarlar (sade, tek sayfa).

Sahne (alan / tüm ekran) · kamera (köşede yuvarlak) · mikrofon (+ seviye göstergesi) · bilgisayar sesi ·
çözünürlük ve kare hızı · geri sayım. Her değişiklik hemen prefs'e yazılır; "Kaydı başlat" → start_req(cfg).
Seçenekler'den açılınca (settings_only) yalnızca ayar penceresidir.
"""
import ctypes
from array import array
from ctypes import wintypes, byref, POINTER

from PyQt6.QtCore import Qt, QTimer, QRectF, pyqtSignal, QObject
from PyQt6.QtCore import QSize, QPointF
from PyQt6.QtGui import QPainter, QColor, QGuiApplication, QPixmap, QIcon, QPen
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QComboBox, QButtonGroup,
                             QSizePolicy)

from . import icons
from .config import prefs, video_dir
from .i18n import t
from .theme import color, qcolor, theme
from .widgets import ThemedDialog, ToggleSwitch, Divider
from .recorder import (rec_config, list_devices, find_ffmpeg, cam_crop, cam_path, rim_style, shadow_image,
                       shadow_pad, RESOLUTIONS,
                       FPS_CHOICES, COUNTDOWNS, CAM_SHAPES, CAM_BORDERS)
from PyQt6.QtCore import QProcess
from PyQt6.QtGui import QImage


# --- mikrofon seviyesi: winmm waveIn (QtMultimedia pakete girmiyor)
class _WFX(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("wFormatTag", wintypes.WORD), ("nChannels", wintypes.WORD), ("nSamplesPerSec", wintypes.DWORD),
                ("nAvgBytesPerSec", wintypes.DWORD), ("nBlockAlign", wintypes.WORD),
                ("wBitsPerSample", wintypes.WORD), ("cbSize", wintypes.WORD)]


class _WAVEHDR(ctypes.Structure):
    _fields_ = [("lpData", ctypes.c_void_p), ("dwBufferLength", wintypes.DWORD),
                ("dwBytesRecorded", wintypes.DWORD), ("dwUser", ctypes.c_size_t), ("dwFlags", wintypes.DWORD),
                ("dwLoops", wintypes.DWORD), ("lpNext", ctypes.c_void_p), ("reserved", ctypes.c_size_t)]


class _CAPS(ctypes.Structure):
    _fields_ = [("wMid", wintypes.WORD), ("wPid", wintypes.WORD), ("vDriverVersion", wintypes.UINT),
                ("szPname", ctypes.c_wchar * 32), ("dwFormats", wintypes.DWORD), ("wChannels", wintypes.WORD),
                ("wReserved1", wintypes.WORD)]


class MicLevel(QObject):
    """Seçili mikrofonun anlık seviyesi (0–1). DirectShow adı waveIn adıyla (31 harfe kırpılmış) eşlenir."""
    level = pyqtSignal(float)
    RATE, CHUNK, NBUF = 16000, 800, 4      # 50 ms'lik parçalar

    def __init__(self, parent=None):
        super().__init__(parent)
        self.h = None
        self.hdrs = []
        self.bufs = []
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self._poll)
        try:
            self.w = ctypes.WinDLL("winmm")
        except OSError:
            self.w = None

    @staticmethod
    def _device_id(w, name):
        n = w.waveInGetNumDevs()
        for i in range(n):
            c = _CAPS()
            if w.waveInGetDevCapsW(i, byref(c), ctypes.sizeof(c)) == 0:
                pn = c.szPname.strip()
                if pn and (name == pn or name.startswith(pn)):
                    return i
        return None

    def start(self, name):
        self.stop()
        if self.w is None or not name:
            return False
        dev = self._device_id(self.w, name)
        if dev is None:
            return False
        wf = _WFX(1, 1, self.RATE, self.RATE * 2, 2, 16, 0)
        h = ctypes.c_void_p()
        if self.w.waveInOpen(byref(h), ctypes.c_uint(dev), byref(wf), None, None, 0) != 0:
            return False
        self.h = h
        sz = ctypes.sizeof(_WAVEHDR)
        for _ in range(self.NBUF):
            b = ctypes.create_string_buffer(self.CHUNK * 2)
            hd = _WAVEHDR(ctypes.cast(b, ctypes.c_void_p), self.CHUNK * 2, 0, 0, 0, 0, None, 0)
            self.w.waveInPrepareHeader(h, byref(hd), sz)
            self.w.waveInAddBuffer(h, byref(hd), sz)
            self.bufs.append(b)
            self.hdrs.append(hd)
        self.w.waveInStart(h)
        self.timer.start()
        return True

    def _poll(self):
        if self.h is None:
            return
        peak = 0
        sz = ctypes.sizeof(_WAVEHDR)
        for hd, b in zip(self.hdrs, self.bufs):
            if hd.dwFlags & 1:      # WHDR_DONE
                a = array("h", b.raw[:hd.dwBytesRecorded])
                if a:
                    peak = max(peak, max(a), -min(a))
                hd.dwFlags &= ~1
                self.w.waveInAddBuffer(self.h, byref(hd), sz)
        self.level.emit(min(1.0, peak / 32768.0))

    def stop(self):
        self.timer.stop()
        if self.h is not None and self.w is not None:
            sz = ctypes.sizeof(_WAVEHDR)
            self.w.waveInReset(self.h)
            for hd in self.hdrs:
                self.w.waveInUnprepareHeader(self.h, byref(hd), sz)
            self.w.waveInClose(self.h)
        self.h = None
        self.hdrs, self.bufs = [], []


class LevelMeter(QWidget):
    """İnce seviye çubuğu: dB ölçeği (−60 … 0), tepe noktası yavaş düşer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(6)
        self.v = 0.0
        self.peak = 0.0

    def set_level(self, lin):
        import math
        db = 20 * math.log10(lin) if lin > 1e-5 else -100
        v = max(0.0, min(1.0, (db + 60) / 60))
        self.v = max(v, self.v * 0.7)
        self.peak = max(v, self.peak - 0.02)
        self.update()

    def clear(self):
        self.v = self.peak = 0.0
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qcolor("surface_hover"))
        p.drawRoundedRect(r, 3, 3)
        if self.v > 0:
            w = r.width() * self.v
            p.setBrush(QColor("#ff3b3b") if self.v > 0.93 else qcolor("text2"))
            p.drawRoundedRect(QRectF(r.x(), r.y(), w, r.height()), 3, 3)
        if self.peak > 0.01:
            x = r.x() + r.width() * self.peak
            p.setBrush(qcolor("text"))
            p.drawRect(QRectF(min(x, r.right() - 2), r.y(), 2, r.height()))


class Seg(QWidget):
    """Seçmeli düğme dizisi (Chip stili)."""
    changed = pyqtSignal(object)

    def __init__(self, items, current, parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.keys = []
        for key, label in items:
            b = QPushButton(label)
            b.setObjectName("Chip")
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setChecked(key == current)
            b.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            self.group.addButton(b, len(self.keys))
            self.keys.append(key)
            lay.addWidget(b)
        self.group.idClicked.connect(lambda i: self.changed.emit(self.keys[i]))

    def value(self):
        i = self.group.checkedId()
        return self.keys[i] if i >= 0 else None

    def set_value(self, key):
        if key in self.keys:
            self.group.button(self.keys.index(key)).setChecked(True)


class CamPreview(QWidget):
    """Kameranın canlı önizlemesi: ffmpeg küçük boyutta ham RGB kare verir (QtMultimedia pakette yok).
    Şekil, kenarlık ve siyah beyaz kayıttakiyle aynı yoldan (recorder.cam_path) çizilir."""
    W, H = 400, 172

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(self.W, self.H)
        self.proc = None
        self.buf = bytearray()
        self.img = None
        self.size = (0, 0)
        self.dev = ""
        self.shape = "circle"
        self.border = "none"
        self.gray = False
        self.error = False

    def configure(self, dev=None, shape=None, border=None, gray=None):
        restart = False
        if dev is not None and dev != self.dev:
            self.dev, restart = dev, True
        if shape is not None and shape != self.shape:
            self.shape, restart = shape, True
        if border is not None:
            self.border = border
        if gray is not None:
            self.gray = gray
        if restart and self.proc is not None:
            self.start()
        self.update()

    def start(self):
        self.stop()
        self.error = False
        ff = find_ffmpeg()
        if not ff or not self.dev:
            self.error = True
            self.update()
            return
        pw, ph = (256, 144) if self.shape == "rect" else (160, 160)
        self.size = (pw, ph)
        self.buf = bytearray()
        self.img = None
        p = QProcess(self)
        p.setProgram(ff)
        p.setArguments(["-hide_banner", "-loglevel", "error", "-f", "dshow", "-i", f"video={self.dev}",
                        "-vf", f"{cam_crop(self.shape)},scale={pw}:{ph},fps=15", "-f", "rawvideo",
                        "-pix_fmt", "rgb24", "-"])
        p.readyReadStandardOutput.connect(lambda: self._read(p))
        p.finished.connect(lambda *_: self._ended(p))
        self.proc = p
        p.start()
        self.update()

    def _read(self, p):
        if p is not self.proc:
            return
        self.buf += bytes(p.readAllStandardOutput())
        pw, ph = self.size
        n = pw * ph * 3
        if len(self.buf) >= n:
            k = len(self.buf) // n
            frame = bytes(self.buf[(k - 1) * n:k * n])
            del self.buf[:k * n]
            self.img = QImage(frame, pw, ph, pw * 3, QImage.Format.Format_RGB888).copy()
            self.update()

    def _ended(self, p):
        if p is self.proc:
            self.proc = None
            if self.img is None:
                self.error = True      # kamera açılamadı (başka uygulama kullanıyor olabilir)
            self.update()

    def stop(self):
        """Kamerayı bırak (kayıt aynı kamerayı açacak): süreç bitene kadar bekler."""
        p, self.proc = self.proc, None
        if p is not None:
            p.kill()
            p.waitForFinished(2000)
            p.deleteLater()
        self.img = None

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(qcolor("surface"))
        p.drawRoundedRect(r, 10, 10)
        if self.shape == "rect":
            w, h = 208.0, 117.0
        else:
            w = h = 124.0
        ox, oy = (self.W - w) / 2, (self.H - h) / 2
        p.translate(ox, oy)
        path = cam_path(self.shape, w, h)
        if self.border == "shadow":
            key = (self.shape, w, h)
            if getattr(self, "_shadow_key", None) != key:
                self._shadow_key, self._shadow = key, shadow_image(self.shape, round(w), round(h))
            pad, _dy = shadow_pad(round(w), round(h))
            p.drawImage(QPointF(-pad, -pad), self._shadow)
        if self.img is not None:
            img = self.img.convertToFormat(QImage.Format.Format_Grayscale8) if self.gray else self.img
            p.save()
            p.setClipPath(path)
            p.drawImage(QRectF(0, 0, w, h), img)
            p.restore()
        else:
            p.setBrush(qcolor("surface_hover"))
            p.drawPath(path)
            p.setPen(qcolor("text2"))
            f = self.font()
            f.setPixelSize(12)
            p.setFont(f)
            p.drawText(QRectF(4, 0, w - 8, h), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                       t("rp_prev_err") if self.error else t("rp_prev_wait"))
        if self.border != "none":
            col, bw = rim_style(self.border, w, h)
            bw = bw * 1.2 if self.border != "shadow" else bw
            p.setPen(QPen(col, bw))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(cam_path(self.shape, w, h, bw / 2))


def swatch_icon(col, size=18):
    dpr = 2.0
    pm = QPixmap(round(size * dpr), round(size * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(128, 128, 128, 160), 1))
    p.setBrush(QColor(col))
    p.drawEllipse(QRectF(1.5, 1.5, size - 3, size - 3))
    p.end()
    return pm


def corner_icon(pos, fg, size=20):
    """Küçük ekran çerçevesi, kameranın duracağı köşede dolu daire."""
    dpr = 2.0
    pm = QPixmap(round(size * dpr), round(size * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = QRectF(1.5, 3.5, size - 3, size - 7)
    p.setPen(QPen(QColor(fg), 1.4))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(r, 2.5, 2.5)
    rad = 2.8
    cx = r.left() + 3.6 if pos[1] == "l" else r.right() - 3.6
    cy = r.top() + 3.6 if pos[0] == "t" else r.bottom() - 3.6
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(fg))
    p.drawEllipse(QPointF(cx, cy), rad, rad)
    p.end()
    return pm


class RecordPanel(ThemedDialog):
    start_req = pyqtSignal(dict)

    def __init__(self, settings_only=False, parent=None):
        super().__init__(parent, t("rp_title"))
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.settings_only = settings_only
        self.setFixedWidth(460)
        cfg = rec_config()
        cams, mics = list_devices()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 16, 22, 18)
        lay.setSpacing(8)
        self._icons = []

        def head(icon, title, right=None, sub=None):
            row = QHBoxLayout()
            row.setSpacing(10)
            ic = QLabel()
            ic.setFixedWidth(20)
            self._icons.append((ic, icon))
            row.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop if sub else Qt.AlignmentFlag.AlignVCenter)
            box = QVBoxLayout()
            box.setSpacing(1)
            lb = QLabel(title)
            lb.setObjectName("RpHead")
            box.addWidget(lb)
            if sub:
                s = QLabel(sub)
                s.setObjectName("Secondary")
                s.setWordWrap(True)
                box.addWidget(s)
            row.addLayout(box, 1)
            if right is not None:
                row.addWidget(right, 0, Qt.AlignmentFlag.AlignVCenter)
            lay.addSpacing(6)
            lay.addLayout(row)

        def indent(w):
            row = QHBoxLayout()
            row.setContentsMargins(30, 0, 0, 0)
            row.addWidget(w, 1)
            lay.addLayout(row)
            return row

        # --- Sahne
        self.seg_scene = Seg([("area", t("rp_area")), ("screen", t("rp_screen"))], cfg["scene"])
        self.seg_scene.changed.connect(self._scene_changed)
        head("monitor", t("rp_scene"), self.seg_scene)
        self.c_screen = QComboBox()
        scrs = QGuiApplication.screens()
        for i, s in enumerate(scrs):
            g = s.geometry()
            dpr = s.devicePixelRatio()
            self.c_screen.addItem(t("rp_screen_n", n=i + 1, w=round(g.width() * dpr), h=round(g.height() * dpr)),
                                  s.name())
        i = self.c_screen.findData(cfg["screen"])
        self.c_screen.setCurrentIndex(max(0, i))
        self.c_screen.currentIndexChanged.connect(lambda: prefs.set("rec_screen", self.c_screen.currentData()))
        self._screen_row = QWidget()
        r = QHBoxLayout(self._screen_row)
        r.setContentsMargins(30, 0, 0, 0)
        r.addWidget(self.c_screen, 1)
        lay.addWidget(self._screen_row)
        self._multi_screen = len(scrs) > 1

        # --- Kamera
        self.sw_cam = ToggleSwitch(cfg["cam"] and bool(cams))
        self.sw_cam.setEnabled(bool(cams))
        self.sw_cam.toggled.connect(self._cam_toggled)
        head("videocam", t("rp_cam"), self.sw_cam, None if cams else t("rp_no_cam"))
        self.cam_box = QWidget()
        cbv = QVBoxLayout(self.cam_box)
        cbv.setContentsMargins(30, 0, 0, 0)
        cbv.setSpacing(8)
        cb = QHBoxLayout()
        cb.setSpacing(8)
        cbv.addLayout(cb)
        self.c_cam = QComboBox()
        for c in cams:
            self.c_cam.addItem(c, c)
        i = self.c_cam.findData(cfg["cam_dev"])
        self.c_cam.setCurrentIndex(max(0, i))
        self.c_cam.currentIndexChanged.connect(self._cam_dev_changed)
        cb.addWidget(self.c_cam, 1)
        self.seg_corner = Seg([(k, "") for k in ("tl", "tr", "bl", "br")], cfg["cam_pos"])
        for b in self.seg_corner.group.buttons():
            b.setFixedSize(36, 30)
            b.setProperty("corner", "1")
            b.setIconSize(QSize(20, 20))
        self.seg_corner.setToolTip(t("rp_cam_pos"))
        self.seg_corner.changed.connect(lambda v: prefs.set("rec_cam_pos", v))
        cb.addWidget(self.seg_corner)
        # şekil + siyah beyaz
        r2 = QHBoxLayout()
        r2.setSpacing(8)
        self.seg_shape = Seg([(k, t("rp_shape_" + k)) for k in CAM_SHAPES], cfg["cam_shape"])
        self.seg_shape.changed.connect(self._shape_changed)
        r2.addWidget(self.seg_shape)
        r2.addStretch(1)
        gl = QLabel(t("rp_gray"))
        r2.addWidget(gl)
        self.sw_gray = ToggleSwitch(cfg["cam_gray"])
        self.sw_gray.toggled.connect(self._gray_changed)
        r2.addWidget(self.sw_gray)
        cbv.addLayout(r2)
        # kenarlık: yok · gölge · renkler
        r2b = QHBoxLayout()
        r2b.setSpacing(8)
        bl = QLabel(t("rp_border"))
        bl.setObjectName("Secondary")
        r2b.addWidget(bl)
        r2b.addStretch(1)
        names = {"none": t("rp_border_none"), "shadow": t("rp_border_shadow")}
        self.seg_border = Seg([(k, names.get(k, "")) for k in CAM_BORDERS], cfg["cam_border"])
        for k, b in zip(self.seg_border.keys, self.seg_border.group.buttons()):
            if k not in names:
                b.setFixedSize(30, 30)
                b.setProperty("corner", "1")
                b.setIconSize(QSize(18, 18))
                b.setIcon(QIcon(swatch_icon(k)))
        self.seg_border.setToolTip(t("rp_border"))
        self.seg_border.changed.connect(self._border_changed)
        r2b.addWidget(self.seg_border)
        cbv.addLayout(r2b)
        # önizleme
        self.preview = CamPreview()
        self.preview.configure(self.c_cam.currentData() or "", cfg["cam_shape"], cfg["cam_border"], cfg["cam_gray"])
        cbv.addWidget(self.preview)
        lay.addWidget(self.cam_box)

        # --- Mikrofon
        self.sw_mic = ToggleSwitch(cfg["mic"] and bool(mics))
        self.sw_mic.setEnabled(bool(mics))
        self.sw_mic.toggled.connect(self._mic_toggled)
        head("mic", t("rp_mic"), self.sw_mic, None if mics else t("rp_no_mic"))
        self.mic_box = QWidget()
        mb = QVBoxLayout(self.mic_box)
        mb.setContentsMargins(30, 0, 0, 0)
        mb.setSpacing(6)
        self.c_mic = QComboBox()
        for m in mics:
            self.c_mic.addItem(m, m)
        i = self.c_mic.findData(cfg["mic_dev"])
        self.c_mic.setCurrentIndex(max(0, i))
        self.c_mic.currentIndexChanged.connect(self._mic_dev_changed)
        mb.addWidget(self.c_mic)
        self.meter = LevelMeter()
        mb.addWidget(self.meter)
        lay.addWidget(self.mic_box)
        self.level = MicLevel(self)
        self.level.level.connect(self.meter.set_level)

        # --- Bilgisayar sesi
        self.sw_sys = ToggleSwitch(cfg["sys"])
        self.sw_sys.toggled.connect(lambda v: prefs.set("rec_sys", v))
        head("volume", t("rp_sys"), self.sw_sys, t("rp_sys_sub"))

        # --- Görüntü
        self.c_res = QComboBox()
        for k in RESOLUTIONS:
            self.c_res.addItem(t("rp_res_" + k), k)
        self.c_res.setCurrentIndex(max(0, self.c_res.findData(cfg["res"])))
        self.c_res.currentIndexChanged.connect(lambda: prefs.set("rec_res", self.c_res.currentData()))
        head("hd", t("rp_video"))
        vrow = QHBoxLayout()
        vrow.setContentsMargins(30, 0, 0, 0)
        vrow.setSpacing(8)
        vrow.addWidget(self.c_res, 1)
        self.seg_fps = Seg([(f, f"{f} fps") for f in FPS_CHOICES], cfg["fps"])
        self.seg_fps.changed.connect(lambda v: prefs.set("record_fps", v))
        vrow.addWidget(self.seg_fps)
        lay.addLayout(vrow)

        # --- Geri sayım
        self.seg_cd = Seg([(n, t("rp_cd_off") if n == 0 else f"{n} sn") for n in COUNTDOWNS], cfg["countdown"])
        self.seg_cd.changed.connect(lambda v: prefs.set("rec_countdown", v))
        head("timer", t("rp_countdown"), self.seg_cd)

        # --- alt
        lay.addSpacing(10)
        lay.addWidget(Divider())
        lay.addSpacing(6)
        foot = QHBoxLayout()
        foot.setSpacing(8)
        self.dir_lbl = QPushButton(icons.icon("folder", color("text2"), 16), " " + self._short_dir())
        self.dir_lbl.setObjectName("Flat")
        self.dir_lbl.setToolTip(t("video_folder_sub") + "\n" + video_dir())
        self.dir_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dir_lbl.clicked.connect(self._open_dir)
        foot.addWidget(self.dir_lbl)
        foot.addStretch(1)
        if settings_only:
            ok = QPushButton(t("ok"))
            ok.setObjectName("Primary")
            ok.clicked.connect(self.accept)
            foot.addWidget(ok)
            self.b_start = ok
        else:
            cancel = QPushButton(t("rp_cancel"))
            cancel.setObjectName("Flat")
            cancel.clicked.connect(self.reject)
            foot.addWidget(cancel)
            self.b_start = QPushButton(t("rec_start"))
            self.b_start.setObjectName("Primary")
            self.b_start.setToolTip("Enter")
            self.b_start.clicked.connect(self._go)
            foot.addWidget(self.b_start)
        for b in (self.b_start, self.dir_lbl):
            b.setCursor(Qt.CursorShape.PointingHandCursor)
        self.b_start.setDefault(True)
        lay.addLayout(foot)

        self.setStyleSheet("QLabel#RpHead { font-size: 14px; font-weight: 600; }"
                           "QPushButton#Chip { min-width: 0px; padding: 6px 11px; border-radius: 8px; }"
                           "QPushButton#Chip[corner=\"1\"] { padding: 0px; }")
        theme.bind(self, lambda d: d._recolor())
        self._recolor()
        self._scene_changed(cfg["scene"], save=False)
        self.cam_box.setVisible(self.sw_cam.isChecked())
        self.mic_box.setVisible(self.sw_mic.isChecked())

    # --- yardımcılar
    def _recolor(self):
        for lb, name in self._icons:
            lb.setPixmap(icons.pixmap(name, color("text2"), 20))
        for key, b in zip(self.seg_corner.keys, self.seg_corner.group.buttons()):
            ic = QIcon()
            ic.addPixmap(corner_icon(key, color("text2")), QIcon.Mode.Normal, QIcon.State.Off)
            ic.addPixmap(corner_icon(key, color("chip_active_fg")), QIcon.Mode.Normal, QIcon.State.On)
            b.setIcon(ic)
        self._update_start_icon()

    def _update_start_icon(self):
        if not self.settings_only:
            self.b_start.setIcon(icons.icon("videocam", color("button_fg"), 18))

    @staticmethod
    def _short_dir():
        import os
        d = video_dir()
        parts = os.path.normpath(d).split(os.sep)
        return "\\".join(parts[-2:]) if len(parts) >= 2 else d

    def _open_dir(self):
        import os
        try:
            os.startfile(video_dir())
        except OSError:
            pass

    def _scene_changed(self, v, save=True):
        if save:
            prefs.set("rec_scene", v)
        self._screen_row.setVisible(v == "screen" and self._multi_screen)
        self.adjustSize()

    def _cam_toggled(self, v):
        prefs.set("rec_cam", v)
        if v and not prefs.get("rec_cam_dev", ""):
            prefs.set("rec_cam_dev", self.c_cam.currentData() or "")
        self.cam_box.setVisible(v)
        self._preview_restart()
        self.adjustSize()

    def _cam_dev_changed(self):
        prefs.set("rec_cam_dev", self.c_cam.currentData() or "")
        self.preview.configure(dev=self.c_cam.currentData() or "")
        self._preview_restart()

    def _shape_changed(self, v):
        prefs.set("rec_cam_shape", v)
        self.preview.configure(shape=v)

    def _border_changed(self, v):
        prefs.set("rec_cam_border", v)
        self.preview.configure(border=v)

    def _gray_changed(self, v):
        prefs.set("rec_cam_gray", v)
        self.preview.configure(gray=v)

    def _preview_restart(self):
        if self.sw_cam.isChecked() and self.isVisible():
            if self.preview.proc is None:
                self.preview.start()
        else:
            self.preview.stop()
            self.preview.update()

    def _mic_toggled(self, v):
        prefs.set("rec_mic_on", v)
        if v and not prefs.get("record_mic", ""):
            prefs.set("record_mic", self.c_mic.currentData() or "")
        self.mic_box.setVisible(v)
        self._meter_restart()
        self.adjustSize()

    def _mic_dev_changed(self):
        prefs.set("record_mic", self.c_mic.currentData() or "")
        self._meter_restart()

    def _meter_restart(self):
        self.level.stop()
        self.meter.clear()
        if self.sw_mic.isChecked() and self.isVisible():
            self.level.start(self.c_mic.currentData() or "")

    def config(self):
        cfg = rec_config()
        if cfg["scene"] == "screen" and not self._multi_screen:
            cfg["screen"] = ""
        return cfg

    def _release(self):
        self.level.stop()
        self.preview.stop()

    def _go(self):
        cfg = self.config()
        self._release()
        self.start_req.emit(cfg)     # önce: kapanış işleyicisi kaydın başladığını bilsin
        self.accept()

    # --- olaylar
    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, self._meter_restart)
        QTimer.singleShot(0, self._preview_restart)
        self.raise_()
        self.activateWindow()

    def done(self, r):
        self._release()
        super().done(r)

    def closeEvent(self, e):
        self._release()
        super().closeEvent(e)


def screen_for(cfg):
    """Tüm ekran kaydında hangi ekran: seçilen ad, yoksa farenin olduğu ekran."""
    from PyQt6.QtGui import QCursor
    name = cfg.get("screen", "")
    for s in QGuiApplication.screens():
        if name and s.name() == name:
            return s
    return QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()


_ = POINTER
