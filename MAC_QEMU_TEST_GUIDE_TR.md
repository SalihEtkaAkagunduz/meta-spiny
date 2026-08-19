# Mac Uzerinde SpinyOS Tam Sistem Testi (QEMU)

Bu kilavuz, SpinyOS'u Raspberry Pi yerine Mac uzerinde Docker + QEMU ile tam sistem olarak test etmek icindir.

## 1. Onemli Ayrim

- MACHINE hedef cihazdir.
- SDKMACHINE ise SDK'yi calistiran host mimarisidir.

Bu nedenle MACHINE degeri `aarch64` gibi genel bir mimari olmamali; gecerli bir Yocto machine adi olmali.

## 2. Yeni QEMU Test Image

Bu repo icine QEMU uyumlu image tarifi eklendi:

- meta-spiny/recipes-core/images/build-spinyos-qemu.bb

Bu profil:

- Orchestrator + ROS2 + spinyctl stack'ini icerir.
- RPi'ya ozel firmware/driver bagimliliklarini disarida birakir.
- Mac'te sanallastirma testini daha stabil yapar.

## 3. Docker Icinde Build (Mac)

Asagidaki adimlar Linux container icinde calistirilir.

1. Konteyner ac:

docker run --rm -it --platform linux/arm64 \
  -v "$PWD":/work -w /work ubuntu:22.04 bash

2. Gerekli paketleri kur:

apt update && apt install -y \
  gawk wget git diffstat unzip texinfo gcc build-essential \
  chrpath socat cpio python3 python3-pip python3-pexpect xz-utils \
  debianutils iputils-ping python3-git python3-jinja2 libegl1-mesa \
  libsdl1.2-dev xterm locales ca-certificates

3. Build ortami ve machine secimi:

cd /work
. ./oe-init-build-env build-qemu

4. local.conf icin zorunlu satirlar:

MACHINE = "qemuarm64"
DISTRO = "spinyos"

5. Parse kontrol:

bitbake -p

6. Image build:

bitbake build-spinyos-qemu

## 4. QEMU ile Calistirma (Linux Ortami)

Build tamamlandiktan sonra ayni ortamda:

runqemu qemuarm64 nographic slirp

Alternatif (ssh erisimi):

runqemu qemuarm64 nographic slirp qemuparams="-netdev user,id=net0,hostfwd=tcp::2222-:22 -device virtio-net-pci,netdev=net0"

Sonra hosttan baglan:

ssh root@127.0.0.1 -p 2222

## 5. Sistem Test Kontrol Listesi

QEMU icinde:

1. systemctl status spiny-orchestrator
2. spinyctl orchestrator node list --json --token <TOKEN>
3. spinyctl orchestrator graph snapshot --json --token <TOKEN>
4. ros2 node list

## 6. Hata Notlari

- MACHINE = "aarch64" yanlistir; gecerli machine adi kullan.
- Mac uzerinde native Yocto host yerine Docker Linux host kullan.
- Donanim bagimli ozellikler (gercek WiFi chipset/AP) QEMU'da birebir temsil edilmez.

## 7. Ne Zaman Gercek Cihaza Donmeli?

Asagidakilerde gercek RPi testine gec:

1. WiFi AP fallback davranisi
2. GPIO ve ekran surucu akislari
3. Donanim bagimli performans testleri
