# Containerized Edge Gateway with Dynamic WireGuard Mesh VPN

Mini project for **21CSC216P Linux and Container Technologies**, SRM Institute of Science and Technology.

**Team:** Anniya Jenet Antony (RA2411033010018), Nanditha S Biju (RA2411033010054)
**Guide:** Dr. Maniraj S P

## Overview

A custom Podman image (`edge-gateway`) built on Alpine Linux that contains WireGuard tools and a small Flask API. Several containers from this one image act as edge nodes and form an encrypted WireGuard mesh.

- New peers are added **at runtime** through an HTTP API, with no rebuild or restart.
- Each node's private key and peer list are stored in a **Podman volume**, so they survive container deletion.
- Nodes run on a user-defined Podman network, with the API published to the host through port mapping.
- A Tkinter launcher (`demo_gui.py`) runs the whole demo in one click.

## Architecture

| Node | Underlay IP (`edgenet`) | Overlay IP (`wg0`) | Host port | Volume |
|------|-------------------------|--------------------|-----------|--------|
| edge-a | 10.89.0.11 | 10.8.0.1 | 8081 | edge-a-data |
| edge-b | 10.89.0.12 | 10.8.0.2 | 8082 | edge-b-data |
| edge-c (optional) | 10.89.0.13 | 10.8.0.3 | 8083 | edge-c-data |

- **Underlay:** Podman bridge network `edgenet` (10.89.0.0/24).
- **Overlay:** WireGuard network 10.8.0.0/24.

## API

| Method and path | Purpose |
|-----------------|---------|
| `GET /` | Node name, overlay IP and public key (JSON) |
| `GET /status` | Output of `wg show` |
| `POST /peers` | Add a peer: `pubkey`, `endpoint`, `allowed_ips` |

## Repository contents

| File | Purpose |
|------|---------|
| `Containerfile` | Image definition |
| `app.py` | Flask management API |
| `entrypoint.sh` | Creates `wg0`, generates keys, restores peers |
| `demo_gui.py` | Tkinter demo launcher |
| `README.md` | This file |

## Prerequisites

Tested on Linux Mint (VirtualBox VM) with Podman 4.9.3.

```bash
sudo apt update
sudo apt install -y podman wireguard-tools curl git python3-tk
lsmod | grep wireguard || sudo modprobe wireguard
podman --version
```

## Build and run (manual)

Rootful Podman (`sudo`) is used because WireGuard needs `NET_ADMIN`.

```bash
# 1. Build the image
sudo podman build -t edge-gateway:1.0 -f Containerfile .

# 2. Network and volumes
sudo podman network create edgenet --subnet 10.89.0.0/24
sudo podman volume create edge-a-data
sudo podman volume create edge-b-data

# 3. Run the nodes
sudo podman run -d --name edge-a --network edgenet --ip 10.89.0.11 \
  --cap-add NET_ADMIN --device /dev/net/tun \
  -e NODE_NAME=edge-a -e WG_ADDR=10.8.0.1 \
  -v edge-a-data:/data -p 8081:5000 edge-gateway:1.0

sudo podman run -d --name edge-b --network edgenet --ip 10.89.0.12 \
  --cap-add NET_ADMIN --device /dev/net/tun \
  -e NODE_NAME=edge-b -e WG_ADDR=10.8.0.2 \
  -v edge-b-data:/data -p 8082:5000 edge-gateway:1.0

sudo podman ps
```

## Verify and peer the nodes

```bash
curl localhost:8081/    # note edge-a public_key
curl localhost:8082/    # note edge-b public_key

curl -X POST localhost:8081/peers -H 'Content-Type: application/json' \
  -d '{"pubkey":"<B_KEY>","endpoint":"10.89.0.12:51820","allowed_ips":"10.8.0.2/32"}'

curl -X POST localhost:8082/peers -H 'Content-Type: application/json' \
  -d '{"pubkey":"<A_KEY>","endpoint":"10.89.0.11:51820","allowed_ips":"10.8.0.1/32"}'

sudo podman exec edge-a ping -c3 10.8.0.2   # ping through the tunnel
sudo podman exec edge-a wg show             # shows latest handshake
```

Dashboard: `http://localhost:8081/status` (open it in a browser inside the VM).

## Persistence test

```bash
curl -s localhost:8081/                 # note the public_key
sudo podman rm -f edge-a
# re-run the same edge-a command from above
curl -s localhost:8081/                 # same public_key
sudo podman exec edge-a wg show         # peer restored automatically
```

## Optional: third node

```bash
sudo podman volume create edge-c-data
sudo podman run -d --name edge-c --network edgenet --ip 10.89.0.13 \
  --cap-add NET_ADMIN --device /dev/net/tun \
  -e NODE_NAME=edge-c -e WG_ADDR=10.8.0.3 \
  -v edge-c-data:/data -p 8083:5000 edge-gateway:1.0
```

Then exchange keys with edge-a and edge-b using the same `POST /peers` calls.

## Container management commands

```bash
sudo podman ps -a                 # list containers
sudo podman logs -f edge-a        # logs
sudo podman exec -it edge-a sh    # shell inside the container
sudo podman inspect edge-a        # full configuration
sudo podman stats --no-stream     # resource usage
sudo podman stop edge-a && sudo podman start edge-a
sudo podman restart edge-a
sudo podman network inspect edgenet
sudo podman volume inspect edge-a-data
```

## Push and pull from Docker Hub

```bash
sudo podman login docker.io
sudo podman tag edge-gateway:1.0 docker.io/<username>/edge-gateway:1.0
sudo podman push docker.io/<username>/edge-gateway:1.0

# on a clean system
sudo podman pull docker.io/<username>/edge-gateway:1.0
```

Registry link: https://hub.docker.com/r/<username>/edge-gateway

## Demo launcher (GUI)

```bash
sudo python3 demo_gui.py
```

If it reports no display, run `xhost +si:localuser:root` and try again.

- **Run Full Demo:** build, network, volumes, run, peer, ping and persistence test.
- **Show Status:** `podman ps -a`, network inspect and volume list.
- **Cleanup:** stops and removes the containers, network and volumes.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `RTNETLINK answers: Operation not permitted` | `NET_ADMIN` missing | Re-create the container with `--cap-add NET_ADMIN` |
| Cannot create `wg0` | WireGuard module not loaded | `sudo modprobe wireguard` |
| `address already in use` | Host port taken | Change the `-p` mapping or check `ss -tulpn` |
| No handshake in `wg show` | Wrong endpoint or swapped keys | Check endpoints and keys, ping the underlay IP |
| Key changes after re-create | Volume not mounted | Check `podman inspect edge-a` mounts |
| Container exits immediately | Script error | `podman logs edge-a` |

## Cleanup

```bash
sudo podman rm -f edge-a edge-b edge-c
sudo podman network rm edgenet
sudo podman volume rm edge-a-data edge-b-data edge-c-data
```

Removing a volume deletes the node's keys permanently.

## Notes and limitations

- The API has no authentication and uses the Flask development server. Use it only on a trusted network.
- Rootful Podman is used because WireGuard needs network capabilities.
