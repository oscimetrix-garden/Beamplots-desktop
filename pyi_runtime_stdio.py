import os
import sys


class _NullStream:
    encoding = "utf-8"

    def write(self, _text):
        return 0

    def flush(self):
        return None

    def isatty(self):
        return False

    def fileno(self):
        raise OSError("No console stream is available")


_null_stream = _NullStream()
for _name in ("stdin", "stdout", "stderr"):
    if getattr(sys, _name, None) is None:
        setattr(sys, _name, _null_stream)

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
