# chocolate-cli

Command-line tool to configure the **M-VAVE Chocolate** ("FootCtrl") and **Chocolate Plus**
("FootCtrlPlus") MIDI foot controllers on Linux from a TOML file, without the Windows-only
"Midi Suite" app.

- Pure Python 3.11+ (uses `tomllib`), no dependencies.
- Talks to the device over raw MIDI (`/dev/snd/midiC<card>D0`, the ALSA card with id `SINCO`).
- Both models share the same USB ID (Jieli `4353:4b4d`); the model is detected from the SysEx
  identification reply.
- The SysEx protocol and memory map were reverse-engineered from Midi Suite v1.15.0 traffic.
  See [`PROTOCOLO.md`](PROTOCOLO.md) (in Portuguese).

## Scope

Only a deliberate subset of the device's features is supported:

- **Advanced custom mode**, with the working mode **"Short = Bank A / Long = Bank B"**
  on foot switches A–D;
- message types **PC** and **CC** (up to 16 messages per bank);
- on the Plus: the 8 groups, *Max Group Count* and *Current Group*;
- the **Interface** setting (Expression Pedal / TRS-MIDI), the **Expression / TRS-MIDI codes**
  list and, on the Plus only, **Polarity reversal**.

Everything else (other modes, other message types, firmware updates) is out of scope; use
Midi Suite for those.

Writes are non-destructive: the tool reads the whole device memory, changes only the bytes it
manages and writes it back, so settings made with Midi Suite are preserved.

## Usage

Close Midi Suite first: raw MIDI access is exclusive. Your user needs access to `/dev/snd/*`
(usually the `audio` group).

```sh
./chocolate.py show                   # print the current config as TOML (a good starting point)
./chocolate.py write my.toml -n       # dry run: show what would change
./chocolate.py write my.toml          # back up to backups/, write, read back and verify
./chocolate.py backup [file.bin]      # dump the whole device memory
./chocolate.py restore file.bin       # rewrite mode + foot switch records from a backup
```

`restore` rewrites the full records (including each switch's working mode), so it is the way to
return exactly to a previous or factory state.

## Configuration file

Examples: [`exemplo.toml`](exemplo.toml) (Chocolate) and [`exemplo-plus.toml`](exemplo-plus.toml)
(Plus), both matching the factory state.

```toml
model = "chocolate"        # optional: "chocolate" | "plus"; must match the device if present

[interface]                # optional, as is each key in it
type = "expression"        # "expression" | "trs-midi"
codes = [                  # up to 16
  { cc = 64, loose = 0, step_on = 127 },
]

[A]
short = [ { cc = 69, value = 0 } ]   # Bank A (short press)
long  = [ { pc = 0 } ]               # Bank B (long press)
```

- Each message is `{ pc = N }` or `{ cc = N, value = V }`, with an optional `ch` (default 1).
- Chocolate: sections `[A]` … `[D]`.
- Plus: sections `[group1.A]` … `[group8.D]`, plus optional top-level `groups` (Max Group Count,
  1–8) and `current_group`; `[interface]` also accepts `polarity_reversal = true|false`.
- Switches and groups missing from the file are left untouched. Writing a switch sets its
  working mode to Short/Long and the global mode to Advanced custom mode.

## Repository layout

| Path | Contents |
|---|---|
| `chocolate.py` | the CLI |
| `protocol.py` | SysEx encoding/decoding |
| `PROTOCOLO.md` | protocol and memory map reference |
| `backups/` | memory dumps made by `write`/`backup` (local only, not versioned) |
| `tools/` | traffic-capture analysis scripts |
| `capturar.sh`, `marca.sh`, `ROTEIRO-CAPTURA.md` | capturing Midi Suite traffic under Wine (logs go to `captures/`, not versioned) |

## Made with AI

This software (code, protocol notes and documentation) was written with the help of AI
(Claude, by Anthropic), based on reverse engineering of the official app's MIDI traffic.
It has been tested on real hardware only in a limited way; review it before relying on it.

## Disclaimer

**Use at your own risk.** This is an unofficial project, not affiliated with or endorsed by
M-VAVE. It writes directly to the device's memory, and a wrong write could leave the device
misconfigured or unusable. It was tested only on Chocolate firmware 051 and Chocolate Plus
firmware 013. Keep the automatic backups. The authors accept no liability for any damage
or data loss.

## License

Copyright (C) 2026 The chocolate-cli authors.

This program is free software: you can redistribute it and/or modify it under the terms of
the GNU General Public License as published by the Free Software Foundation, either version 3
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but **WITHOUT ANY WARRANTY**;
without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
See [`LICENSE`](LICENSE) for the full text.
