#!/usr/bin/env python3
# One latency probe for the Connections panel (click a node): DNS + TCP connect to port 443, same as network.sh. Prints ms, 0 if down.
import socket, sys, time
t = time.monotonic()
try: socket.create_connection((sys.argv[1], 443), timeout=3).close(); print(round((time.monotonic() - t) * 1000))
except (OSError, IndexError): print(0)
