"""Yazıcı katmanı: etiket resmini Bixolon SRP-S300'e (ESC/POS) gönderir.

Yöntem (varsayılan "raw"): resim ESC/POS "GS v 0" bitmap komutuna çevrilir ve Windows
yazdırma kuyruğuna (spooler) RAW olarak verilir. USB'ye doğrudan erişim yoktur; RobotPOS ile
aynı kuyruğu kullandığımız için çakışma olmaz.
Yedek yöntem ("gdi"): RAW çalışmazsa resim sürücü üzerinden normal Windows baskısı olarak gider.

Ayarlar kodu değiştirmeden %APPDATA%\\CoffySKT\\yazici.json dosyasından değiştirilir
(dosya ilk kullanımda varsayılanlarla otomatik oluşur). Değerler test baskısıyla doğrulanır.
"""
import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from PIL import Image

import db

BELGE_ADI = "Coffy SKT Etiket"
BANT_SATIR = 256          # bitmap, bu kadar satırlık parçalar hâlinde gönderilir


class YaziciHatasi(Exception):
    """Kullanıcıya gösterilebilecek, anlaşılır yazıcı hatası."""


@dataclass
class YaziciAyar:
    yazici_adi: str = ""        # boşsa adında "SRP" geçen yazıcı aranır ("HESAP" yazıcısına asla basılmaz)
    yontem: str = "raw"         # raw | gdi
    kafa_nokta: int = 384       # yazıcının tek satırda basabildiği nokta sayısı (58 mm için 384, 80 mm için 576)
    sol_ofset_nokta: int | None = None   # etiketin kafa üzerindeki yatay konumu; None = ortala
    kesim: str = "tam"          # tam | kismi | yok
    kesim_oncesi_besleme: int = 0        # kesimden önce kâğıt ilerletme (nokta, 0-255); kesici bıçak kafanın altındadır
    kopya: int = 1


AYAR_ADLARI = {f.name for f in fields(YaziciAyar)}


def ayar_yolu() -> Path:
    return db.varsayilan_yol().parent / "yazici.json"


def ayar_oku(yol: Path | None = None) -> YaziciAyar:
    """Ayar dosyasını okur; yoksa varsayılanlarla oluşturur. Bozuksa anlaşılır hata verir."""
    yol = yol or ayar_yolu()
    if not yol.is_file():
        ayar = YaziciAyar()
        try:
            yol.write_text(json.dumps(asdict(ayar), indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
        return ayar
    try:
        ham = json.loads(yol.read_text(encoding="utf-8"))
        bilinmeyen = set(ham) - AYAR_ADLARI
        if bilinmeyen:
            raise ValueError(f"bilinmeyen ayar: {', '.join(sorted(bilinmeyen))}")
        ayar = YaziciAyar(**ham)
    except (ValueError, TypeError, OSError) as e:
        raise YaziciHatasi(f"Yazıcı ayar dosyası okunamadı ({yol}): {e}") from e
    _dogrula(ayar)
    return ayar


def _dogrula(a: YaziciAyar):
    if a.yontem not in ("raw", "gdi"):
        raise YaziciHatasi("yazici.json: 'yontem' raw ya da gdi olmalı.")
    if a.kesim not in ("tam", "kismi", "yok"):
        raise YaziciHatasi("yazici.json: 'kesim' tam, kismi ya da yok olmalı.")
    if not 8 <= a.kafa_nokta <= 1024:
        raise YaziciHatasi("yazici.json: 'kafa_nokta' 8-1024 arasında olmalı.")
    if not 0 <= a.kesim_oncesi_besleme <= 255:
        raise YaziciHatasi("yazici.json: 'kesim_oncesi_besleme' 0-255 arasında olmalı.")
    if not 1 <= a.kopya <= 5:
        raise YaziciHatasi("yazici.json: 'kopya' 1-5 arasında olmalı.")


# ---------- ESC/POS üretimi (Windows'tan bağımsız, Linux'ta test edilebilir) ----------

def _kafaya_sigdir(img: Image.Image, ayar: YaziciAyar) -> Image.Image:
    """Etiketi kafa genişliğindeki beyaz bir tuvale yerleştirir (taşan beyaz kenar kırpılır)."""
    g = img.convert("L").point(lambda p: 255 if p >= 160 else 0)
    kafa = (ayar.kafa_nokta + 7) // 8 * 8
    x = ayar.sol_ofset_nokta if ayar.sol_ofset_nokta is not None else (kafa - g.width) // 2
    tuval = Image.new("L", (kafa, g.height), 255)
    tuval.paste(g, (x, 0))
    return tuval


def esc_pos_uret(img: Image.Image, ayar: YaziciAyar) -> bytes:
    """Resmi ESC/POS komut dizisine çevirir: ESC @ + bitmap (bantlar) + besleme + kesim."""
    tuval = _kafaya_sigdir(img, ayar)
    w, h = tuval.size
    bytes_satir = w // 8
    # Pillow'da 1 bit: 1=beyaz. ESC/POS'ta 1=siyah. Bu yüzden ters çevrilir.
    ters = tuval.point(lambda p: 0 if p >= 160 else 255).convert("1")
    ham = ters.tobytes()
    veri = bytearray(b"\x1b@")                      # ESC @ : yazıcıyı sıfırla
    for ust in range(0, h, BANT_SATIR):
        satir = min(BANT_SATIR, h - ust)
        veri += b"\x1dv0\x00"                       # GS v 0, m=0 (normal)
        veri += bytes([bytes_satir & 255, bytes_satir >> 8, satir & 255, satir >> 8])
        veri += ham[ust * bytes_satir:(ust + satir) * bytes_satir]
    if ayar.kesim != "yok":
        if ayar.kesim_oncesi_besleme:
            veri += b"\x1bJ" + bytes([ayar.kesim_oncesi_besleme])   # ESC J n : n nokta ilerlet
        veri += b"\x1dV" + (b"\x00" if ayar.kesim == "tam" else b"\x01")   # GS V 0/1
    return bytes(veri)


def esc_pos_coz(veri: bytes) -> Image.Image:
    """esc_pos_uret çıktısını tekrar resme çevirir (yalnızca testler / doğrulama için)."""
    i, bantlar, genislik = 2, [], None
    assert veri[:2] == b"\x1b@"
    while veri[i:i + 4] == b"\x1dv0\x00":
        bs = veri[i + 4] | veri[i + 5] << 8
        sat = veri[i + 6] | veri[i + 7] << 8
        i += 8
        blok = veri[i:i + bs * sat]
        i += bs * sat
        genislik = bs * 8
        bantlar.append(Image.frombytes("1", (genislik, sat), blok))
    yuk = sum(b.height for b in bantlar)
    sonuc = Image.new("1", (genislik, yuk), 0)
    y = 0
    for b in bantlar:
        sonuc.paste(b, (0, y))
        y += b.height
    return sonuc.point(lambda p: 0 if p else 255).convert("1")   # 1=siyah -> Pillow'un 1=beyaz'ına


# ---------- Windows yazıcı erişimi ----------

def _win32():
    try:
        import win32print
        return win32print
    except ImportError as e:
        raise YaziciHatasi("Yazıcı modülü (pywin32) yüklü değil. Bu özellik yalnızca "
                           "kasa bilgisayarındaki Windows'ta çalışır.") from e


def yazicilari_listele() -> list[str]:
    wp = _win32()
    return [p[2] for p in wp.EnumPrinters(wp.PRINTER_ENUM_LOCAL | wp.PRINTER_ENUM_CONNECTIONS)]


def yazici_bul(ayar: YaziciAyar) -> str:
    """Ayardaki adı doğrular; boşsa adında 'SRP' geçen yazıcıyı seçer. Varsayılan yazıcıya GÜVENMEZ."""
    liste = yazicilari_listele()
    if ayar.yazici_adi:
        for ad in liste:
            if ad.lower() == ayar.yazici_adi.lower():
                return ad
        raise YaziciHatasi(f"'{ayar.yazici_adi}' adlı yazıcı bulunamadı.\n"
                           f"Windows'taki yazıcılar: {', '.join(liste) or '(yok)'}")
    adaylar = [ad for ad in liste if "srp" in ad.lower() or "bixolon" in ad.lower()]
    if len(adaylar) == 1:
        return adaylar[0]
    if not adaylar:
        raise YaziciHatasi("Etiket yazıcısı (Bixolon) bulunamadı. Yazıcının USB kablosunu, gücünü ve "
                           f"Windows'ta görünüp görünmediğini kontrol edin.\nBulunanlar: {', '.join(liste) or '(yok)'}")
    raise YaziciHatasi("Birden fazla Bixolon yazıcısı var; yazici.json içindeki 'yazici_adi' alanına "
                       f"doğru adı yazın: {', '.join(adaylar)}")


def _hazir_mi(wp, ad: str):
    """Yazıcı çevrimdışı / kâğıt bitti / kapak açık gibi durumları yakalar."""
    h = wp.OpenPrinter(ad)
    try:
        bilgi = wp.GetPrinter(h, 2)
    finally:
        wp.ClosePrinter(h)
    durum = bilgi["Status"]
    if bilgi["Attributes"] & wp.PRINTER_ATTRIBUTE_WORK_OFFLINE:
        raise YaziciHatasi("Yazıcı çevrimdışı görünüyor. Gücünü ve USB kablosunu kontrol edin.")
    sorunlar = [(wp.PRINTER_STATUS_PAPER_OUT, "Kâğıt bitti."),
                (wp.PRINTER_STATUS_DOOR_OPEN, "Yazıcının kapağı açık."),
                (wp.PRINTER_STATUS_PAPER_JAM, "Kâğıt sıkıştı."),
                (wp.PRINTER_STATUS_OFFLINE, "Yazıcı çevrimdışı."),
                (wp.PRINTER_STATUS_ERROR, "Yazıcı hata veriyor.")]
    for bit, mesaj in sorunlar:
        if durum & bit:
            raise YaziciHatasi(mesaj)


def _raw_gonder(ad: str, veri: bytes):
    wp = _win32()
    try:
        h = wp.OpenPrinter(ad)
    except Exception as e:
        raise YaziciHatasi(f"Yazıcıya bağlanılamadı: {e}") from e
    try:
        wp.StartDocPrinter(h, 1, (BELGE_ADI, None, "RAW"))
        try:
            wp.StartPagePrinter(h)
            wp.WritePrinter(h, veri)
            wp.EndPagePrinter(h)
        finally:
            wp.EndDocPrinter(h)
    except Exception as e:
        raise YaziciHatasi(f"Yazdırma başarısız: {e}") from e
    finally:
        wp.ClosePrinter(h)


def _gdi_gonder(ad: str, img: Image.Image, ayar: YaziciAyar):
    """Yedek yöntem: sürücü üzerinden normal baskı. (Kasada denenmeden güvenilmemeli.)"""
    try:
        import win32con
        import win32ui
        from PIL import ImageWin
    except ImportError as e:
        raise YaziciHatasi("GDI yöntemi için pywin32 gerekli.") from e
    try:
        dc = win32ui.CreateDC()
        dc.CreatePrinterDC(ad)
        dc.StartDoc(BELGE_ADI)
        dc.StartPage()
        yatay = dc.GetDeviceCaps(win32con.HORZRES)
        yuk = round(img.height * yatay / img.width)
        ImageWin.Dib(img.convert("RGB")).draw(dc.GetHandleOutput(), (0, 0, yatay, yuk))
        dc.EndPage()
        dc.EndDoc()
        dc.DeleteDC()
    except Exception as e:
        raise YaziciHatasi(f"Yazdırma başarısız (GDI): {e}") from e


def resim_yazdir(img: Image.Image, ayar: YaziciAyar | None = None) -> None:
    """Hazır etiket resmini yazıcıya gönderir (etiket ve test baskısı bunu kullanır)."""
    ayar = ayar or ayar_oku()
    _dogrula(ayar)
    ad = yazici_bul(ayar)
    _hazir_mi(_win32(), ad)
    veri = esc_pos_uret(img, ayar) if ayar.yontem == "raw" else None
    for _ in range(ayar.kopya):
        if ayar.yontem == "raw":
            _raw_gonder(ad, veri)
        else:
            _gdi_gonder(ad, img, ayar)


def yazdir(veri: dict) -> None:
    """Etiket verisini çizer ve basar. Hata olursa YaziciHatasi (anlaşılır Türkçe mesajla) fırlatır."""
    import etiket
    resim_yazdir(etiket.etiket_ciz(veri))