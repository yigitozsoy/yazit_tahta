"""Sistem sesi (bilgisayardan çıkan ses): WASAPI loopback, yalnızca ctypes ile (ek paket yok).

ffmpeg'in Windows'ta hoparlör sesini alan bir girişi yok. Burada varsayılan çıkış aygıtının karışımı
loopback modunda okunur ve adlandırılmış bir boruya (\\\\.\\pipe\\...) ham PCM olarak yazılır; ffmpeg o boruyu
ses girişi olarak okur (mikrofonla aynı anda, amix ile karışır).

Hiçbir şey çalmazken loopback paket vermez → videoda ses boşluğu ve kayma olurdu. Bunu önlemek için aynı aygıta
sessizlik çalan bir akış açılır (OBS de böyle yapar): loopback hep düzenli paket üretir.
"""
import ctypes
import threading
import time
import uuid
from ctypes import wintypes, POINTER, byref, c_void_p, c_uint32, c_uint64, c_int64

ole32 = ctypes.WinDLL("ole32")
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

HRESULT = ctypes.c_long


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD), ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8)]

    def __init__(self, s):
        super().__init__()
        u = uuid.UUID(s)
        self.Data1, self.Data2, self.Data3 = u.fields[0], u.fields[1], u.fields[2]
        for i, b in enumerate(u.bytes[8:]):
            self.Data4[i] = b


class WAVEFORMATEX(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("wFormatTag", wintypes.WORD), ("nChannels", wintypes.WORD), ("nSamplesPerSec", wintypes.DWORD),
                ("nAvgBytesPerSec", wintypes.DWORD), ("nBlockAlign", wintypes.WORD),
                ("wBitsPerSample", wintypes.WORD), ("cbSize", wintypes.WORD)]


class WAVEFORMATEXTENSIBLE(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("Format", WAVEFORMATEX), ("wValidBitsPerSample", wintypes.WORD),
                ("dwChannelMask", wintypes.DWORD), ("SubFormat", GUID)]


CLSID_MMDeviceEnumerator = GUID("BCDE0395-E52F-467C-8E3D-C4579291692E")
IID_IMMDeviceEnumerator = GUID("A95664D2-9614-4F35-A746-DE8DB63617E6")
IID_IAudioClient = GUID("1CB9AD4C-DBFA-4C32-B178-C2F568A703B2")
IID_IAudioCaptureClient = GUID("C8ADBD64-E71E-48A0-A4DE-185C395CD317")
IID_IAudioRenderClient = GUID("F294ACFC-3146-4483-A7BF-ADDCA7C260E2")
KSDATAFORMAT_SUBTYPE_IEEE_FLOAT = uuid.UUID("00000003-0000-0010-8000-00aa00389b71")

CLSCTX_ALL = 23
COINIT_MULTITHREADED = 0
eRender, eConsole = 0, 0
AUDCLNT_SHAREMODE_SHARED = 0
AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
AUDCLNT_BUFFERFLAGS_SILENT = 0x2
REFTIMES_PER_SEC = 10_000_000

PIPE_ACCESS_OUTBOUND = 0x2
INVALID_HANDLE = wintypes.HANDLE(-1).value
GENERIC_READ = 0x80000000
OPEN_EXISTING = 3

kernel32.CreateNamedPipeW.restype = wintypes.HANDLE
kernel32.CreateNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD,
                                      wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, c_void_p]
kernel32.ConnectNamedPipe.argtypes = [wintypes.HANDLE, c_void_p]
kernel32.WriteFile.argtypes = [wintypes.HANDLE, c_void_p, wintypes.DWORD, POINTER(wintypes.DWORD), c_void_p]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, c_void_p, wintypes.DWORD,
                                 wintypes.DWORD, wintypes.HANDLE]
kernel32.DisconnectNamedPipe.argtypes = [wintypes.HANDLE]
ole32.CoCreateInstance.argtypes = [POINTER(GUID), c_void_p, wintypes.DWORD, POINTER(GUID), POINTER(c_void_p)]
ole32.CoInitializeEx.argtypes = [c_void_p, wintypes.DWORD]
ole32.CoTaskMemFree.argtypes = [c_void_p]


def _call(obj, idx, *args, argtypes=()):
    """COM arayüzünün vtable'ındaki idx. yöntemi çağırır; başarısızsa OSError."""
    vt = ctypes.cast(obj, POINTER(POINTER(c_void_p)))[0]
    fn = ctypes.WINFUNCTYPE(HRESULT, c_void_p, *argtypes)(vt[idx])
    hr = fn(obj, *args)
    if hr < 0:
        raise OSError(f"WASAPI 0x{hr & 0xFFFFFFFF:08X}")
    return hr


def _release(obj):
    if obj:
        try:
            vt = ctypes.cast(obj, POINTER(POINTER(c_void_p)))[0]
            ctypes.WINFUNCTYPE(wintypes.ULONG, c_void_p)(vt[2])(obj)
        except Exception:
            pass


def _client(dev):
    ac = c_void_p()
    _call(dev, 3, byref(IID_IAudioClient), CLSCTX_ALL, None, byref(ac),
          argtypes=(POINTER(GUID), wintypes.DWORD, c_void_p, POINTER(c_void_p)))
    return ac


def _sample_fmt(wf_ptr):
    wf = ctypes.cast(wf_ptr, POINTER(WAVEFORMATEX))[0]
    is_float = wf.wFormatTag == 3
    if wf.wFormatTag == 0xFFFE and wf.cbSize >= 22:
        ext = ctypes.cast(wf_ptr, POINTER(WAVEFORMATEXTENSIBLE))[0]
        sub = ext.SubFormat
        u = uuid.UUID(fields=(sub.Data1, sub.Data2, sub.Data3, sub.Data4[0], sub.Data4[1],
                              int.from_bytes(bytes(sub.Data4[2:]), "big")))
        is_float = u == KSDATAFORMAT_SUBTYPE_IEEE_FLOAT
    bits = wf.wBitsPerSample
    fmt = "f32le" if is_float and bits == 32 else {16: "s16le", 24: "s24le", 32: "s32le"}.get(bits)
    return fmt, wf.nSamplesPerSec, wf.nChannels, wf.nBlockAlign


class Loopback:
    """Kullanım: lb = Loopback(); fmt = lb.open()  (ffmpeg girdisi: lb.input_args())  ...  lb.close()

    open() iş parçacığını başlatır, aygıtın biçimini öğrenip döner (bulunamazsa None). Boru ffmpeg bağlanınca
    yazılmaya başlar — ondan önce gelen ses atılır, yoksa ses görüntünün önüne geçerdi."""

    def __init__(self):
        self.name = rf"\\.\pipe\yazit-sys-{uuid.uuid4().hex[:12]}"
        self.fmt = None          # (ffmpeg biçimi, örnekleme hızı, kanal)
        self.error = ""
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._pipe = None
        self._connected = False
        self._thread = None

    def open(self, timeout=3.0):
        self._thread = threading.Thread(target=self._run, name="yazit-loopback", daemon=True)
        self._thread.start()
        self._ready.wait(timeout)
        return self.fmt

    def input_args(self):
        f, rate, ch = self.fmt
        return ["-thread_queue_size", "1024", "-f", f, "-ar", str(rate), "-ac", str(ch), "-i", self.name]

    def close(self):
        self._stop.set()
        if self._pipe and not self._connected:
            # ConnectNamedPipe'ta bekleyen iş parçacığını çöz: boruya kendimiz bağlanırız
            h = kernel32.CreateFileW(self.name, GENERIC_READ, 0, None, OPEN_EXISTING, 0, None)
            if h and h != INVALID_HANDLE:
                kernel32.CloseHandle(h)
        if self._thread is not None:
            self._thread.join(2.0)

    # --- iş parçacığı
    def _run(self):
        ole32.CoInitializeEx(None, COINIT_MULTITHREADED)
        enum = dev = cap_ac = cap = ren_ac = ren = None
        wf = c_void_p()
        try:
            enum = c_void_p()
            hr = ole32.CoCreateInstance(byref(CLSID_MMDeviceEnumerator), None, CLSCTX_ALL,
                                        byref(IID_IMMDeviceEnumerator), byref(enum))
            if hr < 0:
                raise OSError(f"MMDeviceEnumerator 0x{hr & 0xFFFFFFFF:08X}")
            dev = c_void_p()
            _call(enum, 4, eRender, eConsole, byref(dev),
                  argtypes=(ctypes.c_int, ctypes.c_int, POINTER(c_void_p)))
            cap_ac = _client(dev)
            _call(cap_ac, 8, byref(wf), argtypes=(POINTER(c_void_p),))
            fmt, rate, ch, block = _sample_fmt(wf)
            if not fmt:
                raise OSError("desteklenmeyen ses biçimi")
            _call(cap_ac, 3, AUDCLNT_SHAREMODE_SHARED, AUDCLNT_STREAMFLAGS_LOOPBACK, c_int64(REFTIMES_PER_SEC),
                  c_int64(0), wf, None,
                  argtypes=(ctypes.c_int, wintypes.DWORD, c_int64, c_int64, c_void_p, c_void_p))
            cap = c_void_p()
            _call(cap_ac, 14, byref(IID_IAudioCaptureClient), byref(cap), argtypes=(POINTER(GUID), POINTER(c_void_p)))
            # sessizlik çalan akış: loopback hiçbir şey çalmazken de düzenli paket versin
            try:
                ren_ac = _client(dev)
                _call(ren_ac, 3, AUDCLNT_SHAREMODE_SHARED, 0, c_int64(REFTIMES_PER_SEC), c_int64(0), wf, None,
                      argtypes=(ctypes.c_int, wintypes.DWORD, c_int64, c_int64, c_void_p, c_void_p))
                ren = c_void_p()
                _call(ren_ac, 14, byref(IID_IAudioRenderClient), byref(ren),
                      argtypes=(POINTER(GUID), POINTER(c_void_p)))
                rbuf = c_uint32()
                _call(ren_ac, 4, byref(rbuf), argtypes=(POINTER(c_uint32),))
                _call(ren_ac, 10)
            except OSError:
                _release(ren)
                _release(ren_ac)
                ren = ren_ac = None
            self._pipe = kernel32.CreateNamedPipeW(self.name, PIPE_ACCESS_OUTBOUND, 0, 1, 1 << 20, 0, 0, None)
            if not self._pipe or self._pipe == INVALID_HANDLE:
                self._pipe = None
                raise OSError("boru açılamadı")
            self.fmt = (fmt, rate, ch)
        except OSError as e:
            self.error = str(e)
            self.fmt = None
        finally:
            self._ready.set()
        try:
            if self.fmt is None:
                return
            kernel32.ConnectNamedPipe(self._pipe, None)   # ffmpeg girişi açana kadar bekler
            self._connected = True
            if self._stop.is_set():
                return
            _call(cap_ac, 10)   # Start
            n = c_uint32()
            data = c_void_p()
            flags = wintypes.DWORD()
            written = wintypes.DWORD()
            while not self._stop.is_set():
                if ren is not None:
                    self._feed_silence(ren_ac, ren, rbuf.value)
                time.sleep(0.01)
                while True:
                    _call(cap, 5, byref(n), argtypes=(POINTER(c_uint32),))
                    if n.value == 0:
                        break
                    _call(cap, 3, byref(data), byref(n), byref(flags), None, None,
                          argtypes=(POINTER(c_void_p), POINTER(c_uint32), POINTER(wintypes.DWORD), c_void_p, c_void_p))
                    size = n.value * block
                    if flags.value & AUDCLNT_BUFFERFLAGS_SILENT or not data:
                        buf = bytes(size)
                        ok = kernel32.WriteFile(self._pipe, buf, size, byref(written), None)
                    else:
                        ok = kernel32.WriteFile(self._pipe, data, size, byref(written), None)
                    _call(cap, 4, n.value, argtypes=(c_uint32,))
                    if not ok:          # ffmpeg boruyu kapattı (kayıt bitti)
                        self._stop.set()
                        break
        except OSError as e:
            self.error = str(e)
        finally:
            for ac in (cap_ac, ren_ac):
                if ac:
                    try:
                        _call(ac, 11)
                    except OSError:
                        pass
            for o in (cap, ren, cap_ac, ren_ac, dev, enum):
                _release(o)
            if wf:
                ole32.CoTaskMemFree(wf)
            if self._pipe:
                kernel32.DisconnectNamedPipe(self._pipe)
                kernel32.CloseHandle(self._pipe)
                self._pipe = None

    @staticmethod
    def _feed_silence(ac, ren, size):
        pad = c_uint32()
        _call(ac, 6, byref(pad), argtypes=(POINTER(c_uint32),))
        free = size - pad.value
        if free > 0:
            ptr = c_void_p()
            _call(ren, 3, free, byref(ptr), argtypes=(c_uint32, POINTER(c_void_p)))
            _call(ren, 4, free, AUDCLNT_BUFFERFLAGS_SILENT, argtypes=(c_uint32, wintypes.DWORD))


def available():
    """Sistem sesi alınabilir mi (varsayılan çıkış aygıtı var mı)? Kısa bir deneme yapar."""
    lb = Loopback()
    ok = lb.open(2.0) is not None
    lb.close()
    return ok


_ = c_uint64  # (GetBuffer konum işaretçileri kullanılmıyor)
