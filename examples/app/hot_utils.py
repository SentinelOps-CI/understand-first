import time, requests
import grpc

def wait_http(url: str = "http://127.0.0.1:8000/pets", timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=1.0)
            if r.status_code < 500:
                return True
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("HTTP server not ready")

def wait_grpc_optional(addr="127.0.0.1:50051", timeout=5):
    start = time.time()
    while time.time() - start < timeout:
        try:
            channel = grpc.insecure_channel(addr)
            grpc.channel_ready_future(channel).result(timeout=0.5)
            return True
        except Exception:
            time.sleep(0.2)
    return False
