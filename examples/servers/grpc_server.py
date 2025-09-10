import os, sys, time
from concurrent import futures
import grpc

# Generated at CI time into examples/apis/gen/
GEN = os.path.join(os.path.dirname(__file__), "..", "apis", "gen")
sys.path.insert(0, os.path.abspath(GEN))

import orders_pb2, orders_pb2_grpc  # type: ignore

class OrdersService(orders_pb2_grpc.OrdersServicer):
    def GetOrder(self, request, context):
        return orders_pb2.OrderResponse(id=request.id, status="OK")
    def CreateOrder(self, request, context):
        return orders_pb2.OrderResponse(id="new-123", status="CREATED")

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    orders_pb2_grpc.add_OrdersServicer_to_server(OrdersService(), server)
    server.add_insecure_port("[::]:50051")
    server.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == "__main__":
    serve()
