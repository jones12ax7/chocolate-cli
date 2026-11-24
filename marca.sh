#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 The chocolate-cli authors
# This file was written with the help of AI (Claude, by Anthropic). It is provided AS IS,
# WITHOUT ANY WARRANTY; use it at your own risk. See LICENSE and README.md.
# Insere um marcador na captura em andamento: ./marca.sh "botão A curto: PC 5 -> PC 6"
LOG="$(dirname "$0")/captures/atual.log"
[ -e "$LOG" ] || { echo "Nenhuma captura em andamento (rode ./capturar.sh)." >&2; exit 1; }
echo "### $(date +%H:%M:%S) $*" >> "$LOG" && echo "Marcado: $*"
