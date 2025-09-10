from examples.app.hot_utils import wait_http, wait_grpc_optional
from examples.clients.pet_client import list_pets, create_pet, get_pet
from examples.clients.orders_client import get_order, create_order


def run_hot_path():
    wait_http()
    pets = list_pets()
    create_pet({"id": "99", "name": "Nori", "tag": "cat"})
    p = get_pet("99")
    # gRPC is optional locally; CI will generate stubs and start server
    if wait_grpc_optional():
        o1 = get_order("abc")
        o2 = create_order("SKU-1", 2)
        return {"pets": pets, "pet": p, "orders": [o1, o2]}
    return {"pets": pets, "pet": p, "orders": []}
