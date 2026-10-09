# Changelog

## 0.36.0 — 2026-10-09 (suporte universal em andamento)

- Godrays (PEGR): 25 controles reais, renderer original API 2 radial/spin.
- Quality separador recusado, Buffer Expansion neutro, Point bruto recuperado
  do transporte do host. Sempre aproximado, strict sem publicação parcial.
- Dez casos nativos e 25 controles persistidos/reabertos sobre pixels próprios.
- Diagnóstico agregado reproduzível, sem valores/caminhos privados.
- Corpus: 3596 controles/561 chaves, 132 PARTIAL/12 UNSUPPORTED.
- [Instalação, evidência e limites](docs/godrays-extension.md).

## 0.35.0 — 2026-10-09 (suporte universal em andamento)

- OLM Directional Blur: 14 controles reais, renderer anisotrópico original
  com fades/caudas/grupos/ruído e entrada Layer condicional comprovada.
- Smooth/Block estático torna Noise Layer inativa; vínculo opaco e avisos
  preservados. Layer/seletores ambíguos não recebem None por suposição.
- Doze casos na Session nativa, controles persistidos/reabertos, pixels
  próprios full/half. Corpus: 3571 controles/561 chaves, 132 PARTIAL/12 UNSUPPORTED.
- [Instalação, evidência e limites](docs/olmdirectional-extension.md).

## 0.34.0 — 2026-10-09 (suporte universal em andamento)

- HitFilm Hotspots: cinco controles visíveis, gate/threshold, preenchimento
  de cor abaixo do limiar, saturação/brilho e suavização de fonte originais.
- Dois presets reais, dez valores persistidos/reabertos; nove casos nativos
  full/half/alpha sobre pixels próprios. Hidden e fidelidade continuam perdas.
- Módulo independente de S_Hotspots, sem alteração do parser ou presets.
- [Instalação, evidência e limites](docs/hfhotspots-extension.md).

## 0.33.0 — 2026-10-09 (suporte universal em andamento)

- S_Hotspots: renderer original aproximado API 2, nove controles e
  uma máscara substituta explícita; sem presumir None no FFX opaco.
- Session real: máscara luma/alpha/inversão, modos alpha, full/half,
  salvamento/reabertura; nove valores reais preservados sobre pixels próprios.
- Sem vínculos manuais, corpus continua 132 PARTIAL/12 UNSUPPORTED,
  3546 controles/561 chaves; fidelidade/Mocha/path permanecem perdas.
- [Instalação e limites](docs/hotspots-extension.md).

## 0.32.0 — 2026-10-09 (suporte universal em andamento)

- Pixel Encoder: renderer original aproximado API 2, 16 controles, dez
  padrões matemáticos, glifos de segmentos, cores e caos determinístico.
- Um snapshot real, controles persistidos/reabertos em imagens próprias.
  Sem atlas proprietário nem equivalência visual presumida; sempre PARTIAL.
- Corpus: 132 PARTIAL/12 UNSUPPORTED, 3546 controles/561 chaves. O arquivo
  já era parcial por outros efeitos; hashes e 1341 avisos preservados.
- [Instalação e limites](docs/pixelencoder-extension.md).

## 0.31.0 — 2026-10-09 (suporte universal em andamento)

- Geometric Filter: renderer original aproximado API 4, 21 controles,
  seis formas, busca por cor, recursão, fades e acesso a imagens retidas.
- Um snapshot real convertido; 21 controles persistidos/reabertos na Session.
  Seletor de estilo e hidden continuam perdas, strict sem saída parcial.
- Corpus: 132 PARTIAL/12 UNSUPPORTED, 3530 controles/561 chaves; hashes
  e 1341 avisos relevantes preservados. Sem equivalência visual certificada.
- [Instalação, evidência e limites](docs/geometric-extension.md).

## 0.30.0 — 2026-10-09 (suporte universal em andamento)

- API 4/revisão 3 experimental: imagens do prefixo da camada em outros
  instantes, retenção e offsets declarativos; consultas limitadas por árvore.
- Bridge valida manifestos, planos e capabilities antes de alterar a Session.
  APIs anteriores e extensões existentes conservadas.
- 23 verificações de pixels originais na Session real; nenhum novo mapa Adobe.
  Corpus permanece 131 PARTIAL/13 UNSUPPORTED, sem promoção de compatibilidade.
- [Contrato, reprodução e limites](docs/temporal-input-host.md).

## 0.29.0 — 2026-10-09 (suporte universal em andamento)

- Signal: extensão opcional original aproximada API 2, 34 controles brutos,
  modulação/decodificação, ruído, filtros, distorção e tape errors.
- Dois snapshots reais e 68 valores persistidos/reabertos na Session;
  Destruction button permanece perda, sem ação inferida ou unidades inventadas.
- Corpus com todas as extensões: 131 PARTIAL/13 UNSUPPORTED, 3509 controles/561
  chaves. Os 144 hashes e 1341 avisos relevantes preservados; strict sem saída parcial.
- [Evidência, instalação e limites](docs/signal-extension.md).

## 0.28.0 — 2026-10-09 (suporte universal em andamento)

- Host experimental reconhece tempo em plugins API 1 mesmo com controles
  estáticos, corrigindo cache congelado. ABI/mapas/módulos preservados;
  samples full/half, reabertura e reversão temporal verificados.

- Renderer Heatwave original aproximado API 2: 24 controles e substituição
  explícita de máscara, ruído, blur, geometria e cinco modos de saída.
- Menus comprovados no FFX, incluindo Shape None; pontos exigem --size.
  Criação íntegra, grupos selecionados preservados e strict sem saída parcial.
- Testes de controles reais separados de imagens sintéticas; sem comparação
  visual Adobe. Corpus sem vínculos continua 129 PARTIAL/15 UNSUPPORTED;
  144 hashes e 1341 avisos relevantes preservados.
- [Instalação, evidência e limites](docs/heatwave-extension.md).

## 0.27.0 — 2026-10-09 (suporte universal em andamento)

- S_DissolveShake: renderer original aproximado de duas imagens, 40 controles
  e Background manual. Quatro snapshots e cinco grupos reais verificados.
- API 3/revisão 2 experimental acrescenta limites temporais reais da camada;
  APIs 1/2 preservadas. Plugins com contexto não reutilizam pixels cujo cache
  desconhece as dependências de tempo/imagens auxiliares.
- Cinco arquivos antes UNSUPPORTED passam a PARTIAL: 129/15 no corpus de 144,
  3441 controles/561 chaves sem vínculos manuais. Referências FFX continuam
  opacas, perdas preservadas e strict sem preset parcial.
- [Uso e limites](docs/dissolveshake-extension.md).

## 0.26.0 — 2026-10-09 (suporte universal em andamento)

- Renderer MathOps original aproximado API 2/revisão 1, 17 operações, ajustes
  de cor e máscara opcional; controles não neutros preservados.
- Vínculos manuais de origem fixados ao hash/índice/ID, com null explícito,
  perdas no relatório, recusa de animação/expressão e strict sem saída parcial.
- CLI inspect/convert --source-layers; nenhum decoder de referência opaca.
  Criação exige controles íntegros; alterações selecionadas preservam recursos.
- Testes de pixels próprios e projeto reaberto; quatro FFX reais opt-in.
  Corpus automático permanece 124 PARTIAL/20 UNSUPPORTED sem vínculos manuais.
  [Uso e limites](docs/mathops-extension.md).

## 0.25.0 — 2026-10-09 (integração em andamento)

- Patch opt-in para host EffectCraft com transporte experimental API 2: até
  quatro imagens auxiliares, Layer tipado, UID exato, geometria e limites.
  Preparação em cópia isolada; contratos API 1 preservados.
- Sem novo mapa Adobe ou alteração dos contadores de presets nesta etapa.
- Bridge aceita manifestos API 2 com revisão experimental 1, preserva null
  declarado na instalação e exige planos v4/vínculos Layer explícitos.
- Preflight recusa host/API/plugin/defaults divergentes antes de mutação;
  IDs de camada permanecem inteiros exatos. Fingerprints API 1 preservados.
- Plano sintético estático/animado conferido em full/half, save/reopen e
  desvinculação de instância existente preservando suas chaves não selecionadas.
- 602 testes gerais, 27 reais opt-in, Ruff, Mypy e Clippy do probe passaram. Host experimental
  e seus renderers continuam separados; S_DissolveShake/S_MathOps ainda pendentes.
  [Contrato e verificação](docs/experimental-multi-input-host.md).

## 0.24.0 — 2026-10-08 (expansão em andamento)

- Extensão Colorize original aproximada: 23 controles BCC3Colorize, seis
  cores/RGB-HSL-HSV, canais invertidos, looping, Squeeze/Ease/HSL e Mix.
- Quatro instâncias reais preservaram 92 valores estáticos após salvar/reabrir.
  PixelChooser/Mocha/tracking/Compare e diferenças de cor/calibração permanecem
  perdas; Input PixelChooser e criação sem os 23 controles são recusados.
- 11 testes Rust/Clippy, rebuild byte idêntico e 60 casos WASM com referência
  colorsys passaram, incluindo HSL próximo de zero. Full HD ~5,6 s/UHD ~22,2 s.
- 556 testes gerais, 27 reais opt-in e Ruff/Mypy passaram. Com os 12 opcionais
  e Flare local: 124 PARTIAL/20 UNSUPPORTED, 3393 propriedades/507 chaves.
  Os 144 originais permanecem intactos; equivalência visual e objetivo universal pendentes.

## 0.23.1 — 2026-10-08 (diagnósticos de compatibilidade)

- Corrigida omissão de avisos de parâmetros quando um efeito não possui mapa
  ou sua conversão é recusada antes do loop de propriedades. Nome/ID e caminho
  identificam o controle; código, severidade e dados de origem são preservados.
- Auditoria dos 144 arquivos recuperou 353 avisos antes omitidos em 65
  instâncias sem mapa, incluindo seis expressões e dados Mesh Warp.
- 535 testes gerais, 26 reais opt-in, Ruff e Mypy passaram. Os originais
  permanecem intactos. Esta correção não adiciona mapas: cobertura continua
  124 PARTIAL/20 UNSUPPORTED, 3301 propriedades e 507 chaves, sem suporte universal.

## 0.23.0 — 2026-10-08 (integração em andamento)

- Planos v4: referências Layer nativas estáticas com bindings CLI/API explícitos;
  UID bruto/string/Bools não são aceitos como valor de recurso. Null só é unbind
  explícito dentro do objeto tipado; FFX opaco não vira None.
- Preflight confere contexto/pertencimento, recusa self/ausências e fixa UIDs.
  Readback Layer exige tipo estático e comparação inteira exata, inclusive >2⁵³.
- 71 parâmetros Layer em 42 efeitos nativos aplicados, persistidos/reabertos
  com dados próprios. Unbind existente preservou UID/contexto. Três casos de
  pixels no EffectHost oficial verificaram duas imagens; sem comparação Adobe.
- 527 testes gerais, 25 reais opt-in e Ruff/Mypy passaram. Cobertura permanece
  124 PARTIAL/20 UNSUPPORTED e 3301 propriedades/507 chaves. Objetivo universal
  pendente; referências FFX e renderers WASM multientrada ainda exigem trabalho.

## 0.22.0 — 2026-10-08 (expansão em andamento)

- Extensão S_Sharpen original aproximada: 15 controles, Best multibanda/Fast
  unsharp, rejeição de bordas, luma/chroma/RGB e três modos Opacity.
- Uma instância real preservou 15 valores estáticos, conferidos na Session
  oficial após salvar/reabrir. Alternativas e animação só sintéticas.
- Matte/Mocha continuam opacos; widget de edição não é transferido. Kernels,
  qualidade, calibração/cor/HDR permanecem perdas. Strict não publica.
- 11 testes Rust/Clippy, rebuild byte idêntico e 32 casos WASM distintos.
  Full HD Best/Fast ~45/~15 s e 4K Best ~233 s; preview CPU ainda é lento.
- 495 testes gerais e 25 reais opt-in passaram; Ruff/Mypy passaram.
  Todos os opcionais: 124 PARTIAL/20 UNSUPPORTED, 3301 propriedades/507 chaves,
  zero SUCCESS. Os 144 arquivos originais permanecem intactos.

## 0.21.0 — 2026-10-08 (expansão em andamento)

- Extensão Directional Blur original aproximada: 12 controles BCC3Directional
  Blur, Thin/Spread, limiares, deslocamento, nove canais e 27 misturas.
- Três instâncias reais preservaram 36 valores estáticos na Session oficial,
  conferidos após salvar/reabrir. Outras opções/animação só sintéticas.
- Avoid Clipping usa transparência na amostragem, mas não expande canvas.
  Máscaras/audio, calibração/amostragem/cor permanecem perdas. Strict não publica.
- 13 testes Rust/Clippy, rebuild byte idêntico e 86 casos WASM. Full HD com
  checker original não uniforme passou (~96 s); CPU/WASM ainda é lento para preview.
- 478 testes gerais e 24 reais opt-in passaram; Ruff/Mypy passaram.
  Todos os opcionais: 124 PARTIAL/20 UNSUPPORTED, 3286 propriedades/507 chaves,
  zero SUCCESS. Os 144 arquivos originais permanecem intactos.

## 0.20.0 — 2026-10-08 (expansão em andamento)

- Extensão Median original aproximada: dez controles BCC3Median, janela
  retangular orientada, quatro modos/nove canais e raios fracionários.
- Três instâncias reais transferiram 30 valores estáticos; módulo final
  carregado na Session, valores conferidos após salvar/reabrir. Outras opções
  e animações possuem apenas testes sintéticos; sem comparação visual Adobe.
- Até 36 amostras por pixel, com perdas de amostragem/calibração/cor e
  máscaras/composição explícitas. Strict não publica planos parciais.
- 41 casos WASM e 15 testes Rust/Clippy; geração/rebuild byte idênticos.
  Full HD uniforme com um impulso é teste de correção, não benchmark geral.
- 462 testes gerais e 23 reais opt-in passaram; Ruff/Mypy passaram.
  Corpus com todos os opcionais: 123 PARTIAL/21 UNSUPPORTED,
  3250 propriedades/507 chaves, zero SUCCESS. Originais intactos.

## 0.19.0

- Extensão Flicker original aproximada: 14 coeficientes S_Flicker, ruído temporal
  suave determinístico, onda e amplitudes RGB; seed fracionário sem arredondamento.
- Snapshot real de 14 controles e grupo selecionado de três propriedades/três
  chaves isoladas, com preservação de UID/enabled/controles restantes na engine
  e salvamento/reabertura. Calibração e fidelidade visual permanecem perdas.
- 31 casos WASM, nove testes Rust e strict recusando planos parciais. Corpus com
  todos os opcionais: 122 PARTIAL/22 UNSUPPORTED, 3220 propriedades/507 chaves.
  Nenhum preset completo; nenhum arquivo original alterado.


## 0.18.0 — 2026-10-08 (expansão em andamento)

- Extensão Pixel Sort original: 24 controles S_PixelSort, padrões Linear/
  Radial/Circular, dez métricas, seed fracionário/reinícios/mistura/visualizações.
- Um snapshot real Linear preservou 24 propriedades estáticas na Session e
  após reabrir; centros em pixels e seed exato. Outros padrões são sintéticos.
- 48 casos WASM passaram, com controles reais sobre pixels originais e Full HD
  a 37° ~41,4 s; 13 testes Rust, Clippy e rebuild exato.
- Com todas as extensões: 122 PARTIAL/22 UNSUPPORTED, 3203 propriedades/504 chaves.
  Nenhum SUCCESS; Matte/Mocha/canvas/fidelidade continuam perdas. Strict não publica.
- 436 testes regulares e 21 reais opt-in passaram; Ruff/Mypy passaram.
  Os 144 arquivos originais permanecem intactos.

## 0.17.0 — 2026-10-08 (expansão em andamento)

- Extensão Glint original: 25 controles S_Glint, 50 propriedades/12 chaves
  Linear persistidas na Session e após reabrir; 15 samples escalares independentes.
- Raios exponenciais em quatro eixos e canais, threshold/blur/hue/composição
  próprios. Background/Matte/Mocha e fidelidade visual permanecem perdas.
- 30 casos WASM passaram, incluindo dois conjuntos reais de controles sobre
  pixels originais e Full HD ~23,2 s; onze testes Rust, Clippy e rebuild exato.
- Com todas as extensões: 121 PARTIAL/23 UNSUPPORTED, 3179 controles/504 chaves;
  nenhum SUCCESS. Strict não publica parciais. Os originais permanecem intactos.
- 421 testes regulares e 20 reais opt-in passaram; Ruff/Mypy passaram.

## 0.16.0 — 2026-10-08 (expansão em andamento)

- Extensão opcional Modulation original: 12 controles, 24 propriedades/seis
  chaves Linear verificadas na Session e após reabrir, com 12 samples intermediários.
- Renderer próprio FM/quadratura; calibração/filtros/alpha/HDR/gama são perdas
  permanentes. Sempre PARTIAL; strict não publica. Nenhuma comparação visual com origem.
- 22 casos WASM passaram, incluindo dois conjuntos reais de controles sobre
  pixels originais e Full HD ~14,6 s; dez testes Rust de invariantes/limites.
- Com todas as extensões: 120 PARTIAL/24 UNSUPPORTED, 3129 propriedades/492 chaves,
  zero SUCCESS. Builtin 35 mapas permanece 75/69; originais não modificados.
- Pacotes incluem avisos Rust completos junto a Modulation e Diffusion.

## 0.15.1 — 2026-10-08 (expansão em andamento)

- FFX Continuous Bezier: conserva velocidades/influências explícitas; endpoints assimétricos aceitos, interior divergente/Auto/Roving recusados.
- Relatório KEYFRAME_CONTINUITY com perda de vínculo de edição; strict não publica curva parcial.
- S_Shake real recupera uma propriedade/duas chaves; grupo de 11 propriedades/12 chaves validado com quatro lados Bezier, três samples e salvamento/reabertura na engine.
- Harness de grupos selecionados aceita --file dentro do corpus autorizado, para validação focada sem copiar presets privados.

## 0.15.0 — 2026-10-08 (expansão em andamento)

- Premiere CS6: três mapas parciais comprovados (Geometry legado, Channel Blur, Mosaic), total 35 builtin/5 Premiere.
- Slider inteiro XML type 1: constante salva e valores animados, rejeição de frações/não finitos; interpolação continua recusada.
- Limitações permanentes de obturação, menu Dimensions e Sharp Colors não implementado pelo renderer.
- Referência pública opt-in: cinco componentes/26 parâmetros estáticos importados e conferidos integralmente na Session FilmCraft. Sem comparação Adobe ou fixture distribuída.

## 0.14.1 — 2026-10-08 (expansão em andamento)

- Leitor estrutural Mesh Warp: 64 registros/dez floats por blob, cabeçalho
  observado, sem perda de pares e roundtrip exato nos dois blobs reais.
- Associação usa instância aRbs, sem substituir pelo default parT; animações,
  layouts desconhecidos e dados inválidos continuam recusados.
- Geometria/tangentes ainda sem tradução: efeito permanece UNSUPPORTED.
  Nenhum mapa nominal OLM foi criado; pacote oficial não contém código-fonte.

## 0.14.0 — 2026-10-08 (expansão em andamento)

- Extensão original Diffusion: 17 controles omino_diffusion; paleta, faixas e
  difusão limitada de erro. Algoritmo/calibração próprios, sempre PARTIAL.
- Quatro componentes reais: 68 propriedades estáticas conferidas na Session
  oficial e na reabertura; WASM verificado em pixels de teste, incluindo Full HD.
- Com todas as extensões: 119 PARTIAL/25 UNSUPPORTED, 3104 propriedades/484 chaves;
  zero SUCCESS. Todos os 144 hashes do pacote privado permanecem iguais.
- S_DissolveShake continua sem mapa: segunda entrada e Auto Trans não são
  atendidos pelo ABI v1; Background permanece opaco.

## 0.13.0 — 2026-10-08 (expansão em andamento)

- Extensão original Stretch: 20 controles pixel_stretch, estiramento cumulativo
  com integração de cobertura subpixel, quatro direções, seis curvas, oito modos
  de canal, distribuição, phase/sync, shading, bordas e feather próprios.
- Oito snapshots reais em dois perfis de versão: 145 propriedades estáticas
  aplicadas/persistidas na Session nativa. Intensity Source permanece opaco e
  sem acesso a outra camada; a aproximação é permanente e strict não publica.
- Animação selecionada exclusivamente sintética: três controles/seis chaves,
  quatro lados Bezier e nove valores intermediários conferidos após reabertura,
  mantendo UID/índice/enabled e controles não selecionados.
- Com Glow, Shake, biblioteca Flare e Stretch: 117 PARTIAL/27 UNSUPPORTED,
  3036 propriedades/484 chaves. Nenhum SUCCESS; suporte universal permanece pendente.
- Loader WASM oficial: 21 casos de pixels/controlos passaram, incluindo oito
  conjuntos reais de controles sobre pixels originais de teste e Full HD ~72 s.
  Desempenho interativo limitado; sem comparação visual Adobe.

## 0.12.0 — 2026-10-08 (expansão em andamento)

- Biblioteca Flare local: builder headless de WASM/mapa a partir de Options OFP
  estático associado. Template original MIT sem cenas privadas; runtime não exige
  compilador, Adobe ou assets externos. Dez controles globais, 12 famílias
  procedurais aproximadas e escolha de cena por hash exato.
- Criação exige cena comprovada; ausência/ambiguidade/cena fora da biblioteca
  recusa o componente inteiro. Atualizações selecionadas preservam scene existente.
  Texturas e controles não implementados são perdas permanentes; strict não publica.
- Corpus real: 9 snapshots/6 cenas +21 grupos selecionados, 219 controles/141
  chaves exportados e persistidos na Session nativa. Cena não default, UID/índice/
  enabled, 22 lados Bezier e 75 samples intermediários verificados após reabertura.
- Com Glow, Shake e biblioteca Flare: 111 PARTIAL/33 UNSUPPORTED, 2891 controles/
  484 chaves. Nenhum SUCCESS; sem comparação visual Adobe. Full HD passou em ~83 s
  no renderer CPU/WASM, com desempenho interativo limitado.
- Harness calcula a grade temporal exata quando a lista usual de FPS não serve;
  um grupo Optical exige 21 fps, que antes faltava na lista de auditoria.

## 0.11.1 — 2026-10-08 (expansão em andamento)

- Leitor estrutural original OFP v3 para Optical Flares: 38 blocos reais,
  602 objetos e 39665 campos, com reconstrução exata dos bytes.
- Nove cenas vinculadas ao parâmetro Options em snapshots estáticos;
  29 blocos sem associação ficam no diagnóstico, sem escolher um estado atual.
- Limites de tamanho/campos/objetos e prazo de parsing; estruturas truncadas,
  valores não finitos e edições inconsistentes recusadas. Sem execução ou acesso a assets.
- Optical Flares ainda não é exportado nem renderizado. A cobertura do lote
  permanece 101 PARTIAL/43 UNSUPPORTED com Glow e Shake; nenhum preset completo.
- 313 testes passaram com corpus real e Qt offscreen; Ruff/Mypy passaram.
  Wheel instalado sem Qt e build desktop Linux verificados; fontes privadas preservadas.

## 0.11.0 — 2026-10-08 (expansão em andamento)

- Renderer original opcional Bridge Shake: 43 controles S_Shake, ruído/ondas
  determinísticos, estilos, wrapping, canais e blur aproximado. Sempre PARTIAL.
- 19 snapshots/13 grupos selecionados: 954 controles/233 chaves exportadas.
  31 componentes preservaram 911 controles/229 chaves na engine e após reabertura;
  um componente foi recusado por tempo incompatível, sem deslocar keyframes.
- Com Glow e Shake: 101 PARTIAL/43 UNSUPPORTED, 2672 controles/343 chaves.
  Builtin permanece 75/69, 1370/17. Suporte universal ainda não atingido.
- 290 testes Python, sete Rust e Clippy passaram; 17 casos WASM sintéticos
  renderizados, incluindo Full HD/blur/RGB (~132 s em CPU). Sem comparação Adobe.

## 0.10.0 — 2026-10-08 (expansão em andamento)

- Perfis de origem ampliados para 2648 IDs comprovados em parT/tdb4, independentes
  dos mapas. IDs derivados pelo Bridge deixam de ser tratados como prova de origem.
- Deep Glow selecionado: 18 grupos/49 controles/93 keyframes, com 31 lados Bezier
  persistidos e 150 amostras intermediárias verificadas na engine e após reabertura.
- Aplicação animada ativa a composição de destino após preflight: a API de seleção
  de chaves usa a composição ativa. GUI/CLI/dry-run informam essa etapa.
- Com Glow: 92 PARTIAL/52 UNSUPPORTED, 1718 parâmetros/110 chaves. Builtin: 75/69,
  1370/17. A aproximação permanece parcial; suporte a todos os efeitos não foi atingido.

## 0.9.0 — 2026-10-08 (expansão em andamento)

- Extensão opcional Bridge Glow: renderer WebAssembly original MIT, sem dependências,
  mapa de 13 controles PEDG com evidência real e instalação headless por extensions.
- Limitações de mapa declaradas geram MAPPING_APPROXIMATION; strict recusa sempre.
- 23 snapshots reais: 299 propriedades persistidas pela engine. Com extensão: 80
  parciais/64 não suportados, 1669 parâmetros/17 chaves; builtin permanece 75/69.
- Auditoria do renderer e teste de animação sintéticos separados da evidência real.
  Gama automática, controles antigos/qualidade e fidelidade visual continuam pendentes.

## 0.8.0 — 2026-10-07 (expansão em andamento)

- Pacotes v2 podem declarar catálogos de plugins nativos API v1 com tipos/limites validados.
- Planos v3 fixam o manifesto; preflight confere versão, parâmetros e defaults antes da mutação.
- Planos v2 builtin permanecem aceitos; instalação falha não altera parcialmente o registro.
- Loader WASM oficial no harness: três propriedades persistidas e 12 samples sintéticos renderizados.
- 259 testes passaram, incluindo corpus real; Ruff/Mypy e distribuição Python/Linux verificados.
- Cobertura real inalterada: 75 parciais/69 sem conversão, 1370 parâmetros/17 chaves; nenhum completo.
- A extensão permite renderers novos; ainda não implementa equivalência de Deep Glow/Optical Flares/Sapphire.

## 0.7.0 — 2026-10-07 (expansão em andamento)

- Novo mapa Color Neutralizer: Pinning/Blend com condições para View e pontos preto/branco.
- pard display_flags preservado; RGB sem unidade comprovada continua perda, sem inferir escala pelo intervalo.
- Perfil RGB percentual estático testado apenas com fixture sintética; seletores UI-only não aplicam correção duplicada.
- Engine: quatro propriedades de dois efeitos reais e cinco de um efeito sintético salvas/reabertas.
- Corpus: 75 parciais/69 sem conversão, 1370 parâmetros/17 keyframes; 32 mapas; nenhum preset completo.
- 219 testes passaram, incluindo corpus real; Ruff/Mypy, builds Python/Linux e smoke Qt verificados.
- Suporte universal e equivalência visual Adobe continuam pendentes.

## 0.6.0 — 2026-10-07 (expansão em andamento)

- Curves parcial: cinco canais com todos os 256 samples da LUT de origem; pontos originais retidos.
- Perdas de interpolação, HDR e precisão 16/32bpc registradas; strict continua recusando resultados parciais.
- Text estático tipado e limitado; Hidden recebe Text somente quando seu default nativo é string.
- Gramática de curvas recusa tokens inválidos, duplicatas, NUL, valores não finitos e animação textual.
- Corpus: 75 parciais/69 sem conversão, 1366 parâmetros/17 keyframes; nenhum completo.
- Engine: 22 componentes/110 propriedades persistidos; erro máximo de 0,0246 nível de 8 bits nos samples auditados.
- 197 testes passaram, incluindo corpus real; Ruff/Mypy, builds Python/Linux e smoke Qt verificados.
- Suporte integral continua pendente, incluindo plugins, tangentes Mesh Warp e curvas animadas.

## 0.5.0 — 2026-10-07 (expansão em andamento)

- Quatro mapas FFX: Radial Blur, CC Radial Blur, Camera Lens Blur e CC Scale Wipe.
- Menus com opções sem equivalente recusadas; Amount fora do limite nativo não é limitado silenciosamente.
- Camera Lens Blur converte limiar 0–1 para 0–255, incluindo velocidades; layer e focal não zero continuam perdas.
- Catálogo FilmCraft completo: 303 efeitos/1426 parâmetros; validação de parâmetros não animáveis.
- Perfis exatos de origem ampliados para 176 IDs, sem conflitos.
- Corpus: 69 parciais/75 sem conversão, 1256 parâmetros/17 keyframes; nenhum preset completo.
- Engine real: oito componentes/47 parâmetros/duas chaves conferidos e persistidos em projeto reaberto.
- Suporte universal ainda em andamento; sem garantia de equivalência visual Adobe.

## 0.4.0 — 2026-10-07 (expansão em andamento)

- Lumetri parcial com condições declarativas para grupos ativos, intensidade e menus verificados.
- Catálogo de 150 tipos de parâmetros de origem; propriedades selecionadas agrupadas e vinculadas à instância existente.
- Preflight dos vínculos e preservação dos demais parâmetros/ativação; não mescla animações/expressões existentes.
- Bool/Choice Hold e Color single-ease Linear/Hold; chaves isoladas discretas normalizadas com registro.
- Checagem temporal em segundos corrige aceitação indevida de taxas decimais próximas ao NTSC.
- Corpus: 64 parciais/80 sem conversão, 1209 parâmetros e 15 keyframes; nenhum preset completo.
- Engine real: 16 novos componentes, 226 valores e 11 keyframes conferidos; Bool/Choice/Color sintéticos com valores intermediários verificados.
- 151 testes, Ruff/Mypy; objetivo universal ainda em andamento.

## 0.3.0 — 2026-10-07 (expansão em andamento)

- Seis novos mapas: Hue/Saturation, Levels, Exposure, Black & White, Invert e Box Blur.
- Leitura validada de aRbp com todos os canais; campos temporários da UI deixam de substituir os ajustes reais.
- Curves preserva LUTs/pontos no modelo; exportação ainda depende de validar a interpolação.
- Menus Invert com separadores e clipping Levels com tabela explícita; opção 32bpc recusada.
- Lote privado: 56 parciais/88 sem conversão, 989 parâmetros/nove keyframes; nenhum completo.
- Engine real: 55 planos aplicados, 976 parâmetros conferidos e projeto salvo; um plano recusado por arredondamento de frames.
- 124 testes, incluindo corpus real; Ruff/Mypy e build Linux verificados.
- Suporte universal continua em andamento; plugins e recursos restantes não são declarados compatíveis.

## 0.2.0 — 2026-10-07 (expansão em andamento)

- Catálogo EffectCraft com 306 efeitos/3009 parâmetros extraídos da biblioteca oficial.
- Onze novos mapas FFX; pontos em pixels, conversão ARGB/RGBA, menus com separadores e propriedades aninhadas.
- Correção de Geometry2; planos v2 exigem reconversão de planos v1.
- Associação verificada de índices com lacunas e separação de caminhos de propriedades em presets mistos.
- 102 testes; lote privado: 52 resultados parciais e 92 sem conversão, 513 parâmetros/9 keyframes preservados.
- Objetivo de suportar todos os efeitos ainda não concluído; inventário e lacunas documentados.

## 0.1.0 — 2026-10-07

- Primeiro núcleo Python local, modelos versionados e parsers XML/RIFX limitados.
- Mapeamentos declarativos, exportação nativa FilmCraft e planos próprios EffectCraft.
- CLI, lotes, relatórios JSON/HTML/CSV, strict, dry-run e operações sem sobrescrita.
- GUI PySide6 em português, temas, inspeção, worker e prévia antes de aplicação.
- Adaptadores locais oficiais, confirmação e salvamento .ecproj pela engine.
- Testes sintéticos, fixtures reais opt-in, validação nativa e preparação de builds multiplataforma.
- Limitações de curvas, plugins e recursos complexos documentadas com evidência explícita.
