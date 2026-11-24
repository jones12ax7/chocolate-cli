# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The chocolate-cli authors
# This file was written with the help of AI (Claude, by Anthropic). It is provided AS IS,
# WITHOUT ANY WARRANTY; use it at your own risk. See LICENSE and README.md.
"""Mostra, por marcador, quais bits da memória cada gravação do app alterou.

Uso: python3 -I tools/diff_writes.py LOG [prefixo_do_marcador]
Mantém uma imagem da memória a partir da primeira leitura e aplica as gravações em ordem.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sysex_log import parse

REC0, REC_LEN = 13, 161
NAMES = "ABCDEF"


def unpack(p):
    acc = n = 0
    out = bytearray()
    for b in p:
        acc |= (b & 0x7F) << n
        n += 7
        while n >= 8:
            out.append(acc & 0xFF)
            acc >>= 8
            n -= 8
    return bytes(out)


def field(m, i):
    return sum((m[i + k] & 0x7F) << (7 * k) for k in range(4))


def where(addr):
    if addr < REC0:
        return f"cab+{addr}"
    r, off = divmod(addr - REC0, REC_LEN)
    return f"{NAMES[r] if r < len(NAMES) else '?'}+{off}" if r < 6 else f"fim+{addr - REC0 - 6 * REC_LEN}"


def main(path, only=None):
    mem = {}
    for marker, d, m in parse(path):
        if len(m) < 20 or m[3] not in (0x0D, 0x09):
            continue
        cmd, addr, ln = m[4], field(m, 9), field(m, 13) >> 4
        if cmd != 0x49:
            continue
        data = unpack(m[19:-1])[:ln]
        if d == "aparelho->app":          # resposta de leitura: atualiza a imagem
            for i, b in enumerate(data):
                mem[addr + i] = b
            continue
        if only and not (marker or "").startswith(only):
            for i, b in enumerate(data):
                mem[addr + i] = b
            continue
        print(f"[{marker}] gravação addr={addr} ({where(addr)}) len={ln} chk={m[17]:02x} {m[18]:02x}")
        for i, b in enumerate(data):
            old = mem.get(addr + i)
            if old is not None and old != b:
                x = old ^ b
                bits = [k for k in range(8) if x >> k & 1]
                print(f"   byte {addr + i:4} ({where(addr + i):7}) {old:08b} -> {b:08b}  bits {bits}")
            mem[addr + i] = b


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
