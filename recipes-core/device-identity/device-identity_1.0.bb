SUMMARY = "SpinyOS Device Identity"
DESCRIPTION = "Generates a unique device ID from the Raspberry Pi CPU serial number \
on first boot. Sets hostname to spinyos-<8hex>, writes /etc/spiny/device-id \
for use by other services, and exports SPINY_DEVICE_ID via /etc/profile.d/."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://device-identity.sh \
           file://device-identity.service"

S = "${WORKDIR}"

inherit systemd

SYSTEMD_SERVICE:${PN} = "device-identity.service"
SYSTEMD_AUTO_ENABLE = "enable"

do_install() {
    install -d ${D}${bindir}
    install -m 0755 ${WORKDIR}/device-identity.sh ${D}${bindir}/device-identity.sh

    install -d ${D}${systemd_unitdir}/system
    install -m 0644 ${WORKDIR}/device-identity.service \
                    ${D}${systemd_unitdir}/system/device-identity.service

    # /etc/spiny dizinini önceden oluştur; içindeki dosyalar boot'ta yazılır
    install -d ${D}${sysconfdir}/spiny

    # /etc/profile.d dizinini garantile (interaktif shell için)
    install -d ${D}${sysconfdir}/profile.d
}

FILES:${PN} += " \
    ${bindir}/device-identity.sh \
    ${systemd_unitdir}/system/device-identity.service \
    ${sysconfdir}/spiny \
    ${sysconfdir}/profile.d \
"

# /proc/cpuinfo ve /etc/machine-id okunması için ekstra bağımlılık yok;
# sadece sh ve logger gerekli (busybox zaten mevcut)
RDEPENDS:${PN} += "util-linux"
