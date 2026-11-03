"""Yönetim ekranları (PIN korumalı): ürün ekle/düzenle, pasife al, kategori, PIN, yedek."""
import time
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime, timedelta

import db
from klavye import dokunmatik, klavye_iste

BIRIM_ETIKET = {"saat": "Saat", "gun": "Gün", "ay": "Ay"}
SAKLAMA_ETIKET = {"dolap": "+4 Dolap", "ortam": "Ortam Sıcaklığı"}
BIRIM_TERS = {v: k for k, v in BIRIM_ETIKET.items()}
SAKLAMA_TERS = {v: k for k, v in SAKLAMA_ETIKET.items()}
ZAMAN_ASIMI_SN = 180      # Yönetim ekranı bu kadar süre dokunulmazsa kapanır
KONTROL_ARALIGI_MS = 5000
GECMIS_LIMIT = 500
UNUTTUM = "unuttum"  # pin_iste bunu döndürürse kullanıcı "PIN'imi unuttum"a bastı


class PinDialog(tk.Toplevel):
    """Dokunmatik rakam tuş takımı. Tamam'a basılınca self.sonuc dolar, iptalde None kalır."""

    def __init__(self, ana, baslik, unuttum=False):
        super().__init__(ana)
        self.title("PIN")
        self.transient(ana)
        self.resizable(False, False)
        self.sonuc, self.deger = None, ""
        self.gosterge = tk.StringVar(value="")

        tk.Label(self, text=baslik, font=("", 16, "bold")).pack(pady=(16, 6))
        tk.Label(self, textvariable=self.gosterge, font=("", 28), width=10,
                 relief="sunken").pack(pady=6, padx=20)
        izgara = tk.Frame(self)
        izgara.pack(padx=20, pady=10)
        for i, t in enumerate(["1", "2", "3", "4", "5", "6", "7", "8", "9", "Sil", "0", "Tamam"]):
            tk.Button(izgara, text=t, font=("", 18, "bold"), width=5, height=2,
                      command=lambda x=t: self._bas(x)).grid(row=i // 3, column=i % 3, padx=3, pady=3)
        alt = tk.Frame(self)
        alt.pack(pady=(0, 14))
        tk.Button(alt, text="İptal", font=("", 13), width=10, command=self.destroy
                  ).pack(side="left", padx=4)
        if unuttum:
            tk.Button(alt, text="PIN'imi unuttum", font=("", 13), command=self._unuttum
                      ).pack(side="left", padx=4)
        self.grab_set()
        self.wait_window(self)

    def _unuttum(self):
        self.sonuc = UNUTTUM
        self.destroy()

    def _bas(self, t):
        if t == "Sil":
            self.deger = self.deger[:-1]
        elif t == "Tamam":
            if self.deger:
                self.sonuc = self.deger
                self.destroy()
            return
        elif len(self.deger) < 8:
            self.deger += t
        self.gosterge.set("•" * len(self.deger))


def pin_iste(ana, baslik, unuttum=False):
    return PinDialog(ana, baslik, unuttum).sonuc


def kurtarma_kodu_goster(ana, kod):
    messagebox.showinfo(
        "Kurtarma kodunuz",
        f"Kurtarma kodunuz:\n\n{kod}\n\n"
        "Bunu hemen güvenli bir yere yazın. Bir daha gösterilmez.\n"
        "PIN'i unutursanız bu kodla sıfırlayabilirsiniz.", parent=ana)


def pin_kurtarma_akisi(ana, conn):
    """'PIN'imi unuttum': kurtarma kodu doğruysa yeni PIN belirletir."""
    kod = pin_iste(ana, "Kurtarma kodu (8 rakam)")
    if kod is None:
        return
    if not db.kurtarma_kodu_dogru(conn, kod):
        messagebox.showerror(
            "Hatalı kod", "Kurtarma kodu yanlış ya da hiç oluşturulmamış.\n\n"
            "Kodu bulamıyorsanız programı kuran kişiyle iletişime geçin.", parent=ana)
        return
    yeni = pin_iste(ana, "Yeni PIN (4-8 rakam)")
    if yeni is None:
        return
    if pin_iste(ana, "Yeni PIN (tekrar)") != yeni:
        messagebox.showerror("Hata", "İki PIN aynı değil.", parent=ana)
        return
    try:
        yeni_kod = db.pin_kurtarma_ile_sifirla(conn, kod, yeni)
    except db.YonetimHatasi as e:
        messagebox.showerror("Hata", str(e), parent=ana)
        return
    messagebox.showinfo("Tamam", "PIN değiştirildi.", parent=ana)
    kurtarma_kodu_goster(ana, yeni_kod)


class UrunFormu(tk.Toplevel):
    def __init__(self, ana, conn, urun=None):
        super().__init__(ana)
        self.conn, self.urun, self.kaydedildi = conn, urun, False
        self.title("Ürün Düzenle" if urun else "Yeni Ürün")
        self.transient(ana)
        self.resizable(False, False)

        kategoriler = db.kategoriler_getir(conn)
        self.kat_id = {ad: kid for kid, ad in kategoriler}
        self.ad_var = tk.StringVar(value=urun.ad if urun else "")
        self.kat_var = tk.StringVar(value=urun.kategori if urun else kategoriler[0][1])
        self.sure_var = tk.StringVar(value=str(urun.sure_deger) if urun else "1")
        self.birim_var = tk.StringVar(value=BIRIM_ETIKET[urun.sure_birim] if urun else "Gün")
        self.sak_var = tk.StringVar(value=SAKLAMA_ETIKET[urun.saklama] if urun else "+4 Dolap")
        self.uyari_var = tk.StringVar(value=urun.uyari if urun else "")

        k = ttk.Frame(self, padding=20)
        k.pack()
        f = ("", 14)
        ad_e = tk.Entry(k, textvariable=self.ad_var, font=f, width=34)
        dokunmatik(ad_e, self.ad_var, "Ürün adı", "metin")
        satirlar = [
            ("Ürün adı", ad_e),
            ("Kategori", ttk.Combobox(k, textvariable=self.kat_var, font=f, width=32,
                                      state="readonly", values=[a for _, a in kategoriler])),
        ]
        for i, (et, w) in enumerate(satirlar):
            tk.Label(k, text=et, font=f).grid(row=i, column=0, sticky="e", padx=6, pady=6)
            w.grid(row=i, column=1, columnspan=2, sticky="w")

        tk.Label(k, text="Raf ömrü", font=f).grid(row=2, column=0, sticky="e", padx=6, pady=6)
        sure_e = tk.Entry(k, textvariable=self.sure_var, font=f, width=6, justify="center")
        dokunmatik(sure_e, self.sure_var, "Raf ömrü (sayı)", "tamsayi")
        sure_e.grid(row=2, column=1, sticky="w")
        ttk.Combobox(k, textvariable=self.birim_var, font=f, width=8, state="readonly",
                     values=list(BIRIM_TERS)).grid(row=2, column=2, sticky="w")

        tk.Label(k, text="Saklama", font=f).grid(row=3, column=0, sticky="e", padx=6, pady=6)
        ttk.Combobox(k, textvariable=self.sak_var, font=f, width=32, state="readonly",
                     values=list(SAKLAMA_TERS)).grid(row=3, column=1, columnspan=2, sticky="w")

        tk.Label(k, text="Uyarı notu", font=f).grid(row=4, column=0, sticky="e", padx=6, pady=6)
        uyari_e = tk.Entry(k, textvariable=self.uyari_var, font=f, width=34)
        dokunmatik(uyari_e, self.uyari_var, "Uyarı notu", "metin")
        uyari_e.grid(row=4, column=1, columnspan=2, sticky="w")
        tk.Label(k, text="(isteğe bağlı, etikette görünür. Örn: Pişirildikten sonra)",
                 font=("", 10), fg="#666").grid(row=5, column=1, columnspan=2, sticky="w")
        tk.Label(k, text="1 ay = 30 gün olarak hesaplanır.", font=("", 10), fg="#666"
                 ).grid(row=6, column=1, columnspan=2, sticky="w")

        d = ttk.Frame(k)
        d.grid(row=7, column=0, columnspan=3, pady=(14, 0))
        tk.Button(d, text="KAYDET", font=("", 15, "bold"), bg="#2e7d32", fg="white",
                  width=12, height=2, command=self._kaydet).pack(side="left", padx=8)
        tk.Button(d, text="İptal", font=("", 14), width=10, height=2,
                  command=self.destroy).pack(side="left", padx=8)
        self.grab_set()
        self.wait_window(self)

    def _kaydet(self):
        try:
            sure = int(self.sure_var.get())
        except ValueError:
            messagebox.showerror("Hatalı giriş", "Süre tam sayı olmalı.", parent=self)
            return
        ad, uyari = self.ad_var.get().strip(), self.uyari_var.get().strip()
        kid = self.kat_id.get(self.kat_var.get())
        birim = BIRIM_TERS[self.birim_var.get()]
        saklama = SAKLAMA_TERS[self.sak_var.get()]
        try:
            if self.urun is None:
                db.urun_ekle(self.conn, ad, kid, sure, birim, saklama, uyari)
            else:
                if (sure, birim) != (self.urun.sure_deger, self.urun.sure_birim):
                    eski = f"{self.urun.sure_deger} {BIRIM_ETIKET[self.urun.sure_birim]}"
                    yeni = f"{sure} {BIRIM_ETIKET[birim]}"
                    if not messagebox.askyesno(
                            "Raf ömrü değişiyor",
                            f"{ad}\n\nEski süre: {eski}\nYeni süre: {yeni}\n\n"
                            "Bu gıda güvenliğini etkiler. Onaylıyor musunuz?", parent=self):
                        return
                db.urun_guncelle(self.conn, self.urun.id, ad, kid, sure, birim, saklama, uyari)
        except db.YonetimHatasi as e:
            messagebox.showerror("Kaydedilemedi", str(e), parent=self)
            return
        self.kaydedildi = True
        self.destroy()


class Yonetim(tk.Toplevel):
    def __init__(self, ana, conn, degisti_cb):
        super().__init__(ana)
        self.conn, self.degisti_cb = conn, degisti_cb
        self.title("Yönetim")
        self.geometry("980x720")
        self.transient(ana)

        if db.pin_varsayilan_mi(conn):
            messagebox.showwarning(
                "Varsayılan PIN", "Şu an varsayılan PIN (1234) kullanılıyor.\n"
                "Lütfen 'PIN Değiştir' ile yeni bir PIN belirleyin.", parent=self)

        self.agac = ttk.Treeview(self, columns=("ad", "kategori", "sure", "saklama", "durum"),
                                 show="headings", height=12, selectmode="browse")
        for kol, bas, gen in (("ad", "Ürün", 330), ("kategori", "Kategori", 180),
                              ("sure", "Raf ömrü", 100), ("saklama", "Saklama", 150),
                              ("durum", "Durum", 80)):
            self.agac.heading(kol, text=bas)
            self.agac.column(kol, width=gen)
        self.agac.tag_configure("pasif", foreground="#999999")
        yb = ttk.Scrollbar(self, orient="vertical", command=self.agac.yview)
        self.agac.configure(yscrollcommand=yb.set)
        self.agac.pack(side="top", fill="both", expand=True, padx=(10, 0), pady=10)
        yb.place(relx=1.0, x=-10, y=10, relheight=0.7, anchor="ne")

        b = tk.Frame(self)
        b.pack(side="bottom", pady=10)
        dugmeler = [
            ("Ürün Ekle", self._ekle), ("Düzenle", self._duzenle),
            ("Pasife Al / Aktif Et", self._durum), ("Sil", self._sil),
            ("Silinenler", self._silinenler), ("Kategori Ekle", self._kategori),
            ("Değişiklik Geçmişi", self._gecmis), ("PIN Değiştir", self._pin),
            ("Kurtarma Kodu Yenile", self._kurtarma_yenile), ("Yedek Al", self._yedek),
            ("Yedekten Geri Yükle", self._geri_yukle), ("Kayıt Saklama Süresi", self._saklama),
            ("Kapat", self.destroy),
        ]
        for i, (m, cmd) in enumerate(dugmeler):
            tk.Button(b, text=m, font=("", 12), width=13, height=2, wraplength=140, command=cmd
                      ).grid(row=i // 5, column=i % 5, padx=4, pady=4)
        self._doldur()
        self.after(KONTROL_ARALIGI_MS, self._zaman_asimi)

    def _doldur(self):
        self.agac.delete(*self.agac.get_children())
        self.urunler = {u.id: u for u in db.urunleri_getir(self.conn, sadece_aktif=False)}
        for u in self.urunler.values():
            self.agac.insert("", "end", iid=str(u.id), tags=() if u.aktif else ("pasif",), values=(
                u.ad, u.kategori, f"{u.sure_deger} {BIRIM_ETIKET[u.sure_birim]}",
                SAKLAMA_ETIKET[u.saklama], "Aktif" if u.aktif else "Pasif"))

    def _secili(self):
        s = self.agac.selection()
        if not s:
            messagebox.showinfo("Seçim yok", "Önce listeden bir ürün seçin.", parent=self)
            return None
        return self.urunler[int(s[0])]

    def _degisti(self):
        self._doldur()
        self.degisti_cb()

    def _ekle(self):
        if UrunFormu(self, self.conn).kaydedildi:
            self._degisti()

    def _duzenle(self):
        u = self._secili()
        if u and UrunFormu(self, self.conn, u).kaydedildi:
            self._degisti()

    def _durum(self):
        u = self._secili()
        if not u:
            return
        yeni = not u.aktif
        soru = (f"'{u.ad}' etiket ekranına geri eklensin mi?" if yeni else
                f"'{u.ad}' etiket ekranından kaldırılsın mı?\n(Silinmez, daha sonra tekrar aktif edilebilir.)")
        if messagebox.askyesno("Onay", soru, parent=self):
            db.urun_aktif_yap(self.conn, u.id, yeni)
            self._degisti()

    def _kategori(self):
        ad = klavye_iste(self, "Yeni kategori adı", "", "metin")
        if ad is None:
            return
        try:
            db.kategori_ekle(self.conn, ad)
        except db.YonetimHatasi as e:
            messagebox.showerror("Eklenemedi", str(e), parent=self)
            return
        messagebox.showinfo("Eklendi", "Kategori eklendi. Ürün eklerken seçebilirsiniz.", parent=self)

    def _pin_onayla(self, baslik="Onay için mevcut PIN'i girin") -> bool:
        """Hassas işlemlerden önce PIN'i yeniden ister (yönetim ekranı açık unutulmuş olabilir)."""
        pin = pin_iste(self, baslik)
        if pin is None:
            return False
        if not db.pin_dogru(self.conn, pin):
            messagebox.showerror("Hatalı PIN", "PIN yanlış, işlem yapılmadı.", parent=self)
            return False
        return True

    def _pin(self):
        if not self._pin_onayla("Mevcut PIN'i girin"):
            return
        yeni = pin_iste(self, "Yeni PIN (4-8 rakam)")
        if yeni is None:
            return
        if pin_iste(self, "Yeni PIN (tekrar)") != yeni:
            messagebox.showerror("Hata", "İki PIN aynı değil.", parent=self)
            return
        try:
            kod = db.pin_degistir(self.conn, yeni)
        except db.YonetimHatasi as e:
            messagebox.showerror("Hata", str(e), parent=self)
            return
        messagebox.showinfo("Tamam", "PIN değiştirildi.", parent=self)
        kurtarma_kodu_goster(self, kod)

    def _kurtarma_yenile(self):
        if not self._pin_onayla():
            return
        if not messagebox.askyesno(
                "Kurtarma kodu", "Yeni bir kurtarma kodu üretilsin mi?\n"
                "Eski kod geçersiz olur.", parent=self):
            return
        kurtarma_kodu_goster(self, db.kurtarma_kodu_uret(self.conn))

    def _sil(self):
        u = self._secili()
        if not u:
            return
        if messagebox.askyesno(
                "Ürün silinsin mi?",
                f"'{u.ad}' silinsin mi?\n\nÜrün etiket ekranından kalkar ve 'Silinenler' "
                "bölümüne taşınır. İstediğiniz zaman oradan geri getirebilirsiniz.", parent=self):
            db.urun_sil(self.conn, u.id)
            self._degisti()

    def _silinenler(self):
        Silinenler(self, self.conn, self._degisti)

    def _yedek(self):
        varsayilan = f"coffy_yedek_{datetime.now():%Y%m%d_%H%M}.db"
        yol = filedialog.asksaveasfilename(parent=self, defaultextension=".db",
                                           initialfile=varsayilan, filetypes=[("Veritabanı", "*.db")])
        if yol:
            db.yedek_al(self.conn, yol)
            messagebox.showinfo("Yedek alındı", yol, parent=self)

    def _gecmis(self):
        Gecmis(self, self.conn)

    def _saklama(self):
        """Etiket kayıtlarının kaç ay saklanacağı (eskileri her gün otomatik temizlenir)."""
        if not self._pin_onayla():
            return
        mevcut = db.etiket_saklama_ay(self.conn)
        s = klavye_iste(self, f"Etiket kayıtları kaç ay saklansın? (şu an {mevcut}, en az {db.SAKLAMA_EN_AZ_AY})",
                        str(mevcut), "tamsayi")
        if not s:
            return
        ay = int(s)
        sayi = db.silinecek_etiket_sayisi(self.conn, ay) if db.SAKLAMA_EN_AZ_AY <= ay <= db.SAKLAMA_EN_FAZLA_AY else 0
        if ay < mevcut and sayi and not messagebox.askyesno(
                "Saklama süresi kısalıyor",
                f"{ay} ay olursa {sayi} eski etiket kaydı bir sonraki temizlikte (bugün alınan yedekten sonra) "
                "silinecek.\n\nDevam edilsin mi?", icon="warning", parent=self):
            return
        try:
            db.etiket_saklama_ayarla(self.conn, ay)
        except db.YonetimHatasi as e:
            messagebox.showerror("Kaydedilemedi", str(e), parent=self)
            return
        messagebox.showinfo("Kaydedildi", f"Etiket kayıtları {ay} ay saklanacak.\n"
                            "Daha eski kayıtlar her gün otomatik temizlenir. "
                            "Ürün değişiklik geçmişi hiçbir zaman silinmez.", parent=self)

    def _geri_yukle(self):
        if not self._pin_onayla("Geri yükleme için PIN'i girin"):
            return
        yol = filedialog.askopenfilename(
            parent=self, title="Yedek dosyasını seçin", initialdir=str(db.yedek_klasoru()),
            filetypes=[("Veritabanı yedeği", "*.db"), ("Tüm dosyalar", "*.*")])
        if not yol:
            return
        try:
            ozet = db.yedek_incele(yol)
        except db.YonetimHatasi as e:
            messagebox.showerror("Geçersiz yedek", str(e), parent=self)
            return
        if not messagebox.askyesno(
                "Yedekten geri yükle",
                f"Yedek: {yol.replace(chr(92), '/').split('/')[-1]}\n"
                f"Dosya tarihi: {ozet['tarih']:%d.%m.%Y %H:%M}\n"
                f"İçinde: {ozet['urun']} ürün, {ozet['etiket']} etiket kaydı\n\n"
                "Şu anki ürünler ve etiket kayıtları bu yedekle DEĞİŞTİRİLECEK.\n"
                "PIN ve kurtarma kodu değişmez. Geri yüklemeden önce şu anki durum "
                "otomatik olarak ayrıca yedeklenir.\n\nDevam edilsin mi?", icon="warning", parent=self):
            return
        try:
            onceki = db.yedekten_geri_yukle(self.conn, yol)
        except db.YonetimHatasi as e:
            messagebox.showerror("Geri yüklenemedi", str(e), parent=self)
            return
        self._degisti()
        messagebox.showinfo("Geri yüklendi", f"Yedek geri yüklendi.\n\nÖnceki durum şuraya yedeklendi:\n{onceki}",
                            parent=self)

    @staticmethod
    def _engelleyen_var(widget) -> bool:
        """Bir giriş/onay penceresi açıkken (yarım kalmış işlem) zaman aşımı beklesin."""
        for w in widget.winfo_children():
            if isinstance(w, (PinDialog, UrunFormu)) or type(w).__name__ == "EkranKlavyesi":
                return True
            if Yonetim._engelleyen_var(w):
                return True
        return False

    def _zaman_asimi(self):
        """Dokunma/tuş olmadan ZAMAN_ASIMI_SN geçerse yönetim ekranını kapatır (PIN yeniden gerekir)."""
        if not self.winfo_exists():
            return
        ana = self.master
        bosta = time.monotonic() - getattr(ana, "son_etkilesim", time.monotonic())
        if bosta >= ZAMAN_ASIMI_SN and not self._engelleyen_var(self):
            if hasattr(ana, "durum_var"):
                ana.durum_var.set("Yönetim ekranı hareketsizlik nedeniyle kapatıldı.")
            self.destroy()
            return
        self.after(KONTROL_ARALIGI_MS, self._zaman_asimi)

class Silinenler(tk.Toplevel):
    """Çöp kutusu: silinen ürünleri geri getir veya (PIN ile) kalıcı sil."""

    def __init__(self, ana, conn, degisti_cb):
        super().__init__(ana)
        self.conn, self.degisti_cb = conn, degisti_cb
        self.title("Silinenler")
        self.geometry("760x480")
        self.transient(ana)
        self.agac = ttk.Treeview(self, columns=("ad", "kategori", "sure"), show="headings",
                                 height=12, selectmode="browse")
        for kol, bas, gen in (("ad", "Ürün", 360), ("kategori", "Kategori", 200), ("sure", "Raf ömrü", 100)):
            self.agac.heading(kol, text=bas)
            self.agac.column(kol, width=gen)
        self.agac.pack(fill="both", expand=True, padx=10, pady=10)
        b = tk.Frame(self)
        b.pack(pady=10)
        tk.Button(b, text="Geri Getir", font=("", 13), width=16, height=2,
                  command=self._geri).pack(side="left", padx=6)
        tk.Button(b, text="Kalıcı Sil (PIN ister)", font=("", 13), width=20, height=2,
                  fg="#b00020", command=self._kalici).pack(side="left", padx=6)
        tk.Button(b, text="Kapat", font=("", 13), width=10, height=2,
                  command=self.destroy).pack(side="left", padx=6)
        self._doldur()

    def _doldur(self):
        self.agac.delete(*self.agac.get_children())
        self.urunler = {u.id: u for u in db.silinen_urunler(self.conn)}
        for u in self.urunler.values():
            self.agac.insert("", "end", iid=str(u.id), values=(
                u.ad, u.kategori, f"{u.sure_deger} {BIRIM_ETIKET[u.sure_birim]}"))

    def _secili(self):
        s = self.agac.selection()
        if not s:
            messagebox.showinfo("Seçim yok", "Önce listeden bir ürün seçin.", parent=self)
            return None
        return self.urunler[int(s[0])]

    def _geri(self):
        u = self._secili()
        if u:
            db.urun_geri_getir(self.conn, u.id)
            self._doldur()
            self.degisti_cb()

    def _kalici(self):
        u = self._secili()
        if not u:
            return
        if not messagebox.askyesno(
                "Kalıcı silme", f"'{u.ad}' KALICI olarak silinecek.\nBu işlem geri alınamaz!\n\nDevam edilsin mi?",
                icon="warning", parent=self):
            return
        pin = pin_iste(self, "Onay için PIN'i tekrar girin")
        if pin is None:
            return
        if not db.pin_dogru(self.conn, pin):
            messagebox.showerror("Hatalı PIN", "PIN yanlış, ürün silinmedi.", parent=self)
            return
        db.urun_kalici_sil(self.conn, u.id)
        self._doldur()



class Gecmis(tk.Toplevel):
    """Değişiklik geçmişi: ürün adı, tarih aralığı ve türe göre arama. Kayıtlar hiç silinmez."""

    def __init__(self, ana, conn):
        super().__init__(ana)
        self.conn = conn
        self.title("Değişiklik Geçmişi")
        self.geometry("1020x700")
        self.transient(ana)
        self.metin_var, self.bas_var, self.bit_var = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.tur_var = tk.StringVar(value="Tümü")
        f = ("", 13)

        s = tk.Frame(self)
        s.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(s, text="Ürün:", font=f).grid(row=0, column=0, sticky="e", padx=4, pady=4)
        urun_e = tk.Entry(s, textvariable=self.metin_var, font=f, width=26)
        urun_e.grid(row=0, column=1, sticky="w")
        dokunmatik(urun_e, self.metin_var, "Ürün adında ara", "metin")
        tk.Label(s, text="Tür:", font=f).grid(row=0, column=2, sticky="e", padx=(16, 4))
        tur = ttk.Combobox(s, textvariable=self.tur_var, font=f, width=30, state="readonly",
                           values=list(db.GECMIS_TURLERI))
        tur.grid(row=0, column=3, sticky="w")
        tur.bind("<<ComboboxSelected>>", lambda _e: self._ara())

        tk.Label(s, text="Başlangıç:", font=f).grid(row=1, column=0, sticky="e", padx=4, pady=4)
        self.bas_e = tk.Entry(s, textvariable=self.bas_var, font=f, width=12, justify="center")
        self.bas_e.grid(row=1, column=1, sticky="w")
        dokunmatik(self.bas_e, self.bas_var, "Başlangıç tarihi (GG.AA.YYYY, boş = sınırsız)", "gun")
        tk.Label(s, text="Bitiş:", font=f).grid(row=1, column=2, sticky="e", padx=(16, 4))
        self.bit_e = tk.Entry(s, textvariable=self.bit_var, font=f, width=12, justify="center")
        self.bit_e.grid(row=1, column=3, sticky="w")
        dokunmatik(self.bit_e, self.bit_var, "Bitiş tarihi (GG.AA.YYYY, boş = sınırsız)", "gun")

        b = tk.Frame(self)
        b.pack(fill="x", padx=10, pady=4)
        for metin, gun in (("Bugün", 1), ("Son 7 gün", 7), ("Son 30 gün", 30)):
            tk.Button(b, text=metin, font=("", 12), width=11,
                      command=lambda g=gun: self._hizli(g)).pack(side="left", padx=3)
        tk.Button(b, text="ARA", font=("", 13, "bold"), bg="#2e7d32", fg="white", width=10,
                  command=self._ara).pack(side="left", padx=(16, 3))
        tk.Button(b, text="Temizle", font=("", 12), width=10,
                  command=self._temizle).pack(side="left", padx=3)

        tabl = tk.Frame(self)
        tabl.pack(fill="both", expand=True, padx=10, pady=6)
        self.agac = ttk.Treeview(tabl, columns=("zaman", "urun", "alan", "eski", "yeni"),
                                 show="headings", height=14)
        for kol, bas, gen in (("zaman", "Zaman", 130), ("urun", "Ürün", 290), ("alan", "Alan", 110),
                              ("eski", "Eski", 190), ("yeni", "Yeni", 190)):
            self.agac.heading(kol, text=bas)
            self.agac.column(kol, width=gen)
        yb = ttk.Scrollbar(tabl, orient="vertical", command=self.agac.yview)
        self.agac.configure(yscrollcommand=yb.set)
        self.agac.pack(side="left", fill="both", expand=True)
        yb.pack(side="right", fill="y")

        self.durum_var = tk.StringVar()
        tk.Label(self, textvariable=self.durum_var, font=("", 12), anchor="w", padx=10
                 ).pack(fill="x", pady=(0, 4))
        tk.Button(self, text="Kapat", font=("", 12), width=10, command=self.destroy).pack(pady=(0, 10))
        self._ara()

    def _hizli(self, gun):
        bugun = datetime.now().date()
        self.bas_var.set((bugun - timedelta(days=gun - 1)).strftime("%d.%m.%Y"))
        self.bit_var.set(bugun.strftime("%d.%m.%Y"))
        self._ara()

    def _temizle(self):
        self.metin_var.set("")
        self.bas_var.set("")
        self.bit_var.set("")
        self.tur_var.set("Tümü")
        self._ara()

    def _tarih(self, metin, ad):
        metin = metin.strip()
        if not metin:
            return None
        try:
            return datetime.strptime(metin, "%d.%m.%Y").date()
        except ValueError:
            messagebox.showerror("Hatalı tarih", f"{ad} tarihi GG.AA.YYYY biçiminde olmalı.", parent=self)
            raise

    def _ara(self):
        try:
            bas = self._tarih(self.bas_var.get(), "Başlangıç")
            bit = self._tarih(self.bit_var.get(), "Bitiş")
        except ValueError:
            return
        if bas and bit and bas > bit:
            messagebox.showerror("Hatalı aralık", "Başlangıç tarihi bitişten sonra olamaz.", parent=self)
            return
        satirlar, daha = db.degisiklik_ara(self.conn, self.metin_var.get(), bas, bit,
                                           self.tur_var.get(), GECMIS_LIMIT)
        self.agac.delete(*self.agac.get_children())
        for r in satirlar:
            self.agac.insert("", "end", values=(
                datetime.strptime(r["zaman"], db.FMT).strftime("%d.%m.%Y %H:%M"),
                r["urun_ad"], r["alan"], r["eski"], r["yeni"]))
        self.durum_var.set(f"{len(satirlar)} kayıt" + (
            f" (en yeni {GECMIS_LIMIT} gösteriliyor, filtreyi daraltın)" if daha else ""))