# SpinyOS Orchestrator Baglanti ve Yonetim Kilavuzu (TR)

Bu dokuman, uygulamanin SpinyOS orkestratorune nasil baglanacagini ve node/graph/stream/peer yonetimini nasil yapacagini anlatir.

Detayli egitim raporu (sifirdan baslayan istemci icin):

- APP_INTEGRATION_TRAINING_REPORT_TR.md
- sistem.md

## 1) Kapsam ve Gercek Durum

Su an sistemde uygulama ile haberlesme ve yonetim icin bunlar hazir:

- WebSocket tabanli orkestrator API (token ve rol bazli yetkilendirme)
- spinyctl ile hazir istemci komutlari
- Node list/status/start/stop/restart
- ROS2 graph snapshot
- Node I/O inspect
- Capture window (zamana yayili snapshot)
- Selective stream subscribe/unsubscribe/watch
- Peer (uzak cihaz) list ve uzaktan node kontrolu

Onemli not:
- Bu asamada ana model, yonetim ve gozlem odaklidir.
- Uygulama icinde dogrudan rclpy ile typed publish/subscribe bridge yazimi ayri bir app gelistirme adimidir.

## 2) Hedef Cihazda On Kosullar

Cihazda asagidakileri dogrula:

```bash
spinyctl orchestrator service status --json
spinyctl orchestrator policy --json
spinyctl orchestrator nodes --details --json
```

Beklenen temel dosyalar:

- /etc/spiny/orchestrator-auth.json
- /etc/spiny/orchestrator-policy.json
- /etc/spiny/orchestrator-manifest.json
- /etc/spiny/orchestrator-peers.json

## 3) Kimlik Dogrulama ve Roller

Orkestrator token ile calisir.

- Viewer: listeleme/gozlem (`node.list`, `node.status`, `graph.snapshot`, `node.io.inspect`, `capture.window`, `stream.subscribe`, `stream.unsubscribe`, `peer.list`, `peer.node.status`)
- Operator: Viewer + node start/stop/restart + peer start/stop/restart + paket aksiyonlari
- Admin: Operator ile ayni aksiyon seti

spinyctl token secme sirasi:

1. `--token` verildi ise onu kullanir
2. Degilse `--auth-file` (varsayilan `/etc/spiny/orchestrator-auth.json`) icinden role uygun token arar

## 4) En Kolay Baglanti: spinyctl ile

Varsayilan URL: `ws://127.0.0.1:8765`

Genel kalip:

```bash
spinyctl orchestrator <alt-komut> ... --json --token <TOKEN>
```

Ornekler:

```bash
# Node
spinyctl orchestrator node list --json --token <TOKEN>
spinyctl orchestrator node status demo_talker --json --token <TOKEN>
spinyctl orchestrator node start demo_talker --json --token <TOKEN>
spinyctl orchestrator node stop demo_talker --grace-sec 3 --json --token <TOKEN>
spinyctl orchestrator node restart demo_talker --json --token <TOKEN>

# Graph ve I/O
spinyctl orchestrator graph snapshot --json --token <TOKEN>
spinyctl orchestrator io /spiny/demo/spiny_demo_talker --json --token <TOKEN>
spinyctl orchestrator user info --json --token <TOKEN>

# Capture
spinyctl orchestrator capture window --duration-sec 5 --sample-interval-sec 1 --json --token <TOKEN>
spinyctl orchestrator capture window --duration-sec 10 --node-name /spiny/demo/spiny_demo_talker --json --token <TOKEN>

# Stream
spinyctl orchestrator stream watch demo_talker --seconds 10 --rate-hz 1 --field running --field pid --field ros2State --json --token <TOKEN>

# Peer
spinyctl orchestrator peer list --json --token <TOKEN>
spinyctl orchestrator peer status peer-example demo_talker --json --token <TOKEN>
spinyctl orchestrator peer start peer-example demo_talker --json --token <TOKEN>
spinyctl orchestrator peer stop peer-example demo_talker --grace-sec 3 --json --token <TOKEN>
spinyctl orchestrator peer restart peer-example demo_talker --json --token <TOKEN>
```

Faydali opsiyonlar:

- `--url ws://IP:8765`
- `--timeout <sn>`
- `--auth-file <path>`

## 5) Dogrudan WebSocket ile Baglanti (Uygulama Tarafi)

URL uzerinden token tasima:

- `ws://<host>:8765?token=<TOKEN>`

Istek zarfi:

```json
{
  "v": 1,
  "type": "command",
  "action": "node.status",
  "requestId": "<uuid>",
  "payload": {
    "nodeId": "demo_talker"
  }
}
```

Not:
- Basarili baglantida zorunlu bir "welcome" mesaji bekleme.
- Sunucu ayni `requestId` ile `ack`, `progress`, `event` veya `error` donebilir.

Mesaj tipleri:

- `ack`: is kabul edildi
- `progress`: uzun suren islerde ara durum
- `event`: basarili sonuc
- `error`: hata

Baglanti acildiginda sunucu ayrica `action: connect` ile bir `event` mesaji gonderir.

## 6) Aksiyonlar ve Payload Ozetleri

### Node

- `node.list`
  - payload: `{}`
- `node.status`
  - payload: `{}` veya `{ "nodeId": "demo_talker" }`
- `node.start`
  - payload: `{ "nodeId": "demo_talker" }`
- `node.stop`
  - payload: `{ "nodeId": "demo_talker", "graceSec": 5 }`
- `node.restart`
  - payload: `{ "nodeId": "demo_talker" }`

### User

- `user.info`
  - payload: `{}`
  - sonuc: `role`, `permissions`, `deviceId`

### Graph

- `graph.snapshot`
  - payload: `{}`
  - sonuc: `graph.nodes`, `graph.topics`, `graph.services`, `graph.actions`, `managedNodes`

### Node I/O

- `node.io.inspect`
  - payload: `{ "nodeName": "/spiny/demo/spiny_demo_talker" }`
  - alternatif: `{ "nodeId": "demo_talker" }`

### Capture

- `capture.window`
  - payload:

```json
{
  "durationSec": 5,
  "sampleIntervalSec": 1,
  "nodeNames": ["/spiny/demo/spiny_demo_talker"]
}
```

### Stream

- `stream.subscribe`

```json
{
  "nodeId": "demo_talker",
  "fields": ["running", "pid", "ros2State"],
  "rateHz": 1.0
}
```

- `stream.unsubscribe`

```json
{
  "subscriptionId": "<uuid>"
}
```

- `stream.data` event tam mesaji:

```json
{
  "v": 1,
  "type": "event",
  "action": "stream.data",
  "requestId": null,
  "ts": "2026-04-08T12:34:56.123456+00:00",
  "deviceId": "spiny-...",
  "role": "viewer",
  "payload": {
    "subscriptionId": "<uuid>",
    "nodeId": "demo_talker",
    "ts": "2026-04-08T12:34:56.123456+00:00",
    "data": {
      "running": true,
      "pid": 1234,
      "ros2State": "active"
    }
  }
}
```

### Peer (Uzak Cihaz)

- `peer.list`
  - payload: `{}`
- `peer.node.status`
  - payload: `{ "peerId": "peer-example", "nodeId": "demo_talker", "timeoutSec": 15 }`
- `peer.node.start`
  - payload: `{ "peerId": "peer-example", "nodeId": "demo_talker", "timeoutSec": 15 }`
- `peer.node.stop`
  - payload: `{ "peerId": "peer-example", "nodeId": "demo_talker", "graceSec": 5, "timeoutSec": 15 }`
- `peer.node.restart`
  - payload: `{ "peerId": "peer-example", "nodeId": "demo_talker", "timeoutSec": 15 }`

## 7) Manifest ve Lifecycle Kisa Not

Manifestte ROS2-native format kullan:

```json
{
  "nodes": {
    "demo_talker": {
      "mode": "ros2",
      "package": "demo_nodes_cpp",
      "executable": "talker",
      "node_name": "spiny_demo_talker",
      "namespace": "/spiny/demo",
      "parameters": { "use_sim_time": false },
      "remaps": ["chatter:=/spiny/chatter"],
      "lifecycle_mode": "process"
    }
  }
}
```

`lifecycle_mode` secenekleri:

- `process`: yalnizca process seviyesinde start/stop
- `managed`: ROS2 lifecycle transition (configure -> activate, stopta deactivate -> shutdown)

`managed` icin `node_name` zorunludur.

## 8) Hata Kodlari ve Ilk Kontrol Listesi

Yaygin hata kodlari:

- `WS_AUTH_INVALID_TOKEN`
- `WS_AUTH_FORBIDDEN_ROLE`
- `WS_SCHEMA_INVALID`
- `NODE_NOT_FOUND`
- `NODE_START_FAILED`
- `NODE_STOP_FAILED`
- `ROS2_GRAPH_FAILED`
- `ROS2_NODE_INFO_FAILED`
- `PEER_NOT_FOUND`
- `PEER_CONTROL_DISABLED`
- `PEER_ACTION_DENIED`
- `PEER_UNREACHABLE`

Hizli ariza akisi:

1. Servis ayakta mi?
2. Token ve rol dogru mu?
3. Manifestte nodeId var mi?
4. ROS2 CLI hedefte calisiyor mu? (`ros2 node list`)
5. Peer icin allowlist/policy dogru mu?

## 9) Uctan Uca Duman Testi (5 Dakika)

```bash
# 1) Node baslat
spinyctl orchestrator node start demo_talker --json --token <TOKEN>

# 2) Graph cek
spinyctl orchestrator graph snapshot --json --token <TOKEN>

# 3) Node I/O kontrol
spinyctl orchestrator io /spiny/demo/spiny_demo_talker --json --token <TOKEN>

# 4) Stream izle
spinyctl orchestrator stream watch demo_talker --seconds 5 --rate-hz 1 --field running --field ros2State --json --token <TOKEN>

# 5) Node durdur
spinyctl orchestrator node stop demo_talker --grace-sec 3 --json --token <TOKEN>
```

Bu 5 adim sorunsuz ise uygulama entegrasyonu icin yonetim kanali hazir kabul edilebilir.
