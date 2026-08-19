FILESEXTRAPATHS:prepend := "${THISDIR}:"
FILESEXTRAPATHS:prepend := "${THISDIR}/files:"

# Yocto resmi yöntemi: hostname değişkenini ayarla
hostname = "salihh"

SRC_URI += "file://README.en.md \
            file://README.tr.md \
            file://README.de.md \
            file://README.fr.md \
            file://README.ar.md \
            file://README.hi.md \
            file://help.sh \
            file://info.sh \
            file://buzzer-profile.sh \
           "

# Yeni dosyaları pakete ekle
FILES:${PN} += "${bindir}/help \
                ${bindir}/info \
                /usr/local/bin/help \
                /usr/local/bin/info \
                /etc/profile.d/help-override.sh \
                /etc/profile.d/info-alias.sh \
                /etc/profile.d/neofetch-alias.sh \
                /etc/profile.d/buzzer-profile.sh \
                /etc/README.md \
                /etc/README.en.md \
                /etc/README.tr.md \
                /etc/README.de.md \
                /etc/README.fr.md \
                /etc/README.ar.md \
                /etc/README.hi.md \
               "

# /etc/profile'a help function ekle - busybox built-in'i override eder
add_help_function() {
    # /etc/profile sonuna help function ekle
    if [ -f ${IMAGE_ROOTFS}/etc/profile ]; then
        echo '' >> ${IMAGE_ROOTFS}/etc/profile
        echo '# Custom help command - overrides busybox built-in' >> ${IMAGE_ROOTFS}/etc/profile
        echo 'help() {' >> ${IMAGE_ROOTFS}/etc/profile
        echo '    /usr/bin/help "$@"' >> ${IMAGE_ROOTFS}/etc/profile
        echo '}' >> ${IMAGE_ROOTFS}/etc/profile
    fi
    
    # Root kullanıcısının .profile dosyasına da ekle
    if [ -d ${IMAGE_ROOTFS}/home/root ]; then
        echo '' >> ${IMAGE_ROOTFS}/home/root/.profile
        echo '# Custom help command' >> ${IMAGE_ROOTFS}/home/root/.profile
        echo 'help() { /usr/bin/help "$@"; }' >> ${IMAGE_ROOTFS}/home/root/.profile
    fi
}

# ROOTFS_POSTPROCESS_COMMAND: Son olarak hostname'i garanti altına al
force_hostname_salih() {
    echo "salih" > ${IMAGE_ROOTFS}/etc/hostname
    # /etc/hosts'u da güncelle
    if [ -f ${IMAGE_ROOTFS}/etc/hosts ]; then
        sed -i '/127.0.1.1/d' ${IMAGE_ROOTFS}/etc/hosts
        echo "127.0.1.1 salih" >> ${IMAGE_ROOTFS}/etc/hosts
    fi
}

ROOTFS_POSTPROCESS_COMMAND += "add_help_function; force_hostname_salih;"

do_install:append() {
    # Hostname'i /etc/hostname dosyasına yaz - FORCE override
    echo "salih" > ${D}${sysconfdir}/hostname
    
    # /etc/hosts dosyasını da güncelle
    if [ -f ${D}${sysconfdir}/hosts ]; then
        # Eski hostname satırlarını temizle
        sed -i '/127.0.1.1/d' ${D}${sysconfdir}/hosts
        # Yeni hostname'i ekle
        echo "127.0.1.1 salih" >> ${D}${sysconfdir}/hosts
    fi
    
    # README dosyalarini /etc altina kur (tum diller)
    install -m 0644 ${WORKDIR}/README.en.md ${D}/etc/README.en.md
    install -m 0644 ${WORKDIR}/README.tr.md ${D}/etc/README.tr.md
    install -m 0644 ${WORKDIR}/README.de.md ${D}/etc/README.de.md
    install -m 0644 ${WORKDIR}/README.fr.md ${D}/etc/README.fr.md
    install -m 0644 ${WORKDIR}/README.ar.md ${D}/etc/README.ar.md
    install -m 0644 ${WORKDIR}/README.hi.md ${D}/etc/README.hi.md
    
    # Geriye uyumluluk icin README.md'yi README.en.md'ye symlink yap
    ln -sf README.en.md ${D}/etc/README.md
    
    # help scriptini birden fazla yere kur (busybox built-in'i override etmek için)
    install -d ${D}${bindir}
    install -d ${D}/usr/local/bin
    install -m 0755 ${WORKDIR}/help.sh ${D}${bindir}/help
    install -m 0755 ${WORKDIR}/help.sh ${D}/usr/local/bin/help
    
    # info scriptini kur
    install -m 0755 ${WORKDIR}/info.sh ${D}${bindir}/info
    install -m 0755 ${WORKDIR}/info.sh ${D}/usr/local/bin/info
    
    # Profile'a FUNCTION ekle - busybox built-in help'i override eder
    # Function, alias'tan daha güçlüdür ve built-in komutları override edebilir
    install -d ${D}/etc/profile.d
    echo '# Override busybox built-in help with custom help' > ${D}/etc/profile.d/help-override.sh
    echo 'help() {' >> ${D}/etc/profile.d/help-override.sh
    echo '    /usr/bin/help "$@"' >> ${D}/etc/profile.d/help-override.sh
    echo '}' >> ${D}/etc/profile.d/help-override.sh
    chmod 0755 ${D}/etc/profile.d/help-override.sh
    
    # info komutu için alias ekle
    echo 'alias info="/usr/bin/info"' >> ${D}/etc/profile.d/info-alias.sh
    chmod 0755 ${D}/etc/profile.d/info-alias.sh
    
    # neofetch komutu için alias ekle
    echo 'alias neofetch="/usr/bin/info"' > ${D}/etc/profile.d/neofetch-alias.sh
    chmod 0755 ${D}/etc/profile.d/neofetch-alias.sh
    
    # buzzer profile script'ini kur
    install -m 0755 ${WORKDIR}/buzzer-profile.sh ${D}/etc/profile.d/buzzer-profile.sh
}