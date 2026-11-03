"""Acil durum PIN sıfırlama aracı (programı kuran kişi için).

PIN'i 1234'e döndürür. Ürünlere, ayarlara ve etiket kayıtlarına DOKUNMAZ.
Kullanım:  python3 pin_sifirla.py            (varsayılan veritabanı)
           python3 pin_sifirla.py yol/etiketler.db
"""
import sys
from pathlib import Path

import db


def main():
    yol = Path(sys.argv[1]) if len(sys.argv) > 1 else db.varsayilan_yol()
    print(f"Veritabanı: {yol}")
    if not yol.exists():
        print("Bu yolda veritabanı bulunamadı, işlem yapılmadı.")
        return
    if input("PIN 1234'e sıfırlanacak. Devam için EVET yazın: ").strip() != "EVET":
        print("İptal edildi.")
        return
    conn = db.baglan(yol)
    db.pin_sifirla_varsayilan(conn)
    print("Tamam. PIN şimdi 1234. Yönetim ekranından hemen değiştirin.")


if __name__ == "__main__":
    main()