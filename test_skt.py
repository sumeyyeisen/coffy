import unittest
from datetime import datetime
from skt import urunleri_yukle, skt_hesapla, etiket_verisi

U = {u.ad: u for u in urunleri_yukle()}


class SktTest(unittest.TestCase):
    def test_karamel_sos_1_ay_30_gun(self):
        # 12 Kasım + 30 gün = 12 Aralık
        s = skt_hesapla(U["Karamel Sos"], datetime(2026, 11, 12, 14, 30))
        self.assertEqual(s, datetime(2026, 12, 12, 14, 30))

    def test_saat_bazli_ay_sonu_gecisi(self):
        s = skt_hesapla(U["Tereyağlı Kruvasan"], datetime(2026, 10, 31, 21, 15))
        self.assertEqual(s, datetime(2026, 11, 1, 21, 15))

    def test_matcha_sut_24_saat(self):
        s = skt_hesapla(U["Matcha / Süt Karışımı"], datetime(2026, 11, 12, 21, 0))
        self.assertEqual(s, datetime(2026, 11, 13, 21, 0))

    def test_2_ay_60_gun(self):
        s = skt_hesapla(U["Hindistan Cevizi Yağı"], datetime(2026, 11, 1, 9, 0))
        self.assertEqual(s, datetime(2026, 12, 31, 9, 0))

    def test_saniye_atilir(self):
        s = skt_hesapla(U["Ekmek"], datetime(2026, 11, 1, 9, 0, 45))
        self.assertEqual(s.second, 0)

    def test_manuel_gecmis_acilis(self):
        v = etiket_verisi(U["Karamel Sos"], acilis=datetime(2026, 11, 10, 8, 0))
        self.assertEqual(v["skt"], datetime(2026, 12, 10, 8, 0))
        self.assertTrue(v["manuel"])

    def test_manuel_skt(self):
        v = etiket_verisi(U["Ekmek"], acilis=datetime(2026, 11, 1, 9, 0),
                          skt=datetime(2026, 11, 3, 9, 0))
        self.assertEqual(v["skt"], datetime(2026, 11, 3, 9, 0))

    def test_gecersiz_skt(self):
        with self.assertRaises(ValueError):
            etiket_verisi(U["Ekmek"], acilis=datetime(2026, 11, 5, 9, 0),
                          skt=datetime(2026, 11, 4, 9, 0))

    def test_otomatik_manuel_degil(self):
        self.assertFalse(etiket_verisi(U["Ekmek"])["manuel"])

    def test_pisirildikten_sonra_uyarisi(self):
        self.assertEqual(U["Rustik Baget Esmer"].uyari, "Pişirildikten sonra")

    def test_urun_sayisi_ve_kategoriler(self):
        self.assertEqual(len(U), 75)
        self.assertEqual(len({u.kategori for u in U.values()}), 8)

    def test_skt_only_urunler_yok(self):
        for ad in ["Cheddar Peyniri", "Yoğurt Sos", "Sprey Krema", "Bal", "Çay"]:
            self.assertNotIn(ad, U)


if __name__ == "__main__":
    unittest.main(verbosity=2)
