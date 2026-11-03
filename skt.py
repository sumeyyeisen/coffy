"""SKT hesaplama çekirdeği (yazıcıdan ve arayüzden bağımsız)."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from urunler import URUNLER

GUN_PER_AY = 30  # karar: 1 ay = 30 gün

SAKLAMA_METNI = {"dolap": "+4 Dolap", "ortam": "Ortam Sıcaklığı"}


@dataclass(frozen=True)
class Urun:
    ad: str
    kategori: str
    sure_deger: int
    sure_birim: str  # saat | gun | ay
    saklama: str     # dolap | ortam
    uyari: str = ""
    id: int | None = None
    aktif: bool = True

    def sure(self) -> timedelta:
        if self.sure_birim == "saat":
            return timedelta(hours=self.sure_deger)
        if self.sure_birim == "gun":
            return timedelta(days=self.sure_deger)
        if self.sure_birim == "ay":
            return timedelta(days=self.sure_deger * GUN_PER_AY)
        raise ValueError(f"Bilinmeyen birim: {self.sure_birim}")

    def saklama_metni(self) -> str:
        return SAKLAMA_METNI[self.saklama]


def urunleri_yukle() -> list[Urun]:
    return [Urun(*u) for u in URUNLER]


def skt_hesapla(urun: Urun, acilis: datetime | None = None) -> datetime:
    """SKT = açılış zamanı + raf ömrü. Açılış verilmezse şu an (saat:dakika dahil)."""
    if acilis is None:
        acilis = datetime.now()
    acilis = acilis.replace(second=0, microsecond=0)
    return acilis + urun.sure()


def etiket_verisi(urun: Urun, acilis: datetime | None = None,
                  skt: datetime | None = None) -> dict:
    """Etiketin içeriği. Manuel verilen açılış/SKT varsayılanı ezer."""
    acilis_z = (acilis or datetime.now()).replace(second=0, microsecond=0)
    otomatik = skt_hesapla(urun, acilis_z)
    skt_z = skt.replace(second=0, microsecond=0) if skt else otomatik
    if skt_z <= acilis_z:
        raise ValueError("SKT, açılış zamanından sonra olmalı.")
    return {
        "ad": urun.ad,
        "acilis": acilis_z,
        "skt": skt_z,
        "saklama": urun.saklama_metni(),
        "uyari": urun.uyari,
        "manuel": (acilis is not None) or (skt is not None and skt_z != otomatik),
    }