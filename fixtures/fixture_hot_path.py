from examples.app.hot_path import run_hot_path

def test_hot_path():
    out = run_hot_path()
    assert "pet" in out and out["pet"]["id"] == "99"

if __name__ == "__main__":
    test_hot_path()
