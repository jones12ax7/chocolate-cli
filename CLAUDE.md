# chocolate-cli

Ferramenta de linha de comando (Python, sem dependências) para gravar a configuração das
pedaleiras MIDI **M-VAVE Chocolate** ("FootCtrl") e **Chocolate Plus** ("FootCtrlPlus") a partir
de um arquivo TOML. As duas usam o mesmo USB (Jieli 4353:4b4d, "SINCO" no ALSA); o modelo é
detectado pela resposta de identificação SysEx. Substitui, para o uso do Jonathan, o app Windows
"Midi Suite" (que roda via Wine em `../MidiSuiteLinux/`, ver o CLAUDE.md de lá).

## Escopo (decidido pelo Jonathan em 2026-11-23)
Implementar **apenas** (Chocolate e, desde 2026-11-23, Chocolate Plus):
- modo **Advanced custom mode**; na Plus, também os 8 grupos, Max Group Count e Current Group;
- **Interface** (Expression Pedal / TRS-MIDI), a lista **Expression / TRS-MIDI codes**
  (External pedal) e, só na Plus, **Polarity reversal** (incluídos em 2026-11-23);
- working mode **"Short = Bank A / Long = Bank B"**;
- tipos de mensagem **PC** e **CC**.
Qualquer outro recurso: usar o Midi Suite via Wine ou uma máquina Windows. Não expandir o escopo.

Tela correspondente no app (v1.15.0, firmware v51): MODE → "Advanced custom mode";
FOOT SWITCH A/B/C/D; SELECT WORKING MODE → "Short = Bank A / Long = Bank B";
abas "A Bank" / "B Bank", cada uma com uma lista de mensagens (botão +), e cada mensagem com
CH, TYPE, DATA1, DATA2. Para PC, DATA2 não se aplica. Pedais E e F (combinações) entram no escopo
**se o protocolo permitir** (pedido em 2026-11-23). "Interface type" (Expression Pedal) fica fora.

Princípio de gravação: ler a config inteira do aparelho, alterar só os bytes do escopo e
gravar de volta, preservando tudo o que o app configurou fora do escopo.
Atualização de firmware está fora de questão (risco de inutilizar o aparelho).

## Decisões
- Formato de configuração: **TOML** (lido com `tomllib` da biblioteca padrão). YAML descartado pelo usuário.
- Acesso ao hardware: rawmidi direto (`/dev/snd/midiC<card>D0`, card com id `SINCO`), sem ALSA-seq.
  O Midi Suite precisa estar fechado (o rawmidi é exclusivo).

## Uso
    ./chocolate.py show                  # config atual em TOML (bom ponto de partida)
    ./chocolate.py write minha.toml -n   # prévia, não grava
    ./chocolate.py write minha.toml      # backup automático em backups/, grava, relê e confere
    ./chocolate.py backup [arq.bin]      # memória inteira (1858 bytes)
    ./chocolate.py restore arq.bin       # regrava modo + pedais A-D de um backup
Formato: `exemplo.toml` (Chocolate) e `exemplo-plus.toml` (Plus), ambos = estado original.
- Chocolate: seções [A]-[D]. Plus: [group1.A] ... [group8.D], mais `groups` (Max Group Count)
  e `current_group`, opcionais. `model = "chocolate"|"plus"` é opcional; se presente, tem de bater.
- Cada pedal: listas `short` (A Bank) e `long` (B Bank), até 16 itens `{ pc = N }` ou
  `{ cc = N, value = V }`, `ch` opcional (1).
- Seção `[interface]` (opcional; cada chave também): `type = "expression"|"trs-midi"`,
  `polarity_reversal = true|false` (só Plus), `codes = [ { cc, loose, step_on, ch? } ]` (até 16).
- Pedais/grupos ausentes do arquivo não são alterados. Ao gravar um pedal, o working mode dele
  vira Short/Long e o modo global vira Advanced custom mode.
- `restore` regrava os registros inteiros (inclusive working mode) do backup: é o jeito de
  voltar exatamente ao estado de fábrica (na Plus, 26 pedais vêm em Single step).

## Arquivos
- `README.md`: descrição pública em inglês (manter em sincronia com o uso/formato abaixo).
- Licença: GPL-3.0-or-later (`LICENSE`); cada `.py`/`.sh` tem cabeçalho SPDX + aviso de feito com IA
  e uso por conta e risco (em inglês). Arquivos novos devem levar o mesmo cabeçalho.
- `chocolate.py`: CLI. `protocol.py`: codificação SysEx (ver `PROTOCOLO.md`, que é a referência).
- `backups/original-antes-da-captura.bin` (Chocolate) e `backups/plus-original-antes-da-captura.bin`
  (Plus): memória como estava antes de qualquer teste (2026-11-23). `backups/` não é versionado
  (só existe no disco local); não apagar esses dois arquivos.
- `tools/`: análise de capturas (`sysex_log.py`, `state.py`, `diff_writes.py` — este usa a
  decodificação antiga, desalinhada em 2 bytes; preferir `state.py`).
- `capturar.sh` / `marca.sh` / `ROTEIRO-CAPTURA.md`: captura de tráfego do Midi Suite.

## Capturas
- `./capturar.sh [chocolate|plus]`: abre o Midi Suite via Wine gravando o tráfego em
  `captures/sessao-*.log` (`captures/atual.log` aponta para a sessão corrente).
- `./marca.sh "descrição"`: insere `### hh:mm:ss descrição` no log antes de cada ação no app.
- Formato do log: `hh:mm:ss <direção> tipo=130 src=... <bytes hex>` (gerado por `sinco-bridge.py`).
- Validação do codificador: `protocol.py` reproduz byte a byte as 31 mensagens distintas da
  captura de referência.

## Estado / pendências
- [x] Protocolo e mapa de memória (`PROTOCOLO.md`).
- [x] `chocolate.py` testado offline (ida e volta TOML <-> memória, validações).
- [x] Chocolate: show e write testados no aparelho (2026-11-23).
- [x] Plus: protocolo mapeado, show testado no aparelho.
- [x] Plus: write testado pelo Jonathan (2026-11-23).
- 2026-11-23: corrigido o offset do Bank B da Plus (86 → 81; ver PROTOCOLO.md). Gravações anteriores
  com o `chocolate.py` puseram o `long` uma posição adiante; o Jonathan refez no app e a memória
  foi conferida (nenhum resto a partir de 86).
- [ ] Interface/polarity/codes: implementado e testado offline; falta write real e conferir no app
  que, na Plus, as linhas da lista passam a ser numeradas a partir de 1.
- Pedais E/F: trocam de grupo; não são configuráveis no Advanced custom mode (fora do escopo).
