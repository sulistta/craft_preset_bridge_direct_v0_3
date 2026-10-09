# Pesquisa e escopo do primeiro incremento

Em 07/10/2026 foram clonados e lidos os seis repositórios indicados no plano.
Versões imutáveis e licenças: [references.json](references.json),
[avisos](../THIRD_PARTY_NOTICES.md). Foram examinados os documentos de arquitetura,
protocolos, estruturas de presets, parâmetros e comandos, implementações e testes.
O checkout de py-aep não completou os objetos LFS (git-lfs ausente); a documentação
textual e os arquivos Git não LFS estavam disponíveis. Não se atribui validação ao corpus LFS.

## FilmCraft

`crates/engine/src/presets.rs` define `filmcraft.effect-presets`, versão 1.
O documento contém presets com name, description, keyframes (Scale/AnchorToIn/AnchorToOut),
source_duration (inteiro, 254016000000 ticks/s), source_size e effects.
EffectInstance usa effect, enabled, params e masks. Param.value é enum serde
externamente marcado (`{"Float": 90}`, `{"Vec2":{"x":960,"y":540}}`, Bool, Choice, Color).
Keyframe contém time, value, interp e influências. A importação também verifica IDs de efeitos.
Parâmetros Point são armazenados em pixels e redimensionados pelo destino.

## Premiere

PremiereData é um grafo XML ObjectID/ObjectRef. FilterPresetItem agrupa FilterPresets;
TreeItemBase liga nomes a esses grupos. FilterPreset aponta a Component, que referencia Params.
As três amostras notoow confirmam `AE.ADBE Gaussian Blur 2` e `AE.ADBE Geometry2`,
valores StartKeyframe que podem divergir de CurrentValue e pontos normalizados 0.5:0.5.
O sentinel negativo de StartKeyframe não é tempo de animação. Máscaras Base64 e
curvas XML não documentadas são preservadas como diagnóstico, sem interpretação geométrica especulativa.
Type 0/1/2 é tratado como Scale/AnchorToIn/AnchorToOut, hipótese isolada e sinalizada
em animações até existir fixture rotulada para os três modos. Um override explícito é oferecido.

## EffectCraft

`docs/control-protocol.md`: TCP 127.0.0.1:9877, JSON por linha, id/ok/result.
`engine.execute` envolve command/params. `effect.apply` retorna `effects` (UIDs) e `paths`;
usar esses paths, nunca presumir #1. Propriedades usam prop.set/prop.addKey.
keys.select + keys.interpolation configuram interpolações e keys.setEase configura velocidades
e influências por componente (em % na API). Os tempos de prop.addKey são da camada e a engine os arredonda para frames da composição;
keys.select e keys.setEase usam tempo da camada. O adaptador verifica start_time/stretch
e converte apenas em camadas com tempo simples. file.saveAs salva .ecproj pela engine.
Não foi encontrado formato de preset externo oficial; a saída é um plano próprio.

## FFX: evidência e divergências

FFX Compatibility Tool: RIFX big-endian, form FaFX, LIST besc, caminhos tdsp/tdsi,
sentinela de fim de caminho; pares tdsp e sspc por posição, não por nome.
parT contém tdmn/pard/pdnm; pard +12 indica tipo e +4 flags.
tdmn antes de tdgp pertence ao grupo; antes de tdbs, à propriedade.
Repetições de efeitos podem omitir parT e reaproveitar a primeira descrição.
Presets sem sspc contêm caminhos para propriedades e árvores tdgp/tdbs.
Na 0.4, IDs/tipos comprovados em parT reais são registrados em um snapshot de origem
para decodificar esses streams sem adivinhar tipos. Caminhos simples são agrupados por
instância e vinculados a efeitos existentes; grupos complexos e estruturas mistas ainda
sem associação comprovada continuam perdas. Veja ADR 004.

**Divergência:** FFX Compatibility Tool interpreta lhd3[3] como dimensões em certos
streams intercalados; py-aep documenta esse campo como número de blocos alocados.
Não se assume um significado universal. O perfil normal exige count × record_size
igual ao tamanho de ldat e dimensões/flags de tdb4. O perfil intercalado só é aceito
se a igualdade com dimensões e os tempos iguais por componente forem verificados.
Layouts espaciais, roving e flags desconhecidas são recusados para exportação.
Tangentes nunca são arbitrariamente zeradas ou limitadas para produzir uma curva plausível.

`py-aep/docs/file_format.md` confirma tdb4 magic DB99, dimensões +2, flags +4,
base temporal +12, expressão +120, animação +68. Essa base tem precedência sobre beso.
Nos presets do usuário há 20480, 23976 e outras bases; não há constante universal 30720.
dot-aep descreve outro layout de lhd3 (offsets u16), incompatível com os FFX examinados;
foi estudado, mas seu leitor de keyframes não foi reutilizado.

## Arquitetura

Python 3.11+, modelos Pydantic serializáveis, parsers próprios limitados, mapas JSON
declarativos, exportadores e adaptador local desacoplados. defusedxml bloqueia entidades.
PySide6 opcional executa análise/conversão em worker e permite cancelamento entre arquivos.
Relatórios preservam hashes, offsets, amostras limitadas de bytes e perdas por propriedade.
As validações sintéticas, com arquivos reais e com engines são registradas separadamente.

## Optical Flares / OFP

Em 08/10/2026, pesquisa pública NuajFramework/LensFlare.cs fixada em
3ae072166486e5df6a575062bd0da1afeb50a471 foi consultada para o envelope OFP v3;
nenhum código/asset foi reutilizado. O leitor original foi conferido nos 38 blobs
do corpus autorizado, com roundtrip de bytes exato (602 objetos/39665 campos).
Nove associações estáticas a Options foram verificadas; 29 blocos permanecem
sem associação e disponíveis como diagnóstico. A semântica visual dos objetos,
texturas e controles ainda exige renderer/validação próprios.
[ADR 011](decisions/011-ofp-structural-scenes.md), [inspeção](ofp-scenes.md).

Na 0.12, um renderer original aproximado e biblioteca local usam apenas os nove
snapshots associados (seis cenas distintas). Dez controles globais são sustentados
pelos tipos/menus parT/tdb4 reais; fórmulas/PRNG/calibração dos objetos são próprios,
com perdas permanentes no relatório. Os 29 blocos sem associação continuam diagnóstico.
Não foram incorporados código nem assets Nuaj/Adobe. [ADR 012](decisions/012-local-flare-library.md).

## Pixel Stretch

Em 08/10/2026, a [página oficial Satori/aescripts](https://aescripts.com/pixel-stretch/)
foi consultada para a descrição funcional do estiramento cumulativo, canais,
versões e dependência de intensidade. Oito snapshots locais comprovam IDs/tipos/
menus em dois perfis parT/tdb4, com 20 ou 17 controles mapeados. Não foram baixados
SDK, binário, manual distribuído com o plugin ou assets proprietários. A implementação
de reconstrução/calibração do Bridge é original e aproximada. [ADR 013](decisions/013-approximate-stretch-renderer.md).

## Omino Diffusion e Sapphire DissolveShake

Em 08/10/2026 foram consultadas as páginas oficiais Omino e Boris FX. Quatro
snapshots Omino comprovam 17 controles estáticos, sem disponibilizar algoritmo
ou unidade dos sliders. Código Omino é oferecido mediante acordo e não foi
obtido/reutilizado. Renderer MIT original aproximado, com limites/calibração
próprios: [ADR 014](decisions/014-approximate-diffusion-renderer.md).
S_DissolveShake exige duas imagens e limites da camada para Auto Trans; o ABI v1
oferece uma imagem, e Background local continua opaco. Não se criou mapa falso.

## Mesh Warp estrutural

Na 0.14.1, o perfil observado 2580 bytes/64 registros de dez float32 possui
leitor estrutural com roundtrip dos blobs real default/instância. A ordem dos
campos é preservada sem inventar unidades ou significado das tangentes.
O destino bilinear não representa esses controles diretamente; nenhum mapa
foi criado. A propriedade continua unknown e a perda visual explícita.
[ADR 015](decisions/015-mesh-structural-records.md).

## Premiere CS6: expansão 0.15.0

Referência pública PPCS6-Pack-DM-001 fixada no commit
498aa583f45af4316eb4ab54403ddb6b30af3601 comprova sliders inteiros e três
perfis adicionais (Geometry legado, Channel Blur, Mosaic). Nenhum arquivo
externo foi incorporado à distribuição. Auditoria do renderer identifica
perdas de obturação, menu não rotulado e Sharp Colors não implementado.
IDs, limites, hash e verificação: [ADR 016](decisions/016-premiere-cs6-legacy.md).

## Continuous Bezier — 0.15.1

Dois streams reais normais têm temporalContinuous=0x0008 nos endpoints.
Leitor conserva velocidades/influências explícitas; não aplica a regra de
edição como equalização arbitrária. Interior divergente continua recusado.
S_Shake recupera duas chaves, verificadas na engine com samples e projeto
reaberto. Vínculo de edição é perda; Auto/Roving permanecem recusados.
[ADR 017](decisions/017-continuous-bezier-endpoints.md).

## Modulation — 0.16.0

A [página oficial aescripts](https://aescripts.com/modulation/) foi consultada
em 08/10/2026 para a descrição funcional; não fornece a calibração ou fórmulas
necessárias para certificar equivalência. Dois perfis parT/tdb4 locais comprovam
12 controles do efeito com nome Modulation e ID ADBE Checkout. Renderer FM
original, limites próprios e perdas permanentes: [ADR 018](decisions/018-approximate-modulation-renderer.md).
Não foram baixados nem reutilizados código, binários, SDK ou assets proprietários.

## S_Glint — 0.17.0

Em 08/10/2026 foi consultada a [documentação oficial Boris FX](https://borisfx.com/documentation/sapphire/ae/glint/)
para a descrição funcional e dependências. Dois perfis parT/tdb4 locais comprovam
25 controles e o menu Opacity. Fórmulas, kernels e calibração da extensão são
originais, com perdas permanentes. Background/Matte/Mocha continuam opacos;
nenhum estado vazio é presumido. Não foram obtidos/reutilizados código,
binários, SDK ou assets proprietários. [ADR 019](decisions/019-approximate-glint-renderer.md).

## S_PixelSort — 0.18.0

Em 08/10/2026 foi consultada a [documentação oficial Boris FX](https://borisfx.com/documentation/sapphire/ae/pixelsort/)
para a descrição funcional e dependências. Um perfil Linear parT/tdb4 comprova
24 controles estáticos e menus, incluindo centros normalizados e seed fracionário.
Ordenação, geometria, métricas e reinícios da extensão são originais; calibração
não certificada. Radial/Circular têm testes exclusivamente sintéticos.
Matte/Mocha permanecem opacos, sem presumir ausência. Nenhum código, binário,
SDK ou asset proprietário foi obtido/reutilizado. [ADR 020](decisions/020-approximate-pixelsort-renderer.md).


## S_Flicker — 0.19.0

Em 08/10/2026 foi consultada a [documentação oficial Boris FX](https://borisfx.com/documentation/sapphire/ae/flicker/)
para a função de modulação temporal aleatória/periódica de cor. Um snapshot
parT/tdb4 comprova 14 controles kind 2, um grupo selecionado contém três chaves
isoladas. Fórmulas/PRNG/unidades de frequência e fase do renderer são próprios,
sem certificação visual ou inferência de unidades da origem. Nenhum código,
binário, SDK ou asset proprietário foi obtido/reutilizado.
[ADR 021](decisions/021-approximate-flicker-renderer.md).


## BCC3Median — 0.20.0

Em 08/10/2026 foi consultada a [documentação oficial Boris FX](https://borisfx.com/documentation/continuum/bcc-median/)
para a função de filtro de vizinhança e janela orientada. Três perfis parT/tdb4
em dois arquivos locais comprovam dez controles estáticos e a ordem dos menus.
Angle kind 3 usa graus; os outros sliders permanecem brutos, sem inferência de
unidades. O menu de origem tem precedência sobre a ordem de outra versão da
página pública. A janela quadrada nativa não traduz a geometria real 100/3
rotacionada. Renderer, redes de comparação e calibração são originais; limite
WASM motivou amostragem esparsa declarada. Compare/Compositing/Mocha/PixelChooser
permanecem perdas. Nenhum código, SDK, binário ou asset proprietário foi obtido
ou reutilizado. [ADR 022](decisions/022-approximate-median-renderer.md).


## BCC3Directional Blur — 0.21.0

Em 08/10/2026 foram consultadas a [descrição oficial Boris FX](https://borisfx.com/documentation/continuum/bcc-directional-blur/)
e a [referência de Apply Modes](https://borisfx.com/documentation/continuum/bcc-apply-modes/).
Três instâncias parT/tdb4 comprovam 12 controles estáticos, nove canais,
27 misturas e graus para Angle. Sliders mantêm os coeficientes brutos.
Kernel, distribuição, limiares e fórmulas são originais; a documentação
funcional não certifica equivalência. Apply Mix com flags 32 é funcional.
Avoid Clipping usa transparência na amostragem, mas ABI v1 mantém o canvas:
a expansão dos limites permanece perda explícita. Mocha/PixelChooser,
tracking, Compare e Beat Reactor/audio continuam opacos ou não traduzidos.
Nenhum código, SDK, binário ou asset proprietário foi obtido/reutilizado.
[ADR 023](decisions/023-approximate-directional-renderer.md).

A revisão de S_DissolveShake e S_MathOps confirmou dependências de segunda
imagem. EffectCtx nativo possui host para camadas, mas PluginFrame/ABI v1
transmite somente uma imagem e não oferece Layer como parâmetro de plugin.
Referências locais permanecem opacas; não se presume Background=None nem
se substitui a segunda imagem por preto para declarar suporte. A integração
de recursos e extensões de host continua necessária para o objetivo universal.


## S_Sharpen — 0.22.0

Em 08/10/2026 foi consultada a [documentação oficial Boris FX](https://borisfx.com/documentation/sapphire/ae/sharpen/)
para a função de sharpening e controles de detalhes/cor. Um snapshot local
comprova 15 controles estáticos e menus Quality/Opacity. Show Small Detail
Size é um widget de edição, não um overlay do renderer. Matte/path/Mocha
continuam opacos; default público None não comprova ausência no arquivo.
Filtro multibanda, boxes fracionários e calibração são originais aproximados.
Sem código, binários, SDK ou assets proprietários obtidos/reutilizados.
[ADR 024](decisions/024-approximate-sharpen-renderer.md).


## Recursos Layer nativos — 0.23.0

A revisão do código fixado confirmou 71 parâmetros Layer em 42 efeitos,
Value::Layer(u64/None), comp.info/layer.tree e prop.get.type. coerce_json
é permissivo e pode transformar strings inválidas em None: o Bridge agora
transporta referência simbólica e resolve um seletor explícito antes de escrever.
O host nativo recebe LayerPixels e recusa self/recursão; API WASM v1 continua
sem múltiplas entradas. Nenhum tipo Layer de origem foi inferido de blobs
FFX opacos e nenhum mapa foi renomeado como certificado.
[ADR 025](decisions/025-native-layer-bindings.md).

## Avisos de origem antes da recusa de mapa — 0.23.1

A inspeção de map_effect encontrou retornos antecipados que omitiam os avisos
relevantes de parâmetros no relatório, apesar de preservados no IR. A coleta
agora antecede a decisão de mapa/criação e não muta o modelo de origem.
Auditoria local recuperou 353 avisos antes omitidos em 65 instâncias sem mapa,
incluindo expressões, layouts de animação e dados estruturais Mesh Warp.
A revisão MathOps confirmou controles de entrada/saída sem correspondência
direta no Compound Arithmetic; referências FFX desconhecidas não foram
interpretadas como None. Nenhum parser/mapa novo nesta correção.
Veja [ADR 026](decisions/026-source-warnings-before-mapping.md) e
[diagnósticos](compatibility-diagnostics.md).

## BCC3Colorize — 0.24.0

As páginas oficiais Boris FX Colorize/Gradient e manual legado público foram
consultados em 08/10/2026 para a função de gradiente e os controles. Quatro
snapshots locais parT/tdb4 comprovam 23 IDs/tipos/menus estáticos. Hue kind 3
comprova graus; demais sliders mantêm coeficientes brutos. Renderer, distribuição
de knots, luma, HSL/HSV e calibração são originais aproximados, com perdas
permanentes. PixelChooser/Mocha/tracking/camadas/path/Compare permanecem perdas;
Input PixelChooser é recusado. Não se presume ausência de referência opaca.
Nenhum código, SDK, binário ou asset proprietário obtido/reutilizado.
[ADR 027](decisions/027-approximate-colorize-renderer.md).

## Transporte experimental de múltiplas imagens — desenvolvimento

Em 09/10/2026 foi revisado o percurso plugin::run_slot → WasmPlugin::render
e o acesso nativo EffectCtx::layer_param/EffectHost. O contexto disponível na
engine não atravessava o wrapper API 1. Um patch original opt-in sobre cópia
do commit fixado acrescenta método com contexto e tabela API 2, preservando
Layer como UID exato e as unidades documentadas por Buf::to_px. ABI 1 e sua
assinatura permanecem. Esta ABI 2 é experimental do Bridge, não oficial.
Nenhum decoder, mapa ou preset de origem foi alterado; referências FFX opacas
continuam desconhecidas. [ADR 028](decisions/028-experimental-multi-input-host.md).

## Integração de planos API 2 — 0.25.0

O Bridge aceita o manifesto experimental mediante revisão 1 explícita e plano
v4, preserva default null de Layer ao instalar e exige todas as entradas
de recurso na criação. O preflight confere capacidades e API individual do
plugin. Uma Session própria comprova aplicação estática/animada, pixels full/
half em 32 bpc, projeto reaberto e unbind sem substituir chaves não selecionadas.
O valor 0,5 é quantizado pelo destino em 8 bpc: não foi usado para tolerar erro
do transporte. ABI/fingerprints legados foram conferidos contra wheel 0.24.0.
Nenhum parser, tipo de origem, mapa ou renderer Adobe foi acrescentado.
[ADR 029](decisions/029-api2-layer-plan-integration.md).

## S_MathOps e substituições explícitas — 0.26.0

A documentação pública [Boris FX MathOps](https://borisfx.com/documentation/sapphire/ae/mathops/)
foi consultada em 09/10/2026 para operação, fontes e controles. Quatro snapshots
locais comprovam 15 controles estáticos/menus mais Source B/Mask kind 0 opacos.
A Darks=-0,04 e Blur Mask=12 impedem substituir o efeito apenas por Add nativo.
Vínculos manuais são fixados ao hash/posição/ID, nunca decodificação Layer/None;
strict mantém a recusa e avisos de origem continuam no relatório. Renderer
Rust original aproximado usa API 2/revisão 1, com modelos próprios documentados
para cor/alpha/geometria/blur/quantização. Nenhum código, binário, SDK ou asset
proprietário foi obtido/reutilizado. [ADR 030](decisions/030-explicit-source-resources-and-mathops.md).

## S_DissolveShake — 0.27.0

Documentação oficial Boris FX DissolveShake consultada em 09/10/2026. Nove
instâncias locais: quatro snapshots de 40 controles + Background opaco e
cinco grupos selecionados. APIs/menus/IDs comprovados; sliders mantêm dados
brutos. Host opt-in revisão 2 acrescenta tempos reais da camada via API 3
e evita cache que desconhece recursos/tempo. Renderer MIT original com
substituição manual fixada ao hash, aproximações e perdas permanentes. Não
houve alteração do parser, execução de expressão ou obtenção de material
proprietário. [ADR 031](decisions/031-approximate-dissolve-shake-and-layer-timing.md).


## Universe_Distort_Heatwave — 0.28.0

Documentação pública Maxon Heatwave consultada em 09/10/2026. Um snapshot
parT/tdb4 comprova 24 controles, pontos normalizados e menus; Shape inclui
None e Channel começa por Luminance, conforme FFX e não ordem inferida da
página atual. Mask Layer continua kind 0 opaco. Renderer MIT original API 2
usa modelos próprios, com recurso manual fixado ao hash e tamanho explícito.
Parser e arquivos privados intactos; sem material proprietário reutilizado,
expressão executada ou comparação visual. [ADR 032](decisions/032-approximate-heatwave-renderer.md).


## Cache de plugins API 1 — correção 0.28.0

Session real comprovou cache congelado em um Flicker original com wave e
controles estáticos. O método is_time_dependent reconhecia apenas efeitos
nativos. A cópia experimental agora inclui todos os plugins registrados,
permitindo que o hash existente acompanhe tempo local/start/stretch. Quinze
samples matemáticos próprios comprovam evolução temporal e reversão; não há
alteração de ABI/módulos/presets, nem do upstream oficial. [ADR 033](decisions/033-plugin-time-aware-cache.md).


## ADBE Signal — 0.29.0

Página pública [Zaebects/aescripts](https://aescripts.com/signal/) consultada
em 09/10/2026 para a função de modulação/decodificação analógica. Dois snapshots
parT/tdb4 comprovam 26 sliders kind 10 sem unidade, seis checkboxes e dois
menus. Destruction button permanece sem tradução: ação não comprovada.
Renderer MIT original API 2, matriz/portadora/filtros/ruído/calibração próprios,
sempre PARTIAL. Sem alteração de parser, execução de expressão ou material
proprietário reutilizado. [ADR 034](decisions/034-approximate-signal-renderer.md).


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
