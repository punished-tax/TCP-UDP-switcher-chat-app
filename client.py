#client.py
import argparse, socket, threading, sys, datetime
from proto import pack_frame, tcp_recv_frames, loads, dumps, sign, verify

def fmt_ts(ms):
    return datetime.datetime.fromtimestamp(ms/1000).strftime("%H:%M:%S")

def show(obj):
    t = obj.get("type")
    if t == "msg":
        print(f"[{fmt_ts(obj['ts'])}] {obj.get('name','?')}: {obj.get('text','')}")
    elif t == "sys":
        print(f"[{fmt_ts(obj['ts'])}] * {obj.get('text','')}")
    elif t == "list":
        print(f"[{fmt_ts(obj['ts'])}] * Users: {', '.join(obj.get('users', []))}")
    elif t == "whisper":
        print(f"[{fmt_ts(obj['ts'])}] (whisper from {obj.get('from','?')}): {obj.get('text','')}")
    elif t == "err":
        print(f"[{fmt_ts(obj['ts'])}] ! {obj.get('text','')}")

def recv_tcp(sock):
    buf = bytearray()
    while True:
        out = tcp_recv_frames(sock, buf)
        if out is False:
            print("** disconnected **")
            break
        for obj in out if not isinstance(out, bool) else []:
            if verify(obj):
                show(obj)

def recv_udp(sock):
    while True:
        try:
            data = sock.recv(65535)
        except Exception:
            break
        try:
            obj = loads(data)
        except Exception:
            continue
        if verify(obj):
            show(obj)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=12000)
    ap.add_argument("--mode", choices=["tcp", "udp"], default="tcp")
    ap.add_argument("--name", required=True)
    args = ap.parse_args()

    if args.mode == "tcp":
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((args.host, args.port))
        s.setblocking(False)
        s.sendall(pack_frame(sign({"type": "join", "name": args.name})))
        threading.Thread(target=recv_tcp, args=(s,), daemon=True).start()
        print("Connected (TCP). Commands: /list, /whisper <name> <msg>, /quit")
        for line in sys.stdin:
            line = line.rstrip("\n")
            if not line:
                continue
            if line == "/quit":
                break
            if line.startswith("/list"):
                s.sendall(pack_frame(sign({"type": "cmd", "cmd": "list"})))
                continue
            if line.startswith("/whisper "):
                parts = line.split(maxsplit=2)
                if len(parts) < 3:
                    print("usage: /whisper <name> <message>")
                    continue
                _, to, text = parts
                s.sendall(pack_frame(sign({"type": "cmd", "cmd": "whisper", "to": to, "text": text})))
                continue
            s.sendall(pack_frame(sign({"type": "msg", "text": line})))
        try:
            s.sendall(pack_frame(sign({"type": "leave"})))
        except Exception:
            pass
        s.close()

    else:  #UDP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((args.host, args.port))  #allows recv() without address
        s.send(dumps(sign({"type": "join", "name": args.name})))
        threading.Thread(target=recv_udp, args=(s,), daemon=True).start()
        print("Connected (UDP). Commands: /list, /whisper <name> <msg>, /quit")
        for line in sys.stdin:
            line = line.rstrip("\n")
            if not line:
                continue
            if line == "/quit":
                break
            if line.startswith("/list"):
                s.send(dumps(sign({"type": "cmd", "cmd": "list"})))
                continue
            if line.startswith("/whisper "):
                parts = line.split(maxsplit=2)
                if len(parts) < 3:
                    print("usage: /whisper <name> <message>")
                    continue
                _, to, text = parts
                s.send(dumps(sign({"type": "cmd", "cmd": "whisper", "to": to, "text": text})))
                continue
            s.send(dumps(sign({"type": "msg", "text": line})))
        try:
            s.send(dumps(sign({"type": "leave"})))
        except Exception:
            pass
        s.close()

if __name__ == "__main__":
    main()
