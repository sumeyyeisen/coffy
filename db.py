"""Veritabanı katmanı (SQLite, yerel dosya): ürünler, kategoriler, etiket kayıtları, ayarlar."""
import hashlib
import os
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

from skt import Urun
from urunler import URUNLER

FMT = "%Y-%m-%d %H:%M"
BIRIMLER = ("saat", "gun", "ay")
SAKLAMALAR = ("dolap", "ortam")
VARSAYILAN_PIN = "1234"


class YonetimHatasi(ValueError):
    """Kullanıcıya gösterilebilecek doğrulama hatası."""


def varsayilan_yol() -> Path:
    """Kalıcı konum: Windows'ta %APPDATA%\\CoffySKT, Linux'ta ~/.local/share/CoffySKT."""
    if os.name == "nt":
        taban = Path(os.environ.get("APPDATA", str(Path.home())))
    else:
        taban = Path.home() / ".local" / "share"
    klasor = taban / "CoffySKT"
    klasor.mkdir(parents=True, exist_ok=True)
    return klasor / "etiketler.db"


SEMA = """
CREATE TABLE IF NOT EXISTS kategori (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS urun (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ad TEXT NOT NULL UNIQUE,
    kategori_id INTEGER NOT NULL REFERENCES kategori(id),
    sure_deger INTEGER NOT NULL,
    sure_birim TEXT NOT NULL,
    saklama TEXT NOT NULL,
    uyari TEXT NOT NULL DEFAULT '',
    aktif INTEGER NOT NULL DEFAULT 1,
    silindi INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS etiket_kaydi (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    urun_ad      TEXT NOT NULL,
    acilis       TEXT NOT NULL,
    skt          TEXT NOT NULL,
    saklama      TEXT NOT NULL,
    uyari        TEXT NOT NULL DEFAULT '',
    manuel       INTEGER NOT NULL DEFAULT 0,
    basim_zamani TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ayar (
    anahtar TEXT PRIMARY KEY,
    deger TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS degisiklik (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman TEXT NOT NULL,
    urun_ad TEXT NOT NULL,
    alan TEXT NOT NULL,
    eski TEXT NOT NULL,
    yeni TEXT NOT NULL
);
"""


def baglan(yol=None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(yol if yol is not None else varsayilan_yol()))
    conn.row_factory = sqlite3.Row
    conn.executescript(SEMA)
    _gocler(conn)
    _ilk_kurulum(conn)
    return conn


def _gocler(conn):
    """Eski sürümle oluşturulmuş veritabanlarını yeni şemaya taşır (veri kaybı olmaz)."""
    kolonlar = {r["name"] for r in conn.execute("PRAGMA table_info(urun)")}
    if "silindi" not in kolonlar:
        conn.execute("ALTER TABLE urun ADD COLUMN silindi INTEGER NOT NULL DEFAULT 0")
    conn.commit()


def _ilk_kurulum(conn):
    """İlk açılışta ürün listesini yükler ve varsayılan PIN'i atar."""
    if conn.execute("SELECT COUNT(*) FROM urun").fetchone()[0] == 0:
        for ad, kat, deger, birim, saklama, uyari in URUNLER:
            conn.execute("INSERT OR IGNORE INTO kategori (ad) VALUES (?)", (kat,))
            kid = conn.execute("SELECT id FROM kategori WHERE ad=?", (kat,)).fetchone()[0]
            conn.execute(
                "INSERT INTO urun (ad, kategori_id, sure_deger, sure_birim, saklama, uyari)"
                " VALUES (?, ?, ?, ?, ?, ?)", (ad, kid, deger, birim, saklama, uyari))
    if _ayar_oku(conn, "pin_hash") is None:
        _pin_yaz(conn, VARSAYILAN_PIN)
        _ayar_yaz(conn, "pin_varsayilan", "1")
    conn.commit()


# ---------- ayarlar / PIN ----------

def _ayar_oku(conn, anahtar):
    s = conn.execute("SELECT deger FROM ayar WHERE anahtar=?", (anahtar,)).fetchone()
    return s["deger"] if s else None


def _ayar_yaz(conn, anahtar, deger):
    conn.execute("INSERT INTO ayar (anahtar, deger) VALUES (?, ?)"
                 " ON CONFLICT(anahtar) DO UPDATE SET deger=excluded.deger", (anahtar, deger))


def _hash(pin: str, tuz: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", pin.encode(), tuz, 100_000).hex()


def _pin_yaz(conn, pin):
    tuz = secrets.token_bytes(16)
    _ayar_yaz(conn, "pin_tuz", tuz.hex())
    _ayar_yaz(conn, "pin_hash", _hash(pin, tuz))


def pin_dogru(conn, pin: str) -> bool:
    tuz = bytes.fromhex(_ayar_oku(conn, "pin_tuz"))
    return secrets.compare_digest(_hash(pin, tuz), _ayar_oku(conn, "pin_hash"))


def pin_varsayilan_mi(conn) -> bool:
    return _ayar_oku(conn, "pin_varsayilan") == "1"


def _pin_kontrol(yeni: str):
    if not (yeni.isdigit() and 4 <= len(yeni) <= 8):
        raise YonetimHatasi("PIN 4 ile 8 arasında rakamdan oluşmalı.")
    if yeni == VARSAYILAN_PIN:
        raise YonetimHatasi("Varsayılan PIN tekrar kullanılamaz.")


def _pin_ata(conn, yeni: str) -> str:
    _pin_kontrol(yeni)
    _pin_yaz(conn, yeni)
    _ayar_yaz(conn, "pin_varsayilan", "0")
    conn.commit()
    return kurtarma_kodu_uret(conn)


def pin_degistir(conn, yeni: str) -> str:
    """PIN'i değiştirir ve YENİ kurtarma kodunu döndürür (eski kod geçersiz olur).
    Mevcut PIN ile aynı PIN kabul edilmez."""
    _pin_kontrol(yeni)
    if pin_dogru(conn, yeni):
        raise YonetimHatasi("Yeni PIN, mevcut PIN ile aynı olamaz.")
    return _pin_ata(conn, yeni)


def kurtarma_kodu_uret(conn) -> str:
    """8 haneli kurtarma kodu üretir. Kod saklanmaz (sadece hash'i), bir kez gösterilir."""
    kod = "".join(secrets.choice("0123456789") for _ in range(8))
    tuz = secrets.token_bytes(16)
    _ayar_yaz(conn, "kurtarma_tuz", tuz.hex())
    _ayar_yaz(conn, "kurtarma_hash", _hash(kod, tuz))
    conn.commit()
    return kod


def kurtarma_kodu_dogru(conn, kod: str) -> bool:
    h, t = _ayar_oku(conn, "kurtarma_hash"), _ayar_oku(conn, "kurtarma_tuz")
    if h is None or t is None:
        return False
    return secrets.compare_digest(_hash(kod, bytes.fromhex(t)), h)


def pin_kurtarma_ile_sifirla(conn, kod: str, yeni: str) -> str:
    """Unutulan PIN için: doğru kurtarma koduyla yeni PIN belirler, yeni kod döndürür."""
    if not kurtarma_kodu_dogru(conn, kod):
        raise YonetimHatasi("Kurtarma kodu yanlış.")
    # Mevcut PIN'i bilmiyor (unutmuş), bu yüzden "aynı PIN" kontrolü yapılmaz.
    return _pin_ata(conn, yeni)


def pin_sifirla_varsayilan(conn):
    """Acil durum (pin_sifirla.py aracı): PIN'i 1234'e döndürür, ürünlere dokunmaz."""
    _pin_yaz(conn, VARSAYILAN_PIN)
    _ayar_yaz(conn, "pin_varsayilan", "1")
    conn.execute("DELETE FROM ayar WHERE anahtar IN ('kurtarma_tuz', 'kurtarma_hash')")
    conn.commit()


# ---------- kategori / ürün yönetimi ----------

def _log(conn, urun_ad, alan, eski, yeni):
    conn.execute("INSERT INTO degisiklik (zaman, urun_ad, alan, eski, yeni) VALUES (?,?,?,?,?)",
                 (datetime.now().strftime(FMT), urun_ad, alan, str(eski), str(yeni)))


def kategoriler_getir(conn) -> list[tuple[int, str]]:
    return [(r["id"], r["ad"]) for r in conn.execute("SELECT id, ad FROM kategori ORDER BY id")]


def kategori_ekle(conn, ad: str) -> int:
    ad = ad.strip()
    if not ad:
        raise YonetimHatasi("Kategori adı boş olamaz.")
    try:
        cur = conn.execute("INSERT INTO kategori (ad) VALUES (?)", (ad,))
    except sqlite3.IntegrityError:
        raise YonetimHatasi("Bu isimde bir kategori zaten var.")
    conn.commit()
    return cur.lastrowid


def _dogrula(ad, kategori_id, sure_deger, sure_birim, saklama):
    if not ad.strip():
        raise YonetimHatasi("Ürün adı boş olamaz.")
    if kategori_id is None:
        raise YonetimHatasi("Kategori seçin.")
    if not isinstance(sure_deger, int) or sure_deger < 1:
        raise YonetimHatasi("Süre 1 veya daha büyük bir tam sayı olmalı.")
    if sure_birim not in BIRIMLER:
        raise YonetimHatasi("Geçersiz süre birimi.")
    if saklama not in SAKLAMALAR:
        raise YonetimHatasi("Geçersiz saklama koşulu.")


def _urun_satiri(r) -> Urun:
    return Urun(ad=r["ad"], kategori=r["kategori"], sure_deger=r["sure_deger"],
                sure_birim=r["sure_birim"], saklama=r["saklama"], uyari=r["uyari"],
                id=r["id"], aktif=bool(r["aktif"]))


_URUN_SORGU = ("SELECT u.*, k.ad AS kategori FROM urun u"
               " JOIN kategori k ON k.id = u.kategori_id")


def urunleri_getir(conn, sadece_aktif: bool = True) -> list[Urun]:
    """Silinmişler hiçbir zaman dönmez. sadece_aktif=False: pasifler de gelir."""
    kosul = " WHERE u.silindi=0" + (" AND u.aktif=1" if sadece_aktif else "")
    return [_urun_satiri(r) for r in conn.execute(_URUN_SORGU + kosul + " ORDER BY k.id, u.id")]


def silinen_urunler(conn) -> list[Urun]:
    return [_urun_satiri(r) for r in conn.execute(
        _URUN_SORGU + " WHERE u.silindi=1 ORDER BY k.id, u.id")]


def _cakisma_hatasi(conn, ad):
    r = conn.execute("SELECT silindi FROM urun WHERE ad=?", (ad,)).fetchone()
    if r and r["silindi"]:
        return YonetimHatasi("Bu isimde silinmiş bir ürün var. 'Silinenler' bölümünden geri getirebilirsiniz.")
    return YonetimHatasi("Bu isimde bir ürün zaten var.")


def urun_sil(conn, urun_id):
    """Ürünü silinenlere taşır (geri getirilebilir). Etiket kayıtları etkilenmez."""
    r = conn.execute("SELECT ad, silindi FROM urun WHERE id=?", (urun_id,)).fetchone()
    if r is None or r["silindi"]:
        raise YonetimHatasi("Ürün bulunamadı.")
    conn.execute("UPDATE urun SET silindi=1 WHERE id=?", (urun_id,))
    _log(conn, r["ad"], "durum", "mevcut", "silindi")
    conn.commit()


def urun_geri_getir(conn, urun_id):
    r = conn.execute("SELECT ad, silindi FROM urun WHERE id=?", (urun_id,)).fetchone()
    if r is None or not r["silindi"]:
        raise YonetimHatasi("Bu ürün silinenler arasında değil.")
    conn.execute("UPDATE urun SET silindi=0 WHERE id=?", (urun_id,))
    _log(conn, r["ad"], "durum", "silindi", "geri getirildi")
    conn.commit()


def urun_kalici_sil(conn, urun_id):
    """GERİ DÖNÜŞÜ YOK. Sadece zaten silinenler arasındaki ürün kalıcı silinebilir."""
    r = conn.execute("SELECT ad, silindi FROM urun WHERE id=?", (urun_id,)).fetchone()
    if r is None or not r["silindi"]:
        raise YonetimHatasi("Sadece silinenler arasındaki ürünler kalıcı silinebilir.")
    conn.execute("DELETE FROM urun WHERE id=?", (urun_id,))
    _log(conn, r["ad"], "durum", "silindi", "kalıcı silindi")
    conn.commit()


def urun_ekle(conn, ad, kategori_id, sure_deger, sure_birim, saklama, uyari="") -> int:
    ad = ad.strip()
    _dogrula(ad, kategori_id, sure_deger, sure_birim, saklama)
    try:
        cur = conn.execute(
            "INSERT INTO urun (ad, kategori_id, sure_deger, sure_birim, saklama, uyari)"
            " VALUES (?,?,?,?,?,?)", (ad, kategori_id, sure_deger, sure_birim, saklama, uyari.strip()))
    except sqlite3.IntegrityError:
        raise _cakisma_hatasi(conn, ad)
    _log(conn, ad, "ürün eklendi", "-", f"{sure_deger} {sure_birim}, {saklama}")
    conn.commit()
    return cur.lastrowid


def urun_guncelle(conn, urun_id, ad, kategori_id, sure_deger, sure_birim, saklama, uyari=""):
    ad, uyari = ad.strip(), uyari.strip()
    _dogrula(ad, kategori_id, sure_deger, sure_birim, saklama)
    eski = conn.execute(_URUN_SORGU + " WHERE u.id=?", (urun_id,)).fetchone()
    if eski is None:
        raise YonetimHatasi("Ürün bulunamadı.")
    try:
        conn.execute(
            "UPDATE urun SET ad=?, kategori_id=?, sure_deger=?, sure_birim=?, saklama=?, uyari=?"
            " WHERE id=?", (ad, kategori_id, sure_deger, sure_birim, saklama, uyari, urun_id))
    except sqlite3.IntegrityError:
        raise _cakisma_hatasi(conn, ad)
    yeni_kat = conn.execute("SELECT ad FROM kategori WHERE id=?", (kategori_id,)).fetchone()["ad"]
    for alan, e, y in (("ad", eski["ad"], ad), ("kategori", eski["kategori"], yeni_kat),
                       ("süre", eski["sure_deger"], sure_deger), ("birim", eski["sure_birim"], sure_birim),
                       ("saklama", eski["saklama"], saklama), ("uyarı", eski["uyari"], uyari)):
        if e != y:
            _log(conn, ad, alan, e, y)
    conn.commit()


def urun_aktif_yap(conn, urun_id, aktif: bool):
    r = conn.execute("SELECT ad FROM urun WHERE id=?", (urun_id,)).fetchone()
    if r is None:
        raise YonetimHatasi("Ürün bulunamadı.")
    conn.execute("UPDATE urun SET aktif=? WHERE id=?", (int(aktif), urun_id))
    _log(conn, r["ad"], "durum", "pasif" if aktif else "aktif", "aktif" if aktif else "pasif")
    conn.commit()


def degisiklik_gecmisi(conn, limit: int = 100) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM degisiklik ORDER BY id DESC LIMIT ?", (limit,)).fetchall()


def yedek_al(conn, hedef_yol):
    hedef = sqlite3.connect(str(hedef_yol))
    try:
        conn.backup(hedef)
    finally:
        hedef.close()


# ---------- etiket kayıtları ----------

def kaydet(conn: sqlite3.Connection, veri: dict) -> int:
    cur = conn.execute(
        "INSERT INTO etiket_kaydi (urun_ad, acilis, skt, saklama, uyari, manuel, basim_zamani)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (veri["ad"], veri["acilis"].strftime(FMT), veri["skt"].strftime(FMT),
         veri["saklama"], veri["uyari"], int(veri["manuel"]),
         datetime.now().strftime(FMT)),
    )
    conn.commit()
    return cur.lastrowid


def _veriye_cevir(satir: sqlite3.Row) -> dict:
    return {
        "id": satir["id"],
        "ad": satir["urun_ad"],
        "acilis": datetime.strptime(satir["acilis"], FMT),
        "skt": datetime.strptime(satir["skt"], FMT),
        "saklama": satir["saklama"],
        "uyari": satir["uyari"],
        "manuel": bool(satir["manuel"]),
        "basim_zamani": datetime.strptime(satir["basim_zamani"], FMT),
    }


def son_kayitlar(conn: sqlite3.Connection, limit: int = 30) -> list[dict]:
    satirlar = conn.execute(
        "SELECT * FROM etiket_kaydi ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    return [_veriye_cevir(s) for s in satirlar]


# ---------- değişiklik geçmişi: arama / filtre ----------

_KATLA = str.maketrans({"İ": "i", "I": "i", "ı": "i", "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g",
                        "ö": "o", "Ö": "o", "ş": "s", "Ş": "s", "ü": "u", "Ü": "u"})


def katla(metin: str) -> str:
    """Arama için Türkçe harfleri sadeleştirir: 'İpek' ile 'ipek' (ya da 'Şurup' ile 'surup') eşleşir."""
    return metin.translate(_KATLA).lower()


GECMIS_TURLERI = {
    "Tümü": None,
    "Süre değişiklikleri": "alan IN ('süre', 'birim')",
    "Silme / geri getirme": "alan = 'durum' AND yeni IN ('silindi', 'geri getirildi', 'kalıcı silindi')",
    "Pasife alma / aktif etme": "alan = 'durum' AND yeni IN ('aktif', 'pasif')",
    "Ürün ekleme": "alan = 'ürün eklendi'",
    "Ad / kategori / saklama / uyarı": "alan IN ('ad', 'kategori', 'saklama', 'uyarı')",
    "Yedek işlemleri": "alan = 'yedek'",
    "Kayıt temizliği / saklama süresi": "alan IN ('temizlik', 'saklama süresi')",
}


def degisiklik_ara(conn, metin: str = "", baslangic: date | None = None, bitis: date | None = None,
                   tur: str = "Tümü", limit: int = 500):
    """Filtrelenmiş geçmiş. (satırlar, daha_fazla_var) döndürür. Hiçbir kayıt silinmez."""
    kosullar, par = [], []
    if baslangic:
        kosullar.append("zaman >= ?")
        par.append(f"{baslangic:%Y-%m-%d} 00:00")
    if bitis:
        kosullar.append("zaman <= ?")
        par.append(f"{bitis:%Y-%m-%d} 23:59")
    if GECMIS_TURLERI.get(tur):
        kosullar.append(GECMIS_TURLERI[tur])
    sql = "SELECT * FROM degisiklik" + (" WHERE " + " AND ".join(kosullar) if kosullar else "") + " ORDER BY id DESC"
    satirlar = conn.execute(sql, par).fetchall()
    aranan = katla(metin.strip())
    if aranan:
        satirlar = [r for r in satirlar if aranan in katla(r["urun_ad"])]
    return satirlar[:limit], len(satirlar) > limit


# ---------- yedekleme / geri yükleme ----------

# Yedekten geri yüklemede mevcut hâliyle korunan ayarlar (PIN + saklama süresi)
PIN_ANAHTARLARI = ("pin_tuz", "pin_hash", "pin_varsayilan", "kurtarma_tuz", "kurtarma_hash",
                   "etiket_saklama_ay")
GEREKLI_TABLOLAR = {"urun", "kategori", "etiket_kaydi"}


def yedek_klasoru() -> Path:
    k = varsayilan_yol().parent / "yedekler"
    k.mkdir(parents=True, exist_ok=True)
    return k


def _dosyaya_yedekle(conn, hedef: Path):
    """Yarım kalmış yedek dosyası bırakmamak için önce geçici dosyaya yazar."""
    gecici = hedef.with_name(hedef.name + ".tmp")
    yedek_al(conn, gecici)
    os.replace(gecici, hedef)


def otomatik_yedek(conn, klasor=None, tut: int = 7, bugun: date | None = None):
    """Bugün için yedek yoksa alır, son `tut` günlük yedeği bırakır. Alınmadıysa None döner."""
    klasor = Path(klasor) if klasor is not None else yedek_klasoru()
    klasor.mkdir(parents=True, exist_ok=True)
    bugun = bugun or datetime.now().date()
    hedef = klasor / f"otomatik_{bugun:%Y%m%d}.db"
    if hedef.exists():
        return None
    _dosyaya_yedekle(conn, hedef)
    for eski in sorted(klasor.glob("otomatik_*.db"))[:-tut]:
        eski.unlink()
    return hedef


def yedek_incele(yol) -> dict:
    """Seçilen dosyanın geçerli bir yedek olup olmadığını kontrol eder, özetini döndürür."""
    yol = Path(yol)
    if not yol.is_file():
        raise YonetimHatasi("Dosya bulunamadı.")
    try:
        c = sqlite3.connect(yol.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            tablolar = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if GEREKLI_TABLOLAR - tablolar:
                raise YonetimHatasi("Bu dosya bir Coffy yedeği değil.")
            if c.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise YonetimHatasi("Yedek dosyası bozuk.")
            return {
                "urun": c.execute("SELECT COUNT(*) FROM urun").fetchone()[0],
                "etiket": c.execute("SELECT COUNT(*) FROM etiket_kaydi").fetchone()[0],
                "tarih": datetime.fromtimestamp(yol.stat().st_mtime),
            }
        finally:
            c.close()
    except sqlite3.DatabaseError:
        raise YonetimHatasi("Seçilen dosya geçerli bir yedek değil.")


def yedekten_geri_yukle(conn, yol, onceki_klasor=None) -> Path:
    """Yedeği geri yükler. Önce mevcut durumu ayrıca yedekler (geri alınabilsin diye).
    PIN ve kurtarma kodu DEĞİŞMEZ: geri yükleme PIN'i sıfırlamanın yolu olamaz."""
    yedek_incele(yol)
    klasor = Path(onceki_klasor) if onceki_klasor is not None else yedek_klasoru()
    klasor.mkdir(parents=True, exist_ok=True)
    conn.commit()
    onceki = klasor / f"geri_yukleme_oncesi_{datetime.now():%Y%m%d_%H%M%S}.db"
    _dosyaya_yedekle(conn, onceki)
    for eski in sorted(klasor.glob("geri_yukleme_oncesi_*.db"))[:-5]:
        eski.unlink()

    korunan = {k: _ayar_oku(conn, k) for k in PIN_ANAHTARLARI}
    kaynak = sqlite3.connect(str(yol))
    try:
        kaynak.backup(conn)
    finally:
        kaynak.close()
    conn.executescript(SEMA)   # eski sürüm yedeklerde eksik tablolar varsa oluştur
    _gocler(conn)
    for k, v in korunan.items():
        if v is None:
            conn.execute("DELETE FROM ayar WHERE anahtar=?", (k,))
        else:
            _ayar_yaz(conn, k, v)
    _log(conn, "(sistem)", "yedek", "-", f"geri yüklendi: {Path(yol).name}")
    conn.commit()
    return onceki


# ---------- etiket kayıtlarının saklama süresi ----------

SAKLAMA_VARSAYILAN_AY = 12
SAKLAMA_EN_AZ_AY = 7      # en uzun raf ömrü 6 ay: daha kısa saklanırsa rafta duran ürünün kaydı silinir
SAKLAMA_EN_FAZLA_AY = 120


def etiket_saklama_ay(conn) -> int:
    v = _ayar_oku(conn, "etiket_saklama_ay")
    return int(v) if v and v.isdigit() else SAKLAMA_VARSAYILAN_AY


def etiket_saklama_ayarla(conn, ay: int):
    if not isinstance(ay, int) or not (SAKLAMA_EN_AZ_AY <= ay <= SAKLAMA_EN_FAZLA_AY):
        raise YonetimHatasi(f"Saklama süresi {SAKLAMA_EN_AZ_AY} ile {SAKLAMA_EN_FAZLA_AY} ay arasında olmalı "
                            "(en uzun raf ömrü 6 ay olduğundan daha kısası önerilmez).")
    eski = etiket_saklama_ay(conn)
    _ayar_yaz(conn, "etiket_saklama_ay", str(ay))
    if eski != ay:
        _log(conn, "(sistem)", "saklama süresi", f"{eski} ay", f"{ay} ay")
    conn.commit()


def _saklama_siniri(ay: int, bugun: datetime | None = None) -> str:
    """Bu zamandan ÖNCE basılan kayıtlar saklama süresini aşmıştır (1 ay = 30 gün)."""
    return ((bugun or datetime.now()) - timedelta(days=30 * ay)).strftime(FMT)


def silinecek_etiket_sayisi(conn, ay: int | None = None, bugun: datetime | None = None) -> int:
    ay = ay if ay is not None else etiket_saklama_ay(conn)
    return conn.execute("SELECT COUNT(*) FROM etiket_kaydi WHERE basim_zamani < ?",
                        (_saklama_siniri(ay, bugun),)).fetchone()[0]


def eski_etiketleri_temizle(conn, bugun: datetime | None = None) -> int:
    """Saklama süresinden eski etiket kayıtlarını siler, silinen sayıyı döndürür.
    Ürün değişiklik geçmişine DOKUNMAZ (o hiçbir zaman silinmez)."""
    ay = etiket_saklama_ay(conn)
    sayi = silinecek_etiket_sayisi(conn, ay, bugun)
    if sayi:
        conn.execute("DELETE FROM etiket_kaydi WHERE basim_zamani < ?", (_saklama_siniri(ay, bugun),))
        _log(conn, "(sistem)", "temizlik", "-", f"{sayi} etiket kaydı silindi ({ay} aydan eski)")
        conn.commit()
    return sayi