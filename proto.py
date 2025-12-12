#proto.py
import json, time, struct, hmac, hashlib, os

#Shared secret for HMAC integrity (set CHAT_SECRET in env for production)
SECRET = os.environ.get("CHAT_SECRET", "dev-shared-secret").encode("utf-8")

def now_ms() -> int:
    return int(time.time() * 1000)

def _canon(obj: dict) -> bytes:
    #Exclude 'mac' from signature
    obj2 = {k: v for k, v in obj.items() if k != "mac"}
    return json.dumps(obj2, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")

def sign(obj: dict) -> dict:
    mac = hmac.new(SECRET, _canon(obj), hashlib.sha256).hexdigest()
    out = dict(obj); out["mac"] = mac
    return out

def verify(obj: dict) -> bool:
    mac = obj.get("mac")
    if not mac:
        return False
    expect = hmac.new(SECRET, _canon(obj), hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, expect)

def dumps(obj: dict) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")

def loads(b: bytes) -> dict:
    return json.loads(b.decode("utf-8", errors="replace"))

# ---- TCP framing: 4-byte big-endian length prefix ----
def pack_frame(obj: dict) -> bytes:
    body = dumps(obj)
    return struct.pack("!I", len(body)) + body

def tcp_recv_frames(sock, buf: bytearray):
    """
    Read from a non-blocking TCP socket into 'buf' and yield decoded JSON frames.
    Returns False if the peer closed; True if no full frame yet.
    """
    try:
        chunk = sock.recv(4096)
    except BlockingIOError:
        chunk = b""
    if chunk == b"":     #peer closed (definitive close)
        return False
    if not chunk:        #would block 
        return True
    buf += chunk
    while True:
        if len(buf) < 4:
            break
        msg_len = struct.unpack("!I", buf[:4])[0]
        if len(buf) - 4 < msg_len:
            break
        body = bytes(buf[4:4+msg_len]); del buf[:4+msg_len]
        yield loads(body)
    return True
