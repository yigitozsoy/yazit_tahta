"""Yapay zekâ istemcileri (MCP) testi: gerçek MCP alt süreci (python main.py --mcp) + offscreen yazıt penceresi.

Ayrı tek örnek sunucusu adı (YAZIT_SERVER) kullanır: kurulu / çalışan yazıt'a dokunmaz; LOCALAPPDATA geçici klasör;
ekranı kaydetmez, kısayol kaydetmez — kullanıcı çalışırken de çalıştırılabilir.

python tests/mcp_test.py
"""
import json
import os
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.join(ROOT, "tests"))
import smoke_test as S  # noqa: E402  (LOCALAPPDATA → geçici)

TMP = S.TMP
NAME = f"yazit-mcp-test-{os.getpid()}"
os.environ["YAZIT_SERVER"] = NAME

from PyQt6.QtWidgets import QApplication  # noqa: E402


def main():
    from yazit.config import prefs
    prefs.set("notes_dir", os.path.join(TMP, "notes"))
    prefs.set("snapshot_dir", os.path.join(TMP, "pictures"))
    prefs.set("research_dir", os.path.join(TMP, "res"))
    prefs.set("check_updates", False)
    for n in ("capture", "annotate", "note", "record"):
        prefs.set("hotkey_" + n, "")
    main.app = QApplication(sys.argv)   # test boyunca yaşasın
    from PyQt6.QtGui import QFontDatabase
    QFontDatabase.addApplicationFont(r"C:\Windows\Fonts\segoeui.ttf")
    rfold = os.path.join(TMP, "res", "Zırhlı Araçlar")
    S.make_sources(rfold)
    with open(os.path.join(rfold, "tank-chats.mp4"), "wb") as f:
        f.write(b"\0" * 64)
    with open(os.path.join(rfold, "tank-chats.srt"), "w", encoding="utf-8") as f:
        f.write("1\n00:00:05,000 --> 00:00:08,000\nLittle Willie ilk tanktır.\n\n2\n00:01:02,500 --> "
                "00:01:06,000\nMark I cepheye çıktı.\n")
    from yazit.pages import NoteStore
    from yazit.window import MainWindow
    from yazit.mcpapp import McpHost
    from yazit import app as yapp
    from PyQt6.QtNetwork import QLocalServer

    class D:
        pass
    d = D()
    d.store = NoteStore()
    d.win = MainWindow(d.store)
    d.win.show()
    d.mcp = McpHost(d)
    QLocalServer.removeServer(NAME)
    srv = QLocalServer()
    srv.listen(NAME)
    yapp.serve(srv, d)
    d.win.set_research_mode(True)
    d.win.research.open(rfold)
    rv = d.win.research
    rv.research.probe_all_now()
    S.pump(5)
    # vurgu: elle (PDF görünümü açmadan)
    rv.research.data.setdefault("highlights", {})["Ogorkiewicz - Tanks 100 Years.pdf"] = [
        {"p": 2, "a": 0, "n": 10, "c": "yellow", "t": "Sayfa 3 Zırhlı"}]
    rv.research.save()
    prefs.set("mcp_enabled", True)
    prefs.set("mcp_write", "allow")

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    p = subprocess.Popen([sys.executable, os.path.join(ROOT, "main.py"), "--mcp"], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=ROOT)
    errs = []
    threading.Thread(target=lambda: errs.append(p.stderr.read()), daemon=True).start()
    nid = [0]

    def rpc(method, params=None, note=False):
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        if not note:
            nid[0] += 1
            msg["id"] = nid[0]
        p.stdin.write((json.dumps(msg, ensure_ascii=False) + "\n").encode("utf-8"))
        p.stdin.flush()
        if note:
            return None
        box = {}
        th = threading.Thread(target=lambda: box.update(r=p.stdout.readline()))
        th.start()
        t0 = time.time()
        while th.is_alive() and time.time() - t0 < 60:
            QApplication.processEvents()
            time.sleep(0.005)
        r = json.loads(box["r"].decode("utf-8"))
        assert r.get("id") == nid[0], r
        return r

    def call(name, **args):
        r = rpc("tools/call", {"name": name, "arguments": args})
        res = r["result"]
        return res["content"][0]["text"], res["isError"]

    r = rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                           "clientInfo": {"name": "claude-ai", "version": "1"}})
    S.step("mcp: initialize", r["result"]["serverInfo"]["name"] == "yazit"
           and r["result"]["protocolVersion"] == "2025-06-18")
    rpc("notifications/initialized", note=True)
    tl = rpc("tools/list")["result"]["tools"]
    S.step("mcp: tools/list 12 araç", len(tl) == 12 and all("inputSchema" in x for x in tl))
    out, err = call("list_research")
    print(out)
    S.step("mcp: list_research", not err and "Zırhlı Araçlar" in out and "yazıt'ta açık" in out)
    out, err = call("list_sources")
    print(out)
    S.step("mcp: list_sources", not err and "Tanks: 100 Years of Evolution" in out and "dökümlü" in out)
    out, err = call("read_source", source="Ogorkiewicz", start=2, end=3)
    print(out[:600])
    S.step("mcp: read_source sayfa numaralı", not err and "=== s. 2 ===" in out and "=== s. 3 ===" in out
           and "s. 4" not in out)
    out, err = call("read_source", source="tank-chats")
    S.step("mcp: video dökümü zamanlı", not err and "[1:02] Mark I" in out)
    out, err = call("read_source", source="reaktif.docx")
    S.step("mcp: docx okunur", not err and "1982" in out)
    out, err = call("search_sources", query="hareket kabiliyeti")
    print(out[:500])
    S.step("mcp: search_sources", not err and "Ogorkiewicz · s. 1" in out and "tam eşleşme" in out)
    out, err = call("search_sources", query="CEPHEYE")
    S.step("mcp: arama büyük/küçük harf + dökümde zaman", not err and "1:02" in out)
    out, err = call("get_highlights")
    S.step("mcp: get_highlights", not err and "s. 3" in out)
    out, err = call("add_quote", source="Ogorkiewicz", text="tank tasarımı üç temel özelliğin dengesidir", page=5)
    print(out)
    S.pump(5)
    html_ = rv.page.body.toHtml()
    S.step("mcp: add_quote doğrular, künye + bağlantı", not err and "OGORKIEWICZ · S. 5" in html_.upper()
           and "delta-src:Ogorkiewicz" in html_ and ("#p=5&amp;a=" in html_ or "#p=5&a=" in html_))
    out, err = call("add_quote", source="Ogorkiewicz", text="tankların uçabildiği bilinmektedir")
    S.step("mcp: kaynakta olmayan alıntı reddedilir", err and "birebir" in out)
    out, err = call("add_quote", source="tank-chats", text="Mark I cepheye çıktı.")
    S.pump(5)
    S.step("mcp: dökümden zamanlı alıntı", not err and "#t=62.50" in rv.page.body.toHtml())
    rv.page.flush()
    rv.research.save()
    out, err = call("check_quotes")
    print(out)
    S.step("mcp: check_quotes", not err and "2 alıntı denetlendi, 0 sorunlu" in out)
    out, err = call("get_page")
    S.step("mcp: get_page künyeli", not err and "Ogorkiewicz" in out and "kaynak:" in out)
    out, err = call("add_note", text="Claude'un notu", anchor="dengesidir")
    S.pump(5)
    n = rv.research.notes[-1] if rv.research.notes else {}
    S.step("mcp: add_note sözcüğe bağlı", not err and n.get("text") == "Claude'un notu"
           and (n.get("anchor") or {}).get("text", "").lower() == "dengesidir" and n["id"] in rv.page.note_ranges())
    out, err = call("get_notes")
    S.step("mcp: get_notes", not err and "Claude'un notu" in out)
    # sor kipi: balon çıkar, Reddet
    prefs.set("mcp_write", "ask")
    box = {}

    def later():
        for _ in range(400):
            QApplication.processEvents()
            if d.mcp.bubble is not None and d.mcp.bubble.isVisible():
                box["seen"] = True
                S.shot(d.mcp.bubble, "mcp_bubble") if S.SHOTS else None
                d.mcp.bubble.b_no.click()
                return
            time.sleep(0.01)
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(50, later)
    out, err = call("add_note", text="reddedilecek")
    S.step("mcp: sor kipinde balon çıkar, reddedince eklenmez", box.get("seen") and err and "reddetti" in out
           and rv.research.notes[-1]["text"] != "reddedilecek")

    def later_ok():
        for _ in range(400):
            QApplication.processEvents()
            if d.mcp.bubble is not None and d.mcp.bubble.isVisible():
                d.mcp.bubble.chk.setChecked(True)
                d.mcp.bubble.b_ok.click()
                return
            time.sleep(0.01)
    QTimer.singleShot(50, later_ok)
    out, err = call("add_note", text="onaylanan")
    S.step("mcp: Ekle + bu oturumda sorma", not err and rv.research.notes[-1]["text"] == "onaylanan"
           and d.mcp.session_allow)
    prefs.set("mcp_write", "off")
    out, err = call("add_note", text="x")
    S.step("mcp: ekleme kapalıysa reddedilir", err)
    prefs.set("mcp_enabled", False)
    out, err = call("list_sources")
    S.step("mcp: erişim kapalıyken araçlar çalışmaz", err and "kapalı" in out)
    r = rpc("bogus/method")
    S.step("mcp: bilinmeyen yöntem -32601", r["error"]["code"] == -32601)
    pl = rpc("prompts/list")["result"]["prompts"]
    pg = rpc("prompts/get", {"name": "literature_scan", "arguments": {"topic": "reaktif zırh"}})["result"]
    S.step("mcp: prompts", len(pl) == 3 and "reaktif zırh" in pg["messages"][0]["content"]["text"])
    # metin kuralları: read_source'un gösterdiği metin locate ile bulunur (satır sonu tireleri aynı kural)
    from yazit import mcpserver as MS
    pg_ = "Bu COVID-\r\n19 salgını hareket kabi-\nliyeti ve “tırnak”￾\ndenemesi"
    shown = MS.tidy(pg_)
    loc = MS.locate(pg_, "COVID-\n19 salgını hareket kabiliyeti")
    S.step("mcp: tidy / locate aynı kural (COVID-19 kalır, kabi-liyeti birleşir)",
           "kabiliyeti" in shown and "COVID-\n19" in shown and MS.locate(pg_, shown) is not None
           and loc is not None and pg_[loc[0]:loc[0] + loc[1]].endswith("liyeti"))

    class _R:
        page = {"html": '<p>Ali "merhaba" dedi.</p><p>“Gerçek alıntı”</p>'
                        '<p><a href="delta-src:a.pdf#p=2">— A · s. 2</a></p>'}
    qs = MS.page_quotes(_R())
    S.step("mcp: alıntı kartı yalnızca kendi satırından okunur", len(qs) == 1 and qs[0][0] == "Gerçek alıntı"
           and qs[0][2].get("p") == "2")
    prefs.set("mcp_enabled", True)
    prefs.set("mcp_write", "allow")
    out, err = call("add_quote", source="tank-chats", text="uydurma cümle", time=62)
    out2, err2 = call("add_quote", source="tank-chats", text="[0:05] Little Willie ilk tanktır.", time=60)
    S.pump(5)
    S.step("mcp: video alıntısı zaman verilse de doğrulanır, zaman satırdan", err and not err2
           and "#t=5.00" in rv.page.body.toHtml())
    prefs.set("mcp_enabled", False)
    # glow
    rv.shelf.glow("Ogorkiewicz - Tanks 100 Years.pdf")
    img = rv.shelf.grab()
    S.step("mcp: okunan kitap rafta parlar", bool(rv.shelf._glow) and not img.isNull())
    p.stdin.close()
    p.wait(10)
    if errs and errs[0]:
        print("STDERR:", errs[0].decode("utf-8", "replace")[-2000:])
    # Claude Desktop ayarı (geçici klasöre)
    from yazit.mcpapp import add_to_claude_desktop, claude_code_command
    cd = os.path.join(TMP, "ClaudeCfg")
    os.makedirs(cd)
    with open(os.path.join(cd, "claude_desktop_config.json"), "w", encoding="utf-8") as f:
        json.dump({"mcpServers": {"other": {"command": "x"}}, "theme": "dark"}, f)
    ok, files, e = add_to_claude_desktop([cd])
    cfg = json.load(open(files[0], encoding="utf-8"))
    S.step("mcp: Claude Desktop ayarına eklenir, diğerleri korunur", ok and "other" in cfg["mcpServers"]
           and cfg["mcpServers"]["yazit"]["args"][-1] == "--mcp" and cfg["theme"] == "dark"
           and os.path.isfile(files[0] + ".bak"))
    print(claude_code_command())
    srv.close()
    d.win.research.close_research()
    fails = [n for n, ok in S.steps if not ok]
    print(f"\n{len(S.steps) - len(fails)}/{len(S.steps)}", fails)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
