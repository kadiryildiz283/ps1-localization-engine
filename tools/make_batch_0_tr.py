"""Generate batch_0_tr.json conforming to Sevin Okyay and Kutlukhan Kutlu translations."""

import json
import re

BATCH_0_PATH = "/home/kadir/PS1-Localization-Engine/translations/batches/batch_0.json"
OUTPUT_PATH = "/home/kadir/PS1-Localization-Engine/translations/batches/batch_0_tr.json"

CUSTOM_TR = {
    # 0 - 49: Story recaps
    0: "#0#$001Ron Weasley ve ağabeyleri Fred ile George, Harry Potter'ı Privet Drive dört numaradaki sefaletten kurtardılar. Onu uçan bir arabayla kendi evleri olan Kovuk'a götürdüler; Harry burada Bayan Weasley ile tanıştı. Harry'nin şimdi tavan arasındaki gürültücü hortlağı susturması gerekiyor.",
    1: "#3#$002Tavan arasına tırmanan Harry, Bayan Weasley için gürültücü hortlağı susturmayı başardı. Harry ve Ron'un şimdi Bay Weasley'yi bulmaları gerekiyor.",
    2: "#6#$003Harry etrafa bakınırken, utangaç Ginny Weasley ve evcil Pofuduk'u ile karşılaştı. Daha sonra Arthur Weasley'nin büyü dışı hurdalarını parçalamak için Wingardium Leviosa büyüsünü kullanan Harry, gizlenmiş cüce ayıklama eldivenlerini buldu. Harry şimdi Kovuk'un bahçesindeki cüceleri ayıklamalı.",
    3: "#9#$004Bay Weasley'nin verdiği cüce ayıklama eldivenlerini kullanan Harry, Kovuk'un bahçesindeki cüceleri başarıyla ayıkladı. Harry'nin şimdi Fred Weasley'ye karşı ilk Büyücü Düellosu'na çıkması gerekiyor.",
    4: "#C#$005Büyücü düellosunda Fred Weasley'yi yenen Harry ve Ron, kaybolan Ginny Weasley'yi aramak için ayrıldılar.",
    5: "#F#$006Harry Ginny'yi buldu ve Ginny ona Hatırlatıcı'sını verdi. Harry şimdi Hogwarts'taki ikinci yılı için gereken kitapları ve diğer okul eşyalarını almak üzere, Weasley'lerle birlikte Uçuş Tozu kullanarak Diagon Yolu'na gitmeli.",
    6: "#12#$007Harry, Borgin ve Burkes'te Lucius ile Draco Malfoy'u gözetledi. Daha sonra Flourish ve Blotts'ta yeni Karanlık Sanatlara Karşı Savunma öğretmeni Gilderoy Lockhart ile tanıştı. Anlaşılmayan bir nedenden ötürü Ron ve Harry Peron Dokuz Üç Çeyrek'e geçemeyince, uçan arabayı Hogwarts'a sürmeye karar verdiler.",
    7: "#15#$008Harry ve Ron nihayet Hogwarts'a sağ salim vardılar — ya da en azından öyle sandılar! Ne yazık ki Şamarcı Söğüt'ün menziline iniş yaptılar. Harry, Ron'u Şamarcı Söğüt'ten kurtarmalı ve yoklukları fark edilmeden önce okula girmeli.",
    8: "#18#$009Şamarcı Söğüt'ten kurtulduktan sonra Harry ve Ron, Seçim Töreni'nde boş bir sandalye fark ettiler. Bu sandalye, onları yakalayıp odasına götürdükten sonra Gryffindor Ortak Odası'na gitmelerini emreden Profesör Snape'e aitti.",
    9: "#1B#$010Seçim Töreni'ni kaçırdıkları için Harry ve Ron'a Gryffindor Ortak Odası'nın bu yılki parolası söylenmemişti. Kütüphanedeki Hermione Granger'ı bulmaya gittiler. Hermione onlara yeni parolayı söyledi; Harry ve Ron'un şimdi Ortak Oda'ya dönmeleri gerekiyor.",
    10: "#1E#$011Ortak Oda'da hayranlıktan dili tutulmuş Colin Creevey ve ardından Fred ile George Weasley ile buluştuktan sonra Harry'nin bahçeye çıkıp dönemin ilk Bitkibilim dersine gitmesi gerekiyor.",
    11: "#21#$012Ortak Oda'dan ayrıldıktan sonra Harry diğer öğrencileri takip etmeli ve dönemin ilk Bitkibilim dersinin yolunu bulmalı.",
    12: "#24#$013Bitkibilim Dersine vaktinde yetişen Harry, şimdi Profesör Sprout ile yapacağı Incendio Duo büyü dersinde geçer not almak zorunda.",
    13: "#27#$014Harry ilk Bitkibilim dersinde Incendio Duo büyüsünü öğrendi ve Profesör Sprout için birkaç adamotu topladı.",
    14: "#2A#$015Harry, Oliver Wood'dan kendisini Quidditch Antrenman Sahası'ndaki idmana çağıran bir baykuş postası aldı. Harry oraya olabildiğince çabuk gitmeli.",
    15: "#2D#$016Harry, Oliver Wood ile yaptığı Quidditch Antrenmanında hünerini başarıyla kanıtladı.",
    16: "#30#$017Quidditch Antrenmanından sonra Ron, Harry'yi bir büyücü düellosuna davet etti.",
    17: '#33#$018Draco Malfoy, Hermione\'ye "pis Bulanık" deyince Ron, Malfoy\'a büyü yapmaya çalıştı; ancak asası geri tepti ve sümüklüböcek kusmaya başladı. Harry, yardım almak için Hagrid\'in Kulübesi\'ne koşan Ron\'u takip etti. Ron\'un sümüklüböcek kusmasını durdurmak için Hagrid\'i bulmalılar.',
    18: "#36#$019Hagrid'in Kulübesi'nde Harry, sümüklüböcekleri Fang'in çanağında yakalamayı başardı. Harry ve Ron, Hermione ile buluşmak için Gryffindor Ortak Odası'na dönmek zorundalar.",
    19: "#39#$020Ortak Oda'da Ron ve Hermione ile buluştuktan sonra üç arkadaş Karanlık Sanatlara Karşı Savunma Dersine doğru yola çıktılar. Bu yılki öğretmenleri ünlü Gilderoy Lockhart'tı. Şimdi Harry derse vaktinde yetiştiğinden emin olmalı.",
    20: "#3C#$021Karanlık Sanatlara Karşı Savunma dersine vaktinde yetişen Harry, şimdi Gilderoy Lockhart'tan Petrificus Totalus büyüsünü öğrenmeli.",
    21: "#3F#$022Harry, Gilderoy Lockhart ile ilk Karanlık Sanatlara Karşı Savunma dersine katıldı; burada Petrificus Totalus büyüsünü öğrendi ve Cornwall cin perileriyle savaştı.",
    22: "#42#$023Karanlık Sanatlara Karşı Savunma sınıfının dışında Harry, Ron ve Hermione, kendilerini Ölüm Günü Partisi'ne davet eden Neredeyse Kafasız Nick ile karşılaştılar. Harry, Neredeyse Kafasız Nick'i takip ederek Zindanlar'a giden yolu bulmalı.",
    23: "#45#$024Harry, Zindanlar boyunca Neredeyse Kafasız Nick'i takip ederek onun Ölüm Günü Partisi'ne gitti.",
    24: "#48#$025Harry, Neredeyse Kafasız Nick ile buluşup Ölüm Günü partisine katıldı. Ardından Harry, Filch'in esrarengiz bir biçimde taşlaşmış olan kedisi Bayan Norris ile karşılaştı. Duvarda, Sırlar Odası'nın açıldığını bildiren tüyler ürpertici bir mesaj yazılıydı.",
    25: "#4B#$026Kütüphanede Hermione, Çoközlü İksir'i ve bu iksirin Slytherin Ortak Odası'na gizlice girmelerini nasıl sağlayacağını anlattı. Harry ve Ron, Çoközlü İksir malzemelerini bulmakla görevlendirildiler. Ancak önce Snape'in İksir dersine girmeleri gerekiyordu.",
    26: "#4E#$027Profesör Snape'in verdiği İksir Dersinden sonra Harry ve Ron'a Wiggenweld İksiri'nin nasıl hazırlanacağı öğretildi. Harry, Cadılar Bayramı balkabaklarını saran bahçe cücelerini temizlemek için yardım isteyen Hagrid ile karşılaştı.",
    27: "#51#$028Harry, balkabağı tarlasındaki cüceleri ayıklayarak Hagrid'e yardım etti; Hagrid de Harry'yi Çoközlü İksir malzemelerinden biriyle ödüllendirdi. Artık Harry'nin Slytherin'e karşı ilk Quidditch maçının vakti gelmişti.",
    28: "#54#$029Hagrid'in balkabağı tarlasındaki cüceleri ayıkladıktan ve ödül olarak Çoközlü İksir malzemelerinden birini aldıktan sonra, Harry'nin bu yılki ilk Quidditch maçında Slytherin'e karşı mücadele etmesi gerekiyor.",
    29: "#57#$030Harry, Slytherin'e karşı Quidditch oynadı ve maç sırasında kontrolden çıkmış bir Bludger kolunu kırdı. Harry kendini Hastane Kanadı'nda buldu. O gece Harry, Colin Creevey'nin de taşlaşmış olduğunu öğrendi. İyileştiğinde Harry, Çoközlü İksir için gerekenleri almak üzere Diagon Yolu'nda Hagrid ile buluştu.",
    30: "#5A#$031Diagon Yolu'ndaki Sihirli Menajerlik'te Harry, Çoközlü İksir için gereken dantelkanat sineklerini başarıyla yakaladı.",
    31: "#5D#$032Harry, Diagon Yolu'nda Çoközlü İksir için gereken dantelkanat sineklerini ele geçirdi. Eczane'de ortalığı saran Cornwall cin perilerinden kurtuldu ve karşılığında bir miktar sülük aldı. Harry ve Hagrid Hogwarts'a geri döndüler.",
    32: "#60#$033Harry ve Ron, Çoközlü İksir malzemelerini Hermione'ye verdiler ancak hâlâ bazı hayati malzemeler eksikti. Hermione, iksire katmak üzere Crabbe ve Goyle'dan saç teli koparıp getirmeleri için onları gönderdi. Ron, Harry'ye Ortak Oda'da buluşacaklarını söyledi.",
    33: "#63#$034Çoközlü İksir'e katmak üzere Crabbe ve Goyle'un saç tellerini arayan Harry ve Ron, kendilerini yeni kurulan Büyücü Düellosu Kulübü'nün ilk toplantısını yaptığı Büyük Salon'un önünde buldular.",
    34: "#66#$035Harry, Büyücü Düellosu Kulübü'nde Draco Malfoy ile düello yaparken, Malfoy Serpensortia büyüsü yaptı ve asasından kara bir yılan fırladı. Yılan başka bir öğrenciye saldırmaya çalıştı ancak Harry Çatalağızca bir şeyler haykırarak onu durdurdu. Dumbledore, Harry'ye saldırganın o olduğunu düşünmediğini söyledi.",
    35: "#69#$036Tüm Çoközlü İksir malzemeleri toplandıktan sonra Hermione iksiri hazırlayabildi; Ron ile Harry de Crabbe ve Goyle'a dönüştüler. Harry ve Ron'un Slytherin Ortak Odası'nı bulmak için bir Slytherin öğrencisini takip etmeleri gerekiyor.",
    36: "#6C#$037Harry ve Ron koşarak Slytherin Ortak Odası'na gittiler; Harry burada Draco Malfoy'un Slytherin'in Vârisi olmadığını öğrendi.",
    37: "#6F#$038Kızlar Tuvaleti'ne döndüklerinde Mızmız Myrtle, Harry'ye günlüğü verdi. Harry, Profesör Lockhart'tan Karanlık Sanatlara Karşı Savunma dersi için derhal odasına gelmesini isteyen bir mesaj aldı.",
    38: "#72#$039Harry, Gilderoy Lockhart'tan Verdimillious Duo büyüsünü öğrendi. Lockhart'ın odasından çıkarken, Sevgililer Günü kartları dağıtan kart taşıyıcı aşk meleklerinin saldırısına uğradı. Harry, kart taşıyıcı aşk meleklerine yakalanmaktan kaçınmalı.",
    39: "#75#$040Tom Riddle'ın Günlüğü'nde genç Hagrid'i gördükten sonra Harry ve Ron gidip Hagrid'i görmeleri gerektiğine karar verdiler. Ancak son saldırıların ardından öğretmenler okul bahçesinde devriye gezmektedir. Harry'nin dışarıya, Hagrid'in Kulübesi'ne gizlice süzülmek için Görünmezlik Pelerini'ni kullanması gerekecek.",
    40: "#78#$041Harry, dışarıya, Hagrid'in Kulübesi'ne süzülmek için Görünmezlik Pelerini'ni kullandı. Oradayken Hagrid'in Azkaban'a götürüldüğünü gördü. Harry şimdi Hagrid'in tavsiyesine uymalı ve örümcekleri takip ederek Yasak Orman'a girmeli.",
    41: "#7B#$042Hagrid'in tavsiyesine uyan Harry, Yasak Orman boyunca örümcekleri takip ediyordu. Harry, 50 yıl önce Sırlar Odası'nı açan kişinin gerçekten Hagrid olup olmadığını öğrenmeli.",
    42: "#7E#$043Harry örümcekleri takip ederek Yasak Orman'a girdi ve Aragog ile konuştu. Harry, Hagrid'in Slytherin'in Vârisi olmadığını öğrendi. Harry ve Ron, Ford Anglia ile Aragog'dan kaçtılar; şimdi Hastane Kanadı'ndaki Hermione'yi ziyaret etmeleri gerekiyor.",
    43: "#81#$044Ginny kayboldu ve Harry, Hermione'nin taşlaşmış elinde bir kitaptan koparılmış bir sayfa buldu. Bu sayfa ona basiliski anlattı ve Harry, Ginny'yi Sırlar Odası'ndan kurtarmaya yardım etmesi için Lockhart'ı ikna etmesi gerektiğini anladı.",
    44: "#84#$045Ron ve Harry, Gilderoy Lockhart'ı Hogwarts'tan ayrılmak için harıl harıl eşyalarını toplarken buldular. Onu kalıp Ginny'yi bulmalarına yardım etmesi gerektiğine ikna ettiler ve Sırlar Odası'na giden yolun Kızlar Tuvaleti'nde olduğunu düşündüklerini söylediler.",
    45: "#87#$046Kızlar Tuvaleti'nde Myrtle, Harry'ye Oda'nın girişinin nerede olduğunu söyledi. Harry, Ron ve Gilderoy Lockhart; Harry'nin Çatalağızca konuşmasıyla ortaya çıkan geniş borudan içeri girmeye hazırlandılar.",
    46: "#8A#$047Kızlar Tuvaleti'nde Sırlar Odası'nın girişini bulup kapıyı Çatalağızca açtıktan sonra Harry, Lockhart ve Ron okulun altındaki tünele vardılar. Şimdi Ginny'yi bulmaya çalışmalılar.",
    47: "#8D#$048Sırlar Koridoru'na girdikten sonra Harry düelloda Lockhart'ı yenip silahsızlandırmayı başardı; ancak düellonun şiddeti tavanın çökmesine yol açarak Harry ile Ron'un bağlantısını kesti. Harry, Ginny'yi kurtarmak için Sırlar Odası'na doğru ilerlemeli.",
    48: "#90#$049Harry, okulun altındaki Sırlar Koridoru'ndan geçmeyi başararak Sırlar Odası'na girdi.",
    49: "#93#$050Sırlar Odası'nda Tom Riddle, kendisinin Lord Voldemort olduğunu açıkladı. Riddle, basiliske Harry'ye saldırmasını emretti.",

    # 50 - 65: Objectives
    50: "$001Diagon Yolu'na git",
    51: "$002Hogwarts'a vaktinde ulaş",
    52: "$003Şişman Hanım'a git",
    53: "$004Ortak Oda'ya girmek için parolayı öğren",
    54: "$005Bitkibilim dersi için Üç Numaralı Sera'ya git",
    55: "$006Quidditch Antrenmanı için Oliver Wood ile buluş",
    56: "$007Ron ile düello yap",
    57: "$008Ron'u gözden kaybetme!",
    58: "$009Sümüklüböcekleri kasede yakala ve fıçıya boşalt",
    59: "$010Yukarı Şato'daki Karanlık Sanatlara Karşı Savunma sınıfına git",
    60: "$011Bütün cin perilerini yakala",
    61: "$012Zindanlar'daki Neredeyse Kafasız Nick'in Ölüm Günü Partisi'ne git",
    62: "$013Çoközlü İksir için dantelkanat sinekleri, ağaçyılanı derisi ve sülük topla",
    63: "$014Malzemeleri Yukarı Şato Kızlar Tuvaleti'ndeki Hermione'ye götür.",
    64: "$015Slytherin Ortak Odası'nın girişini bul",
    65: "$016Aşağı Şato'daki Gilderoy Lockhart'ın Odası'na git",

    # 66 - 89: Famous Cards names
    66: "$001Paracelsus",
    67: "$002Gaspard Shingleton",
    68: "$003Ignatia Wildsmith",
    69: "$004Felix Summerbee",
    70: "$005Greta Catchlove",
    71: "$006Jocunda Sykes",
    72: "$007Dorcas Wellbeloved",
    73: "$008Crispin Cronk",
    74: "$009Yardley Platt",
    75: "$010Edgar Stroulger",
    76: "$011Adalbert Waffling",
    77: "$012Cassandra Vablatsky",
    78: "$013Montague Knightley",
    79: "$014Chauncey Oldridge",
    80: "$015Godric Gryffindor",
    81: "$016Salazar Slytherin",
    82: "$017Rowena Ravenclaw",
    83: "$018Helga Hufflepuff",
    84: "$019Woodcroft'lu Hengist",
    85: "$020Daisy Dodderidge",
    86: "$021Celestina Warbeck",
    87: "$022Cyprian Youdle",
    88: "$023Hain Herpo",
    89: "$024Bertie Bott",

    # 90 - 113: Card Descriptions
    90: "$001Ortaçağ simyacılarının en büyüğü.",
    91: "$002Kendi Kendini Karıştıran Kazan'ın ünlü mucidi.",
    92: "$003Uçuş Tozu'nu icat eden cadı.",
    93: "$004Neşelendirme Büyüleri'nin mucidi.",
    94: "$005'Kendi Peynirini Kendin Büyüle' kitabının yazarı.",
    95: "$006Süpürgeyle Atlas Okyanusu'nu geçen ilk kişi.",
    96: "$007Muhtaç Cadılar Derneği'nin kurucusu.",
    97: "$008Arka bahçesinde Sfenks beslediği için Azkaban'a gönderildi.",
    98: "$009Seri goblin katili.",
    99: "$010Sinsiölçer'in mucidi.",
    100: "$011Ünlü büyü teorisyeni.",
    101: "$012Ünlü Kâhin ve 'Geleceğin Sis Perdesini Aralamak' kitabının yazarı.",
    102: "$013Büyücü Satrancı Şampiyonu 1506 - 1588.",
    103: "$014Ejderha Çiçeği'nin bilinen ilk kurbanı.",
    104: "$015Hogwarts'ın kurucu ortaklarından. Bir Hogwarts Binasına adını verdi.",
    105: "$016Hogwarts'ın kurucu ortaklarından. Bir Hogwarts Binasına adını verdi.",
    106: "$017Hogwarts'ın kurucu ortaklarından. Bir Hogwarts Binasına adını verdi.",
    107: "$018Hogwarts'ın kurucu ortaklarından. Bir Hogwarts Binasına adını verdi.",
    108: "$019Hogsmeade köyünü kurdu.",
    109: "$020Çatlak Kazan'ın ilk kadın işletmecisi.",
    110: "$021Popüler şarkıcı büyücü kadın.",
    111: "$022Bir maç sırasında ölen tek Quidditch hakemi.",
    112: "$023Basiliskin bilinen ilk yaratıcısı.",
    113: "$024Bertie Bott'un Binbir Çeşit Fasulyeleri'nin mucidi.",

    # 114: Controller interaction prompt
    114: "$005< Konuş",

    # Credits Titles & Roles
    115: "$025Yapımcı",
    117: "$031Yardımcı Yapımcı",
    119: "$012Baş Tasarımcı",
    121: "$014Tasarımcılar",
    126: "$001Baş Programcı",
    128: "$003Oyun Programcıları",
    132: "$032Baş Sanatçı",
    134: "$034Sanatçılar",
    139: "$095Hikâye Kitabı Sanatçısı",
    141: "$037Baş Animatör",
    143: "$035Animatör",
    145: "$022Ses Departmanı Başkanı",
    147: "$049Ses Tasarımcısı",
    149: "$054Kalite Güvence Müdürü",
    151: "$060Baş Test Uzmanı",
    153: "$059Test Uzmanları",
    157: "$038Özel Teşekkürler:",
    160: "$041Harry Potter ve Felsefe Taşı Ekibi",
    162: "$029İdari Yapımcı",
    164: "$001Electronic Arts Avrupa",
    165: "$002Yapım Ekibi:",
    174: "$011Sanat Ekibi:",
    179: "$016Tasarım ve Senaryo:",
    184: "$021Ses Ekibi:",
    190: "$027Müzikleri Besteleyen ve İcra Eden:",
    192: "$029Stüdyo Pazarlama:",
    196: "$001Avrupa Yerelleştirme Müdürü:",
    198: "$003Yazılım Yerelleştirme Müdürü:",
    200: "$005Yerelleştirme:",
    204: "$009Seslendirme Kadrosu:",
    236: "$033Kalite Güvence:",
    254: "$041Avrupa Mastering:",
    261: "$048Avrupa CQC Operasyon Müdürü:",
    263: "$050Avrupa CQC:",
    275: "$066Yapım Müdürü:",
    277: "$068Müşteri Temsilcisi:",
    283: "$070Üretim Planlayıcısı:",
    285: "$072Materyal Koordinatörü:",
    287: "$074Yaratıcı Müşteri Temsilcisi:",
    289: "$076Yazılım Kılavuzu Yazarı:",
    291: "$078Yazılım Kılavuzu Editörü:",
    293: "$051Özel Teşekkür:",
    319: "$001Warner Bros. Interactive Entertainment",
    322: "$005Pazarlama:",
    325: "$008WBIE Özel Teşekkür:",
    340: "$024Belirli Teknolojiler | 2002 Argonaut Software Ltd. Tüm hakları saklıdır.",
    341: "$082Stüdyo Operasyonları:",
    344: "$080Web Yerelleştirme Koordinasyonu:",
    346: "$001Argonaut Games",
    347: "$008Motor Programcısı",
    349: "$010Ses Programcısı",
}

def main():
    with open(BATCH_0_PATH, encoding="utf-8") as f:
        data = json.load(f)

    tag_regex = re.compile(r"^((?:#[0-9A-Fa-f]+#)?(?:\$[0-9]{3}))")

    result = []
    for item in data:
        idx = item["id"]
        en_str = item["en"]

        m_en = tag_regex.match(en_str)
        en_tag = m_en.group(1) if m_en else ""

        if idx in CUSTOM_TR:
            tr_str = CUSTOM_TR[idx]
        else:
            tr_str = en_str

        # Verify tag preservation
        m_tr = tag_regex.match(tr_str)
        tr_tag = m_tr.group(1) if m_tr else ""
        if en_tag != tr_tag:
            raise ValueError(f"Tag mismatch at ID {idx}: EN tag '{en_tag}' != TR tag '{tr_tag}'")

        # Verify controller glyphs
        glyphs = set("{}[]<>@")
        en_glyphs = [c for c in en_str if c in glyphs]
        tr_glyphs = [c for c in tr_str if c in glyphs]
        if en_glyphs != tr_glyphs:
            raise ValueError(f"Glyph mismatch at ID {idx}: EN '{en_glyphs}' != TR '{tr_glyphs}'")

        if not tr_str.strip():
            # Check if it was purely newline in en
            if not en_str.strip():
                pass
            else:
                raise ValueError(f"Empty translation at ID {idx}")

        result.append({
            "id": idx,
            "en": en_str,
            "tr": tr_str
        })

    if len(result) != 360:
        raise ValueError(f"Expected 360 entries, got {len(result)}")

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[OK] Successfully wrote {len(result)} entries to {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
