# Customize os-release for SpinyOS

# Override OS identification
OS_RELEASE_FIELDS:remove = "VERSION_CODENAME"
OS_RELEASE_FIELDS:append = " VARIANT_ID VARIANT HOME_URL SUPPORT_URL BUG_REPORT_URL"

VARIANT_ID = "raspberrypi4"
VARIANT = "Raspberry Pi 4 Edition"
HOME_URL = "https://spinyos.local"
SUPPORT_URL = "https://support.spinyos.local"
BUG_REPORT_URL = "https://bugs.spinyos.local"

# Additional branding
PRETTY_NAME = "SpinyOS ${DISTRO_VERSION} (${VARIANT})"
VERSION = "${DISTRO_VERSION} (${VARIANT})"

python do_compile:append() {
    # Add custom fields to os-release
    with open(d.expand('${B}/os-release'), 'a') as f:
        f.write('VARIANT_ID="%s"\n' % d.getVar('VARIANT_ID'))
        f.write('VARIANT="%s"\n' % d.getVar('VARIANT'))
        f.write('HOME_URL="%s"\n' % d.getVar('HOME_URL'))
        f.write('SUPPORT_URL="%s"\n' % d.getVar('SUPPORT_URL'))
        f.write('BUG_REPORT_URL="%s"\n' % d.getVar('BUG_REPORT_URL'))
}

