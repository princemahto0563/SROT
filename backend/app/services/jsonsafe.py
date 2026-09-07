"""Coerce values into something the JSON columns can store.

NumPy scalars, bytes and datetimes leak in from OpenCV/ffprobe/PIL. Rather than
patching each call site, every JSON column write goes through this.
"""
from __future__ import annotations
import datetime as dt
import numpy as np


def jsonable(o):
    if o is None or isinstance(o, (str, int, float, bool)):
        return o
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, np.ndarray):
        return jsonable(o.tolist())
    if isinstance(o, (bytes, bytearray, memoryview)):
        return bytes(o).decode("utf-8", "replace")[:300]
    if isinstance(o, dt.datetime):
        return o.isoformat()
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [jsonable(v) for v in o]
    return str(o)[:500]
