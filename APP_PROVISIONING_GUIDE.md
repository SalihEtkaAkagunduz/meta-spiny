# SpinyOS — Uygulama Geliştirici WiFi Provisioning Yönergesi

Bu döküman, masaüstü uygulamanın (Electron/VS Code fork) SpinyOS cihazına
WiFi kimlik bilgilerini nasıl göndereceğini ve cihazın durumunu nasıl
okuyacağını açıklar.

---

## Genel Akış

```
Uygulama                          SpinyOS Cihazı
   │                                     │
   │  1. `SpinyOS-<device_id>` SSID'ye bağlan   │
   │ ──────────────────────────────────► │
   │                                     │  ← AP modu, IP: 192.168.73.1
   │  2. GET /api/wifi/status            │
   │ ──────────────────────────────────► │
   │  ◄── {"status": "first_setup"} ──  │
   │                                     │
   │  3. POST /api/wifi/configure        │
   │     {"ssid":"Evim","password":"123"}│
   │ ──────────────────────────────────► │
  │  ◄── {"status": "credentials_received"} │
   │                                     │  ← Cihaz wifi-manager'ı yeniden
   │                                     │    başlatır, ev WiFi'a bağlanır
   │                                     │
   │  4. Ev WiFi ağına geri dön          │
   │  5. spinyos-<device_id>.local       │
   │     ile cihaza eriş                 │
```

---

## Provisioning API

**Base URL (AP modunda):** `http://192.168.73.1:7373`  
**Base URL (LAN modunda):** `http://spinyos-<device_id>.local:7373`  
(Port 7373 her iki modda da açıktır — LAN modunda da durum sorgulanabilir)

`device_id`, `/api/system/info` endpoint'inden alınan `device_id` alanıdır.

### `GET /api/wifi/status`

Cihazın mevcut durumunu döner.

**Yanıt:**
```json
{
  "status": "first_setup" | "wifi_error" | "ok",
  "configured": false | true,
  "last_error": "" | "ap_not_found" | "auth_fail" | "dhcp_fail" | "unknown"
}
```

| `status`      | Açıklama |
|---------------|----------|
| `first_setup` | Cihaz hiç yapılandırılmamış. İlk kurulum akışını başlat. |
| `wifi_error`  | Daha önce kaydedilmiş WiFi bilgileriyle bağlantı kurulamadı. `last_error` ile hata türünü göster. |
| `ok`          | Cihaz LAN'a bağlı, sorun yok. |

**`last_error` değerleri:**

| Değer          | Kullanıcıya gösterilecek mesaj |
|----------------|-------------------------------|
| `ap_not_found` | "WiFi ağı bulunamadı. SSID'yi kontrol edin." |
| `auth_fail`    | "WiFi şifresi hatalı." |
| `dhcp_fail`    | "IP adresi alınamadı. Router'ı kontrol edin." |
| `unknown`      | "Bilinmeyen hata. Lütfen tekrar deneyin." |

---

### `GET /api/system/info`

Cihaz hakkında temel bilgi döner.

**Yanıt:**
```json
{
  "hostname":  "spinyos-a1b2c3d4",
  "device":    "SpinyOS",
  "device_id": "a1b2c3d4",
  "version":   "1.0"
}
```

---

### `POST /api/wifi/configure`

WiFi kimlik bilgilerini cihaza kaydeder ve bağlantıyı başlatır.

**İstek (Content-Type: application/json):**
```json
{
  "ssid": "EvWifi",
  "password": "sifre1234"
}
```

**Başarı yanıtı (200):**
```json
{
  "status": "credentials_received",
  "message": "Credentials received. Device is reconnecting."
}
```

**Hata yanıtları:**

| Kod | `error`                       | Sebep |
|-----|-------------------------------|-------|
| 400 | `ssid_and_password_required`  | Boş alan |
| 400 | `invalid_characters`          | Geçersiz karakter (ör. `"`, `\`) |
| 400 | `invalid_json`                | Geçersiz JSON gövdesi |
| 400 | `payload_too_large`           | 4 KB üstü gövde |

Kaydetme işleminden sonra cihaz `wifi-manager` servisini yeniden başlatır.
Bu işlem birkaç saniye sürebilir. Uygulama; cihazın ev WiFi'a bağlanmasını
bekleyip sonra `spinyos-<device_id>.local` üzerinden bağlantıyı doğrulayabilir.

---

## Canlı Konsol

Uygulamadaki alttan açılan panelde yer alan `Debug Console` sekmesi,
uygulama tarafında `Canlı Konsol` olarak yeniden adlandırılmalıdır.
Bu alan yalnızca log göstermek için değil, doğrudan cihazın gerçek SSH shell
oturumunu açmak için kullanılmalıdır.

### Hedef davranış

- Sekme başlığı: `Canlı Konsol`
- Bağlantı: gerçek SSH PTY oturumu
- Amaç: kullanıcının cihazı normal bir SSH terminali gibi yönetebilmesi
- Desteklenen kullanım:
  - servis yönetimi: `systemctl`, `journalctl`
  - ağ inceleme: `ip`, `ss`, `ping`
  - süreç yönetimi: `ps`, `top`, `kill`
  - dosya işlemleri: `cp`, `mv`, `rm`, `tar`
  - SpinyOS komutları: `spinyctl ...`

### OS tarafı

SpinyOS image'i gerçek yönetim oturumu için şu bileşenleri içermelidir:

- `OpenSSH` sunucusu
- `bash`
- `coreutils`
- `procps`
- `scp`
- `sftp-server`

Bağlantı bilgileri:

- Protokol: SSH
- Port: `22`
- Kullanıcı: `root`
- Hedef: cihaz IP'si veya `spinyos-<device_id>.local`

### Electron entegrasyonu

Bu SSH oturumu renderer process içinde değil, Electron `main` process içinde
yönetilmelidir. Renderer sadece terminal görünümünü göstermelidir.

Önerilen yapı:

- terminal UI: `xterm.js`
- SSH bağlantısı: `ssh2`
- dosya transferi: `ssh2` SFTP veya `scp`
- yapılandırılmış yönetim işlemleri: `spinyctl`

Örnek:

```ts
import { ipcMain } from "electron";
import { Client } from "ssh2";

function openLiveConsole(mainWindow, options: {
  host: string;
  username: string;
  password: string;
}) {
  const ssh = new Client();

  ssh.on("ready", () => {
    ssh.shell({ term: "xterm-256color", cols: 120, rows: 30 }, (error, stream) => {
      if (error) {
        throw error;
      }

      stream.on("data", (chunk: Buffer) => {
        mainWindow.webContents.send("live-console:data", chunk.toString("utf8"));
      });

      ipcMain.on("live-console:input", (_event, data: string) => {
        stream.write(data);
      });

      ipcMain.on("live-console:resize", (_event, cols: number, rows: number) => {
        stream.setWindow(rows, cols, 0, 0);
      });
    });
  });

  ssh.connect({
    host: options.host,
    port: 22,
    username: options.username,
    password: options.password,
    keepaliveInterval: 10000,
    readyTimeout: 15000,
  });
}
```

### Bağlantı önceliği

`Canlı Konsol` açılırken şu sıra izlenmelidir:

1. `192.168.50.2:22`
2. `spinyos-<device_id>.local:22`
3. son başarılı IP: `lastKnownIp:22`
4. kullanıcının elle girdiği IP: `manualIp:22`

## Doğrudan Ethernet

SpinyOS cihazı doğrudan Ethernet kablosu ile bağlandığında `eth0` üzerinde
`192.168.50.2/24` adresini alır ve host bilgisayara DHCP ile otomatik bir
`192.168.50.x` adresi dağıtır.

Beklenen davranış:

- cihaz IP'si: `192.168.50.2`
- API: `http://192.168.50.2:7373/api/system/info`
- SSH: `ssh root@192.168.50.2`
- host ağ ayarı: `Automatic (DHCP)`

Eğer host işletim sistemi DHCP ile adres almazsa elle şu adres verilebilir:

- host IP: `192.168.50.1/24`
- gateway: boş bırakılabilir

Hızlı doğrulama:

```bash
ip addr show
ping 192.168.50.2
curl http://192.168.50.2:7373/api/system/info
ssh root@192.168.50.2
```

Bu workspace içinde Electron/VS Code fork uygulama kodu bulunmadığı için,
burada sadece OS tarafı ve entegrasyon sözleşmesi güncellenmiştir. Uygulama
repo'su eklendiğinde sekme adını ve gerçek SSH terminal ekranını doğrudan kodda
bağlayabilirim.

---

### `POST /api/wifi/forget`

Kayıtlı kimlik bilgilerini siler; cihazı `first_setup` durumuna döndürür.
Fabrika ayarlarına dönüş veya sorun giderme için kullanılır.

**Yanıt (200):**
```json
{ "status": "forgotten" }
```

---

## Uygulama Tarafı Akış (Pseudocode)

```javascript
// 1. AP modunu tespit et
async function provisionDevice(ssid, password) {

  // Adım 1: Durumu sorgula
  const status = await fetch("http://192.168.73.1:7373/api/wifi/status")
    .then(r => r.json());

  if (status.status === "first_setup") {
    showMessage("İlk kurulum yapılıyor...");
  } else if (status.status === "wifi_error") {
    showError(errorMessage(status.last_error));
    // Kullanıcıdan yeni bilgi iste
  }

  // Adım 2: Kimlik bilgilerini gönder
  const response = await fetch("http://192.168.73.1:7373/api/wifi/configure", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ssid, password }),
  }).then(r => r.json());

  if (response.status !== "credentials_received") {
    throw new Error(response.error);
  }

  showMessage("Bilgiler alındı. Cihaz WiFi ağına bağlanıyor...");

  // Adım 3: Ev ağına geri dön, önce Ethernet sabit IP'yi sonra mDNS'i dene
  await reconnectToHomeNetwork();
  await waitForDevice("192.168.50.2", 7373, timeout=5_000)
    .catch(() => waitForDevice(`spinyos-${deviceInfo.device_id}.local`, 7373, timeout=30_000));

  showMessage("Cihaz hazır!");
}
```

---

## Cihaza Bağlanma (IP Değişse Bile)

Öncelik sırası şöyle çalışır:

1. **Doğrudan Ethernet statik IP:** `http://192.168.50.2:7373`
2. **mDNS:** `spinyos-<device_id>.local`
3. **Son bilinen IP:** uygulama son başarılı bağlantı IP'sini kısa timeout ile deneyebilir
4. **AP fallback:** WiFi bağlantısı kesilirse cihaz `SpinyOS-<device_id>` ağını yayar;
  uygulama bu ağı görerek kurtarma moduna girer

SpinyOS, doğrudan Ethernet kablosu için `eth0` arayüzüne kalıcı olarak `192.168.50.2/24`
adresi atar. Uygulama host makinenin Ethernet arayüzünü `192.168.50.1/24` yapmalıdır.

`device_id` değerini kaydetmek için ilk bağlantıda `GET /api/system/info` çağrısı yapın.
Bu değer cihaz değiştirilmedikçe hiç değişmez.

---

## Uygulama Tarafında device_id Saklama ve Hatırlama

### Ne zaman kaydedilmeli?

İlk provisioning tamamlandıktan hemen sonra `GET /api/system/info` çağrısı yapılır.
Gelen `device_id` ve diğer bilgiler kalıcı olarak uygulamanın yerel veritabanına yazılır.

### Ne saklanmalı?

```typescript
// Uygulama tarafı cihaz kaydı — yerel veritabanında sakla
interface SpinyDevice {
  device_id:   string;   // "a1b2c3d4"  — asla değişmez, birincil anahtar
  hostname:    string;   // "spinyos-a1b2c3d4"
  mdns:        string;   // "spinyos-a1b2c3d4.local"
  label:       string;   // kullanıcının verdiği takma ad, ör. "Lab Cihazı 1"
  added_at:    string;   // ISO8601 tarih
  last_seen:   string;   // son başarılı bağlantı zamanı
}
```

Electron/Node ortamında bu yapıyı `electron-store`, `lowdb` veya SQLite ile
`userData` klasörüne kaydedin:

```typescript
import Store from "electron-store";

const store = new Store<{ devices: SpinyDevice[] }>({
  name: "spiny-devices",
  defaults: { devices: [] },
});

// İlk kurulumda kaydet
function registerDevice(info: { device_id: string; hostname: string }) {
  const devices = store.get("devices");
  const exists  = devices.find(d => d.device_id === info.device_id);
  if (!exists) {
    devices.push({
      device_id: info.device_id,
      hostname:  info.hostname,
      mdns:      `${info.hostname}.local`,
      label:     `SpinyOS Cihazı`,
      added_at:  new Date().toISOString(),
      last_seen: new Date().toISOString(),
    });
    store.set("devices", devices);
  }
}

// Sonraki bağlantılarda cihazı bul
function getDevice(device_id: string): SpinyDevice | undefined {
  return store.get("devices").find(d => d.device_id === device_id);
}
```

### Bağlantı öncelik sırası (sonraki açılışlar)

Uygulama kayıtlı bir cihaza bağlanmak istediğinde şu sırayı izler:

```typescript
async function connectToDevice(device: SpinyDevice): Promise<string> {
  // 1. mDNS ile dene (en hızlı, IP bağımsız)
  try {
    await fetch(`http://${device.mdns}:7373/api/wifi/status`, { signal: AbortSignal.timeout(3000) });
    updateLastSeen(device.device_id);
    return `http://${device.mdns}:7373`;
  } catch {}

  // 2. WiFi taramasında SpinyOS-<device_id> AP'si görünüyor mu? (fallback modu)
  const apSsid = `SpinyOS-${device.device_id}`;
  const visibleAPs = await scanWifiNetworks();          // platform API'si
  if (visibleAPs.includes(apSsid)) {
    // Cihaz AP moduna düşmüş → provisioning akışını yeniden başlat
    return "AP_FALLBACK";
  }

  throw new Error("device_unreachable");
}
```

### AP fallback tespit akışı

```
connectToDevice() → "AP_FALLBACK" döndü
        │
        ▼
WiFi taramasında SpinyOS-<device_id> görünüyor
        │
        ▼
Kullanıcıya göster: "Cihaz WiFi ağına bağlanamıyor.
                     Yeniden yapılandırmak ister misiniz?"
        │
        ▼ [Evet]
SpinyOS-<device_id> AP'sine bağlan
GET /api/wifi/status → last_error ile hata sebebini göster
POST /api/wifi/configure → yeni bilgilerle yeniden yapılandır
```

### Kayıtlı cihaz listesi (çoklu cihaz desteği)

Uygulamada birden fazla SpinyOS cihazı kayıtlı olabilir.
`device_id` birincil anahtar olduğu için çakışma olmaz.

```typescript
// Tüm kayıtlı cihazları listele
function listDevices(): SpinyDevice[] {
  return store.get("devices");
}

// Cihazı kaldır (fabrika sıfırlama sonrası)
function removeDevice(device_id: string): void {
  const devices = store.get("devices").filter(d => d.device_id !== device_id);
  store.set("devices", devices);
}

// Kullanıcı takma adını güncelle
function relabelDevice(device_id: string, label: string): void {
  const devices = store.get("devices").map(d =>
    d.device_id === device_id ? { ...d, label } : d
  );
  store.set("devices", devices);
}
```

---

## AP Ağ Bilgileri (Provisioning modu)

Her cihazın AP SSID'si **benzersizdir** — CPU seri numarasının son 8 hex karakterini içerir.

| Alan     | Değer                        |
|----------|-----------------------------|
| SSID     | `SpinyOS-<device_id>`        |
| Şifre    | `spiny1234`                 |
| Cihaz IP | `192.168.73.1`              |
| API Port | `7373`                      |

Örnek: Seri numarasının son 8 hanesi `a1b2c3d4` olan cihazın SSID'si `SpinyOS-a1b2c3d4` olur.

Uygulama, WiFi tarama listesinde `SpinyOS-` ile başlayan SSID'leri filtreleyerek yakındaki SpinyOS cihazlarını listeleyebilir.

---

## Durum / Hata Gösterimi Özeti

Uygulamanın kullanıcıya göstermesi gereken mesajlar:

| `status`      | `last_error`   | Kullanıcı mesajı |
|---------------|----------------|------------------|
| `first_setup` | —              | "Cihaz kurulmamış. WiFi bilgilerini girin." |
| `wifi_error`  | `ap_not_found` | "WiFi ağı bulunamadı. SSID'yi kontrol edin." |
| `wifi_error`  | `auth_fail`    | "WiFi şifresi hatalı." |
| `wifi_error`  | `dhcp_fail`    | "IP adresi alınamadı. Router'ı kontrol edin." |
| `wifi_error`  | `unknown`      | "Bilinmeyen hata. Cihaza erişilemedi." |
| `ok`          | —              | "Cihaz bağlı." |
