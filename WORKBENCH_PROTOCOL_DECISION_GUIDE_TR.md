# VS Code Workbench - Orchestrator Karar ve Veri Akis Kilavuzu (TR)

Bu kilavuz, uygulama tarafinda hangi ozelliklerin tekrar gelistirilmemesi gerektigini ve mevcut protokol ile verinin nasil cekilip gonderilecegini aciklar.

Not:
- Bu repository icinde sistem.md dosyasi bulunmuyor.
- Bu nedenle bu dokuman, mevcut kod gercekligine gore olusturulmus "uygulama entegrasyon referansi"dir.

## 1) Hangi Maddeler Eklenmemeli, Neden?

Asagidaki maddeler backlog'a yeni is olarak tekrar eklenmemeli, cunku sistemde zaten mevcut:

| Madde | Durum | Neden tekrar eklenmemeli |
| :--- | :--- | :--- |
| graph.snapshot | ZATEN VAR | ROS2 graph (nodes/topics/services/actions) cikiyor. Yeni gelistirme yerine test/izleme gerekir. |
| node.io.inspect | ZATEN VAR | Node bazli io endpoint ve tipleri donuyor. Yeniden yazmak yerine contract testi yeterli. |
| capture.window | ZATEN VAR | Time-window ornekleme, progress ve artifact path uretiyor. |
| managed lifecycle destegi | TEMEL OLARAK VAR | managed modda configure/activate ve stopta deactivate/shutdown uygulanmis. |

Bunlar icin yapilacak dogru is:
- Yeni endpoint acmak degil
- Mevcut endpointleri UI tarafinda dogru kullanmak
- Contract ve regress testlerini guclendirmek

## 2) Hangi Madde Gercekten Eklenmeliydi?

- user.info
  - Neden gerekli: istemci baglandiginda rol ve izinleri net okumak icin
  - Durum: EKLENDI

## 3) Veri Nasil Cekilir? (Read Path)

### 3.1 Kimlik ve Yetki

1. WebSocket ac:
   - ws://<host>:8765?token=<TOKEN>
2. Baglanti acildiginda connect event gelebilir.
3. Rol/izin icin net okuma yap:
   - action: user.info

Istek:

```json
{
  "v": 1,
  "type": "command",
  "action": "user.info",
  "requestId": "req-user-1",
  "payload": {}
}
```

### 3.2 Node Durumu Cekme

- Tum node'lar:

```json
{
  "v": 1,
  "type": "command",
  "action": "node.status",
  "requestId": "req-status-all",
  "payload": {}
}
```

- Tek node:

```json
{
  "v": 1,
  "type": "command",
  "action": "node.status",
  "requestId": "req-status-1",
  "payload": { "nodeId": "demo_talker" }
}
```

### 3.3 Graph ve I/O Cekme

- Graph:

```json
{
  "v": 1,
  "type": "command",
  "action": "graph.snapshot",
  "requestId": "req-graph-1",
  "payload": {}
}
```

- Node I/O:

```json
{
  "v": 1,
  "type": "command",
  "action": "node.io.inspect",
  "requestId": "req-io-1",
  "payload": { "nodeName": "/spiny/demo/spiny_demo_talker" }
}
```

### 3.4 Gercek Zamanli Veri Cekme (Stream)

Abonelik ac:

```json
{
  "v": 1,
  "type": "command",
  "action": "stream.subscribe",
  "requestId": "req-sub-1",
  "payload": {
    "nodeId": "demo_talker",
    "fields": ["running", "pid", "ros2State"],
    "rateHz": 1.0
  }
}
```

Gelen stream mesaji envelope + payload seklindedir:

```json
{
  "v": 1,
  "type": "event",
  "action": "stream.data",
  "requestId": null,
  "ts": "2026-04-10T12:00:00.000000+00:00",
  "deviceId": "spiny-...",
  "role": "viewer",
  "payload": {
    "subscriptionId": "sub-uuid",
    "nodeId": "demo_talker",
    "ts": "2026-04-10T12:00:00.000000+00:00",
    "data": {
      "running": true,
      "pid": 1234,
      "ros2State": "active"
    }
  }
}
```

Abonelik kapat:

```json
{
  "v": 1,
  "type": "command",
  "action": "stream.unsubscribe",
  "requestId": "req-unsub-1",
  "payload": { "subscriptionId": "sub-uuid" }
}
```

## 4) Veri Nasil Gonderilir? (Write Path)

Yazma islemleri node kontrol aksiyonlaridir:

- node.start
- node.stop
- node.restart
- peer.node.start
- peer.node.stop
- peer.node.restart

Ornek start:

```json
{
  "v": 1,
  "type": "command",
  "action": "node.start",
  "requestId": "req-start-1",
  "payload": { "nodeId": "demo_talker" }
}
```

Ornek stop:

```json
{
  "v": 1,
  "type": "command",
  "action": "node.stop",
  "requestId": "req-stop-1",
  "payload": { "nodeId": "demo_talker", "graceSec": 5 }
}
```

## 5) UI Kurallari - Dogru Oncelik Sirasi

Renk/oncelik algoritmasi su sekilde olmalidir:

1. En yuksek oncelik: error mesaji varsa KIRMIZI
2. Sonra stream.data degerleri:
   - running true veya ros2State active -> YESIL
   - running false veya ros2State inactive/unconfigured -> SARI
3. Veri yok/timeout -> GRI veya UNKNOWN

Bu siralama onemlidir; error her zaman diger durumlari override etmelidir.

## 6) Istemci Ic Mimari Onerisi

UI ile WebSocketi dogrudan baglamayin, adapter katmani kullanin:

- Transport Katmani:
  - WebSocket ac/kapat
  - requestId uret
  - timeout/retry

- Protocol Adapter:
  - Envelope parse
  - ack/progress/event/error ayrimi
  - action bazli handler dispatch

- Domain Store:
  - nodeStateMap
  - streamSubscriptions
  - lastErrors

- UI:
  - sadece domain store dinler

## 7) Retry ve Timeout Politikasi

- retryable true:
  - 1s -> 2s -> 4s backoff, max 3-5 deneme
- retryable false:
  - yeniden deneme yapma, hatayi kullaniciya goster

Onerilen timeoutlar:

- user.info, node.status: 10-15 sn
- node.start/stop/restart: 15-30 sn
- capture.window: 60-120 sn

## 8) Hangi Veriyi Nereden Cekmeli?

- Yetki/izin: user.info
- Toplu durum: node.status (payload bos)
- Topoloji: graph.snapshot
- Port/topic detay: node.io.inspect
- Surekli kucuk metrik: stream.subscribe + stream.data
- Zamana yayili artifact: capture.window

## 9) Kisa Entegrasyon Kontrol Listesi

- user.info basarili mi?
- node.status ile tum node listesi geliyor mu?
- stream.subscribe sonrasi stream.data akiyor mu?
- node.start/stop sonrasi durum degisimi goruluyor mu?
- error mesaji geldiginde UI kirmiziya geciyor mu?
- unsubscribe sonrasi stream kesiliyor mu?

## 10) Sonuc

Bu yaklasimla:

- Zaten var olan endpointleri tekrar gelistirme maliyeti ortadan kalkar.
- UI tarafi gercek protokole birebir oturur.
- Bakim maliyeti dusuk, davranis daha tahmin edilebilir olur.
