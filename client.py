#client.py
import argparse, socket, threading, sys, time, datetime
from proto import pack_frame, tcp_recv_frames, now_ms, loads, dumps

def fmt_ts(ms):
    return datetime.datetime.fromtimestamp(ms/1000).strftime("%H:%M:%S")

def recv_tcp(sock):
    buf = bytearray()
    while True:
        cont = tcp_recv_frames(sock, buf)
        if cont is False: print("** disconnected **"); break
        for obj in cont if not isinstance(cont, bool) else []:
            show(obj)

def recv_udp(sock):
    while True:
        try: data = sock.recv(65535)
        except Exception: break
        try: obj = loads(data)
        except Exception: continue
        show(obj)
        

def show(obj):
    t = obj.get("type")
    if t == "msg":
        print(f"[{fmt_ts(obj.get('ts', now_ms()))}][{obj.get('mode','?')}] {obj.get('nick','?')}: {obj.get('text','')}")
    elif t == "sys":
        print(f"[{fmt_ts(obj.get('ts', now_ms()))}][{obj.get('mode','?')}] * {obj.get('text','')}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=12000)
    ap.add_argument("--mode", choices=["tcp","udp"], default="tcp")
    ap.add_argument("--nick", required=True)
    args = ap.parse_args()

    if args.mode == "tcp":
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((args.host, args.port)); s.setblocking(False)
        s.sendall(pack_frame({"type":"join","nick":args.nick}))
        threading.Thread(target=recv_tcp, args=(s,), daemon=True).start()
        print("Connected via TCP. Type /quit to exit.")
        for line in sys.stdin:
            line = line.rstrip("\n")
            if line.strip() == "/quit": break
            s.sendall(pack_frame({"type":"msg","text":line}))
        try: s.sendall(pack_frame({"type":"leave"}))
        except Exception: pass
        s.close()
    else:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #"Connect" UDP so we can recv() without address tuple
        s.connect((args.host, args.port))
        s.send(dumps({"type":"join","nick":args.nick}))
        threading.Thread(target=recv_udp, args=(s,), daemon=True).start()
        print("Connected via UDP. Type /quit to exit.")
        for line in sys.stdin:
            line = line.rstrip("\n")
            if line.strip() == "/quit": break
            s.send(dumps({"type":"msg","nick":args.nick,"text":line}))
        try: s.send(dumps({"type":"leave","nick":args.nick}))
        except Exception: pass
        s.close()

if __name__ == "__main__":
    main()
