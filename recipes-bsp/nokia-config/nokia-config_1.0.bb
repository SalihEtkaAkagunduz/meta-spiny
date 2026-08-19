SUMMARY = "Nokia 5110 Configuration for Raspberry Pi"
DESCRIPTION = "Enables SPI and configures boot settings for Nokia 5110 display"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = "file://nokia5110-config.sh"

S = "${WORKDIR}"

inherit allarch deploy

do_install() {
    install -d ${D}${sysconfdir}/profile.d
    install -m 0755 ${WORKDIR}/nokia5110-config.sh ${D}${sysconfdir}/profile.d/
}

# This runs after rpi-config to add Nokia 5110 settings
do_deploy() {
    # Check if config.txt exists in deploy directory
    if [ -f ${DEPLOYDIR}/bcm2835-bootfiles/config.txt ]; then
        # Add SPI enable if not already present
        if ! grep -q "^dtparam=spi=on" ${DEPLOYDIR}/bcm2835-bootfiles/config.txt; then
            echo "" >> ${DEPLOYDIR}/bcm2835-bootfiles/config.txt
            echo "# Nokia 5110 SPI Configuration" >> ${DEPLOYDIR}/bcm2835-bootfiles/config.txt
            echo "dtparam=spi=on" >> ${DEPLOYDIR}/bcm2835-bootfiles/config.txt
            bbnote "Added SPI configuration for Nokia 5110"
        fi
    else
        bbwarn "config.txt not found, Nokia 5110 SPI config not added"
    fi
}

# Run after rpi-config deployment
do_deploy[depends] = "rpi-config:do_deploy"

addtask deploy before do_build after do_install

FILES:${PN} = "${sysconfdir}/profile.d/nokia5110-config.sh"
