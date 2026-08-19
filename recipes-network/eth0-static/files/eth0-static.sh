#!/bin/sh

PATH=/sbin:/usr/sbin:/bin:/usr/bin
LOGFILE=/var/log/eth0-static.log
ETH_IFACE=eth0
ETH_ADDR=192.168.50.2/24

log() {
    ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    mkdir -p "$(dirname "$LOGFILE")" 2>/dev/null || true
    echo "$ts eth0-static: $1" >> "$LOGFILE" 2>/dev/null || true
    logger -t eth0-static "$1" 2>/dev/null || true
}

i=0
while [ "$i" -lt 30 ]; do
    if ip link show "$ETH_IFACE" >/dev/null 2>&1; then
        break
    fi
    i=$((i + 1))
    sleep 1
done

if ! ip link show "$ETH_IFACE" >/dev/null 2>&1; then
    log "interface $ETH_IFACE not found"
    exit 1
fi

ip link set "$ETH_IFACE" up || {
    log "failed to bring $ETH_IFACE up"
    exit 1
}

if ip addr replace "$ETH_ADDR" dev "$ETH_IFACE"; then
    log "assigned $ETH_ADDR to $ETH_IFACE"
else
    log "failed to assign $ETH_ADDR to $ETH_IFACE"
    exit 1
fi

exit 0