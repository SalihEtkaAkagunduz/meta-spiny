#!/bin/sh
# SpinyOS Device Identity — runs once per boot (idempotent)
#
# Kaynak: Raspberry Pi CPU seri numarası (/proc/cpuinfo → "Serial: xxxxxxxxxxxxxxxx")
# Son 8 hex karakter → kısa, benzersiz, DNS-güvenli kimlik.
#
# Üretilen değerler:
#   /etc/spiny/device-id      → SPINY_DEVICE_ID=<8hex>  (kaynak alınabilir dosya)
#   /etc/hostname             → spinyos-<8hex>
#   /etc/profile.d/spiny-device-id.sh → shell oturumları için export
#   /run/spiny/device-id      → tmpfs'te hızlı erişim (servisler için)

# set -e YOK — herhangi bir ara komut başarısız olursa betik çıkmasın

ID_FILE=/etc/spiny/device-id
PROFILE_FILE=/etc/profile.d/spiny-device-id.sh
RUN_FILE=/run/spiny/device-id

# ---------------------------------------------------------------------------
# 1. CPU seri numarasını oku
# ---------------------------------------------------------------------------
SERIAL=""
if [ -r /proc/cpuinfo ]; then
    # Pi 4 formatı: "Serial          : 10000000a1b2c3d4"
    # sed: kolon + ardındaki boşlukları sil (POSIX karakter sınıfı, busybox uyumlu)
    SERIAL="$(grep -m1 '^Serial' /proc/cpuinfo | sed 's/^[^:]*:[[:space:]]*//' | tr -d '[:space:]')"
fi

# Seri numara yoksa veya sıfırsa yedek kaynaklara geri dön
if [ -z "$SERIAL" ] || [ "$SERIAL" = "0000000000000000" ]; then
    # 1. Önceki boot'tan kaydedilmiş kalıcı rastgele seri varsa kullan
    if [ -r /etc/spiny/fallback-serial ]; then
        SERIAL="$(tr -d '[:space:]' < /etc/spiny/fallback-serial)"
    fi
fi

if [ -z "$SERIAL" ] || [ "$SERIAL" = "0000000000000000" ]; then
    # 2. machine-id dene — "uninitialized" veya boşsa geç
    if [ -r /etc/machine-id ]; then
        _MID="$(tr -d '[:space:]' < /etc/machine-id)"
        if [ -n "$_MID" ] && [ "$_MID" != "uninitialized" ]; then
            SERIAL="$_MID"
        fi
    fi
fi

if [ -z "$SERIAL" ] || [ "$SERIAL" = "0000000000000000" ]; then
    # 3. Son çare: rastgele oluştur ve kalıcı kaydet — sonraki bootlar bunu kullanır
    mkdir -p /etc/spiny
    SERIAL="$(cat /dev/urandom 2>/dev/null | tr -dc 'a-f0-9' | head -c 16)"
    echo "$SERIAL" > /etc/spiny/fallback-serial
    chmod 644 /etc/spiny/fallback-serial
fi

# Son 8 hex karakteri al — saf POSIX parametre genişletmesi (rev/cut gerektirmez)
HEX="$(printf '%s' "$SERIAL" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-f0-9')"
LEN="${#HEX}"
if [ "$LEN" -ge 8 ]; then
    # Son 8 karakteri al: önce son-8'den öncesini çıkart, kalanı al
    PREFIX="${HEX%????????}"   # son 8 karakteri sil → ön kısım
    DEVICE_ID="${HEX#"$PREFIX"}"  # ön kısmı çıkart → son 8 karakter
else
    DEVICE_ID="$HEX"
fi

# Hâlâ 8 karakter değilse başından tamamla
if ! printf '%s' "$DEVICE_ID" | grep -qE '^[a-f0-9]{8}$'; then
    DEVICE_ID="$(printf '%08s' "$DEVICE_ID" | tr ' ' '0')"
fi

# Hâlâ boşsa hard-coded fallback (olmamalı)
DEVICE_ID="${DEVICE_ID:-00000000}"

HOSTNAME="spinyos-${DEVICE_ID}"

# ---------------------------------------------------------------------------
# 2. Dosyalara yaz (idempotent: halihazırda aynı değer varsa değiştirme)
# ---------------------------------------------------------------------------
mkdir -p /etc/spiny /etc/profile.d "$(dirname "$RUN_FILE")"

# Kalıcı kimlik dosyası (servisler source alır)
if ! grep -q "SPINY_DEVICE_ID=${DEVICE_ID}" "$ID_FILE" 2>/dev/null; then
    printf 'SPINY_DEVICE_ID=%s\nSPINY_HOSTNAME=%s\n' "$DEVICE_ID" "$HOSTNAME" > "$ID_FILE"
    chmod 644 "$ID_FILE"
fi

# tmpfs'te hızlı okunur kopya
printf 'SPINY_DEVICE_ID=%s\nSPINY_HOSTNAME=%s\n' "$DEVICE_ID" "$HOSTNAME" > "$RUN_FILE"
chmod 644 "$RUN_FILE"

# Shell profile (interaktif oturumlar için)
printf '# SpinyOS device identity — generated at boot\nexport SPINY_DEVICE_ID=%s\nexport SPINY_HOSTNAME=%s\n' \
    "$DEVICE_ID" "$HOSTNAME" > "$PROFILE_FILE"
chmod 644 "$PROFILE_FILE"

# ---------------------------------------------------------------------------
# 3. Hostname güncelle
# ---------------------------------------------------------------------------
CURRENT_HOSTNAME="$(cat /etc/hostname 2>/dev/null | tr -d '[:space:]')"
if [ "$CURRENT_HOSTNAME" != "$HOSTNAME" ]; then
    echo "$HOSTNAME" > /etc/hostname
    # Kernel hostname'ini her zaman güncelle (busybox hostname komutu)
    hostname "$HOSTNAME" 2>/dev/null || true
    # systemd-hostnamed varsa D-Bus üzerinden de güncelle
    if command -v hostnamectl >/dev/null 2>&1; then
        hostnamectl set-hostname "$HOSTNAME" 2>/dev/null || true
    fi
fi

# /etc/hosts'u güncelle (127.0.1.1 satırı)
if grep -q "^127\.0\.1\.1" /etc/hosts 2>/dev/null; then
    sed -i "s/^127\.0\.1\.1.*/127.0.1.1\t${HOSTNAME}/" /etc/hosts
else
    printf '127.0.1.1\t%s\n' "$HOSTNAME" >> /etc/hosts
fi

logger -t device-identity "SPINY_DEVICE_ID=${DEVICE_ID} hostname=${HOSTNAME}" 2>/dev/null || true
