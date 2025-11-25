#proto.py
import json, time, struct

def now_ms() -> int:
    return int(time.time() * 1000)

def dumps(obj) -> bytes:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def loads(b: bytes):
    return json.loads(b.decode("utf-8", errors="replace"))

# ---- TCP framing: 4-byte big-endian length prefix ----
def pack_frame(obj) -> bytes:
    body = dumps(obj)
    return struct.pack("!I", len(body)) + body

def tcp_recv_frames(sock, buf: bytearray):
    """Yield decoded JSON objects as they become available. Returns False if closed."""
    import struct
    try:
        chunk = sock.recv(4096)
    except BlockingIOError:
        chunk = b""
    if not chunk:
        #peer closed or no data (would block): on closed, recv==b""
        if chunk == b"":  #definite close
            return False
        return True
    buf += chunk
    #parse as many frames as available
    while True:
        if len(buf) < 4:
            break
        msg_len = struct.unpack("!I", buf[:4])[0]
        if len(buf) - 4 < msg_len:
            break
        body = bytes(buf[4:4+msg_len]); del buf[:4+msg_len]
        yield loads(body)
    return True
