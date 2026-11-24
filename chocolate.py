#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The chocolate-cli authors
# This file was written with the help of AI (Claude, by Anthropic). It is provided AS IS,
# WITHOUT ANY WARRANTY; use it at your own risk. See LICENSE and README.md.
"""Configura as pedaleiras M-VAVE Chocolate (FootCtrl) e Chocolate Plus (FootCtrlPlus)
a partir de um arquivo TOML.

Escopo: modo "Advanced custom mode", working mode "Short = Bank A / Long = Bank B",
mensagens PC e CC nos pedais A-D (na Plus, em até 8 grupos). Para o resto, use o Midi Suite.

Comandos:
  chocolate.py show                 mostra a configuração atual no formato TOML
  chocolate.py write ARQ.toml       grava a configuração (faz backup antes)
  chocolate.py write ARQ.toml -n    só mostra o que mudaria, sem gravar
  chocolate.py backup [ARQ.bin]     salva a memória inteira da pedaleira
  chocolate.py restore ARQ.bin      regrava, a partir de um backup, só a parte do escopo

O modelo é detectado automaticamente. O Midi Suite precisa estar fechado.
"""
import argparse
import os
import re
import select
import sys
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path

import protocol as P

HERE = Path(__file__).resolve().parent
BACKUP_DIR = HERE / "backups"

PEDALS = "ABCD"
WM_SHORT_A_LONG_B = 4
SLOTS, SLOT_LEN = 16, 5                     # [ativa, ch-1, tipo, data1, data2]
TYPE_PC, TYPE_CC = 0, 1


class Erro(Exception):
    pass


@dataclass(frozen=True)
class Model:
    key: str                # nome usado no TOML e nos backups
    id_name: str            # nome na resposta de identificação
    title: str
    mem_size: int
    mode_advanced: int      # valor do byte 0 (modo global) para Advanced custom mode
    rec0: int               # endereço do registro do grupo 1, pedal A
    rec_len: int
    bank_long: int          # offset do B Bank dentro do registro (A Bank fica em 1)
    groups: int             # nº máximo de grupos
    interface_addr: int     # 0 = Expression Pedal, 1 = TRS-MIDI
    codes_addr: int         # 1ª posição da lista "Expression / TRS-MIDI codes" (16 × 5 bytes)
    codes_region: tuple     # (addr, len) que o app grava ao mudar a lista
    group_count_addr: int | None = None   # Max Group Count (guardado como n-1)
    current_group_addr: int | None = None # Current Group (guardado a partir de 0)
    polarity_addr: int | None = None      # Polarity reversal (só na Plus)

    def blocks(self):
        return [(a, min(P.MAX_CHUNK, self.mem_size - a)) for a in range(0, self.mem_size, P.MAX_CHUNK)]

    def rec_addr(self, group, pedal):      # group a partir de 1, pedal 0-3
        return self.rec0 + self.rec_len * (4 * (group - 1) + pedal)

    def banks(self):
        return {"short": 1, "long": self.bank_long}


CHOCOLATE = Model("chocolate", "FootCtrl", "M-VAVE Chocolate (FootCtrl)", 1858,
                  mode_advanced=9, rec0=13, rec_len=161, bank_long=81, groups=1,
                  interface_addr=12, codes_addr=658, codes_region=(657, 161))
PLUS = Model("plus", "FootCtrlPlus", "M-VAVE Chocolate Plus (FootCtrlPlus)", 23646,
             mode_advanced=3, rec0=93, rec_len=417, bank_long=81, groups=8,
             interface_addr=1, codes_addr=13, codes_region=(13, 80),
             group_count_addr=23639, current_group_addr=23640, polarity_addr=23642)
INTERFACES = {"expression": 0, "trs-midi": 1}
MODELS = {m.id_name: m for m in (CHOCOLATE, PLUS)}
MODE_ADDR = 0


# ---------------------------------------------------------------- dispositivo

def find_device():
    try:
        cards = Path("/proc/asound/cards").read_text()
    except OSError as e:
        raise Erro(f"não consegui ler /proc/asound/cards: {e}")
    found = re.findall(r"^\s*(\d+)\s+\[SINCO\s*\]", cards, re.M)
    if not found:
        raise Erro("pedaleira não encontrada (placa ALSA 'SINCO'). Ela está ligada no USB?")
    if len(found) > 1:
        raise Erro("há mais de uma pedaleira M-VAVE ligada; deixe só uma no USB")
    dev = f"/dev/snd/midiC{found[0]}D0"
    if not os.path.exists(dev):
        raise Erro(f"{dev} não existe")
    return dev


class Pedal:
    def __init__(self, path):
        try:
            self.fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        except OSError as e:
            if e.errno == 16:
                raise Erro(f"{path} está em uso. Feche o Midi Suite e tente de novo.")
            raise Erro(f"não consegui abrir {path}: {e}")
        self.buf = bytearray()
        self.model, self.version = self.identify()

    def close(self):
        os.close(self.fd)

    def send(self, msg):
        view = memoryview(msg)
        while view:
            select.select([], [self.fd], [], 1)
            n = os.write(self.fd, view)
            view = view[n:]

    def recv_sysex(self, timeout=3.0):
        """Devolve a próxima mensagem SysEx completa (ignora o resto do tráfego MIDI)."""
        deadline = time.monotonic() + timeout
        while True:
            start = self.buf.find(0xF0)
            if start >= 0:
                end = self.buf.find(0xF7, start)
                if end >= 0:
                    msg = bytes(self.buf[start:end + 1])
                    del self.buf[:end + 1]
                    return msg
            left = deadline - time.monotonic()
            if left <= 0:
                raise Erro("a pedaleira não respondeu a tempo")
            r, _, _ = select.select([self.fd], [], [], left)
            if r:
                self.buf += os.read(self.fd, 4096)

    def identify(self):
        self.buf.clear()
        self.send(P.ID_REQUEST)
        for _ in range(8):
            ident = P.parse_id(self.recv_sysex())
            if ident:
                name, version = ident
                if name not in MODELS:
                    raise Erro(f"modelo não suportado: {name}_{version}")
                return MODELS[name], version
        raise Erro("a pedaleira não se identificou")

    def read_mem(self, addr, length):
        self.buf.clear()
        self.send(P.read_request(addr, length))
        for _ in range(8):
            msg = self.recv_sysex()
            if P.has_data(msg):
                a, data = P.parse_data(msg)
                if a == addr and len(data) == length:
                    return data
        raise Erro(f"resposta inesperada à leitura de {addr}")

    def read_all(self):
        mem = bytearray()
        for addr, length in self.model.blocks():
            mem += self.read_mem(addr, length)
        return mem

    def write_mem(self, addr, data):
        self.buf.clear()
        self.send(P.write_request(addr, bytes(data)))
        for _ in range(8):
            if self.recv_sysex() == P.ACK:
                return
        raise Erro(f"a pedaleira não confirmou a gravação em {addr}")


def open_pedal():
    dev = Pedal(find_device())
    print(f"# {dev.model.title}, firmware {dev.version}", file=sys.stderr)
    return dev


# ---------------------------------------------------------- memória <-> dados

def decode_bank(rec, off):
    msgs = []
    for s in range(SLOTS):
        on, ch, typ, d1, d2 = rec[off + s * SLOT_LEN: off + (s + 1) * SLOT_LEN]
        if not on:
            break
        if on == 1:            # como o app: ignora posição com lixo (ex.: ativa = 4 na Plus)
            msgs.append((ch + 1, typ, d1, d2))
    return msgs


def encode_bank(rec, off, msgs):
    for s in range(SLOTS):
        i = off + s * SLOT_LEN
        rec[i:i + SLOT_LEN] = bytes([1, msgs[s][0] - 1, *msgs[s][1:]]) if s < len(msgs) else bytes(SLOT_LEN)


def fmt_msg(ch, typ, d1, d2):
    ch_s = "" if ch == 1 else f", ch = {ch}"
    if typ == TYPE_PC:
        return f"{{ pc = {d1}{ch_s} }}"
    if typ == TYPE_CC:
        return f"{{ cc = {d1}, value = {d2}{ch_s} }}"
    return f"# tipo {typ} fora do escopo (ch={ch} data1={d1} data2={d2})"


def pedal_toml(model, mem, group, p, header):
    a = model.rec_addr(group, p)
    rec = mem[a:a + model.rec_len]
    out = [f"[{header}]"]
    if rec[0] != WM_SHORT_A_LONG_B:
        out.append(f"# ATENÇÃO: working mode atual = {rec[0]} (não é Short = Bank A / Long = Bank B)")
    for bank, off in model.banks().items():
        msgs = decode_bank(rec, off)
        if msgs:
            out += [f"{bank} = ["] + [f"  {fmt_msg(*m)}," for m in msgs] + ["]"]
        else:
            out.append(f"{bank} = []")
    return out + [""]


def decode_codes(model, mem):
    """Linhas ativas da lista Expression / TRS-MIDI: (ch, cc, loose, step_on)."""
    out = []
    for s in range(SLOTS):
        on, ch, cc, loose, step = mem[model.codes_addr + s * SLOT_LEN: model.codes_addr + (s + 1) * SLOT_LEN]
        if on == 1:            # na Plus, a posição 1 pode ter lixo de firmware antigo (on = 4)
            out.append((ch + 1, cc, loose, step))
        elif on == 0:
            break
    return out


def encode_codes(model, mem, codes):
    for s in range(SLOTS):
        i = model.codes_addr + s * SLOT_LEN
        mem[i:i + SLOT_LEN] = bytes([1, codes[s][0] - 1, *codes[s][1:]]) if s < len(codes) else bytes(SLOT_LEN)


def interface_toml(model, mem):
    names = {v: k for k, v in INTERFACES.items()}
    it = mem[model.interface_addr]
    out = ["[interface]",
           f'type = "{names.get(it, it)}"' + ("" if it in names else "   # valor desconhecido")
           + '        # "expression" (Expression Pedal) ou "trs-midi" (TRS-MIDI)']
    if model.polarity_addr is not None:
        out.append(f"polarity_reversal = {'true' if mem[model.polarity_addr] else 'false'}")
    codes = decode_codes(model, mem)
    if codes:
        out.append("codes = [                  # Expression / TRS-MIDI codes (até 16)")
        for ch, cc, loose, step in codes:
            ch_s = "" if ch == 1 else f", ch = {ch}"
            out.append(f"  {{ cc = {cc}, loose = {loose}, step_on = {step}{ch_s} }},")
        out.append("]")
    else:
        out.append("codes = []                 # Expression / TRS-MIDI codes (até 16)")
    return out + [""]


def to_toml(model, mem):
    out = [f"# {model.title}: Advanced custom mode, Short = Bank A / Long = Bank B",
           "# Mensagens: { pc = N } ou { cc = N, value = V }; ch é opcional (padrão 1).",
           f'model = "{model.key}"', ""]
    if mem[MODE_ADDR] != model.mode_advanced:
        out.append(f"# ATENÇÃO: a pedaleira não está em Advanced custom mode (modo={mem[MODE_ADDR]}).\n")
    if model.groups == 1:
        out += interface_toml(model, mem)
        for p, name in enumerate(PEDALS):
            out += pedal_toml(model, mem, 1, p, name)
        return "\n".join(out)
    n = mem[model.group_count_addr] + 1
    out[3:3] = [f"groups = {n}                 # Max Group Count (1-{model.groups})",
                f"current_group = {mem[model.current_group_addr] + 1}          # grupo ativo"]
    out += interface_toml(model, mem)
    for g in range(1, model.groups + 1):
        if g > n:
            out.append(f"# grupo {g}: inativo (acima de groups = {n})")
        for p, name in enumerate(PEDALS):
            out += pedal_toml(model, mem, g, p, f"group{g}.{name}")
    return "\n".join(out)


def parse_msg(item, where):
    if not isinstance(item, dict):
        raise Erro(f"{where}: cada mensagem deve ser uma tabela, ex.: {{ pc = 5 }}")
    keys = set(item)
    extra = keys - {"pc", "cc", "value", "ch"}
    if extra:
        raise Erro(f"{where}: chave(s) desconhecida(s): {', '.join(sorted(extra))}")

    def num(k, lo, hi, default=None):
        v = item.get(k, default)
        if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
            raise Erro(f"{where}: '{k}' deve ser um inteiro de {lo} a {hi}")
        return v

    ch = num("ch", 1, 16, 1)
    if ("pc" in keys) == ("cc" in keys):
        raise Erro(f"{where}: use exatamente uma de 'pc' ou 'cc'")
    if "pc" in keys:
        if "value" in keys:
            raise Erro(f"{where}: PC não tem 'value'")
        return (ch, TYPE_PC, num("pc", 0, 127), 0)
    return (ch, TYPE_CC, num("cc", 0, 127), num("value", 0, 127))


def parse_pedal(sec, where):
    if not isinstance(sec, dict) or set(sec) - {"short", "long"}:
        raise Erro(f"[{where}]: use apenas as chaves 'short' e 'long'")
    banks = {}
    for bank in ("short", "long"):
        items = sec.get(bank, [])
        if not isinstance(items, list):
            raise Erro(f"[{where}].{bank}: deve ser uma lista, ex.: [ {{ pc = 1 }} ]")
        if len(items) > SLOTS:
            raise Erro(f"[{where}].{bank}: no máximo {SLOTS} mensagens")
        banks[bank] = [parse_msg(it, f"[{where}].{bank}[{k + 1}]") for k, it in enumerate(items)]
    return banks


def parse_code(item, where):
    if not isinstance(item, dict):
        raise Erro(f"{where}: cada linha deve ser uma tabela, ex.: {{ cc = 7, loose = 0, step_on = 127 }}")
    extra = set(item) - {"cc", "loose", "step_on", "ch"}
    if extra:
        raise Erro(f"{where}: chave(s) desconhecida(s): {', '.join(sorted(extra))}")
    vals = []
    for k, lo, hi, default in (("ch", 1, 16, 1), ("cc", 0, 127, None),
                               ("loose", 0, 127, None), ("step_on", 0, 127, None)):
        v = item.get(k, default)
        if not isinstance(v, int) or isinstance(v, bool) or not lo <= v <= hi:
            raise Erro(f"{where}: '{k}' é obrigatório e deve ser um inteiro de {lo} a {hi}"
                       if default is None else f"{where}: '{k}' deve ser um inteiro de {lo} a {hi}")
        vals.append(v)
    return tuple(vals)


def parse_interface(sec, model):
    if not isinstance(sec, dict):
        raise Erro("[interface]: deve ser uma seção")
    allowed = {"type", "codes"} | ({"polarity_reversal"} if model.polarity_addr is not None else set())
    extra = set(sec) - allowed
    if extra:
        hint = " (polarity_reversal só existe na Chocolate Plus)" if "polarity_reversal" in extra else ""
        raise Erro(f"[interface]: chave(s) desconhecida(s): {', '.join(sorted(extra))}{hint}")
    out = {}
    if "type" in sec:
        if sec["type"] not in INTERFACES:
            raise Erro(f'[interface].type: use "expression" ou "trs-midi"')
        out["type"] = INTERFACES[sec["type"]]
    if "polarity_reversal" in sec:
        if not isinstance(sec["polarity_reversal"], bool):
            raise Erro("[interface].polarity_reversal: use true ou false")
        out["polarity"] = int(sec["polarity_reversal"])
    if "codes" in sec:
        codes = sec["codes"]
        if not isinstance(codes, list):
            raise Erro("[interface].codes: deve ser uma lista")
        if len(codes) > SLOTS:
            raise Erro(f"[interface].codes: no máximo {SLOTS} linhas")
        out["codes"] = [parse_code(c, f"[interface].codes[{k + 1}]") for k, c in enumerate(codes)]
    return out


def load_config(path, model):
    """Valida o TOML para o modelo e devolve {"pedals": {(grupo, p): bancos}, "groups", "current",
    "interface"}."""
    try:
        cfg = tomllib.loads(Path(path).read_text())
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise Erro(f"{path}: {e}")
    file_model = cfg.pop("model", None)
    if file_model is not None and file_model != model.key:
        raise Erro(f"{path} é para o modelo '{file_model}', mas a pedaleira ligada é '{model.key}'")
    out = {"pedals": {}, "groups": cfg.pop("groups", None), "current": cfg.pop("current_group", None),
           "interface": parse_interface(cfg.pop("interface"), model) if "interface" in cfg else {}}
    if model.groups == 1:
        if out["groups"] is not None or out["current"] is not None:
            raise Erro(f"{path}: 'groups' e 'current_group' só existem na Chocolate Plus")
        if any(k.startswith("group") for k in cfg):
            raise Erro(f"{path}: a Chocolate não tem grupos; use seções [A] a [D]")
        extra = set(cfg) - set(PEDALS)
        if extra:
            raise Erro(f"{path}: seções desconhecidas: {', '.join(sorted(extra))} (use A, B, C, D)")
        for name, sec in cfg.items():
            out["pedals"][(1, PEDALS.index(name))] = parse_pedal(sec, name)
        return out
    if set(cfg) & set(PEDALS):
        raise Erro(f"{path}: na Chocolate Plus use seções [group1.A], [group2.B] etc.")
    for key, sec in cfg.items():
        m = re.fullmatch(r"group([1-9])", key)
        if not m or not 1 <= int(m.group(1)) <= model.groups:
            raise Erro(f"{path}: seção desconhecida [{key}] (use group1 a group{model.groups})")
        g = int(m.group(1))
        if not isinstance(sec, dict) or set(sec) - set(PEDALS):
            raise Erro(f"[{key}]: use subseções [{key}.A] a [{key}.D]")
        for name, psec in sec.items():
            out["pedals"][(g, PEDALS.index(name))] = parse_pedal(psec, f"{key}.{name}")
    for k, v in (("groups", out["groups"]), ("current_group", out["current"])):
        if v is not None and (not isinstance(v, int) or isinstance(v, bool) or not 1 <= v <= model.groups):
            raise Erro(f"{path}: '{k}' deve ser um inteiro de 1 a {model.groups}")
    return out


def apply_config(model, mem, cfg):
    new = bytearray(mem)
    new[MODE_ADDR] = model.mode_advanced
    for (g, p), banks in cfg["pedals"].items():
        a = model.rec_addr(g, p)
        rec = new[a:a + model.rec_len]
        rec[0] = WM_SHORT_A_LONG_B
        for bank, off in model.banks().items():
            encode_bank(rec, off, banks[bank])
        new[a:a + model.rec_len] = rec
    itf = cfg["interface"]
    if "type" in itf:
        new[model.interface_addr] = itf["type"]
    if "polarity" in itf:
        new[model.polarity_addr] = itf["polarity"]
    if "codes" in itf:
        encode_codes(model, new, itf["codes"])
    if cfg["groups"] is not None:
        new[model.group_count_addr] = cfg["groups"] - 1
    if cfg["current"] is not None:
        new[model.current_group_addr] = cfg["current"] - 1
    if model.groups > 1:
        n, cur = new[model.group_count_addr] + 1, new[model.current_group_addr] + 1
        if cur > n:
            raise Erro(f"current_group = {cur} é maior que groups = {n}")
        unused = sorted({g for g, _ in cfg["pedals"]} - set(range(1, n + 1)))
        if unused:
            print(f"Aviso: grupo(s) {', '.join(map(str, unused))} acima de groups = {n}; "
                  f"serão gravados, mas a pedaleira não os usa.", file=sys.stderr)
    return new


def single_bytes(model):
    out = [MODE_ADDR, model.interface_addr]
    if model.groups > 1:
        out += [model.group_count_addr, model.current_group_addr]
    if model.polarity_addr is not None:
        out.append(model.polarity_addr)
    return out


def records(model):
    return [(g, p) for g in range(1, model.groups + 1) for p in range(len(PEDALS))]


def regions(model):
    """Áreas que o app grava inteiras: lista de códigos do pedal e registros dos pedais."""
    return [model.codes_region] + [(model.rec_addr(g, p), model.rec_len) for g, p in records(model)]


def plan_writes(model, old, new):
    """Lista (addr, dados) das gravações necessárias, na granularidade usada pelo app."""
    writes = [(a, new[a:a + 1]) for a in single_bytes(model) if old[a] != new[a]]
    for a, n in regions(model):
        if old[a:a + n] != new[a:a + n]:
            writes.append((a, new[a:a + n]))
    return writes


def describe(model, addr):
    names = {MODE_ADDR: "modo global -> Advanced custom mode",
             model.interface_addr: "Interface", model.polarity_addr: "Polarity reversal",
             model.codes_region[0]: "Expression / TRS-MIDI codes",
             model.group_count_addr: "Max Group Count", model.current_group_addr: "Current Group"}
    if addr in names:
        return names[addr]
    g, p = divmod((addr - model.rec0) // model.rec_len, 4)
    return f"grupo {g + 1}, pedal {PEDALS[p]}" if model.groups > 1 else f"pedal {PEDALS[p]}"


def save_backup(model, mem, path=None):
    if path is None:
        BACKUP_DIR.mkdir(exist_ok=True)
        path = BACKUP_DIR / f"{model.key}-{time.strftime('%Y%m%d-%H%M%S')}.bin"
    Path(path).write_bytes(bytes(mem))
    return path


def do_writes(dev, old, new):
    model = dev.model
    writes = plan_writes(model, old, new)
    if not writes:
        print("Nada a gravar: a pedaleira já está com essa configuração.")
        return
    bk = save_backup(model, old)
    print(f"Backup da configuração anterior: {bk}")
    for addr, data in writes:
        print(f"Gravando {describe(model, addr)}...")
        dev.write_mem(addr, data)
    if dev.read_all() != new:
        raise Erro(f"a releitura não confere com o que foi gravado. Restaure com: "
                   f"{Path(sys.argv[0]).name} restore {bk}")
    print("Gravado e conferido.")


# ------------------------------------------------------------------- comandos

def cmd_show(args):
    dev = open_pedal()
    try:
        print(to_toml(dev.model, dev.read_all()))
    finally:
        dev.close()


def cmd_backup(args):
    dev = open_pedal()
    try:
        print(f"Backup salvo em {save_backup(dev.model, dev.read_all(), args.arquivo)}")
    finally:
        dev.close()


def cmd_write(args):
    dev = open_pedal()
    try:
        model = dev.model
        cfg = load_config(args.arquivo, model)
        old = dev.read_all()
        new = apply_config(model, old, cfg)
        if args.dry_run:
            for addr, _ in plan_writes(model, old, new):
                print(f"Gravaria: {describe(model, addr)}")
            print("Prévia da configuração resultante:\n")
            print(to_toml(model, new))
            return
        do_writes(dev, old, new)
    finally:
        dev.close()


def cmd_restore(args):
    backup = Path(args.arquivo).read_bytes()
    dev = open_pedal()
    try:
        model = dev.model
        if len(backup) != model.mem_size:
            raise Erro(f"{args.arquivo} tem {len(backup)} bytes; não é um backup de {model.title}")
        old = dev.read_all()
        new = bytearray(old)
        for a in single_bytes(model):
            new[a] = backup[a]
        for a, n in regions(model):
            new[a:a + n] = backup[a:a + n]
        do_writes(dev, old, new)
    finally:
        dev.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("show", help="mostra a configuração atual em TOML").set_defaults(fn=cmd_show)
    p = sub.add_parser("write", help="grava a configuração de um arquivo TOML")
    p.add_argument("arquivo")
    p.add_argument("-n", "--dry-run", action="store_true", help="só mostra o que mudaria")
    p.set_defaults(fn=cmd_write)
    p = sub.add_parser("backup", help="salva a memória inteira da pedaleira")
    p.add_argument("arquivo", nargs="?")
    p.set_defaults(fn=cmd_backup)
    p = sub.add_parser("restore", help="regrava a parte do escopo a partir de um backup")
    p.add_argument("arquivo")
    p.set_defaults(fn=cmd_restore)
    args = ap.parse_args()
    try:
        args.fn(args)
    except Erro as e:
        sys.exit(f"Erro: {e}")


if __name__ == "__main__":
    main()
