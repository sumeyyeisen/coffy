"""Ana ekran: kategori sekmeleri + büyük ürün butonları (dokunmatik için)."""
import base64
import time
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

import db
import etiket
import yazici
from skt import skt_hesapla, etiket_verisi
from klavye import dokunmatik
from yonetim import Yonetim, pin_iste, pin_kurtarma_akisi, UNUTTUM

TARIH_FMT = "%d.%m.%Y %H:%M"
SUTUN_SAYISI = 4


def tarih_oku(metin: str) -> datetime:
    return datetime.strptime(metin.strip(), TARIH_FMT)


class Onizleme(tk.Toplevel):
    """Ürüne dokununca açılır: otomatik tarihler hazır gelir, istenirse elle değişir."""

    def __init__(self, ana, urun, yazdir_cb):
        super().__init__(ana)
        self.urun, self.yazdir_cb = urun, yazdir_cb
        self.title("Etiket Önizleme")
        self.transient(ana)
        self.resizable(False, False)

        self.baslangic = datetime.now().replace(second=0, microsecond=0)
        self.acilis_var = tk.StringVar(value=self.baslangic.strftime(TARIH_FMT))
        self.skt_var = tk.StringVar(
            value=skt_hesapla(urun, self.baslangic).strftime(TARIH_FMT))
        self.manuel_var = tk.BooleanVar(value=False)

        k = ttk.Frame(self, padding=20)
        k.pack(side="left", anchor="n")
        tk.Label(k, text=urun.ad, font=("", 20, "bold"), wraplength=500).grid(
            row=0, column=0, columnspan=2, pady=(0, 6))
        tk.Label(k, text=urun.saklama_metni(), font=("", 13)).grid(
            row=1, column=0, columnspan=2)
        if urun.uyari:
            tk.Label(k, text=urun.uyari, font=("", 14, "bold"), fg="#b00020").grid(
                row=2, column=0, columnspan=2, pady=4)

        tk.Label(k, text="Açılış:", font=("", 14)).grid(
            row=3, column=0, sticky="e", pady=8, padx=6)
        self.acilis_e = tk.Entry(k, textvariable=self.acilis_var, font=("", 18),
                                 width=18, justify="center", state="disabled")
        self.acilis_e.grid(row=3, column=1)
        dokunmatik(self.acilis_e, self.acilis_var, "Açılış (GG.AA.YYYY SS:DD)", "tarih")

        tk.Label(k, text="SKT:", font=("", 18, "bold")).grid(
            row=4, column=0, sticky="e", pady=8, padx=6)
        self.skt_e = tk.Entry(k, textvariable=self.skt_var, font=("", 22, "bold"),
                              width=16, justify="center", state="disabled")
        self.skt_e.grid(row=4, column=1)
        dokunmatik(self.skt_e, self.skt_var, "SKT (GG.AA.YYYY SS:DD)", "tarih")

        tk.Checkbutton(k, text="Manuel düzenle", variable=self.manuel_var,
                       font=("", 13), command=self._manuel_degisti).grid(
            row=5, column=0, columnspan=2, pady=(10, 0))
        self.hesap_b = tk.Button(k, text="SKT'yi açılışa göre yeniden hesapla",
                                 font=("", 12), state="disabled",
                                 command=self._yeniden_hesapla)
        self.hesap_b.grid(row=6, column=0, columnspan=2, pady=6)
        tk.Label(k, text="Tarih biçimi: GG.AA.YYYY SS:DD", font=("", 10),
                 fg="#666").grid(row=7, column=0, columnspan=2)

        d = ttk.Frame(k)
        d.grid(row=8, column=0, columnspan=2, pady=(14, 0))
        tk.Button(d, text="YAZDIR", font=("", 16, "bold"), bg="#2e7d32", fg="white",
                  width=12, height=2, command=self._yazdir).pack(side="left", padx=8)
        tk.Button(d, text="İptal", font=("", 14), width=10, height=2,
                  command=self.destroy).pack(side="left", padx=8)

        # Sağda: etiketin gerçek görünümü (tarihler değişince canlı güncellenir)
        sag = ttk.Frame(self, padding=(0, 20, 20, 20))
        sag.pack(side="left", anchor="n")
        tk.Label(sag, text="Etiket önizleme", font=("", 11), fg="#666").pack()
        self.onizleme_lbl = tk.Label(sag, relief="solid", bd=1, bg="white", font=("", 12), fg="#b00020")
        self.onizleme_lbl.pack(pady=4)
        self._foto = None
        self.acilis_var.trace_add("write", self._onizleme_guncelle)
        self.skt_var.trace_add("write", self._onizleme_guncelle)
        self._onizleme_guncelle()

        self.grab_set()

    def _onizleme_guncelle(self, *_):
        try:
            veri = etiket_verisi(self.urun, acilis=tarih_oku(self.acilis_var.get()),
                                 skt=tarih_oku(self.skt_var.get()))
        except ValueError:  # yarım yazılmış ya da geçersiz tarih
            self._foto = None
            self.onizleme_lbl.config(image="", text="Geçersiz\ntarih / saat", width=20, height=12)
            return
        png = etiket.png_bytes(etiket.etiket_ciz(veri), olcek=0.5)
        self._foto = tk.PhotoImage(data=base64.b64encode(png))
        self.onizleme_lbl.config(image=self._foto, text="", width=0, height=0)

    def _manuel_degisti(self):
        durum = "normal" if self.manuel_var.get() else "disabled"
        self.acilis_e.config(state=durum)
        self.skt_e.config(state=durum)
        self.hesap_b.config(state=durum)

    def _yeniden_hesapla(self):
        try:
            acilis = tarih_oku(self.acilis_var.get())
        except ValueError:
            messagebox.showerror("Hatalı tarih", "Açılış tarihi GG.AA.YYYY SS:DD biçiminde olmalı.", parent=self)
            return
        self.skt_var.set(skt_hesapla(self.urun, acilis).strftime(TARIH_FMT))

    def _yazdir(self):
        try:
            acilis = tarih_oku(self.acilis_var.get())
            skt = tarih_oku(self.skt_var.get())
            veri = etiket_verisi(self.urun, acilis=acilis, skt=skt)
        except ValueError as e:
            mesaj = str(e) if "SKT" in str(e) else "Tarihler GG.AA.YYYY SS:DD biçiminde olmalı."
            messagebox.showerror("Hatalı giriş", mesaj, parent=self)
            return
        # Elle değiştirilmişse işaretle (açılış ya da SKT otomatik değerden farklıysa)
        veri["manuel"] = (acilis != self.baslangic) or (skt != skt_hesapla(self.urun, acilis))
        if self.yazdir_cb(veri):
            self.destroy()


class SonBasilanlar(tk.Toplevel):
    def __init__(self, ana, conn, yazdir_cb):
        super().__init__(ana)
        self.conn, self.yazdir_cb = conn, yazdir_cb
        self.title("Son Basılanlar")
        self.geometry("760x460")
        self.transient(ana)

        self.agac = ttk.Treeview(self, columns=("ad", "acilis", "skt"),
                                 show="headings", height=12)
        for kolon, baslik, gen in (("ad", "Ürün", 330), ("acilis", "Açılış", 160), ("skt", "SKT", 160)):
            self.agac.heading(kolon, text=baslik)
            self.agac.column(kolon, width=gen)
        self.agac.pack(fill="both", expand=True, padx=10, pady=10)

        self.kayitlar = db.son_kayitlar(conn)
        for i, k in enumerate(self.kayitlar):
            isaret = " *" if k["manuel"] else ""
            self.agac.insert("", "end", iid=str(i), values=(
                k["ad"] + isaret, k["acilis"].strftime(TARIH_FMT), k["skt"].strftime(TARIH_FMT)))

        tk.Label(self, text="* manuel düzenlenmiş", font=("", 10), fg="#666").pack()
        tk.Button(self, text="Seçileni Tekrar Yazdır", font=("", 14), height=2,
                  command=self._tekrar).pack(pady=8)

    def _tekrar(self):
        secili = self.agac.selection()
        if not secili:
            return
        veri = self.kayitlar[int(secili[0])]
        if self.yazdir_cb(veri):
            self.destroy()


class Uygulama(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Coffy SKT Etiket")
        self.geometry("1024x700")
        self.conn = db.baglan()
        # Yönetim ekranı zaman aşımı için son dokunma/tuş zamanını izle
        self.son_etkilesim = time.monotonic()
        for olay in ("<ButtonPress>", "<KeyPress>"):
            self.bind_all(olay, self._etkilesim, add="+")

        stil = ttk.Style()
        stil.configure("TNotebook.Tab", padding=(18, 12), font=("", 13, "bold"))

        self.durum_var = tk.StringVar(value="Etiket basmak için ürüne dokunun.")
        tk.Label(self, textvariable=self.durum_var, font=("", 13), anchor="w",
                 bg="#eeeeee", padx=10, pady=8).pack(side="bottom", fill="x")
        bar = tk.Frame(self)
        bar.pack(side="bottom", fill="x", padx=10, pady=4)
        tk.Button(bar, text="Son Basılanlar", font=("", 12),
                  command=self._son_basilanlar).pack(side="right", padx=(8, 0))
        tk.Button(bar, text="Yönetim", font=("", 12),
                  command=self._yonetim).pack(side="right")

        self.defter = ttk.Notebook(self)
        self.defter.pack(fill="both", expand=True)
        self._sekmeleri_kur()
        self._otomatik_yedek()

    def _etkilesim(self, _olay=None):
        self.son_etkilesim = time.monotonic()

    def _otomatik_yedek(self):
        """Günde bir kez yedek alır (program günlerce açık kalsa da yarım saatte bir kontrol eder)."""
        try:
            yol = db.otomatik_yedek(self.conn)
            if yol:
                self.durum_var.set(f"Günlük yedek alındı: {yol.name}")
            # Temizlik yedekten SONRA yapılır; yedek alınamazsa (yukarıda hata verirse) hiçbir şey silinmez
            silinen = db.eski_etiketleri_temizle(self.conn)
            if silinen:
                self.durum_var.set(f"{silinen} eski etiket kaydı temizlendi (saklama süresi: "
                                   f"{db.etiket_saklama_ay(self.conn)} ay).")
        except Exception as e:  # yedek hatası etiket basmayı engellemesin
            self.durum_var.set(f"Otomatik yedek alınamadı: {e}")
        self.after(30 * 60 * 1000, self._otomatik_yedek)

    def _sekmeleri_kur(self):
        """Aktif ürünlerden sekmeleri yeniden çizer (yönetimde değişiklik olunca da çağrılır)."""
        secili = self.defter.index(self.defter.select()) if self.defter.tabs() else 0
        for w in self.defter.winfo_children():
            w.destroy()

        kategoriler: dict[str, list] = {}
        for u in db.urunleri_getir(self.conn):
            kategoriler.setdefault(u.kategori, []).append(u)

        if not kategoriler:
            sayfa = ttk.Frame(self.defter, padding=30)
            self.defter.add(sayfa, text="Ürün yok")
            tk.Label(sayfa, text="Aktif ürün yok. 'Yönetim' ekranından ürün ekleyin.",
                     font=("", 14)).pack()
            return

        for kategori, urunler in kategoriler.items():
            sayfa = ttk.Frame(self.defter, padding=8)
            self.defter.add(sayfa, text=kategori)
            for c in range(SUTUN_SAYISI):
                sayfa.columnconfigure(c, weight=1, uniform="k")
            for i, urun in enumerate(urunler):
                tk.Button(sayfa, text=urun.ad, font=("", 12, "bold"), wraplength=210,
                          height=3, command=lambda u=urun: Onizleme(self, u, self.yazdir_ve_kaydet)
                          ).grid(row=i // SUTUN_SAYISI, column=i % SUTUN_SAYISI,
                                 sticky="nsew", padx=4, pady=4)
        sekmeler = self.defter.tabs()
        self.defter.select(sekmeler[min(secili, len(sekmeler) - 1)])

    def yazdir_ve_kaydet(self, veri: dict) -> bool:
        try:
            yazici.yazdir(veri)
        except yazici.YaziciHatasi as e:  # yazıcı hatası: kaydetme, kullanıcıya göster
            messagebox.showerror("Yazdırma hatası", f"{e}\n\nEtiket basılmadı ve kaydedilmedi.")
            return False
        except Exception as e:  # beklenmeyen hata
            messagebox.showerror("Yazdırma hatası", f"Beklenmeyen hata: {e}\n\nEtiket basılmadı ve kaydedilmedi.")
            return False
        db.kaydet(self.conn, veri)
        self.durum_var.set(
            f"✔ {veri['ad']} yazdırıldı — SKT: {veri['skt'].strftime(TARIH_FMT)}")
        return True

    def _son_basilanlar(self):
        SonBasilanlar(self, self.conn, self.yazdir_ve_kaydet)

    def _yonetim(self):
        pin = pin_iste(self, "Yönetim PIN'i", unuttum=True)
        if pin is None:
            return
        if pin == UNUTTUM:
            pin_kurtarma_akisi(self, self.conn)
            return
        if not db.pin_dogru(self.conn, pin):
            messagebox.showerror("Hatalı PIN", "PIN yanlış.")
            return
        Yonetim(self, self.conn, self._sekmeleri_kur)


if __name__ == "__main__":
    Uygulama().mainloop()