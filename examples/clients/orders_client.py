import os, sys
import grpc

GEN = os.path.join(os.path.dirname(__file__), "..", "apis", "gen")
sys.path.insert(0, os.path.abspath(GEN))
try:
    import orders_pb2, orders_pb2_grpc  # type: ignore
except Exception:
    orders_pb2 = None
    orders_pb2_grpc = None

ADDR = "127.0.0.1:50051"

def get_order(oid: str):
    if orders_pb2 is None:  # not generated yet
        return {"id": oid, "status": "SKIPPED"}
    channel = grpc.insecure_channel(ADDR)
    stub = orders_pb2_grpc.OrdersStub(channel)
    resp = stub.GetOrder(orders_pb2.OrderRequest(id=oid), timeout=1.0)
    return {"id": resp.id, "status": resp.status}

def create_order(sku: str, qty: int):
    if orders_pb2 is None:
        return {"id": "SKIPPED", "status": "SKIPPED"}
    channel = grpc.insecure_channel(ADDR)
    stub = orders_pb2_grpc.OrdersStub(channel)
    resp = stub.CreateOrder(orders_pb2.CreateOrderRequest(sku=sku, quantity=qty), timeout=1.0)
    return {"id": resp.id, "status": resp.status}
