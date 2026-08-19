# SpinyOS Dynamic SDK Deployment Sistemi

Bu dokuman, SDK ile disarida derlenen uygulama paketlerini WebSocket uzerinden cihaza yukleme, eksik bagimlilik tespiti ve ROS calisma ortamina entegre etme akisinin ana referansidir.

## 1. Hedef

Amac:

1. Cihazda kurulu paketleri cekmek
2. Gonderilen paket listesinde eksik olanlari bulmak
3. Eksik bagimliliklar ve ana uygulamayi SDK ile derlemek
4. Derlenen ROS paket arsivini WebSocket ile cihaza yuklemek
5. Arsivi sisteme kurmak
6. Shared library dosyalarini harici kutuphane klasorune koymak
7. Harici kutuphane klasorunu sistemin gormesini saglamak

## 2. Baglanti Protokolu

WebSocket URL:

ws://<host>:8765?token=<TOKEN>

Tum istekler su zarfta olmalidir:

```json
{
  "v": 1,
  "type": "command",
  "action": "ACTION_NAME",
  "requestId": "unique-id",
  "payload": {}
}
```

## 3. Asama 1 - Envanter ve Eksik Bagimlilik Analizi

### 3.1 Kurulu paketleri cek

Action: `pkg.list`

```json
{
  "v": 1,
  "type": "command",
  "action": "pkg.list",
  "requestId": "req-list-opkg",
  "payload": {
    "manager": "opkg"
  }
}
```

Desteklenen manager degerleri:

1. `opkg`
2. `pip`
3. `ros`

### 3.2 Istenen listeye gore eksikleri bul

Action: `pkg.missing`

```json
{
  "v": 1,
  "type": "command",
  "action": "pkg.missing",
  "requestId": "req-missing-ros",
  "payload": {
    "manager": "ros",
    "requiredPackages": [
      "rclpy",
      "rclcpp",
      "sensor_msgs",
      "geometry_msgs"
    ]
  }
}
```

Ornek basarili cevap payload:

```json
{
  "result": "success",
  "manager": "ros",
  "requiredPackages": ["geometry_msgs", "rclcpp", "rclpy", "sensor_msgs"],
  "missingPackages": ["sensor_msgs"],
  "missingCount": 1,
  "installedCount": 153
}
```

## 4. Asama 2 - SDK Derleme Tarafi

Uygulama tarafi (ayri bilgisayar) su adimlari uygular:

1. `pkg.missing` sonucundaki `missingPackages` listesini alir
2. Bu paketleri ve ana projeyi SDK ile derler
3. Tek bir ROS deploy arsivi uretir (onerilen: `.tar.gz`)

Not:

- Arsiv icinde `install/` klasoru varsa sistem dogrudan workspace install altina birlestirir.
- Yoksa arsiv kokunu install altina acip birlestirir.

## 5. Asama 3 - Arsiv Yukleme (WebSocket)

### 5.1 Upload baslat

Action: `pkg.upload.begin`

```json
{
  "v": 1,
  "type": "command",
  "action": "pkg.upload.begin",
  "requestId": "req-upload-begin",
  "payload": {
    "manager": "ros",
    "artifactType": "tar.gz",
    "fileName": "my-ros-app.tar.gz",
    "sizeBytes": 1234567,
    "sha256": "<full-file-sha256>",
    "target": "install"
  }
}
```

### 5.2 Chunk gonder

Action: `pkg.upload.chunk`

```json
{
  "v": 1,
  "type": "command",
  "action": "pkg.upload.chunk",
  "requestId": "req-upload-chunk-1",
  "payload": {
    "uploadId": "<upload-id>",
    "seq": 0,
    "data": "<base64>",
    "chunkSha256": "<chunk-sha256>"
  }
}
```

### 5.3 Commit et ve kur

Action: `pkg.upload.commit`

```json
{
  "v": 1,
  "type": "command",
  "action": "pkg.upload.commit",
  "requestId": "req-upload-commit",
  "payload": {
    "uploadId": "<upload-id>",
    "sha256": "<full-file-sha256>",
    "installNow": true
  }
}
```

Basarili cevapta `payload.storedPath` gelir.

## 6. Asama 4 - ROS Arsiv Kurulumu

Iki yontem vardir:

1. `pkg.upload.commit` icinde `installNow: true`
2. Ayrica `pkg.install` ile manuel kurulum

Manuel kurulum ornegi:

Action: `pkg.install`

```json
{
  "v": 1,
  "type": "command",
  "action": "pkg.install",
  "requestId": "req-install-ros",
  "payload": {
    "manager": "ros",
    "archivePath": "/tmp/spiny-orchestrator/uploads/<upload-id>-my-ros-app.tar.gz",
    "workspaceRoot": "/home/root/spiny_ws",
    "externalLibDir": "/opt/spiny/external/lib",
    "packages": []
  }
}
```

## 7. Asama 5 - Shared Library Gorunurlugu

Kurulum sirasinda sistem su islemleri yapar:

1. ROS workspace install altini birlestirir
2. `install/lib` ve `install/lib64` altindaki `.so` dosyalarini `externalLibDir` altina kopyalar
3. `/etc/ld.so.conf.d/spiny-external.conf` dosyasina external lib yolunu yazar
4. `/etc/profile.d/spiny-external-libs.sh` olusturur
5. `/etc/profile.d/spiny-ros-workspace.sh` olusturur
6. Varsa `ldconfig` calistirir

Bu sayede hem dynamic linker hem shell ortami harici kutuphane klasorunu gorur.

## 8. Asama 6 - Servis Tarafinda Yeni Icerigi Gorme

Manifest veya calisma konfigi degistiyse:

Action: `orchestrator.reload`

```json
{
  "v": 1,
  "type": "command",
  "action": "orchestrator.reload",
  "requestId": "req-reload",
  "payload": {}
}
```

## 9. Uygulama Tarafi Ornek Is Akisi

1. `pkg.list` (opkg/pip/ros)
2. `pkg.missing` ile hedef paketlere gore diff
3. SDK build (eksikler + ana proje)
4. `pkg.upload.begin`
5. `pkg.upload.chunk` (tum chunklar)
6. `pkg.upload.commit` (`installNow: true`)
7. Gerekirse `orchestrator.reload`
8. `node.status` ve `graph.snapshot` ile smoke test

## 10. Hata ve Retry Kurallari

Hata mesaji `type=error` ve payload alanlari:

1. `errorCode`
2. `retryable`
3. `message`
4. `details`

Onerilen istemci davranisi:

1. `retryable=true` ise exponential backoff ile tekrar dene
2. `retryable=false` ise islemi durdur ve operator aksiyonu iste

## 11. Guvenlik ve Operasyon Notlari

1. Tokenlari istemci loglarina yazma
2. Buyuk dosyalari chunk ve SHA dogrulamasi ile gonder
3. Yukleme tamamlanmadan kurulum deneme
4. Kurulum sonrasi temel dogrulama komutlari calistir

## 12. Basit Dogrulama Kontrol Listesi

1. `pkg.missing` bos donuyor mu?
2. `pkg.upload.commit` basarili mi?
3. `pkg.install` sonucu `result=success` mi?
4. `externalLibDir` olustu mu?
5. ROS node calisiyor ve graph gorunuyor mu?
