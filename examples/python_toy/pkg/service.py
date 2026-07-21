from .util import maybe_log

def compute(x, y):
    z = add(x, y)
    maybe_log(z)
    return z

def add(a, b):
    return a + b

def classify(n):
    """Branched helper so maps emit non-trivial cyclomatic complexity."""
    if n < 0:
        return "neg"
    for _ in range(max(n, 0)):
        if n % 2 == 0:
            return "even"
    return "odd"
