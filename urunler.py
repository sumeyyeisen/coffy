"""Ürün listesi: raf ömrü tablosundaki 'Açılmış & Çözdürülmüş Ürün' sütunundan.

Alanlar: (ad, kategori, süre değeri, birim, saklama, uyarı)
birim: "saat" | "gun" | "ay"   (1 ay = 30 gün)
saklama: "dolap" (+4 Dolap) | "ortam" (Ortam Sıcaklığı)
Sütunda sadece "SKT" yazan ürünler listeye alınmadı:
Cheddar Peyniri, Yoğurt Sos, Sprey Krema, Bal, Çay.
"""

D, O = "dolap", "ortam"
SM, EK, KP, TA, SB, SU, SO, KT = (
    "Sandviç Malzemeleri", "Ekmek ve Sandviçler", "Kruvasan ve Poğaçalar",
    "Tatlılar", "Soğuklar & Bubble", "Süt Ürünleri", "Soslar", "Kahve Toz Şurup",
)

URUNLER = [
    # Sandviç Malzemeleri
    ("Beyaz Peynir", SM, 5, "gun", D, ""),
    ("Kaşar Peynir", SM, 5, "gun", D, ""),
    ("Hindi Füme", SM, 2, "gun", D, ""),
    ("Kremalı Pesto Sos", SM, 30, "gun", D, ""),
    ("Suda Mozzarella", SM, 2, "gun", D, ""),
    ("Siyah Zeytin Ezmesi", SM, 14, "gun", D, ""),
    ("Sucuk", SM, 3, "gun", D, ""),
    ("Kuru Domates", SM, 20, "gun", D, ""),
    # Ekmek ve Sandviçler
    ("Ekmek", EK, 14, "gun", D, ""),
    ("Rustik Baget Esmer", EK, 24, "saat", D, "Pişirildikten sonra"),
    ("Susamlı Çörekotlu Simit", EK, 24, "saat", D, ""),
    ("Kaşarlı ve Zeytin Ezmeli Simit Sandviç", EK, 24, "saat", D, ""),
    ("Sıcak Karışık Sandviç", EK, 24, "saat", D, ""),
    ("Sıcak Peynirli Sandviç", EK, 24, "saat", D, ""),
    ("Sıcak Hindi Fümeli Sandviç", EK, 24, "saat", D, ""),
    ("Beyaz Peynirli Kuru Domatesli Rustik Baget", EK, 24, "saat", D, ""),
    ("Hindi Fümeli ve Kuru Domatesli Rustik Baget", EK, 24, "saat", D, ""),
    ("Füme Etli (Roastbeef) Bagel", EK, 48, "saat", D, ""),
    ("Hindi Jambonlu Peynirli Bagel", EK, 48, "saat", D, ""),
    ("Haşhaşlı Üç Peynirli Bagel", EK, 48, "saat", D, ""),
    ("İsli Peynirli, Köri Soslu Tavuklu Sandviç", EK, 48, "saat", D, ""),
    # Kruvasan ve Poğaçalar
    ("Tereyağlı Kruvasan", KP, 24, "saat", O, ""),
    ("Dereotlu Poğaça", KP, 24, "saat", O, ""),
    ("Fındık Kremalı Kruvasan", KP, 24, "saat", O, ""),
    ("Zeytinli Açma", KP, 24, "saat", O, ""),
    ("Çikolata Dolgulu Kruvasan", KP, 24, "saat", O, ""),
    # Tatlılar
    ("Sufle", TA, 7, "gun", D, ""),
    ("Frambuazlı Cheesecake", TA, 48, "saat", D, ""),
    ("Limonlu Cheesecake", TA, 48, "saat", D, ""),
    ("Kremalı Havuç Dilim Kek", TA, 48, "saat", D, ""),
    ("Mozaik Dilim Kek", TA, 48, "saat", O, ""),
    ("İspanyol Cheesecake (San Sebastian)", TA, 3, "gun", D, ""),
    ("Mozaik Pasta Üçgen Dilim", TA, 48, "saat", D, ""),
    ("Kakao Fındık Dolgulu Donut", TA, 48, "saat", D, ""),
    ("Çikolatalı Muffin", TA, 48, "saat", O, ""),
    ("Yaban Mersinli Muffin", TA, 48, "saat", O, ""),
    ("Çikolatalı Cookie (Bitter ve Beyaz Çikolatalı K.)", TA, 48, "saat", O, ""),
    ("Çikolata Parçacıklı Cookie", TA, 48, "saat", O, ""),
    ("Tiramisu", TA, 3, "gun", D, ""),
    ("Profiterollü Pasta", TA, 3, "gun", D, ""),
    ("Orman Meyveli Pasta", TA, 2, "gun", D, ""),
    ("Çikolatalı Portakallı Kek", TA, 48, "saat", O, ""),
    ("Matcha Rulo Pasta", TA, 2, "gun", D, ""),
    ("Latte Pasta", TA, 3, "gun", D, ""),
    ("Cookie Cups Caramel", TA, 2, "gun", O, ""),
    ("Cookie Cups Kakao Fındık Kremalı", TA, 2, "gun", O, ""),
    ("Chia Puding", TA, 48, "saat", D, ""),
    ("Bardak - Bitter ve Beyaz Çikolatalı Kurabiye", TA, 7, "gun", O, ""),
    ("Bardak - Çikolatalı Kurabiye", TA, 7, "gun", O, ""),
    ("Glutensiz Brownie", TA, 5, "gun", O, ""),
    # Soğuklar & Bubble
    ("Cold Brew", SB, 5, "gun", D, ""),
    ("Limonata", SB, 5, "gun", D, ""),
    ("Matcha / Süt Karışımı", SB, 24, "saat", D, ""),  # "Günlük" = 24 saat
    ("Yabanmersinli Bubble", SB, 30, "gun", D, ""),
    ("Karamel Bubble", SB, 30, "gun", D, ""),
    # Süt Ürünleri
    ("Badem Sütü", SU, 5, "gun", D, ""),
    ("Yulaf Sütü", SU, 5, "gun", D, ""),
    ("Yarım Yağlı Süt", SU, 48, "saat", D, ""),
    ("Yağsız Süt", SU, 48, "saat", D, ""),
    ("Laktozsuz Süt", SU, 48, "saat", D, ""),
    # Soslar
    ("Çikolata Sos (Sütlü Waffle Sos)", SO, 1, "ay", O, ""),
    ("Karamel Sos", SO, 1, "ay", O, ""),
    ("Mango Sos", SO, 1, "ay", O, ""),
    ("Kavun Sos", SO, 1, "ay", O, ""),
    ("Orman Meyveli Sos", SO, 1, "ay", O, ""),
    ("Antep Fıstıklı Sos", SO, 1, "ay", O, ""),
    ("Hindistan Cevizi Yağı", SO, 2, "ay", O, ""),
    ("Çilek Sos", SO, 1, "ay", O, ""),
    ("Süt Reçelli Sos (Condensed Milk)", SO, 1, "ay", O, ""),
    # Kahve Toz Şurup
    ("Çekirdek Kahveler", KT, 1, "ay", O, ""),
    ("Şubede Öğütülen Çekirdek Kahveler", KT, 1, "gun", O, ""),
    ("Şuruplar", KT, 3, "ay", O, ""),
    ("Türk Kahvesi", KT, 1, "ay", O, ""),
    ("Tozlar", KT, 6, "ay", O, ""),
    ("Matcha Tozu", KT, 1, "ay", O, ""),
]
