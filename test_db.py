import unittest
from datetime import datetime
import db
from skt import urunleri_yukle, etiket_verisi


class DbTest(unittest.TestCase):
    def test_kaydet_ve_oku(self):
        conn = db.baglan(":memory:")
        u = next(x for x in urunleri_yukle() if x.ad == "Karamel Sos")
        v = etiket_verisi(u, acilis=datetime(2026, 11, 12, 14, 30))
        db.kaydet(conn, v)
        k = db.son_kayitlar(conn)
        self.assertEqual(len(k), 1)
        self.assertEqual(k[0]["ad"], "Karamel Sos")
        self.assertEqual(k[0]["skt"], datetime(2026, 12, 12, 14, 30))
        self.assertTrue(k[0]["manuel"])

    def test_siralama_en_yeni_ustte(self):
        conn = db.baglan(":memory:")
        urunler = urunleri_yukle()[:3]
        for u in urunler:
            db.kaydet(conn, etiket_verisi(u))
        self.assertEqual(db.son_kayitlar(conn)[0]["ad"], urunler[2].ad)


if __name__ == "__main__":
    unittest.main()


class YonetimTest(unittest.TestCase):
    def setUp(self):
        self.conn = db.baglan(":memory:")

    def test_ilk_kurulumda_75_urun_8_kategori(self):
        self.assertEqual(len(db.urunleri_getir(self.conn)), 75)
        self.assertEqual(len(db.kategoriler_getir(self.conn)), 8)

    def test_ikinci_baglantida_tekrar_yuklenmez(self):
        db._ilk_kurulum(self.conn)
        self.assertEqual(len(db.urunleri_getir(self.conn, sadece_aktif=False)), 75)

    def test_urun_ekle_ve_skt(self):
        from skt import skt_hesapla
        kid = db.kategoriler_getir(self.conn)[0][0]
        uid = db.urun_ekle(self.conn, "Test Sos", kid, 10, "gun", "dolap")
        u = next(x for x in db.urunleri_getir(self.conn) if x.id == uid)
        self.assertEqual(skt_hesapla(u, datetime(2026, 1, 1, 10, 0)), datetime(2026, 1, 11, 10, 0))

    def test_ayni_isim_reddedilir(self):
        kid = db.kategoriler_getir(self.conn)[0][0]
        with self.assertRaises(db.YonetimHatasi):
            db.urun_ekle(self.conn, "Karamel Sos", kid, 1, "ay", "ortam")

    def test_gecersiz_sure_reddedilir(self):
        kid = db.kategoriler_getir(self.conn)[0][0]
        for sure in (0, -3):
            with self.assertRaises(db.YonetimHatasi):
                db.urun_ekle(self.conn, "X", kid, sure, "gun", "dolap")
        with self.assertRaises(db.YonetimHatasi):
            db.urun_ekle(self.conn, "X", kid, 3, "hafta", "dolap")

    def test_pasif_urun_gizlenir_ama_silinmez(self):
        u = db.urunleri_getir(self.conn)[0]
        db.urun_aktif_yap(self.conn, u.id, False)
        self.assertEqual(len(db.urunleri_getir(self.conn)), 74)
        self.assertEqual(len(db.urunleri_getir(self.conn, sadece_aktif=False)), 75)
        db.urun_aktif_yap(self.conn, u.id, True)
        self.assertEqual(len(db.urunleri_getir(self.conn)), 75)

    def test_guncelleme_ve_degisiklik_gecmisi(self):
        u = next(x for x in db.urunleri_getir(self.conn) if x.ad == "Karamel Sos")
        kid = db.kategoriler_getir(self.conn)[0][0]
        kat_id = next(i for i, a in db.kategoriler_getir(self.conn) if a == u.kategori)
        db.urun_guncelle(self.conn, u.id, u.ad, kat_id, 20, "gun", u.saklama, u.uyari)
        gecmis = db.degisiklik_gecmisi(self.conn)
        self.assertEqual(gecmis[0]["alan"], "birim")
        self.assertTrue(any(g["alan"] == "süre" and g["eski"] == "1" and g["yeni"] == "20" for g in gecmis))

    def test_kategori_ekle(self):
        db.kategori_ekle(self.conn, "Yeni Kategori")
        self.assertEqual(len(db.kategoriler_getir(self.conn)), 9)
        with self.assertRaises(db.YonetimHatasi):
            db.kategori_ekle(self.conn, "Yeni Kategori")

    def test_pin(self):
        self.assertTrue(db.pin_dogru(self.conn, "1234"))
        self.assertTrue(db.pin_varsayilan_mi(self.conn))
        db.pin_degistir(self.conn, "8642")
        self.assertTrue(db.pin_dogru(self.conn, "8642"))
        self.assertFalse(db.pin_dogru(self.conn, "1234"))
        self.assertFalse(db.pin_varsayilan_mi(self.conn))

    def test_zayif_pin_reddedilir(self):
        for kotu in ("12", "abcd", "1234", "123456789"):
            with self.assertRaises(db.YonetimHatasi):
                db.pin_degistir(self.conn, kotu)

    def test_yedek(self):
        import tempfile, os
        with tempfile.TemporaryDirectory() as d:
            yol = os.path.join(d, "yedek.db")
            db.yedek_al(self.conn, yol)
            self.assertTrue(os.path.getsize(yol) > 0)


class SilmeTest(unittest.TestCase):
    def setUp(self):
        self.conn = db.baglan(":memory:")
        self.u = db.urunleri_getir(self.conn)[0]

    def test_sil_gizler_geri_getir_acar(self):
        db.urun_sil(self.conn, self.u.id)
        self.assertEqual(len(db.urunleri_getir(self.conn)), 74)
        self.assertEqual(len(db.urunleri_getir(self.conn, sadece_aktif=False)), 74)
        self.assertEqual([x.id for x in db.silinen_urunler(self.conn)], [self.u.id])
        db.urun_geri_getir(self.conn, self.u.id)
        self.assertEqual(len(db.urunleri_getir(self.conn)), 75)
        self.assertEqual(db.silinen_urunler(self.conn), [])

    def test_pasif_urun_silinip_geri_gelince_pasif_kalir(self):
        db.urun_aktif_yap(self.conn, self.u.id, False)
        db.urun_sil(self.conn, self.u.id)
        db.urun_geri_getir(self.conn, self.u.id)
        self.assertEqual(len(db.urunleri_getir(self.conn)), 74)
        self.assertEqual(len(db.urunleri_getir(self.conn, sadece_aktif=False)), 75)

    def test_kalici_sil_sadece_silinenlere(self):
        with self.assertRaises(db.YonetimHatasi):
            db.urun_kalici_sil(self.conn, self.u.id)
        db.urun_sil(self.conn, self.u.id)
        db.urun_kalici_sil(self.conn, self.u.id)
        self.assertEqual(db.silinen_urunler(self.conn), [])
        self.assertEqual(len(db.urunleri_getir(self.conn, sadece_aktif=False)), 74)

    def test_silinen_isimle_ekleme_yonlendirir(self):
        db.urun_sil(self.conn, self.u.id)
        kid = db.kategoriler_getir(self.conn)[0][0]
        with self.assertRaises(db.YonetimHatasi) as h:
            db.urun_ekle(self.conn, self.u.ad, kid, 1, "gun", "dolap")
        self.assertIn("Silinenler", str(h.exception))

    def test_silme_gecmise_yazilir(self):
        db.urun_sil(self.conn, self.u.id)
        db.urun_geri_getir(self.conn, self.u.id)
        yeniler = [g["yeni"] for g in db.degisiklik_gecmisi(self.conn)]
        self.assertEqual(yeniler[:2], ["geri getirildi", "silindi"])

    def test_etiket_kaydi_urun_silinince_korunur(self):
        from skt import etiket_verisi
        db.kaydet(self.conn, etiket_verisi(self.u))
        db.urun_sil(self.conn, self.u.id)
        db.urun_kalici_sil(self.conn, self.u.id)
        self.assertEqual(db.son_kayitlar(self.conn)[0]["ad"], self.u.ad)

    def test_eski_veritabani_tasinir(self):
        import tempfile, os, sqlite3
        with tempfile.TemporaryDirectory() as d:
            yol = os.path.join(d, "eski.db")
            c = sqlite3.connect(yol)
            c.executescript("""
                CREATE TABLE kategori (id INTEGER PRIMARY KEY AUTOINCREMENT, ad TEXT NOT NULL UNIQUE);
                CREATE TABLE urun (id INTEGER PRIMARY KEY AUTOINCREMENT, ad TEXT NOT NULL UNIQUE,
                    kategori_id INTEGER NOT NULL, sure_deger INTEGER NOT NULL, sure_birim TEXT NOT NULL,
                    saklama TEXT NOT NULL, uyari TEXT NOT NULL DEFAULT '', aktif INTEGER NOT NULL DEFAULT 1);
                INSERT INTO kategori (ad) VALUES ('Soslar');
                INSERT INTO urun (ad, kategori_id, sure_deger, sure_birim, saklama) VALUES ('Eski Sos', 1, 1, 'ay', 'ortam');
            """)
            c.commit(); c.close()
            conn = db.baglan(yol)
            self.assertEqual([u.ad for u in db.urunleri_getir(conn)], ["Eski Sos"])
            db.urun_sil(conn, 1)
            self.assertEqual(db.urunleri_getir(conn), [])


class KurtarmaTest(unittest.TestCase):
    def setUp(self):
        self.conn = db.baglan(":memory:")

    def test_kod_yokken_dogrulama_basarisiz(self):
        self.assertFalse(db.kurtarma_kodu_dogru(self.conn, "12345678"))

    def test_pin_degistirince_kod_doner(self):
        kod = db.pin_degistir(self.conn, "8642")
        self.assertEqual(len(kod), 8)
        self.assertTrue(kod.isdigit())
        self.assertTrue(db.kurtarma_kodu_dogru(self.conn, kod))

    def test_kodla_sifirlama(self):
        kod = db.pin_degistir(self.conn, "8642")
        yeni_kod = db.pin_kurtarma_ile_sifirla(self.conn, kod, "9753")
        self.assertTrue(db.pin_dogru(self.conn, "9753"))
        self.assertFalse(db.pin_dogru(self.conn, "8642"))
        self.assertFalse(db.kurtarma_kodu_dogru(self.conn, kod))  # eski kod geçersiz
        self.assertTrue(db.kurtarma_kodu_dogru(self.conn, yeni_kod))

    def test_yanlis_kod_reddedilir(self):
        db.pin_degistir(self.conn, "8642")
        with self.assertRaises(db.YonetimHatasi):
            db.pin_kurtarma_ile_sifirla(self.conn, "00000000", "9753")
        self.assertTrue(db.pin_dogru(self.conn, "8642"))

    def test_kurtarma_kodu_yenile(self):
        eski = db.pin_degistir(self.conn, "8642")
        yeni = db.kurtarma_kodu_uret(self.conn)
        self.assertFalse(db.kurtarma_kodu_dogru(self.conn, eski))
        self.assertTrue(db.kurtarma_kodu_dogru(self.conn, yeni))

    def test_acil_sifirlama_veriye_dokunmaz(self):
        db.pin_degistir(self.conn, "8642")
        u = db.urunleri_getir(self.conn)[0]
        db.urun_sil(self.conn, u.id)
        db.pin_sifirla_varsayilan(self.conn)
        self.assertTrue(db.pin_dogru(self.conn, "1234"))
        self.assertTrue(db.pin_varsayilan_mi(self.conn))
        self.assertEqual(len(db.silinen_urunler(self.conn)), 1)
        self.assertFalse(db.kurtarma_kodu_dogru(self.conn, "12345678"))


class AyniPinTest(unittest.TestCase):
    def setUp(self):
        self.conn = db.baglan(":memory:")

    def test_mevcut_pin_ile_ayni_pin_reddedilir(self):
        kod = db.pin_degistir(self.conn, "8642")
        with self.assertRaises(db.YonetimHatasi) as h:
            db.pin_degistir(self.conn, "8642")
        self.assertIn("aynı", str(h.exception))
        # reddedilince hiçbir şey değişmemeli: PIN aynı, kurtarma kodu hâlâ geçerli
        self.assertTrue(db.pin_dogru(self.conn, "8642"))
        self.assertTrue(db.kurtarma_kodu_dogru(self.conn, kod))

    def test_farkli_pin_kabul_edilir(self):
        db.pin_degistir(self.conn, "8642")
        db.pin_degistir(self.conn, "9753")
        self.assertTrue(db.pin_dogru(self.conn, "9753"))

    def test_unutma_akisinda_ayni_pin_kabul_edilir(self):
        kod = db.pin_degistir(self.conn, "8642")
        yeni_kod = db.pin_kurtarma_ile_sifirla(self.conn, kod, "8642")
        self.assertTrue(db.pin_dogru(self.conn, "8642"))
        self.assertTrue(db.kurtarma_kodu_dogru(self.conn, yeni_kod))


class YedekTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        self.tmp = tempfile.TemporaryDirectory()
        self.klasor = Path(self.tmp.name)
        self.conn = db.baglan(":memory:")

    def tearDown(self):
        self.tmp.cleanup()

    def test_otomatik_yedek_gunde_bir_kez(self):
        from datetime import date
        a = db.otomatik_yedek(self.conn, self.klasor, bugun=date(2026, 11, 1))
        self.assertTrue(a.exists())
        self.assertIsNone(db.otomatik_yedek(self.conn, self.klasor, bugun=date(2026, 11, 1)))
        self.assertEqual(db.yedek_incele(a)["urun"], 75)

    def test_son_7_yedek_kalir(self):
        from datetime import date
        for gun in range(1, 11):
            db.otomatik_yedek(self.conn, self.klasor, bugun=date(2026, 11, gun))
        kalan = sorted(p.name for p in self.klasor.glob("otomatik_*.db"))
        self.assertEqual(len(kalan), 7)
        self.assertEqual(kalan[0], "otomatik_20261104.db")
        self.assertEqual(kalan[-1], "otomatik_20261110.db")
        self.assertEqual(list(self.klasor.glob("*.tmp")), [])

    def test_gecersiz_dosyalar_reddedilir(self):
        import sqlite3
        metin = self.klasor / "metin.db"
        metin.write_text("bu bir veritabanı değil")
        baska = self.klasor / "baska.db"
        c = sqlite3.connect(baska); c.execute("CREATE TABLE x (a)"); c.commit(); c.close()
        for yol in (metin, baska, self.klasor / "yok.db"):
            with self.assertRaises(db.YonetimHatasi):
                db.yedek_incele(yol)

    def test_geri_yukleme_veriyi_dondurur_pin_degismez(self):
        kid = db.kategoriler_getir(self.conn)[0][0]
        db.urun_ekle(self.conn, "Yedekteki Ürün", kid, 3, "gun", "dolap")
        db.pin_degistir(self.conn, "1357")
        yedek = self.klasor / "yedek.db"
        db.yedek_al(self.conn, yedek)

        # yedekten sonra: ürün ekle, bir ürünü sil, PIN değiştir
        db.urun_ekle(self.conn, "Sonradan Eklenen", kid, 1, "gun", "dolap")
        db.urun_sil(self.conn, db.urunleri_getir(self.conn)[0].id)
        db.pin_degistir(self.conn, "8642")

        onceki = db.yedekten_geri_yukle(self.conn, yedek, self.klasor / "oncesi")
        adlar = {u.ad for u in db.urunleri_getir(self.conn, sadece_aktif=False)}
        self.assertIn("Yedekteki Ürün", adlar)
        self.assertNotIn("Sonradan Eklenen", adlar)
        self.assertEqual(db.silinen_urunler(self.conn), [])
        # PIN geri yüklemeden etkilenmez
        self.assertTrue(db.pin_dogru(self.conn, "8642"))
        self.assertFalse(db.pin_dogru(self.conn, "1357"))
        # geri yükleme öncesi durum ayrıca yedeklendi ve içinde "Sonradan Eklenen" var
        self.assertTrue(onceki.exists())
        import sqlite3
        c = sqlite3.connect(onceki)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM urun WHERE ad='Sonradan Eklenen'").fetchone()[0], 1)
        c.close()
        # işlem geçmişe yazıldı
        self.assertEqual(db.degisiklik_ara(self.conn, tur="Yedek işlemleri")[0][0]["eski"], "-")

    def test_eski_surum_yedegi_geri_yuklenir(self):
        import sqlite3
        eski = self.klasor / "eski.db"
        c = sqlite3.connect(eski)
        c.executescript("""
            CREATE TABLE kategori (id INTEGER PRIMARY KEY AUTOINCREMENT, ad TEXT NOT NULL UNIQUE);
            CREATE TABLE urun (id INTEGER PRIMARY KEY AUTOINCREMENT, ad TEXT NOT NULL UNIQUE,
                kategori_id INTEGER NOT NULL, sure_deger INTEGER NOT NULL, sure_birim TEXT NOT NULL,
                saklama TEXT NOT NULL, uyari TEXT NOT NULL DEFAULT '', aktif INTEGER NOT NULL DEFAULT 1);
            CREATE TABLE etiket_kaydi (id INTEGER PRIMARY KEY AUTOINCREMENT, urun_ad TEXT NOT NULL,
                acilis TEXT NOT NULL, skt TEXT NOT NULL, saklama TEXT NOT NULL,
                uyari TEXT NOT NULL DEFAULT '', manuel INTEGER NOT NULL DEFAULT 0, basim_zamani TEXT NOT NULL);
            INSERT INTO kategori (ad) VALUES ('Soslar');
            INSERT INTO urun (ad, kategori_id, sure_deger, sure_birim, saklama) VALUES ('Eski Sos', 1, 1, 'ay', 'ortam');
        """)
        c.commit(); c.close()
        db.yedekten_geri_yukle(self.conn, eski, self.klasor / "oncesi")
        self.assertEqual([u.ad for u in db.urunleri_getir(self.conn)], ["Eski Sos"])
        self.assertTrue(db.pin_dogru(self.conn, "1234"))  # PIN ayarları korunmuş
        db.urun_sil(self.conn, db.urunleri_getir(self.conn)[0].id)  # yeni şema çalışıyor


class GecmisAramaTest(unittest.TestCase):
    def setUp(self):
        self.conn = db.baglan(":memory:")
        self.kid = db.kategoriler_getir(self.conn)[0][0]
        for ad in ("İpek Çay Şurubu", "Karamel Sos X", "Isparta Gülü"):
            db.urun_ekle(self.conn, ad, self.kid, 5, "gun", "dolap")
        u = next(x for x in db.urunleri_getir(self.conn) if x.ad == "Karamel Sos X")
        db.urun_guncelle(self.conn, u.id, u.ad, self.kid, 9, "gun", "dolap", "")   # süre değişti
        db.urun_sil(self.conn, u.id)
        # tarihleri kontrollü hale getir
        self.conn.execute("UPDATE degisiklik SET zaman='2026-09-01 10:00' WHERE urun_ad='İpek Çay Şurubu'")
        self.conn.commit()

    def test_katla(self):
        self.assertEqual(db.katla("İPEK Çay Şurubu"), db.katla("ipek cay surubu"))
        self.assertEqual(db.katla("Isparta"), db.katla("ısparta"))

    def test_turkce_duyarsiz_arama(self):
        for sorgu in ("ipek", "İPEK", "cay surubu", "şurubu"):
            satirlar, _ = db.degisiklik_ara(self.conn, sorgu)
            self.assertEqual({r["urun_ad"] for r in satirlar}, {"İpek Çay Şurubu"}, sorgu)

    def test_tur_filtreleri(self):
        sure, _ = db.degisiklik_ara(self.conn, tur="Süre değişiklikleri")
        self.assertEqual([(r["urun_ad"], r["alan"]) for r in sure], [("Karamel Sos X", "süre")])
        silme, _ = db.degisiklik_ara(self.conn, tur="Silme / geri getirme")
        self.assertEqual([r["yeni"] for r in silme], ["silindi"])
        ekleme, _ = db.degisiklik_ara(self.conn, tur="Ürün ekleme")
        self.assertEqual(len(ekleme), 3)
        tumu, _ = db.degisiklik_ara(self.conn)
        self.assertEqual(len(tumu), 3 + 1 + 1)

    def test_tarih_araligi(self):
        from datetime import date
        eylul, _ = db.degisiklik_ara(self.conn, baslangic=date(2026, 9, 1), bitis=date(2026, 9, 1))
        self.assertEqual({r["urun_ad"] for r in eylul}, {"İpek Çay Şurubu"})
        bugunden_sonra, _ = db.degisiklik_ara(self.conn, baslangic=date(2026, 9, 2))
        self.assertNotIn("İpek Çay Şurubu", {r["urun_ad"] for r in bugunden_sonra})
        self.assertEqual(db.degisiklik_ara(self.conn, baslangic=date(2099, 1, 1))[0], [])

    def test_filtreler_birlikte_ve_limit(self):
        satirlar, daha = db.degisiklik_ara(self.conn, "karamel", tur="Silme / geri getirme")
        self.assertEqual(len(satirlar), 1)
        satirlar, daha = db.degisiklik_ara(self.conn, limit=2)
        self.assertEqual(len(satirlar), 2)
        self.assertTrue(daha)
        self.assertFalse(db.degisiklik_ara(self.conn, limit=50)[1])


class SaklamaTest(unittest.TestCase):
    BUGUN = datetime(2026, 11, 1, 12, 0)

    def setUp(self):
        self.conn = db.baglan(":memory:")

    def _kayit(self, gun_once, ad="Karamel Sos"):
        z = (self.BUGUN - __import__("datetime").timedelta(days=gun_once)).strftime(db.FMT)
        self.conn.execute(
            "INSERT INTO etiket_kaydi (urun_ad, acilis, skt, saklama, uyari, manuel, basim_zamani) "
            "VALUES (?, ?, ?, 'Ortam Sıcaklığı', '', 0, ?)", (ad, z, z, z))
        self.conn.commit()

    def test_varsayilan_12_ay(self):
        self.assertEqual(db.etiket_saklama_ay(self.conn), 12)

    def test_ayarla_ve_sinirlar(self):
        db.etiket_saklama_ayarla(self.conn, 18)
        self.assertEqual(db.etiket_saklama_ay(self.conn), 18)
        for kotu in (6, 0, -1, 121, "12"):
            with self.assertRaises(db.YonetimHatasi):
                db.etiket_saklama_ayarla(self.conn, kotu)
        self.assertEqual(db.etiket_saklama_ay(self.conn), 18)

    def test_sadece_suresi_dolanlar_silinir(self):
        self._kayit(400, "Eski"); self._kayit(361, "Eski2"); self._kayit(359, "Yeni"); self._kayit(10, "Yeni2")
        self.assertEqual(db.silinecek_etiket_sayisi(self.conn, bugun=self.BUGUN), 2)   # önizleme, silmez
        self.assertEqual(len(db.son_kayitlar(self.conn, 100)), 4)
        self.assertEqual(db.eski_etiketleri_temizle(self.conn, self.BUGUN), 2)
        self.assertEqual({k["ad"] for k in db.son_kayitlar(self.conn, 100)}, {"Yeni", "Yeni2"})
        self.assertEqual(db.eski_etiketleri_temizle(self.conn, self.BUGUN), 0)          # tekrar çalışınca bir şey olmaz

    def test_temizlik_degisiklik_gecmisine_dokunmaz_ve_kaydedilir(self):
        kid = db.kategoriler_getir(self.conn)[0][0]
        db.urun_ekle(self.conn, "Gecmisli Urun", kid, 1, "gun", "dolap")
        onceki = len(db.degisiklik_ara(self.conn)[0])
        self._kayit(500)
        db.eski_etiketleri_temizle(self.conn, self.BUGUN)
        satirlar, _ = db.degisiklik_ara(self.conn, tur="Kayıt temizliği / saklama süresi")
        self.assertEqual(len(satirlar), 1)
        self.assertIn("1 etiket kaydı silindi", satirlar[0]["yeni"])
        self.assertEqual(len(db.degisiklik_ara(self.conn)[0]), onceki + 1)               # eski geçmiş duruyor

    def test_sure_uzayinca_silinecek_azalir(self):
        self._kayit(400)
        db.etiket_saklama_ayarla(self.conn, 18)
        self.assertEqual(db.eski_etiketleri_temizle(self.conn, self.BUGUN), 0)

    def test_geri_yuklemede_saklama_ayari_korunur(self):
        import tempfile, os
        db.etiket_saklama_ayarla(self.conn, 9)
        with tempfile.TemporaryDirectory() as d:
            yedek = os.path.join(d, "y.db")
            db.yedek_al(self.conn, yedek)
            db.etiket_saklama_ayarla(self.conn, 24)
            db.yedekten_geri_yukle(self.conn, yedek, os.path.join(d, "once"))
        self.assertEqual(db.etiket_saklama_ay(self.conn), 24)