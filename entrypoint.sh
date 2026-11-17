#!/bin/sh
set -e
mkdir -p /data
[ -f /data/private.key ] || { wg genkey | tee /data/private.key | wg pubkey > /data/public.key; }
ip link add wg0 type wireguard 2>/dev/null || true
ip addr add ${WG_ADDR}/24 dev wg0 2>/dev/null || true
wg set wg0 listen-port 51820 private-key /data/private.key
ip link set wg0 up
# restore saved peers from the volume
[ -f /data/peers.txt ] && while read pk ep ips; do
  wg set wg0 peer $pk endpoint $ep allowed-ips $ips persistent-keepalive 10
done < /data/peers.txt
exec python3 /app/app.py
