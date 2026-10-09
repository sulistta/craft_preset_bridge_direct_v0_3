# Matriz de compatibilidade 0.36.0

Objetivo de suporte a todos os efeitos em andamento. Catálogos contêm 306 efeitos EffectCraft e 303 FilmCraft;
somente os mapas explicitamente implementados abaixo são conversões. Evidências e lacunas:
[expansão](effect-expansion.md).

| Origem / recurso | Leitura | Exportação | Fixture real | Engine real |
|---|---|---|---|---|
| Host múltiplas imagens / experimental opt-in | Sem novo decoder FFX | Manifestos API 2/revisão 1 e API 3/revisão 2, planos v4/Layer explícito e preflight; host separado | Exclusivamente dados originais sintéticos | Bridge: mistura estática/animada full/half, vínculo persistido/reaberto, unbind sem alterar chaves; 12 módulos API 1 carregados. Sem novo suporte Adobe; veja experimental-multi-input-host.md |
| ADBE Signal / extensão signal opt-in | 34 controles estáticos e menus; botão não traduzido | Renderer original API 2/revisão 1, sempre PARTIAL | Dois snapshots: 68 controles, sem animação de origem | Session experimental: matemática/pixels próprios full/half, tempo/reverso/Linear/reabertura e valores reais persistidos; sem comparação Adobe; signal-extension.md |
| Universe_Distort_Heatwave / extensão heatwave opt-in | 24 controles, pontos e menus; Mask Layer continua opaco | Renderer original API 2 com recurso manual e tamanho explícito, sempre PARTIAL | Um snapshot: 24 controles + uma substituição manual, estático | Session própria full/half, máscaras/ruído/blur/animação/reabertura, sem comparação Adobe; heatwave-extension.md |
| S_DissolveShake / extensão dissolveshake opt-in | 40 controles/menus; Background continua opaco | Renderer original API 3/revisão 2 com vínculo manual, sempre PARTIAL | Quatro snapshots: 160 controles/quatro substituições/13 chaves; cinco grupos: 48 controles/54 chaves | Session real com pixels próprios, Auto trim/stretch/reverso/full/half e projeto reaberto; sem comparação Adobe; dissolveshake-extension.md |
| S_MathOps / extensão mathops opt-in | 15 controles/menus, Layer FFX permanece desconhecido | Renderer original API 2/revisão 1; duas substituições manuais fixadas ao hash, sempre PARTIAL | Quatro snapshots: 60 controles + oito substituições; sem vínculo automático | 23 casos próprios full/half, Linear e projeto reaberto; sem comparação Adobe; mathops-extension.md |
| BCC3Colorize / extensão opcional | 23 controles, menus e cores | Renderer original aproximado; máscaras/tracking e calibração são perdas | Quatro instâncias Luma/RGB estáticas; alternativas só sintéticas | 92 valores persistidos/reabertos; 60 casos WASM de pixels próprios, sem comparação Adobe |
| Premiere Gaussian Blur 2, estático | Sim | FilmCraft blurriness/dimensions/repeat_edge | Sim, com máscaras não suportadas | Modelo/catálogo; importação conforme validation.md |
| Premiere Geometry2, estático | Sim | Parcial: 10 de 12 parâmetros, resolução explícita | Sim | Importação na Session FilmCraft; sem comparação visual |
| Premiere Geometry CS6 / Channel Blur / Mosaic | Sim, incluindo slider inteiro control type 1 | Parcial: 9 / 5 / 2 controles; perdas de obturação/menu/Sharp Colors explícitas | Pack público CS6, 10 presets/21 efeitos | Importação nativa de cinco componentes/26 parâmetros estáticos; sem render comparativo |
| Premiere Motion/Opacity e demais IDs | Diagnóstico | Planejado | Não | Não |
| XML keyframes textuais | Tempo/valor, interp desconhecida | Recusada para evitar alteração de curva | Sem fixture escalar rotulada | Somente exportador do modelo sintético |
| Máscaras XML/Base64 | Identificação + bytes limitados | Não | Sim | Não |
| FFX tdsp/sspc/parT/tdgp/tdbs | Sim | Conforme mapas | 144 privados + sample_1 | EffectCraft para subconjunto |
| FFX escalar lhd3/ldat 48 bytes | Sim, base tdb4 +12 | Linear/Hold/Bezier | Sim | Brightness animado verificado |
| FFX Continuous Bezier normal/intercalado | Lados Bezier explícitos, endpoints assimétricos e interior com velocidades iguais | Curva manual, vínculo de edição perdido e strict recusado | Dois streams reais; um com mapa S_Shake | 11 propriedades/12 chaves no grupo, quatro lados Bezier/três samples e projeto reaberto |
| FFX não espacial multidimensional 88/128 bytes | Sim | Conforme tipo e mapa | Não certificada | Não certificada |
| Perfil FFX intercalado 48 bytes | Sim, checagem estrita de tamanho/tempo | Conforme mapa | Não certificada | Não certificada |
| Layout espacial/roving/auto e single-ease desconhecido | Diagnóstico | Não | Presente no pacote | Não |
| FFX Brightness & Contrast 2 | Sim | ec.color.brightnesscontrast, 3 parâmetros | Sim | Aplicação, curvas e salvamento .ecproj |
| FFX Sharpen | Sim | ec.blur.sharpen | Sim, incluindo índices com lacunas verificados | Duas instâncias reais aplicadas |
| FFX Unsharp Mask2 | Sim | ec.blur.unsharp | Sim, estático | Quatro instâncias aplicadas na Session EffectCraft |
| FFX Geometry2 | Sim | ec.distort.transform, 12 parâmetros | Sim, estático | Conforme validação nativa |
| FFX Motion Tile | Sim | ec.stylize.motiontile, pontos exigem --size | Sim | 27 instâncias reais aplicadas |
| FFX Tint / Tritone | Sim | ec.color.tint / ec.color.tritone, cores convertidas ARGB→RGBA | Sim | Parâmetros conferidos na engine |
| FFX 4-Color Gradient | Sim | ec.generate.fourcolor, propriedades aninhadas e tabela de blend | Sim | Nove instâncias reais aplicadas |
| FFX Noise / HLS / HLS Auto | Sim | ec.noise.noise / noisehls / noisehlsauto | Sim | Aplicação real conforme expansão; um preset completo recusado por frames |
| FFX Wave Warp | Sim | ec.distort.wavewarp, opções de anti-alias sem equivalente | Sim | Aplicação real, resultado parcial |
| FFX Optics Compensation | Sim | ec.distort.opticscompensation, pontos exigem --size | Sim | Uma instância real aplicada |
| FFX Upscale / Camera-Shake Deblur | Sim | ec.distort.upscale / ec.blur.camerashakedeblur, limitações por opção/animação | Sim | Aplicação real de parâmetros preservados |
| FFX Gaussian Blur 2 / Directional Blur | Perfil de parâmetros | Experimental, aviso MAPPING_UNVERIFIED | Não | Só destino auditado / sintéticos |
| FFX Hue/Saturation | aRbp estático, Master e seis faixas | 45 ajustes, seleção de canal e Colorize; sombras UI identificadas | Sete instâncias | Sete instâncias, valores conferidos |
| FFX Levels | aRbp estático, cinco canais | 25 ajustes, seleção e clipping; opção 32bpc recusada | Três instâncias | Três instâncias, valores conferidos |
| FFX Exposure / Black & White | Sim | Parâmetros e grupos aninhados; cor ARGB→RGBA | Duas / uma instâncias | Aplicação e conferência de valores |
| FFX Invert / Box Blur | Sim | Tabela de canais com separadores / quatro parâmetros | Duas instâncias cada | Aplicação e conferência de valores |
| FFX Curves | LUTs e pontos de cinco canais estáticos | Parcial: 256 samples/canal como Text; interpolação/HDR/16–32bpc continuam perdas | 22 estáticas convertidas, duas recusadas | 110 propriedades persistidas; erro máximo nos samples 0,0246 nível de 8 bits; sem comparação visual Adobe |
| FFX CC Color Neutralizer (CS Color Neutralizer) | Sliders e seletores UI-only identificados | Parcial: Pinning/Blend com View final e pontos 0/100; RGB percentual só em perfil sintético | Duas instâncias; RGB sem unidade recusado | Quatro propriedades reais e cinco sintéticas persistidas; sem equivalência visual |
| FFX Lumetri | Parâmetros escalares/menus e switches de origem | Basic/Creative/Vignette condicionais; curvas/LUTs/wheels/HSL ainda limitados | Nove instâncias | 205 valores conferidos |
| FFX propriedades selecionadas Motion Tile/Tritone | Tipos exatos de catálogo de origem | Agrupadas por instância, vínculo a efeito existente | Cinco arquivos | Cinco grupos, 13 valores; demais parâmetros e enabled preservados |
| FFX Bool/Choice animados | Valores tipados | Hold; chave isolada Linear → Hold documentada | Motion Tile/Camera-Shake Deblur | Aplicação real; Hold entre duas chaves sintéticas conferido |
| FFX Color single-ease 152 bytes | ARGB com tangentes nulas | Linear/Hold, Bezier ainda recusado | Tritone selecionado | Chave real e sequência sintética com ponto intermediário conferidos |
| FFX Radial Blur | Sim | Amount/Center/Type; somente anti-alias High; Amount >100 e seed recusados | Duas instâncias | Cinco parâmetros conferidos e projeto reaberto |
| FFX CC Radial Blur | Sim | Tabela de tipos com separador; Scratch sem equivalente | Três instâncias, todas Scratch | Nove parâmetros conferidos; Type continua perda |
| FFX Camera Lens Blur | Sim | 15 propriedades; limiar ×255, canal Luminance/Alpha; focal somente zero estático; layer opaco | Duas instâncias | 30 parâmetros/duas chaves, salvamento/reabertura |
| FFX CC Scale Wipe | Sim | Stretch/Center/Direction; coordenadas em pixels | Uma instância | Três parâmetros conferidos e projeto reaberto; sem comparação visual |
| PEDG / Deep Glow (extensão glow opcional) | 23 snapshots completos e 18 grupos selecionados; outros caminhos ainda limitados | 13 controles para renderer próprio aproximado; sempre PARTIAL | 348 controles/93 chaves PEDG; sem comparação visual | Aplicação e projeto reaberto; pixels sintéticos pelo WASM; gama/qualidade/algoritmo continuam perdas |
| S_Shake (extensão shake opcional) | 19 snapshots e 13 grupos selecionados | 43 controles para renderer próprio aproximado; sempre PARTIAL | 955 controles/235 chaves exportados; um componente recusado na aplicação por tempo | Auditoria anterior: 31 componentes/911 controles/229 chaves; grupo Continuous atual: 11 controles/12 chaves, quatro lados Bezier/três samples e projeto reaberto; pixels/tempo sintéticos; sem comparação Adobe |
| Optical Flares / OFP v3 (biblioteca local opcional) | 38 blocos estruturais, 602 objetos/39665 campos; nove associados a Options, 29 sem associação preservados no diagnóstico | Dez controles globais e Choice por hash de cena; 12 famílias procedurais originais aproximadas, texturas omitidas; sempre PARTIAL | Seis cenas distintas; 9 snapshots +21 grupos selecionados, 219 propriedades/141 chaves exportadas; roundtrip exato nos 38 blocos | 30 componentes: 219 propriedades/141 chaves persistidas; cena existente preservada; seis cenas renderizadas, uma Full HD ~83 s; sem comparação Adobe; veja flare-library.md |
| Catálogos de plugins EffectCraft API v1 | Manifesto declarativo de pacote v2 | Plano v3 com fingerprint, preflight de versão/parâmetros/defaults | Sem novo plugin Adobe real | Módulo WASM sintético: três propriedades persistidas, 12 samples renderizados |
| pixel_stretch (extensão stretch opcional) | Oito snapshots reais em dois perfis de versão; IDs/tipos/menus comprovados | 20 controles para renderer cumulativo original aproximado; Intensity Source opaco continua perda; sempre PARTIAL | Três instâncias com 20 controles/cinco com 17; 145 propriedades estáticas, sem animação real | Oito componentes/145 controles persistidos e projeto reaberto; pixels de teste com oito conjuntos reais de controles; animação separada exclusivamente sintética; sem comparação Adobe |
| omino_diffusion (extensão diffusion opcional) | Quatro snapshots estáticos com IDs/tipos/menus/cores comprovados | 17 controles para renderer original aproximado; stamps/debug permanecem perdas; sempre PARTIAL | 68 propriedades estáticas; sem animação real | Quatro componentes/68 controles persistidos e projeto reaberto; WASM sintético e controles reais em pixels de teste; Full HD ~7,3 s; sem comparação Adobe |
| Modulation / ADBE Checkout (extensão modulation opcional) | Dois snapshots com 12 IDs/tipos/menus comprovados | Renderer FM em cinza original aproximado; calibração/filtros/alpha/HDR/gama continuam perdas; sempre PARTIAL | 24 propriedades/seis chaves Linear | Dois componentes persistidos e projeto reaberto; 12 samples intermediários, 22 casos WASM com pixels originais e Full HD ~14,6 s; sem comparação com origem |
| S_Glint (extensão glint opcional) | Dois snapshots, IDs/tipos/cores e menu Opacity comprovados | 25 controles para raios originais aproximados; Background/Matte/Mocha/quadro/fidelidade permanecem perdas; sempre PARTIAL | 50 propriedades/12 chaves Linear, uma de cor | Dois componentes persistidos e projeto reaberto; 15 samples escalares; 30 casos WASM sobre pixels originais, Full HD ~23,2 s; sem comparação Adobe |
| S_PixelSort (extensão pixelsort opcional) | Um snapshot Linear com 24 IDs/tipos/menus e centros normalizados | Ordenação original Linear/Radial/Circular; Matte/Mocha/canvas/calibração/fidelidade continuam perdas; sempre PARTIAL | 24 propriedades estáticas; outros padrões/animação só sintéticos | Um componente persistido e projeto reaberto, centros/seed exatos; 48 casos WASM, Full HD a 37° ~41,4 s; sem comparação Adobe |
| S_Flicker (extensão flicker opcional) | Um snapshot e um grupo selecionado; 14 IDs kind 2 comprovados | Modulação temporal RGB original; PRNG/calibração/cor/fidelidade permanecem perdas; sempre PARTIAL | 17 propriedades/três chaves isoladas | Criado e existente persistidos/reabertos; UID/enabled/controle não selecionado preservados; 31 casos WASM, Full HD ~2,2 s; sem comparação Adobe |
| BCC3Median (extensão median opcional) | Três snapshots, dez IDs/tipos e ordem de menus comprovados | Mediana retangular orientada original com até 36 taps/pixel; calibração/cor/máscaras/composição permanecem perdas; sempre PARTIAL | 30 propriedades estáticas; modo ARGB separado e ângulos 45°/108°/138°; demais modos/animação só sintéticos | Três componentes persistidos/reabertos; 41 casos WASM, incluindo controles reais em pixels originais; Full HD uniforme com um impulso ~55 s, sem benchmark geral ou comparação Adobe |
| BCC3Directional Blur (extensão directional opcional) | Três snapshots e 12 IDs/tipos/menus comprovados | Linha bilinear original, Thin/Spread, limiares, nove canais/27 misturas; sempre PARTIAL | 36 propriedades estáticas, Normal/RGBA, ângulos 0°/90°; outras opções/animação só sintéticas | Três componentes persistidos/reabertos; WASM sobre pixels originais e controles reais; Avoid Clipping não amplia canvas, máscaras/audio/calibração/fidelidade continuam perdas; sem comparação Adobe |
| S_Sharpen (extensão sharpen opcional) | Um snapshot e 15 IDs/tipos/menus de processamento comprovados | Best multibanda/Fast unsharp originais; luma/chroma/canais/alpha; sempre PARTIAL | 15 propriedades estáticas Best/Normal; animação e outros modos só sintéticos | Um componente persistido/reaberto; pixels próprios no loader oficial; Matte/Mocha, widget, calibração/cor/fidelidade continuam perdas; sem comparação Adobe |
| Catálogo FilmCraft completo | 303 efeitos/1426 parâmetros nativos | Cinco mapas, três novos parciais; tipos complexos ainda limitados | Catálogo extraído da biblioteca oficial | Parâmetros não animáveis recusam chaves, inclusive JSON importado |
| Parâmetros Layer nativos / planos v4 | Referências FFX continuam opacas; sem novo decoder/mapa | Referência simbólica estática, binding CLI/API e null explícito; v2/v3 aceitos | Somente dados originais sintéticos | 71 parâmetros/42 efeitos aplicados e persistidos/reabertos; unbind existente/UID/contexto/refusal; três casos EffectHost de duas imagens. Sem validação visual dos 42 efeitos ou Adobe |
| Propriedades Text / Hidden Value::Str | Tipo nativo auditado pelo default | Texto estático UTF-8 até 65536 bytes; sem NUL; curvas com gramática estrita | Curves derivadas de LUTs reais | prop.set/get e projeto; animação textual recusada |
| FFX Mesh Warp aRbp | Perfil estrutural estático: 64 registros de dez float32, ordem completa preservada | Não; tangentes/unidades/superfície sem tradução certificada | Dois blobs reais (default/instância), byte roundtrip exato de 1280 floats | Sem mapa; destino bilinear auditado, permanece UNSUPPORTED |
| FFX texto, animadores e shapes | Classificação estruturada | Não | Pacote possui propriedades sem snapshot | Não |
| Expressões / blobs privados / plugins | Preservados em diagnóstico | Nunca executados; sem equivalência presumida | Sim | Não |

Nenhum fixture sintético é apresentado como preset salvo pela Adobe.
Sem renderização comparativa, não há garantia de equivalência visual mesmo quando APIs aceitam os dados.

A correção 0.23.1 preserva os avisos de parâmetros inclusive em efeitos sem
mapa e recusas antecipadas: 353 avisos antes omitidos em 65 instâncias do corpus
local. Os status e contadores de conversão não foram promovidos. Veja
[diagnósticos de compatibilidade](compatibility-diagnostics.md).


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


## Diagnóstico agregado do corpus

O script `scripts/audit_compatibility.py` separa efeitos sem mapa, parâmetros
opacos e avisos de perda sem exportar conteúdo privado. Na configuração
auditada: 27 identificadores sem mapa em 49 dos 144 arquivos; 107 arquivos
com parâmetro desconhecido. As contagens se sobrepõem.
[Causas, medição e reprodução](compatibility-diagnosis.md).

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
