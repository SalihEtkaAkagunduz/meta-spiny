SUMMARY = "Resize root filesystem on first boot"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = " \
    file://resize-rootfs.sh \
    file://resize-rootfs.service \
"

inherit systemd

# Betiği /usr/sbin/ dizinine kur
do_install() {
    install -d ${D}${sbindir}
    install -m 0755 ${WORKDIR}/resize-rootfs.sh ${D}${sbindir}

    # Systemd servisini kur (standart unitdir altında)
    install -d ${D}${systemd_unitdir}/system
    install -m 0644 ${WORKDIR}/resize-rootfs.service ${D}${systemd_unitdir}/system/resize-rootfs.service

    # Marker dizinini önceden oluştur (runtime'da da oluşturulur ama yine de)
    install -d ${D}${localstatedir}/lib/resize-rootfs
    
    # Remove any accidental root-level installs of the service (avoid QA issues)
    rm -f ${D}/resize-rootfs.service || true
}

# Servisin açılışta etkinleştirilmesini sağla
SYSTEMD_SERVICE:${PN} = "resize-rootfs.service"
SYSTEMD_AUTO_ENABLE = "enable"

FILES:${PN} = "${sbindir}/resize-rootfs.sh \
                ${systemd_unitdir}/system/resize-rootfs.service \
                ${localstatedir}/lib/resize-rootfs \
               "

# Runtime dependencies
RDEPENDS:${PN} += "parted e2fsprogs-resize2fs"

