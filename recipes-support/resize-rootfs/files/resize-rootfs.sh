#!/bin/sh

# ============================================================================
# MARKER DOSYASI KONTROLÜ - İŞLEMİN SADECE BİR KEZ GERÇEKLEŞMESİNİ GARANTİ EDER
# ============================================================================
MARKER_DIR="/var/lib/resize-rootfs"
MARKER_FILE="${MARKER_DIR}/completed"

# Eğer işlem daha önce tamamlandıysa, SADECE mesaj ver ve çık
if [ -f "${MARKER_FILE}" ]; then
	echo "========================================"
	echo "UYARI: Bu işlem ikinci defa gerçekleştirilemez!"
	echo "Resize işlemi daha önce tamamlanmış."
	echo "Marker: ${MARKER_FILE}"
	echo "========================================"
	exit 0
fi

# Buradan sonra gerçek işlem başlıyor - strict mode aktif
set -eu

STARTED_MARKER="${MARKER_DIR}/started-$(date +%Y%m%d-%H%M%S).marker"

# Log dosyası kullanıcının görebileceği yerde
LOG_DIR=/home/root
LOG=${LOG_DIR}/resize-rootfs.log

# Dizinleri oluştur
mkdir -p "${MARKER_DIR}"
mkdir -p "${LOG_DIR}"

# İşlem başladı marker'ı oluştur (service'in çalıştığını gösterir - /var/lib altında)
echo "resize-rootfs service STARTED at $(date)" > "${STARTED_MARKER}" || true

# Log dosyasını aç (tüm çıktılar buraya gidecek)
touch "${LOG}"
exec > "${LOG}" 2>&1

echo "Starting resize-rootfs: $(date)"
echo "Started marker: ${STARTED_MARKER}"
echo "-- Initial diagnostics --"
echo "Command line: $(cat /proc/cmdline 2>/dev/null || true)"
echo "Kernel: $(uname -a)"
echo "PATH=${PATH}"
echo "lsblk:"; lsblk -o NAME,SIZE,TYPE,MOUNTPOINT,FSTYPE || true
echo "blkid:"; blkid || true
echo "mount:"; mount || true
echo "/proc/partitions:"; cat /proc/partitions || true
echo "-- End diagnostics --"

# Birincil yol: lsblk ile doğrudan kök partition'unu bul
ROOT_PART=$(lsblk -nr -o KNAME,MOUNTPOINT | awk '$2=="/"{print "/dev/"$1; exit}')
if [ -z "${ROOT_PART}" ]; then
	# Yedek: findmnt kullan
	ROOT_PART=$(findmnt / -o SOURCE -n 2>/dev/null || true)
fi

# Eğer findmnt /dev/root gibi bir symlink döndürdüyse, gerçek cihazı çöz
ROOT_PART=$(readlink -f "${ROOT_PART}" 2>/dev/null || echo "${ROOT_PART}")
echo "Root partition: ${ROOT_PART}"

# basename ile isim al
name=$(basename "${ROOT_PART}")

# Partition numarası ve ana cihazı tespit et
if echo "${name}" | grep -q 'p[0-9]\+$'; then
	PART_NUM="${name##*p}"
	DEV_BASE="${name%p${PART_NUM}}"
elif echo "${name}" | grep -q '[0-9]$'; then
	PART_NUM="${name##*[!0-9]}"
	DEV_BASE="${name%${PART_NUM}}"
else
	echo "Could not determine partition number for ${ROOT_PART}. This may be LVM/overlay or unsupported layout. Aborting with failure so systemd may retry later."
	exit 1
fi

ROOT_DEV="/dev/${DEV_BASE}"
echo "Root device: ${ROOT_DEV}"
echo "Partition number: ${PART_NUM}"

if [ ! -b "${ROOT_DEV}" ]; then
	echo "Device ${ROOT_DEV} does not exist or is not a block device. Aborting with failure so systemd may retry later."
	exit 1
fi

# Parted ile bölümü sonuna kadar genişlet
echo "Resizing partition ${PART_NUM} on ${ROOT_DEV} to 100%..."
if ! parted -s "${ROOT_DEV}" resizepart "${PART_NUM}" 100% 2>/tmp/resize-rootfs-parted.log; then
	echo "parted resizepart failed (see /tmp/resize-rootfs-parted.log for details)"
fi

# Kernel'e yeni partition tablosunu bildir
partprobe "${ROOT_DEV}" || true

# UDEV'in yeni cihaz düğümünü oluşturması için kısa bekleme
sleep 1

# Yeni partition cihaz yolunu dene (mmcblk0p2 veya sda2 gibi)
NEW_ROOT_PART=""
if [ -b "/dev/${DEV_BASE}p${PART_NUM}" ]; then
	NEW_ROOT_PART="/dev/${DEV_BASE}p${PART_NUM}"
elif [ -b "/dev/${DEV_BASE}${PART_NUM}" ]; then
	NEW_ROOT_PART="/dev/${DEV_BASE}${PART_NUM}"
else
	# Fallback: kullanılandığı gibi devam et
	NEW_ROOT_PART="${ROOT_PART}"
fi

echo "Using filesystem device for resize: ${NEW_ROOT_PART}"

# Dosya sistemini genişlet
if resize2fs "${NEW_ROOT_PART}"; then
	echo "resize2fs completed successfully at $(date)"
	
	# ============================================================================
	# BAŞARI DURUMUNDA MARKER DOSYASINI OLUŞTUR - İŞLEMİN TEKRAR YAPILMASINI ÖNLER
	# ============================================================================
	echo "Resize işlemi başarılı! Tarih: $(date)" > "${MARKER_FILE}"
	chmod 644 "${MARKER_FILE}"
	echo "Created completion marker: ${MARKER_FILE}"
	echo "Bu işlem bir daha ASLA çalışmayacak."
	
	# Başarılı ise servisi TAMAMEN KAPATIP MASKELE (hiç açılamaz hale gelir)
	if command -v systemctl >/dev/null 2>&1; then
		echo "Servisi kalıcı olarak kapatıyorum..."
		/bin/systemctl disable resize-rootfs.service 2>/dev/null || true
		/bin/systemctl mask resize-rootfs.service 2>/dev/null || true
		echo "✓ resize-rootfs.service DISABLED ve MASKED"
		echo "✓ Servis bir daha asla çalışmayacak (manuel olarak bile)"
	fi
	
	# Parted ayrıntılarını log'a ekle
	echo "-- parted log --"
	if [ -f /tmp/resize-rootfs-parted.log ]; then
		cat /tmp/resize-rootfs-parted.log || true
	fi
	
	echo "========================================"
	echo "resize-rootfs BAŞARIYLA TAMAMLANDI!"
	echo "Marker dosyası: ${MARKER_FILE}"
	echo "Log dosyası: ${LOG}"
	echo "========================================"
	exit 0
else
	echo "resize2fs reported no changes or failed at $(date)"
	echo "UYARI: İşlem başarısız oldu, marker dosyası OLUŞTURULMAYACAK"
	echo "Servis bir sonraki boot'ta tekrar deneyecek."
	
	# Parted ayrıntılarını log'a ekle
	echo "-- parted log --"
	if [ -f /tmp/resize-rootfs-parted.log ]; then
		cat /tmp/resize-rootfs-parted.log || true
	fi
	echo "resize-rootfs finished (failure)"
	exit 2
fi