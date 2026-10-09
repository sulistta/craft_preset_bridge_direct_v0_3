# ADR 036 — renderer geométrico original aproximado

Data: 2026-10-09. Estado: implementado, opt-in, sempre PARTIAL.

Um parT/tdb4 real sustenta 21 controles, com quatro menus. A documentação
funcional pública Satori/aescripts não certifica unidades nem algoritmo.
Mapear apenas para geração nativa de triângulos perderia busca por cor,
recursão, jitter e fonte temporal. A API 4 validada permite consultar o
prefixo da própria camada em outro instante.

A implementação MIT original combina seis primitivas, busca esparsa por RGB,
recursão, seed repetível, fades, composição e frame_hold declarado. Mantém
valores brutos; limites/fórmulas são próprios. Não interpreta o seletor de
estilo como preset aplicado, nem o hidden como intensidade. Ambos são perdas.
Budgets de probes/rasterização recusam a saída completa. Não modifica parser,
.research ou o pacote privado; nenhuma expressão é executada.

A evidência separa descritores reais, testes matemáticos próprios e Session
real sobre pixels próprios. Nenhuma equivalência Adobe é presumida.
[Modelo, instalação e limites](../geometric-extension.md).
