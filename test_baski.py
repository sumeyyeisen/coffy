"""Kasada yazıcı ayarını doğrulamak için test baskısı.

Kullanım:
  python test_baski.py --yazicilar            Windows'taki yazıcı adlarını listeler
  python test_baski.py                        cetvelli test etiketini basar (yazici.json ayarlarıyla)
  python test_baski.py --kesim yok|tam|kismi  kesim modunu geçici olarak değiştirir
  python test_baski.py --kafa 576             kafa genişliğini geçici olarak değiştirir (80 mm yazıcı: 576)
  python test_baski.py --ofset 0              etiketin sol konumunu geçici olarak değiştirir (nokta)
  python test_baski.py --png test.png         basmadan, resmi dosyaya kaydeder

Basılı kâğıtta ölçülecekler (sonucu bana yaz):
  1) Dış çerçevenin sol ve sağ çizgisi görünüyor mu? Kaç mm kesiliyor?
  2) Üstteki cetvelde 0-58 cm'lik ölçek gerçek mm ile uyuşuyor mu? (203 dpi doğrulaması)
  3) Etiketin toplam uzunluğu cetvelle 86 mm mi?
  4) Kesim, etiketin hangi noktasında oldu (çerçevenin altına göre)?
"""
import argparse
import sys
from dataclasses import replace

from PIL import Image, ImageDraw

import etiket
import yazici

A = etiket.AYAR


def test_resmi(ayar: etiket.EtiketAyar = A) -> Image.Image:
    W, H = ayar.genislik_dot, ayar.uzunluk_dot
    mm = ayar.dpi / 25.4
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    f = etiket._font(True, 18)
    k = etiket._font(False, 15)

    # 1 mm'lik cetvel çizgileri: üstte ve solda (5 mm'de bir uzun, 10 mm'de bir sayılı)
    for i in range(0, int(ayar.genislik_mm) + 1):
        x = round(i * mm)
        uz = 30 if i % 10 == 0 else 20 if i % 5 == 0 else 10
        d.line([(x, 0), (x, uz)], fill=0, width=2)
        if i % 10 == 0 and 0 < i < ayar.genislik_mm:
            d.text((x + 4, 30), str(i // 10), font=f, fill=0)
    for i in range(0, int(ayar.uzunluk_mm) + 1):
        y = round(i * mm)
        uz = 30 if i % 10 == 0 else 20 if i % 5 == 0 else 10
        d.line([(0, y), (uz, y)], fill=0, width=2)
        if i % 10 == 0 and i > 0:
            d.text((34, y - 9), f"{i // 10}cm", font=k, fill=0)

    # 1 cm'lik noktalı ızgara
    for i in range(1, int(ayar.genislik_mm // 10) + 1):
        x = round(i * 10 * mm)
        for y in range(40, H - 40, 12):
            d.point((x, y), fill=0)
    for i in range(1, int(ayar.uzunluk_mm // 10) + 1):
        y = round(i * 10 * mm)
        for x in range(60, W - 6, 12):
            d.point((x, y), fill=0)

    # Dış çerçeve: kesilen/basılmayan kenarları gösterir
    d.rectangle([0, 0, W - 1, H - 1], outline=0, width=3)
    # Etiket kenar boşluğunun sınırı (kesikli): gerçek içerik bu çizgilerin içinde kalır
    sol = ayar.dot(ayar.kenar_mm)
    ust = ayar.dot(ayar.ust_alt_mm)
    for y in range(ust, H - ust, 16):
        d.line([(sol, y), (sol, y + 8)], fill=0, width=2)
        d.line([(W - sol, y), (W - sol, y + 8)], fill=0, width=2)
    for x in range(sol, W - sol, 16):
        d.line([(x, ust), (x + 8, ust)], fill=0, width=2)
        d.line([(x, H - ust), (x + 8, H - ust)], fill=0, width=2)

    # Ortada ölçü bilgisi ve örnek yazı (Türkçe karakter + okunabilirlik)
    g = etiket._font(True, 26)
    orta = [f"TEST {ayar.genislik_mm:g} x {ayar.uzunluk_mm:g} mm", f"{ayar.dpi} dpi  {W} x {H} nokta",
            "ĞÜŞİÖÇ  ğüşıöç", "Kenar boşluğu: %g mm" % ayar.kenar_mm]
    y = H // 2 - 60
    for s in orta:
        y = etiket._ortala(d, s, g, y, sol, W - 2 * sol)
    # Alt kenar oku: kesimin nereye denk geldiğini bulmak için
    y = etiket._ortala(d, "ALT (86 mm)", g, H - ust - 50, sol, W - 2 * sol)
    return img.point(lambda p: 255 if p >= 160 else 0).convert("1")


def main():
    p = argparse.ArgumentParser(description="Coffy SKT yazıcı test baskısı")
    p.add_argument("--yazicilar", action="store_true")
    p.add_argument("--kesim", choices=["tam", "kismi", "yok"])
    p.add_argument("--kafa", type=int)
    p.add_argument("--ofset", type=int)
    p.add_argument("--besleme", type=int, help="kesimden önce ilerletme (nokta)")
    p.add_argument("--png")
    a = p.parse_args()
    try:
        if a.yazicilar:
            for ad in yazici.yazicilari_listele():
                print(ad)
            return 0
        img = test_resmi()
        if a.png:
            img.save(a.png)
            print(f"{a.png} yazıldı")
            return 0
        ayar = yazici.ayar_oku()
        if a.kesim:
            ayar = replace(ayar, kesim=a.kesim)
        if a.kafa:
            ayar = replace(ayar, kafa_nokta=a.kafa)
        if a.ofset is not None:
            ayar = replace(ayar, sol_ofset_nokta=a.ofset)
        if a.besleme is not None:
            ayar = replace(ayar, kesim_oncesi_besleme=a.besleme)
        print(f"Ayar: {ayar}")
        yazici.resim_yazdir(img, ayar)
        print("Gönderildi.")
        return 0
    except yazici.YaziciHatasi as e:
        print(f"HATA: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())