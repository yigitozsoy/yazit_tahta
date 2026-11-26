"""Uçtan uca test: gerçek arayüzü açar, fareyle çizer / siler / yazar, notu kaydedip geri okur.
Gerçek tercihlere dokunmaz (LOCALAPPDATA geçici klasöre yönlendirilir). Ekranın kendisini yakalamaz.

python tests/smoke_test.py [--shots KLASÖR]
"""
import math
import os
import sys
import tempfile

TMP = tempfile.mkdtemp(prefix="yazit_test_")
os.environ["LOCALAPPDATA"] = TMP
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtCore import Qt, QPoint, QPointF, QEvent, QRect, QRectF  # noqa: E402
from PyQt6.QtGui import QMouseEvent, QImage, QColor, QPixmap, QKeyEvent, QWheelEvent  # noqa: E402
from PyQt6.QtWidgets import QApplication, QScrollArea  # noqa: E402

SHOTS = sys.argv[sys.argv.index("--shots") + 1] if "--shots" in sys.argv else None
steps = []
L, R, M, NB = (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton,
               Qt.MouseButton.NoButton)
NOMOD, CTRL = Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.ControlModifier
PRESS, MOVE, REL, DBL = (QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove, QEvent.Type.MouseButtonRelease,
                         QEvent.Type.MouseButtonDblClick)


def step(name, ok):
    ok = bool(ok)
    steps.append((name, ok))
    print(("OK   " if ok else "FAIL ") + name, flush=True)


def pump(n=5):
    for _ in range(n):
        QApplication.processEvents()


def mouse(w, typ, pos, btn, btns, mods=NOMOD):
    pos = QPointF(pos)
    ev = QMouseEvent(typ, pos, QPointF(w.mapToGlobal(pos.toPoint())), btn, btns, mods)
    QApplication.sendEvent(w, ev)


def drag(w, pts, btn=L, mods=NOMOD):
    mouse(w, PRESS, pts[0], btn, btn, mods)
    for p in pts[1:]:
        mouse(w, MOVE, p, NB, btn, mods)
    mouse(w, REL, pts[-1], btn, NB, mods)
    pump()


def click(w, p, btn):
    mouse(w, PRESS, p, btn, btn)
    mouse(w, REL, p, btn, NB)
    pump()


def key(w, k, text="", mods=NOMOD):
    QApplication.sendEvent(w, QKeyEvent(QEvent.Type.KeyPress, k, mods, text))
    QApplication.sendEvent(w, QKeyEvent(QEvent.Type.KeyRelease, k, mods, text))
    pump()


def wheel(w, pos, delta, mods=NOMOD):
    ev = QWheelEvent(QPointF(pos), QPointF(w.mapToGlobal(pos)), QPoint(0, 0), delta, NB, mods,
                     Qt.ScrollPhase.NoScrollPhase, False)
    QApplication.sendEvent(w, ev)
    pump()


def make_sources(out):
    """Araştırma testi için örnek kaynaklar: ISBN'li PDF (kitap), 120 sayfalık PDF (kitap), kısa PDF (makale),
    docx (makale), md, jpg, .url."""
    import zipfile
    from PyQt6.QtGui import QPdfWriter, QPainter, QPageSize
    os.makedirs(out, exist_ok=True)
    text = ("Zırhlı araçların gelişimi siper çıkmazıyla başladı. Ogorkiewicz'e göre tank tasarımı üç temel "
            "özelliğin dengesidir: ateş gücü, koruma ve hareket kabiliyeti. ") * 3

    def pdf(name, pages, title, first=""):
        w = QPdfWriter(os.path.join(out, name))
        w.setPageSize(QPageSize(QPageSize.PageSizeId.A5))
        w.setTitle(title)
        w.setResolution(96)
        pt = QPainter(w)
        for i in range(pages):
            if i:
                w.newPage()
            pt.drawText(QRectF(40, 40, 480, 700), 0x1000 | 0x0001, (first if i == 0 else f"Sayfa {i + 1}\n") + text)
        pt.end()

    pdf("Ogorkiewicz - Tanks 100 Years.pdf", 12, "Tanks: 100 Years of Evolution",
        "Tanks: 100 Years of Evolution\nISBN 978-1-4728-0670-3\n\n")
    pdf("Technology of Tanks.pdf", 120, "Technology of Tanks")
    pdf("hull-armor.pdf", 5, "Composite Hull Armor")
    with zipfile.ZipFile(os.path.join(out, "reaktif.docx"), "w") as z:
        z.writestr("word/document.xml", '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/'
                   'wordprocessingml/2006/main"><w:body><w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>'
                   'Reaktif zırh</w:t></w:r></w:p><w:p><w:r><w:rPr><w:b/></w:rPr><w:t>ERA</w:t></w:r><w:r><w:t> ilk '
                   'kez 1982\'de kullanıldı.</w:t></w:r></w:p></w:body></w:document>')
        z.writestr("docProps/core.xml", '<?xml version="1.0"?><cp:coreProperties xmlns:cp="x" xmlns:dc="http://purl.org/'
                   'dc/elements/1.1/"><dc:title>Reaktif Zırh Notları</dc:title><dc:creator>Y. Özsoy</dc:creator>'
                   '</cp:coreProperties>')
    with open(os.path.join(out, "altay.md"), "w", encoding="utf-8") as f:
        f.write("# Altay özeti\n\nAltay ana muharebe tankıdır.\n")
    img = QImage(320, 200, QImage.Format.Format_RGB32)
    img.fill(QColor("#4a5a3a"))
    img.save(os.path.join(out, "leopard.jpg"))
    with open(os.path.join(out, "Tank Encyclopedia.url"), "w") as f:
        f.write("[InternetShortcut]\nURL=https://tanks-encyclopedia.com/\n")


def shot(widget, name):
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        widget.grab().save(os.path.join(SHOTS, name + ".png"))


def console_steps(d):
    """Geliştirici konsolu: Shift+" modu açar, " açar / kapatır, yazı alanında yazılır, komutlar, geçmiş, tamamlama.
    main() en sonda çağırır; kayıt / OCR adımları olmadan tek başına da çağrılabilir (offscreen sürücü betiği)."""
    import time
    from PyQt6.QtWidgets import QLineEdit
    from PyQt6.QtNetwork import QLocalServer
    import threading
    from yazit import cli, app as yapp
    from yazit.config import prefs
    from yazit.tools import state
    win = d.win
    con, keys = win.console, win.console_keys
    win.set_research_mode(False)
    pump()

    def ckey(shift=False, scan=41, k=Qt.Key.Key_QuoteDbl, text='"'):
        mods = Qt.KeyboardModifier.ShiftModifier if shift else NOMOD
        return QKeyEvent(QEvent.Type.KeyPress, k, mods, scan, 0, 0, text)

    def settle():
        for _ in range(40):
            pump(1)
            if con._anim is None or con._anim.state() != con._anim.State.Running:
                break
            time.sleep(0.01)
        pump()

    prefs.set("dev_mode", False)
    ok = not keys.handle(ckey()) and not con.is_open() and not keys.handle(ckey(scan=40))
    ok = ok and keys.handle(ckey(shift=True, k=Qt.Key.Key_Eacute, text="é"))
    settle()
    step("konsol: mod kapalıyken \" dokunmaz; Shift+\" modu açar ve konsol iner (başlık çubuğunun altında)",
         ok and prefs.get("dev_mode") and con.is_open() and con.height() > 100
         and con.geometry().top() >= win.titlebar.geometry().bottom())
    con.edit.setText("open ")
    con.edit.setFocus()
    pump()
    ok = True
    if QApplication.focusWidget() is con.edit:
        ok = not keys.handle(ckey())                 # komutun içinde " yazılır
        con.edit.clear()
        ok = ok and keys.handle(ckey())              # boş satırda " kapatır
    else:
        con.close_panel()
    settle()
    ok = ok and not con.is_open() and not con.isVisible()
    ok = ok and keys.handle(ckey(scan=0))            # yapay olay: tuş koduna bakılır
    settle()
    step("konsol: satırda \" yazılır, boş satırda \" kapatır, yapay olayda tuş koduna bakılır", ok and con.is_open())

    # komutlar
    n0 = len(d.store.sorted())
    code, out = con.execute("new")
    page = win.page
    con.execute('rename "Konsol notu"')
    ok_new = code == 0 and win.page.title == "Konsol notu"
    state.set_tool("pen")
    drag(win.board.viewport(), [QPoint(300, 300), QPoint(360, 330), QPoint(420, 300)])
    code, out = con.execute("status")
    ok_status = code == 0 and "Konsol notu" in out
    code, out = con.execute("notes konsol")
    ok_notes = code == 0 and "▶" in out and "Konsol notu" in out
    ok_tool = con.execute("tool text") == (0, "text") and state.tool == "text"
    ok_tool = ok_tool and con.execute("tool yokboyle")[0] == 1
    ok_color = con.execute("color red") == (0, "#ff453a") and con.execute("color 3")[1] == "#3ea6ff"
    ok_color = ok_color and con.execute("color mor")[0] == 1
    out_png = os.path.join(TMP, "konsol.png")
    code, out = con.execute(f'export png "{out_png}"')
    ok_exp = code == 0 and os.path.isfile(out_png)
    code, out = con.execute("undo")
    ok_undo = code == 0 and len(win.board.scene().content_items()) == 0
    con.execute("redo")
    ok_go = con.execute("go research") == (0, "research") and win.in_research()
    ok_go = ok_go and con.execute("go board") == (0, "board") and not win.in_research()
    other = next((p for p in d.store.sorted() if p is not page), None)
    if other is not None:
        con.execute(f"open {d.store.sorted().index(other) + 1}")
        ok_go = ok_go and win.page is other
        con.execute('open "Konsol notu"')
        ok_go = ok_go and win.page is page
    ok_err = con.execute("yokboyle")[0] == 2 and con.execute("open 999")[0] == 1
    ok_err = ok_err and con.execute('open "kapanmamış')[0] == 1 and con.execute("pref tool") == (0, '"text"')
    ok_err = ok_err and cli.run(None, ["notes"])[0] == 1 and cli.run(None, ["version"])[0] == 0
    step("konsol: new / rename / status / notes / tool / color / export / undo / go / open, hatalar",
         ok_new and ok_status and ok_notes and ok_tool and ok_color and ok_exp and ok_undo and ok_go and ok_err
         and len(d.store.sorted()) >= n0)
    # python -m yazit.cli yolu: gerçek yerel soket, app.serve (ayrı sunucu adı: kurulu yazıt'a gitmesin)
    reply = cli.handle_request(d, '["status"]')
    name = f"yazit-smoke-cli-{os.getpid()}"
    QLocalServer.removeServer(name)
    srv = QLocalServer()
    srv.listen(name)
    yapp.serve(srv, d)
    box = {}
    th = threading.Thread(target=lambda: box.update(r=cli.send(["tool"], name=name)))
    th.start()
    t0 = time.time()
    while th.is_alive() and time.time() - t0 < 6:
        pump(1)
        time.sleep(0.005)
    srv.close()
    step("konsol: komut satırı tek örnek sunucusundan cevap alır",
         b'"code": 0' in reply and box.get("r") == (0, state.tool))
    if SHOTS:
        con.execute("help")
        pump()
        shot(win, "70_konsol")
        theme_ = prefs.get("theme")
        con.execute("theme white")
        pump()
        shot(win, "71_konsol_acik")
        con.execute("theme " + theme_)
    con.execute("clear")
    ok = con.output_text() == ""
    con.edit.setText("not")
    con._complete()
    ok = ok and con.edit.text() == "notes "
    con.edit.setText("go res")
    con._complete()
    ok = ok and con.edit.text() == "go research "
    con.edit.setText("status")
    con._submit()
    ok = ok and prefs.get("console_history")[-1] == "status"
    con.edit.setText("")
    con.eventFilter(con.edit, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Up, NOMOD))
    ok = ok and con.edit.text() == "status"
    con.execute("exit")
    settle()
    ok = ok and not con.is_open()
    le = QLineEdit(win.area)
    le.show()
    le.setFocus()
    pump()
    if QApplication.focusWidget() is le:
        ok = ok and not keys.handle(ckey())          # yazı alanında " normal yazılır
    le.deleteLater()
    ok = ok and keys.handle(ckey(shift=True))        # Shift+" modu kapatır
    settle()
    step("konsol: clear, Tab tamamlama, ↑ geçmiş, exit; yazı alanında \" yazılır; Shift+\" modu kapatır",
         ok and not prefs.get("dev_mode") and not con.is_open())


def main():
    from yazit.config import prefs
    for n in ("capture", "annotate", "note", "record"):
        prefs.set("hotkey_" + n, "")  # testte gerçek kısayolları kapmayalım
    prefs.set("video_dir", os.path.join(TMP, "videos"))
    prefs.set("record_mic", "")
    for k, v in (("rec_mic_on", False), ("rec_cam", False), ("rec_sys", False), ("rec_countdown", 0),
                 ("rec_scene", "area"), ("rec_res", "src")):
        prefs.set(k, v)            # kamera / mikrofon testte açılmaz
    prefs.set("check_updates", False)   # testte ağa çıkma
    prefs.set("notes_dir", os.path.join(TMP, "notes"))       # gerçek Resimler\yazit'e dokunma
    prefs.set("snapshot_dir", os.path.join(TMP, "pictures"))
    prefs.set("research_dir", os.path.join(TMP, "res"))
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    from yazit.app import YazitApp
    from yazit import items as I
    from yazit.tools import state
    prefs.set("sidebar_visible", False)     # kapatılıp çıkılmış gibi: yine açık gelmeli
    d = YazitApp(app)
    win = d.win
    panel_at_start = not win.panel.isHidden()
    win.resize(1280, 800)
    pump(20)
    b = win.board
    vp = b.viewport()
    sc = b.scene()
    step("pencere açıldı, boş not", b.is_empty() and win.area.hint.isVisible())
    shot(win, "01_bos")

    state.set_tool("pen")
    drag(vp, [QPoint(200 + i * 8, 200 + int(40 * math.sin(i / 4))) for i in range(60)])
    strokes = [it for it in sc.content_items() if isinstance(it, I.StrokeItem)]
    step("kalemle çizim", len(strokes) == 1 and len(strokes[0].pts) > 5)
    step("boş ipucu gizlendi", not win.area.hint.isVisible())

    state.set_color("#ff453a")
    drag(vp, [QPoint(200, 380), QPoint(300, 383), QPoint(400, 380)], mods=Qt.KeyboardModifier.ShiftModifier)
    lines = [it for it in sc.content_items() if isinstance(it, I.StrokeItem) and it.kind == "line"]
    step("Shift+sürükle düz çizgi", len(lines) == 1)

    for tool, a, bb in (("rect", QPoint(600, 150), QPoint(800, 300)), ("ellipse", QPoint(850, 150), QPoint(1000, 300)),
                        ("arrow", QPoint(600, 400), QPoint(800, 480))):
        state.set_tool(tool)
        drag(vp, [a, QPoint((a.x() + bb.x()) // 2, (a.y() + bb.y()) // 2), bb])
    kinds = sorted(it.kind for it in sc.content_items() if isinstance(it, I.StrokeItem))
    step("şekiller (dikdörtgen/elips/ok)", kinds == ["arrow", "ellipse", "line", "pen", "rect"])

    state.set_tool("hl")
    state.set_color("#ffd60a")
    drag(vp, [QPoint(180, 240), QPoint(340, 242), QPoint(500, 240)])
    step("fosforlu kalem", any(it.kind == "hl" for it in sc.content_items() if isinstance(it, I.StrokeItem)))

    # yazı yalnızca Yazı aracıyla (7): kalemde boş yere çift tık yazı açmaz
    state.set_tool("pen")
    state.set_color("auto")
    p = QPoint(250, 560)
    n_before = win.page.undo.index()
    mouse(vp, PRESS, p, L, L)
    mouse(vp, REL, p, L, NB)
    mouse(vp, DBL, p, L, L)
    mouse(vp, REL, p, L, NB)
    pump()
    no_text = b.editing_text() is None
    while win.page.undo.index() > n_before:      # kalemin bıraktığı nokta(lar)
        win.page.undo.undo()
    b.setFocus()
    key(vp, Qt.Key.Key_M, "M")
    key(vp, Qt.Key.Key_Return)
    no_text = no_text and b.editing_text() is None and not [i for i in sc.content_items() if isinstance(i, I.TextItem)]
    state.set_tool("text")
    mouse(vp, PRESS, p, L, L)
    mouse(vp, REL, p, L, NB)
    pump()
    ed = b.editing_text()
    step("yazı yalnızca Yazı aracıyla açılır (çift tık, harf, Enter açmaz; 7 + tık açar)", no_text and ed is not None)
    for ch in "Toplantı notu: Q3 hedefleri":
        key(vp, 0, ch)
    key(vp, Qt.Key.Key_Escape)
    texts = [it for it in sc.content_items() if isinstance(it, I.TextItem)]
    step("klavyeden yazı", len(texts) == 1 and texts[0].toPlainText() == "Toplantı notu: Q3 hedefleri"
         and b.editing_text() is None)
    pump(5)
    step("otomatik başlık", win.page.auto.startswith("Toplantı notu"))
    tt = win.titlebar.title
    mouse(tt, PRESS, QPoint(10, 10), L, L)
    mouse(tt, REL, QPoint(10, 10), L, NB)
    pump()
    step("not adı: tek tık düzenlemeye açmaz, kutu dar", not tt.editing() and tt.width() <= tt.MAX_W)
    mouse(tt, DBL, QPoint(10, 10), L, L)
    pump()
    step("not adı: çift tık düzenler", tt.editing() and tt.hasFocus())
    key(tt, Qt.Key.Key_Escape)
    b.setFocus()
    pump()
    step("not adı: Esc / odak kaybı kilitler", not tt.editing())

    # Enter: Seçenekler'de "harfe basınca yazı başlasın" açıksa imlecin olduğu yere yazı
    prefs.set("type_to_text", True)
    state.set_tool("pen")
    b.setFocus()
    key(vp, Qt.Key.Key_Return)
    step("Enter yazı kutusu açar (seçenek açıkken)", b.editing_text() is not None)
    key(vp, Qt.Key.Key_Escape)
    step("boş yazı kutusu iz bırakmaz", len([i for i in sc.content_items() if isinstance(i, I.TextItem)]) == 1)

    # rakam tuşları araç seçer, Shift+rakam renk (gerçek sanal tuş koduyla)
    def vkey(w, k, vk, text="", mods=NOMOD):
        for typ in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            QApplication.sendEvent(w, QKeyEvent(typ, k, mods, 0, vk, 0, text))
        pump()
    got_tools = []
    for k, vk in ((Qt.Key.Key_3, 0x33), (Qt.Key.Key_8, 0x38), (Qt.Key.Key_0, 0x30), (Qt.Key.Key_1, 0x31)):
        vkey(vp, k, vk, chr(vk))
        got_tools.append(state.tool)
    step("1-9/0 araç seçer (3 ok, 8 lazer, 0 seç, 1 kalem)", got_tools == ["arrow", "laser", "select", "pen"])
    vkey(vp, Qt.Key.Key_Dollar, 0x34, "$", Qt.KeyboardModifier.ShiftModifier)   # Shift+4
    step("Shift+4 kırmızı renk", state.color == "#ff453a" and state.tool == "pen")
    state.set_color("auto")
    # hızlı yazı: harfe basınca imlecin olduğu yerde yazı başlar
    n_txt = len([i for i in sc.content_items() if isinstance(i, I.TextItem)])
    b.setFocus()
    key(vp, Qt.Key.Key_M, "M")
    ed = b.editing_text()
    for ch in "erhaba":
        key(vp, 0, ch)
    txt = ed.toPlainText() if ed is not None else ""
    key(vp, Qt.Key.Key_Escape)
    step("harfe basınca hızlı yazı (Merhaba, seçenek açıkken)", txt == "Merhaba" and
         len([i for i in sc.content_items() if isinstance(i, I.TextItem)]) == n_txt + 1)
    prefs.set("type_to_text", False)

    # görsel yapıştır
    img = QImage(320, 200, QImage.Format.Format_RGB32)
    img.fill(QColor("#3ea6ff"))
    QApplication.clipboard().setImage(img)
    b.setFocus()
    key(vp, Qt.Key.Key_V, "", CTRL)
    imgs = [it for it in sc.content_items() if isinstance(it, I.ImageItem)]
    step("Ctrl+V görsel yapıştırma", len(imgs) == 1)
    # görsel boyutlandırma: yapıştırılan görsel seçili gelir, kalem açıkken de köşeden büyür
    if imgs:
        g = imgs[0]
        state.set_tool("pen")
        pump()
        step("eklenen görsel seçili geliyor", g.isSelected())
        def vcorner(c):
            return b.mapFromScene(g.mapToScene(c))

        def grect():
            return g.mapRectToScene(QRectF(0, 0, g.pixmap().width(), g.pixmap().height()))
        r0 = grect()
        n_strokes = len([i for i in sc.content_items() if isinstance(i, I.StrokeItem)])
        br = vcorner(QPointF(g.pixmap().width(), g.pixmap().height()))
        drag(vp, [br, br + QPoint(40, 10), br + QPoint(80, 20)])
        r1 = grect()
        same_strokes = n_strokes == len([i for i in sc.content_items() if isinstance(i, I.StrokeItem)])
        step("sağ alt köşeden büyüdü (kalemde, çizgi çizmeden)", r1.width() > r0.width() * 1.2 and
             abs(r1.left() - r0.left()) < 0.5 and abs(r1.top() - r0.top()) < 0.5 and same_strokes)
        tl = vcorner(QPointF(0, 0))
        drag(vp, [tl, tl + QPoint(30, 30), tl + QPoint(60, 60)])
        r2 = grect()
        step("sol üst köşeden küçüldü, sağ alt sabit", r2.width() < r1.width() and
             abs(r2.right() - r1.right()) < 0.5 and abs(r2.bottom() - r1.bottom()) < 0.5)
        key(vp, Qt.Key.Key_Z, "", CTRL)
        key(vp, Qt.Key.Key_Z, "", CTRL)
        r3 = grect()
        step("boyutlandırma geri alınır", abs(r3.width() - r0.width()) < 0.5 and abs(r3.left() - r0.left()) < 0.5)
    shot(win, "02_cizim")

    # sağ tık basılı sürükle = sil (dikdörtgenin üst kenarı + elipsin ortası üstünden geç)
    n0 = len(sc.content_items())
    drag(vp, [QPoint(590, 150), QPoint(700, 150), QPoint(850, 225), QPoint(1010, 225)], btn=R)
    left = [it.kind for it in sc.content_items() if isinstance(it, I.StrokeItem)]
    step("sağ tık sürükle sildi", "rect" not in left and "ellipse" not in left)
    step("görsel silgiden etkilenmedi", any(isinstance(i, I.ImageItem) for i in sc.content_items()))
    key(vp, Qt.Key.Key_Z, "", CTRL)
    step("Ctrl+Z silmeyi geri aldı", len(sc.content_items()) == n0)
    click(vp, QPoint(10, 10), Qt.MouseButton.BackButton)
    step("fare geri tuşu = geri al", len(sc.content_items()) == n0 - 1)
    click(vp, QPoint(10, 10), Qt.MouseButton.ForwardButton)
    step("fare ileri tuşu = yinele", len(sc.content_items()) == n0)

    # yakınlaştırma (tekerlek) + Alt+tekerlek kalınlık
    z0 = b.zoom()
    wheel(vp, QPoint(640, 400), QPoint(0, 120))
    step("tekerlek yakınlaştırır", b.zoom() > z0 * 1.1)
    w0 = state.width
    wheel(vp, QPoint(640, 400), QPoint(120, 0), Qt.KeyboardModifier.AltModifier)
    step("Alt+tekerlek kalınlık", state.width > w0)
    state.set_width(4.0)
    h0 = b.horizontalScrollBar().value()
    drag(vp, [QPoint(600, 400), QPoint(550, 400), QPoint(500, 400)], btn=M)
    step("orta tuşla kaydırma", b.horizontalScrollBar().value() != h0)
    key(vp, Qt.Key.Key_Home)
    step("F hepsini sığdırır", all(vp.rect().contains(b.mapFromScene(it.sceneBoundingRect().center()))
                                   for it in sc.content_items()))

    # Ctrl+sol ile taşıma + geri al
    tgt = texts[0]
    c = b.mapFromScene(tgt.sceneBoundingRect().center())
    pos0 = tgt.pos()
    drag(vp, [c, c + QPoint(40, 0), c + QPoint(80, 30)], mods=CTRL)
    moved = tgt.pos() != pos0
    key(vp, Qt.Key.Key_Z, "", CTRL)
    step("Ctrl+sürükle taşır, Ctrl+Z geri alır", moved and tgt.pos() == pos0)
    sc.clearSelection()

    # renk tuşu seçimi boyar
    tgt.setSelected(True)
    tool_before = state.tool
    QApplication.sendEvent(vp, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Ampersand, Qt.KeyboardModifier.ShiftModifier,
                                         0, 0x36, 0, "&"))
    pump()
    step("seçiliyken Shift+6 boyar, araç değişmez", tgt.color_name == "#ffd60a" and state.tool == tool_before)
    key(vp, Qt.Key.Key_Z, "", CTRL)
    step("boyama geri alınır", tgt.color_name == "auto")
    sc.clearSelection()

    # lazer kaydedilmez
    state.set_tool("laser")
    n1 = len(sc.content_items())
    drag(vp, [QPoint(300, 300), QPoint(400, 350), QPoint(500, 300)])
    step("lazer içerik eklemez", len(sc.content_items()) == n1 and b._lasers)
    state.set_tool("pen")

    # tema değişince "auto" renk döner
    from yazit.theme import theme
    theme.apply("light")
    pump()
    step("açık temada otomatik renk siyah", texts[0].defaultTextColor().lightness() < 60)
    shot(win, "03_acik_tema")
    theme.apply("dark")
    pump()

    # kaydet + yeni not + geri dön
    pid = win.page.id
    win.store.flush()
    step("not dosyası yazıldı", os.path.exists(win.page.path) and os.path.exists(win.page.thumb_path))
    win.new_note()
    pump()
    step("yeni boş not", win.page.id != pid and b.is_empty())
    win.new_note()
    step("boş notta yeni not açılmaz", sum(1 for p in win.store.pages.values() if not p.saved_once) == 1)
    win.open_page(win.store.get(pid))
    pump()
    step("boş not listeden düştü, eski not açıldı", win.page.id == pid and len(win.store.pages) == 1)

    from yazit.pages import NoteStore
    s2 = NoteStore()
    p2 = s2.get(pid)
    p2.ensure_loaded()
    step("not diskten geri okundu", len(p2.scene.content_items()) == len(b.scene().content_items()))
    shot(win, "04_kayitli")

    # Ekran alıntısı: gerçek ekran yerine sahte görüntüyle (kişisel pencereler görüntüye girmesin)
    from yazit.capture import CaptureOverlay
    fake = QPixmap(1600, 1000)
    fake.fill(QColor("#203040"))
    scr = app.primaryScreen()
    got = []
    d.capture.to_yazit.connect(lambda pm: got.append(pm))
    ov = CaptureOverlay(d.capture, scr, fake)
    d.capture.overlays.append(ov)
    ov.setGeometry(QRect(0, 0, 800, 500))
    ov.dpr = 2.0
    ov.show()
    pump(5)
    drag(ov, [QPoint(100, 100), QPoint(200, 150), QPoint(300, 250)])
    pump(5)
    step("alıntı alanı seçildi + çubuk çıktı", ov.sel.width() == 200 and ov.sel.height() == 150 and ov.bar.isVisible())
    clip = QApplication.clipboard().image()
    print("   panodaki görüntü:", clip.width(), "x", clip.height(), "(beklenen 400 x 300)")
    shot(ov, "05_alinti")
    n_pages = len(win.store.pages)
    key(ov, Qt.Key.Key_Return)
    pump(10)
    step("Enter: alıntı yeni notta görsel oldu", got and len(win.store.pages) == n_pages + 1 and
         any(isinstance(i, I.ImageItem) for i in b.scene().content_items()))
    im = [i for i in b.scene().content_items() if isinstance(i, I.ImageItem)]
    step("alıntı mantıksal boyutta (HiDPI)", im and im[0].pixmap().width() == 400 and
         abs(im[0].pixmap().width() * im[0].scale() - 200) < 2)
    vis = b.mapToScene(b.viewport().rect()).boundingRect()
    step("alıntı yapıştırılmış gelir: seçili değil, kalem hazır, görünüm alıntıya sığar",
         im and not im[0].isSelected() and state.tool in ("pen", "hl", "line", "arrow", "rect", "ellipse")
         and vis.contains(I.exact_rect(im[0])) and b.zoom() <= 1.0 + 1e-6)

    # alıntının üstüne çiz + Ctrl+C: çizimli alıntı, alıntının kendi boyutunda kopyalanır (eski alıntı değil)
    if im:
        g = im[0]
        was_sel = g.isSelected()
        state.set_tool("pen")
        old_color = state.color
        state.set_color("#ff2020")
        r = g.mapRectToScene(QRectF(g.pixmap().rect()))
        p1 = b.mapFromScene(QPointF(r.left() + r.width() * 0.2, r.center().y()))
        p2 = b.mapFromScene(QPointF(r.left() + r.width() * 0.8, r.center().y()))
        drag(vp, [p1, (p1 + p2) / 2, p2])
        state.set_color(old_color)
        b.setFocus()
        key(vp, Qt.Key.Key_C, "", CTRL)
        cim = QApplication.clipboard().image()
        mid = QColor(cim.pixel(cim.width() // 2, cim.height() // 2)) if not cim.isNull() else QColor()
        print("   çizimli alıntı:", cim.width(), "x", cim.height(), "orta:", mid.name(), "seçiliydi:", was_sel)
        step("alıntıya çizip Ctrl+C: çizimiyle, alıntı boyutunda kopyalanır",
             cim.width() == 400 and cim.height() == 300 and mid.red() > 200 and mid.green() < 100)

    # alıntıyı ekrana iğnele
    ov = CaptureOverlay(d.capture, scr, fake)
    d.capture.overlays.append(ov)
    ov.setGeometry(QRect(0, 0, 800, 500))
    ov.dpr = 2.0
    ov.show()
    pump(5)
    drag(ov, [QPoint(100, 100), QPoint(200, 150), QPoint(300, 250)])
    want = ov.mapToGlobal(QPoint(100, 100))
    key(ov, Qt.Key.Key_T, mods=Qt.KeyboardModifier.ControlModifier)
    pump(10)
    pins = d.pins.pins
    pw = pins[0] if pins else None
    step("Ctrl+T: alıntı iğnelendi (yerinde, mantıksal boyut)", pw is not None and pw.isVisible() and
         pw.pos() == want and pw.width() == 200 and pw.height() == 150 and not d.capture.active())
    if pw is not None:
        wheel(pw, QPoint(0, 0), QPoint(0, 120))
        step("iğne: tekerlek büyütür, sol üst sabit", pw.width() == 220 and pw.pos() == want)
        wheel(pw, QPoint(10, 10), QPoint(0, -120), Qt.KeyboardModifier.ControlModifier)
        step("iğne: Ctrl+tekerlek saydamlık", abs(pw.windowOpacity() - 0.9) < 0.02)
        drag(pw, [QPoint(10, 10), QPoint(60, 40)])
        step("iğne: sürükleyince taşınır", pw.pos() == want + QPoint(50, 30))
        key(pw, Qt.Key.Key_C, mods=Qt.KeyboardModifier.ControlModifier)
        cim = QApplication.clipboard().image()
        step("iğne: Ctrl+C tam çözünürlük kopyalar", cim.width() == 400 and cim.height() == 300)
        pw._hover = True
        shot(pw, "11_igne")
        mouse(pw, QEvent.Type.MouseButtonDblClick, QPoint(30, 30), L, L)
        pump(10)
        step("iğne: çift tık kapatır", not d.pins.pins)

    # ekrana çiz katmanı
    ann = d.annotate
    ann.open()
    pump(10)
    state.set_tool("pen")
    drag(ann.board.viewport(), [QPoint(100, 100), QPoint(200, 160), QPoint(300, 120)])
    step("ekrana çiz: çizim", len(ann.board.scene().content_items()) == 1)
    ann.set_passthrough(True)
    pump()
    step("fareyi bırak modu", ann.passthrough and not ann.toolbar.isVisible())
    ann.toggle()
    pump()
    step("kısayol tekrar: çizime dönüş", not ann.passthrough and ann.isVisible())
    if SHOTS:
        ann.toolbar.grab().save(os.path.join(SHOTS, "06_ekrana_ciz_arac.png"))
    ann.toggle()
    pump()
    step("kısayol tekrar: kapandı ve temizlendi", not ann.isVisible() and ann.board.is_empty())

    # pencereden "ekrana çiz": yazıt görev çubuğuna iner, kapanınca geri gelir
    win.bring_front()
    pump(10)
    win.request_annotate.emit()
    pump(10)
    went_down = win.isMinimized()
    from PyQt6.QtTest import QTest
    QTest.qWait(300)
    opened = ann.isVisible()
    ann.close_overlay()
    pump(10)
    step("pencereden ekrana çiz: yazıt iner, kapanınca geri gelir",
         went_down and opened and not win.isMinimized() and win.isVisible())

    # ekrana çiz açıkken alıntı: yazıt alıntıya girmesin, alıntı bitince geri gelsin
    win.request_annotate.emit()
    pump(10)
    QTest.qWait(300)
    real_start = d.capture.start
    d.capture.start = lambda delay=0, mode="snip": None
    d.handle_message("snip")
    pump(10)
    still_down = win.isMinimized() and not ann.isVisible()
    d.capture.start = real_start
    d.capture.finished.emit()
    pump(10)
    step("ekrana çiz → alıntı: yazıt alıntı süresince aşağıda, sonra geri gelir",
         still_down and not win.isMinimized() and win.isVisible())

    # ekran videosu: önce seçim ekranı (sahte görüntü) kayıt modunda
    from yazit.recorder import find_ffmpeg
    recs = []
    d.capture.record.connect(lambda data: recs.append(data))
    d.capture.mode = "record"
    ov2 = CaptureOverlay(d.capture, scr, fake)
    d.capture.overlays.append(ov2)
    ov2.setGeometry(QRect(0, 0, 800, 500))
    ov2.dpr = 1.0
    ov2.show()
    pump(5)
    drag(ov2, [QPoint(50, 50), QPoint(150, 120), QPoint(251, 201)])
    shot(ov2, "09_kayit_secim")
    key(ov2, Qt.Key.Key_Return)
    pump(5)
    step("kayıt modu: Enter alanı kayda gönderir", recs and recs[0][1].width() == 201)
    d.capture.mode = "snip"
    step("ffmpeg bulundu", find_ffmpeg() is not None)
    # gerçek kayıt: küçük bir alan, 2 sn; dosya geçici klasöre yazılır, içeriğine bakılmaz, sonra silinir
    from PyQt6.QtCore import QEventLoop, QTimer
    saved = []
    d.recorder.saved.connect(lambda pth: saved.append(pth))
    d.recorder.failed.connect(lambda m: print("   kayıt hatası:", m))
    d.recorder.start(scr, QRect(0, 0, 161, 121), 1.0)
    step("kayıt başladı (çerçeve + durdur çubuğu)", d.recorder.active() and d.recorder.bar is not None)
    if SHOTS and d.recorder.bar is not None:
        d.recorder.bar.grab().save(os.path.join(SHOTS, "10_kayit_cubugu.png"))
    if d.recorder.bar is not None:
        from PyQt6.QtWidgets import QPushButton as _QB
        rb = d.recorder.bar
        before = [w.geometry() for w in [rb.time] + rb.findChildren(_QB)] + [rb.size()]
        rb.set_blink(False)
        pump(5)
        after = [w.geometry() for w in [rb.time] + rb.findChildren(_QB)] + [rb.size()]
        rb.set_blink(True)
        step("kayıt çubuğu: nokta sönünce hiçbir şey kaymıyor", before == after)
    loop = QEventLoop()
    QTimer.singleShot(2200, loop.quit)
    loop.exec()
    d.recorder.stop()
    loop = QEventLoop()
    d.recorder.stopped.connect(loop.quit)
    QTimer.singleShot(10000, loop.quit)
    loop.exec()
    ok = bool(saved) and os.path.getsize(saved[0]) > 1000
    step("video kaydedildi (MP4, çift boyut)", ok and not d.recorder.active())
    for pth in saved:
        os.remove(pth)
    d.recorder.start(scr, QRect(0, 0, 100, 100), 1.0)
    loop = QEventLoop()
    QTimer.singleShot(800, loop.quit)
    loop.exec()
    n_saved = len(saved)
    d.recorder.discard()
    loop = QEventLoop()
    d.recorder.stopped.connect(loop.quit)
    QTimer.singleShot(10000, loop.quit)
    loop.exec()
    vids = os.listdir(os.path.join(TMP, "videos"))
    step("vazgeç: dosya silindi", len(saved) == n_saved and not vids)

    # kayıt ayarları: ffmpeg komutu (aygıt açmadan)
    from yazit.i18n import t
    from yazit.recorder import build_args, out_size, summary, rec_config, Countdown
    a = build_args(0, 0, 1920, 1080, {"fps": 60, "res": "720", "cam_pos": "tl"},
                   {"cam": "Cam", "mic": "Mic", "sys": True}, "o.mp4", ["-f", "f32le", "-i", "PIPE"])
    fc = a[a.index("-filter_complex") + 1]
    step("kayıt komutu: kamera + mikrofon tek dshow girişi, ses borusu, ekran, maske",
         "video=Cam:audio=Mic" in a and a.index("video=Cam:audio=Mic") < a.index("PIPE") < a.index("desktop")
         and a[a.index("-framerate") + 1] == "60")
    step("kayıt komutu: 720p'ye küçültme, yuvarlak kamera sol üstte, iki ses karışır",
         "scale=1280:720" in fc and "alphamerge" in fc and "overlay=" in fc and ":eof_action" in fc
         and "amix=inputs=2" in fc and "[v]" in a and "[a]" in a)
    a2 = build_args(10, 20, 800, 600, {"fps": 30, "res": "1080"}, {"cam": "", "mic": "", "sys": False}, "o.mp4")
    step("kayıt komutu: ek kaynak yoksa filtre yok, sessiz, büyütme yok",
         "-filter_complex" not in a2 and "-c:a" not in a2 and a2[a2.index("-video_size") + 1] == "800x600")
    a3 = build_args(0, 0, 1920, 1080, {"fps": 30, "res": "src", "cam_pos": "br", "cam_shape": "rect",
                                       "cam_border": "#ffffff", "cam_gray": True},
                    {"cam": "Cam", "mic": "", "sys": False}, "o.mp4")
    fc3 = a3[a3.index("-filter_complex") + 1]
    pngs = [x for x in a3 if x.endswith(".png")]
    step("kamera: dikdörtgen 16:9, beyaz kenarlık resmi, siyah beyaz",
         "ih*16/9" in fc3 and "scale=408:230" in fc3 and "hue=s=0" in fc3 and fc3.count("overlay=") == 2
         and len(pngs) == 2 and all(os.path.exists(x) for x in pngs))
    a4 = build_args(0, 0, 1280, 720, {"fps": 30, "res": "src", "cam_pos": "tl", "cam_shape": "circle",
                                      "cam_border": "shadow"}, {"cam": "Cam", "mic": "", "sys": False}, "o.mp4")
    fc4 = a4[a4.index("-filter_complex") + 1]
    step("kamera gölgesi: gölge resmi kameranın altında, üstte ince açık kenar",
         fc4.count("overlay=") == 3 and fc4.index("[sh]") < fc4.index("[cam]overlay")
         and len([x for x in a4 if x.endswith(".png")]) == 3)
    a5 = build_args(0, 0, 1920, 1080, {"fps": 30, "res": "720", "cam_pos": "br", "cam_shape": "circle",
                                       "cam_border": "none"}, {"cam": "Cam", "mic": "", "sys": False}, "o.mp4",
                    preview=(278, 278))
    fc5 = a5[a5.index("-filter_complex") + 1]
    step("kendini gör: kamera ikiye ayrılır, ikinci çıktı ham kare olarak stdout'a",
         "split=2" in fc5 and "scale=278:278" in fc5 and a5[-1] == "pipe:1" and a5.index("o.mp4") < a5.index("[pv]"))
    from yazit.recorder import SelfView
    from PyQt6.QtCore import QRectF as _QRF
    sv = SelfView(_QRF(100, 100, 120, 120), (40, 40), {"cam_shape": "circle", "cam_border": "shadow"})
    sv.feed(bytes([200, 30, 30]) * 40 * 40 + bytes([0, 200, 0]) * 40 * 40 + b"xx")
    step("kendini gör: karelerin sonuncusu gösterilir, artan bayt bekler, pencere gölge payı kadar büyük",
         sv.img is not None and sv.img.pixelColor(5, 5).green() == 200 and len(sv.buf) == 2
         and sv.width() > 120)
    sv.deleteLater()
    step("çıkış boyutu çift, en-boy korunur", out_size(2560, 1440, "1080") == (1920, 1080)
         and out_size(1001, 701, "src") == (1000, 700) and out_size(1280, 720, "1080") == (1280, 720))
    step("kayıt özeti: sessiz", summary(rec_config()) == t("rec_silent"))

    # kayıt paneli
    d.toggle_record(from_window=False)
    pump(10)
    rp = d.rec_panel
    step("kayıt düğmesi / kısayol kayıt panelini açar", rp is not None and rp.isVisible())
    if rp is not None:
        shot(rp, "10b_kayit_paneli")
        rp.seg_cd.group.button(rp.seg_cd.keys.index(5)).click()
        rp.seg_scene.group.button(1).click()
        rp.seg_fps.group.button(rp.seg_fps.keys.index(60)).click()
        rp.c_res.setCurrentIndex(rp.c_res.findData("720"))
        rp.sw_sys.setChecked(True)
        rp.seg_shape.group.button(rp.seg_shape.keys.index("square")).click()
        rp.seg_border.group.button(rp.seg_border.keys.index("#ff3b30")).click()
        rp.sw_gray.setChecked(True)
        pump(5)
        step("panel: kamera şekli / kenarlık / siyah beyaz kaydedilir, önizleme aynısını çizer",
             rec_config()["cam_shape"] == "square" and rec_config()["cam_border"] == "#ff3b30"
             and rec_config()["cam_gray"] and rp.preview.shape == "square" and rp.preview.gray
             and rp.preview.proc is None)
        shot(rp.preview, "10e_kamera_onizleme_bos")
        cfg = rec_config()
        step("panel ayarları hemen kaydedilir", cfg["countdown"] == 5 and cfg["scene"] == "screen"
             and cfg["fps"] == 60 and cfg["res"] == "720" and cfg["sys"])
        step("panel: alan seç / tüm ekran ayrıntıları", rp._screen_row.isHidden() != rp._multi_screen)
        # Başlat → (tüm ekran) geri sayım; Esc vazgeçer, kayıt başlamaz
        rp._go()
        loop = QEventLoop()
        QTimer.singleShot(400, loop.quit)
        loop.exec()
        cd = d.countdown
        step("Başlat: panel kapanır, geri sayım başlar (5)", d.rec_panel is None and cd is not None and cd.n == 5)
        if cd is not None:
            shot(cd, "10c_geri_sayim")
            key(cd, Qt.Key.Key_Escape)
            pump(10)
            loop = QEventLoop()
            QTimer.singleShot(150, loop.quit)
            loop.exec()
        step("geri sayımda Esc: kayıt başlamaz", d.countdown is None and not d.recorder.active())
    cdl = []
    c2 = Countdown(QRect(0, 0, 300, 200), 3)
    c2.done.connect(lambda: cdl.append("done"))
    c2.start()
    click(c2, QPoint(150, 100), Qt.MouseButton.LeftButton)
    loop = QEventLoop()
    QTimer.singleShot(200, loop.quit)
    loop.exec()
    step("geri sayıma tıklamak hemen başlatır", cdl == ["done"])
    for k, v in (("rec_countdown", 0), ("rec_scene", "area"), ("rec_res", "src"), ("record_fps", 30)):
        prefs.set(k, v)

    # gerçek kayıt + bilgisayar sesi (WASAPI loopback → boru → ffmpeg)
    prefs.set("rec_sys", True)
    saved.clear()
    d.recorder.start(scr, QRect(0, 0, 160, 120), 1.0)
    has_lb = d.recorder._lb is not None
    if d.recorder.bar is not None:
        shot(d.recorder.bar, "10d_kayit_cubugu_ses")
    step("bilgisayar sesi açıldı, çubukta simgesi var",
         has_lb and d.recorder.src.get("sys") and d.recorder.bar is not None and len(d.recorder.bar.src_icons) == 1)
    loop = QEventLoop()
    QTimer.singleShot(2000, loop.quit)
    loop.exec()
    d.recorder.stop()
    loop = QEventLoop()
    d.recorder.stopped.connect(loop.quit)
    QTimer.singleShot(10000, loop.quit)
    loop.exec()
    import subprocess as _sp
    info = ""
    if saved:
        r = _sp.run([find_ffmpeg(), "-hide_banner", "-i", saved[0]], capture_output=True, creationflags=0x08000000)
        info = r.stderr.decode("utf-8", errors="ignore")
    step("bilgisayar sesiyle video: görüntü + ses akışı", "Video: h264" in info and "Audio: aac" in info
         and d.recorder._lb is None)
    for pth in saved:
        os.remove(pth)
    prefs.set("rec_sys", False)

    from yazit.hotkeys import parse
    step("kısayol ayrıştırma", parse("Win+Shift+A") == (0x8 | 0x4, ord("A")) and parse("A") is None
         and parse("Ctrl+Alt+F5") == (0x2 | 0x1, 0x74))
    ok = d.hotkeys.set("capture", "Ctrl+Alt+Shift+F11")
    step("global kısayol kaydı (RegisterHotKey)", ok is True)
    reg = {}
    for s in ("Win+Shift+A", "Win+Shift+D", "Win+Shift+N"):
        reg[s] = d.hotkeys.set("note", s)
    print("   varsayılan kısayollar boşta mı:", reg)
    d.hotkeys.unregister_all()

    from yazit.dialogs import PrefsDialog, HelpDialog
    pd = PrefsDialog(win, d.hotkeys, updater=getattr(d, "updater", None))
    pd.show()
    pump(5)
    shot(pd, "07_secenekler")
    sa = pd.findChild(QScrollArea)
    if SHOTS and sa is not None:
        for i, frac in enumerate((0.33, 0.66, 1.0)):
            sa.verticalScrollBar().setValue(int(sa.verticalScrollBar().maximum() * frac))
            pump(3)
            shot(pd, f"07_secenekler_{i + 2}")
    pd.close()
    hd = HelpDialog(win)
    hd.show()
    pump(5)
    shot(hd, "08_yardim")
    hd.close()
    step("seçenekler ve yardım pencereleri açıldı", True)

    # ---- 1.1.0: OCR, PNG/JPEG/PDF, araç çubuğu konumu, tahta kısayolları, güncelleme sürüm karşılaştırması
    from PyQt6.QtCore import QEventLoop, QTimer
    from PyQt6.QtGui import QPainter, QFont
    from yazit import ocr, export
    oimg = QImage(560, 120, QImage.Format.Format_RGB32)
    oimg.fill(QColor("white"))
    pt = QPainter(oimg)
    f = QFont("Segoe UI")
    f.setPixelSize(30)
    pt.setFont(f)
    pt.setPen(QColor("black"))
    pt.drawText(QRect(10, 10, 540, 100), 0, "Çarşamba toplantısı 2026")
    pt.end()
    got_txt = []
    loop = QEventLoop()
    ocr.read_text(oimg, lambda x: (got_txt.append(x), loop.quit()), lambda m: (got_txt.append("HATA " + m), loop.quit()))
    QTimer.singleShot(20000, loop.quit)
    loop.exec()
    print("   OCR:", got_txt)
    step("OCR Türkçe yazıyı okur", bool(got_txt) and "Çarşamba" in got_txt[0] and "2026" in got_txt[0])

    from yazit.canvas import render_scene
    rimg = render_scene(win.board.scene())
    outs = {}
    for ext in ("png", "jpg", "pdf"):
        path = os.path.join(TMP, "disa." + ext)
        ok = export.save_image(rimg, path, QColor("#0f0f0f"))
        outs[ext] = ok and os.path.exists(path) and os.path.getsize(path) > 500
    with open(os.path.join(TMP, "disa.pdf"), "rb") as fh:
        is_pdf = fh.read(5) == b"%PDF-"
    step("PNG / JPEG / PDF kaydı", all(outs.values()) and is_pdf)
    multi = os.path.join(TMP, "hepsi.pdf")
    ok = export.export_pdf([rimg, rimg], multi)
    with open(multi, "rb") as fh:
        pdf = fh.read()
    step("birden çok not tek PDF (2 sayfa)", ok and pdf.count(b"/Type /Page\n") + pdf.count(b"/Type /Page\r") +
         pdf.count(b"/Type /Page ") + pdf.count(b"/Type /Page>") >= 2)
    step("dışa aktarma: uzantı ekleme", export.fix_ext("a", "PDF (*.pdf)") == "a.pdf" and
         export.fix_ext("b.jpeg", "") == "b.jpeg")

    from yazit.toolbar import set_position
    tb = win.area.toolbar
    set_position("left")
    pump(5)
    left_ok = tb.vertical and tb.x() < 40 and tb.height() > tb.width()
    shot(win, "12_dikey_arac_cubugu")
    set_position("top")
    pump(5)
    top_ok = (not tb.vertical) and tb.y() < 40
    # sürükle-bırak: sağ kenara taşı
    mouse(tb, PRESS, QPoint(3, tb.height() // 2), L, L)
    tgt = tb.mapFromGlobal(win.area.mapToGlobal(QPoint(win.area.width() - 5, win.area.height() // 2)))
    mouse(tb, MOVE, tgt, NB, L)
    mouse(tb, REL, tgt, L, NB)
    pump(5)
    right_ok = tb.vertical and tb.x() > win.area.width() // 2
    set_position("bottom")
    pump(5)
    step("araç çubuğu: sol/üst/sürükleyip sağ/alt", left_ok and top_ok and right_ok and not tb.vertical and
         tb.y() > win.area.height() // 2)

    from yazit.tools import set_tool_key, reset_tool_keys, tool_key
    set_tool_key("laser", "Q")
    vkey(vp, Qt.Key.Key_Q, 0x51, "q")
    q_ok = state.tool == "laser" and b.editing_text() is None
    set_tool_key("pen", "8")      # 8 lazerdeydi: lazerden kalkmalı değil (lazer Q), pen 8 olur
    vkey(vp, Qt.Key.Key_8, 0x38, "8")
    swap_ok = state.tool == "pen" and tool_key("pen") == "8"
    set_tool_key("eraser", "8")   # aynı tuş: kalemden kaldırılır
    steal_ok = tool_key("pen") == "" and tool_key("eraser") == "8"
    reset_tool_keys()
    step("tahta kısayolları özelleştirilir (Q→lazer, çakışma kaldırılır, sıfırlanır)",
         q_ok and swap_ok and steal_ok and tool_key("pen") == "1" and tool_key("laser") == "8")
    state.set_tool("pen")

    calls = []
    real_start = d.capture.start
    d.capture.start = lambda delay=0, mode="snip": calls.append((delay, mode))
    d.handle_message("snip")
    d.capture.start = real_start
    step("--snip / \"yazıt alıntı\" simgesi alıntıyı başlatır", calls == [(250, "snip")])

    # ---- 1.3: hizala / diz / grupla / katman / kilit / gizle / kılavuz / ok tuşları / katmanlar paneli
    import random
    SHIFT = Qt.KeyboardModifier.ShiftModifier
    win.new_note()
    pump(5)
    b = win.board
    vp = b.viewport()
    sc = b.scene()
    b.set_zoom(1.0)
    b.centerOn(QPointF(0, 0))
    random.seed(7)
    pics = []
    for i in range(10):
        im10 = QImage(random.randint(60, 120), random.randint(40, 90), QImage.Format.Format_RGB32)
        im10.fill(QColor.fromHsv(i * 36, 160, 230))
        pics.append(b.insert_image(im10, QPointF(random.uniform(-300, 300), random.uniform(-200, 200))))
    pump()

    def rects():
        return [I.exact_rect(it) for it in pics]

    def overlap_free(rs):
        return not any(rs[i].intersects(rs[j]) for i in range(len(rs)) for j in range(i + 1, len(rs)))
    b.select_all()
    pump()
    step("seçim çubuğu: seçince görünür", b.selbar.isVisible())
    before = [it.pos() for it in pics]
    b.arrange("grid")
    rs = rects()
    xs = {round(r.center().x(), 1) for r in rs}
    ys = {round(r.center().y(), 1) for r in rs}
    step("ızgaraya diz: 10 görsel 4 sütun × 3 satır, üst üste binmez", len(xs) == 4 and len(ys) == 3 and overlap_free(rs))
    win.page.undo.undo()
    step("dizmeyi geri al: yerler geri gelir", all(it.pos() == p0 for it, p0 in zip(pics, before)))
    b.arrange("circle")
    rs = rects()
    c = QPointF(sum(r.center().x() for r in rs) / len(rs), sum(r.center().y() for r in rs) / len(rs))
    ds = [math.hypot(r.center().x() - c.x(), r.center().y() - c.y()) for r in rs]
    angs = sorted(math.atan2(r.center().y() - c.y(), r.center().x() - c.x()) for r in rs)
    steps_ = [angs[i + 1] - angs[i] for i in range(len(angs) - 1)]
    step("çembere diz: merkeze eşit uzaklık, eşit açı, çakışma yok",
         max(ds) - min(ds) < 1.0 and max(steps_) - min(steps_) < 0.01 and overlap_free(rs))
    b.arrange("row")
    rs = sorted(rects(), key=lambda r: r.left())
    gaps = [rs[i + 1].left() - rs[i].right() for i in range(len(rs) - 1)]
    step("yan yana diz: aynı hizada, eşit boşluk",
         max(gaps) - min(gaps) < 0.01 and len({round(r.center().y(), 1) for r in rs}) == 1)
    for it in pics:
        it.setPos(it.pos() + QPointF(random.uniform(-40, 40), random.uniform(-60, 60)))
    b.align("top")
    tops = {round(r.top(), 2) for r in rects()}
    b.distribute("h")
    rs = sorted(rects(), key=lambda r: r.left())
    gaps = [rs[i + 1].left() - rs[i].right() for i in range(len(rs) - 1)]
    step("üste hizala + yatayda eşit dağıt", len(tops) == 1 and max(gaps) - min(gaps) < 0.01)
    b.arrange("grid")

    # grup: biri seçilince hepsi; tek parça taşınır; çöz
    sc.clearSelection()
    pics[0].setSelected(True)
    pics[1].setSelected(True)
    vp.setFocus()
    key(vp, Qt.Key.Key_G, "", CTRL)
    gid = I.group_of(pics[0])
    sc.clearSelection()
    pics[1].setSelected(True)
    pump()
    g_sel = pics[0].isSelected() and pics[1].isSelected() and not pics[2].isSelected()
    step("Ctrl+G grupla: biri seçilince grubun tamamı seçilir", bool(gid) and I.group_of(pics[1]) == gid and g_sel)
    d0 = pics[0].pos()
    key(vp, Qt.Key.Key_Right, "")
    key(vp, Qt.Key.Key_Right, "", SHIFT)
    moved_ok = abs(pics[0].pos().x() - d0.x() - 11) < 1e-6 and pics[0].pos().y() == d0.y()
    win.page.undo.undo()
    step("ok tuşu kaydırır (Shift ×10), art arda kaydırmalar tek geri al", moved_ok and pics[0].pos() == d0)
    key(vp, Qt.Key.Key_G, "", CTRL | SHIFT)
    step("Ctrl+Shift+G grubu çözer", I.group_of(pics[0]) is None and I.group_of(pics[1]) is None)

    # katman sırası
    sc.clearSelection()
    a_, b_ = pics[2], pics[3]
    b_.setPos(a_.pos() + QPointF(20, 20))   # üst üste binsinler
    low, high = sorted((a_, b_), key=lambda i: i.zValue())
    low.setSelected(True)
    key(vp, Qt.Key.Key_PageUp, "", CTRL)
    fwd = low.zValue() > high.zValue()
    key(vp, Qt.Key.Key_PageDown, "", CTRL)
    bwd = low.zValue() < high.zValue()
    key(vp, Qt.Key.Key_PageUp, "", CTRL | SHIFT)
    front = low.zValue() == max(it.zValue() for it in sc.content_items())
    key(vp, Qt.Key.Key_PageDown, "", CTRL | SHIFT)
    back = low.zValue() == min(it.zValue() for it in sc.content_items())
    state.set_tool("pen")
    drag(vp, [b.mapFromScene(QPointF(-500, -400)), b.mapFromScene(QPointF(-450, -380))])
    pen_top = max(sc.content_items(), key=lambda i: i.zValue())
    step("katman: öne / geri / en öne / en arkaya; sonra çizilen yine en üstte",
         fwd and bwd and front and back and isinstance(pen_top, I.StrokeItem))

    # kilit + gizle + kayıt
    sc.clearSelection()
    pics[4].setSelected(True)
    key(vp, Qt.Key.Key_L, "", CTRL)
    pics[4].setSelected(True)
    locked_ok = I.is_locked(pics[4]) and not pics[4].isSelected()
    stroke = pen_top
    stroke.setSelected(False)
    b.set_locked([stroke], True)
    state.set_tool("eraser")
    spt = b.mapFromScene(stroke.sceneBoundingRect().center())
    drag(vp, [spt, spt + QPoint(3, 1)])
    survived = stroke.scene() is sc
    b.set_locked([stroke], False)
    b.set_hidden([pics[5]], True)
    dd = I.to_dict(pics[4])
    dd2 = I.to_dict(pics[5])
    back4, back5 = I.from_dict(dd), I.from_dict(dd2)
    rimg_all = render_scene(sc)
    step("kilit: seçilmez, silgi dokunmaz; gizli resme girmez; kayıtta korunur",
         locked_ok and survived and not pics[5].isVisible() and I.is_locked(back4) and not back5.isVisible()
         and rimg_all is not None)
    b.set_hidden([pics[5]], False)
    b.set_locked([pics[4]], False)
    state.set_tool("select")

    # akıllı kılavuz: sürüklerken üst kenara yapışır
    sc.clearSelection()
    ta, tb_ = pics[6], pics[7]
    ta.setPos(QPointF(2000, 2000))      # diğerlerinden uzakta: başka kenara yapışmasın
    tb_.setPos(QPointF(2250, 2210))
    b.centerOn(QPointF(2150, 2100))
    pump()
    want = I.exact_rect(ta).top()
    rb = I.exact_rect(tb_)
    start = b.mapFromScene(rb.center())
    dy = (want - rb.top()) + 4      # hedefe 4 birim kala bırak: yapışmalı
    end = b.mapFromScene(rb.center() + QPointF(-30, dy))
    mouse(vp, PRESS, start, L, L)
    mouse(vp, MOVE, start + QPoint(5, 5), NB, L)
    mouse(vp, MOVE, end, NB, L)
    guides = bool(b._guides)
    mouse(vp, REL, end, L, NB)
    pump()
    step("akıllı kılavuz: sürüklerken üst kenara yapışır, kılavuz çizgisi çıkar",
         guides and abs(I.exact_rect(tb_).top() - want) < 0.01 and not b._guides)

    # katmanlar paneli
    win.set_panel(True)
    win.panel.set_layers_open(True)
    pump(10)
    lp = win.layers
    lp.refresh()
    rows_ok = lp.list.count() == len(sc.content_items())
    sc.clearSelection()
    lp.list.item(0).setSelected(True)
    pump()
    top_item = max(sc.content_items(), key=lambda i: i.zValue())
    sel_sync = top_item.isSelected()
    order = b.layer_order()
    b.set_layer_order(list(reversed(order)))
    rev_ok = b.layer_order() == list(reversed(order))
    win.page.undo.undo()
    step("katmanlar paneli: satırlar, seçim eşlemesi, sıralama (+geri al)",
         rows_ok and sel_sync and rev_ok and b.layer_order() == order)
    shot(win, "13_katmanlar")
    sc.clearSelection()
    pump()
    step("seçim çubuğu: seçim kalkınca gizlenir", not b.selbar.isVisible())
    g0 = prefs.get("grid", "dots")
    key(vp, Qt.Key.Key_R, "", CTRL)
    step("Ctrl+R ızgarayı değiştirir", prefs.get("grid", "dots") != g0)
    key(vp, Qt.Key.Key_R, "", CTRL)
    key(vp, Qt.Key.Key_R, "", CTRL)

    # ---- paket 3: döndür / çevir / kırp / saydamlık / dolgu / yazı biçimi
    # yazı / hücre düzenleme sahnenin etkin olmasını ister: pencere arka planda kalmışsa etkinleştir
    win.activateWindow()
    win.raise_()
    try:
        QApplication.setActiveWindow(win)
    except Exception:
        pass
    pump(10)
    win.set_panel(False)
    for it in list(sc.content_items()):
        sc.removeItem(it)
    img = QImage(200, 100, QImage.Format.Format_RGB32)
    img.fill(QColor("#4caf50"))
    for x in range(100):
        for y in range(100):
            img.setPixelColor(x, y, QColor("#e53935"))      # sol yarı kırmızı
    ri = b.insert_image(img, QPointF(0, 0))
    pump()
    c0 = I.exact_rect(ri).center()
    sc.clearSelection()
    ri.setSelected(True)
    b.rotate_selection(90)
    r90 = I.exact_rect(ri)
    rot_ok = (abs(r90.width() - 100 * ri.scale()) < 0.6 and abs(r90.height() - 200 * ri.scale()) < 0.6
              and abs(r90.center().x() - c0.x()) < 0.6 and abs(r90.center().y() - c0.y()) < 0.6)
    win.page.undo.undo()
    step("90° döndür: en/boy yer değiştirir, merkez sabit (+geri al)",
         rot_ok and I.geom(ri) == (0.0, False, False) and abs(I.exact_rect(ri).width() - 200 * ri.scale()) < 0.6)
    b.flip_selection("h")
    pm = render_scene(sc, rect=I.exact_rect(ri))
    left = pm.pixelColor(5, pm.height() // 2) if pm is not None else QColor()
    step("yatay çevir: sol yarı yeşil olur", I.geom(ri)[1] and left.green() > 120 and left.red() < 120)
    win.page.undo.undo()
    # tutamaçtan sürükleyerek döndür
    b.centerOn(c0)
    pump()
    rh = b._rot_handle()
    hp = b.mapFromScene(rh[1])
    cc = b.mapFromScene(rh[2])
    tgt = QPoint(cc.x() + 200, cc.y())                     # merkezin sağı → 90°
    mouse(vp, PRESS, hp, L, L)
    mouse(vp, MOVE, hp + QPoint(3, 2), NB, L)
    mouse(vp, MOVE, tgt + QPoint(0, 3), NB, L)             # 90°'ye yakın: dik açıya yapışmalı
    mouse(vp, REL, tgt + QPoint(0, 3), L, NB)
    pump()
    step("döndürme tutamacı: sürükleyince döner, dik açıya yapışır, tek geri al",
         rh is not None and abs(I.geom(ri)[0] - 90) < 0.01 and win.page.undo.undoText() == "rotate")
    win.page.undo.undo()
    # kırp: sağ yarıyı bırak
    b.start_crop(ri)
    crop_mode = b._crop is not None and not b.selbar.isVisible()
    b._crop["rect"] = QRectF(100, 0, 100, 100)
    key(vp, Qt.Key.Key_Return)
    pump()
    er = I.exact_rect(ri)
    crop_ok = (ri.pixmap().width() == 100 and ri.pixmap().height() == 100
               and abs(er.width() - 100 * ri.scale()) < 0.6)
    # içerik yerinde kalmalı: kırpılan görselin sol kenarı eski görselin ortasında
    full_left = c0.x() - 100 * ri.scale()
    content_ok = abs(er.left() - (full_left + 100 * ri.scale())) < 0.6
    step("kırp (çift tık / Enter): kalan parça yerinde durur, boyut doğru",
         crop_mode and crop_ok and content_ok and ri.pixmap().toImage().pixelColor(5, 5).green() > 120)
    d_ = I.to_dict(ri)
    win.page.undo.undo()
    step("kırpmayı geri al: görselin tamamı geri gelir", ri.pixmap().width() == 200)
    # Esc vazgeçer
    b.start_crop(ri)
    b._crop["rect"] = QRectF(0, 0, 50, 50)
    key(vp, Qt.Key.Key_Escape)
    step("kırpmada Esc: değişiklik yok", b._crop is None and ri.pixmap().width() == 200)
    # saydamlık + dolgu + yazı biçimi + kayıt
    sc.clearSelection()
    ri.setSelected(True)
    b.rotate_selection(30)
    b.set_opacity_items([ri], 0.5)
    shp = I.StrokeItem("rect", "#e53935", 4, [QPointF(400, 0), QPointF(600, 120)])
    sc.addItem(shp)
    sc.clearSelection()
    shp.setSelected(True)
    b.fill_selection("#64b5f6")
    inside_hit = shp.shape().contains(shp.mapFromScene(QPointF(500, 60)))
    tx = b.new_text(QPointF(0, 300), "Merhaba")
    b.finish_text()
    texts = [it for it in sc.content_items() if isinstance(it, I.TextItem)]
    tx = texts[0] if texts else None
    sc.clearSelection()
    if tx is not None:
        tx.setSelected(True)
    b.toggle_text("bold")
    b.text_align("center")
    s0 = I.text_style(tx)[0] if tx is not None else 0
    b.text_size(1.2)
    pump()
    info = b.selection_info()
    bar_ok = b.selbar.b_bold.isVisible() and b.selbar.b_bold.isChecked() and not b.selbar.b_crop.isVisible()
    style_ok = tx is not None and tx.bold and tx.align == "center" and abs(I.text_style(tx)[0] - s0 * 1.2) < 0.2
    rd = [I.from_dict(I.to_dict(x)) for x in (ri, shp, tx)]
    rt_ok = (abs(I.geom(rd[0])[0] - 30) < 0.01 and abs(rd[0].opacity() - 0.5) < 0.01
             and rd[0].pixmap().width() == 200 and rd[1].fill == "#64b5f6" and rd[2].bold and rd[2].align == "center"
             and abs(I.exact_rect(rd[0]).center().x() - I.exact_rect(ri).center().x()) < 0.6)
    cr = I.from_dict(d_)
    step("saydamlık, şekil dolgusu (içi tıklanır), kalın/ortala/büyüt, seçim çubuğu düğmeleri",
         style_ok and bar_ok and info["texts"] == 1 and inside_hit and shp.fill == "#64b5f6")
    step("kayıt: döndürme / saydamlık / dolgu / yazı biçimi / kırpma korunur",
         rt_ok and cr.pixmap().width() == 100)
    sc.clearSelection()
    ri.setSelected(True)
    pump()
    shot(win, "14_dondur")

    # ---- tablo: kenarlı / kenarsız, hücreye yazma, Tab, sütun genişliği, kayıt
    for it in list(sc.content_items()):
        sc.removeItem(it)
    state.set_tool("pen")
    n0 = win.page.undo.count()
    tb = b.insert_table(2, 2)
    pump()
    ins_ok = isinstance(sc.focusItem(), I.CellEditor) and tb.edit == (0, 0) and tb.border
    for i, w_ in enumerate(["Konu", "Kim", "Tasarım", "Ayşe"]):
        if i:
            key(b, Qt.Key.Key_Tab)
        for ch in w_:
            key(b, 0, ch)
    key(b, Qt.Key.Key_Tab)              # son hücrede Tab: yeni satır
    tab_row = tb.rows == 3 and tb.edit == (2, 0)
    key(b, Qt.Key.Key_Escape)
    pump()
    step("tablo: ekle, hücrelere yaz, Tab ile geç, son hücrede yeni satır",
         ins_ok and tb.cells[:2] == [["Konu", "Kim"], ["Tasarım", "Ayşe"]] and tab_row and b.editing_text() is None
         and win.page.undo.count() == n0 + 2)
    win.page.undo.undo()
    step("tablo yazısını geri al: hücreler boşalır", tb.cells == [["", ""], ["", ""]])
    win.page.undo.redo()
    # kalem aracındayken çift tık: o hücreye yazar, nokta bırakmaz
    b.centerOn(I.exact_rect(tb).center())
    pump()
    cp = b.mapFromScene(tb.mapToScene(tb.cell_rect(1, 1).center()))
    n1 = len(sc.content_items())
    mouse(vp, PRESS, cp, L, L)
    mouse(vp, REL, cp, L, NB)
    mouse(vp, QEvent.Type.MouseButtonDblClick, cp, L, L)
    mouse(vp, REL, cp, L, NB)
    pump()
    step("tabloda çift tık (kalemde de): o hücre düzenlenir, nokta kalmaz",
         tb.edit == (1, 1) and len(sc.content_items()) == n1)
    key(b, Qt.Key.Key_Escape)
    # seç aracında sütun çizgisinden genişlik
    state.set_tool("select")
    sc.clearSelection()
    pump()
    w0 = tb.colw[0]
    bp = b.mapFromScene(tb.mapToScene(QPointF(tb.colw[0], tb.rowh[0] / 2)))
    drag(vp, [bp, bp + QPoint(2, 0), bp + QPoint(60, 0)])
    zf = b.zoom()
    wide_ok = abs(tb.colw[0] - (w0 + 60 / zf)) < 2 / zf
    win.page.undo.undo()
    step("sütun çizgisini sürükle: genişlik değişir (+geri al)", wide_ok and tb.colw[0] == w0)
    # kenarsız, başlık, satır / sütun ekle-sil, kayıt
    b.set_table_border(tb, False)
    b.table_op(tb, lambda: tb.insert_col(1))
    b.table_op(tb, lambda: tb.delete_row(0))
    rt = I.from_dict(I.to_dict(tb))
    step("kenarsız tablo; sütun ekle, satır sil; kayıtta korunur",
         not tb.border and tb.cols == 3 and tb.rows == 2 and not rt.border and rt.cells == tb.cells
         and rt.colw == tb.colw and I.exact_rect(rt).width() == I.exact_rect(tb).width())
    win.page.undo.undo()
    win.page.undo.undo()
    win.page.undo.undo()
    step("tablo işlemlerini geri al: kenarlı 3×2'ye döner", tb.border and tb.cols == 2 and tb.rows == 3)
    sc.clearSelection()
    tb.setSelected(True)
    pump()
    step("seçim çubuğu: tabloda tablo / kenar / yazı boyutu düğmeleri",
         b.selbar.b_table.isVisible() and b.selbar.b_corner.isVisible() and b.selbar.b_bigger.isVisible()
         and not b.selbar.b_bold.isVisible())
    shot(win, "15_tablo")

    # ---- yan panel, kalınlık, klasörler
    step("uygulama açılınca notlar paneli açık (kapatılıp çıkılmış olsa da)", panel_at_start)
    from yazit.tools import COLORS, SIZES, DEFAULT_WIDTH
    step("ana renkler beyaz, siyah, mavi, kırmızı; ince kalem",
         COLORS[:4] == ["#ffffff", "#000000", "#3ea6ff", "#ff453a"] and min(SIZES) <= 1.5
         and DEFAULT_WIDTH <= 2.5)
    from yazit.widthmenu import build_width_menu
    from PyQt6.QtWidgets import QMenu
    w_before = state.width
    mm = QMenu(win)
    box = build_width_menu(mm)
    box.slider.setValue(13)            # 6,5 px
    w_set = state.width
    mm.deleteLater()
    pen_btn = win.area.toolbar.tool_btns["pen"]
    step("kaleme sağ tık: kalınlık kaydırıcısı (yarım piksel adım), sağ tık menüsü bağlı",
         abs(w_set - 6.5) < 1e-6 and pen_btn.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu)
    state.set_width(w_before)

    st = win.store
    win.set_panel(True)
    pg = win.page
    if not pg.saved_once:
        b.new_text(QPointF(0, 0), "klasör testi")
        b.finish_text()
        st.flush()
    fid = win.panel.new_folder()
    pump(5)
    editing = win.panel.list.state() == win.panel.list.State.EditingState
    st.list_changed.emit()                      # yazarken otomatik kayıt listeyi yenilemeye kalkar: ertelenmeli
    from PyQt6.QtWidgets import QLineEdit
    eds = [w_ for w_ in win.panel.list.viewport().findChildren(QLineEdit) if w_.isVisible()]
    if eds:
        eds[0].setText("Toplantılar")
        key(eds[0], Qt.Key.Key_Return)
    pump(5)
    fid = "Toplantılar" if st.folder("Toplantılar") else fid      # klasör = diskteki alt klasör (adıyla)
    win.panel.list.moved.emit(pg.id, fid)       # sürükle-bırak sonucu
    pump(5)
    rows = [(win.panel.list.item(i).data(Qt.ItemDataRole.UserRole + 1), win.panel.list.item(i).data(Qt.ItemDataRole.UserRole))
            for i in range(win.panel.list.count())]
    st.flush()
    from yazit.pages import NoteStore
    s3 = NoteStore()
    step("klasör: aç, adını yaz, notu sürükleyip bırak; panelde klasörün altında, yeniden açılışta korunur",
         editing and pg.folder == fid and rows[0] == ("folder", fid) and rows[1] == ("note", pg.id)
         and s3.get(pg.id).folder == fid and s3.folder(fid)["name"] == "Toplantılar"
         and os.path.dirname(pg.file) == os.path.join(st.root, "Toplantılar") and pg.file.endswith(".yazit"))
    st.set_folder_open(fid, False)
    win.panel.set_current(None)
    pump()
    hidden = all(win.panel.list.item(i).data(Qt.ItemDataRole.UserRole) != pg.id for i in range(win.panel.list.count()))
    win.panel.set_current(pg.id)
    st.set_folder_open(fid, True)
    win.new_note(fid)
    newp = win.page
    in_folder = newp.folder == fid
    win.open_page(pg)
    shot(win, "16_klasor")
    st.delete_folder(fid)
    step("klasör kapanır, klasörde yeni not; klasör silinince notlar kalır",
         hidden and in_folder and pg.folder == "" and st.get(pg.id) is not None and not st.folders)

    # ---- .yazit dosyaları: Resimler\\yazit (testte geçici klasör), başlıkla ad, dışarıdan açma, eski notları taşıma
    import json as _json
    import shutil as _sh
    from yazit import pages as PG
    from yazit.config import NOTES_DIR
    win.open_page(pg)
    pump()
    with open(pg.file, encoding="utf-8") as f_:
        dd = _json.load(f_)
    old_file = pg.file
    win.store.rename(pg, "Proje: Sunum")
    step(".yazit dosyası: Resimler\\yazit içinde, çizimler içinde; başlık değişince dosya adı da değişir",
         dd.get("format") == "delta-note" and dd.get("id") == pg.id and dd.get("items")
         and os.path.basename(pg.file) == "Proje. Sunum.yazit" and not os.path.exists(old_file)
         and os.path.dirname(pg.file) == st.root)
    ext_dir = os.path.join(TMP, "masaustu")
    os.makedirs(ext_dir, exist_ok=True)
    ext = os.path.join(ext_dir, "Arkadaştan gelen.delta")
    _sh.copy2(pg.file, ext)
    ep = win.open_file(ext)
    pump()
    b.new_text(QPointF(400, 400), "ek yazı")
    b.finish_text()
    st.flush()
    with open(ext, encoding="utf-8") as f_:
        n_items = len(_json.load(f_)["items"])
    step("eski .delta çift tık: dışarıdaki dosya açılır, kopya kimliği yenilenir, değişiklik o dosyaya yazılır",
         ep is not None and win.page is ep and ep.id != pg.id and ep.external
         and ep.file == ext and ep.display_title() == "Proje: Sunum" and n_items == len(dd["items"]) + 1)
    # eski sürümün notu (%LOCALAPPDATA%\\yazit\\notes\\<id>.json) bir kez taşınır, eskisi yedek kalır
    legacy_id = "20250101-101010-abcd"
    with open(os.path.join(NOTES_DIR, legacy_id + ".json"), "w", encoding="utf-8") as f_:
        _json.dump({"version": 1, "items": dd["items"]}, f_)
    with open(os.path.join(NOTES_DIR, "index.json"), "w", encoding="utf-8") as f_:
        _json.dump({legacy_id: {"title": "Eski not", "created": 1735725010, "modified": 1735725010}}, f_)
    root2 = os.path.join(TMP, "notes2")
    s4 = PG.NoteStore(root2)
    lp = s4.get(legacy_id)
    step("eski notlar .yazit'e taşınır (her not bir kez), eski dosya yedek kalır",
         lp is not None and os.path.exists(os.path.join(root2, "Eski not.yazit"))
         and os.path.exists(os.path.join(NOTES_DIR, legacy_id + ".json")) and legacy_id in prefs.get("migrated_ids", [])
         and PG.NoteStore(os.path.join(TMP, "notes3")).get(legacy_id) is None)

    # ---- ad değişikliği (delta → yazıt): eski .delta notları, kamug bağlantısı, klasör taşıma
    old_note = os.path.join(st.root, "Eski delta notu.delta")
    _sh.copy2(pg.file, old_note)
    with open(old_note, encoding="utf-8") as f_:
        od = _json.load(f_)
    od["id"] = "20260101-000000-dlta"
    with open(old_note, "w", encoding="utf-8") as f_:
        _json.dump(od, f_)
    st.scan()
    opn = st.get("20260101-000000-dlta")
    if opn is not None:
        win.open_page(opn)
        pump()
        win.store.rename(opn, "Eski not yeni ad")
    step("eski .delta notu not klasöründe listelenir; adı değişince .delta uzantısı korunur, içerik \"delta-note\"",
         opn is not None and opn.file == os.path.join(st.root, "Eski not yeni ad.delta")
         and os.path.isfile(opn.file) and not os.path.exists(old_note)
         and _json.load(open(opn.file, encoding="utf-8")).get("format") == "delta-note")
    from yazit.config import is_note_file
    step("komut satırı / sürükle-bırak: .yazit ve eski .delta not dosyası sayılır",
         is_note_file(r"C:\x\a.yazit") and is_note_file(r"C:\x\B.DELTA") and not is_note_file(r"C:\x\a.png"))
    from PyQt6.QtCore import QMimeData, QUrl
    md_ = QMimeData()
    md_.setUrls([QUrl.fromLocalFile(ext), QUrl.fromLocalFile(pg.file)])
    step("not dosyası tuvale sürüklenince not olarak açılacak dosyalar bulunur",
         b._mime_ok(md_) and [os.path.normcase(x) for x in b._note_paths(md_)]
         == [os.path.normcase(ext), os.path.normcase(pg.file)])
    from yazit import kamuglink as KL
    from yazit import items as IT
    vid = os.path.join(TMP, "video.mp4")
    t_new = IT.from_dict({"t": "text", "txt": "kamug", "x": 0, "y": 0, "ln": {"kamug": vid, "t": 12.5}})
    t_old = IT.from_dict({"t": "text", "txt": "gamma", "x": 0, "y": 0, "ln": {"gamma": vid, "t": 3}})
    t_both = {"kamug": vid, "gamma": os.path.join(TMP, "eski.mp4"), "t": 1}
    step("kamug bağlantısı: \"kamug\" anahtarı önce, eski \"gamma\" yedek; kayıtta \"kamug\" yazılır",
         t_new is not None and t_new.link == {"kamug": vid, "t": 12.5}
         and t_old is not None and t_old.link == {"kamug": vid, "t": 3.0}
         and KL.video_of(t_both) == vid and IT.to_dict(t_old).get("ln") == {"kamug": vid, "t": 3.0}
         and KL.open_link({"kamug": os.path.join(TMP, "yok.mp4"), "t": 0}) == "missing"
         and KL.fmt(3725) == "1:02:05")
    from yazit import config as CF
    mig = os.path.join(TMP, "migrate")
    o1, n1 = os.path.join(mig, "a", "delta"), os.path.join(mig, "a", "yazit")
    os.makedirs(os.path.join(o1, "kamug"))
    open(os.path.join(o1, "kamug", "not.yazit"), "w").close()
    r1 = CF._migrate_dir(o1, n1, both="old")
    o2, n2 = os.path.join(mig, "b", "delta"), os.path.join(mig, "b", "yazit")
    os.makedirs(o2)
    os.makedirs(n2)
    open(os.path.join(o2, "x.delta"), "w").close()
    open(os.path.join(n2, "y.yazit"), "w").close()
    r2 = CF._migrate_dir(o2, n2, both="old")
    o3, n3 = os.path.join(mig, "c", "delta"), os.path.join(mig, "c", "yazit")
    os.makedirs(o3)
    os.makedirs(n3)                     # boş yeni klasör (ör. başka program erken açtı): kaldırılıp taşınır
    open(os.path.join(o3, "z.delta"), "w").close()
    r3 = CF._migrate_dir(o3, n3, both="old")
    step("klasör taşıma: eski varsa yeni ada taşınır, eski yolla gelen dosya yeni yola çevrilir; ikisi de doluysa "
         "dokunulmaz (eski kullanılır); boş yeni klasör engel olmaz",
         r1 == n1 and not os.path.exists(o1) and os.path.isfile(os.path.join(n1, "kamug", "not.yazit"))
         and CF.remap_old_path(os.path.join(o1, "kamug", "not.yazit")) == os.path.join(n1, "kamug", "not.yazit")
         and r2 == o2 and os.path.isfile(os.path.join(o2, "x.delta")) and os.path.isfile(os.path.join(n2, "y.yazit"))
         and r3 == n3 and os.path.isfile(os.path.join(n3, "z.delta")) and not os.path.exists(o3))
    # varsayılan klasör (Resimler\delta → Resimler\yazit): gerçek Resimler yerine geçici klasör
    fake_pics = os.path.join(mig, "Pictures")
    os.makedirs(os.path.join(fake_pics, "delta", "Araştırma"))
    saved = (CF._std_location, dict(CF._defaults), {k: prefs.data.get(k) for k in CF._PATH_PREFS + CF._RECENT_PREFS})
    try:
        CF._std_location = lambda kind: fake_pics
        CF._defaults.clear()
        for k in CF._PATH_PREFS:
            prefs.data.pop(k, None)
        prefs.data["research_recent"] = [os.path.join(fake_pics, "delta", "Araştırma")]
        d1 = CF.default_dir("PicturesLocation")
        rec = list(prefs.get("research_recent"))
    finally:
        CF._std_location, CF._defaults = saved[0], saved[1]
        for k, v in saved[2].items():
            if v is None:
                prefs.data.pop(k, None)
            else:
                prefs.data[k] = v
        prefs.save()
    step("varsayılan not klasörü Resimler\\delta → Resimler\\yazit taşınır, son araştırma yolları yeni yola çevrilir",
         d1 == os.path.join(fake_pics, "yazit") and os.path.isdir(os.path.join(fake_pics, "yazit", "Araştırma"))
         and not os.path.exists(os.path.join(fake_pics, "delta"))
         and rec == [os.path.join(fake_pics, "yazit", "Araştırma")])

    # ---- 1.4: yazı tipleri, tüm alfabeler, katmanlar notların altında, kalınlık çubuğu, çizgi türleri
    from PyQt6.QtGui import QTextLayout
    from yazit import fonts as FN

    def used_fonts(fnt, s):
        lay = QTextLayout(s, fnt)
        lay.beginLayout()
        lay.createLine()
        lay.endLayout()
        return [(r.rawFont().familyName(), all(g != 0 for g in r.glyphIndexes())) for r in lay.glyphRuns()]
    scripts = ["\U00010C00\U00010C07\U00010C03", "中文字", "Привет", "हिन्दी", "한국어", "ひらがな", "مرحبا", "ελληνικά",
               "\U00010330\U00010331", "\U00010000"]
    bad = [s for s in scripts if not all(ok for _f, ok in used_fonts(FN.font(), s))]
    step("tüm alfabeler harf olarak çizilir (Göktürk, Çince, Kiril, Hintçe, Korece, Japonca, Arapça, Gotik, Linear B)",
         not bad and used_fonts(FN.font(), scripts[0])[0][0] == "Segoe UI Historic")
    step("yazıt ile gelen ücretsiz yazı tipleri yüklenir, Türkçe harfleri var",
         len(FN.bundled()) >= 15 and "Unbounded" in FN.bundled() and "Inter Thin" not in FN.system_fonts()
         and all(ok for _f, ok in used_fonts(FN.font("Unbounded"), "ğüşıöçĞÜŞİÖÇ")))
    win.open_page(st.create())
    pump()
    b = win.board
    sc = b.scene()
    tx = b.new_text(QPointF(0, 0), "Başlık 𐱅𐰇𐰼𐰚")
    b.finish_text()
    tb4 = b.insert_table(2, 2)
    b.finish_text()
    sc.clearSelection()
    tx.setSelected(True)
    tb4.setSelected(True)
    pump()
    font_btn = b.selbar.b_font.isVisible()
    b.set_font_family("Unbounded")
    rt = I.from_dict(I.to_dict(tx))
    ok_set = tx.family == "Unbounded" and tb4.family == "Unbounded" and rt.family == "Unbounded" \
        and tx.font().family() == "Unbounded" and I.to_dict(tb4).get("ff") == "Unbounded"
    win.page.undo.undo()
    step("yazı tipi: seçili yazı + tabloya uygulanır, kaydedilir, geri alınır; yeni yazı son seçileni kullanır",
         font_btn and ok_set and tx.family == "" and tb4.family == "" and b.default_family() == "Unbounded")
    from yazit.fontpick import FontPicker
    fp = FontPicker("Unbounded")
    fp.search.setText("unbou")
    first = fp.first_visible()
    step("yazı tipi seçici: arama süzer, seçili yazı tipi işaretli",
         first is not None and first.data(Qt.ItemDataRole.UserRole) == "Unbounded"
         and fp.list.currentItem() is not None and fp.list.currentItem().data(Qt.ItemDataRole.UserRole) == "Unbounded")
    fp.deleteLater()
    prefs.set("font_family", "")
    pnl = win.panel
    win.set_panel(True)
    pnl.set_layers_open(True)
    pump()
    below = pnl.layers_box.isVisible() and pnl.layers_box.y() > pnl.list.y() and pnl.list.isVisible()
    pnl.set_layers_open(False)
    pump()
    closed = not pnl.layers.isVisible() and pnl.list.isVisible() and prefs.get("layers_open") is False
    win.toggle_layers()
    pump()
    step("katmanlar notların altında: başlıktan açılır / kapanır, Ctrl+Shift+K açar",
         below and closed and pnl.layers_open() and pnl.layers.isVisible())
    from yazit.toolbar import t_to_w, w_to_t
    ws = win.board.parentWidget().toolbar.width_slider
    w0 = state.width
    click(ws, QPoint(ws.width() - 12, ws.height() // 2), L)
    w_max = state.width
    click(ws, QPoint(12, ws.height() // 2), L)
    w_min = state.width
    state.set_width(w0)
    step("kalınlık çubuğu: araç çubuğunda, tıklanan yere ayarlanır (ince uç ↔ kalın uç)",
         ws.isVisible() and w_max == 30 and w_min == 0.5 and abs(t_to_w(w_to_t(2.5)) - 2.5) < 0.01)
    from yazit.tools import state as _st
    sc.clearSelection()
    b.apply_dash("dot")
    vp = b.viewport()
    _st.set_tool("pen")
    drag(vp, [QPoint(200, 300), QPoint(300, 310), QPoint(400, 320)])
    pen_it = max((i for i in sc.content_items() if isinstance(i, I.StrokeItem)), key=lambda i: i.zValue())
    sc.clearSelection()
    pen_it.setSelected(True)
    pump()
    dash_btn = b.selbar.b_dash.isVisible()
    b.apply_dash("dash")
    rt = I.from_dict(I.to_dict(pen_it))
    win.page.undo.undo()
    step("çizgi türü: kalem noktalı çizer, seçili çizgi kesiğe döner (+kayıt, geri al)",
         _st.dash == "dot" and dash_btn and rt.dash == "dash" and pen_it.dash == "dot"
         and pen_it.pen().dashPattern() != [])
    _st.set_dash("solid")
    shot(win, "20_yazi_tipi_katmanlar")

    # ---- 1.4: kalem türleri, ince silgi, ok bükme, rötuş (arka plan sil), damlalık, kova
    from PyQt6.QtGui import QPainter as _QP
    win.open_page(st.create())
    pump()
    b = win.board
    sc = b.scene()
    vp = b.viewport()
    b.resetTransform()
    b.centerOn(QPointF(0, 0))
    pump()
    ok_br = True
    for i, br in enumerate(("pen", "calli", "marker", "pencil", "crayon", "spray", "water")):
        _st.set_brush(br)
        y = 60 + i * 30
        drag(vp, [QPoint(80, y), QPoint(140, y + 8), QPoint(200, y - 6), QPoint(260, y)])
        it = max((x for x in sc.content_items() if isinstance(x, I.StrokeItem)), key=lambda x: x.zValue())
        ok_br = ok_br and it.brush == br and I.from_dict(I.to_dict(it)).brush == br \
            and not b.grab().toImage().isNull()
    _st.set_brush("pen")
    step("kalem türleri: kalem, kaligrafi, keçeli, kurşun kalem, pastel, sprey, suluboya çizer ve kaydedilir",
         ok_br and _st.tool == "pen")
    for x in list(sc.content_items()):
        sc.removeItem(x)
    _st.set_tool("pen")
    drag(vp, [QPoint(100, 400), QPoint(250, 400), QPoint(400, 400)])
    line_it = [x for x in sc.content_items() if isinstance(x, I.StrokeItem)]
    _st.set_eraser_mode("part")
    _st.set_eraser_size(20)
    drag(vp, [QPoint(250, 370), QPoint(250, 430)])
    parts = [x for x in sc.content_items() if isinstance(x, I.StrokeItem)]
    win.page.undo.undo()
    back = [x for x in sc.content_items() if isinstance(x, I.StrokeItem)]
    _st.set_eraser_mode("object")
    drag(vp, [QPoint(250, 370), QPoint(250, 430)])
    gone = [x for x in sc.content_items() if isinstance(x, I.StrokeItem)]
    step("ince silgi: çizginin yalnızca geçtiği yerini keser (2 parça, geri al); nesne silgisi tümden siler",
         len(line_it) == 1 and len(parts) == 2 and back == line_it and not gone)
    _st.set_eraser_mode("part")
    ws = win.board.parentWidget().toolbar.width_slider
    _st.set_tool("eraser")
    w_before = _st.width
    click(ws, QPoint(ws.width() - 12, ws.height() // 2), L)
    big = _st.eraser_size
    click(ws, QPoint(12, ws.height() // 2), L)
    step("silgi boyutu: silgi seçiliyken kalınlık çubuğu silgiyi ayarlar (kalem kalınlığı değişmez)",
         big == 160 and _st.eraser_size == 4 and _st.width == w_before)
    _st.set_eraser_size(22)
    _st.set_tool("arrow")
    drag(vp, [QPoint(150, 300), QPoint(300, 300), QPoint(450, 300)])
    arw = max((x for x in sc.content_items() if isinstance(x, I.StrokeItem)), key=lambda x: x.zValue())
    _st.set_tool("select")
    sc.clearSelection()
    arw.setSelected(True)
    pump()
    mid = b.mapFromScene(arw.mapToScene(I.bend_point(arw)))
    drag(vp, [mid, mid + QPoint(0, -40), mid + QPoint(0, -80)])
    bent = arw.bend is not None and abs(arw.mapToScene(arw.bend).y() - b.mapToScene(mid + QPoint(0, -80)).y()) < 2
    tip = b.mapFromScene(arw.mapToScene(arw.pts[-1]))
    drag(vp, [tip, tip + QPoint(30, 40), tip + QPoint(60, 80)])
    moved_tip = abs(arw.mapToScene(arw.pts[-1]).y() - b.mapToScene(tip + QPoint(60, 80)).y()) < 2
    rt = I.from_dict(I.to_dict(arw))
    win.page.undo.undo()
    win.page.undo.undo()
    step("ok bükme: ortadaki tutamaç oku eğer, uçtaki tutamaç ucu taşır (+kayıt, geri al)",
         bent and moved_tip and rt.bend is not None and arw.bend is None)
    # rötuş
    src = QImage(300, 200, QImage.Format.Format_ARGB32)
    src.fill(QColor("#eef1f4"))
    pq = _QP(src)
    pq.setRenderHint(_QP.RenderHint.Antialiasing)
    pq.setBrush(QColor("#d03a30"))
    pq.drawEllipse(QRectF(60, 30, 180, 140))
    pq.setBrush(QColor("#111111"))
    pq.drawRect(QRectF(130, 80, 40, 40))
    pq.end()
    im = b.insert_image(src, QPointF(0, 0), select=False)
    pump()
    n_undo = win.page.undo.index()
    sc.clearSelection()
    im.setSelected(True)
    pump()
    rt_btn = b.selbar.b_retouch.isVisible()
    b.start_retouch()
    pump()
    r = b._retouch
    on = r is not None and b.retouch_bar.isVisible() and im.checker
    r.auto_bg()
    a_corner = r.img.pixelColor(2, 2).alpha()
    a_mid = r.img.pixelColor(150, 50).alpha()
    cp = im.mapToScene(QPointF(150, 100))
    r.set_tool("wand")
    click(vp, b.mapFromScene(cp), L)
    sel_n = r.mask.count(1) if r.mask is not None else 0
    key(vp, Qt.Key.Key_Delete)
    hole = r.img.pixelColor(150, 100).alpha()
    r.set_tool("restore")
    r.size = 30
    drag(vp, [b.mapFromScene(cp), b.mapFromScene(cp) + QPoint(2, 0)])
    restored = r.img.pixelColor(150, 100).alpha()
    r.set_tool("lasso")
    q0 = b.mapFromScene(im.mapToScene(QPointF(70, 90)))
    drag(vp, [q0, q0 + QPoint(20, 0), q0 + QPoint(20, 20), q0 + QPoint(0, 20)])
    lasso_n = r.mask.count(1) if r.mask is not None else 0
    key(vp, Qt.Key.Key_Escape)
    key(vp, Qt.Key.Key_Return)
    pump()
    fi = im.full_image()
    saved = I.from_dict(I.to_dict(im))
    one_step = win.page.undo.index() == n_undo + 1
    step("rötuş: otomatik arka plan siler, değnek + Delete, geri getir fırçası, kement; Enter tek geri al adımı",
         rt_btn and on and a_corner == 0 and a_mid == 255 and 1200 < sel_n < 2000 and hole == 0 and restored == 255
         and 300 < lasso_n < 600 and b._retouch is None and not im.checker and fi.pixelColor(2, 2).alpha() == 0
         and fi.pixelColor(150, 100).alpha() == 255 and one_step and saved.orig is not None
         and saved.full_image().pixelColor(2, 2).alpha() == 0)
    win.page.undo.undo()
    step("rötuş geri alınır (özgün pikseller döner)", im.full_image().pixelColor(2, 2).alpha() == 255)
    b.start_retouch(im)
    b._retouch.auto_bg()
    b.end_retouch(False)
    step("rötuş iptal: değişiklik atılır", im.full_image().pixelColor(2, 2).alpha() == 255 and b._retouch is None)
    # damlalık + kova
    _st.set_tool("rect")
    r0, r1 = b.mapFromScene(QPointF(200, 120)), b.mapFromScene(QPointF(320, 220))
    drag(vp, [r0, (r0 + r1) / 2, r1])
    rct = max((x for x in sc.content_items() if isinstance(x, I.StrokeItem)), key=lambda x: x.zValue())
    _st.set_tool("picker")
    pump()
    red_pt = b.mapFromScene(im.mapToScene(QPointF(90, 100)))
    click(vp, red_pt, L)
    picked = QColor(_st.color)
    _st.set_tool("fill")
    click(vp, b.mapFromScene(QPointF(260, 170)), L)
    filled = rct.fill == _st.color
    _st.set_color("#3ea6ff")
    _st.set_tool("fill")
    click(vp, b.mapFromScene(im.mapToScene(QPointF(150, 100))), L)
    blue_sq = im.full_image().pixelColor(150, 100)
    step("damlalık rengi alır ve önceki araca döner; kova şekli ve görseldeki renk bölgesini doldurur",
         picked.red() > 180 and picked.green() < 90 and filled and blue_sq.blue() > 200 and blue_sq.red() < 100)
    _st.set_tool("pen")
    _st.set_color("auto")
    shot(win, "21_rotus_kalemler")
    # tablo taşıma tutamacı: kalem açıkken ve hücre düzenlenirken de sol üstteki tutamaçtan taşınır
    tbm = b.insert_table(2, 3, at=QPointF(-250, -150))
    pump()
    editing = isinstance(b.editing_text(), I.CellEditor)
    g = b._grip_rect(tbm).center().toPoint()
    p0 = QPointF(tbm.pos())
    n_u = win.page.undo.index()
    n_str = len([x for x in sc.content_items() if isinstance(x, I.StrokeItem)])
    drag(vp, [g, g + QPoint(40, 30), g + QPoint(80, 60)])
    moved = tbm.pos() - p0
    still_one = len([x for x in sc.content_items() if isinstance(x, I.StrokeItem)]) == n_str   # çizim yapılmadı
    one_undo = win.page.undo.index() == n_u + 1
    win.page.undo.undo()
    step("tablo: sol üstteki tutamaçtan taşınır (kalem açıkken, hücre düzenlenirken de; tek geri al)",
         editing and abs(moved.x() * b.zoom() - 80) < 2 and abs(moved.y() * b.zoom() - 60) < 2 and still_one
         and one_undo and tbm.pos() == p0)
    sc.clearSelection()
    b.finish_text()
    pump()
    hover = b.mapFromScene(tbm.mapToScene(tbm.cell_rect(1, 1).center()))
    mouse(vp, MOVE, hover, NB, NB)
    pump()
    step("tablo: fare üstüne gelince tutamaç görünür", b._grip_table() is tbm)

    # ---------------------------------------------------------------- araştırma modu
    from yazit import research as RS
    from yazit.readers import PdfView, ProseView, docx_to_html
    rfold = os.path.join(TMP, "res", "Zırhlı Araçlar")
    make_sources(rfold)
    rr = RS.Research(rfold)
    rr.scan()
    rr.probe_all_now()
    types = {x.rel: x.type for x in rr.sources}
    step("araştırma: klasördeki dosyalar kaynak olur, türler doğru (ISBN / çok sayfa → kitap)",
         types.get("Ogorkiewicz - Tanks 100 Years.pdf") == "book" and types.get("Technology of Tanks.pdf") == "book"
         and types.get("hull-armor.pdf") == "article" and types.get("reaktif.docx") == "article"
         and types.get("altay.md") == "article" and types.get("leopard.jpg") == "image"
         and types.get("Tank Encyclopedia.url") == "link" and len(rr.sources) == 7)
    ogo = rr.source("Ogorkiewicz - Tanks 100 Years.pdf")
    dx = rr.source("reaktif.docx")
    step("araştırma: başlık / yazar / ISBN / sayfa / ilk satırlar okunur, künye",
         ogo.title == "Tanks: 100 Years of Evolution" and ogo.author == "Ogorkiewicz" and ogo.get("isbn") ==
         "9781472806703" and ogo.get("pages") == 12 and "Tanks" in ogo.get("excerpt", "")
         and dx.title == "Reaktif Zırh Notları" and dx.author == "Y. Özsoy" and ogo.cite(42) == "Ogorkiewicz · s. 42"
         and rr.source("Tank Encyclopedia.url").get("url") == "https://tanks-encyclopedia.com/")
    rr.set_override("hull-armor.pdf", type="book")
    rr.save()
    rr2 = RS.Research(rfold)
    rr2.scan()
    step("araştırma: tür değiştirme ve bilgiler dosyada saklanır (yeniden okunmaz)",
         rr2.source("hull-armor.pdf").type == "book" and not rr2._pending and
         os.path.isfile(os.path.join(rfold, RS.META_FILE)))
    rr2.set_override("hull-armor.pdf", type=None)
    rr2.save()
    rr2.close()
    rr.close()
    h = docx_to_html(os.path.join(rfold, "reaktif.docx"))
    step("araştırma: docx → HTML (başlık, kalın)", "<h2>Reaktif zırh</h2>" in h and "<b>ERA</b>" in h)

    rv = win.research
    win.set_research_mode(True)
    pump()
    step("araştırma modu: Ctrl+Shift+R / düğme ile açılır, ana ekran", win.in_research() and
         rv.stack.currentIndex() == 0 and win.titlebar.btn_research.isChecked() and not win.titlebar.btn_new.isVisible())
    rv.open(rfold)
    pump(10)
    rv.research.probe_all_now()
    pump(5)
    kinds = sorted({sl.src.type for sl in rv.shelf.slots})
    step("araştırma: üç sütun, rafta kitap / makale / görsel / bağlantı",
         rv.stack.currentIndex() == 1 and kinds == ["article", "book", "image", "link"] and
         rv.shelf._content_h > 300 and win.titlebar.title.text() == "Zırhlı Araçlar")
    shot(win, "60_arastirma")
    book = next(sl for sl in rv.shelf.slots if sl.src.rel == "Technology of Tanks.pdf")
    c = book.rect.center().toPoint()
    mouse(rv.shelf, MOVE, c, NB, NB)
    import time as _time
    _t0 = _time.time()
    while _time.time() - _t0 < 0.4:
        QApplication.processEvents()
    slid = rv.shelf._h.get(book.src.rel, 0) > 0.5
    mouse(rv.shelf, PRESS, c, L, L)
    mouse(rv.shelf, REL, c, L, NB)
    pump(10)
    cur = rv.pages.currentWidget()
    step("raf: kitabın üstüne gelince sırt kayar, tıklayınca PDF yeni sekmede açılır",
         slid and isinstance(cur, PdfView) and cur.n == 120 and len(rv.tabs) == 2 and
         rv.shelf.current == "Technology of Tanks.pdf")
    rv.open_source(rv.research.source("reaktif.docx"))
    pump(5)
    step("araştırma: docx sekmede okunur; aynı kaynak ikinci kez sekme açmaz",
         isinstance(rv.pages.currentWidget(), ProseView) and "1982" in rv.pages.currentWidget().toPlainText()
         and (rv.open_source(rv.research.source("reaktif.docx")) or len(rv.tabs) == 3))
    rv.close_tab(0)
    rv.close_tab(2)
    pump(3)
    step("araştırma: ilk sekme (araştırma sayfası) kapanmaz, diğerleri kapanır",
         len(rv.tabs) == 2 and rv.tabs[0][0] is None)
    rv.notes.inp.setText("Altay'da hangisi öne çıkıyor?")
    rv.notes._add()
    rv.page.title.setText("Zırh araştırması")
    rv.page._title_done()
    rv.page.body.setPlainText("Giriş metni")
    rv.page.flush()
    rv.flush()
    import json as _json
    with open(os.path.join(rfold, RS.META_FILE), encoding="utf-8") as f:
        md = _json.load(f)
    step("araştırma: not, başlık ve sayfa metni klasördeki dosyaya yazılır",
         md["notes"][-1]["text"] == "Altay'da hangisi öne çıkıyor?" and md["title"] == "Zırh araştırması"
         and "Giriş metni" in md["page"]["html"] and win.titlebar.title.text() == "Zırh araştırması")
    extra = os.path.join(TMP, "dis-kaynak.md")
    with open(extra, "w", encoding="utf-8") as f:
        f.write("# Dış kaynak\n")
    rv._dropped([extra])
    pump(3)
    step("raf: dışarıdan bırakılan dosya klasöre kopyalanır, rafa girer",
         os.path.isfile(os.path.join(rfold, "dis-kaynak.md")) and rv.research.source("dis-kaynak.md") is not None)
    with open(os.path.join(rfold, "yeni-makale.txt"), "w", encoding="utf-8") as f:
        f.write("Klasöre doğrudan konan dosya")
    for _ in range(60):
        pump(2)
        QApplication.processEvents()
        _time.sleep(0.02)
        if rv.research.source("yeni-makale.txt") is not None:
            break
    step("raf: klasöre konan dosyayı kendiliğinden görür", rv.research.source("yeni-makale.txt") is not None)
    # ---- PDF: seç, kopyala → alıntı kartı, geri al, vurgula, ara, künyeden atla
    from PyQt6.QtGui import QKeyEvent as _QKE, QTextCursor as _QTC
    from PyQt6.QtCore import QEvent as _QE
    rv.tabbar.setCurrentIndex(0)
    rv.open_source(rv.research.source("Ogorkiewicz - Tanks 100 Years.pdf"))
    pump(5)
    pv = rv.pages.currentWidget()
    ptxt = pv.page_text(0)
    ia = ptxt.find("Ogorkiewicz'e")
    pv.set_selection(0, ia, 40)
    pv.setFocus()
    body = rv.page.body
    steps0 = body.document().availableUndoSteps()
    QApplication.sendEvent(pv, _QKE(_QE.Type.KeyPress, Qt.Key.Key_C, CTRL, "c"))
    pump(3)
    html_ = body.toHtml()
    step("PDF: seçip Ctrl+C → panoya + araştırma sayfasına künyeli alıntı kartı",
         QApplication.clipboard().text().startswith("Ogorkiewicz'e göre") and "OGORKIEWICZ · S. 1" in html_
         and "delta-src:" in html_ and body.document().availableUndoSteps() > steps0)
    QApplication.sendEvent(pv, _QKE(_QE.Type.KeyPress, Qt.Key.Key_Z, CTRL, "z"))
    pump(3)
    step("PDF: okuyucuda Ctrl+Z alıntıyı tek adımda geri alır", "delta-src:" not in body.toHtml())
    pv.set_selection(0, ia, 40)
    rv.quote("Ogorkiewicz - Tanks 100 Years.pdf", "Ogorkiewicz'e göre tank tasarımı", 1, pv)
    pv.set_selection(0, ia, 13)
    pv.add_highlight("yellow")
    pv.find("koruma")
    step("PDF: vurgu araştırma dosyasına girer, arama tüm sayfalarda bulur",
         rv.research.data["highlights"]["Ogorkiewicz - Tanks 100 Years.pdf"][0]["t"] == "Ogorkiewicz'e"
         and len(pv.matches) >= 12 and pv.mi >= 0)
    shot(win, "61_pdf")
    href = None
    b0 = body.document().begin()
    while b0.isValid() and href is None:
        it_ = b0.begin()
        while not it_.atEnd():
            if it_.fragment().charFormat().anchorHref().startswith("delta-src:"):
                href = it_.fragment().charFormat().anchorHref()
            it_ += 1
        b0 = b0.next()
    pv.sel = None
    pv.verticalScrollBar().setValue(pv.verticalScrollBar().maximum())
    rv.tabbar.setCurrentIndex(0)
    rv.jump(href)
    pump(5)
    step("künyeye tıklayınca kaynak açılır, alıntılanan yer seçilir",
         rv.pages.currentWidget() is pv and pv.sel == (0, ia, 0, ia + 39))
    # ---- video dökümü → zamanlı alıntı
    with open(os.path.join(rfold, "tank-chats.mp4"), "wb") as f:
        f.write(b"\0" * 64)
    with open(os.path.join(rfold, "tank-chats.srt"), "w", encoding="utf-8") as f:
        f.write("1\n00:00:05,000 --> 00:00:08,000\nLittle Willie ilk tanktır.\n\n2\n00:01:02,500 --> "
                "00:01:06,000\nMark I cepheye çıktı.\n")
    rv.research.scan()
    rv.research.probe_all_now()
    rv.open_source(rv.research.source("tank-chats.mp4"))
    pump(3)
    tv = rv.pages.currentWidget()
    from yazit.readers import TranscriptView
    ok_tv = isinstance(tv, TranscriptView) and len(tv.cues) == 2
    if ok_tv:
        cur_ = tv.textCursor()
        blk = tv.document().findBlockByNumber(1)
        cur_.setPosition(blk.position() + 6)
        cur_.setPosition(blk.position() + blk.length() - 1, _QTC.MoveMode.KeepAnchor)
        tv.setTextCursor(cur_)
        QApplication.sendEvent(tv, _QKE(_QE.Type.KeyPress, Qt.Key.Key_C, CTRL, "c"))
        pump(3)
    step("video dökümü sekmede açılır, kopyalanan satır zamanıyla alıntı olur (künye 1:02)",
         ok_tv and "TANK-CHATS · 1:02" in body.toHtml() and "#t=62.50" in body.toHtml())
    # ---- kelimeye bağlı not
    rv.tabbar.setCurrentIndex(0)
    body.setFocus()
    cw = body.textCursor()
    cw.movePosition(_QTC.MoveOperation.Start)
    cw.movePosition(_QTC.MoveOperation.EndOfWord, _QTC.MoveMode.KeepAnchor)
    body.setTextCursor(cw)
    word = cw.selectedText()
    rv._attach()
    rv.notes.inp.setText("Bu kelimeye bağlı not")
    rv.notes._add()
    pump(5)
    nid = rv.research.notes[-1]["id"]
    rv.links.set_hot(nid)
    img_ = rv.grab()
    step("kelimeye not iliştirilir: not bağlı, kelime işaretli, halka + ok çizilir",
         rv.research.notes[-1].get("anchor", {}).get("text") == word and nid in rv.page.note_ranges()
         and not img_.isNull())
    shot(win, "62_bagli_not")
    # ---- dışa aktarma
    n_src = len(rv.research.sources)
    outs = {k: rv.export(k, os.path.join(rfold, "cikti." + k)) for k in ("html", "pdf", "md")}
    rv.research.scan()
    with open(outs["html"], encoding="utf-8") as f:
        sh = f.read()
    with open(outs["md"], encoding="utf-8") as f:
        smd = f.read()
    step("dışa aktarma: site HTML'i (raf + kenar notu), PDF, Markdown; çıktılar rafa kaynak olarak girmez",
         all(outs.values()) and os.path.getsize(outs["pdf"]) > 2000 and 'class="sn-not" data-n="' + nid + '"' in sh
         and 'class="kitap"' in sh and "<blockquote>" in sh and "> Ogorkiewicz'e göre" in smd
         and "## Kaynaklar" in smd and len(rv.research.sources) == n_src)

    rv.close_research()
    pump(3)
    step("araştırma: kapatınca ana ekranda son araştırmalar listesinde", rv.stack.currentIndex() == 0 and
         RS.recent() and os.path.normcase(RS.recent()[0]) == os.path.normcase(rfold))
    win.set_research_mode(False)
    pump()
    step("araştırma modundan çizim tahtasına dönülür", not win.in_research() and win.titlebar.btn_new.isVisible())

    from yazit.updater import is_newer, parse_version
    step("güncelleme: sürüm karşılaştırma", is_newer("v1.2.0", "1.1.0") and not is_newer("1.1.0", "1.1.0")
         and not is_newer("1.0.9", "1.1.0") and parse_version("v2") == (2, 0, 0))

    console_steps(d)

    win.quit_app()
    pump()
    fails = [n for n, ok in steps if not ok]
    print(f"\n{len(steps) - len(fails)}/{len(steps)} adım geçti")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
