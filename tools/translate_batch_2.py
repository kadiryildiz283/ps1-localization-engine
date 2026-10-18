#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batch 2 Translation (IDs 720 - 1079) for Harry Potter and the Chamber of Secrets (PS1).

Conforms to Sevin Okyay and Kutlukhan Kutlu translations and preserves all tags,
controller glyphs, Latin spells, and canon lore.
"""

import json
import os
import re

BATCH_2_TRANSLATIONS = {
    # 720 - 728: The Burrow fireplace & Floo network travel
    720: "#48#$022Gözlüğün mü kırıldı? Korkunç bir şeydi!",
    721: "#0#$003Dirseklerini de sakın açma!",
    722: "#3#$006Çocuk oyuncağı!",
    723: "#6#$002Şömineye girdiğinde nereye gittiğini söyle -",
    724: "#9#$005Bunun güvenli olduğuna emin misiniz?",
    725: "#C#$007$D-Di-ya-gon $Yolu!",
    726: "#F#$001Daha önce hiç $Uçuş $Tozu ile yolculuk etmediğin için bilmen gereken birkaç şey var!",
    727: "#12#$004Doğru şöminede çıkmaya dikkat et!",
    728: "$004Daha hızlı kaymak için > butonuna bas!",

    # 729 - 757: Arthur Weasley, Garden Junk, Ginny & Puffskein at the Burrow
    729: "#0#$002Wingardium Leviosa",
    730: "#4#$004Felix Summerbee",
    731: "#9#$004Merhaba Harry! Ben Arthur Weasley. Bahçedeki cüceleri temizlememe yardım eder misin acaba? Kapının hemen ardında ama cüceleri yakalamak için cüce ayıklama eldivenlerine ihtiyacın olacak. Ne yazık ki bütün bu ıvır zıvırın arasında onları kaybettim galiba.",
    732: "#C#$005Ivır zıvırı büyüleyip hareket ettirmek için Wingardium Leviosa büyünü kullan. > butonunu basılı tutmak her bir ıvır zıvır parçasını havaya kaldırır. Yön butonlarını kullanarak ıvır zıvırı hareket ettir ve kayaların üzerine bırakıp parçalamak için [ butonuna bas.",
    733: "#F#$006Onları büyüleyip kayaların üzerine bırakabilir misin lütfen? Belki şu eldivenleri buluruz... Buralarda bir yere bıraktığıma eminim...",
    734: "#12#$002Aynen öyle Harry. Devam et!",
    735: "#15#$003Aferin Harry! Güzel iş. Cüce ayıklama eldivenlerini buldun. İşte buradalar!",
    736: "#18#$003Parçalamak istiyorsam ıvır zıvırı bundan daha yüksekten bırakmam gerek sanırım.",
    737: "#1B#$001Hey baksana! Ginny Pofuduk Puf'ların orada. Neden gidip onunla sohbet etmiyorsun? Son zamanlarda biraz utangaç davranıyor - neden acaba? Ben babamın ne yaptığına bakmaya gidiyorum.",
    738: "#1E#$012Unutma Harry, tıpkı geçen yılki Tılsım dersi gibi. Cüce ayıklama eldivenlerini bulsak iyi olur. Onlar olmadan cüce ayıklayamayız!",
    739: "#21#$018$Sandıkları yukarı kaldır ve aşağıdaki $kayaların üzerine bırak!",
    740: "#24#$001Babama yardım ettiğin için teşekkürler Harry! Nesneleri nasıl büyüleyeceğini de öğrendin ve eminim bu çok işine yarayacak!",
    741: "#27#$001Bahçedeki cüceleri ne kadar çabuk temizlersek o kadar çabuk uyuyabiliriz. Pestilim çıktı!",
    742: "#2A#$002Merhaba, bir büyücü düellosuna ne dersin?",
    743: "#2D#$004Daha önce hiç büyücü düellosuna katılmadım deme sakın! Öğreneceğin çok şey var Harry.",
    744: "#30#$006Elbette güvenli... yani, çoğunlukla...",
    745: "#33#$003Büyücü düellosu mu?",
    746: "#36#$005Bu güvenli mi?",
    747: "#39#$007Tüm yardımın için teşekkürler Harry. Sanırım Ron cüce ayıklamak için kapıdan önden koşup gitti.",
    748: "#3C#$008Sonra görüşürüz Harry!",
    749: "#3F#$001M-merhaba Harry! Tanıştığıma memnun oldum. Ben Ginny. Pofuduk Puf'umuza göz kulak oluyorum, Fred ve George Quidditch oynarken onu Bludger olarak kullanmasın diye.",
    750: "#42#$003Pofuduk Puf'u çalılara doğru yönlendir, onları yiyecek ve toplayabileceğin $Binbir $Çeşit $Fasulye ortaya çıkacaktır. Fasulyeler Hogwarts'ta Fred ve George'dan $Ünlü $Cadı $ve $Büyücü $kartları satın almak için kullanılabilir.",
    751: "#45#$004Pofuduk Puf'u çalılara doğru yönlendirirsen onları yer ve bir $Ünlü $Cadı $ve $Büyücü $kartı bulabilirsin!",
    752: "#48#$005Ne zaman bir Büyücü kartı alsan $Folio $Magi albümüne konur. $SELECT butonuna bas. Bu sana $Folio $Magi'yi ve o ana kadar topladığın Büyücü kartlarını gösterir.",
    753: "#4B#$006İki tür Ünlü Cadı ve Büyücü kartı vardır: Gümüş kartlar ve dört özel altın kurucu kartı!",
    754: "#4E#$005Şey... Kovuk'un tadını çıkar Harry.",
    755: "#51#$002Aferin Harry! İşte bir $Ünlü $Cadı $ve $Büyücü $kartı!",
    756: "#54#$001Ron'u bulsan iyi olur Harry. Sanırım babamın yanına gitti. Bu taraftan.",
    757: "#57#$002Hemen şuradan Harry. Sonra görüşürüz!",

    # 758 - 767: Burrow Barn / Yard, Remembrall & Hengist of Woodcroft
    758: "#3#$007Wingardium Leviosa",
    759: "#7#$001Ginny'yi bulmamız gerek. Bir yerlere gitti ve Diagon Yolu'na gidip okul gereçlerimizi alabilelim diye bütün aile bekliyor. Ayrılsak ve onu arasak iyi olur.",
    760: "#A#$002Bu arada babamın ıvır zıvırlarına dikkat et. Karşına çıkarsa kendini savunmak için $Flipendo büyünü ya da $Wingardium $Leviosa büyünü kullan.",
    761: "#D#$003Canının biraz azaldığını hissedersen $Çikolata $Kurbağalar enerjini tazelemeye yardımcı olur, o yüzden gözünü dört aç. Pekâlâ, ayrılalım. Ben bu taraftan gideyim - yakında görüşürüz Harry, bol şans!",
    762: "$003Çamaşır makinesini $hedef $almak için $_ butonuna bas",
    763: "$004$Basınç $plakasının üzerine $büyüleyip koyacak bir şey ara",
    764: "$005Etrafa bakmak için [ butonuna bas",
    765: "#7#$019Hengist of Woodcroft",
    766: "#B#$001Oh selam Harry! Çok şükür geldin. Pofuduk Puf'um $Hatırlatıcı'mı yuttu, ben de onu ararken kayboldum! Bir $Hatırlatıcı sana yapmayı unuttuğun bir şey olup olmadığını söyler. Sende kalabilir Harry. Şu an yanımda asam yok, o yüzden Pofuduk Puf'a Flipendo büyünü yaparsan onu tükürecektir.",
    767: "#E#$001Ah Ginny, işte buradasın! Güzel iş Harry! Umarım babamın ıvır zıvırları senin için pek sorun olmamıştır. Pekâlâ, eve dönsek iyi olur. Annemle babam bizi Diagon Yolu'na götürmek için bekliyor!",

    # 768 - 843: Quidditch Match Commentary (Lee Jordan)
    768: "#F#$026İşte Potter geliyor!",
    769: "#12#$022O Snitch miydi?",
    770: "#15#$023Altın bir parıltı... Snitch mi o?",
    771: "#18#$024İŞTE SNITCH ORADA!",
    772: "#1B#$025Potter Snitch'i gördü!",
    773: "#1E#$027Potter'a bakın hele... Snitch'in peşinde!",
    774: "#21#$028Seyirciler ayakta! Haydi Harry Potter!",
    775: "#24#$029Potter bitirici hamle için yaklaşıyor...",
    776: "#27#$030Ooooh, kaybetti!",
    777: "#2A#$031Aaah, Snitch'i kaybetti!",
    778: "#2D#$032Başarısız!",
    779: "#30#$033Dönüyor ve kaçırıyor!",
    780: "#33#$034Hayır, Snitch kaçtı!",
    781: "#36#$035Potter hamle yapıyor!",
    782: "#39#$036Potter doğrudan üzerine gidiyor!",
    783: "#3C#$037Snitch'i yakaladı!",
    784: "#3F#$038Snitch Potter'da!",
    785: "#42#$039Güzel yakalayış! Snitch Potter'da!",
    786: "#45#$040Kusursuz bir yakalayış! Potter zaferi Gryffindor'a getiriyor!",
    787: "#48#$041Yakaladı! Gryffindor'a tam puan!",
    788: "#4B#$042Hızla gelen Bludger'dan sıyrılıyor!",
    789: "#4E#$043Bir Bludger geliyor!",
    790: "#51#$044Ooooh, çok yakındı!",
    791: "#54#$045Potter kıl payı kurtuldu!",
    792: "#57#$046Ooooh, bu fena acıtmış olmalı!",
    793: "#5A#$047Bludger!",
    794: "#5D#$048Ah, bunun acısını yarın hisseder!",
    795: "#60#$049Potter Bludger'ların ateşi altında...",
    796: "#63#$052Buna daha fazla dayanamaz!",
    797: "#66#$050Vuruldu! Düşüyor!",
    798: "#69#$051Potter kontrolü kaybetti, yaralandı!",
    799: "#6C#$053Potter çakılacak!",
    800: "#6F#$054İşi bitti! Çakılıyor!",
    801: "#72#$055Potter oyun dışı kaldı!",
    802: "#75#$056Harry Potter için her şey bitti!",
    803: "#78#$057Şanssızlık Potter -- o Bludger'lar fazlasıyla ağırdı!",
    804: "#7B#$058Dayanabileceği kadar dayandı!",
    805: "#7E#$059Potter tekrar bakmak için yukarı çıkıyor.",
    806: "#81#$060Potter yeniden yükseliyor!",
    807: "#84#$061Potter tekrar aramak için yukarı uçuyor.",
    808: "#87#$077Ooooh!",
    809: "#8A#$078Ahhh!",
    810: "#8D#$079Potter arayı kapatıyor!",
    811: "#90#$080Potter'a bakın hele!",
    812: "#93#$081Gittikçe yaklaşıyor",
    813: "#96#$095Harry Potter Snitch'e yaklaşıyor...",
    814: "#99#$096Potter çok yaklaştı!!",
    815: "#9C#$104Harika!",
    816: "#9F#$105Mükemmel!!",
    817: "#A2#$106İnanılmaz bir ustalık!!",
    818: "#A5#$107Böyle uçuş görmedim!",
    819: "#A8#$113Bu inanılmaz!!!",
    820: "#AB#$097Haydi Potter, şimdi pes etme sakın!",
    821: "#AE#$102Arayıcılar kıyasıya mücadele ediyor...",
    822: "#B1#$103Snitch'i kim yakalayacak?",
    823: "#B4#$110Arayıcılar Snitch için savaşıyor",
    824: "#B7#$111Arayıcılara bakın hele!",
    825: "#BA#$109Hayııııır!!!!",
    826: "#BD#$112Potter kontrolü kaybediyor...",
    827: "#C0#$115Potter geride kalıyor...",
    828: "#C3#$098İşte Gryffindor Arayıcısı geliyor!",
    829: "#C6#$099İşte Hufflepuff Arayıcısı geliyor!",
    830: "#C9#$100İşte Ravenclaw Arayıcısı geliyor!",
    831: "#CC#$101İşte Slytherin Arayıcısı geliyor!",
    832: "#CF#$114Potter öne geçiyor...",
    833: "#D2#$108Yaaaşasın!!!",
    834: "$031> Snitch'i Yakala",
    835: "#D5#$001Quidditch'e hoş geldiniz. Ben yorumcunuz Lee Jordan!",
    836: "#D8#$002Quidditch sahasının her iki ucunda üçer kale çemberi bulunur. Kovalayıcılar sayı yapmak için Quaffle'ı fırlatıp çemberlerden geçirmeye çalışırlar.",
    837: "#DB#$003Bludger'lara dikkat edin. Seni süpürgenden düşürebilecek büyülü toplardır bunlar! Her takımdaki iki Vurucu onları uzak tutmaya çalışır.",
    838: "#DE#$006Slytherin'e karşı oynanacak bu maçta Gryffindor, bir kez daha mükemmel Arayıcımız Harry Potter'a güveniyor!",
    839: "#E1#$004Gryffindor takımının Arayıcısı Harry Potter'dır. Görevi Altın Snitch'i bulup yakalamaktır.",
    840: "#E4#$005Harry Potter bir kez daha Gryffindor takımının Arayıcısı. Son maçta Snitch'i yakalayarak maçı kazandırmıştı.",
    841: "#E7#$007Unutmayın, Snitch ortaya çıktığında, Arayıcının daha hızlı uçmasına yardımcı olan Hız Halkaları bırakır.",
    842: "$001TEKRAR DENE, HARRY!",
    843: "$001AFERİN, HARRY!!",

    # 844 - 883: Diagon Alley Shops, Hagrid, Malfoy & Apothecary/Menagerie
    844: "$006< Duyuruyu Oku",
    845: "#2#$001Git de gereçlerini al, Harry.",
    846: "#5#$002Ben eski dostlarla buluşmak için bara gidiyorum.",
    847: "#8#$003Birazdan seninle yine burada buluşuruz.",
    848: "$008Diagon Yolu",
    849: "#B#$001Ayy, ne kadar da hoş bir gençsin sen!",
    850: "#E#$003Fazla şımarma evlat. İltifat haznem tükendi... şimdi git başımdan!",
    851: "#11#$001Bütün eşyalarını aldıysan, Hogwarts'a dönsen iyi olur.",
    852: "#14#$002Tatile çıktık -- seneye döneriz.",
    853: "#17#$001Kargaşaya yol açan bazı kusurlu kazanlar sebebiyle hâlâ kapalıyız, kusura bakmayın.",
    854: "#1A#$003Gündüz soygunu sebebiyle kapalıyız - saat yedide döneceğiz.",
    855: "#1D#$004Geçici kapanış sebebiyle müşterilerimizden özür dileriz. Gilderoy Lockhart'ın son ziyaretinden sonra ortalığı hâlâ toparlıyoruz.",
    856: "$001Sihirli Menajeri",
    857: "#21#$005Bugün Cinperi Resmi Tatili, bu yüzden kapalıyız.",
    858: "#24#$006Galler'e kuş gözlemine gittik.",
    859: "#27#$007Kısa bir süreliğine çıktık, birazdan döneceğiz.",
    860: "$002Eczane",
    861: "#2A#$001Kulaklıkların çok hoşmuş Potter, annen mi ördü sana?",
    862: "#2D#$002Ah, çok affedersin, unutmuştum...",
    863: "#30#$004Pekâlâ, dörtgöz. Ah bu arada, bu dükkânda senin için güzel bir sürpriz bıraktım. Tadını çıkar.",
    864: "#33#$001Harry, $Çoközlü $İksir'i yapmak için mükemmel yeri buldum! $Yukarı $Şato'daki Mızmız Myrtle'ın Tuvaleti. Bütün malzemeleri toplayınca hemen gel, sevgiler Hermione.",
    865: "#37#$003Malfoy, neredeyse Filch kadar komiksin, şimdi çekil yolumdan.",
    866: "#1#$001Nasıl yardımcı olabilirim?",
    867: "#4#$003Biraz $zarkanatlı $sinek alabilir miyim lütfen?",
    868: "#7#$004Elimde gerçekten de biraz $zarkanatlı $sinek var ama yakalayamayacağım kadar hızlı hareket ediyorlar.",
    869: "#A#$005Şu kutulardan birinde saklanıyorlar. Benim için beş tane yakalayabilirsen sende kalmalarına izin veririm.",
    870: "#D#$006Süre dolmadan bütün sinekleri toplaman gerek.",
    871: "#10#$007Daha dikkatli ol, bütün mallarımı kırıyorsun. Şimdi yeniden başlamalısın.",
    872: "#13#$001Süren bitti.",
    873: "#16#$002Tekrar dene ve daha hızlı ol.",
    874: "#1A#$001Aferin, bütün sinekleri topladın. Eksikliklerini hiç hissetmeyeceğim doğrusu. Şimdi vızıldayıp git başımdan...",
    875: "#1F#$001$Sihirli $Menajeri'ye hoş geldiniz.",
    876: "#22#$003Böyle daha iyi mi?",
    877: "#26#$002Burası pek Noel havasında görünmüyor, değil mi?",
    878: "#3#$001Lütfen yardım edin! Biri dükkânıma bir çete Cinperi salmış ve ortalığı birbirine katıyorlar!",
    879: "#6#$002Dükkânımı mahvetmeden önce onları durdurabilirsen ne istersen veririm.",
    880: "#9#$001Çok teşekkür ederim. Size borcumu nasıl ödeyebilirim?",
    881: "#C#$001Daha hızlı olmalısın, tekrar dene.",
    882: "#10#$002Hiç sülüğünüz var mı?",
    883: "#13#$003İşte buyur - ve yardımın için tekrar teşekkürler.",

    # 884 - 939: Hogwarts Castle, Portraits, Dobby, Colin Creevey & Hallways
    884: "$018< Kolu Kullan",
    885: "$038< İksiri İç",
    886: "#3#$013Montague Knightley",
    887: "#9#$001A, Bay Potter! Geçen yıldan hatırlıyorum sizi!",
    888: "#C#$002Bir üst kata çıkmak istiyorsanız buyrun geçin, Bay Potter!",
    889: "$002Girilmez!",
    890: "#10#$001Seni uyarıyorum! Buradan geçme! Git buradan!",
    891: "#13#$002Umarım o kolu çekmemişsindir genç adam!",
    892: "#0#$002Harry Potter Hogwarts'ta kalmamalı",
    893: "$012Doğu Kanadına",
    894: "$005Yukarı Hogwarts",
    895: "$007Yasak Bölge",
    896: "$010Zindanlara",
    897: "$002Zindanlar",
    898: "$004Prof. Lockhart'ın Odası",
    899: "$006Gryffindor Ortak Odası",
    900: "#4#$001Parola?",
    901: "#7#$001Hotozlu kuş!",
    902: "$021Büyük Salon",
    903: "$009Ön Bahçe",
    904: "$019Kütüphane",
    905: "#A#$002Harika! Ne girişti ama!",
    906: "#D#$001Uçan bir arabayla doğruca Şamarcı Söğüt'e dalmak ha, millet bunu yıllarca konuşacak!",
    907: "#10#$004Şey... Teşekkürler çocuklar!",
    908: "#13#$001Snape bizi görmeden Ortak Oda'ya gitsek iyi olur.",
    909: "#16#$002Bak, işte Lockhart'ın odası. O koca kafasını kapıdan nasıl sokabiliyor şaşıyorum doğrusu!",
    910: "#19#$004Hadi Harry, geç kalmak istemezsin.",
    911: "#1C#$006Partimde kurtlu işkembe, tüylü yeşil peynir ve mezartaşı şeklinde pasta var! Nefis, değil mi?",
    912: "#1F#$007Bu taraftan, Harry!",
    913: "#22#$005Özel bir Ölümgünü konuşması hazırladım!",
    914: "#25#$008Bunun gerçekten unutulmaz bir Ölümgünü olacağını düşünüyorum!",
    915: "#28#$010Vay canına, Harry Potter. Gerçekten sensin!",
    916: "#2B#$002Ben Colin Creevey.",
    917: "#2E#$002Ben de Gryffindor'dayım. Bir fotoğrafını çeksem bir sakıncası olur mu?",
    918: "#31#$003Kim-Olduğunu-Bilirsin-Sen seni öldürmeye çalıştığında nasıl hayatta kaldığını herkes anlattı bana.",
    919: "#34#$004Ve alnında gerçekten de o şimşek biçimli yara izi var!",
    920: "#37#$002Burası harika bir yer, değil mi!",
    921: "$014Arka Hole",
    922: "$013Prof. Lockhart'ın Odasına",
    923: "$016Ön Hol",
    924: "$015Ön Hole",
    925: "#3A#$001Şansımıza inanabiliyor musun? Fred ile George o arabayı beş altı kez uçurmuş olmalılar ve hiç kaza yapmadılar! Kesin okuldan atılacağız sanmıştım.",
    926: "#3D#$003Sorun değil. Takip et beni.",
    927: "#40#$002Hadi Ron, Gryffindor Ortak Odası'na gidelim. Yolu hatırlayabileceğini düşünüyor musun?",
    928: "#43#$001Seralara gitmek için dışarı çıkmamız gerek.",
    929: "#46#$003Bana bunu hatırlatma!",
    930: "#49#$002Dışarı çıkacaksak Şamarcı Söğüt'ten uzak duralım.",
    931: "$022Aşağı Hogwarts Şatosu",
    932: "#4D#$001Şu Gryffindor Bina Hayaleti Neredeyse Kafasız Nick değil miydi?",
    933: "#50#$002Evet Colin, oydu...",
    934: "#53#$001Bil bakalım ne oldu Harry - Hermione Hastane Kanadı'nda. Çoközlü İksir onu kediye dönüştürdü - görünüşe göre Millicent'ın kılı meğer ona ait değilmiş.",
    935: "#56#$002Umarım Madam Pomfrey ona çok fazla soru sormaz. Neyse, sanırım Lockhart'la olan özel derse gitmeliyim...",
    936: "#59#$001Harry, duydun mu, Malfoy Büyük Salon'da ve herkesi düelloya davet ediyor.",
    937: "#5C#$003Neden içeri girip onunla düello yapmıyorsun Harry, duyduğuma göre epey iyiymişsin.",
    938: "#5F#$002Evet, hem henüz onu yenen çıkmadı.",
    939: "#62#$004Hadi Harry, onu yenebileceğinden eminim, o sinsi Slytherin suratındaki sırıtışı silmek harika olur!",

    # 940 - 959: Founder Duels & Beans/Cards with Fred and George
    940: "#15#$001Görünüşe göre bu yıl $Bitkibilim ve $Karanlık $Sanatlara $Karşı $Savunma alanında üstün başarı gösterenlere $Bina $Kupaları vereceklermiş. Onları $Gryffindor kazanırsa harika olur!",
    941: "#18#$003Onu ne kadar özlediğimi unutmuşum. Hadi Harry.",
    942: "#1B#$002Hadi ikiniz de acele edin, $Bitkibilim başlamak üzere. Ona da geç kalmak istemezsiniz.",
    943: "#1E#$004Vay canına! $Gryffindor $Ortak $Odası! Babama göndermek için birkaç fotoğraf çekeceğim.",
    944: "#21#$005Fotoğraf albümüme baksana Harry, masanın üzerinde. Benim fotoğraflarım sıradan fotoğraflar gibi değildir - fotoğraflarım büyülüdür!",
    945: "#24#$001Gizli $Kurucu $Düellolarını duydun mu hiç?",
    946: "#27#$004Tanıdığımız hiç kimse bütün kurucu düellocuları yenip Kurucular Kulesi'ne girmeyi başaramadı. İçeride ne olduğunu çok merak ediyoruz.",
    947: "#2A#$006Düelloların her birini açmak için belirli sayıda $Ünlü $Cadı $ve $Büyücü $kartına ihtiyacın olacak.",
    948: "#2D#$008İyi bir anlaşma: Bize $Elli $Bertie $Bott'un $Binbir $Çeşit $Fasulyesi ver, biz de karşılığında sana bir $Ünlü $Cadı $ve $Büyücü $kartı verelim.",
    949: "#30#$009Bize $Elli $Bertie $Bott'un $Binbir $Çeşit $Fasulyesi ver, biz de karşılığında sana bir $Ünlü $Cadı $ve $Büyücü $kartı verelim.",
    950: "#33#$002Arkamızda bir heykel var. Gizli $Kurucu $Düellolarının girişlerini bulmak için onu kullanabilirsin.",
    951: "#36#$003Hogwarts $Kurucu $Ünlü $Cadı $ve $Büyücü $kartı kazanmak için her kurucu bina düellocusunu yen. Hepsini topla ve özel Kurucular Kulesi'ne girebil.",
    952: "#39#$005İşte tam burada sen devreye giriyorsun Harry. Her düellocuyu yenip bütün $Kurucu $Büyücü $kartlarını kazanacak potansiyele sahip olduğunu düşünüyoruz.",
    953: "#3C#$007Herkes bilir ki $Ünlü $Cadı $ve $Büyücü $kartlarını bulmak çok zor olabilir. Bu yüzden sana beş tanesini satmaya razıyız Harry.",
    954: "#3F#$004Başardık!",
    955: "#42#$001Bir $Çikolata $Kurbağa yersen dayanıklılığının geri geldiğini biliyor muydun?",
    956: "#45#$002Evet Colin, biliyorum...",
    957: "#48#$002Harika! 50 tane $Binbir $Çeşit $Fasulye'n var! Al bakalım bir $Ünlü $Cadı $ve $Büyücü $kartı.",
    958: "#4B#$001Kusura bakma Harry ama bir $Ünlü $Cadı $ve $Büyücü $kartı istiyorsan bize $50 $Binbir $Çeşit $Fasulye vermelisin.",
    959: "#4E#$003Kusura bakma Harry ama daha fazla $Ünlü $Cadı $ve $Büyücü $kartı istiyorsan, onları $Hogwarts civarında gizlenmiş olarak bulman gerekecek!",

    # 960 - 976: House Cup Hourglasses & Valentine's Day
    960: "#8#$007Bu sırada bina puanı kum saatleri yavaş yavaş doluyor...",
    961: "#B#$002Ravenclaw",
    962: "#E#$003Hufflepuff",
    963: "#11#$001Slytherin",
    964: "#14#$004Gryffindor",
    965: "#17#$005Bina puanlarında Slytherin önde!",
    966: "#1A#$006Bina puanlarında Gryffindor önde!",
    967: "#1D#$008Bina Kupası için yarış devam ediyor...",
    968: "#20#$010Bina Kupası için yarış kızışıyor.",
    969: "#23#$011Sonunda, bakalım bu yılın Bina Kupası'nı kim kazanacak!",
    970: "#0#$004Gözleri taze turşu kurbağası kadar yeşil, saçları karatahta kadar kara. Keşke benim olsa, öyle ilahi ki, Karanlık Lord'u yenen kahraman.",
    971: "#5#$001Sevgililer Günü'n kutlu olsun, Harry!",
    972: "#8#$001Kaç kart aldın bakalım? Şimdiye dek ben sadece kırk altı tane aldım - ama gün daha yeni başladı.",
    973: "#B#$003Senin ve Hogwarts'taki diğer öğrenciler için küçük bir sürpriz hazırladım.",
    974: "#E#$004Benim sevimli, kart taşıyan aşk meleklerim!",
    975: "#11#$005Hey sen! 'Arry Potter! Dur orada! Sana iletecek müzikli bir mesajım var...",
    976: "#16#$001Sevgililer Günü kartları, ııığğh... Uzak dur benden.",

    # 977 - 1011: Gryffindor Password, Mudblood, Hagrid's Pumpkin Patch & Ingredients
    977: "#0#$005Incendio",
    978: "#A#$002Eee... Domuz Burnu... Caput Draconis...",
    979: "#D#$003Üzgünüm ama parola bu değil.",
    980: "#10#$005Ron, sen burada bekle, belki başka bir Gryffindor'lu geçer. Ben Hermione'yi bulayım, o parolayı bilir.",
    981: "#13#$001Ah, işte buradasın Harry! Hermione ile Ron çoktan Ölümgünü partime gittiler bile.",
    982: "#16#$002Hadi Harry, geç kalmak istemezsin!",
    983: "#19#$003Zindanlarda görüşürüz. Çabuk ol, kutlamaları kaçırmak istemezsin.",
    984: "#1F#$001Hadi, $Bitkibilim dışarıdaki seralardan birinde, gidelim!",
    985: "$018Doğu Kanadı",
    986: "#22#$008Mecbur muyuz?",
    987: "#25#$010Şey, o öyle düşünüyor gibi...",
    988: "#28#$001Nasıl hissediyorsun Ron?",
    989: "#2B#$002Yaşadığım sürece bir daha asla sümüklüböcek görmek istemiyorum. Bir dahaki sefere Malfoy'un hakkından kesin geleceğim. Hermione'ye nasıl Bulanık der?",
    990: "#2E#$004Evet ama bu kelime aklına gelebilecek en hakaretamiz şey. Bulanık, anne babası büyücü olmayan birine söylenebilecek son derece çirkin bir isimdir. Safkan oldukları için kendilerini herkesten üstün gören bazı büyücüler vardır.",
    991: "#31#$006Iyyk... Hâlâ sümüklüböceklerin tadını alabiliyorum. Sanırım gidip dişlerimi bir kez daha fırçalamam gerek...",
    992: "#34#$003Ron, sadece bir kelime alt tarafı.",
    993: "#37#$005Beni savunduğun için teşekkürler Ron - özellikle de asanın bu durumunda.",
    994: "#3A#$007Aman Tanrım! Saate bak - Profesör Lockhart'ın Karanlık Sanatlara Karşı Savunma dersine gitsek iyi olur.",
    995: "#3D#$009Cidden Harry. Profesör Lockhart'a karşı ne alıp veremediğin var anlamıyorum - olağanüstü bir öğretmen o!",
    996: "#40#$018Karanlık Sanatlara Karşı Savunma dersliği Yukarı Şato'da. Sana yolu göstereyim Harry.",
    997: "#43#$001Merhaba çocuklar. Acaba bana bir iyilik yapabilir misiniz?",
    998: "#46#$003Neredeyse Cadılar Bayramı geldi ve balkabağı tarlamı bahçe cüceleri bastı. Onlardan kurtulmama yardım edebilir misiniz?",
    999: "#49#$008$Sülükler mi - ııığh - iğrenç yaratıklar! Ama $ağaç $yılanı $derisi peşindeysen kulübemde biraz var. Bu ıvır zıvırı ödev için istiyorsun, öyle mi?",
    1000: "#4C#$010Pekâlâ o zaman Harry, seninle bir anlaşma yapalım: Balkabağı tarlamdaki şu cücelerden kurtul, ben de sana biraz $ağaç $yılanı $derisi vereyim.",
    1001: "#4F#$002Elbette Hagrid.",
    1002: "#52#$004Ben yardım ederim Hagrid - ama sanırım Ron'un yapması gereken bazı işler var.",
    1003: "#55#$006Biraz $düğümotu ve $karasu $otu bulmak gibi mi?",
    1004: "#58#$011Tamamdır Hagrid - anlaştık.",
    1005: "#5B#$005Var mıymış?",
    1006: "#5E#$007Ah, evet! $Ağaç $yılanı $derisini, $zarkanatlıları ve $sülükleri unutmadığından emin ol yeter.",
    1007: "#61#$009Iıı, evet doğru - ödev, şey için - İksir için...",
    1008: "#64#$001Harry! Crabbe, Goyle ve Malfoy $Büyük $Salon'dalar. $Düello $Kulübü'ne kaydolmuşlar. Dersi kim verecek çok merak ediyorum.",
    1009: "#67#$002Umarım $Lockhart değildir. Bir günde ondan fazlasıyla bıktım.",
    1010: "#6A#$001Harry, Ortak Oda'ya gerçekten girmemiz gerek.",
    1011: "#72#$004Olamaz! Şişman Hanım'ın portresinin parolasını bilmiyoruz, şimdi içeri giremeyeceğiz.",

    # 1012 - 1049: Lockhart's DADA Class, Verdimillious Duo & Chamber of Secrets Clue
    1012: "#0#$008Crispin Cronk",
    1013: "#3#$004Verdimillious",
    1014: "$001Uyarı! Uzak Durun! İçeride Tehlikeli Yaratıklar Var!",
    1015: "$002Gilderoy Lockhart'ın Odası.",
    1016: "$003Karanlık Sanatlara Karşı Savunma Malzeme Odası",
    1017: "$004Aşağı Şato",
    1018: "#8#$019Hazır mısın?",
    1019: "#B#$003Harika!",
    1020: "#E#$004Kusursuz!",
    1021: "#11#$007Çok havalı - tıpkı benim gibi!",
    1022: "#14#$001Vah vah...",
    1023: "#17#$002Tüh vah...",
    1024: "#1A#$009Olamaz...",
    1025: "#1D#$001Ah Harry, sonunda gelebildin. Zavallı Mrs Norris bir yana, genç Bay Creevey'nin taşlaşması korkunç bir haber.",
    1026: "#20#$002Yine de endişelenmeye gerek yok - Karanlık Sanatlara Karşı Savunma öğretmeniniz olarak günü ben kurtaracağım!",
    1027: "#23#$004Pahalı asam hareket ederken onu izle ve işaret ettiği sembollere bas!",
    1028: "#26#$006Bunu üç kez yaparsan $Verdimillious $Duo büyüsünü öğreneceksin!",
    1029: "#29#$004Bu kolay olanıydı. Hazır mısın?",
    1030: "#2C#$004Bir tane kaldı, hazırlan.",
    1031: "#2F#$004Bu son tekrar.",
    1032: "#32#$012Geçer not aldın. Aferin.",
    1033: "#35#$012Daha sonra tekrar gelirsen daha iyi bir not almaya çalışabilir ve özel bir ödül kazanabilirsin!",
    1034: "#38#$012$A notu aldın. Tebrikler!",
    1035: "#3B#$012Mükemmel - gerçekten mükemmel! Şimdi işe koyulalım...",
    1036: "#3E#$004$Petrificus $Totalus büyüsünü tekrar denemeye mi geldin? Bu sefer daha iyisini yapmalısın.",
    1037: "#41#$004Şimdiki notunu yükseltmek ister misin Harry?",
    1038: "#44#$004Tekrar denemek ister misin Harry?",
    1039: "#47#$012İşte hepsi bu kadar, Potter! Aferin!",
    1040: "#4A#$003Neredeyse Kafasız Nick! Olamaz!",
    1041: "#4D#$001Öğrendiğin büyüyü uygulamaya koyma vakti...",
    1042: "#50#$002Şimdi Harry, tam dolu bir $Verdimillious $Duo büyüsü yapmak için > butonunu basılı tut.",
    1043: "#53#$003Büyü yapıldığında sana karanlık büyüyle gizlenmiş nesneleri gösterecektir. Odadan çıkmak için bulduklarını kullan!",
    1044: "#56#$001Mükemmel Harry! Başaracağını biliyordum! Birkaç yıl sonra ayağımı denk almam gerekecek, yoksa işimi elimden alacaksın!",
    1045: "#59#$002Şimdi koş bakalım; yarın Sevgililer Günü ve çok özel bir şey planladım.",
    1046: "#5C#$001Şey... Bay Potter... Şu anda biraz meşgulüm.",
    1047: "#5F#$003Ah... şey... pekâlâ... Madem eminsin?",
    1048: "#62#$002Profesör, size vermem gereken bir bilgi var: Bence elli yıl önce canavarın öldürdüğü kız Mızmız Myrtle'dı, $Sırlar $Odası'nın girişinin nerede olduğunu o biliyor olabilir!",
    1049: "#66#$001Tuhaf, kapı neden kilitli? Başka bir yol bulsam iyi olur.",

    # 1050 - 1079: Library, Polyjuice Potion, Headless Hunt & Basilisk Voice
    1050: "$017Arka Hol",
    1051: "#2#$001Harry, Ron ile senin bu kadar sorumsuz olduğunuza inanamıyorum! Ölebilirdiniz, ya da daha kötüsü - okuldan atılabilirdiniz!",
    1052: "#5#$002Şişman Hanım'ın parolası 'Hotozlu kuş'. Tabii okula vaktinde gelmeyi başarabilseydiniz bunu bilirdiniz!",
    1053: "#8#$001Harry, karneni kontrol etmeyi sakın unutma.",
    1054: "#B#$003Sizin yerinizde olsam Snape sizi görmeden Ortak Oda'ya giderdim.",
    1055: "#E#$001Merhaba genç Harry Potter! Ne güzel bir gün!",
    1056: "#11#$002Mutlu görünüyorsun, Nick.",
    1057: "#14#$003Öyleyim Harry! Bugün Sir Patrick Delaney-Podmore'a bir mektup gönderdim. Kafasızlar Avı'na katılmak için yaptığım başvuru.",
    1058: "#17#$004Aslına bakarsan arkadaşın Hermione Granger'a da anlatıyordum, Kafasızlar Avı'na katılmak bir süredir benim hayalimdi.",
    1059: "#1A#$005Hermione burada mı?",
    1060: "#1D#$006Elbette! Ama dikkatli ol, etrafta oldukça yaramaz kitaplar var. Haddini bildirmek için Flipendo büyünü kullan!",
    1061: "$006Ortak Odaya Gidildi",
    1062: "$005Çataldil 1'i Tamamla",
    1063: "#20#$006Sanırım haklı olabilirsin - ve eğer öyleyse, bunu kanıtlayabileceğimiz bir yol biliyorum: Çoközlü İksir.",
    1064: "#23#$010Çoközlü İksir bir insanı bir başkasına dönüştürebilir - bir Slytherin'liye bile. Malfoy'u kandırıp varis olduğunu itiraf ettirebiliriz.",
    1065: "#26#$010$Çoközlü $İksir yapmak için birkaç malzemeye ihtiyacımız olacak: $zarkanatlı sinekler, $sülükler, $karasu $otu, $düğümotu, $çiftboynuz $boynuzu ve $kıyılmış $ağaç $yılanı $derisi.",
    1066: "#29#$014Ben de $çiftboynuz $boynuzunu alırım. Siz ikiniz İksir dersine gitseniz iyi olur. Çoközlü İksir'i hazırlayacak bir yer bulduğumda $Hedwig'i göndereceğim.",
    1067: "#2C#$011Saate baksanıza! Siz ikiniz İksir dersine gitseniz iyi olur. Ben bir kazan bulmaya gidiyorum. Dersten sonra yine burada buluşalım.",
    1068: "#2F#$001Draco Malfoy'un Slytherin'in Varisi olduğuna adım gibi eminim.",
    1069: "#32#$007Çok-ne?",
    1070: "#35#$012Tamam, ben $düğümotu ve $karasu $otunu alırım. Harry, sen de $sülükleri, $zarkanatlı $sinekleri ve $kıyılmış $ağaç $yılanı $derisini alabilirsin.",
    1071: "$001Kullanılmıyor",
    1072: "$002Kullanılmıyor",
    1073: "$003Kullanılmıyor",
    1074: "#38#$002Bırak senin için açabilecek miyim bir bakayım, Hermione.",
    1075: "#3B#$003Açıl!",
    1076: "#0#$001Gel, gel bana...",
    1077: "#3#$002Seni öldüreyim...",
    1078: "#6#$003Seni parçalayayım...",
    1079: "#9#$004Seni yırtayım...",
}


def validate_and_build():
    batch_file = "/home/kadir/PS1-Localization-Engine/translations/batches/batch_2.json"
    output_file = "/home/kadir/PS1-Localization-Engine/translations/batches/batch_2_tr.json"

    with open(batch_file, "r", encoding="utf-8") as f:
        items = json.load(f)

    assert len(items) == 360, f"Expected 360 items, got {len(items)}"

    out_items = []
    missing = []
    tag_errors = []
    glyph_errors = []

    for item in items:
        item_id = item["id"]
        en = item["en"]

        if item_id not in BATCH_2_TRANSLATIONS:
            missing.append(item_id)
            continue

        tr = BATCH_2_TRANSLATIONS[item_id]
        if not tr or not tr.strip():
            missing.append(item_id)
            continue

        # Extract leading tags from EN (e.g. #48#$022 or $004 or #0#$002)
        cue_m = re.match(r"^(#[0-9A-Fa-f]+#\$[0-9]{3}|\$[0-9]{3}|#[0-9A-Fa-f]+#\$[0-9]+)", en)
        if cue_m:
            expected_prefix = cue_m.group(1)
            if not tr.startswith(expected_prefix):
                tag_errors.append((item_id, en, tr, f"Missing prefix {expected_prefix}"))

        # Verify controller glyphs
        for glyph in ["{", "}", "[", "]", ">", "<", "@"]:
            if glyph in en and glyph not in tr:
                glyph_errors.append((item_id, en, tr, f"Missing glyph {glyph}"))

        out_items.append({
            "id": item_id,
            "en": en,
            "tr": tr
        })

    if missing:
        print(f"Error: Missing translations for {len(missing)} items: {missing[:10]}")
        return False

    if tag_errors:
        print(f"Error: Tag mismatch in {len(tag_errors)} items:")
        for err in tag_errors[:5]:
            print(err)
        return False

    if glyph_errors:
        print(f"Error: Glyph mismatch in {len(glyph_errors)} items:")
        for err in glyph_errors[:5]:
            print(err)
        return False

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(out_items, f, ensure_ascii=False, indent=2)

    print(f"Successfully generated {output_file} with {len(out_items)} entries.")
    return True


if __name__ == "__main__":
    validate_and_build()
