# EcoPrune

EcoPrune, Windows bilgisayarında kullanıcının seçtiği klasörü salt okunur tarayarak aynı içeriğe sahip dosyaları bulmak için geliştirilmiş bir Python ve Streamlit prototipidir. Proje, Yeşil Gelecek Hackathonu'nun 2.3 teması kapsamında sunulmak üzere hazırlanmıştır. Hackathon hakkında bilgi: [Yeşil Gelecek Hackathonu](https://arti.arel.edu.tr/yesil-gelecek-hackathonu-2026/).

## Şu anda çalışan özellikler

- Seçilen klasörü ve alt klasörlerini salt okunur tarar.
- Önce dosya boyutlarına göre gruplar; aynı boyutlu adaylarda SHA-256 hesaplar, ardından içeriği 1 MiB parçalarla karşılaştırarak kesin eşitliği doğrular. Büyük dosyaları belleğe tamamen yüklemez.
- Sembolik bağlantıları ve Windows junction/reparse noktalarını izlemez. Hard linklerle aynı fiziksel dosyanın yeniden sayılmasını önler.
- Okunamayan, tarama sırasında değişen veya doğrulanamayan öğeleri raporlar.
- Taranan dosya sayısını, toplam mantıksal boyutu ve her kopya grubunda bir dosya korunursa azaltılabilecek mantıksal veri miktarını gösterir.
- Her grupta korunacak dosyanın seçilmesini; adayların işaretlenmesini; bu tarama için gerekli olduğu belirtilen grupların işlem dışında tutulmasını sağlar.
- Kök dizine göreli korunan klasör yollarını destekler. Korunan klasörler listelenir ancak dosyaları işlem adayı seçilemez. Yol ilişkisi metinsel önekle değil, yol bileşenleriyle denetlenir.
- Seçimlerin dosya işlem önizlemesini verir. Bu sürüm hiçbir dosyayı taşımaz veya silmez.

## Boyutların anlamı

**Toplam mantıksal boyut**, hard linkler hariç taramada sayılan dosyaların boyutlarının toplamıdır. Aynı içeriğe sahip ayrı dosyalar da bu toplama dahildir. **Azaltılabilecek mantıksal veri**, her kopya grubunda bir dosya korunursa tekrar eden dosya boyutlarının toplamıdır. **Seçilen adayların toplam mantıksal boyutu** ise önizlemede işaretlenen adayların boyut toplamıdır. Bu ölçümler gerçek fiziksel disk alanı kazanımını veya karbon tasarrufunu göstermez.

## Planlanan özellikler

Bu maddeler mevcut sürümde uygulanmamıştır:

- Geri alınabilir karantina ve geri yükleme.
- Sonraki taramalarda yeniden oluşan kopyaların takibi.
- Ölçülen değerlerle tahminleri açıkça ayıran çevresel etki modeli.
- AI destekli özellikler ve karbon hesabı.

## Windows 11 ve Python 3.12 kurulumu

Proje klasöründe PowerShell açın:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

PowerShell betik ilkesi sanal ortamı etkinleştirmeyi engellerse yalnızca açık olan oturum için `Set-ExecutionPolicy -Scope Process Bypass` çalıştırın. Alternatif olarak sanal ortamı etkinleştirmeden `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` kullanabilirsiniz.

## Demo

Demo klasörü sentetik metin ve CSV dosyalarından oluşur; farklı adlarla aynı içerikleri, aynı adla farklı içerikleri ve benzersiz dosyaları içerir. Varsayılan tarama yolu proje içindeki `demo` klasörüdür. Eksik demo dosyalarını oluşturmak için:

```powershell
python .\seed_demo.py
```

Script, aynı adlı mevcut dosyaların üzerine yazmaz. Arayüzde **Klasörü tara** düğmesine basın. Kopya grubunu inceleyin, korunacak dosyayı belirleyin ve isterseniz işlem adayı kutusunu seçin. Korunacak klasörleri taranan köke göreli olarak, her satıra bir yol şeklinde girin; örneğin `kaynak`.

## Testler

```powershell
python -m unittest discover -s tests -v
```

Testler kesin kopya tespitini, aynı adlı farklı içerikleri, boyutları, hard linkleri, dosyaların değişmeden kalmasını, korunan klasör sınırlarını ve işlem önizlemesi kurallarını kapsar. Windows ortamında sembolik bağlantı oluşturma yetkisi yoksa bu testi atlayabilir.

## Uygulamayı çalıştırma

```powershell
streamlit run .\app.py
```

Arayüz yerel Streamlit sunucusunda açılır. Tarama için klasörün tam yolunu yazın veya varsayılan demo klasörünü kullanın. Klasör değiştiğinde ve yeni tarama başladığında önceki tarama ile seçimler temizlenir.

## Gizlilik

Tarama seçilen yerel klasörde yapılır. Uygulama dosya içeriklerini buluta ya da harici bir AI servisine göndermez; kopya sonuçlarını veya işlem kayıtlarını diske kaydetmez. Streamlit kullanım istatistikleri proje yapılandırmasında kapalıdır. Kullanıcının seçtiği klasör proje klasörünün dışında kalabilir; tarama dosya içeriğini değiştirmez.

## Sınırlamalar

- Klasör seçimi metin alanıyla yapılır; yerel dosya seçici yoktur.
- Dosya sistemi değişirken oluşabilecek tüm yarış koşullarını önlemek mümkün değildir. Tespit edilen değişiklikler raporlanır; bazı dosya sistemlerinde aynı boyut ve değiştirilme zamanını koruyan eşzamanlı değişiklikler saptanamayabilir.
- Junction ve sembolik bağlantı atlama denetimleri Windows davranışları içindir. Özel ağ sürücüleri, sanal dosya sistemleri ve erişim izinleri farklı sonuç verebilir.
- Tarama ve önizleme sırasında silme, taşıma, karantina, bulut bağlantısı, AI özelliği veya karbon hesabı yoktur.

## Lisans

MIT lisansı için [LICENSE](LICENSE) dosyasına bakın. Telif hakkı sahibi adı ekip tarafından henüz doğrulanmadığı için dosyada yer tutucu bulunuyor; yayımlamadan önce gerçek hak sahibi bilgisiyle değiştirilmelidir.
