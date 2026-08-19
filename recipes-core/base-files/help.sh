#!/bin/sh
# Custom help command with multi-language support

LANG_CODE="${1:-en}"

case "$LANG_CODE" in
    tr|turkish)
        README_FILE="/etc/README.tr.md"
        ;;
    ar|arabic)
        README_FILE="/etc/README.ar.md"
        ;;
    de|german|deutsch)
        README_FILE="/etc/README.de.md"
        ;;
    en|english)
        README_FILE="/etc/README.en.md"
        ;;
    fr|french|francais)
        README_FILE="/etc/README.fr.md"
        ;;
    hi|hindi)
        README_FILE="/etc/README.hi.md"
        ;;
    *)
        echo "Unknown language: $LANG_CODE"
        echo "Available languages: en (English), tr (Turkish), ar (Arabic), de (German), fr (French), hi (Hindi)"
        echo "Usage: help [language_code]"
        echo "Example: help tr"
        exit 1
        ;;
esac

if [ -f "$README_FILE" ]; then
    more "$README_FILE"
else
    echo "README file not found: $README_FILE"
    exit 1
fi