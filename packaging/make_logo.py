"""yazıt logosu: Göktürk "y" harfi (kalın bir "D" gibi: solda dikey gövde, düz üst ve alt kollar, sağda yarım daire;
her yerde aynı kalınlıkta çizgi, tırnaksız). kamug'un logo üreticisiyle (kamug\\packaging\\make_logo.py) aynı tarz.

Üretir (Pillow gerekir):
  yazit/assets/logo.png — beyaz harf, saydam (arayüzde tema rengine boyanır); eski logoyla aynı 262×306 tuval
  yazit/assets/logo.ico — açık gri yuvarlak kare üstünde koyu harf, 16–256 px
  yazit/assets/snip.ico — aynı zemin, köşe işaretli seçim çerçevesi içinde küçük harf ("yazıt alıntı" kısayolu)
Logo değişirse bir kez çalıştırılır:
    python packaging/make_logo.py
"""
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "yazit", "assets")
SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]

# Harf, yükseklik = 1 birim. Gövde + düz kollar STRAIGHT kadar, sonra sağda yarım daire (yatay yarıçap RX;
# 0,5 tam daire olurdu, biraz dar tutuldu). İç boşluk her yandan T içeride → çizgi her yerde aynı kalınlıkta.
T = 0.17                        # çizgi kalınlığı (kamug'un "k"sı 0,135; D'nin iç boşluğu büyük, biraz kalın)
STRAIGHT = 0.27                 # yarım dairenin merkezi (sol kenardan); T'den küçük olamaz
RX = 0.39                       # yarım dairenin yatay yarıçapı (dikeyde 0,5)
W = STRAIGHT + RX               # harf genişliği
INK = (24, 24, 24, 255)         # simgede harf rengi (kamug ile aynı)


def glyph_mask(h, ss=1):
    """Harfin alfa maskesi: genişlik W·h, yükseklik h (piksel, ss kat büyük çizilir sonra küçültülür)."""
    H = round(h * ss)
    Wp = round(W * h * ss)
    m = Image.new("L", (Wp + 2 * ss, H), 0)
    d = ImageDraw.Draw(m)
    cx, rx, t = STRAIGHT * H, RX * H, T * H
    # dış biçim: dikdörtgen (gövde + düz kollar) + sağda yarım daire
    d.rectangle([0, 0, cx, H - 1], fill=255)
    d.pieslice([cx - rx, 0, cx + rx, H - 1], -90, 90, fill=255)
    # iç boşluk: aynı biçim, her yandan t içeride
    if cx > t:
        d.rectangle([t, t, cx, H - 1 - t], fill=0)
    d.pieslice([cx - (rx - t), t, cx + (rx - t), H - 1 - t], -90, 90, fill=0)
    m = m.crop((0, 0, Wp, H))
    if ss > 1:
        m = m.resize((max(1, round(Wp / ss)), max(1, round(H / ss))), Image.LANCZOS)
    return m


def paste_glyph(img, x, y, h, color, ss=1):
    m = glyph_mask(h, ss)
    img.paste(Image.new("RGBA", m.size, color), (round(x), round(y)), m)


def make_png(path):
    w, h = 262, 306                              # eski Δ logosuyla aynı tuval (yerleşim değişmesin)
    gh = h - 60
    img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    paste_glyph(img, (w - W * gh) / 2, 30, gh, (255, 255, 255, 255), ss=8)
    img.save(path)


SNIP_BOX = (40 / 256, 216 / 256)   # seçim çerçevesi (köşe işaretleri)
SNIP_ARM = 50 / 256
SNIP_W = 16 / 256
SNIP_GLYPH_H = 0.40


def tile(size, snip=False, ss=8):
    n = size * ss
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    grad = Image.new("RGBA", (n, n))
    gd = ImageDraw.Draw(grad)
    for yy in range(n):                          # üstten alta açık griden biraz koyuya
        v = int(236 - (236 - 191) * yy / max(1, n - 1))
        gd.line([(0, yy), (n, yy)], fill=(v, v, v, 255))
    mask = Image.new("L", (n, n), 0)
    r = int(n * 0.19)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, n - 1, n - 1], r, fill=255)
    img.paste(grad, (0, 0), mask)
    ImageDraw.Draw(img).rounded_rectangle([ss // 2, ss // 2, n - 1 - ss // 2, n - 1 - ss // 2], r,
                                          outline=(150, 150, 150, 255), width=max(1, ss // 2))
    if snip:   # ekran alıntısı: dört köşede L işaretleri
        a, b = SNIP_BOX[0] * n, SNIP_BOX[1] * n
        arm, w = SNIP_ARM * n, max(1.2 * ss, SNIP_W * n)
        d = ImageDraw.Draw(img)
        for x, sx in ((a, 1), (b, -1)):
            for y, sy in ((a, 1), (b, -1)):
                d.rectangle([min(x, x + sx * arm), min(y, y + sy * w), max(x, x + sx * arm), max(y, y + sy * w)],
                            fill=INK)
                d.rectangle([min(x, x + sx * w), min(y, y + sy * arm), max(x, x + sx * w), max(y, y + sy * arm)],
                            fill=INK)
        gh = n * SNIP_GLYPH_H
    else:
        gh = n * (0.60 if size > 24 else 0.68)
    paste_glyph(img, (n - W * gh) / 2, (n - gh) / 2, gh, INK)
    return img.resize((size, size), Image.LANCZOS)


def make_ico(path, snip=False):
    imgs = [tile(s, snip) for s in SIZES]
    imgs[-1].save(path, sizes=[(s, s) for s in SIZES], append_images=imgs[:-1])


if __name__ == "__main__":
    make_png(os.path.join(ASSETS, "logo.png"))
    make_ico(os.path.join(ASSETS, "logo.ico"))
    make_ico(os.path.join(ASSETS, "snip.ico"), snip=True)
    print("logo.png + logo.ico + snip.ico üretildi")
