from flask import Flask, request, jsonify
import subprocess, os
app = Flask(__name__)
def sh(c): return subprocess.run(c, capture_output=True, text=True).stdout

@app.route("/")
def index():
    return jsonify(node=os.environ.get("NODE_NAME"),
                   wg_ip=os.environ.get("WG_ADDR"),
                   public_key=open("/data/public.key").read().strip())

@app.route("/status")
def status(): return "<pre>" + sh(["wg", "show"]) + "</pre>"

@app.route("/peers", methods=["POST"])
def add_peer():
    d = request.json
    subprocess.run(["wg","set","wg0","peer",d["pubkey"],"endpoint",d["endpoint"],
                    "allowed-ips",d["allowed_ips"],"persistent-keepalive","10"], check=True)
    open("/data/peers.txt","a").write(f'{d["pubkey"]} {d["endpoint"]} {d["allowed_ips"]}\n')
    return jsonify(ok=True)

app.run(host="0.0.0.0", port=5000)
