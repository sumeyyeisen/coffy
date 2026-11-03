import unittest
from datetime import datetime
from io import BytesIO

from PIL import Image

import etiket
from skt import etiket_verisi, urunleri_yukle

AYAR = etiket.AYAR
SOL = AYAR.dot(AYAR.kenar_mm)
UST = AYAR.dot(AYAR.ust_alt_mm)
W, H = AYAR.genislik_dot, AYAR.uzunluk_dot


def veri(ad="Karamel Sos", uyari="", saklama="Ortam Sıcaklığı",
         acilis=datetime(2026, 11, 12, 14, 30), skt=datetime(2026, 12, 12, 14, 30)):
    return {"ad": ad, "acilis": acilis, "skt": skt, "saklama": saklama, "uyari": uyari}


class EtiketTest(unittest.TestCase):
    def test_olcu_58x86_mm_203dpi(self):
        self.assertEqual((W, H), (464, 687))
        img = etiket.etiket_ciz(veri())
        self.assertEqual(img.size, (W, H))
        self.assertEqual(img.mode, "1")  # saf siyah-beyaz, gri ton yok

    def test_tum_urunler_kenar_boslugunu_asmaz(self):
        """75 ürünün hepsi için: siyah piksel hiçbir zaman kenar boşluğuna taşmamalı."""
        for u in urunleri_yukle():
            v = etiket_verisi(u, acilis=datetime(2026, 12, 31, 23, 59))
            kutu = etiket.siyah_alan(etiket.etiket_ciz(v))
            self.assertIsNotNone(kutu, u.ad)
            sol, ust, sag, alt = kutu
            self.assertGreaterEqual(sol, SOL, u.ad)
            self.assertLessEqual(sag, W - SOL, u.ad)
            self.assertGreaterEqual(ust, UST, u.ad)
            self.assertLessEqual(alt, H - UST, u.ad)

    def test_asiri_uzun_metinler_de_sigar(self):
        v = veri(ad="Çok Uzun Bir Ürün Adı " * 6, uyari="Pişirildikten sonra açıldıktan sonra tüketilmelidir " * 3)
        sol, ust, sag, alt = etiket.siyah_alan(etiket.etiket_ciz(v))
        self.assertTrue(sol >= SOL and sag <= W - SOL and ust >= UST and alt <= H - UST)

    def test_tek_uzun_kelime_tasmaz(self):
        v = veri(ad="Süperuzunbirkelimeuzunuzunuzunuzunuzunuzunuzunuzun")
        sol, ust, sag, alt = etiket.siyah_alan(etiket.etiket_ciz(v))
        self.assertTrue(sol >= SOL and sag <= W - SOL)

    def test_turkce_harfler_cizilir_ve_birbirinden_farkli(self):
        def harf(c):
            img = Image.new("L", (80, 80), 255)
            from PIL import ImageDraw
            ImageDraw.Draw(img).text((10, 5), c, font=etiket._font(True, 48), fill=0)
            return img.tobytes()
        for a, b in (("ı", "i"), ("ğ", "g"), ("ş", "s"), ("ç", "c"), ("ö", "o"), ("ü", "u"),
                     ("İ", "I"), ("Ğ", "G"), ("Ş", "S"), ("Ç", "C"), ("Ö", "O"), ("Ü", "U")):
            self.assertNotEqual(harf(a), harf(b), f"{a} ile {b} aynı çizildi (font eksik olabilir)")
            self.assertNotEqual(harf(a), harf("\uFFFF"), f"{a} çizilemedi")

    def test_tr_buyuk_metin(self):
        self.assertEqual(etiket.tr_buyuk_metin("Ortam Sıcaklığı"), "ORTAM SICAKLIĞI")
        self.assertEqual(etiket.tr_buyuk_metin("+4 Dolap"), "+4 DOLAP")
        self.assertEqual(etiket.tr_buyuk_metin("Pişirildikten sonra"), "PİŞİRİLDİKTEN SONRA")

    def test_ayni_girdi_ayni_resim(self):
        self.assertEqual(etiket.etiket_ciz(veri()).tobytes(), etiket.etiket_ciz(veri()).tobytes())

    def test_icerik_degisince_resim_degisir(self):
        temel = etiket.etiket_ciz(veri()).tobytes()
        self.assertNotEqual(temel, etiket.etiket_ciz(veri(skt=datetime(2026, 12, 13, 14, 30))).tobytes())
        self.assertNotEqual(temel, etiket.etiket_ciz(veri(uyari="Pişirildikten sonra")).tobytes())
        self.assertNotEqual(temel, etiket.etiket_ciz(veri(saklama="+4 Dolap")).tobytes())
        self.assertNotEqual(temel, etiket.etiket_ciz(veri(ad="Mango Sos")).tobytes())

    def test_uyari_yoksa_siyah_kutu_yok(self):
        uyarisiz = etiket.siyah_alan(etiket.etiket_ciz(veri()))
        uyarili = etiket.siyah_alan(etiket.etiket_ciz(veri(uyari="Pişirildikten sonra")))
        self.assertGreater(uyarili[3], uyarisiz[3])  # uyarı etiketi aşağı doğru uzatır

    def test_png_bytes_ve_olcek(self):
        img = etiket.etiket_ciz(veri())
        tam = etiket.png_bytes(img)
        self.assertTrue(tam.startswith(b"\x89PNG"))
        yari = Image.open(BytesIO(etiket.png_bytes(img, 0.5)))
        self.assertEqual(yari.size, (232, 344))

    def test_ayar_degisince_olcu_degisir(self):
        k = etiket.EtiketAyar(genislik_mm=80, uzunluk_mm=60)
        img = etiket.etiket_ciz(veri(), k)
        self.assertEqual(img.size, (k.genislik_dot, k.uzunluk_dot))


ACIK = etiket.EtiketAyar(acilis_goster=True)
KAPALI = etiket.EtiketAyar(acilis_goster=False)


def _gruplar(indeksler):
    """Ardışık satır numaralarını (ilk, son) gruplarına ayırır."""
    gruplar = []
    for i in indeksler:
        if gruplar and i == gruplar[-1][1] + 1:
            gruplar[-1][1] = i
        else:
            gruplar.append([i, i])
    return gruplar


class SktVeAcilisTest(unittest.TestCase):
    def test_skt_tarih_ve_saat_ayni_buyuklukte(self):
        """SKT kutusunun içindeki iki satırın (tarih, saat) rakam yüksekliği aynı olmalı."""
        px = etiket.etiket_ciz(veri()).convert("L").load()
        x0, x1 = SOL + 8, W - SOL - 8
        siyah = [sum(1 for x in range(x0, x1) if px[x, y] < 128) for y in range(H)]
        uzun = _gruplar([y for y in range(H) if siyah[y] >= 0.9 * (x1 - x0)])
        kutu_ust, kutu_alt = uzun[-2][1], uzun[-1][0]      # kutunun üst ve alt kenarı
        bantlar = _gruplar([y for y in range(kutu_ust + 1, kutu_alt) if siyah[y] > 0])
        self.assertEqual(len(bantlar), 3, bantlar)           # "SKT" yazısı, tarih, saat
        _, tarih, saat = bantlar
        yuk_tarih, yuk_saat = tarih[1] - tarih[0] + 1, saat[1] - saat[0] + 1
        self.assertGreaterEqual(yuk_tarih, 40)
        self.assertLessEqual(abs(yuk_tarih - yuk_saat), 2, (yuk_tarih, yuk_saat))

    def test_acilis_varsayilan_olarak_basilir(self):
        self.assertTrue(etiket.AYAR.acilis_goster)
        a = etiket.etiket_ciz(veri())
        b = etiket.etiket_ciz(veri(acilis=datetime(2026, 11, 10, 8, 0)))
        self.assertNotEqual(a.tobytes(), b.tobytes())        # açılış etikette görünüyor

    def test_acilis_kapatilinca_basilmaz(self):
        a = etiket.etiket_ciz(veri(), KAPALI)
        b = etiket.etiket_ciz(veri(acilis=datetime(2026, 11, 10, 8, 0)), KAPALI)
        self.assertEqual(a.tobytes(), b.tobytes())

    def test_acilis_satiri_etiketi_asagi_uzatir(self):
        acik = etiket.siyah_alan(etiket.etiket_ciz(veri(), ACIK))
        kapali = etiket.siyah_alan(etiket.etiket_ciz(veri(), KAPALI))
        self.assertGreater(acik[3], kapali[3])

    def test_acilis_acikken_de_tum_urunler_sigar(self):
        for u in urunleri_yukle():
            v = etiket_verisi(u, acilis=datetime(2026, 12, 31, 23, 59))
            sol, ust, sag, alt = etiket.siyah_alan(etiket.etiket_ciz(v, ACIK))
            self.assertTrue(sol >= SOL and sag <= W - SOL and ust >= UST and alt <= H - UST, u.ad)


if __name__ == "__main__":
    unittest.main()