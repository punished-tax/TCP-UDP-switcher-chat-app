#server.py
import selectors, socket, types, traceback
from proto import pack_frame, tcp_recv_frames, now_ms, loads, dumps

HOST, PORT = "0.0.0.0", 12000

sel = selectors.DefaultSelector()

#TCP listen socket
ls = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
ls.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
ls.bind((HOST, PORT)); ls.listen(); ls.setblocking(False)
sel.register(ls, selectors.EVENT_READ, data=("accept", None))

#UDP socket
us = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
us.bind((HOST, PORT)); us.setblocking(False)
sel.register(us, selectors.EVENT_READ, data=("udp", None))

tcp_buf = {}    #sock -> bytearray
tcp_nick = {}   #sock -> nick
udp_nick = {}   #(addr,port) -> nick

def tcp_broadcast(obj, exclude=None):
    msg = pack_frame(obj)
    for s in list(tcp_nick.keys()):
        if s is exclude: continue
        try: s.sendall(msg)
        except Exception:
            close_tcp(s)

def udp_broadcast(obj, exclude_addr=None):
    msg = dumps(obj)
    for addr in list(udp_nick.keys()):
        if addr == exclude_addr: continue
        try: us.sendto(msg, addr)
        except Exception: udp_nick.pop(addr, None)

def close_tcp(s):
    nick = tcp_nick.pop(s, None)
    tcp_buf.pop(s, None)
    try: sel.unregister(s)
    except Exception: pass
    try: s.close()
    except Exception: pass
    if nick:
        tcp_broadcast({"type":"sys","mode":"tcp","text":f"{nick} left","ts":now_ms()})

print(f"Chat server ready on TCP/UDP {HOST}:{PORT}")

while True:
    for key, ev in sel.select(timeout=1.0):
        kind, _ = key.data
        try:
            if kind == "accept":  #new TCP connection
                conn, addr = key.fileobj.accept()
                conn.setblocking(False)
                tcp_buf[conn] = bytearray()
                sel.register(conn, selectors.EVENT_READ, data=("tcp", None))
            elif kind == "tcp":   #TCP client traffic
                s = key.fileobj
                cont = tcp_recv_frames(s, tcp_buf[s])
                if cont is False:
                    close_tcp(s); continue
                for obj in cont if not isinstance(cont, bool) else []:
                    t = obj.get("type")
                    if t == "join":
                        tcp_nick[s] = obj.get("nick","?")
                        tcp_broadcast({"type":"sys","mode":"tcp","text":f"{tcp_nick[s]} joined","ts":now_ms()})
                    elif t == "msg":
                        nick = tcp_nick.get(s, "?")
                        tcp_broadcast({"type":"msg","mode":"tcp","nick":nick,"text":obj.get("text",""),"ts":now_ms()})
                    elif t == "leave":
                        close_tcp(s)
            elif kind == "udp":   #UDP datagram
                data, addr = us.recvfrom(65535)
                try:
                    obj = loads(data)
                except Exception:
                    continue
                t = obj.get("type")
                if t == "join":
                    udp_nick[addr] = obj.get("nick","?")
                    udp_broadcast({"type":"sys","mode":"udp","text":f"{udp_nick[addr]} joined","ts":now_ms()})
                elif t == "msg":
                    nick = udp_nick.get(addr, obj.get("nick","?"))
                    udp_nick.setdefault(addr, nick)
                    udp_broadcast({"type":"msg","mode":"udp","nick":nick,"text":obj.get("text",""),"ts":now_ms()})
                elif t == "leave":
                    nick = udp_nick.pop(addr, None)
                    if nick:
                        udp_broadcast({"type":"sys","mode":"udp","text":f"{nick} left","ts":now_ms()})
        except Exception:
            #defensive: don't crash on one bad client
            if kind == "tcp":
                close_tcp(key.fileobj)
            else:
                traceback.print_exc()
