# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The chocolate-cli authors
# This file was written with the help of AI (Claude, by Anthropic). It is provided AS IS,
# WITHOUT ANY WARRANTY; use it at your own risk. See LICENSE and README.md.
"""Mostra as gravações do app (decodificadas) e o registro A após cada uma.

Uso: python3 -I tools/state.py LOG [prefixo_do_marcador]
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sysex_log import parse
import protocol as P

mem = bytearray(32768)  # cobre Chocolate (1858) e Plus (23646)
only = sys.argv[2] if len(sys.argv) > 2 else None
for mk, d, m in parse(sys.argv[1]):
    if len(m) < 18 or not P.has_data(m):
        continue
    a, data = P.parse_data(m)
    old = bytes(mem[a:a + len(data)])
    mem[a:a + len(data)] = data
    if d == "app->aparelho" and (not only or (mk or "").startswith(only)):
        ch = [(a + i, o, n) for i, (o, n) in enumerate(zip(old, data)) if o != n]
        print(f"[{mk}] grava addr={a} len={len(data)} mudanças={ch}")
