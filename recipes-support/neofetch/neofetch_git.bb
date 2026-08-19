SUMMARY = "A command-line system information tool written in bash"
DESCRIPTION = "Neofetch displays information about your operating system, software and hardware in an aesthetic and visually pleasing way."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

PV = "7.1.0"

# Use local neofetch script
SRC_URI = "file://neofetch"

S = "${WORKDIR}"

do_configure() {
    :
}

do_compile() {
    :
}

do_install() {
    install -d ${D}${bindir}
    install -m 0755 ${WORKDIR}/neofetch ${D}${bindir}/
}

FILES:${PN} = "${bindir}/neofetch"

RDEPENDS:${PN} = "bash"
