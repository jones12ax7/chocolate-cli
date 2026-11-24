#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The chocolate-cli authors
# This file was written with the help of AI (Claude, by Anthropic). It is provided AS IS,
# WITHOUT ANY WARRANTY; use it at your own risk. See LICENSE and README.md.
# Abre o Midi Suite (Wine) registrando todo o tráfego MIDI numa nova sessão em captures/.
# Use ./marca.sh "descrição" (em outro terminal) antes de cada ação no app.
cd "$(dirname "$0")" || exit 1
LOG="$PWD/captures/sessao-$(date +%Y%m%d-%H%M%S).log"
ln -sf "$LOG" captures/atual.log
echo "Gravando em $LOG"
BRIDGE_LOG="$LOG" exec "../MidiSuiteLinux/midi-suite.sh" "${1:-chocolate}"
