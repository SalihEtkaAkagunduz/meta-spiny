SUMMARY = "SpinyOS orchestrator service"
DESCRIPTION = "WebSocket-based orchestrator with package command channel and policy enforcement"
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

SRC_URI = " \
    file://spiny-orchestrator.py \
    file://spiny-orchestrator.service \
    file://orchestrator-policy.json \
    file://orchestrator-auth.json \
    file://orchestrator-manifest.json \
    file://orchestrator-peers.json \
"

S = "${WORKDIR}"

inherit systemd

SYSTEMD_SERVICE:${PN} = "spiny-orchestrator.service"


do_install() {
    install -d ${D}${bindir}
    install -m 0755 ${WORKDIR}/spiny-orchestrator.py ${D}${bindir}/spiny-orchestrator.py

    install -d ${D}${systemd_unitdir}/system
    install -m 0644 ${WORKDIR}/spiny-orchestrator.service ${D}${systemd_unitdir}/system/spiny-orchestrator.service

    install -d ${D}${sysconfdir}/spiny
    install -m 0644 ${WORKDIR}/orchestrator-policy.json ${D}${sysconfdir}/spiny/orchestrator-policy.json
    install -m 0600 ${WORKDIR}/orchestrator-auth.json ${D}${sysconfdir}/spiny/orchestrator-auth.json
    install -m 0644 ${WORKDIR}/orchestrator-manifest.json ${D}${sysconfdir}/spiny/orchestrator-manifest.json
    install -m 0600 ${WORKDIR}/orchestrator-peers.json ${D}${sysconfdir}/spiny/orchestrator-peers.json
}

FILES:${PN} += " \
    ${bindir}/spiny-orchestrator.py \
    ${systemd_unitdir}/system/spiny-orchestrator.service \
    ${sysconfdir}/spiny/orchestrator-policy.json \
    ${sysconfdir}/spiny/orchestrator-auth.json \
    ${sysconfdir}/spiny/orchestrator-manifest.json \
    ${sysconfdir}/spiny/orchestrator-peers.json \
"

RDEPENDS:${PN} += " \
    python3-core \
    python3-websockets \
    python3-pip \
"

SYSTEMD_AUTO_ENABLE:${PN} = "enable"
