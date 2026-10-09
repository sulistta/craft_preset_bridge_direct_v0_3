# ADR 040 — OLM anisotrópico e entradas comprovadamente inativas

Status: implementado em 0.35.0; sem certificação visual.

## Evidência

Um snapshot privado comprova 14 controles, incluindo Angle=106 graus,
Front=140, menu Smooth/Block/Layer e Noise Layer kind 0 opaco. Manual oficial
EN do ZIP OLM (hash/URL em [olmdirectional-extension.md](../olmdirectional-extension.md))
foi extraído/lido e páginas 5–8 renderizadas/conferidas. Sem código-fonte no
pacote; nenhum plugin compilado executado ou distribuído. Documentação
licenciada Apache 2.0 consultada, renderer MIT original independente.

O manual torna a entrada Layer condicional ao menu. Obrigar substituição
manual em Smooth ou inferir None para qualquer configuração seriam decisões
sem correspondência com essa evidência. Sliders kind 2 permanecem brutos:
percentuais da UI não comprovam a escala do FFX. Alpha Fade legado difere
do nome Edge Fade no texto; fidelidade permanece perda.

## Decisão

Acrescentar `Rule.inactive_when` exclusivamente a vínculos Layer explícitos.
Valores inteiros distintos devem pertencer a um Choice comprovado no mapa,
obrigatório na criação, com enum_map/minus_one e faixa válida. Null de
transporte só é emitido diante de seletor único estático tipado sem perdas,
chaves declaradas ou expressão. Recurso original presente/estático e seus
avisos continuam exigidos; um binding manual tem precedência. Não modifica
IR, não decodifica vínculo e mantém perda `SOURCE_LAYER_INACTIVE`.

API 2/revisão 1 original transporta Layer/Source e 14 controles. Kernel de
máximo alpha preserva detalhe opaco, amostra dois raios independentes e
ignora RGB transparente. Grupos 8-conectados modulam comprimento e taper;
ruído próprio Smooth/Block e luma de Layer modulam comprimento. Modelo
limitado a 64 samples/lado e 2097152 pixels/imagem; canvas fixo. Fades,
calibração, normalização /100 e unidades internas são explicitamente próprias.
Não aplicar filtro linear comum que dilui cor/transparência para rotular OLM.

## Consequências

O snapshot Smooth pode ser convertido automaticamente apesar de manter o
vínculo desconhecido no diagnóstico; Layer ainda precisa de escolha explícita.
Todos os quinze alvos obrigatórios são transportados, sem defaults parciais.
Strict recusa parcial. Mapas/manifestações/WASM anteriores permanecem intactos;
schemas aceitam a nova condição, sem alterar parser nem fixtures privadas.
Doze casos nativos e provas de recusa suportam o contrato limitado, não
suporte universal ou equivalência OLM/Adobe.
