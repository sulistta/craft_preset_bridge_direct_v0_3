# ADR 028 — Transporte experimental de imagens auxiliares

Data: 09/10/2026. Estado: experimental, sem promoção de suporte de presets.

## Problema

A ABI WASM API 1 fixada oferece uma imagem e não recebe EffectCtx/EffectHost.
S_DissolveShake e S_MathOps exigem imagens adicionais, e os respectivos valores
Layer FFX permanecem desconhecidos. Acrescentar um nome ao catálogo, usar preto
ou transformar um blob opaco em None perderia o comportamento do preset.

## Decisão

Oferecer um patch opt-in para uma cópia exportada do commit fixado, mantendo a
pesquisa intacta. Preservar os contratos API 1, adicionar render com contexto
e uma ABI experimental API 2 com tabela de imagens/geometry e UID exato em
metades u32. Limitar recursos e recusar ligação indisponível antes da execução.
Revisão/capacidade do host são explícitas; o número API 2 não é atribuído ao
upstream. Não habilitar mapas Adobe nem manifestos API 2 no Bridge nesta etapa.

## Verificação e consequências

Testes originais exercitam pixels auxiliares, UID acima de 2^53/u64 máximo,
offsets/tamanhos/escalas diferentes, modos de recurso, tipos e valores inválidos,
limites, alocação, traps, combustível, resultados não finitos, recuperação,
concorrência e a entrada pelo wrapper de efeitos. Os seis testes API 1 upstream
permanecem incluídos. Um probe separado passa pela Session/render/salvamento.
O preparador produz uma cópia repetível do patch, sem substituir diretórios.

Esta é infraestrutura necessária, não uma conversão de efeitos novos. Sem
renderer e evidência da origem, os status do corpus e o objetivo universal
permanecem pendentes. Detalhes: [contrato](../experimental-multi-input-host.md).
