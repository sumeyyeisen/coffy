"""Etiket görseli: ürün etiketini siyah-beyaz (1 bit) resim olarak çizer.

Yazıcıdan bağımsızdır: aynı resim hem ekran önizlemesinde hem (adım 8'de) yazıcıda kullanılır.
Yazıyı resim olarak çizdiğimiz için Türkçe karakter sorunu yaşanmaz.

Ölçüler (cetvelle ölçülen): rulo 58 mm genişlik, etiket 86 mm uzunluk, 203 dpi (8 nokta/mm).
Yazıcı kafası kâğıttan dar olabildiği için sağ/sol kenarda `kenar_mm` boşluk bırakılır;
gerçek yazıcıda test baskısından sonra AYAR içinden ayarlanır.
"""
from dataclasses import dataclass
from functools import lru_cache
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

FONT_KLASORLERI = [Path(__file__).with_name("fontlar"), Path(__file__).with_name("files")]
FONT_ADAYLARI = {
    True: ["DejaVuSansCondensed-Bold.ttf"],
    False: ["DejaVuSansCondensed.ttf"],
}
SISTEM_FONTLARI = {  # bundled font bulunamazsa son çare
    True: [r"C:\Windows\Fonts\arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf"],
    False: [r"C:\Windows\Fonts\arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf"],
}


@dataclass(frozen=True)
class EtiketAyar:
    genislik_mm: float = 58.0
    uzunluk_mm: float = 86.0
    dpi: int = 203
    kenar_mm: float = 5.0     # sağ/sol boşluk -> baskı alanı 48 mm (58 mm'lik yazıcıların tipik kafa genişliği)
    ust_alt_mm: float = 3.0   # üst/alt boşluk
    acilis_goster: bool = True    # False yapılırsa etikette "AÇILIŞ" tarihi basılmaz (kayıtta her zaman tutulur)

    def dot(self, mm: float) -> int:
        return round(mm * self.dpi / 25.4)

    @property
    def genislik_dot(self) -> int:
        return self.dot(self.genislik_mm)

    @property
    def uzunluk_dot(self) -> int:
        return self.dot(self.uzunluk_mm)


AYAR = EtiketAyar()


def tr_buyuk_metin(metin: str) -> str:
    """Türkçe büyük harf: 'dolap'->'DOLAP', 'pişirildikten'->'PİŞİRİLDİKTEN', 'sıcaklığı'->'SICAKLIĞI'."""
    return metin.replace("i", "İ").replace("ı", "I").upper()


@lru_cache(maxsize=None)
def _font(kalin: bool, boyut: int) -> ImageFont.FreeTypeFont:
    adaylar = [k / a for k in FONT_KLASORLERI for a in FONT_ADAYLARI[kalin]] + [Path(p) for p in SISTEM_FONTLARI[kalin]]
    for yol in adaylar:
        if yol.is_file():
            return ImageFont.truetype(str(yol), boyut)
    raise FileNotFoundError(
        "Türkçe karakterleri destekleyen yazı tipi bulunamadı. 'fontlar' klasörüne "
        "DejaVuSansCondensed.ttf ve DejaVuSansCondensed-Bold.ttf koyun.")


def _genislik(d, metin, font) -> float:
    return d.textlength(metin, font=font)


def _yukseklik(font) -> int:
    asc, desc = font.getmetrics()
    return asc + desc


def _sigdir(d, metin, kalin, max_genislik, en_buyuk, en_kucuk=14):
    """Metin max_genislik'e sığana kadar yazıyı küçültür."""
    for boyut in range(en_buyuk, en_kucuk - 1, -1):
        f = _font(kalin, boyut)
        if _genislik(d, metin, f) <= max_genislik:
            return f
    return _font(kalin, en_kucuk)


def _kirp(d, metin, font, max_genislik) -> str:
    if _genislik(d, metin, font) <= max_genislik:
        return metin
    while metin and _genislik(d, metin + "…", font) > max_genislik:
        metin = metin[:-1]
    return metin.rstrip() + "…"


def _satirlara_bol(d, metin, font, max_genislik) -> list[str]:
    satirlar, mevcut = [], ""
    for kelime in metin.split():
        deneme = (mevcut + " " + kelime).strip()
        if _genislik(d, deneme, font) <= max_genislik:
            mevcut = deneme
        else:
            if mevcut:
                satirlar.append(mevcut)
            mevcut = kelime
    if mevcut:
        satirlar.append(mevcut)
    return satirlar


def _ortala(d, metin, font, y, sol, genis, fill=0) -> int:
    x = sol + (genis - _genislik(d, metin, font)) / 2
    d.text((x, y), metin, font=font, fill=fill)
    return y + _yukseklik(font)


def _sigan_satirlar(d, metin, kalin, genis, en_buyuk, en_kucuk, en_cok_satir):
    """(font, satırlar): en çok `en_cok_satir` satıra sığan en büyük yazı boyutu."""
    for boyut in range(en_buyuk, en_kucuk - 1, -1):
        f = _font(kalin, boyut)
        satirlar = _satirlara_bol(d, metin, f, genis)
        if len(satirlar) <= en_cok_satir and all(_genislik(d, s, f) <= genis for s in satirlar):
            return f, satirlar
    f = _font(kalin, en_kucuk)   # son çare: sığmayanı kırp
    satirlar = [_kirp(d, s, f, genis) for s in _satirlara_bol(d, metin, f, genis)[:en_cok_satir]]
    return f, satirlar


def _ciz(veri: dict, ayar: EtiketAyar, ad_en_buyuk: int):
    W, H = ayar.genislik_dot, ayar.uzunluk_dot
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    sol = ayar.dot(ayar.kenar_mm)
    genis = W - 2 * sol
    y = ayar.dot(ayar.ust_alt_mm)

    # 1) Ürün adı (en çok 3 satır, sığmazsa küçülür)
    f, satirlar = _sigan_satirlar(d, veri["ad"], True, genis, ad_en_buyuk, 20, 3)
    for s in satirlar:
        y = _ortala(d, s, f, y, sol, genis)
    y += 12
    d.line([(sol, y), (sol + genis - 1, y)], fill=0, width=3)
    y += 16

    # 2) Açılış (isteğe bağlı: AYAR.acilis_goster)
    if ayar.acilis_goster:
        y_et = _font(False, 26)
        d.text((sol, y), "AÇILIŞ", font=y_et, fill=0)
        y += _yukseklik(y_et)
        acilis = veri["acilis"]
        fa = _sigdir(d, f"{acilis:%d.%m.%Y}  {acilis:%H:%M}", True, genis, 42)
        d.text((sol, y), f"{acilis:%d.%m.%Y}  {acilis:%H:%M}", font=fa, fill=0)
        y += _yukseklik(fa) + 22

    # 3) SKT: en belirgin kısım, çerçeveli kutu
    skt = veri["skt"]
    pad = 12
    kutu_ust = y
    ic_genis = genis - 2 * pad
    y += pad
    f_et = _font(True, 32)
    d.text((sol + pad, y), "SKT", font=f_et, fill=0)
    y += _yukseklik(f_et)
    # Tarih ve saat AYNI boyutta: göz sadece saate değil, tarihin tamamına gitsin
    f_skt = _sigdir(d, f"{skt:%d.%m.%Y}", True, ic_genis, 80, 24)
    y = _ortala(d, f"{skt:%d.%m.%Y}", f_skt, y, sol, genis)
    y = _ortala(d, f"{skt:%H:%M}", f_skt, y, sol, genis)
    y += pad
    d.rectangle([sol, kutu_ust, sol + genis - 1, y], outline=0, width=4)
    y += 22

    # 4) Saklama koşulu
    saklama = tr_buyuk_metin(veri["saklama"])
    fs = _sigdir(d, saklama, True, genis, 42, 16)
    y = _ortala(d, saklama, fs, y, sol, genis)
    y += 18

    # 5) Uyarı notu (varsa): siyah zemin üstüne beyaz yazı
    if veri.get("uyari"):
        uyari = tr_buyuk_metin(veri["uyari"])
        for boyut in range(36, 23, -1):          # önce tek satıra sığdırmayı dene (en az 24 punto)
            fu = _font(True, boyut)
            if _genislik(d, uyari, fu) <= genis - 16:
                satirlar = [uyari]
                break
        else:                                     # sığmadıysa en çok 2 satıra böl
            fu, satirlar = _sigan_satirlar(d, uyari, True, genis - 16, 36, 16, 2)
        yuk = sum(_yukseklik(fu) for _ in satirlar) + 14
        d.rectangle([sol, y, sol + genis - 1, y + yuk], fill=0)
        yy = y + 7
        for s in satirlar:
            yy = _ortala(d, s, fu, yy, sol, genis, fill=255)
        y += yuk + 4
    return img, y


def etiket_ciz(veri: dict, ayar: EtiketAyar = AYAR) -> Image.Image:
    """Etiketi çizer ve 1 bitlik (siyah/beyaz) resim döndürür. Taşma olursa yazıyı küçülterek tekrar dener."""
    alt_sinir = ayar.uzunluk_dot - ayar.dot(ayar.ust_alt_mm)
    for ad_en_buyuk in (52, 46, 40, 34, 28, 22):
        img, y = _ciz(veri, ayar, ad_en_buyuk)
        if y <= alt_sinir:
            break
    # Termal yazıcı için net siyah-beyaz (gri ton/ditering yok)
    return img.point(lambda p: 255 if p >= 160 else 0).convert("1")


def png_bytes(img: Image.Image, olcek: float = 1.0) -> bytes:
    g = img.convert("L")
    if olcek != 1.0:
        g = g.resize((round(g.width * olcek), round(g.height * olcek)), Image.LANCZOS)
    b = BytesIO()
    g.save(b, "PNG")
    return b.getvalue()


def siyah_alan(img: Image.Image):
    """Siyah piksellerin sınırlayıcı kutusu (sol, üst, sağ, alt) ya da None. Testler için."""
    return ImageChops.invert(img.convert("L")).getbbox()


if __name__ == "__main__":
    # Örnek etiketleri tek bir PNG'ye çizer: python3 etiket.py
    from datetime import datetime
    from skt import etiket_verisi, urunleri_yukle

    urunler = {u.ad: u for u in urunleri_yukle()}
    secim = ["Karamel Sos", "Hindi Fümeli ve Kuru Domatesli Rustik Baget",
             "Rustik Baget Esmer", "Matcha / Süt Karışımı"]
    resimler = [etiket_ciz(etiket_verisi(urunler[a], acilis=datetime(2026, 11, 12, 14, 30))) for a in secim]
    bosluk = 30
    W = sum(r.width for r in resimler) + bosluk * (len(resimler) + 1)
    H = resimler[0].height + 2 * bosluk
    tuval = Image.new("L", (W, H), 200)
    x = bosluk
    for r in resimler:
        tuval.paste(r.convert("L"), (x, bosluk))
        x += r.width + bosluk
    tuval.save("ornek_etiketler.png")
    print("ornek_etiketler.png yazıldı")