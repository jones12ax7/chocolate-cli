# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The chocolate-cli authors
# This file was written with the help of AI (Claude, by Anthropic). It is provided AS IS,
# WITHOUT ANY WARRANTY; use it at your own risk. See LICENSE and README.md.
"""Protocolo SysEx das pedaleiras M-VAVE Chocolate (FootCtrl) e Chocolate Plus (FootCtrlPlus),
obtido por engenharia reversa. Detalhes e mapas de memória: PROTOCOLO.md.

Formato de uma mensagem de leitura/gravação de memória:

    F0 00 32 | tipo | c | n 00 00 02 | addr (4) | len<<4 (4) | payload | F7

- tipo: 0x0D (pedido de leitura e resposta), 0x09 (gravação), 0x01 (confirmação).
- c, n: carregam V = 8 + (nº de bytes de dados na mensagem): c = 0x01 | (V & 0xF) << 3,
        n = V >> 4. Pedido de leitura: V = 8 (c = 0x41, n = 0); dados: ex. len 1009 -> c = 0x49.
        Atenção: len 80 também dá c = 0x41 (com n = 5); distinguir sempre por V.
- addr, len<<4: inteiros em 7 bits little-endian, 4 bytes cada.
- payload: bytes de dados seguidos de 1 byte de checksum, compactados como fluxo
  contínuo de 7 bits (LSB primeiro).
- checksum = (0xFB - soma(bytes LE32 de addr) - soma(bytes LE32 de len) - soma(dados)) & 0xFF.

Confirmação de gravação recebida: F0 00 32 01 08 00 00 00 00 7F 01 F7.
Identificação: pedido F0 00 32 45 00 00 00 40 7F F7; a resposta traz, compactado em 7 bits,
o texto "FootCtrl_051" ou "FootCtrlPlus_013" (modelo_versão do firmware).
"""
import re

HEADER = bytes([0xF0, 0x00, 0x32])
T_READ, T_WRITE, T_ACK = 0x0D, 0x09, 0x01
CMD_READ = 0x41
ACK = bytes.fromhex("f0 00 32 01 08 00 00 00 00 7f 01 f7")
ID_REQUEST = bytes.fromhex("f0 00 32 45 00 00 00 40 7f f7")
T_ID = 0x45
MAX_CHUNK = 1009          # maior bloco que o app lê/grava de uma vez


def pack7(data: bytes) -> bytes:
    """Fluxo de bits LSB primeiro, 7 bits por byte MIDI."""
    out = bytearray()
    acc = n = 0
    for b in data:
        acc |= b << n
        n += 8
        while n >= 7:
            out.append(acc & 0x7F)
            acc >>= 7
            n -= 7
    if n:
        out.append(acc & 0x7F)
    return bytes(out)


def unpack7(data: bytes) -> bytes:
    out = bytearray()
    acc = n = 0
    for b in data:
        acc |= (b & 0x7F) << n
        n += 7
        while n >= 8:
            out.append(acc & 0xFF)
            acc >>= 8
            n -= 8
    return bytes(out)


def enc28(v: int) -> bytes:
    return bytes((v >> (7 * i)) & 0x7F for i in range(4))


def dec28(b: bytes) -> int:
    return sum((b[i] & 0x7F) << (7 * i) for i in range(4))


def checksum(addr: int, length: int, data: bytes = b"") -> int:
    s = sum(addr.to_bytes(4, "little")) + sum(length.to_bytes(4, "little")) + sum(data)
    return (0xFB - s) & 0xFF


def _frame(typ: int, addr: int, length: int, data: bytes) -> bytes:
    v = 8 + len(data)
    body = bytes([typ, 0x01 | (v & 0xF) << 3, v >> 4, 0, 0, 2]) + enc28(addr) + enc28(length << 4)
    return HEADER + body + pack7(data + bytes([checksum(addr, length, data)])) + b"\xF7"


def read_request(addr: int, length: int) -> bytes:
    return _frame(T_READ, addr, length, b"")


def write_request(addr: int, data: bytes) -> bytes:
    return _frame(T_WRITE, addr, len(data), data)


def header_v(msg: bytes) -> int:
    """V = 8 + nº de bytes de dados, codificado nos bytes c e n do cabeçalho."""
    return (msg[4] >> 3 & 0xF) | (msg[5] << 4)


def has_data(msg: bytes) -> bool:
    # Não basta olhar c == 0x41: com 80 bytes de dados, V = 88 também dá c = 0x41 (n = 5).
    return len(msg) > 18 and msg[:3] == HEADER and msg[3] in (T_READ, T_WRITE) and header_v(msg) > 8


def parse_data(msg: bytes):
    """Decodifica uma mensagem com dados. Retorna (addr, dados) e valida o checksum."""
    if not has_data(msg) or msg[-1] != 0xF7:
        raise ValueError(f"mensagem inesperada: {msg[:20].hex(' ')}")
    addr, length = dec28(msg[9:13]), dec28(msg[13:17]) >> 4
    raw = unpack7(msg[17:-1])
    if len(raw) < length + 1:
        raise ValueError(f"mensagem truncada: {len(raw)} < {length + 1}")
    data, chk = raw[:length], raw[length]
    if chk != checksum(addr, length, data):
        raise ValueError(f"checksum inválido em addr={addr}")
    return addr, data


def parse_id(msg: bytes):
    """Extrai (modelo, versão) da resposta de identificação, ex. ("FootCtrlPlus", "013")."""
    if msg[:4] != HEADER + bytes([T_ID]) or len(msg) < 12:
        return None
    v = sum((b & 0x7F) << (7 * i) for i, b in enumerate(msg[4:-1]))
    for shift in range(8):
        raw = (v >> shift).to_bytes(len(msg) * 7 // 8 + 1, "little")
        m = re.search(rb"(FootCtrl[A-Za-z]*)_(\d+)", raw)
        if m:
            return m.group(1).decode(), m.group(2).decode()
    return None
