# Expansão para todos os efeitos — trabalho em andamento

O objetivo é suportar todos os efeitos. **Ainda não foi atingido.** O catálogo de destino
completo e o inventário do corpus não são declarações de conversão universal.

Estado atual builtin 0.23: 35 mapas (30 FFX/cinco Premiere), 75 PARTIAL/69 UNSUPPORTED no corpus
de 144 arquivos, 1370 parâmetros e 17 chaves exportados; nenhum preset completo.
Os números das seções anteriores são históricos, não contagens cumulativas de validação.

## Evidência e cobertura

`catalogs/effectcraft.json` foi extraído dos `ParamSpec` reais da biblioteca oficial,
no commit e38a92e792c07f1c57c5dcfcab37d91932b9e2b8, pelo harness do projeto.
São 306 efeitos e 3009 parâmetros, incluindo os tipos que o exportador ainda não suporta.
O catálogo distingue tipos, defaults, limites e opções. Não se deduz correspondência Adobe
por semelhança de nome. Os seis perfis manuais anteriores mantêm seus limites auditados.

Regeneração opcional, sem alterar os clones:

```sh
CARGO_PROFILE_DEV_DEBUG=0 CARGO_INCREMENTAL=0 CARGO_TARGET_DIR=artifacts/native-target \
  cargo +1.98.1 build --locked --manifest-path scripts/native-validation/Cargo.toml -j 4
artifacts/native-target/debug/craft-bridge-native-validation catalog-effectcraft > docs/catalogs/effectcraft.json
python scripts/make_builtin_catalog.py
python scripts/generate_schemas.py
```

O snapshot contém somente dados públicos do catálogo MIT. Os presets privados não estão
incluídos. Na 0.2 foram adicionados 11 mapas FFX: Motion Tile, Noise, Noise HLS, Noise HLS Auto,
Wave Warp, Optics Compensation, Detail-preserving Upscale, Camera-Shake Deblur, Tint,
Tritone e 4-Color Gradient. As opções sem equivalente permanecem recusadas por parâmetro.

## Correções de semântica

- **Pontos:** o FFX guarda pontos normalizados; `EffectCraft default_value` multiplica
  defaults pela dimensão da camada e os renders usam pixels. A versão 0.1 enviava os
  pontos de Geometry2 diretamente, o que estava errado. Agora Transform, Motion Tile,
  Optics Compensation e os pontos do gradiente exigem `--size` para converter em pixels.
  Para FFX, informe o tamanho da camada de destino. Não se assume 1920×1080 no produto.
- **Planos v2:** planos EffectCraft v1 são rejeitados com instrução de reconverter.
  Alterar somente o número da versão não corrige valores antigos. O formato nativo
  FilmCraft continua na versão 1 definida pela engine.
- **Cores:** `py-aep/docs/file_format.md`, seção cdat, documenta doubles A,R,G,B em
  0–255. A API destino usa R,G,B,A em 0–1. O mapa reordena e divide os valores e
  velocidades por 255; reordena também as influências e códigos por componente.
- **Menus:** pdnm inclui separadores que consomem posições. Wave Warp/pinning e
  4-Color Gradient/blendingMode usam tabelas explícitas. Exemplo: valor 7 do gradiente
  corresponde a Overlay, índice 5 no destino, não ao índice 6. Separadores são recusados.
  Upscale/Alpha aceita Bicubic; Detail-preserving da origem não equivale ao Bilinear destino.
- **Índices:** índices originais podem começar em 1 ou conter lacunas. Só se aceita
  associação por ordem quando há um snapshot por caminho de efeito, índices estritamente
  crescentes e namespace de parâmetros correspondente ao match name. Duplicatas, ordem
  invertida e namespaces divergentes continuam recusados.
- **Presets mistos:** caminhos para parâmetros selecionados não consomem snapshots de
  efeitos inteiros. Os efeitos inteiros são associados separadamente; os caminhos de
  propriedades ainda sem aplicação ficam nos avisos. Isso impede atribuir parâmetros
  do primeiro efeito ao caminho de uma propriedade de outro efeito.
- **Curvas de pontos:** easing temporal por componente não equivale ao easing espacial
  único da engine (`commands/anim.rs:set_ease`). Bezier Vec2 permanece recusado até existir
  tradução geométrica comprovada; não basta escalar duas velocidades.

## Validação da expansão 0.2

102 testes passaram, incluindo fixtures reais opt-in. Ruff e Mypy passaram.
Com referência explícita de 1920×1080, o corpus privado de 144 arquivos passou de
6 PARTIAL/138 UNSUPPORTED para **52 PARTIAL/92 UNSUPPORTED**, zero SUCCESS.
São **513 parâmetros e nove keyframes** preservados. Isso não torna completos os 52 presets.

Na Session EffectCraft real, 51 planos foram aplicados e 500 parâmetros conferidos
por prop.get. Um plano foi recusado antes de mutação porque a composição 30 fps
arredondaria keyframes. O componente Noise HLS desse preset foi aplicado separadamente,
com seis parâmetros conferidos, sem declarar o preset inteiro como aplicado. Assim, todos
os 11 novos mapas tiveram ao menos um componente real aplicado; curvas/opções recusadas
continuam perdas. `file.saveAs` produziu `artifacts/expanded-v0.2-validation.ecproj` pela engine.
Os resultados detalhados estão em `artifacts/expanded-*` e `artifacts/native-noisehls-component.json`.
Não houve renderização comparativa Adobe nem comprovação de identidade visual.

## Expansão 0.3: dados arbitrários de cor

Foram adicionados seis mapas FFX: Hue/Saturation, Levels, Exposure, Black & White, Invert
e Box Blur. São 25 mapas no total, 23 FFX e dois Premiere. Os três efeitos de cor com
dados arbitrários são lidos em aRbs/aRbp de instância, após o tdbs correspondente;
não se usam os defaults de parT nem os valores temporários da UI como estado renderizável.

Hue/Saturation decodifica 45 ajustes, incluindo Master e as seis janelas de cor circulares.
Levels decodifica os 25 valores dos cinco canais e replica os switches globais de clipping
para cada canal no destino. O corpus contém divergências entre os valores UI e o blob,
cobertas por teste real. Curves preserva cinco LUTs de 256 bytes e até 16 pontos por canal
no modelo intermediário, mas ainda não exporta: falta validar a equivalência da interpolação.
Blobs animados/múltiplos, versões/flags desconhecidos e sombras UI animadas são recusados.
Detalhes e clipping Levels condicionado a 32bpc: [ADR 003](decisions/003-arbitrary-color-state.md).

Com a mesma referência explícita de 1920×1080, os 144 arquivos agora produzem
**56 PARTIAL / 88 UNSUPPORTED / zero SUCCESS**, com **989 parâmetros e nove keyframes**
preservados. Todos continuam incompletos. As sete instâncias Hue/Saturation, três Levels,
duas Exposure, uma Black & White, duas Invert e duas Box Blur foram aplicadas na engine real.

Na Session EffectCraft, 55 planos tiveram 976 parâmetros conferidos por prop.get.
O plano de hash fc6677db… continuou recusado antes de mutação por arredondamento a 30 fps.
Todos os 476 parâmetros acrescentados nesta etapa foram conferidos na engine.
O projeto de validação foi salvo pela API oficial em `artifacts/arbitrary-v0.3-validation.ecproj`.
Resultados detalhados: `artifacts/arbitrary-*`. A aceitação e o roundtrip dos parâmetros
não comprovam identidade visual Adobe; não houve renderização comparativa.
124 testes passaram, incluindo os testes reais opt-in; Ruff e Mypy passaram.
O executável Linux foi reconstruído e verificado em execução Qt offscreen.

## Expansão 0.4: Lumetri e propriedades selecionadas

Lumetri acrescenta 24 regras condicionais: Basic Correction, Creative e Vignette exigem
ativação estática comprovada; Creative exige intensidade 100. Look/Input LUT só aceitam
None. Curvas, wheels, seleção HSL e blobs não interpretados continuam perdas explícitas.
Nove instâncias reais forneceram 205 parâmetros aplicados e conferidos na engine.
O catálogo agora tem 26 mapas, 24 FFX e dois Premiere.

Um snapshot de 150 IDs/tipos reais de origem permite ler propriedades selecionadas sem
parT. Cinco arquivos do corpus contêm ajustes Motion Tile/Tritone; eles são agrupados
por instância e exportados como application=existing. O adaptador confere o efeito na
posição original antes de qualquer mutação e mantém os outros parâmetros e enabled.
Não cria cópias nem mescla chaves/expressões existentes sem validação.

Bool/Choice aceitam Hold; uma chave isolada Linear é tipada e normalizada para Hold,
com adaptação registrada. Color single-ease de 152 bytes aceita Linear/Hold com tangentes
nulas. Bezier, auto e variantes desconhecidas continuam recusados. O Tritone selecionado
do corpus confirmou a estrutura real de cor animada. Consulte [ADR 004](decisions/004-selected-properties-and-conditions.md).

O lote 1920×1080 agora produz **64 PARTIAL / 80 UNSUPPORTED / zero SUCCESS**, preservando
**1209 parâmetros e 15 keyframes**. Os 144 hashes originais continuam iguais. Nesta etapa,
**16 componentes novos tiveram 226 parâmetros e 11 keyframes conferidos** na engine real:
nove Lumetri, quatro Motion Tile selecionados, um Tritone selecionado e dois Camera-Shake
Deblur com opções animadas. Os cinco vínculos existentes mantiveram a quantidade de efeitos,
o estado disabled e um parâmetro não selecionado com valor não padrão. São componentes;
não se declara que todos os 64 planos completos foram aplicados.

A investigação nativa revelou que 23.976 é normalizado a 24000/1001 pela engine. A checagem
temporal foi corrigida para comparar segundos pós-snap; a diferença do preset 23976/1000
agora é recusada antes de mutação. Nas composições isoladas de validação, 47.952 preservou
os tempos exatos de dois componentes. O adaptador não altera FPS do projeto do usuário.

Fixtures sintéticas separadas confirmaram dois keyframes Hold de Bool/Choice e dois
Linear de Color, incluindo valores intermediários via prop.get. Não são fixtures Adobe.
O projeto real foi salvo em `artifacts/selected-v0.4-validation.ecproj`; evidência detalhada
em `artifacts/selected-*` e `artifacts/synthetic-new-keyframes-native.json`.
O arquivo foi reaberto por file.open oficial: os 16 componentes, 226 valores e 11 chaves
persistiram corretamente. Foram executados 151 testes, Ruff/Mypy e smoke Qt do build Linux.
Não houve comparação de renderização Adobe nem comprovação de equivalência visual.

## Trabalho necessário para concluir o objetivo

O corpus contém **77 IDs distintos**. Ainda faltam os demais mapas nativos, incluindo
exportação de Curves, completar Lumetri (LUTs/curvas/wheels/HSL), LUTs, Radial/Lens Blur,
Mesh Warp, efeitos CC, propriedades selecionadas complexas, máscaras e curvas espaciais.
O FilmCraft também precisa ter o catálogo e os mapas ampliados além dos dois perfis iniciais.

OpticalFlares, S_Shake, PEDG, S_DissolveShake, Looks e os demais plugins exigem interpretação
de parâmetros/blobs e uma implementação de renderização correspondente. Um arquivo FFX
contém configurações, não o executável do plugin. Quando a engine não oferece o efeito,
será necessário desenvolver uma implementação própria ou uma extensão de destino;
substituir o nome por um efeito parecido não satisfaz o objetivo.

Para cada efeito, conclusão exige: associação correta das propriedades, unidades e menus,
preservação de animação/recursos, efeito de destino implementado, aplicação nativa conferida
e validação do resultado visual. O inventário em `effects-inventory.json` registra os IDs
locais e mapas existentes; não omite efeitos difíceis para reduzir o escopo.

## Expansão 0.5: blurs, Scale Wipe e catálogo FilmCraft

Foram adicionados quatro mapas FFX, com evidência dos descriptors e valores reais de origem:

- **Radial Blur:** Amount, Center (normalizado → pixels), Type e anti-alias High.
  O renderer nativo ignora a escolha de qualidade e sempre faz anti-alias. Low permanece
  recusado, assim como o seed e o campo interno sem semântica estabelecida. Uma das duas
  instâncias tem Amount=231, além do limite 100 do destino: o parâmetro é recusado, sem clamp.
- **CC Radial Blur:** tabela explícita Straight Zoom/Fading Zoom/Centered Zoom/Rotate/Rotate
  Fading. O separador ocupa o índice 4 na origem; Scratch (6) não existe no renderer destino.
  As três instâncias reais usam Scratch: Amount/Quality/Center são aplicados, mas Type
  permanece uma perda relevante. Os resultados continuam parciais; o tipo default da engine
  não é declarado equivalente a Scratch.
- **Camera Lens Blur:** 15 propriedades, incluindo iris aninhada, highlights e toggles.
  O menu real tem oito polígonos; não se inventa a opção Circle. Canal aceita somente
  Luminance/Alpha, porque os canais RGB separados não equivalem ao Color combinado nativo.
  A documentação Adobe de [Blur & Sharpen](https://helpx.adobe.com/uk/after-effects/desktop/apply-effects-and-animation-presets/list-of-effects/blur-sharpen-effects.html)
  estabelece Threshold 0–1; blur2.rs nativo divide por 255. A operação times_255 converte
  valores e velocidades Bezier, sem mudar influências nem tempos. Blur Map Layer continua
  opaco, inclusive quando seus bytes são zero; não se presume referência None. Focal Distance
  é aplicado somente quando zero estático, pois as unidades não zero ainda não foram comprovadas.
- **CC Scale Wipe:** Stretch e Direction conservados; Center convertido em pixels.
  O roundtrip confirma os valores, sem afirmar igualdade do algoritmo visual Adobe.

Com referência explícita 1920×1080, a cobertura passou de 64 para **69 presets parciais**, e
os sem conversão de 80 para **75**. São **1256 parâmetros e 17 keyframes** exportados,
47 parâmetros/duas chaves a mais. Nenhum preset completo. Os 144 hashes de entrada foram
comparados ao relatório anterior e aos arquivos atuais, sem alterações.

Todos os oito componentes reais dos novos mapas foram aplicados na Session oficial
EffectCraft isolada: três CC Radial Blur, dois Radial Blur, dois Camera Lens Blur e um
CC Scale Wipe. O adaptador conferiu os **47 valores e duas chaves** após aplicar. file.saveAs
salvou .ecproj e file.open reabriu o projeto; prop.get retornou exatamente os mesmos valores,
tempos e interpolações de cada propriedade. A instância Lens com chave em 9000/23976 s
usou composição 47.952 fps, sem arredondar seu tempo. Isso não certifica os planos inteiros
que contêm esses componentes nem substitui renderização comparativa Adobe.

A validação pode ser repetida no harness descartável (nunca na Session desktop do usuário):

```sh
.venv/bin/python scripts/validate_native_components.py CORPUS_LOCAL artifacts/nova-validacao \
  --source 'ADBE Radial Blur' --source 'CC Radial Blur' \
  --source 'ADBE Camera Lens Blur' --source 'CC Scale Wipe'
```

Artefatos privados de evidência: artifacts/blur-native-v0.5/{reports,components,summary}.json
mais planos individuais e native-validation.ecproj. Não são incluídos na distribuição.

O harness também extrai agora effect_defs() oficial FilmCraft para
**docs/catalogs/filmcraft.json: 303 efeitos e 1426 parâmetros**. O catálogo gerado preserva
IDs, tipos, opções, limites, defaults e animatable, com os limites manuais auditados dos dois
mapas anteriores. Campos não animáveis recusam chaves na conversão e na validação de JSON
importado. Os defaults Vec2 NaN de auto_point aparecem como null na serialização serde;
permanecem dados de catálogo e nunca são usados como coordenadas de conversão. Os 303
IDs disponíveis não constituem 303 mapas Premiere: continuam dois mapas nesse fluxo.

Regeneração do snapshot, com o mesmo build nativo descrito no início:

```sh
artifacts/native-target/debug/craft-bridge-native-validation catalog-filmcraft > docs/catalogs/filmcraft.json
.venv/bin/python scripts/make_builtin_catalog.py
.venv/bin/python scripts/make_ffx_profiles.py CORPUS_LOCAL
.venv/bin/python scripts/generate_schemas.py
```

O catálogo de tipos de origem agora tem 176 IDs exatos, sem conflitos. Os testes desta etapa
incluem opções Scratch/separadores/RGB/Low recusadas, limiar e velocidades ×255, Amount fora
do intervalo, referências opacas, strict sem saída parcial e animação FilmCraft não suportada.

## Expansão 0.6: Curves e strings estruturadas

Curves estático agora tem conversão parcial: cada uma das cinco LUTs é transferida
integralmente como 256 pares x/255,y/255 no parâmetro Text nativo correspondente.
Pontos, flags e LUT originais continuam no modelo intermediário. O relatório sempre
registra a perda CURVES_INTERPOLATION, pois a reamostragem nativa e a LUT de 8 bits
não preservam a interpolação Adobe, cálculos 16/32bpc nem HDR. Strict continua recusando.
Detalhes, controles de segurança e evidência: [ADR 005](decisions/005-curves-lut-transfer.md).

O novo tipo Text admite UTF-8 estático de até 65536 bytes sem NUL. Hidden só recebe esse
perfil quando seu default nativo é Value::Str. Campos numéricos Hidden continuam Opaque.
A gramática Curves exige pares finitos, em 0..1, x crescente de 0 a 1; tokens inválidos
ou duplicados que a engine ignoraria silenciosamente são recusados. Text animado é
recusado tanto na conversão como na validação de planos. Text FilmCraft estático também
usa o wrapper serde nativo e schema verificado. Planos com esse tipo exigem Bridge 0.6+.

Dos 24 efeitos Curves do corpus, **22 estáticos são transferidos**, com **110 propriedades**;
as duas instâncias com animação/estrutura não validada permanecem recusadas. A seleção
UI do canal da origem ainda aparece como parâmetro não mapeado. O corpus passou de
69 para **75 PARTIAL**, de 75 para **69 UNSUPPORTED**. Agora são **1366 parâmetros e
17 keyframes exportados**; nenhum preset completo. Os 144 hashes originais foram verificados.

A engine oficial aplicou os 22 componentes e conferiu as 110 strings por prop.get.
file.saveAs/file.open preservaram todas elas exatamente. O avaliador Curve::parse/eval
oficial examinou 110 canais ×256 samples. A reconstrução só pelos pontos gerou erro
máximo de **39,094917 níveis de 8 bits**; a transferência de LUT, **0,02454235 nível**.
O harness renderizou também 220 ramps pelo renderer ec.color.curves, isolando um canal
por vez, e confirmou os mesmos samples do avaliador. Isso verifica o renderer destino e
sua transferência dos samples, sem afirmar equivalência visual com Adobe.

Evidência privada: artifacts/curves-native-v0.6/ contém planos, relatórios, roundtrip e
native-validation.ecproj; artifacts/curves-render-audit-v0.6/ contém auditoria quantitativa.
Nenhum desses dados/fixtures é incluído no Git ou nas distribuições. Uma fixture Text
sintética de simple_text FilmCraft foi importada pela Session oficial, separadamente.

Mesh Warp foi investigado: default e instância contêm grade com controles adicionais,
enquanto o destino interpola offsets bilinearmente. As tangentes ainda não têm tradução
comprovada; o blob continua opaco. O objetivo de suportar todos os efeitos permanece ativo.

197 testes passaram, incluindo corpus real; Ruff/Mypy passaram. Wheel/sdist, instalação
headless sem Qt e executável Linux foram verificados; o smoke Qt não apresentou erros.

## Expansão 0.7: Color Neutralizer e declaração de unidades

Novo mapa CS Color Neutralizer → ec.color.cccolorneutralizer. Pinning/Blend exigem
View final, Black Point 0 e White Point 100, todos únicos/estáticos/sem perdas.
Os dois efeitos reais preservam quatro propriedades no total, aplicadas e conferidas
após salvar/reabrir o projeto nativo. RGB continua perda nessas instâncias: seus
descriptors não declaram unidade percentual. O intervalo -100..100 não foi tomado
como prova de escala. O relatório explica essa recusa por trio RGB.

O parser preserva display_flags de pard kind 10. Um perfil RGB adicional exige
porcentagem explícita, três sliders estáticos e o seletor UI-only comprovado; combina
os componentes usando as anchors nativas sem aplicar o seletor novamente. Foi
validado apenas com fixture sintética: cinco propriedades persistidas na engine,
inclusive cores fora de 0..1. Interpolação tonal/clipping/pinning continuam aproximações
e strict recusa resultados parciais. Evidências e condições: [ADR 006](decisions/006-neutralizer-rgb-transfer.md).

O corpus tem **75 PARTIAL/69 UNSUPPORTED, 1370 parâmetros e 17 chaves**; nenhum
preset completo. O novo mapa não aumenta o número de arquivos parcialmente convertidos,
pois os dois arquivos já continham outros efeitos mapeados. Há 32 mapas, sendo 30 FFX
e dois Premiere. Suporte integral continua em andamento.

219 testes passaram, incluindo corpus real; Ruff/Mypy passaram. Wheel/sdist, instalação
headless e build desktop Linux foram verificados, com smoke Qt offscreen. Os 144 hashes
de origem continuam iguais aos do lote anterior. As fontes privadas não foram modificadas.

## Expansão 0.8: suporte a renderers externos

Pacotes v2 podem adicionar manifestos de plugins nativos API v1 ao catálogo do Bridge.
Planos v3 fixam o manifesto; o preflight recusa alterações de versão, parâmetros e
defaults antes da mutação. Planos v2 builtin continuam aceitos. Não há carga automática
de módulos nem execução de código no parser/instalador.

Um módulo WebAssembly original/sintético foi carregado pelo loader oficial: três
propriedades aplicadas e persistidas em projeto reaberto; três casos de renderização
e 12 amostras conferidas. A extensão foi necessária porque o catálogo fixado não
contém renderers dos principais plugins. É infraestrutura para implementações próprias,
não equivalência de Deep Glow/Optical Flares/Sapphire. Veja [ADR 007](decisions/007-native-plugin-catalogs.md).

A cobertura real permanece **75 PARTIAL/69 UNSUPPORTED, 1370 parâmetros e 17 chaves**.
Há 32 mapas builtin; nenhum preset completo ou nova equivalência visual Adobe validada.

## Expansão 0.9: renderer próprio aproximado de glow

Um módulo WASM original, sem dependências, implementa bloom multiescala e 13 controles
com mapa PEDG opcional. Os IDs/tipos foram comprovados em 23 snapshots reais. A API
não fornece espaço de cor para Auto Detect Gamma; outros controles e o algoritmo
proprietário continuam perdas. `Mapping.limitations` força PARTIAL e recusa strict
mesmo com todos os controles aceitos. Não é declarada equivalência Deep Glow.
[Uso](glow-extension.md), [algoritmo/limites/evidência](decisions/008-approximate-glow-renderer.md).

Os 23 componentes reais preservaram 299 controles, verificados após salvar/reabrir.
Com extensão instalada: **80 PARTIAL/64 UNSUPPORTED, 1669 parâmetros/17 chaves**;
sem ela: 75/69, 1370/17. Há 32 mapas builtin e um opcional. Nenhum preset completo.
Os 144 hashes de entrada continuam iguais. Animação de Radius é sintética separada;
as 50 outras ocorrências PEDG ainda não recebem um tipo de origem adivinhado.

## Expansão 0.10: propriedades selecionadas e contexto de animação

2648 tipos de origem são extraídos de todos os descriptors reais parT/tdb4,
independentemente de mapas, excluindo conflitos e IDs derivados. Isso ampliou a
decodificação dos grupos selecionados; tipos conhecidos sem renderer continuam
sem conversão. [ADR 009](decisions/009-source-profiles-and-selected-glow.md).

Para a extensão Glow, mais 18 grupos preservaram 49 controles e 93 keyframes.
31 lados Bezier e 150 amostras intermediárias passaram pela engine e por reabertura
do projeto. Os destinos começaram inativos: a integração agora abre a composição
alvo antes de selecionar chaves, como exige a implementação oficial da API.
Estado enabled, UIDs, contagem e controles não selecionados foram preservados.

Com Glow: **92 PARTIAL/52 UNSUPPORTED, 1718 controles/110 chaves**, zero SUCCESS.
Builtin permanece **75/69, 1370/17**. O renderer é o mesmo módulo original da 0.9;
a aproximação visual e os recursos ausentes continuam perdas. Suportar todos os
efeitos ainda exige renderers/mapas adicionais e evidência de fidelidade.

## Expansão 0.11: renderer original para S_Shake

A extensão opcional Shake preserva 43 controles de translação, zoom, rotação,
ruído/ondas, estilos, canais, wrapping e blur. IDs/tipos/menus foram comprovados
em 19 snapshots reais. O renderer é original e aproximado; não se declara
equivalência Sapphire. [ADR 010](decisions/010-approximate-shake-renderer.md).

Com Glow e Shake, os 144 arquivos geram **101 PARTIAL/43 UNSUPPORTED**,
2672 controles/343 chaves, zero SUCCESS. Shake contribui 954 controles/233 chaves
exportadas. 18 componentes criados e 13 selecionados preservaram 911 controles
e 229 chaves após reabertura. Um componente criado foi recusado antes de alterar
propriedades: suas quatro chaves exigiriam uma grade que excede as taxas nativas
permitidas, e o adaptador não desloca os tempos.

A aplicação selecionada preservou estado, índice, UID e controles restantes em
destinos inicialmente inativos. A validação de pixels/time do WASM passou em
17 casos sintéticos, incluindo Full HD com oito amostras e RGB separado (~132 s).
O modo CPU/WASM permanece lento; máscaras/Mocha/crop e espaço/algoritmo
proprietário não foram reproduzidos.

## Expansão 0.11.1: cenas Optical Flares

Um leitor estrutural original OFP v3 decodifica **38 blocos, 602 objetos e
39665 campos**, com reconstrução exata dos bytes. **Nove cenas** ficam
associadas a Options em snapshots estáticos; **29 blocos** sem associação
comprovada permanecem no diagnóstico, incluindo estados múltiplos sem seleção
arbitrária. Campos/objetos/bytes são preservados, sem derivar controles exportáveis.
[Uso](ofp-scenes.md), [evidência e limites](decisions/011-ofp-structural-scenes.md).

Optical Flares ainda não tem renderer nem mapa. Sua leitura não amplia a
cobertura de conversão: builtin 75/69, 1370 controles/17 chaves; com Glow e
Shake 101/43, 2672/343. Nenhum preset completo. Associação de estados
selecionados, semântica dos objetos/texturas, transporte e renderização
continuam trabalho necessário para a meta de suporte universal.

## Expansão 0.12: biblioteca Flare local

Nove snapshots associados a Options contêm seis cenas distintas. A biblioteca
privada preserva seus bytes/hash exatos e usa um renderer procedural original
aproximado. Vinte e um grupos selecionados preservam a cena existente. Trinta
componentes/219 controles/141 chaves foram persistidos na Session nativa; textura,
3D e vários controles continuam perdas. Com Glow/Shake/Flare: 111 PARTIAL/33
UNSUPPORTED, 2891 controles/484 chaves. [ADR 012](decisions/012-local-flare-library.md).

## Expansão 0.13: estiramento cumulativo

A extensão Stretch transfere até 20 controles pixel_stretch para um renderer
original de scanlines, cobertura subpixel, direção, curvas/canais, distribuição,
phase/sync, shading e bordas. Oito snapshots reais em dois perfis de versão
preservaram 145 controles estáticos na engine e reabertura. Intensity Source
permanece opaco; a API v1 não fornece outra camada. Toda conversão continua parcial.
A animação selecionada é verificada somente com fixture sintética separada.

Com Glow/Shake/Flare/Stretch: 117 PARTIAL/27 UNSUPPORTED, 3036 controles/484 chaves,
zero SUCCESS. Builtin permanece 75/69, 1370/17. [Uso](stretch-extension.md),
[ADR 013](decisions/013-approximate-stretch-renderer.md). O objetivo universal mantém
máscaras, animações/recursos restantes, FilmCraft e fidelidade visual no escopo.

## Expansão 0.14: paleta e difusão de erro

Diffusion transfere 17 controles omino_diffusion para renderer original aproximado.
Quatro componentes/68 propriedades estáticas passaram na Session e na reabertura.
Stamps/debug, calibração/fase/alpha/HDR e fidelidade visual permanecem perdas.
Com Glow, Shake, biblioteca Flare, Stretch e Diffusion: 119 PARTIAL/25 UNSUPPORTED,
3104 propriedades/484 chaves, zero SUCCESS. S_DissolveShake permanece sem mapa por
falta de segunda entrada/limites de camada e Background opaco.
[Uso](diffusion-extension.md), [ADR 014](decisions/014-approximate-diffusion-renderer.md).
O objetivo de todos os efeitos continua em andamento.

## Expansão 0.14.1: estrutura da malha

Mesh Warp agora preserva 64 registros de dez float32 no payload de instância,
com roundtrip dos dois blobs reais e diagnóstico explícito de geometria ainda
sem tradução. Não há mapa e as contagens permanecem 119 PARTIAL/25 UNSUPPORTED
com extensões, zero SUCCESS. A pesquisa OLM mostrou pacote Apache 2.0 com
binários/manuais, sem fonte; não se substituiu pelo blur nativo comum.
[ADR 015](decisions/015-mesh-structural-records.md).

## Expansão 0.15.0: Premiere CS6

35 mapas builtin: 30 FFX e cinco Premiere. Três novos mapas parciais:
Geometry legado (nove controles), Channel Blur (cinco), Mosaic (dois).
Leitura de slider inteiro control type 1 com rejeição de frações/não finitos.
Pack público de dez presets/21 efeitos: quatro saídas nativas, cinco
componentes/26 propriedades estáticas, zero chaves preservadas. Importação
FilmCraft com readback completo; nenhum efeito visual comparado com Adobe.
Obturação, Dimensions não rotulado e Sharp Colors ignorado pelo renderer
são perdas permanentes, inclusive strict. [ADR 016](decisions/016-premiere-cs6-legacy.md).
Cobertura dos 144 FFX privados permanece 75/69 builtin, 119/25 com extensões;
nenhum SUCCESS. O objetivo de suporte universal continua em andamento.

## Expansão 0.15.1: Continuous Bezier em FFX

Dois streams reais com temporalContinuous=0x0008 possuem seus handles
lidos sem equalizar ou zerar velocidades. S_Shake recupera uma propriedade
e duas chaves; S_DissolveShake permanece sem renderer/mapa. Vínculo de edição
não reproduzido é perda explícita; strict não publica o preset parcial.
Auto/Roving e continuidade interior conflitante seguem recusados.

Com todas as extensões: 119 PARTIAL/25 UNSUPPORTED, 3105 propriedades/486 chaves,
zero SUCCESS. Sem opcionais, 75/69 e 1370/17. Catálogo builtin permanece 35 mapas.
Os 144 hashes originais foram reconferidos. [ADR 017](decisions/017-continuous-bezier-endpoints.md).

## Expansão 0.16.0: Modulation

Extensão original opcional de 12 controles com modulação/demodulação FM em
cinza. Dois snapshots: 24 propriedades/seis chaves Linear, persistência na
Session e 12 samples intermediários verificados após reabrir. Renderer passou
em 22 casos, incluindo dois conjuntos reais de controles sobre pixels originais
e Full HD. Calibração, filtros, alpha/HDR/gama e algoritmo continuam perdas.

Com Glow/Shake/biblioteca Flare local/Stretch/Diffusion/Modulation:
120 PARTIAL/24 UNSUPPORTED, 3129 propriedades/492 chaves, nenhum SUCCESS.
Builtin continua 35 mapas, 75/69 e 1370/17; os 144 hashes originais permanecem
iguais. [Uso](modulation-extension.md), [ADR 018](decisions/018-approximate-modulation-renderer.md).
Suporte universal e fidelidade visual continuam em andamento.

## Expansão 0.17.0: Glint

Extensão original de raios exponenciais nos quatro eixos com ganho/tamanho
por canal, cores, threshold, blur e composição própria. Dois snapshots S_Glint
exportam 50 controles/12 chaves Linear, confirmados na Session e após reabrir;
15 samples intermediários independentes passaram. Dependências de Background,
Matte e Mocha, limites externos do quadro e fidelidade visual continuam perdas.
[Uso](glint-extension.md), [ADR 019](decisions/019-approximate-glint-renderer.md).

Com todas as extensões: 121 PARTIAL/23 UNSUPPORTED, 3179 propriedades/504 chaves,
zero SUCCESS. Builtin continua 35 mapas, 75/69 e 1370/17. Os 144 hashes originais
permanecem iguais. O objetivo universal continua em andamento.

## Expansão 0.18.0: Pixel Sort

Extensão original de ordenação RGBA, com padrões Linear/Radial/Circular,
dez métricas, threshold, seed fracionário e reinícios determinísticos.
Um snapshot real Linear: 24 propriedades estáticas, valores/centros/seed
conferidos na Session e após reabrir. Outros padrões/animação têm somente
evidência sintética; Matte/Mocha/canvas/calibração/fidelidade continuam perdas.
48 casos WASM passaram, incluindo controles reais sobre pixels originais e
Full HD a 37° (~41,4 s). [Uso](pixelsort-extension.md),
[ADR 020](decisions/020-approximate-pixelsort-renderer.md).

Com todas as extensões: 122 PARTIAL/22 UNSUPPORTED, 3203 propriedades/504 chaves,
zero SUCCESS. Builtin permanece 35 mapas, 75/69 e 1370/17. Os 144 hashes
originais foram reconferidos. Suporte universal continua em andamento.


## Expansão 0.19.0: Flicker

Extensão original de modulação temporal RGB por ruído suave/onda independente,
com 14 controles S_Flicker e seed fracionário. Snapshot completo: 14 valores;
grupo existente: três propriedades/três chaves isoladas. Ambos persistiram
após salvar/reabrir na engine; UID/posição/enabled e controle não selecionado
foram preservados. 31 casos WASM; calibração, PRNG e fidelidade continuam perdas.
[Uso](flicker-extension.md), [ADR 021](decisions/021-approximate-flicker-renderer.md).

Com todas as extensões: 122 PARTIAL/22 UNSUPPORTED, 3220 propriedades/507 chaves,
zero SUCCESS. Os dois arquivos já tinham outros componentes convertíveis:
a melhoria preserva mais efeitos internos, sem alterar seus estados. Builtin
permanece 35 mapas, 75/69 e 1370/17. Os 144 hashes originais foram reconferidos.
Suporte universal continua em andamento.


## Expansão 0.20.0: Median

Extensão opcional original para dez controles BCC3Median, janela retangular
orientada, quatro modos/nove canais e raios fracionários. Três snapshots
estáticos transferiram 30 valores; os componentes persistiram após reabrir
na Session com o módulo final. Mode/Channel seguem os menus parT reais.
Calibração, amostragem de até 36 taps, cor/alpha e máscaras/composição
continuam perdas permanentes. Não houve comparação visual Adobe.
[Uso](median-extension.md), [ADR 022](decisions/022-approximate-median-renderer.md).

Com todas as extensões e Flare local: 123 PARTIAL/21 UNSUPPORTED,
3250 propriedades/507 chaves, nenhum SUCCESS. Median permite um arquivo
parcial adicional e preserva mais controles em outro já parcialmente convertido.
Builtin permanece 35 mapas, 75/69 e 1370/17; os 144 hashes originais foram
conferidos. 462 testes gerais/23 reais opt-in, Ruff e Mypy passaram;
15 testes Rust e 41 casos WASM passaram. Suporte universal continua em andamento.


## Expansão 0.21.0: Directional Blur

Extensão original para 12 controles BCC3Directional Blur. Três componentes
conservaram 36 valores estáticos após salvar/reabrir na Session com o módulo
final otimizado. Menus parT comprovam nove canais e 27 Apply Modes; Apply Mix
com flags 32 é funcional. Kernels, mistura e calibração são próprios. A opção
Avoid Clipping tem perda explícita de expansão do canvas; máscaras/audio
continuam não traduzidos. [Uso](directional-extension.md),
[ADR 023](decisions/023-approximate-directional-renderer.md).

Com todos os opcionais e Flare local: 124 PARTIAL/20 UNSUPPORTED,
3286 propriedades/507 chaves, zero SUCCESS. Um arquivo adicional passa a
parcial, e dois já parciais preservam mais controles. Builtin permanece
35 mapas, 75/69 e 1370/17; os 144 hashes originais foram conferidos.
478 testes gerais/24 reais opt-in, Ruff/Mypy, 13 testes Rust e 86 casos WASM
passaram. Full HD não uniforme ~96 s: CPU/WASM permanece lento para preview.

A revisão de DissolveShake/MathOps confirmou segunda imagem/host ausentes
no ABI v1. Não se presume Background=None por blobs opacos nem se troca
uma entrada não resolvida por preto para declarar compatibilidade.
Integração de recursos, expansão do canvas e demais efeitos continuam
necessárias. O objetivo universal não foi atingido.


## Sharpen — 0.22.0

Uma instância S_Sharpen preservou 15 controles estáticos na Session oficial,
com aplicação, salvamento e reabertura. Best/Normal são reais; alternativas
e curvas têm apenas dados sintéticos. O renderer multibanda/unsharp é original
aproximado, com 11 testes Rust e referência de pixels independente no loader.
Show Small Detail Size é widget da origem; Matte/Mocha continuam opacos.

Com os 11 opcionais e Flare local: 124 PARTIAL/20 UNSUPPORTED,
3301 propriedades/507 chaves. Os 144 hashes originais foram reconferidos.
O novo efeito pertence a um arquivo já parcial: a contagem de arquivos não muda.
Equivalência visual, múltiplas imagens/host, recursos, máscaras, geometria e
canvas continuam necessários para o objetivo universal.
[Uso](sharpen-extension.md), [ADR 024](decisions/024-approximate-sharpen-renderer.md).


## Referências Layer de destino — 0.23.0

Planos v4 agora transportam Layer simbólico estático; CLI/API recebem bindings
explícitos. O preflight resolve recursos da mesma composição e recusa self,
valores/seletores inválidos e referências faltantes sem criar efeitos.
71 parâmetros em 42 efeitos nativos foram persistidos/reabertos com dados
próprios. Três casos do EffectHost oficial verificam pixels de duas imagens.
Nenhum desses testes é apresentado como conversão Adobe real.

Cobertura FFX permanece 124 PARTIAL/20 UNSUPPORTED, 3301 propriedades/507
chaves com todos os opcionais; builtin 75/69 e 1370/17. Referências de origem,
renderers multientrada WASM, máscaras/audio/geometria e fidelidade continuam
pendentes para o objetivo universal. [Uso](layer-resources.md),
[ADR 025](decisions/025-native-layer-bindings.md).

## Colorize — 0.24.0

Quatro instâncias BCC3Colorize receberam 23 controles cada na extensão original
aproximada. São 92 valores estáticos conferidos na Session oficial após
salvar/reabrir. Tipos/menus reais Luma/RGB/loop Off; outros modos e curvas
são sintéticos. 11 testes Rust/Clippy e 60 casos WASM com referência colorsys
passaram. HD não uniforme ~5,6 s; UHD ~22,2 s, sem ampliar budgets do loader.

As diferenças de gradiente, calibração, espaços de cor/alpha permanecem perdas.
PixelChooser/Mocha/tracking/Compare e camadas/path continuam pendentes; Input
PixelChooser e criação sem todos os 23 controles são recusados. Fidelidade e
objetivo universal continuam pendentes. [Uso](colorize-extension.md),
[ADR 027](decisions/027-approximate-colorize-renderer.md).

## Host multientrada — desenvolvimento

Um patch experimental sobre cópia do EffectCraft preserva API 1 e transporta
até quatro imagens auxiliares, UID exato e geometria. Foram verificados 21
testes Rust e um percurso Session/render full/half/save/reopen com imagens
originais, além do carregamento dos 12 módulos legados. Esta infraestrutura
não acrescenta mapas S_DissolveShake/S_MathOps: referências de origem continuam
opacas, renderers ainda ausentes e manifestos API 2 recusados pelo Bridge.
Próxima dependência é o suporte explícito de capacidades/planos de recursos
na integração, sem interpretar blobs FFX como None. Contadores e objetivo
universal permanecem pendentes. [Contrato](experimental-multi-input-host.md).

## Integração API 2 — 0.25.0

A etapa seguinte está implementada: manifestos API 2/revisão 1, planos v4
com Layer explícito e preflight de capacidade/versão/defaults. O protocolo
do Bridge foi conferido numa Session própria com mistura estática/animada,
seis samples full/half, save/reopen e unbind preservando animação não selecionada.
Os 602 testes gerais passaram; fingerprints API 1 permanecem compatíveis.
Não se criou mapa nem decoder Layer de origem. S_DissolveShake/S_MathOps ainda
exigem vínculos comprovados e renderers; corpus e objetivo universal seguem
pendentes. [ADR 029](decisions/029-api2-layer-plan-integration.md).

## MathOps — 0.26.0

Nova extensão opcional original aproximada com 17 operações, Source B e máscara
pelo host experimental revisão 1. Quatro instâncias comprovam 15 controles
estáticos cada, incluindo A Darks=-0,04 e Blur Mask=12. Referências kind 0
continuam opacas: duas substituições manuais por instância exigem hash/índice/ID.
Sem essas escolhas, o corpus automático permanece 124 PARTIAL/20 UNSUPPORTED,
3393 controles/507 chaves; não há promoção por defaults. Path/Mocha/calibração,
cor/alpha/geometria e fidelidade continuam perdas. [Detalhes](mathops-extension.md).

## S_DissolveShake — 0.27.0

40 controles + Background manual por criação; cinco grupos selecionados
passam a converter 48 controles/54 chaves em instâncias existentes. Quatro
snapshots exigem vínculos explícitos; 13 chaves preservadas nessas criações.
Corpus automático: 129 PARTIAL/15 UNSUPPORTED, 3441 controles/561 chaves.
144 hashes e 1341 avisos relevantes preservados. Renderer aproximado opt-in
API 3/revisão 2; host oficial não ganha suporte automaticamente. Suporte
universal e equivalência Adobe continuam sem comprovação.
[Uso e limites](dissolveshake-extension.md).


## Heatwave — 0.28.0

Universe_Distort_Heatwave ganha 24 controles e Mask Layer manual por renderer
original aproximado API 2. Todos os controles/tamanho/recurso são exigidos;
menus e pontos vêm de um snapshot real. Corpus automático permanece 129/15
sem escolhas manuais: o snapshot não passa a converter implicitamente seu
recurso opaco. 144 hashes e 1341 avisos relevantes preservados. Suporte
universal permanece aberto. [Uso](heatwave-extension.md).


## Signal — 0.29.0

Dois snapshots ADBE Signal passam de UNSUPPORTED a PARTIAL com a extensão
opcional original aproximada. Preserva 34 controles cada, sem recurso manual.
Destruction button permanece perda por ação desconhecida. Corpus automático
com todas as extensões: 131 PARTIAL/13 UNSUPPORTED, 3509 controles/561 chaves;
144 hashes e 1341 avisos relevantes mantidos. Engine confirma 68 valores
persistidos/reabertos sobre imagens originais; não certifica equivalência.
Suporte universal permanece em andamento. [Uso](signal-extension.md).


## Imagens temporais — 0.30.0

API 4/revisão 3 do host experimental acrescenta imagens da própria camada em
outros tempos pelo callback nativo e controles declarativos limitados.
A Session real verificou 23 samples de pixels originais. Nenhum mapa Adobe
novo: 131 PARTIAL/13 UNSUPPORTED permanecem. APIs anteriores são preservadas;
o EffectCraft oficial exige preparação separada da cópia experimental.
[Contrato, evidência e limites](temporal-input-host.md).


## Geometric Filter — 0.31.0

Extensão opcional original aproximada API 4: 21 controles brutos sustentados
por um snapshot local, seis formas, busca por cor, recursão e pixels retidos.
Seletor de estilo e hidden permanecem perdas; sempre PARTIAL. Session real
confirma controles persistidos/reabertos sobre imagens originais; nenhum
algoritmo/código/asset proprietário reutilizado ou equivalência presumida.
Corpus: 132 PARTIAL/12 UNSUPPORTED, 3530 controles/561 chaves; objetivo universal
continua pendente.
[Instalação, evidência e limites](geometric-extension.md).


## Pixel Encoder — 0.32.0

16 controles de um snapshot real recebem renderer original aproximado
API 2: dez padrões, glifos de segmentos, cores e caos. Sliders brutos,
menus/ARGB comprovados; calibração e fidelidade são perdas. Session real
comprova controle persistido/reaberto sobre pixels próprios. Sem material
proprietário reutilizado. Corpus: 132 PARTIAL/12 UNSUPPORTED, 3546 controles/
561 chaves. Objetivo universal permanece aberto.
[Instalação, evidência e limites](pixelencoder-extension.md).


## S_Hotspots — 0.33.0

Nove controles de processamento reais recebem renderer original aproximado
API 2 e uma máscara substituta explícita, fixada ao hash/índice/ID. None
não é inferido de dados opacos. Mocha/path/combinação/calibração permanecem
perdas; strict sem saída parcial. Sem vínculos manuais o corpus mantém
132 PARTIAL/12 UNSUPPORTED, 3546 controles/561 chaves. Suporte universal
continua pendente.
[Evidência, uso e limites](hotspots-extension.md).


## HitFilm Hotspots — 0.34.0

Dois snapshots reais comprovam cinco controles visíveis; renderer original
API 2 separa fill de cor abaixo do limiar de extração Sapphire. Dez valores
reais persistidos/reabertos sobre pixels próprios; sliders brutos, hidden e
calibração continuam perdas. Sempre PARTIAL; strict não publica parcial.
Sem parser ou pacote privado alterado, sem código/SDK/assets proprietários.
[Evidência, uso e limites](hfhotspots-extension.md).


## OLM Directional Blur — 0.35.0

14 controles reais e uma entrada de transporte recebem renderer anisotrópico
original API 2. Manual OLM comprova Noise Layer somente no modo Layer;
Smooth/Block estático íntegro autoriza entrada inativa, preservando vínculo
opaco e avisos. Layer continua exigindo escolha manual. Fades/tails/grupos/
ruído/calibração próprios, sempre PARTIAL; strict não publica parcial.
Manual consultado de pacote público licenciado, sem código-fonte disponível;
plugins compilados não executados/distribuídos, parser e presets intactos.
[Evidência, uso e limites](olmdirectional-extension.md).


## Godrays — 0.36.0

25 controles reais PEGR recebem renderer original aproximado API 2 radial/spin.
Sliders/Position brutos, graus e menus comprovados; Quality separador recusado,
Buffer Expansion neutro. Point recuperado do transporte escalado do host.
Dez casos nativos, 25 valores persistidos/reabertos, pixels próprios full/half.
Corpus: 3596 controles/561 chaves, 132 PARTIAL/12 UNSUPPORTED; objetivo universal
continua aberto. [Evidência, instalação e limites](godrays-extension.md).
