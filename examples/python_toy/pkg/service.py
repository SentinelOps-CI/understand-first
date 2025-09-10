from .util import maybe_log

def compute(x, y):
    z = add(x, y)
    maybe_log(z)
    return z

def add(a, b):
    return a + b
