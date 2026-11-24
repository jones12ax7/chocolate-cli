# Roteiro de captura

Objetivo: descobrir como o app lê e grava cada campo. Regra: **uma mudança por vez**, sempre
com um marcador antes. Os marcadores são inseridos pelo Claude Code com:

    ! /home/jones/Drive/Personal/10_Musica/M-VAVE/chocolate-cli/marca.sh "texto"

Se o app tiver botão de salvar/enviar, use-o depois de cada mudança e marque também.
Anote os valores originais; no fim, volte tudo ao que era (ou restauramos pela captura 1).

| # | Marcador | Ação no app |
|---|----------|-------------|
| 1 | `leitura` | Clicar em FootCtrl e esperar carregar (esta captura também é o backup) |
| 2 | `A bankA msg1 data1 69->70` | Pedal A, A Bank, mensagem 1: DATA1 de 69 para 70 |
| 3 | `A bankA msg1 data2 0->1` | DATA2 de 0 para 1 |
| 4 | `A bankA msg1 ch 1->2` | CH de 1 para 2 |
| 5 | `A bankA msg1 type CC->PC` | TYPE de CC para PC |
| 6 | `A bankA add msg2` | Botão +, adicionar uma 2ª mensagem (anote os valores que vierem) |
| 7 | `A bankA del msg2` | Apagar a 2ª mensagem (X) |
| 8 | `A bankB msg1 data1 X->Y` | Aba B Bank, mensagem 1: mudar DATA1 (anote de/para) |
| 9 | `B bankA msg1 data1 X->Y` | Pedal B, A Bank: mudar DATA1 |
| 10 | `C bankA msg1 data1 X->Y` | Pedal C, A Bank: mudar DATA1 |
| 10b | `E bankA msg1 data1 X->Y` | Pedal E (se aparecer na tela), A Bank: mudar DATA1 |
| 10c | `F bankA msg1 data1 X->Y` | Pedal F (se aparecer na tela), A Bank: mudar DATA1 |
| 11 | `A modo outro` | Pedal A: trocar o working mode para qualquer outro |
| 12 | `A modo short/long` | Voltar para "Short = Bank A / Long = Bank B" |
| 13 | `modo outro` | Na coluna MODE, clicar em outro modo (ex.: Custom control) |
| 14 | `modo advanced` | Voltar para "Advanced custom mode" |
| 15 | `restaurar` | Desfazer as mudanças de teste restantes |
| 16 | `fim` | Fechar o app |
