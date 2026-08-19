# SpinyOS Uygulama Tarafi Egitim Raporu (TR)

## 1. Amac

Bu raporun amaci, ROS2 ve orkestrator hakkinda hicbir sey bilmeyen bir istemciyi, SpinyOS orkestratoru ile guvenli ve dogru sekilde mesajlasacak seviyeye cikarmaktir.

Bu dokuman bir "egitim plani + teknik sozlesme + test plani" olarak tasarlandi.

## 2. Kisa Cevap: Bu Rapor Yeterli mi?

Evet, su sartla yeterli:

- Egitim asamalari sirasiyla uygulanacak.
- Her asamada verilen dogrulama testleri gecilecek.
- Istemci, burada verilen protokol sozlesmesine birebir uyacak.

Eger bu 3 kosul saglanirsa, sifirdan gelen bir sistemin entegrasyonu kavramasi ve calisir hale gelmesi beklenir.

## 3. Sinirlar ve Gercek Durum

Su an platformda hazir olanlar:

- WebSocket v1 komut kanali
- Token + role bazli yetkilendirme
- Node yonetimi: list, status, start, stop, restart
- Gozlem: graph snapshot, node io inspect, stream subscribe/unsubscribe, capture window
- Uzak cihaz yonetimi: peer list ve peer node actionlari

Su an platformda dogrudan olmayan kisim:

- Uygulama tarafinda rclpy/rclcpp ile typed ROS bridge, bu raporun disinda uygulama kodu olarak ayrica yazilir.

## 4. Mimari Cerceve

Yonetim kanali asagidaki gibi calisir:

1. Uygulama -> Orkestrator: WebSocket command
2. Orkestrator -> ROS2: ros2 CLI ve process lifecycle islemleri
3. Orkestrator -> Uygulama: ack/progress/event/error mesajlari

Ana ilke:

- Uygulama, ROS2 icine dogrudan gomulmeden once orkestrator API uzerinden kontrol ve gozlem yapar.
- Sonra gerekirse rclpy/rclcpp uygulama node katmani eklenir.

## 5. Protokol Sozlesmesi (Mutlaka Ezberlenmeli)

### 5.1 Istek Zarfi

Tum istekler bu formda olmalidir:

```json
{
  "v": 1,
  "type": "command",
  "action": "node.status",
  "requestId": "benzersiz-id",
  "payload": {
    "nodeId": "demo_talker"
  }
}
```

Zorunlu kurallar:

- v kesinlikle 1 olmali
- type kesinlikle command olmali
- action desteklenen listede olmali
- requestId bos olmamali
- payload daima json object olmali

### 5.2 Cevap Tipleri

Orkestrator 4 tip mesaj dondurebilir:

- ack: is kabul edildi
- progress: uzun iste ara durum
- event: basarili sonuc
- error: hata

### 5.3 Hata Zarfi

Hata payload yapisi:

```json
{
  "operationId": null,
  "errorCode": "WS_SCHEMA_INVALID",
  "retryable": false,
  "message": "acik hata metni",
  "details": {}
}
```

Retry karari:

- retryable true ise geri deneme stratejisi calistirilir
- retryable false ise istemci hatayi yukari katmana raporlar

## 6. Yetki Modeli

### 6.1 Roller

- viewer: sadece gozlem ve listeleme agirlikli
- operator: node kontrolu + paket + peer kontrol
- admin: operator ile ayni aksiyon seti

### 6.2 Pratik Kural

Istemci iki token ile calisabilir:

- read token (viewer)
- control token (operator)

Entegrasyon tavsiyesi:

- Okuma ekranlari viewer token kullansin
- Start/stop/restart gibi isler operator token kullansin

## 7. Desteklenen Aksiyonlar ve Beklenen Payload

### 7.1 Node

- node.list: payload {}
- node.status: payload {} veya {"nodeId":"..."}
- node.start: payload {"nodeId":"..."}
- node.stop: payload {"nodeId":"...","graceSec":5}
- node.restart: payload {"nodeId":"..."}

### 7.2 Gozlem

- graph.snapshot: payload {}
- node.io.inspect: payload {"nodeName":"/..."} veya {"nodeId":"..."}
- capture.window: payload {"durationSec":5,"sampleIntervalSec":1,"nodeNames":["/node"]}
- stream.subscribe: payload {"nodeId":"...","fields":["running","pid","ros2State"],"rateHz":1.0}
- stream.unsubscribe: payload {"subscriptionId":"..."}

### 7.3 Uzak Cihaz

- peer.list: payload {}
- peer.node.status: payload {"peerId":"...","nodeId":"...","timeoutSec":15}
- peer.node.start: payload {"peerId":"...","nodeId":"...","timeoutSec":15}
- peer.node.stop: payload {"peerId":"...","nodeId":"...","graceSec":5,"timeoutSec":15}
- peer.node.restart: payload {"peerId":"...","nodeId":"...","timeoutSec":15}

## 8. Istemci Davranis Kurallari

Istemci her command icin su algoritmayi izlemeli:

1. requestId uret
2. command mesaji gonder
3. ayni requestId ile gelen mesajlari topla
4. ack gelirse beklemeye devam et
5. progress gelirse UI durumunu guncelle
6. event gelirse isi basarili tamamla
7. error gelirse retryable alanina gore karar ver
8. timeout olursa istemci tarafi timeout hatasi olustur

Timeout stratejisi:

- Kisa aksiyonlar: 10-20 sn
- Capture ve uzun akislar: 60-120 sn

Retry stratejisi:

- retryable true: exponential backoff (1s, 2s, 4s, max 5 deneme)
- retryable false: tekrar deneme yapma

## 9. Durum Makinesi

### 9.1 Node Is Akisi

- start:
  - beklenen sonuc: event node.start + node snapshot running true
- stop:
  - beklenen sonuc: event node.stop + state stopped
- restart:
  - beklenen sonuc: event node.restart + node snapshot

### 9.2 Stream Is Akisi

- subscribe -> event stream.subscribe (subscriptionId)
- ardindan stream.data eventleri surekli gelir
- unsubscribe -> event stream.unsubscribe

## 10. Sifirdan Egitim Programi

Bu bolum dogrudan "hicbir sey bilmeyen" bir sistem icin adim adim ogrenme sirasidir.

### Faz 0: Sozluk Ogrenimi

Istemciye su terimleri ogret:

- nodeId: manifestteki mantiksal node anahtari
- nodeName: ROS graph uzerindeki ad
- requestId: komut-cagri esleme kimligi
- ack/progress/event/error: cevap turleri
- role: tokenin izin seviyesi

Basari olcutu:

- Istemci bu terimleri karistirmadan aciklayabiliyor.

### Faz 1: Sadece Okuma

Yapilacaklar:

- node.list
- node.status
- graph.snapshot
- node.io.inspect

Basari olcutu:

- Istemci running, pid, ros2State alanlarini dogru yorumlar.

### Faz 2: Kontrol

Yapilacaklar:

- node.start
- node.stop
- node.restart

Basari olcutu:

- Start sonrasi running true gorulmeli.
- Stop sonrasi running false gorulmeli.

### Faz 3: Akis

Yapilacaklar:

- stream.subscribe
- stream.data ayiklama
- stream.unsubscribe

Basari olcutu:

- Istemci sample verilerini zaman etiketi ile kaydedebilmeli.

### Faz 4: Teshis

Yapilacaklar:

- capture.window
- artifact path kaydi
- warning analizi

Basari olcutu:

- En az bir capture artifact'i parse edip raporlayabilmeli.

### Faz 5: Peer

Yapilacaklar:

- peer.list
- peer.node.status/start/stop/restart

Basari olcutu:

- allowRemoteControl false ise islemi engelleyip dogru hata siniflandirmali.

## 11. Ornek WebSocket Senaryolari

### 11.1 Node Start

Istek:

```json
{
  "v": 1,
  "type": "command",
  "action": "node.start",
  "requestId": "req-001",
  "payload": {"nodeId": "demo_talker"}
}
```

Muhtemel cevap sirasi:

1. ack node.start
2. event node.start

### 11.2 Capture Window

Istek:

```json
{
  "v": 1,
  "type": "command",
  "action": "capture.window",
  "requestId": "req-002",
  "payload": {
    "durationSec": 5,
    "sampleIntervalSec": 1,
    "nodeNames": ["/spiny/demo/spiny_demo_talker"]
  }
}
```

Muhtemel cevap sirasi:

1. ack capture.window
2. birden fazla progress capture.window
3. event capture.window (artifactPath ile)

## 12. Hata Sozlugu ve Duzeltme Eslestirmesi

- WS_AUTH_INVALID_TOKEN:
  - Sebep: token yok/gecersiz
  - Cozum: dogru token veya auth dosyasi

- WS_AUTH_FORBIDDEN_ROLE:
  - Sebep: rol bu aksiyonu yapamaz
  - Cozum: operator/admin token kullan

- WS_SCHEMA_INVALID:
  - Sebep: istek zarfi hatali
  - Cozum: action/requestId/payload formatini duzelt

- NODE_NOT_FOUND:
  - Sebep: nodeId manifestte yok
  - Cozum: node.list ile gecerli nodeId cek

- ROS2_GRAPH_FAILED:
  - Sebep: ros2 graph komutlari basarisiz
  - Cozum: hedefte ros2 CLI, ortam ve node durumunu kontrol et

- PEER_NOT_FOUND / PEER_CONTROL_DISABLED / PEER_ACTION_DENIED / PEER_UNREACHABLE:
  - Sebep: peer kaydi yok, policy kapali, aksiyon izinli degil veya erisilemiyor
  - Cozum: /etc/spiny/orchestrator-peers.json ve ag erisimi kontrol

## 13. Guvenlik Gereksinimleri

- Tokeni loglama
- Tokeni istemci tarafi plain text dosyada saklamama
- UI tarafinda role gore buton ac/kapa (ornek: viewer ile start butonu pasif)
- Peer kontrolu varsayilan kapali olmasi tercih edilir

## 14. Uretim Hazirlik Kontrol Listesi

Asagidaki tum maddeler EVET olmadan canliya cikma:

- En az 24 saat stream abonelik testi yapildi
- En az 100 ardil node start/stop dongusu hatasiz tamamlandi
- Capture artifact parse testi gecildi
- Retry ve timeout davranisi test edildi
- Peer control policy negatif testleri gecildi
- Hatali payload testlerinde istemci cokusuz kaldi

## 15. Onerilen Test Matrisi

- Fonksiyonel:
  - node list/status/start/stop/restart
  - graph snapshot
  - io inspect
  - stream subscribe/data/unsubscribe
  - capture window
  - peer list ve peer node actionlari

- Negatif:
  - gecersiz token
  - yetkisiz rol
  - gecersiz payload
  - olmayan node
  - peer timeout

- Dayaniklilik:
  - ani websocket kesilmesi
  - tekrar baglanma
  - paralel coklu requestId yuklenmesi

## 16. Uygulama Ekipleri Icin Is Dagilimi

- Protokol Adapter Katmani:
  - websocket baglanti, requestId, timeout, retry

- Domain Katmani:
  - node yonetimi use-case'leri
  - stream ve capture analiz use-case'leri

- UI Katmani:
  - role bazli yetki gorunurlugu
  - progress ve error durum cizelgesi

- Test Katmani:
  - sahte orchestrator ile contract test
  - cihaz uzeri e2e smoke test

## 17. Cok Kisa Baslangic Rehberi

1. Once sadece viewer token ile oku
2. Sonra operator token ile tek bir demo node start/stop et
3. Sonra stream watch ile veri akisina gec
4. Sonra capture al
5. Sonra peer testlerine gec

Bu sirayla gidilirse ogrenme egrisi en dusuk olur.

## 18. Sonuc

Bu rapor, sifirdan gelen bir istemciyi "kavrama" seviyesinden "guvenli calistirma" seviyesine tasimak icin yeterli bir egitim omurgasi sunar.

Ek not:

- Bu rapor, mevcut yonetim kanalini ogretir.
- Uygulama icinde dogrudan ROS typed mesajlasma (rclpy/rclcpp) bir sonraki implementasyon adimidir.
