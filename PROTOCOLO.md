# Protocolo SysEx da M-VAVE Chocolate (FootCtrl) e Chocolate Plus (FootCtrlPlus)

Obtido por engenharia reversa em 2026-11-23, capturando o tráfego do Midi Suite v1.15.0 com
`sinco-bridge.py`. Capturas de referência: Chocolate firmware 051
`captures/sessao-20261123-153704.log`; Plus firmware 013 `captures/sessao-20261123-185732.log`.
Implementação: `protocol.py` (reproduz byte a byte todas as mensagens das duas capturas).

## Mensagem

    F0 00 32 | tipo | c | n 00 00 02 | addr(4) | len<<4 (4) | payload | F7

| Campo | Valores |
|---|---|
| tipo | `0D` pedido de leitura e resposta; `09` gravação; `01` confirmação |
| c, n | `V = 8 + nº de bytes de dados na mensagem`; `c = 0x01 \| (V & 0xF) << 3`, `n = V >> 4`. Pedido de leitura: `41 00` |
| addr, len<<4 | inteiros em 7 bits little-endian, 4 bytes cada |
| payload | dados + 1 byte de checksum, compactados como fluxo contínuo de 7 bits, LSB primeiro |

    checksum = (0xFB - soma(addr como 4 bytes LE) - soma(len como 4 bytes LE) - soma(dados)) & 0xFF

Confirmação de gravação: `F0 00 32 01 08 00 00 00 00 7F 01 F7`.
Identificação: pedido `F0 00 32 45 00 00 00 40 7F F7`. A resposta traz, num fluxo de 7 bits,
o texto `FootCtrl_051` / `FootCtrlPlus_013` (modelo_firmware). As duas usam o mesmo USB
(Jieli 4353:4b4d, "SINCO"), então a identificação é a única forma de distinguir.

O app lê a memória em blocos de até 1009 bytes, repetindo a leitura a cada ~1 s enquanto está
aberto, e grava 1 byte (ajustes) ou um registro de pedal inteiro por vez.

## Chocolate: memória (1858 bytes, blocos de 1009 + 849)

| Endereço | Conteúdo |
|---|---|
| 0 | modo global: `9` = Advanced custom mode (outros valores = outros modos, não mapeados) |
| 1-11 | desconhecido (zeros) |
| 12 | Interface: `0` = Expression Pedal, `1` = TRS-MIDI |
| 13 + 161·n | registro do pedal n: A=0, B=1, C=2, D=3 |
| 657 | lista "External pedal parameters": byte 657 desconhecido; 16 linhas de 5 bytes a partir de 658 |
| 818 | 6º registro: vazio |

Linha da lista do pedal externo: `[ativa, CH-1, CC#, LOOSE, STEP ON]` (LOOSE = valor com o pedal
solto, STEP ON = pisado). Máximo 16 linhas; lista compacta. O app grava o registro 657 inteiro
(161 bytes). A Chocolate não tem "Polarity reversal".

### Registro de pedal (161 bytes)

| Offset | Conteúdo |
|---|---|
| 0 | working mode: `4` = Short = Bank A / Long = Bank B; `0` = Single step (single bank) |
| 1-80 | A Bank (short): 16 posições de 5 bytes |
| 81-160 | B Bank (long): 16 posições de 5 bytes |

Posição (5 bytes): `[ativa (1/0), CH-1, tipo, DATA1, DATA2]`. Tipo: `0` = PC, `1` = CC
(outros tipos existem no app, fora do escopo). A lista é compacta: ao apagar uma mensagem o
app sobe as seguintes e zera a última posição.

Os pedais E e F ("grupos") não aparecem na tela do Advanced custom mode e não foram localizados.

## Chocolate Plus: memória (23646 bytes, 23 blocos de 1009 + 439)

| Endereço | Conteúdo |
|---|---|
| 0 | modo global: `3` = Advanced Custom Mode (`2` = Custom Mode) |
| 1 | Interface: `0` = Expression Pedal, `1` = TRS-MIDI |
| 2-12 | desconhecido (preservar) |
| 13-92 | lista "Expression / TRS-MIDI codes": 16 linhas de 5 bytes, mesmo formato da Chocolate. O app grava os 80 bytes juntos |
| 93 + 417·(4·(g-1) + p) | registro do grupo g (1-8), pedal p (A=0..D=3) |
| 13437-23636 | desconhecido (outros modos; preservar) |
| 23639 | Max Group Count − 1 |
| 23640 | Current Group − 1 |
| 23642 | Polarity reversal: `0` = desligado, `1` = ligado |

Na Plus, a 1ª linha da lista de códigos vinha com `04 01 00 01 45` (resto de firmware antigo,
igual ao início de um registro de pedal da Chocolate). O app não a exibe (só mostra `ativa = 1`)
e numera as linhas a partir de 2. A ferramenta, ao gravar a lista, usa as 16 posições e limpa esse
resto.

Atenção ao cabeçalho: gravar 80 bytes dá `V = 88`, ou seja, `c = 0x41`, igual ao de um pedido de
leitura (que tem `n = 0`). Diferenciar sempre pelo V completo.

### Registro de pedal (417 bytes)

| Offset | Conteúdo |
|---|---|
| 0 | working mode: `4` = Short = Bank A / Long = Bank B; `0` = Single step |
| 1-80 | Bank A: 16 posições de 5 bytes (o app limita a 16 mensagens) |
| 81-160 | Bank B: 16 posições de 5 bytes (igual à Chocolate) |
| 161-416 | desconhecido (preservar) |

**Armadilha (erro corrigido em 2026-11-23):** a 1ª posição do Bank B do grupo 1 vinha com o lixo
`04 01 00 01 45`. O app não exibe posições com `ativa` ≠ 1, mas também não as reaproveita, então
a "linha 1" do Bank B na tela era a 2ª posição (offset 86). Isso levou a mapear o Bank B em 86 por
engano; o Jonathan notou que o `show` não batia com o app. Mesmo fenômeno da lista de códigos.
Ao gravar um banco, a ferramenta reescreve as 16 posições e limpa esse lixo.

Mesmo formato de posição da Chocolate. De fábrica, 26 dos 32 pedais vêm em Single step.
E/F (A+B, C+D) trocam de grupo no aparelho e não são configuráveis no Advanced Custom Mode.
