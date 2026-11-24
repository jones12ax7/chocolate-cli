# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The chocolate-cli authors
# This file was written with the help of AI (Claude, by Anthropic). It is provided AS IS,
# WITHOUT ANY WARRANTY; use it at your own risk. See LICENSE and README.md.
"""Lê um log da ponte (sinco-bridge.py) e remonta as mensagens SysEx completas.

Uso como módulo: parse(path) -> lista de (marcador, direção, bytes)
Uso direto: python3 -I tools/sysex_log.py LOG  -> resumo das mensagens.
"""
import sys


def parse(path):
    out, buf, marker, cur_dir = [], {}, None, None
    for line in open(path):
        line = line.rstrip("\n")
        if line.startswith("###"):
            marker = line[4:].split(" ", 1)[1] if " " in line[4:] else line[4:]
            continue
        parts = line.split(" ", 4)
        if len(parts) < 5:
            continue
        direction = parts[1]
        data = bytes.fromhex(parts[4].replace(" ", "")) if parts[4] else b""
        b = buf.setdefault(direction, bytearray())
        if data[:1] == b"\xf0":
            b.clear()
        b += data
        if b[-1:] == b"\xf7":
            out.append((marker, direction, bytes(b)))
            b.clear()
    return out


if __name__ == "__main__":
    for marker, d, m in parse(sys.argv[1]):
        print(f"[{marker}] {d:14} len={len(m):5} {m[:24].hex(' ')}")
