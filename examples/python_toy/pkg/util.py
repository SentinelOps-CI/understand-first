STATE = {}

def maybe_log(value):
    if value or value == 0:
        STATE['last'] = value
