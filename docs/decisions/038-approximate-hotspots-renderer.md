# ADR 038 — Hotspots e substituição explícita de máscara

Data: 2026-10-09. Estado: implementado, opt-in, sempre PARTIAL.

Um snapshot sustenta nove controles de processamento e uma máscara de camada
opaca. Blur Mask=12 impede descartar esse caminho como neutro. O default
público None não certifica a referência salva. A substituição manual existente,
fixada ao hash/índice/ID, permite entrada simbólica ou null explícito.

Renderer MIT original usa pico RGB para reduzir regiões escuras mantendo
proporções de cor antes da saturação; boxes fracionários, três modos alpha e
máscara bilinear vêm de código original Bridge. IDs, menus e cor vêm do parT.
Nenhum parser, .research ou preset privado é alterado; nenhum SDK ou asset
proprietário é reutilizado. Fórmulas são aproximações, nunca garantia Sapphire.

A ausência de vínculo recusa a criação, sem defaults substituírem a cena.
Mocha/Path/Combine Masks/tracking permanecem perdas. Strict não publica saída
parcial. Corpus automático não promove status ou contadores por um renderer
instalado; nove controles e um recurso só convertem mediante decisão explícita.
[Contrato, limites e evidência](../hotspots-extension.md).

A inspeção de CurveTracer também encontrou Skip Frame(s) denormal em dois
snapshots. Não se converteu esse padrão em um inteiro presumido: falta evidência
para certificação do layout/unidade. Não foi criado mapa temporal falso.
