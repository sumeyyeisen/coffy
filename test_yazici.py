import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageChops

import etiket
import yazici
from yazici import YaziciAyar, YaziciHatasi, esc_pos_coz, esc_pos_uret
from skt import etiket_verisi, urunleri_yukle


def ornek_etiket():
    u = {x.ad: x for x in urunleri_yukle()}["Karamel Sos"]
    return etiket.etiket_ciz(etiket_verisi(u, acilis=datetime(2026, 11, 12, 14, 30)))


class EscPosTest(unittest.TestCase):
    def test_bitmap_gidis_donus_ayni(self):
        """Etiket -> ESC/POS -> geri çözülen resim, kafaya ortalanmış özgün etiketle birebir aynı olmalı."""
        img = ornek_etiket()
        ayar = YaziciAyar(kafa_nokta=464)       # kırpma yok: birebir aynı çıkmalı
        geri = esc_pos_coz(esc_pos_uret(img, ayar))
        fark = ImageChops.difference(geri.convert("L"), img.convert("L")).getbbox()
        self.assertIsNone(fark)

    def test_kafa_384_icinde_kenar_bosluklari_kirpilir(self):
        """464 nokta etiket 384 kafaya ortalanır; 5 mm'lik beyaz kenarlar kırpılır, içerik kaybolmaz."""
        img = ornek_etiket()
        veri = esc_pos_uret(img, YaziciAyar(kafa_nokta=384))
        geri = esc_pos_coz(veri)
        self.assertEqual(geri.width, 384)
        self.assertEqual(geri.height, img.height)
        merkez = img.crop((40, 0, 424, img.height)).convert("L")
        self.assertIsNone(ImageChops.difference(geri.convert("L"), merkez).getbbox())

    def test_ofset_konumu(self):
        img = Image.new("1", (16, 8), 1)
        img.paste(0, (0, 0, 8, 8))   # sol yarı siyah
        geri = esc_pos_coz(esc_pos_uret(img, YaziciAyar(kafa_nokta=32, sol_ofset_nokta=8)))
        self.assertEqual(geri.width, 32)
        self.assertEqual(geri.convert("L").getpixel((8, 0)), 0)
        self.assertEqual(geri.convert("L").getpixel((0, 0)), 255)

    def test_komutlar_ve_kesim(self):
        img = ornek_etiket()
        tam = esc_pos_uret(img, YaziciAyar(kesim="tam", kesim_oncesi_besleme=40))
        self.assertTrue(tam.startswith(b"\x1b@\x1dv0\x00"))
        self.assertTrue(tam.endswith(b"\x1bJ\x28\x1dV\x00"))
        self.assertTrue(esc_pos_uret(img, YaziciAyar(kesim="kismi")).endswith(b"\x1dV\x01"))
        yok = esc_pos_uret(img, YaziciAyar(kesim="yok"))
        self.assertNotIn(b"\x1dV", yok[-10:])

    def test_bantlar_tum_satirlari_kapsar(self):
        img = ornek_etiket()   # 687 satır -> 256 + 256 + 175
        veri = esc_pos_uret(img, YaziciAyar(kafa_nokta=464, kesim="yok"))
        self.assertEqual(veri.count(b"\x1dv0\x00"), 3)
        self.assertEqual(esc_pos_coz(veri).height, 687)

    def test_beyaz_etiket_bos_cikmaz_siyah_resim_dolu_cikar(self):
        beyaz = esc_pos_uret(Image.new("1", (464, 10), 1), YaziciAyar(kafa_nokta=464, kesim="yok"))
        self.assertEqual(set(beyaz[10:]), {0})          # hiç nokta yok
        siyah = esc_pos_uret(Image.new("1", (464, 10), 0), YaziciAyar(kafa_nokta=464, kesim="yok"))
        self.assertEqual(set(siyah[10:]), {255})        # tüm noktalar dolu


class AyarTest(unittest.TestCase):
    def test_dosya_yoksa_varsayilanla_olusur(self):
        with tempfile.TemporaryDirectory() as t:
            yol = Path(t) / "yazici.json"
            a = yazici.ayar_oku(yol)
            self.assertEqual(a, YaziciAyar())
            self.assertTrue(yol.is_file())
            self.assertEqual(yazici.ayar_oku(yol), a)

    def test_gecersiz_ayarlar_anlasilir_hata_verir(self):
        with tempfile.TemporaryDirectory() as t:
            yol = Path(t) / "yazici.json"
            for icerik in ('{"kesim": "belki"}', '{"kafa_nokta": 5}', '{"yok_boyle": 1}', "{bozuk"):
                yol.write_text(icerik, encoding="utf-8")
                with self.assertRaises(YaziciHatasi, msg=icerik):
                    yazici.ayar_oku(yol)

    def test_ayar_degerleri_okunur(self):
        with tempfile.TemporaryDirectory() as t:
            yol = Path(t) / "yazici.json"
            yol.write_text(json.dumps({"kesim": "yok", "kafa_nokta": 576, "yazici_adi": "BIXOLON SRP-S300"}))
            a = yazici.ayar_oku(yol)
            self.assertEqual((a.kesim, a.kafa_nokta, a.yazici_adi), ("yok", 576, "BIXOLON SRP-S300"))

    def test_pywin32_yoksa_anlasilir_hata(self):
        try:
            import win32print  # noqa: F401
            self.skipTest("pywin32 yüklü")
        except ImportError:
            with self.assertRaises(YaziciHatasi):
                yazici.yazicilari_listele()


if __name__ == "__main__":
    unittest.main()