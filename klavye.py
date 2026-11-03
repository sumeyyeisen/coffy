"""Dokunmatik ekran için uygulama içi klavye.

Windows'un ekran klavyesi Tkinter'da kendiliğinden açılmaz; bu yüzden kendi
klavyemizi kullanıyoruz. Modlar: "metin" (Türkçe Q), "tarih" (sadece rakam, ayraçlar
otomatik: 101120260800 -> 10.11.2026 08:00), "gun" (sadece gün: GG.AA.YYYY, boş bırakılabilir), "tamsayi" (sadece rakam).
Tarih ve sayıda mevcut değer seçili gelir: ilk rakam eskisini siler.
"""
import tkinter as tk
from datetime import datetime

MAKS = {"metin": 60, "tarih": 16, "gun": 10, "tamsayi": 5}
SATIRLAR_METIN = [
    list("1234567890"),
    list("qwertyuıopğü"),
    list("asdfghjklşi"),
    list("zxcvbnmöç.,-"),
]
EKSTRA = list("()/&")
# Tarih girişinde otomatik ayraçlar: GG.AA.YYYY SS:DD
AYIRAC = {2: ".", 5: ".", 10: " ", 13: ":"}


def tr_buyuk(c: str) -> str:
    """Türkçe büyük harf: i→İ, ı→I (Python'un varsayılanı i→I verir, yanlış)."""
    return {"i": "İ", "ı": "I"}.get(c, c.upper())


class EkranKlavyesi(tk.Toplevel):
    def __init__(self, ana, baslik, baslangic="", mod="metin"):
        super().__init__(ana)
        self.title(baslik)
        self.transient(ana)
        self.resizable(False, False)
        self.mod, self.maks = mod, MAKS[mod]
        self.deger = baslangic[: self.maks]
        self.sonuc = None
        self.shift = (mod == "metin" and not baslangic)
        self.secili = (mod != "metin") and bool(baslangic)
        self.harf_tuslari = []
        self.shift_b = None

        tk.Label(self, text=baslik, font=("", 15, "bold")).pack(pady=(12, 4))
        self.gosterge = tk.Label(self, font=("", 22), anchor="w", relief="sunken",
                                 bg="white", width=40, padx=8)
        self.gosterge.pack(padx=14, pady=6)
        govde = tk.Frame(self)
        govde.pack(padx=10, pady=6)
        if mod == "metin":
            self._metin_klavye(govde)
        else:
            self._sayi_klavye(govde)

        alt = tk.Frame(self)
        alt.pack(pady=(4, 12))
        tk.Button(alt, text="TAMAM", font=("", 16, "bold"), bg="#2e7d32", fg="white",
                  width=12, height=2, command=self._tamam).pack(side="left", padx=8)
        tk.Button(alt, text="İptal", font=("", 14), width=10, height=2,
                  command=self.destroy).pack(side="left", padx=8)

        self._guncelle()
        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = max(0, (self.winfo_screenwidth() - w) // 2)
        y = max(0, self.winfo_screenheight() - h - 60)
        self.geometry(f"+{x}+{y}")
        self.grab_set()

    # ---- düzenler ----
    def _metin_klavye(self, govde):
        for r, satir in enumerate(SATIRLAR_METIN):
            c = tk.Frame(govde)
            c.pack(pady=2)
            if r == 3:
                self.shift_b = tk.Button(c, text="⇧", font=("", 16, "bold"), width=3,
                                         command=self._shift_degistir)
                self.shift_b.pack(side="left", padx=(0, 6))
            for t in satir:
                b = tk.Button(c, text=t, font=("", 16, "bold"), width=3,
                              command=lambda x=t: self._tus(x))
                b.pack(side="left", padx=2)
                if t.isalpha():
                    self.harf_tuslari.append((b, t))
            if r == 0:
                tk.Button(c, text="⌫", font=("", 16, "bold"), width=5,
                          command=self._sil).pack(side="left", padx=(6, 0))
        son = tk.Frame(govde)
        son.pack(pady=2)
        for t in EKSTRA:
            tk.Button(son, text=t, font=("", 16, "bold"), width=3,
                      command=lambda x=t: self._tus(x)).pack(side="left", padx=2)
        tk.Button(son, text="Boşluk", font=("", 16), width=20,
                  command=lambda: self._tus(" ")).pack(side="left", padx=6)
        tk.Button(son, text="Temizle", font=("", 14), width=8,
                  command=self._temizle).pack(side="left", padx=2)
        self._harfleri_guncelle()

    def _sayi_klavye(self, govde):
        satirlar = [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"],
                    ["Temizle", "0", "Sil"]]
        for satir in satirlar:
            c = tk.Frame(govde)
            c.pack(pady=2)
            for t in satir:
                tk.Button(c, text=t, font=("", 18, "bold"), width=8, height=2,
                          command=lambda x=t: self._sayi_tusu(x)).pack(side="left", padx=3)

    # ---- işlemler ----
    def _sayi_tusu(self, t):
        if t == "Sil":
            self._sil()
        elif t == "Temizle":
            self._temizle()
        else:
            self._rakam(t)

    def _rakam(self, r):
        if self.secili:  # seçili eski değerin üzerine yazılır
            self.deger, self.secili = "", False
        if len(self.deger) >= self.maks:
            return
        self.deger += r
        if self.mod in ("tarih", "gun") and len(self.deger) in AYIRAC and len(self.deger) < self.maks:
            self.deger += AYIRAC[len(self.deger)]
        self._guncelle()

    def _tus(self, x):
        c = tr_buyuk(x) if (self.shift and x.isalpha()) else x
        self._ekle(c)
        # Baş harf otomatik büyük: boşluktan sonra tekrar aç, harften sonra kapat
        self.shift = (c == " ")
        self._harfleri_guncelle()

    def _shift_degistir(self):
        self.shift = not self.shift
        self._harfleri_guncelle()

    def _harfleri_guncelle(self):
        for b, t in self.harf_tuslari:
            b.config(text=tr_buyuk(t) if self.shift else t)
        if self.shift_b is not None:
            self.shift_b.config(relief="sunken" if self.shift else "raised")

    def _ekle(self, c):
        if len(self.deger) < self.maks:
            self.deger += c
            self._guncelle()

    def _sil(self):
        self.secili = False
        self.deger = self.deger[:-1]
        if self.mod in ("tarih", "gun") and self.deger and self.deger[-1] in ". :":
            self.deger = self.deger[:-1]
        self._guncelle()

    def _temizle(self):
        self.deger, self.secili = "", False
        self._guncelle()

    def _guncelle(self):
        g = self.deger if len(self.deger) <= 38 else "…" + self.deger[-37:]
        self.gosterge.config(text=g + "▏", fg="black",
                             bg="#cfe8ff" if self.secili else "white")

    def _hata(self, mesaj):
        self.gosterge.config(text=mesaj, fg="#b00020", bg="white")
        self.after(1600, lambda: self.winfo_exists() and self._guncelle())

    def _tamam(self):
        if self.mod == "tarih":
            try:
                datetime.strptime(self.deger, "%d.%m.%Y %H:%M")
            except ValueError:
                self._hata("Geçersiz tarih/saat (GG.AA.YYYY SS:DD)")
                return
        if self.mod == "gun" and self.deger:  # boş bırakılabilir (filtreyi temizler)
            try:
                datetime.strptime(self.deger, "%d.%m.%Y")
            except ValueError:
                self._hata("Geçersiz tarih (GG.AA.YYYY)")
                return
        self.sonuc = self.deger.strip()
        self.destroy()


def klavye_iste(ana, baslik, baslangic="", mod="metin"):
    """Klavyeyi açar, yazılan metni döndürür (iptalde None). Modal pencerelerin
    üstünden açılınca önceki pencerenin 'grab'ini geri verir."""
    onceki = ana.grab_current()
    d = EkranKlavyesi(ana, baslik, baslangic, mod)
    ana.wait_window(d)
    if onceki is not None:
        try:
            onceki.grab_set()
        except tk.TclError:
            pass
    return d.sonuc


def dokunmatik(entry, var, baslik, mod="metin"):
    """Alana dokununca ekran klavyesi açılır. Fiziksel klavye de çalışmaya devam eder."""
    def ac(_olay=None):
        if str(entry.cget("state")) == "disabled":
            return "break"
        s = klavye_iste(entry.winfo_toplevel(), baslik, var.get(), mod)
        if s is not None:
            var.set(s)
        return "break"
    entry.bind("<Button-1>", ac)