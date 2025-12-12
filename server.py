#server.py
import selectors, socket, traceback
from proto import pack_frame, tcp_recv_frames, now_ms, loads, dumps, sign, verify

HOST, PORT = "0.0.0.0", 12000
sel = selectors.DefaultSelector()

#TCP listener
ls = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
ls.bind((HOST, PORT))
ls.listen()
ls.setblocking(False)
sel.register(ls, selectors.EVENT_READ, data=("accept", None))

#UDP socket
us = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
us.bind((HOST, PORT))
us.setblocking(False)
sel.register(us, selectors.EVENT_READ, data=("udp", None))

# ---- State ----
tcp_buf = {}        #sock -> bytearray
name_tcp = {}       #name -> sock
name_udp = {}       #name -> (addr, port)
tcp_name = {}       #sock -> name
udp_name = {}       #(addr,port) -> name

def all_names():
    return sorted(set(name_tcp.keys()) | set(name_udp.keys()))

def send_tcp(sock, obj):
    try:
        sock.sendall(pack_frame(sign(obj)))
    except Exception:
        close_tcp(sock)

def send_udp(addr, obj):
    try:
        us.sendto(dumps(sign(obj)), addr)
    except Exception:
        pass

def broadcast(obj, exclude_tcp=None, exclude_udp=None):
    msg = sign(obj)
    data_tcp = pack_frame(msg)
    data_udp = dumps(msg)
    #TCP
    for n, s in list(name_tcp.items()):
        if s is exclude_tcp:
            continue
        try:
            s.sendall(data_tcp)
        except Exception:
            close_tcp(s)
    #UDP
    for n, addr in list(name_udp.items()):
        if addr == exclude_udp:
            continue
        try:
            us.sendto(data_udp, addr)
        except Exception:
            pass

def close_tcp(s):
    name = tcp_name.pop(s, None)
    if name:
        name_tcp.pop(name, None)
        broadcast({"type": "sys", "text": f"{name} left", "ts": now_ms()})
    try:
        sel.unregister(s)
    except Exception:
        pass
    try:
        s.close()
    except Exception:
        pass

def handle_join(name, transport, sock=None, addr=None):
    if not name or name in all_names():
        obj = {"type": "err", "text": "Name taken or invalid", "ts": now_ms()}
        if transport == "tcp" and sock:
            send_tcp(sock, obj)
        elif addr:
            send_udp(addr, obj)
        return False
    if transport == "tcp" and sock:
        tcp_name[sock] = name
        name_tcp[name] = sock
    else:
        udp_name[addr] = name
        name_udp[name] = addr
    broadcast({"type": "sys", "text": f"{name} joined", "ts": now_ms()})
    return True

def handle_msg(name, text, from_tcp=None, from_udp=None):
    broadcast({"type": "msg", "name": name, "text": text, "ts": now_ms()},
              exclude_tcp=from_tcp, exclude_udp=from_udp)

def handle_list(target_tcp=None, target_udp=None):
    obj = {"type": "list", "users": all_names(), "ts": now_ms()}
    if target_tcp:
        send_tcp(target_tcp, obj)
    if target_udp:
        send_udp(target_udp, obj)

def handle_whisper(sender, to_name, text):
    if to_name in name_tcp:
        send_tcp(name_tcp[to_name], {"type": "whisper", "from": sender, "text": text, "ts": now_ms()})
        return True
    if to_name in name_udp:
        send_udp(name_udp[to_name], {"type": "whisper", "from": sender, "text": text, "ts": now_ms()})
        return True
    return False

print(f"Chat server established on {HOST}:{PORT}")

while True:
    for key, ev in sel.select(timeout=1.0):
        kind, _ = key.data
        try:
            if kind == "accept":
                conn, addr = key.fileobj.accept()
                conn.setblocking(False)
                tcp_buf[conn] = bytearray()
                sel.register(conn, selectors.EVENT_READ, data=("tcp", None))

            elif kind == "tcp":
                s = key.fileobj
                out = tcp_recv_frames(s, tcp_buf[s])
                if out is False:
                    close_tcp(s)
                    continue
                for obj in out if not isinstance(out, bool) else []:
                    if not verify(obj):
                        send_tcp(s, {"type": "err", "text": "Bad MAC", "ts": now_ms()})
                        continue
                    t = obj.get("type")
                    name = tcp_name.get(s)
                    if t == "join":
                        handle_join(obj.get("name", ""), "tcp", sock=s)
                    elif t == "msg" and name:
                        handle_msg(name, obj.get("text", ""), from_tcp=s)
                    elif t == "cmd" and name:
                        cmd = obj.get("cmd")
                        if cmd == "list":
                            handle_list(target_tcp=s)
                        elif cmd == "whisper":
                            ok = handle_whisper(name, obj.get("to", ""), obj.get("text", ""))
                            if not ok:
                                send_tcp(s, {"type": "err", "text": "No such user", "ts": now_ms()})
                    elif t == "leave" and name:
                        close_tcp(s)

            elif kind == "udp":
                data, addr = us.recvfrom(65535)
                try:
                    obj = loads(data)
                except Exception:
                    continue
                if not verify(obj):
                    send_udp(addr, {"type": "err", "text": "Bad MAC", "ts": now_ms()})
                    continue
                t = obj.get("type")
                if t == "join":
                    handle_join(obj.get("name", ""), "udp", addr=addr)
                elif t == "msg":
                    name = udp_name.get(addr)
                    if name:
                        handle_msg(name, obj.get("text", ""), from_udp=addr)
                elif t == "cmd":
                    cmd = obj.get("cmd")
                    if cmd == "list":
                        handle_list(target_udp=addr)
                    elif cmd == "whisper":
                        sender = udp_name.get(addr)
                        if not sender:
                            send_udp(addr, {"type": "err", "text": "Join first", "ts": now_ms()})
                        else:
                            ok = handle_whisper(sender, obj.get("to", ""), obj.get("text", ""))
                            if not ok:
                                send_udp(addr, {"type": "err", "text": "No such user", "ts": now_ms()})
                elif t == "leave":
                    name = udp_name.pop(addr, None)
                    if name:
                        name_udp.pop(name, None)
                        broadcast({"type": "sys", "text": f"{name} left", "ts": now_ms()})
        except Exception:
            if kind == "tcp":
                close_tcp(key.fileobj)
            else:
                traceback.print_exc()
