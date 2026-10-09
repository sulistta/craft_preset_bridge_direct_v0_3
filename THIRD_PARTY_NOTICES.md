# Fontes e atribuições

Pesquisa realizada em 7 de outubro de 2026. Os commits exatos estão em `docs/references.json`.

- [filmcraft](https://github.com/storytold/filmcraft/tree/a4536bcfedf588cbef9ea24df149c70bf99a037d): MIT OR Apache-2.0; avisos em `docs/licenses/`.
- [effectcraft](https://github.com/storytold/effectcraft/tree/e38a92e792c07f1c57c5dcfcab37d91932b9e2b8): MIT OR Apache-2.0; avisos em `docs/licenses/`.
- [ffx-compat](https://github.com/marbou92/FFX-Compatibility-Tool/tree/1607b7771025a4fa3b84c6ff3065ae8315d61215): MIT; avisos em `docs/licenses/`.
- [prfpset-analysis](https://github.com/notoow/premiere-pro-prfpset-analysis/tree/4cd86871577b8f692d7654c11a9960701538b195): MIT + disclaimer de pesquisa; avisos em `docs/licenses/`.
- [py-aep](https://github.com/forticheprod/py-aep/tree/edcae7abf08dc31b75c878d84b2a4e952105d842): MIT; avisos em `docs/licenses/`.
- [dot-aep](https://github.com/virtualritz/dot-aep/tree/265bee8736d9ce3f50f0de7d1b14149a03b564ff): MIT OR Apache-2.0; avisos em `docs/licenses/`.

O parser RIFX/FFX é uma implementação Python própria, informada pela pesquisa de MarBou92 (copyright 2026), py-aep/Fortiche (copyright 2023) e dot-aep. Os avisos completos são preservados. As amostras PRFPSET de notoow (copyright 2025) são usadas somente em validação opt-in, sem distribuição de presets Adobe. Nenhum código de runtime dos projetos de referência é incorporado. Os catálogos de destino são descrições de interoperabilidade derivadas das APIs públicas nos commits indicados.

A semântica do limiar e da saturação de highlights do Camera Lens Blur foi conferida na
[documentação pública Adobe de Blur & Sharpen](https://helpx.adobe.com/uk/after-effects/desktop/apply-effects-and-animation-presets/list-of-effects/blur-sharpen-effects.html).
Não foram incorporados código, texto extenso nem binários proprietários.

O pacote local `Presets-20261007T230529Z-1-001` é material fornecido pelo usuário: somente leitura, excluído de Git, wheels e builds; sem autorização presumida de redistribuição. A fixture sample_1.ffx também é lida do clone em testes opcionais, não incorporada.

Dependências: defusedxml (PSF), pydantic (MIT), jsonschema (MIT); GUI opcional PySide6/Qt (LGPLv3/GPLv3/comercial, distribuição dinâmica). Ferramentas de desenvolvimento e suas dependências não são incorporadas ao núcleo. Builds incluem os avisos das bibliotecas; redistribuidores devem atender às condições aplicáveis, inclusive LGPL do Qt.

## Renderer original Bridge Stretch

src/craft_bridge/extensions/stretch/ é código original MIT sem dependências Cargo
externas, compilado com Rust 1.98.1/wasm32-unknown-unknown. Os avisos de std e
compiler-builtins acompanham seu WASM em licenses/. A página pública Satori/aescripts
Pixel Stretch foi usada como descrição funcional; nenhum código, SDK, binário,
manual empacotado ou asset proprietário foi reutilizado. pixel_stretch identifica
somente a origem dos controles; não há afiliação nem equivalência visual certificada.

## Renderer original Bridge Flare Library

src/craft_bridge/extensions/flare/ é implementação original MIT, sem dependências
Cargo externas. Usa Rust 1.98.1/wasm32-unknown-unknown, com avisos de std e
compiler-builtins em licenses/, distribuídos junto do template WASM. O template
não contém cenas privadas. Bibliotecas geradas localmente contêm dados derivados
dos presets do usuário e não entram em wheel/sdist/desktop. Não foram reutilizados
código, assets nem presets NuajFramework/Adobe/Video Copilot. Optical Flares é
identificador de origem, sem afiliação ou equivalência visual certificada.

## Renderer original Bridge Glow

src/craft_bridge/extensions/glow/ é código original MIT do projeto, sem dependências
Rust externas. O WASM distribuído é compilado desse código. O manual v1.4.6 foi
consultado no arquivo oficial Deep Glow v1.5.7 apenas para documentação dos controles;
nenhum código, binário ou manual proprietário é distribuído. Fórmulas de blend seguem
a especificação pública W3C Compositing and Blending Level 1; implementação original.

O binário WASM inclui partes da biblioteca padrão/compiler builtins do Rust 1.98.1.
Copyright dos contribuidores Rust; dual MIT/Apache-2.0 e exceções descritas no aviso
oficial da toolchain. O aviso integral e os textos de licença da toolchain estão
incluídos em src/craft_bridge/extensions/glow/licenses/ e acompanham wheel/sdist/desktop.
A listagem oficial abrange vários alvos; não significa que todas as bibliotecas
listadas sejam vinculadas ao módulo wasm32.

Bridge Shake em src/craft_bridge/extensions/shake/ é código original MIT, sem
dependências Cargo externas. Usa o mesmo toolchain Rust 1.98.1 do Glow e inclui
seus avisos/termos em shake/licenses/. A documentação pública Boris FX foi
consultada como referência de controles; não se reutilizam SDK, binários, código,
presets, imagens ou tracking Sapphire/Mocha. S_Shake/Sapphire são identificadores
da origem, não uma declaração de implementação ou afiliação com Boris FX.

## Pesquisa de formato OFP

[NuajFramework/LensFlare.cs](https://github.com/Patapom/NuajFramework/blob/3ae072166486e5df6a575062bd0da1afeb50a471/Packages/Cirrus.Utility/Helpers/LensFlare.cs)
foi consultado como pesquisa pública de formato em 08/10/2026. Não foi
identificada licença explícita para reutilização de código. O parser OFP do
Bridge é original, com fatos do formato corroborados por blobs locais autorizados;
nenhum código, preset, textura ou outro asset Nuaj foi incluído.
A documentação pública Video Copilot foi consultada para a composição por
objetos/sprites. Optical Flares é identificador da origem; não indica afiliação
ou equivalência visual. Leitura OFP não é renderização do plugin proprietário.

## Diffusion original

src/craft_bridge/extensions/diffusion/ contém código original MIT sem dependências
Cargo externas. A descrição funcional pública Omino e os IDs/tipos de snapshots
locais orientaram a transferência de controles. Nenhum código, binário, SDK ou
asset Omino/Adobe foi incorporado; a licença thanksware do produto não foi tratada
como autorização de redistribuição de seu código. omino_diffusion identifica a
origem, sem afiliação ou equivalência visual certificada. Licenças do compilador
Rust/WASM acompanham docs/licenses. [ADR 014](docs/decisions/014-approximate-diffusion-renderer.md).

## Pesquisa Premiere CS6

[PPCS6-Pack-DM-001 de Dzénetan Massart](https://github.com/DzenetanMassart/PPCS6-Pack-DM-001/tree/498aa583f45af4316eb4ab54403ddb6b30af3601)
foi consultado como referência pública de interoperabilidade (IDs/tipos/limites).
Nenhuma licença explícita de redistribuição encontrada. Nenhum preset, título,
descrição, código ou asset do pack foi incorporado à distribuição. Teste real
exige arquivo local opt-in, com hash fixo; fixtures unitárias são originais.

## Bridge Modulation — implementação original

src/craft_bridge/extensions/modulation/ contém código MIT original sem dependências
Cargo. A descrição funcional oficial Modulation/aescripts foi consultada; não foram
obtidos/reutilizados código, binários ou assets desse plugin. IDs/menus vêm de
metadados do corpus local autorizado, que não é distribuído. Fórmulas e calibração
são próprias e aproximadas. [ADR 018](docs/decisions/018-approximate-modulation-renderer.md).
Avisos completos Rust 1.98.1/std/compiler-builtins acompanham modulation/licenses/.
A 0.16 também inclui os mesmos avisos na pasta diffusion/licenses/ nos pacotes.

## Bridge Glint — implementação original

src/craft_bridge/extensions/glint/ contém código MIT original sem dependências
Cargo. A descrição funcional oficial Boris FX/S_Glint foi consultada; não foram
obtidos/reutilizados código, binários, SDK ou assets proprietários. IDs/tipos/menus
vêm do corpus local autorizado, que não é distribuído. Kernels, calibração e
composição são próprios, aproximados. Avisos completos Rust 1.98.1/std/compiler-builtins
acompanham glint/licenses/. [ADR 019](docs/decisions/019-approximate-glint-renderer.md).

## Bridge Pixel Sort — implementação original

src/craft_bridge/extensions/pixelsort/ contém código MIT original sem dependências
Cargo. Descrição funcional Boris FX/S_PixelSort consultada, sem obter ou reutilizar
código, binários, SDK ou assets proprietários. IDs/tipos/menus vêm do corpus
local autorizado, que não é distribuído. Geometria, métricas, PRNG e calibração
são próprios, aproximados. Avisos completos Rust 1.98.1/std/compiler-builtins
acompanham pixelsort/licenses/. [ADR 020](docs/decisions/020-approximate-pixelsort-renderer.md).


## Renderer Flicker original

src/craft_bridge/extensions/flicker/ contém código MIT original, sem dependências
Rust externas. A descrição funcional Boris FX foi consultada; nenhum código,
SDK, binário ou asset do plugin foi incorporado. Fórmulas/PRNG são independentes.
Rust std/compiler-builtins do toolchain 1.98.1 fazem parte do WASM compilado;
avisos e textos completos de licenças acompanham flicker/licenses/.
[ADR 021](docs/decisions/021-approximate-flicker-renderer.md).


## Bridge Median original

src/craft_bridge/extensions/median/ contém código MIT original, sem dependências
Rust externas. scripts/generate_median_networks.py gera redes matemáticas de
comparação, sem código de plugin proprietário. A descrição pública Boris FX
foi referência funcional; nomes/IDs vêm de descriptors locais não redistribuídos.
O WASM vincula std/compiler-builtins Rust 1.98.1. Os avisos e textos completos
de licenças acompanham median/licenses/.
[ADR 022](docs/decisions/022-approximate-median-renderer.md).


## Bridge Directional Blur original

src/craft_bridge/extensions/directional/ contém código MIT original, sem
dependências Rust externas. Descrições públicas Boris FX foram referência
funcional; IDs/tipos/menus vêm de descriptors locais não redistribuídos.
Kernels e fórmulas são originais aproximados. O WASM vincula std/compiler-builtins
Rust 1.98.1; avisos e textos completos acompanham directional/licenses/.
[ADR 023](docs/decisions/023-approximate-directional-renderer.md).


## Bridge Multiband Sharpen original

src/craft_bridge/extensions/sharpen/ contém código MIT original, sem
dependências Rust externas. A página oficial Boris FX foi referência
funcional; IDs/tipos/menus vêm de descriptors locais não redistribuídos.
Kernels, qualidade, limites e fórmulas são próprios aproximados. O WASM
vincula std/compiler-builtins Rust 1.98.1; avisos e textos completos de
licenças acompanham sharpen/licenses/.
[ADR 024](docs/decisions/024-approximate-sharpen-renderer.md).

## Colorize original — 0.24.0

src/craft_bridge/extensions/colorize/ contém código MIT original. As páginas
públicas Boris FX Colorize/Gradient e manual legado foram consultadas somente
para a descrição funcional; não foram obtidos ou incorporados código, SDK,
binários, presets ou assets proprietários. O WASM usa Rust 1.98.1/std/
compiler-builtins; os avisos e licenças acompanham colorize/licenses/.
[ADR 027](docs/decisions/027-approximate-colorize-renderer.md).

## Patch experimental de host — desenvolvimento

scripts/effectcraft-multi-input/host-api2.patch altera uma cópia do EffectCraft
e38a92e792c07f1c57c5dcfcab37d91932b9e2b8, já listado acima, sob MIT OR
Apache-2.0. As alterações, testes e probe novos são originais do Bridge sob MIT.
O preparador exporta o objeto Git e conserva os avisos/licenças do upstream
na cópia. Não inclui binários upstream ou fixtures privadas na distribuição.
[ADR 028](docs/decisions/028-experimental-multi-input-host.md).

A extensão mathops usa implementação Rust original das operações matemáticas,
modelos de cor/alpha/blur e transporte experimental. A documentação pública
Boris FX MathOps informa somente funções e menus; nenhum código, binário,
SDK, preset ou asset Sapphire é distribuído. Avisos do runtime Rust 1.98.1
estão em extensions/mathops/licenses. Source B/Mask FFX são substituições
manuais explícitas, não dados decodificados de referência.

## Dissolve Shake original — 0.27.0

src/craft_bridge/extensions/dissolveshake contém código MIT original, sem
dependências externas Rust. Documentação pública Boris FX só informa funções;
IDs/tipos/menus vêm de descritores locais não redistribuídos. Sem código,
SDK, binário ou asset Sapphire. Runtime Rust 1.98.1/std/compiler-builtins
tem avisos e textos completos em dissolveshake/licenses. O patch de host
revisão 2 conserva as licenças MIT OR Apache-2.0 do upstream fixado e
acrescenta alterações originais MIT.


## Heatwave original — 0.28.0

src/craft_bridge/extensions/heatwave contém código MIT original, sem
dependências Rust externas. A documentação pública Maxon informa funções;
IDs/tipos/menus derivam de descritores locais não redistribuídos. Nenhum
código, SDK, binário, asset ou preset Universe foi obtido/reutilizado. O WASM
vincula Rust 1.98.1/std/compiler-builtins; avisos e textos completos em
heatwave/licenses. Helpers de ABI são código original já usado pelo Bridge.


## Signal original — 0.29.0

src/craft_bridge/extensions/signal contém código Rust MIT original, sem
bibliotecas Rust externas. Página pública Zaebects/aescripts consultada
somente para a descrição funcional; nenhum código, SDK, binário, preset ou
asset proprietário obtido/reutilizado. IDs/tipos/menus derivam de descritores
locais não redistribuídos. Rust 1.98.1/std/compiler-builtins e suas licenças
acompanham signal/licenses. Envelope ABI reutiliza helpers originais Bridge.
[ADR 034](docs/decisions/034-approximate-signal-renderer.md).


## Imagens temporais — 0.30.0

API 4/revisão 3 do host experimental acrescenta imagens da própria camada em
outros tempos pelo callback nativo e controles declarativos limitados.
A Session real verificou 23 samples de pixels originais. Nenhum mapa Adobe
novo: 131 PARTIAL/13 UNSUPPORTED permanecem. APIs anteriores são preservadas;
o EffectCraft oficial exige preparação separada da cópia experimental.
[Contrato, evidência e limites](docs/temporal-input-host.md).
Upstream fixado e licenciado MIT OR Apache-2.0; alterações, manifesto e WAT
são originais MIT. Nenhum código, asset ou preset proprietário acrescentado.


## Geometric Filter — 0.31.0

Extensão opcional original aproximada API 4: 21 controles brutos sustentados
por um snapshot local, seis formas, busca por cor, recursão e pixels retidos.
Seletor de estilo e hidden permanecem perdas; sempre PARTIAL. Session real
confirma controles persistidos/reabertos sobre imagens originais; nenhum
algoritmo/código/asset proprietário reutilizado ou equivalência presumida.
Corpus: 132 PARTIAL/12 UNSUPPORTED, 3530 controles/561 chaves; objetivo universal
continua pendente.
[Instalação, evidência e limites](docs/geometric-extension.md).
Código Rust MIT original sem bibliotecas Rust externas. Licenças
Rust 1.98.1/std/compiler-builtins acompanham geometric/licenses.


## Pixel Encoder — 0.32.0

16 controles de um snapshot real recebem renderer original aproximado
API 2: dez padrões, glifos de segmentos, cores e caos. Sliders brutos,
menus/ARGB comprovados; calibração e fidelidade são perdas. Session real
comprova controle persistido/reaberto sobre pixels próprios. Sem material
proprietário reutilizado. Corpus: 132 PARTIAL/12 UNSUPPORTED, 3546 controles/
561 chaves. Objetivo universal permanece aberto.
[Instalação, evidência e limites](docs/pixelencoder-extension.md).
Código MIT original, sem bibliotecas Rust externas. Avisos Rust 1.98.1/
std/compiler-builtins acompanham pixelencoder/licenses.


## S_Hotspots — 0.33.0

Nove controles de processamento reais recebem renderer original aproximado
API 2 e uma máscara substituta explícita, fixada ao hash/índice/ID. None
não é inferido de dados opacos. Mocha/path/combinação/calibração permanecem
perdas; strict sem saída parcial. Sem vínculos manuais o corpus mantém
132 PARTIAL/12 UNSUPPORTED, 3546 controles/561 chaves. Suporte universal
continua pendente.
[Evidência, uso e limites](docs/hotspots-extension.md).
Código MIT original, sem bibliotecas Rust externas. Avisos Rust 1.98.1/
std/compiler-builtins em hotspots/licenses; sem material proprietário obtido.


## Bridge HitFilm Hotspots (0.34.0)

Renderer, ABI wrapper e helpers hfhotspots são originais MIT deste projeto.
Rust 1.98.1 std possui avisos em extensions/hfhotspots/licenses. Documentação
pública FXHOME foi consultada funcionalmente; nenhum código, plugin, SDK ou
asset FXHOME/Adobe foi obtido ou incorporado. Fixtures privadas não distribuídas.


## Bridge OLM Directional Blur (0.35.0)

Renderer, ABI wrapper/helpers e emitter WAT de teste são originais MIT.
Rust std 1.98.1 mantém avisos em extensions/olmdirectional/licenses. O manual
público OLM OpenTools foi consultado no ZIP oficial licenciado Apache 2.0;
sem código-fonte disponível. Nenhum .aex foi executado ou incorporado.
ZIP/manual de pesquisa e presets privados não são distribuídos. A extensão
não depende de software Adobe ou OLM e não certifica seu kernel/calibração.


## Bridge Godrays (0.36.0)

Renderer, ABI wrapper e helpers são originais MIT. Rust 1.98.1 std conserva
avisos em extensions/godrays/licenses. Nenhum código, SDK, plugin compilado
ou asset Adobe/ProductionCrate incorporado ou executado. Presets privados,
artefatos de pesquisa e projetos de validação não distribuídos. Sem
certificação de calibração ou equivalência visual com Crate’s Godrays.
