import requests

BASE = "http://127.0.0.1:8000"

def list_pets():
    r = requests.get(f"{BASE}/pets", timeout=2.0)
    r.raise_for_status()
    return r.json()

def create_pet(pet: dict):
    r = requests.post(f"{BASE}/pets", json=pet, timeout=2.0)
    r.raise_for_status()
    return r.json()

def get_pet(pid: str):
    r = requests.get(f"{BASE}/pets/{pid}", timeout=2.0)
    r.raise_for_status()
    return r.json()
