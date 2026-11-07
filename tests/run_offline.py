#!/usr/bin/env python3
"""Run bundled regressions without allowing DNS or outbound connections.

Defence-in-depth guards for this trusted test suite, not an OS security sandbox.
Never loads operator credentials or invokes main() with a live target.
"""
import socket
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


def blocked(*args, **kwargs):
    raise AssertionError("Network access is forbidden during offline tests")


def main():
    tests = Path(__file__).resolve().parent
    with (patch.object(socket.socket, "connect", blocked),
          patch.object(socket.socket, "connect_ex", blocked),
          patch.object(socket, "create_connection", blocked),
          patch.object(socket, "getaddrinfo", blocked)):
        suite = unittest.defaultTestLoader.discover(str(tests), pattern="test_*.py")
        if suite.countTestCases() == 0:
            raise RuntimeError("No tests discovered")
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        print("Network connection and DNS guards were enabled throughout the suite.")
        return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
