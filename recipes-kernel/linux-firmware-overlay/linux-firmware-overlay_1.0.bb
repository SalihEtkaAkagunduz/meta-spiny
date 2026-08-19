SUMMARY = "TFT35A LCD overlay for Waveshare/Spotpear 3.5 inch LCD"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://tft35a.dtbo"

S = "${WORKDIR}"

inherit allarch deploy

do_deploy() {
    install -d ${DEPLOYDIR}/overlays
    install -m 0644 ${WORKDIR}/tft35a.dtbo ${DEPLOYDIR}/overlays/tft35a.dtbo
}

addtask deploy before do_build after do_compile
