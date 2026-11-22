# yazıt — Claude için proje notları

**yazıt** (eski adı **delta**; ASCII biçimi `yazit`), **tamga** ailesinin not uygulaması, kamug'un
(eski adı gamma) kardeşi: toplantıda bir şey anlatmak ve aklına geleni not almak için
**çizim tahtası + ekran alıntısı + ekrana çizim** aracı. Tema, renkler, başlık çubuğu, ikonlar kamug ile aynı
(`C:\Users\yigit\OneDrive\Desktop\kamug` — kamug'un deposu, tasarım referansı orası; onun CLAUDE.md'sindeki çalışma tarzı
kuralları burada da geçerli: Türkçe, sade varsayılanlar, gri vurgu, mor yok, önce çalıştırıp doğrula).

- Python 3.14 · PyQt6 (Pillow isteğe bağlı) · yalnızca Windows 10/11
- Sürüm: `yazit/__init__.py` → `__version__`
- Repo: https://github.com/yigitozsoy/yazit_tahta (herkese açık; sürümler Releases'ta, kurulum + zip). Eski adı
  delta_board; GitHub eski adresi yönlendirir (eski sürümlerin güncelleme denetimi de çalışır). `__init__.REPO`.
  Commit kimliği yerel: `Yiğit Özsoy <yigitozsoy@users.noreply.github.com>`. Push / etiket / release öncesi onay al
  (kullanıcı "commit et githuba koy, sorma" dediyse doğrudan yap).
- Çalıştır: `python main.py` · tepside sessiz başlat: `python main.py --tray` · alıntı başlat: `--snip`
  (kurulum masaüstüne / Başlat'a "yazıt alıntı" kısayolu koyar, simgesi `assets/snip.ico`, `packaging/make_logo.py` üretir)
- Python 3.14 · PyQt6 · pypdfium2 (araştırma modunun PDF okuyucusu; pakette `collect_all`, selfcheck 4 = pdfium yok)
- Test: `python tests/smoke_test.py` (175 adım, gerçek 2 sn'lik ffmpeg kaydı ve gerçek OCR dahil; gerçek arayüz; `--shots KLASÖR` ekran görüntüsü alır).
  Dikkat: kayıt adımları ekranın sol üst köşesini gdigrab ile gerçekten kaydeder ve global kısayol kaydeder; kullanıcı
  çalışırken çalıştırma — yalnızca ilgili bölümü offscreen bir sürücü betiğiyle (QT_QPA_PLATFORM=offscreen, geçici LOCALAPPDATA) dene
  PowerShell'de Türkçe çıktı için `$env:PYTHONIOENCODING="utf-8"`.
- Lint: `python -m pyflakes yazit tests` temiz olmalı.
- Derleme: `powershell -ExecutionPolicy Bypass -File packaging\build.ps1` → `build\dist\yazit\yazit.exe` (PyInstaller,
  ffmpeg dahil) + `build\installer\yazit-setup-X.exe` (Inno Setup 6, yönetici izni istemez) + taşınabilir zip.
  Paket denetimi: `yazit.exe --selfcheck` (0 = tamam). Kurulum çalışan yazıt'ı `yazit.exe --quit` ile kapatır;
  test kurulumunda `/NOQUIT=1` ver — ama yazıt o klasörden çalışıyorsa VERME: [InstallDelete] `_internal`'ı siler,
  kullanımdaki dosyalar yazılamaz, kurulu kopya "Failed to import encodings" hatasıyla açılmaz hale gelir. Veriler (%LOCALAPPDATA%\yazit, Resimler\yazit) kaldırmada silinmez.

## Ad değişikliği: delta → yazıt (tamga ailesi)
Aile adı **tamga** (hep küçük harf). Görünen ad her yerde **yazıt** (noktasız ı; `t("app_name")`), ASCII biçimi
**yazit**: paket `yazit/`, `yazit.exe`, `{autopf}\yazit`, `packaging/yazit.spec`, `%LOCALAPPDATA%\yazit`, tek örnek
sunucusu `yazit-single-instance-v1`, AppUserModelID `tamga.yazit`, HKCU Run değeri `yazit`, geçici dosya önekleri
`yazit-…`, çıktı `yazit-setup-X.exe` / `yazit-portable-X.zip`. Kardeş oynatıcı gamma'nın yeni adı **kamug**.
- **Bilerek eski kalanlar** (iç veri, değişirse eski notlar / araştırmalar bozulur): not JSON'unda
  `"format": "delta-note"`, araştırma dosyası `araştırma.delta-research` (`"format": "delta-research"`), araştırma
  sayfasındaki bağlantılar `delta-src:` / `delta-note:`, tercih anahtarı `notes_dir` (kamug da okur).
- **Not uzantısı**: yeni notlar `.yazit` (`config.NOTE_EXT`); `.delta` her yerde okunur (`config.NOTE_EXTS`,
  `is_note_file`: klasör taraması, komut satırı, "open:" iletisi, tuvale sürükle-bırak). Var olan dosyanın uzantısı
  korunur (`pages.file_ext`): eski bir .delta notu yeniden adlandırılınca / taşınınca / çöpe gidince .delta kalır.
- **Klasör taşıma** (`config._migrate_dir`; hiçbir şey silinmez, üzerine yazılmaz): `%LOCALAPPDATA%\delta` →
  `yazit` config içe aktarılırken; Resimler / Videolar / Belgeler altındaki `delta` → `yazit` açılışta
  (`app.main` → `migrate_user_dirs`, ayrıca ilk `default_dir` çağrısında). Kural: eski var, yeni yoksa os.rename;
  yeni klasör boşsa önce o kaldırılır (rmdir, yalnızca boşsa); taşınamazsa o açılışta eski klasör kullanılır;
  ikisi de doluysa ikisine de dokunulmaz, eski kullanılmaya devam eder. Bir yol tercihi (notes_dir, snapshot_dir,
  video_dir, research_dir) eski klasörün içini gösteriyorsa o klasör taşınmaz. Taşınınca research_recent /
  research_last / external_notes yolları yeni klasöre çevrilir; eski yolla gelen dosya (`remap_old_path`) yeni yola.
- **kamug ile sözleşme**: kamug notu `<notes_dir>\kamug\<başlık>.yazit` olarak yazıp `yazit.exe <yol>` çalıştırır;
  notes_dir'i `%LOCALAPPDATA%\yazit\preferences.json`'dan (yoksa `…\delta\…`) okur, boşsa Resimler\delta varsa
  onu, yoksa Resimler\yazit'i kullanmalı (yazıt henüz taşımadıysa da aynı klasör; taşıyınca yol `remap_old_path` ile
  düzelir). Bağlantı `"ln": {"kamug": video, "t": sn}`; yazıt `kamug.exe video --at=sn` çalıştırır.
- **Kurulum (yükseltme)**: AppId delta ile AYNI (`{274E63FA-…}`) → Programlar'da tek kayıt, yerinde güncelleme;
  `UsePreviousAppDir=no` / `UsePreviousGroup=no` → yeni klasör `{autopf}\yazit`, Başlat'ta "yazıt". [Code]
  `InitializeSetup` eski klasörü kaldırma kaydındaki `Inno Setup: App Path`'ten okur; `PrepareToInstall` eski
  `delta.exe --quit` + taskkill; ssPostInstall'da eski klasör (içinde delta.exe varsa ve {app}'ten farklıysa)
  silinir: adı "delta" ise DelTree, değilse yalnızca kurulumun dosyaları (delta.exe, _internal, LICENSE.txt,
  unins000.*) + boşsa klasör. [InstallDelete] eski kısayolları (Başlat\delta\delta.lnk, "delta alıntı" / "delta
  snip", masaüstündekiler) siler; [Registry] eski Run "delta" değerini, `App Paths\delta.exe`'yi ve
  `HKCU\Software\Classes\Applications\delta.exe`'yi siler. Eski kurulum `Software\delta` ya da RegisteredApplications
  yazmamıştı; başka programlara ait olabilecekleri için onlara dokunulmaz.
- **ProgID'ler**: `.delta` → `delta.Note` adı BİLEREK aynı kalır (Windows'un varsayılan uygulama seçimi / UserChoice
  ProgID adına bağlı; ad değişirse Windows o dosyalarda güvenlik uyarısı / "nasıl açmak istersiniz" sorar). Yalnızca
  komutu (`yazit.exe "%1"`), simgesi ve görünen adı ("yazıt notu (eski delta)") değişir. Yeni `.yazit` → `yazit.Note`.

## Klasör yapısı
```
main.py               kaynaktan başlatıcı
yazit/
  app.py              giriş: tek örnek (QLocalServer), sistem tepsisi, kısayolları bağlar, hata günlüğü
  window.py           ana pencere (çerçevesiz, Windows Snap — kamug ile aynı nativeEvent kodu)
  canvas.py           Board (QGraphicsView): araçlar, fare/klavye, silgi, geri al komutları, render_scene,
                      hizala/diz/grupla/kilit/katman sırası, akıllı kılavuz (drawForeground), seçim çubuğu yerleşimi
  arrange.py          saf geometri: hizala, eşit dağıt, yan yana/alt alta/ızgara/çember, akıllı kılavuz payı
  selbar.py           seçim çubuğu (seçimin üstünde; Board.avoid'e binmez): bağlama göre kırp / dolgu / yazı biçimi, döndür, saydamlık
  layers.py           Katmanlar paneli (NotesPanel'de notların altında, QSplitter; prefs layers_open / layers_split):
                      küçük resim, sürükle-sırala, gizle, kilitle
  items.py            StrokeItem (kalem/fosforlu/şekiller), TextItem, ImageItem, TableItem (+CellEditor), LaserItem,
                      YazitScene, to/from_dict; içerik türleri tek yerde: `items.CONTENT`
  widthmenu.py        kalınlık kaydırıcısı (kalem / fosforlu / şekil düğmesine sağ tık, tahtanın hızlı menüsü)
  engshapes.py        mühendislik şekilleri (saf QPainterPath üretici): normal dağılım, dişli (evolvent), kayış-kasnak,
                      izometrik kutu/silindir/ızgara, kiriş, mesnet, eğik düzlem, yay, sönümleyici, 4 çubuk, termo
                      çevrimleri (P–v / T–s), piston, kompresör/türbin/pompa/ısı değ./vana, turbojet/turbofan, sınır
                      tabaka, boru akışı, silindir etrafında akış, venturi, açık tank, manometre, NACA, araçlar
  mathtex.py          küçük LaTeX dizgi motoru (matplotlib yok): ayrıştırıcı + kutu yerleşimi, Cambria Math, Unicode
                      matematik italik; layout_src / render_pixmap; yazarken hiçbir girişte hata vermez
  formula.py          formül paneli (Word'ün denklem düzenleyicisi gibi): palet sekmeleri, LaTeX satırı (\ tamamlama,
                      Tab sonraki boş {} yuva, { kendiliğinden kapanır), Enter bitir / Esc vazgeç
  brushes.py          kalem türleri (kaligrafi, keçeli, kurşun kalem, pastel, sprey, suluboya): StrokeItem.paint çağırır
  pixels.py           piksel işleri numpy'siz: benzer renk / bağlı bölge (bytes.translate + satır parçası birleşim-bul),
                      otomatik arka plan, seçimi sil (yumuşak kenar), kova, kement maskesi
  retouch.py          rötuş modu (Retouch oturumu + RetouchBar): arka plan sil, değnek, kement, piksel silgisi, geri getir
  fonts.py            yazı tipleri: alfabe yedek zinciri (`fonts.font(aile)` hep bunu kullan), assets/fonts'taki
                      gömülü yazı tipleri, kullanıcının eklediği (%LOCALAPPDATA%\yazit\fonts)
  fontpick.py         yazı tipi seçici (arama + kendi yazı tipiyle liste + "Yazı tipi ekle", menüde QWidgetAction)
  tablepick.py        tablo ekleme seçicisi (kenarlı / kenarsız + boyut ızgarası, menüde QWidgetAction)
  tools.py            ortak araç durumu (araç, renk, kalınlık) + araç tuşları (KEY varsayılan, prefs tool_keys)
  toolbar.py          yüzen araç çubuğu: alt/üst yatay, sol/sağ dikey (prefs toolbar_pos; sürükle-bırak, sağ tık);
                      WidthSlider (kalınlık kaması, karekök ölçek 0,5–30) + çizgi türü düğmesi
  pages.py            notlar: Page (sahne + QUndoStack), NoteStore (otomatik kayıt, klasörler), NotesPanel (sağ liste:
                      klasör satırları + içindeki notlar, NotesList sürükle-bırak ile klasöre taşır)
  capture.py          ekran alıntısı katmanı (ekran başına bir pencere, sahte görüntüyle test edilir; mode snip|record)
  winident.py         görev çubuğu kimliği: AppUserModel ID + pencereye ad/logo/yeniden açma komutu ("Python" yazmasın)
  ocr.py              yazı tanıma: Windows.Media.Ocr, PowerShell 5.1 + QProcess (stdin boş, iş _ACTIVE'de tutulur)
  export.py           PNG / JPEG / PDF kaydetme, tüm notlar tek PDF (QPdfWriter)
  updater.py          GitHub releases/latest denetimi (günde 1, prefs check_updates)
  pin.py              ekrana iğnelenen alıntı (PinWindow, her zaman üstte; PinManager)
  recorder.py         ekran videosu: ffmpeg gdigrab → MP4 (libx264), kırmızı çerçeve + durdur çubuğu;
                      rec_config (prefs), build_args (saf: ffmpeg komutu), Countdown (geri sayım)
  recpanel.py         kayıt paneli (ThemedDialog): sahne, kamera + köşe, mikrofon + seviye (winmm waveIn),
                      bilgisayar sesi, çözünürlük, fps, geri sayım; Seçenekler'den settings_only açılır
  loopback.py         bilgisayar sesi: WASAPI loopback (ctypes COM) → adlandırılmış boru → ffmpeg girişi
  annotate.py         ekrana çiz katmanı (saydam, her zaman üstte; "fareyi bırak" = WS_EX_TRANSPARENT)
  hotkeys.py          global kısayollar (RegisterHotKey + QAbstractNativeEventFilter, hwnd=NULL)
  dialogs.py          Seçenekler, Fare/klavye yardımı, Windows ile başlat (HKCU Run)
  research.py         araştırma modeli: Research(klasör) — tarama (alt klasörler, QFileSystemWatcher), dosyadan
                      bilgi (pypdfium2: sayfa / başlık / ISBN / ilk satırlar; docx core.xml; ffmpeg süre; döküm),
                      tür tahmini, `araştırma.delta-research` JSON (adı bilerek eski kaldı); son araştırmalar (prefs research_recent / _last)
  shelf.py            raf (QPainter): kitap sırtı / kâğıt / VHS kaset / polaroid / fiş; hover animasyonu; sitenin
                      paleti `rp()` (DARK / LIGHT); sağ tık tür / başlık / yazar; dosya bırak → klasöre kopya
  readers.py          okuyucular: PdfView (seç, Ctrl+F, vurgu, copied sinyali), ProseView (docx → HTML kendi
                      dönüştürücümüz, txt / md), ImageView, TranscriptView (video dökümü, zamanlı alıntı)
  research_view.py    ResearchView: ana ekran (Home) | QSplitter raf · sekmeler (0 = ResearchPage) · NotesColumn;
                      alıntı kartı (tek-hücreli QTextTable, künye anchorHref "delta-src:yol#p=&a=&n=" / "#t="),
                      içindekiler, bağlı notlar (anchorHref "delta-note:id") + NoteLinks üst katmanı (halka + ok)
  kamuglink.py        kamug (eski gamma) bağlantısı: notlardaki "ln" alanı, kamug.exe'yi bulma, video --at=sn
  research_export.py  Markdown / PDF / yigitozsoy.net biçiminde tek dosya HTML (raf CSS'i, kenar notu JS'i)
  theme.py icons.py widgets.py titlebar.py i18n.py config.py
  assets/             logo.png (beyaz Göktürk "y" — kalın D gibi; arayüzde renklendirilir), logo.ico, snip.ico
                      (`packaging/make_logo.py` üretir; kamug'un logo üreticisiyle aynı tarz)
```
Notlar: `Resimler\yazit\[Klasör\]Başlık.yazit` (`config.notes_root`, prefs `notes_dir`). .yazit (eski .delta) = JSON
{"format": "delta-note", "version": 2, "id", "meta", "items"}; dosya adı başlıktan (`pages.safe_name`, ":" → "."),
başlık değişince dosya yeniden adlandırılır (dışarıdan açılan dosyalar hariç: `Page.external`, prefs `external_notes`).
Klasör = tek düzey alt klasör (kimliği = adı; açık/kapalı prefs `folder_open`). Çift tık: kurulum `.yazit` / `.delta` →
`yazit.exe "%1"` kaydeder; çalışan yazıt'a "open:<yol>" iletilir (`MainWindow.open_file`).
kamug bağlantısı: kamug'un transkriptten ürettiği notlarda (`<notes_dir>\kamug\Başlık.yazit`) yazı öğesinde `"ln": {"kamug": video,
"t": sn}` (eski notlarda `"gamma"` anahtarı: önce "kamug", yoksa "gamma" okunur; yüklenince "kamug"a çevrilir)
(`TextItem.link`, `kamuglink.video_of / make_link`). Ctrl+tık ya da sağ tık "kamug'da aç" → `kamuglink.open_link` →
`kamug.exe video --at=sn` (`find_kamug`: %LOCALAPPDATA%\Programs\kamug\kamug.exe, Program Files, kaldırma kaydında
DisplayName "kamug" ile başlayan → InstallLocation\kamug.exe; yoksa aynı sırayla eski gamma.exe)
(kamug / gamma yoksa video varsayılan programla açılır). Bağlantı kopyala/yapıştırda korunur (to_dict).
`%LOCALAPPDATA%\yazit\` → `preferences.json`, `thumbs\<id>.png`, `notes_cache.json` (yol → boyut/tarih/özet:
açılışta her dosyayı okumamak için), `trash\` (silinen notlar), `error.log`, `notes\` (1.2'nin eski notları:
her not bir kez .yazit'e taşınır — `NoteStore.migrate_legacy`, prefs `migrated_ids` — silinmez).
Alıntı / PNG: Resimler\yazit. Video: Videolar\yazit (`video_dir`).

## Tasarım kararları ve tuzaklar
- **Renkler (1.3)**: COLORS = beyaz, siyah, mavi, kırmızı, yeşil, sarı, turuncu (Shift+1–7). Varsayılan kalem
  rengi temaya göre beyaz / siyah (`tools.default_color`). Eski notlardaki "auto" renk yine temaya göre çizilir.
  Kalınlıklar ince: SIZES 1,5 / 2,5 / 5 (varsayılan 2,5); yazı boyutu `text_px` = 19 + 1,75 × kalınlık.
- **Yazı tipleri (1.4)**: Qt'nin kendi yedeği Göktürk / Gotik / çivi yazısı / hiyeroglif / Linear B'yi çizemiyor (kutucuk)
  → her QFont `fonts.font()` ile `setFamilies([aile] + FALLBACK)` alır (Segoe UI Historic, YaHei, Nirmala …; Linear B
  için gömülü Noto Sans Linear B). QSS font-family de aynı zincir (`fonts.qss_families`). Yazı / tablo "ff" ailesi;
  son seçilen aile yeni yazılara geçer (prefs font_family). Değişken yazı tipleri her kalınlığı ayrı aile adıyla
  kaydeder ("Inter Thin" …): listede dosya başına tek ana aile (`fonts._main_family`), diğer adlar sistem listesinden
  çıkarılır (`_app_names`). Gömülü yazı tipleri Google Fonts / OFL (lisanslar assets/fonts/licenses). Gatwick
  (Pangram Pangram) ticari: repoya konmaz, kullanıcı "Yazı tipi ekle" ile ekler.
- **Silgi (1.4)**: state.eraser_mode "part" (varsayılan; `items.cut_stroke` yolu düzleştirip silginin değdiği
  noktaları atar, kalan parçalar yeni kalem çizgisi; şekiller de kalem çizgisine döner) | "object". Sağ tık her zaman
  nesne siler. Bir sürüklemede çıkarılan / eklenen → tek ReplaceCmd. Boyut state.eraser_size (ekran pikseli, 4–160),
  silgi seçiliyken WidthSlider ve Alt+tekerlek onu ayarlar. Görseller silgiyle silinmez → rötuş.
- **Kalem türü (1.4)**: StrokeItem.brush (yalnızca kind "pen", kayıtta "br"); brushes.paint çizer, boundingRect
  `brushes.extent` kadar büyür; ağır olanlar (kaligrafi kalıbı, sprey noktaları) `it._bc`'de. Rastgelelik ilk noktadan
  tohumlanır. Kalem / silgi düğmesi: seçili değilse seçer, seçiliyse menü (`ToolBar._menu_tool`).
- **Mühendislik şekilleri (1.4)**: prefs `eng_shapes` (Seçenekler › Davranış, varsayılan kapalı) açıkken şekil
  menüsünde (araç çubuğu + sağ tık › Şekiller) "Mühendislik" alt menüsü, içinde grup başına alt menü (`tools.add_eng_menu`).
  Yandan görünüşlü araçta tekerleğin arkasında kalan çizgiler `engshapes._hide` ile silinir (F1); durum diyagramları
  `_diagram` (eksen + yön okları + durum noktaları). Formülde harfler arası nokta çarpım: m.a → m·a (2.5 ondalık kalır). Her biri StrokeItem
  türü (kayıtta "k", ör. "gear"); yol `engshapes.build(kind, a, b, kalınlık)`. BOX türleri a–b dikdörtgenine sığar
  (Shift kare), LINE türleri (yay, sönümleyici, ölçü, yayılı yük, zemin) a→b uzanır. Dişli modülü kalınlıktan →
  aynı kalınlıkta çizilen dişliler uyuşur; araçlar en/boy oranını korur. İkonlar şeklin kendisinden çizilir
  (`icons.pixmap` "eng_<tür>" → `engshapes.paint_icon`). Ayar kapanınca seçili mühendislik aracı oka döner;
  notlardaki şekiller her durumda çizilir. Dolgu yalnızca kapalı olanlarda (`engshapes.FILLABLE`).
- **Formül (1.4)**: `items.FormulaItem` (kayıtta "t": "formula", "src", "s", "c"); Ctrl+E / araç çubuğu Σ /
  sağ tık "Formül ekle". `Board.insert_formula` öğeyi sahneye koyup paneli açar; yazdıkça `set_formula_state` ile
  öğe canlı değişir (komut yok), bitince tek AddCmd (yeni) ya da AttrCmd (düzenleme); Esc eski hâline döner, boş
  kaynak = sil. Panel açıkken tahtaya tık formülü bitirir (`mousePressEvent` başı), sayfa değişince de. Panel
  formülün altına / üstüne / yanına yerleşir, sığmazsa görünüm kaydırılır (`_place_fpanel`). Seçim çubuğundaki
  A+ / A− formül boyutunu da değiştirir. Word kolaylıkları: <= >= != -> => * (·), "3,14" ondalık virgülü boşluksuz,
  ( ) [ ] eşleşince kendiliğinden büyür. Offscreen testte sistem yazı tipi yok → QFontDatabase ile
  C:\Windows\Fonts\cambria.ttc yükle (yoksa her şey kutucuk görünür).
- **NACA profilleri (1.4)**: kanat profili şeklinin seçeneği `StrokeItem.var` (kayıtta "v"; `engshapes.NACA`,
  4 haneli + 230xx 5 haneli). Menüde kanat profili alt menüsü (`tools.fill_naca_menu`, prefs naca), sağ tıkta
  "NACA profili" ile değiştirilir (AttrCmd set_var). Profil oranı korunur (ince profil kutuya göre küçülür).
- **Bükme (1.4)**: line / arrow için `bend` (eğrinin ortasından geçtiği yerel nokta, kayıtta "bd"); quadTo kontrolü
  2·bend − orta. Seçiliyken ortada mavi tutamaç + uçlarda beyaz (`Board._bend_handles`), AttrCmd(bend_state).
- **Rötuş (1.4)**: `Board._retouch`; kırpma gibi görüntünün tamamını açar (set_crop_keep), bitince eski kırpmaya
  döner. Çalışma kopyası ARGB32 (premultiplied DEĞİL: saydam yapınca renk kaybolmasın); ekranda `set_work_image`,
  bitince PNG → AttrCmd(pixel_state). ImageItem.orig = ilk özgün PNG (geri getir fırçası, kayıtta "png0").
  Kova da görselde aynı bölge kodunu kullanır. Damlalık (`picker`) görünümden 1 piksel alır, state.prev_tool'a döner.
- **Çizgi türü (1.4)**: StrokeItem.dash solid | dash | dot | dashdot (kayıtta "ds"; `items.DASH_PATTERN`, kalınlığın katı,
  yuvarlak uç yüzünden boşluklar > 1). prefs dash; seçim varken `Board.apply_dash` seçili çizgilere uygular.
- **Yan panel** uygulama açılınca hep açık (`sidebar_visible` yalnızca oturum içinde).
- **Alıntı → yazıt** (`MainWindow.receive_image`): görsel gerçek boyutunda (1/dpr), seçili değil, görünüm
  `Board.fit_to` ile ona sığar, çizim aracı değilse kalem seçilir. Hiçbir şey seçili değilken notta tek görsel varsa
  Ctrl+C onu üstündeki çizimlerle, kendi boyutunda kopyalar.
- **Kapanışta çökme (0xC0000409)**: seçili bir şey varken çıkınca sahneler silinirken gelen selectionChanged
  yarı silinmiş Board'a ulaşıyordu → `YazitApp.quit` önce `Board.detach()` çağırır (sinyalleri bırakır).
- **Test** not klasörünü (`notes_dir`) ve alıntı klasörünü geçici klasöre alır; gerçek Resimler\yazit'e yazmaz.
  Yazı / hücre düzenleme sahnenin etkin olmasını ister: testte pencere `QApplication.setActiveWindow` ile etkinleşir.
- **Klasör listesi**: liste tıklama / düzenleme işleyicisi içinden `refresh` çağırma (öğe silinir → çökme);
  `QTimer.singleShot(0, …)` ile ertele. Sürükle-bırakta drop eylemi CopyAction yapılır ki Qt kaynak satırı silmesin.
- **z sırası**: görsel < fosforlu < diğerleri (`items.Z_BASE` + `YazitScene.zseq`). Yüklemede zseq geri hesaplanır.
- **Grup / kilit / gizli**: nesnede `group_id` / `locked` / görünürlük (`items.set_group/set_locked/set_hidden`),
  kayıtta "g" / "lk" / "hd". Öznitelik adı `group` OLAMAZ: QGraphicsItem.group() yöntemiyle çakışır (her şey "grupta" sanılır).
  Gruptan biri seçilince `Board._on_scene_selection` tamamını seçer; kilitli nesne fare almaz (lastik bant üstünden geçer).
- **Katman sırası**: "en öne" = `YazitScene.front_z()` (0 katmanında zseq) → sonra çizilen yine üstte kalır;
  bir adım / panelden sıralama mevcut z değerlerini yeniden dağıtır (görsel < fosforlu < diğerleri kuralı bozulmaz).
- **Döndür / çevir (1.3)**: `transform()` içinde, yerel merkez `gc` etrafında (öznitelikler rot / fh / fv; kayıtta
  "r" / "gc" / "fh" / "fv"). Ölçek eskisi gibi sol üst kökenli → boyutlandır / diz / kopyala kodu değişmedi.
  `items.set_geom` görsel merkezi sabit tutar; `geo_state` / `set_geo_state` birebir geri yükler (GeoCmd).
  Döndürülmüş görselin köşeden boyutlandırması `Board._resize_to` içindeki genel yoldan (karşı köşe sabit).
- **Kırp**: ImageItem.full (özgün) + crop (QRect, kayıtta "cr"); `set_crop_keep` içeriği sahnede yerinde tutar.
  Kırpma modu `Board._crop`; çizimi drawForeground'da, sayfa değişince uygulanır. Saydamlık "op", dolgu "f",
  yazı "b" / "it" / "u" / "al" (ortala / sağa yaslada metin genişliği sabitlenir: `TextItem.apply_layout`).
- **Tablo**: TableItem hücre yazılarını kendisi çizer; düzenlerken hücrenin üstüne çocuk `CellEditor` konur
  (Board.editing_text onu da sayar). Tab'ı QGraphicsScene odak zincirine kaptırmamak için `Board.event` yakalar.
  Bir düzenleme oturumu (Tab'la eklenen satır dahil) tek TableCmd (önceki / sonraki `state()`); yapı işlemleri
  `Board.table_op`. Kayıt: "cells", "cw", "nb" (kenarsız), "nh" (başlıksız). Silgi tabloya dokunmaz (görsel gibi).
- **QGraphicsItem.setBrush** `Qt.BrushStyle` almaz → `QBrush(Qt.BrushStyle.NoBrush)`.
- **Geri al**: AddCmd/RemoveCmd nesneyi sahneye *önceden* ekli/çıkarılmış alır, ilk redo atlanır.
- **Silgi** görsellere dokunmaz (alıntıyı yanlışlıkla silmesin); görsel sağ tık menüsünden / Delete ile silinir.
- **Yazı yalnızca Yazı aracıyla (1.4)**: harf / AltGr işareti / Enter / boş yere çift tık kendiliğinden yazı açmaz;
  prefs `type_to_text` (Seçenekler › Harfe basınca yazı başlasın, varsayılan kapalı) açıksa eskisi gibi
  (`Board.type_to_text`). Çift tık yazıyı / hücreyi düzenler; açıkken boş yere çift tıkta ilk tıklamanın noktası geri alınır.
- **Tablo taşıma tutamacı (1.4)**: tablonun sol üst köşesinin dışında (görünüm pikseli, `Board._grip_rect`);
  düzenlenen, tek seçili ya da farenin üstündeki tabloda görünür (`_grip_table`, `_hover_table`). Basış her şeyden
  önce yakalanır (hücre düzenlenirken de, her araçta) → "tablemove", bırakınca tek TransformCmd (grubuyla).
- **PyQt6 paintEvent'te hata = süreç çöker** (qFatal). `app._install_excepthook` bunu engeller ama testte
  excepthook yok — QPainter'a `QPoint` + float yarıçap verme (`QPointF` kullan).
- **Varsayılan kısayollar**: Win+Shift+X alıntı, Win+Shift+D ekrana çiz, Win+Shift+N hızlı not, Win+Shift+E video.
  Win+Shift+A ve Win+Shift+R bu bilgisayarda Windows tarafından alınmış (RegisterHotKey başarısız) — bu yüzden X ve E.
- **Araştırma modu (1.4)**: `MainWindow.modes` (QStackedWidget: 0 tahta, 1 `ResearchView`), Ctrl+Shift+R /
  `titlebar.btn_research`; prefs mode, research_last, research_split, research_dir (boş = Belgeler\yazit\Araştırmalar).
  Araştırma = klasör; bilgi klasördeki gizli `araştırma.delta-research` (sources = kullanıcı değişiklikleri, probe =
  mtime/boyutla önbellek, page.html, notes, highlights[yol], exports). Dışa aktarılanlar `exports`'a yazılır → rafa
  kaynak olarak girmez. Tür: ISBN ya da ≥80 sayfa / ≥30000 sözcük → kitap. PDF yılı okunmaz (CreationDate tarama tarihi).
  Tuzaklar: temanın genel QSS'i `setFont`'u ezer → araştırma yazı tipleri QSS'te (Oswald / JetBrains Mono / Caveat /
  Inter / Lora; sitenin Barlow'u woff2, Qt açamıyor). `mapTo` hedefi ata olmalı (NoteLinks ResearchView'a göre
  hesaplar). QTextDocument `availableUndoSteps` komut sayar, edit block'u değil: alıntı geri alma "son adım hâlâ
  aynı mı" diye bakar (`ResearchPage._quote_steps`). HTML'den yüklenen bağlantılar altı çizili / mavi gelir →
  `ResearchPage.normalize()`. PyQt6'da `QTextTableCell.begin()` yok: hücrenin blokları first/lastCursorPosition ile.
  Video tıklanınca: dökümü varsa döküm sekmesi (zamana tıkla → kamug), yoksa doğrudan kamug.
- **Araştırma teması (1.4)**: prefs `research_theme` (Seçenekler › Görünüm): `yazit` (varsayılan; theme.py paleti +
  vurgu, Segoe UI / Inter, gri) | `kamuflaj` (yigitozsoy.net: eski DARK/LIGHT, Oswald / JetBrains Mono / Caveat / Lora,
  "// " önekli büyük harf başlıklar) | `soft` (pastel, yuvarlak köşeler; Poppins / Manrope / Patrick Hand / Lora).
  Hepsi tek yerde: `shelf.rp()` (renk + yazı tipi rolleri f_display / f_body / f_label / f_mono / f_hand / f_quote +
  raf şekli: r_book, bands, spines …), yardımcılar `ff` (QSS ailesi), `head` / `cap` (önek / büyük harf), `spine`
  (sırt rengi temanın paletinden; elle seçilen renk korunur). Raf, sayfa, okuyucular, NoteCard, dışa aktarma
  (`site_css`: SITE_CSS'teki sabitler değişkene çevrilir; kamuflaj HTML'i bugünkü gibi hep koyu; PDF temanın açık
  paleti `rp_variant(False)`) bunu okur. Değişince `theme.changed` → `ResearchView.restyle()`: QSS, raf yerleşimi,
  sekme adları, okuyucular (`restyle`: ProseView kaynağı `set_content` ile saklar, yeniden çizer) ve sayfa
  (`normalize` başlık / metin / alıntı / künye yazı tiplerini de temaya çevirir).
- **Yazı tipi yükleme**: Qt, yolu ASCII dışı harf içeren dosyayı (`yazıt\…` klasörü) `addApplicationFont` ile
  açamayabiliyor (sessizce Segoe UI'ye düşer) → hep `fonts.add_font_file` (olmazsa dosya içeriğinden yükler).
- **Kayıt paneli (1.4)**: akış panel → (alan seçimi) → geri sayım → kayıt (`YazitApp.toggle_record`; kısayol
  sırayla: paneli aç / başlat / geri sayımı iptal / durdur). Prefs: rec_scene, rec_screen, rec_cam, rec_cam_dev,
  rec_cam_pos, rec_cam_shape (circle|square|rect), rec_cam_border (none|shadow|renk; shadow = bulanık gölge PNG + ince açık kenar), rec_cam_gray, rec_mic_on + record_mic (aygıt adı), rec_sys, rec_res, record_fps, rec_countdown.
  ffmpeg girişleri sırası: dshow (kamera + mikrofon TEK girişte → ikisi eş), bilgisayar sesi borusu, gdigrab en son
  (yavaş açılanlar önce, kaymalar küçük kalır). Kamera maskesi hazır gri PNG + alphamerge (geq gerçek zamana
  yetişmiyordu). Loopback: WAVEFORMATEX `_pack_ = 1` olmalı (yoksa float biçimi s32 sanılır); hiçbir şey çalmazken
  paket gelsin diye aynı aygıta sessizlik çalınır; kamera şekli `recorder.cam_path` tek yerde (maske, kenarlık PNG'si,
  önizleme). Kayıtta kendini gör (`recorder.SelfView`): ffmpeg kamerayı split'le ikinci çıktıya (ham RGB, stdout)
  verir, pencere videodaki kamera yerine (`cam_rect`) oturur, videoya girmez; çubuktaki kamera düğmesi aç/kapa (prefs
  rec_selfview). Önizleme (`recpanel.CamPreview`) ffmpeg'den ham RGB okur; kayıt başlamadan `_release` ile kamerayı bırakır; boruya ffmpeg bağlanınca yazılmaya başlanır. Paket QtMultimedia'yı
  dışarıda bırakır → mikrofon seviyesi winmm ile. Bu bilgisayarda Realtek mikrofonu 0,6 sn sonra veri kesiyor
  (ffmpeg takılır, video kısa kalır); HyperX çalışıyor. Geri sayım nesnesi sinyali yaydıktan SONRA silinir (çökme).
- **Video**: ffmpeg `imageio_ffmpeg` paketinden gelir; kayıt stdin'e "q" yazılarak durdurulur (dosya düzgün kapanır).
  Çerçeve ve çubuk `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` ile videoya girmez; H.264 çift boyut ister.
  Qt'de ekran kökeni yerel piksel, boyutlar ölçekli: fiziksel x = geo.x() + sel.x*dpr.
- **Klavye (1.3)**: ızgara Ctrl+R (Ctrl+G artık grupla), Ctrl+Shift+G çöz, Ctrl+L kilitle, Ctrl+PgUp/PgDown katman,
  oklar seçileni kaydırır (art arda kaydırmalar `TransformCmd.merge_key` ile tek geri al), Ctrl+Shift+K katmanlar.
- **Klavye**: araçlar rakamlarda (1 kalem … 0 seç), Shift+1–7 renk (sanal tuş kodu, Türkçe düzenden bağımsız),
  harfle yazı yalnızca `type_to_text` açıkken (`Board.keyPressEvent` → `new_text`). Eski harf kısayolları
  (F, G, I, [ ]) Home / Ctrl+G / Ctrl+I / Ctrl+↑↓ oldu.
- **Not adı kutusu** kilitli (`titlebar.NoteTitle`): tek tıkla sürükleme pencereyi taşır, çift tık / F2 düzenler.
- Bash aracında heredoc içindeki `\` karakterleri bozulabiliyor: ters eğik çizgili düzenlemeleri Edit / Write
  ile ya da betiği dosyaya yazıp çalıştırarak yap.
- Test **gerçek tercihlere dokunmaz** (LOCALAPPDATA geçici klasör) ve kısayolları boşaltır; ekranı yakalamaz.
