import tkinter as tk
from tkinter import scrolledtext
import subprocess, threading, json, time, os, urllib.request

DIR = os.path.dirname(os.path.abspath(__file__))
IMG, NET = "edge-gateway:1.0", "edgenet"
NODES = {
    "edge-a": dict(ip="10.89.0.11", wg="10.8.0.1", port=8081),
    "edge-b": dict(ip="10.89.0.12", wg="10.8.0.2", port=8082),
}

class App:
    def __init__(self, root):
        self.root = root
        root.title("Containerized Edge Gateway - WireGuard Mesh Demo")
        root.geometry("900x600")
        tk.Label(root, text="Containerized Edge Gateway with Dynamic WireGuard Mesh VPN",
                 font=("Arial", 14, "bold")).pack(pady=8)
        bar = tk.Frame(root); bar.pack()
        self.btn_run = tk.Button(bar, text="Run Full Demo", width=16, command=lambda: self.go(self.demo))
        self.btn_clean = tk.Button(bar, text="Cleanup", width=16, command=lambda: self.go(self.cleanup))
        self.btn_dash = tk.Button(bar, text="Show Status", width=16, command=lambda: self.go(self.status))
        for b in (self.btn_run, self.btn_dash, self.btn_clean): b.pack(side="left", padx=6)
        self.rm_img = tk.BooleanVar()
        tk.Checkbutton(root, text="Also remove image on cleanup", variable=self.rm_img).pack()
        self.out = scrolledtext.ScrolledText(root, bg="#111", fg="#0f0", font=("Courier", 10))
        self.out.pack(fill="both", expand=True, padx=8, pady=8)
        self.out.tag_config("step", foreground="#ffd700", font=("Courier", 11, "bold"))
        self.out.tag_config("ok", foreground="#00ffff")

    def log(self, text, tag=None):
        self.out.insert("end", text + "\n", tag)
        self.out.see("end")

    def step(self, text): self.log("\n=== " + text + " ===", "step")

    def sh(self, *args):
        self.log("$ " + " ".join(args))
        p = subprocess.run(args, cwd=DIR, capture_output=True, text=True)
        o = (p.stdout + p.stderr).strip()
        if o: self.log(o)
        return p

    def go(self, fn):
        for b in (self.btn_run, self.btn_clean, self.btn_dash): b.config(state="disabled")
        def work():
            try: fn()
            except Exception as e: self.log(f"ERROR: {e}")
            finally:
                for b in (self.btn_run, self.btn_clean, self.btn_dash):
                    self.root.after(0, lambda b=b: b.config(state="normal"))
        threading.Thread(target=work, daemon=True).start()

    def start_node(self, name):
        n = NODES[name]
        self.sh("podman", "rm", "-f", name)
        self.sh("podman", "run", "-d", "--name", name, "--network", NET, "--ip", n["ip"],
                "--cap-add", "NET_ADMIN", "--device", "/dev/net/tun",
                "-e", f"NODE_NAME={name}", "-e", f"WG_ADDR={n['wg']}",
                "-v", f"{name}-data:/data", "-p", f"{n['port']}:5000", IMG)

    def info(self, name):
        url = f"http://localhost:{NODES[name]['port']}/"
        for _ in range(15):
            try: return json.load(urllib.request.urlopen(url, timeout=3))
            except Exception: time.sleep(1)
        raise RuntimeError(f"{name} did not respond on {url}")

    def peer(self, src, dst, dst_key):
        d = NODES[dst]
        body = json.dumps(dict(pubkey=dst_key, endpoint=f"{d['ip']}:51820",
                               allowed_ips=f"{d['wg']}/32")).encode()
        req = urllib.request.Request(f"http://localhost:{NODES[src]['port']}/peers",
                                     body, {"Content-Type": "application/json"})
        self.log(f"POST {src} -> peer {dst}: " + urllib.request.urlopen(req, timeout=5).read().decode())

    def demo(self):
        self.out.delete("1.0", "end")
        self.step("0. Clean slate"); self.cleanup(quiet=True)
        self.step("1. Build custom image from Containerfile")
        self.sh("podman", "build", "-t", IMG, "-f", "Containerfile", ".")
        self.step("2. Create Podman network and volumes")
        self.sh("podman", "network", "create", NET, "--subnet", "10.89.0.0/24")
        for n in NODES: self.sh("podman", "volume", "create", f"{n}-data")
        self.step("3. Run edge nodes (port mapping 8081, 8082)")
        for n in NODES: self.start_node(n)
        self.sh("podman", "ps")
        self.step("4. Fetch node keys via API")
        ka, kb = self.info("edge-a")["public_key"], self.info("edge-b")["public_key"]
        self.log(f"edge-a key: {ka}\nedge-b key: {kb}")
        self.step("5. Dynamically peer the nodes")
        self.peer("edge-a", "edge-b", kb); self.peer("edge-b", "edge-a", ka)
        self.step("6. Test tunnel (ping over WireGuard)")
        self.sh("podman", "exec", "edge-a", "ping", "-c", "3", "10.8.0.2")
        self.sh("podman", "exec", "edge-a", "wg", "show")
        self.step("7. Persistence test: delete edge-a and recreate it")
        self.sh("podman", "rm", "-f", "edge-a")
        self.start_node("edge-a")
        ka2 = self.info("edge-a")["public_key"]
        self.log("Same key after recreate: " + str(ka == ka2), "ok")
        time.sleep(2)
        self.sh("podman", "exec", "edge-a", "ping", "-c", "3", "10.8.0.2")
        self.sh("podman", "exec", "edge-a", "wg", "show")
        self.step("DEMO COMPLETE - dashboards: http://localhost:8081/status and :8082/status")

    def status(self):
        self.step("Status")
        self.sh("podman", "ps", "-a")
        self.sh("podman", "network", "inspect", NET)
        self.sh("podman", "volume", "ls")

    def cleanup(self, quiet=False):
        if not quiet: self.step("Cleanup")
        for n in NODES: self.sh("podman", "rm", "-f", n)
        self.sh("podman", "network", "rm", "-f", NET)
        for n in NODES: self.sh("podman", "volume", "rm", "-f", f"{n}-data")
        if self.rm_img.get() and not quiet: self.sh("podman", "rmi", "-f", IMG)
        if not quiet: self.log("Everything stopped and removed.", "ok")

root = tk.Tk()
App(root)
root.mainloop()
