# Craft Preset Bridge

Aplicação open source para **ler presets Adobe localmente**, analisar compatibilidade e
converter um conjunto explícito de efeitos para FilmCraft e EffectCraft. Primeiro incremento
funcional, versão 0.36.0. Não requer Premiere, After Effects, JSX, plugins Adobe ou serviços remotos.

O programa não promete equivalência universal: plugins privados, máscaras e curvas não
verificadas aparecem nos relatórios. `SUCCESS` significa que os dados relevantes reconhecidos
foram exportados sem perdas detectadas; a validação informada no relatório distingue schema
local de execução real na engine. Não significa identidade visual com Adobe.

## Instalação e execução

Python 3.11–3.13 recomendado para a GUI. Com [uv](https://docs.astral.sh/uv/):

```sh
uv sync --frozen --extra gui
uv run --extra gui craft-bridge gui
```

No ambiente desta entrega, também é possível executar diretamente:

```sh
.venv/bin/craft-bridge-gui
```

No Windows: `.venv\Scripts\craft-bridge-gui.exe`. Somente CLI: `uv sync --frozen`.
Alternativa pip: `python -m pip install '.[gui]'`; o lock reproduzível completo é `uv.lock`.
A instalação baixa dependências; o processamento dos presets funciona offline.

## Interface gráfica

Arraste arquivos ou pastas, ou use **Adicionar arquivos / Selecionar pasta**. Escolha detecção
automática ou um dos dois fluxos. Clique em **Analisar** para ver efeitos, parâmetros,
keyframes decodificados, dados desconhecidos e uma prévia da saída. Pontos normalizados exigem
resolução de referência no campo lateral, por exemplo `1920x1080`; para FFX, use a dimensão
da camada de destino. Nenhuma resolução é assumida automaticamente.

Escolha a pasta de saída e **Converter fila**. Os relatórios JSON/HTML acompanham cada arquivo;
**Relatório** também exporta o resultado selecionado ou CSV do lote. **Rejeitar perdas** ativa
strict. Cancelar interrompe entre arquivos; o arquivo em andamento respeita os limites do parser.
Escuro/claro e a pasta de saída são salvos nas configurações locais do Qt. Selecionar a pasta
faz uma enumeração síncrona; análise, conversão e conexão executam fora da thread da interface.

**Aplicar…** revisa um plano EffectCraft e permite escolher composição e camada. A aplicação
só começa após **Confirmar e aplicar**. O EffectCraft deve estar aberto com `--control 9877`.
Para FilmCraft, use a importação da própria aplicação ou o comando CLI abaixo.
Presets de propriedades selecionadas exigem a instância correspondente já presente na
posição indicada pelo plano. Esses ajustes mantêm os outros parâmetros e a ativação do
efeito; propriedades já animadas ou com expressões são recusadas antes de alterar o projeto.

## CLI

```sh
craft-bridge inspect preset.ffx
craft-bridge inspect preset.prfpset --json
craft-bridge convert preset.prfpset --out preset.filmcraft.json --size 1920x1080
craft-bridge convert preset.ffx --out preset.effectcraft.json
craft-bridge convert preset.ffx --out simulado.json --dry-run --json
craft-bridge convert preset.ffx --out seguro.json --strict --json
craft-bridge batch ./presets --out ./converted --preserve-folders
craft-bridge mappings list
craft-bridge mappings install pacote.json
craft-bridge doctor --json
```

Cada conversão publica `saida.json`, `saida.json.report.json` e `saida.json.report.html`.
Sem conteúdo suportado, ou quando strict rejeita perdas, apenas relatórios são publicados.
Dry-run não escreve arquivos. Saídas existentes e arquivos de origem nunca são sobrescritos.
Os relatórios preservam os avisos de parâmetros mesmo quando o efeito não tem mapa
ou sua criação é recusada. Consulte [por que um preset fica parcial ou não suportado](docs/compatibility-diagnostics.md).
Em lotes, os nomes incluem extensão e, no modo plano, um hash do caminho para evitar colisões;
`--preserve-folders` mantém a hierarquia. O CLI gera também `batch-report.json/csv`.

Parâmetros: `--max-mib 64`, `--timeout 15`, `--size 1920x1080`,
`--keyframe-mode Scale|AnchorToIn|AnchorToOut`. `--verbose` é uma opção global antes do comando.
A extensão não determina o parser: `inspect/convert` identificam o conteúdo.
A busca recursiva em lote seleciona extensões `.ffx`/`.prfpset`.

Códigos: **0** sucesso/inspeção, **1** falha, **2** conversão parcial (ou erro de sintaxe da CLI),
**3** não suportado, **130** cancelado. Consulte o JSON para distinguir erro de argumento de
resultado parcial. Em lotes mistos, consulte os estados individuais; o retorno é o maior código.

## Aplicação nas engines

O arquivo `craftbridge.effectcraft-plan` é um **plano próprio**, não um preset nativo importável.
O plano atual usa versão 2. Reconverta os planos v1: eles podem conter pontos em unidades incorretas.

```sh
effectcraft --control 9877
craft-bridge apply preset.effectcraft.json --layer '#1' --comp 'Minha composição' --dry-run
craft-bridge apply preset.effectcraft.json --layer '#1' --comp 'Minha composição' --yes
craft-bridge apply preset.effectcraft.json --layer '#1' --yes --save-project novo.ecproj
```

Sem `--yes`, a CLI interativa mostra os comandos e pede `APLICAR`; em automação sem terminal,
recusa. O adaptador consulta capacidades, comandos, efeitos, propriedades disponíveis e o alvo;
usa paths e UIDs retornados por `effect.apply`. Tempos são em **segundos da camada**.
Antes de aplicar animação, verifica se a composição arredondaria algum keyframe para outro frame.
Em caso de falha após uma mutação, a engine pode conter parte das mudanças; não há rollback
transacional neste incremento. Use a prévia e o histórico da aplicação.

`--save-project` permite somente um caminho `.ecproj` novo. O arquivo é salvo pela engine;
o Bridge não escreve projetos diretamente.

```sh
filmcraft --control 9876
craft-bridge apply preset.filmcraft.json --target filmcraft --dry-run
craft-bridge apply preset.filmcraft.json --target filmcraft --yes
```

Isso importa os presets para a biblioteca, via `presets.import`; não os aplica automaticamente
a clipes. Presets de mesmo nome podem substituir a entrada da biblioteca conforme o comportamento
oficial do FilmCraft. A prévia mostra o caminho que será importado.

## Suporte e evidência

| Recurso | Estado efetivo | Evidência nesta entrega |
|---|---|---|
| XML PremiereData, referências, valores StartKeyframe | Implementado | 3 amostras PRFPSET públicas + testes sintéticos |
| Gaussian Blur 2 → FilmCraft | Implementado para parâmetros estáticos | Amostras reais com máscaras resultam PARTIAL; fixture sintética sem máscara é completa |
| Geometry2 → FilmCraft | Parcial; exige resolução | Amostra real; importação/tipos nativos validados conforme `docs/validation.md` |
| RIFX/FaFX, índices, snapshots, parT, tipos e strings | Implementado e limitado | 144 FFX locais + sample_1.ffx; sem redistribuição |
| FFX lhd3/ldat escalares, tangentes e base por stream | Implementado | sample_1.ffx e streams reais do pacote |
| Keyframes multidimensionais não espaciais | Implementado estruturalmente | Sintéticos 2D/3D e perfil intercalado; **sem prova real desse perfil** |
| Brightness & Contrast → EffectCraft | Implementado | FFX real, execução na engine oficial, keyframes e .ecproj |
| Unsharp Mask, Geometry2 → EffectCraft | Mapas estáticos implementados | Seis instâncias aplicadas na engine real; sem comparação visual Adobe |
| Sharpen → EffectCraft | Perfil estático | Duas instâncias reais aplicadas; índices com lacunas conferidos por namespace |
| Motion Tile, Noise/HLS/Auto, Tint, Tritone, gradiente 4 cores, Wave Warp, Optics Compensation, Upscale, Camera-Shake Deblur | Novos mapas, com limitações por parâmetro | Corpus real e aplicação nativa; veja expansão |
| Hue/Saturation, Levels, Exposure, Black & White, Invert, Box Blur | Mapas estáticos; estado de canais lido de aRbp | Corpus real e valores conferidos na engine; Levels tem limitação de clipping 32bpc |
| Curves | Transferência parcial dos 256 samples por canal; precisão/interpolação continuam perdas | 22 instâncias reais/110 propriedades salvas e reabertas; comparação quantitativa com avaliador nativo |
| Lumetri | Parcial, com condições de ativação dos grupos | Nove instâncias com valores conferidos na engine |
| Propriedades selecionadas Motion Tile/Tritone | Vínculo a instância existente; tipos comprovados de origem | Cinco grupos reais aplicados, mantendo parâmetros não selecionados e enabled |
| Bool/Choice Hold e Color Linear/Hold | Animação tipada | Chaves reais e fixtures sintéticas com valores intermediários conferidos na engine |
| Radial Blur / CC Radial Blur / Camera Lens Blur / CC Scale Wipe | Mapas com limitações de opções, limites e referências de camada | Oito componentes reais, 47 parâmetros/duas chaves; projeto salvo/reaberto pela engine |
| Gaussian/Directional Blur → EffectCraft | Experimental | Catálogo de destino verificado; fixtures de origem sintéticas; aviso MAPPING_UNVERIFIED |
| GUI, fila, cancelamento, temas e relatórios | Implementado | Smoke test Qt offscreen e testes de worker |
| Aplicação EffectCraft e importação FilmCraft | Implementado | Engine EffectCraft real + mocks; detalhes da importação nativa em `docs/validation.md` |

O pacote privado contém principalmente Optical Flares, Sapphire, Deep Glow e outros plugins.
As extensões opcionais Glow e Shake oferecem conversões aproximadas de PEDG/S_Shake;
Optical Flares agora tem uma biblioteca local de cenas e renderer procedural aproximado;
os demais plugins ainda exigem renderers/mapas próprios. O parser preserva cenas OFP v3
com roundtrip de bytes comprovado, mas dados exatos não garantem aparência equivalente.
[Uso e limites da biblioteca](docs/flare-library.md).
O objetivo de suportar todos os efeitos continua em andamento. O catálogo de destino contém
306 efeitos EffectCraft e 303 FilmCraft; há 35 mapas (30 FFX e cinco Premiere), o que não significa suporte universal.
Com os mapas builtin, 75 dos 144 FFX geram resultados parciais e 69 permanecem sem conversão;
1370 parâmetros e 17 keyframes são exportados. Com Glow e Shake instalados, são
101 parciais e 43 sem conversão, 2673 controles e 345 chaves. Acrescentando a biblioteca
Flare local: 111 parciais/33 sem conversão, 2892 controles/486 chaves.
Com Stretch também ativado: 117 parciais/27 sem conversão, 3037 controles/486 chaves.
Com Diffusion também: 119 parciais/25 sem conversão, 3105 controles/486 chaves.
Com Modulation, Glint, Pixel Sort, Flicker, Median, Directional Blur, Sharpen e Colorize também ativados:
124 parciais/20 sem conversão, 3393 controles/507 chaves. Nenhum preset está completo.
Pacotes v2 podem declarar plugins nativos adicionais; planos v3 fixam seu manifesto e
o preflight confere a instância conectada. Isso exige renderer específico no EffectCraft;
não torna os plugins Adobe automaticamente compatíveis.
Detalhes, correções de unidades e pendências: [expansão](docs/effect-expansion.md).

Limitações: máscaras/Base64, expressões, texto/animadores, shapes, dados privados, curvas
espaciais e keyframes Premiere sem códigos verificados. Motion/Opacity intrínsecos,
Gamma, Crop, várias transições, LUTs externas e Glow ainda precisam de mapas. Lumetri tem mapa parcial condicionado aos grupos ativos. Curves transfere a LUT de 8 bits,
com perdas de interpolação/HDR/16–32bpc registradas; blobs animados e clipping Levels condicionado a 32bpc são recusados.
Color Neutralizer conserva Pinning/Blend somente no modo final com pontos preto/branco default;
RGB sem unidade comprovada continua perda. Não há equivalência visual
validada por renderização comparativa. Multiplataforma preparada por CI; os testes executados
nesta entrega foram em Linux. A GUI não preserva a hierarquia das pastas na saída (o CLI preserva).

## Desenvolvimento e distribuição

```sh
uv sync --frozen --extra dev --extra gui
uv run --extra dev --extra gui pytest -q
CRAFT_REAL_FIXTURES=1 uv run --extra dev pytest -q tests/integration/test_real_fixtures.py
uv run --extra dev ruff check src tests scripts
uv run --extra dev mypy
uv run --extra dev python -m build
```

Os testes `real` são opt-in e precisam dos clones em `.research` e do pacote original local.
Não são baixados pela CI. Os testes sintéticos não provam compatibilidade com presets Adobe reais.
Schemas e mapas são regenerados por `scripts/generate_schemas.py` e
`scripts/make_builtin_catalog.py`, após revisão da evidência.

Empacotamento desktop: `uv run --extra gui --extra build python scripts/build_desktop.py`.
Gera um diretório com executável e bibliotecas dinâmicas. Os workflows verificam Windows,
macOS e Linux; não há instaladores assinados. Instruções em [docs/build.md](docs/build.md).

Arquitetura: `core/` modelos/pipeline/segurança, `parsers/` XML e binário, `mappings/` dados
validados, `exporters/` saídas, `integrations/` APIs locais, `cli/` e `gui/` clientes independentes.
Veja [pesquisa](docs/research.md), [formatos/API](docs/formats.md),
[compatibilidade](docs/compatibility.md), [validação](docs/validation.md),
[adição de mapas](docs/mappings.md) e [decisões](docs/decisions/001-conservative-parsing.md).

MIT para o Bridge. Fontes, commits e avisos em [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
Dependências Qt/PySide6 têm condições próprias; consulte os avisos antes de redistribuir builds.

## Glow próprio opcional

A extensão `glow` transfere 13 controles PEDG para um renderer original aproximado,
sem plugin Adobe. Instale com `craft-bridge extensions install glow` e carregue o
WASM mostrado no EffectCraft. Toda conversão permanece parcial; não há equivalência
visual comprovada. [Instruções e limitações](docs/glow-extension.md).

A extensão `shake` transfere 43 controles S_Shake para **Bridge Shake (Approximate)**,
um renderer original determinístico. Instale com `craft-bridge extensions install shake`
e carregue o módulo mostrado no EffectCraft. [Uso e limites](docs/shake-extension.md).

Para Optical Flares, execute `craft-bridge extensions build-flare ./presets --out ./minha-biblioteca`,
instale o `mapping.json` gerado e carregue seu módulo no EffectCraft. Os dados privados
ficam somente nessa biblioteca local. [Instruções, desempenho e perdas](docs/flare-library.md).

A extensão `stretch` transfere 20 controles de `pixel_stretch` para um renderer
original de estiramento cumulativo. Instale com `craft-bridge extensions install stretch`
e carregue o módulo mostrado no EffectCraft. [Uso e limites](docs/stretch-extension.md).

A extensão `diffusion` transfere 17 controles de `omino_diffusion` para um renderer
original de paleta/difusão. Instale com `craft-bridge extensions install diffusion`
e carregue o módulo mostrado no EffectCraft. [Uso e limites](docs/diffusion-extension.md).

A extensão `modulation` transfere os 12 controles do perfil Modulation com ID
`ADBE Checkout`, incluindo as animações decodificadas, para um renderer original
aproximado de FM em cinza. Instale com `craft-bridge extensions install modulation`
e carregue o módulo mostrado no EffectCraft. [Uso e limites](docs/modulation-extension.md).

A extensão `glint` transfere 25 controles S_Glint para um renderer original de
raios em quatro eixos. Instale com `craft-bridge extensions install glint` e
carregue o módulo mostrado no EffectCraft. Background/Matte/Mocha e fidelidade
visual continuam perdas explícitas. [Uso e limites](docs/glint-extension.md).

A extensão `pixelsort` transfere 24 controles S_PixelSort para um renderer
original de ordenação Linear/Radial/Circular. Instale com
`craft-bridge extensions install pixelsort`, carregue o módulo mostrado no
EffectCraft e informe o tamanho da camada na conversão dos centros.
[Uso e limites](docs/pixelsort-extension.md).


A extensão `flicker` transfere 14 controles S_Flicker para um renderer original
aproximado de modulação temporal RGB. Instale com `craft-bridge extensions install flicker`
e carregue o módulo no EffectCraft. Grupo selecionado exige a instância existente;
seed fracionário e três chaves isoladas foram verificados. Com todas as extensões:
122 parciais/22 sem conversão, 3220 propriedades/507 chaves; nenhum preset completo.
[Uso e limites](docs/flicker-extension.md).

A extensão `median` transfere dez controles BCC3Median para uma mediana retangular
original aproximada. Instale com `craft-bridge extensions install median` e
carregue o módulo mostrado no EffectCraft. Três instâncias reais conservaram 30
valores estáticos após salvar/reabrir. Com todos os opcionais: 123 PARTIAL/21
UNSUPPORTED, 3250 propriedades/507 chaves. Máscaras, Compositing, amostragem
esparsa e fidelidade permanecem perdas. [Uso e limites](docs/median-extension.md).

A extensão `directional` transfere 12 controles BCC3Directional Blur para um
renderer original aproximado. Instale com `craft-bridge extensions install directional`
e carregue o módulo mostrado no EffectCraft. Três instâncias reais conservaram
36 valores estáticos após salvar/reabrir. Com todos os opcionais: 124 PARTIAL/20
UNSUPPORTED, 3286 propriedades/507 chaves. Amostragem, mistura, máscaras/audio
e renderização além do canvas continuam perdas. [Uso e limites](docs/directional-extension.md).

A extensão `sharpen` transfere 15 controles S_Sharpen para um renderer multibanda
original aproximado: `craft-bridge extensions install sharpen`. Uma instância
real preservou os valores estáticos após salvar/reabrir. Matte/Mocha e widget
de edição continuam perdas; nunca se presume máscara vazia. Sempre PARTIAL.
[Uso, diferenças e desempenho](docs/sharpen-extension.md).

Planos próprios v4 agora podem vincular parâmetros nativos Layer a camadas
reais por `--bind-layer REF=SELETOR`. O preflight resolve e confere os UIDs antes
de aplicar; v2/v3 continuam aceitos. 71 vínculos em 42 efeitos nativos foram
persistidos/reabertos com dados próprios. A leitura de referências opacas dos
FFX e a reconstrução automática dos recursos de origem ainda estão pendentes.
[Exemplo, uso e limites](docs/layer-resources.md).

Há um [patch experimental de host](docs/experimental-multi-input-host.md) em
desenvolvimento para transportar até quatro imagens auxiliares ao WASM.
Ele é preparado em cópia separada e preserva API 1. Não é uma ABI oficial,
não acompanha o executável do Bridge e exige instalação separada para renderers API 2.
O Bridge 0.25.0 aceita seus manifestos API 2/planos v4 mediante preflight da
revisão/capacidade, com vínculos Layer explícitos por `--bind-layer`.

A extensão `colorize` preserva 23 controles BCC3Colorize em um gradiente
original aproximado: `craft-bridge extensions install colorize`. Quatro
instâncias reais preservaram 92 valores estáticos após salvar/reabrir.
PixelChooser/Mocha/tracking/Compare e diferenças de cor/calibração continuam
perdas. Input PixelChooser é recusado; strict não publica o plano parcial.
[Uso e diferenças](docs/colorize-extension.md).

A extensão `mathops` acrescenta um renderer original aproximado de S_MathOps
com Source B e máscara de camada, 15 controles e duas substituições explícitas
fixadas ao hash do FFX. Exige host experimental; referências FFX continuam
opacas. `--source-layers` na conversão prepara os nomes e `--bind-layer` na
aplicação resolve as camadas reais. Sempre PARTIAL; strict não publica.
[Uso, evidência e limites](docs/mathops-extension.md).


A extensão opcional `dissolveshake` converte 40 controles de S_DissolveShake e
uma escolha manual de Background. Os cinco grupos selecionados reais agora
convertem 48 controles/54 chaves; os quatro snapshots completos exigem vínculo
explícito de imagem. O renderer original aproximado usa o host experimental
revisão 2/API 3 para receber os tempos reais da camada, incluindo trim e stretch.
A conversão continua PARTIAL; strict recusa a publicação. No corpus automático,
129 de 144 arquivos são PARTIAL e 15 UNSUPPORTED, sem equivalência visual Adobe
comprovada. [Instalação, vínculos e limites](docs/dissolveshake-extension.md).


A extensão opcional `heatwave` acrescenta Universe_Distort_Heatwave com 24
controles e Mask Layer manual, três tipos de ruído, blur espacial e máscaras
geométricas/de camada. Pontos exigem tamanho explícito e a criação exige todos
os controles. Renderer original aproximado API 2, sempre PARTIAL; strict não
publica um preset parcial. [Uso e limites](docs/heatwave-extension.md).


A cópia do host experimental na 0.28.0 também corrige cache temporal de
plugins API 1 com controles estáticos. Isso permite ondas/PRNG evoluírem sem
keyframes artificiais, com ABI/módulos preservados. O aplicativo oficial não
é alterado. [Verificação](docs/decisions/033-plugin-time-aware-cache.md).


A extensão opcional `signal` acrescenta 34 controles de ADBE Signal por
modulação/decodificação original aproximada. Dois snapshots comprovam os
tipos e menus; Destruction button permanece sem tradução. Requer host
experimental API 2. Sempre PARTIAL e strict sem publicação parcial.
[Instalação e limites](docs/signal-extension.md).


## Imagens temporais — 0.30.0

API 4/revisão 3 do host experimental acrescenta imagens da própria camada em
outros tempos pelo callback nativo e controles declarativos limitados.
A Session real verificou 23 samples de pixels originais. Nenhum mapa Adobe
novo: 131 PARTIAL/13 UNSUPPORTED permanecem. APIs anteriores são preservadas;
o EffectCraft oficial exige preparação separada da cópia experimental.
[Contrato, evidência e limites](docs/temporal-input-host.md).


## Geometric Filter — 0.31.0

Extensão opcional original aproximada API 4: 21 controles brutos sustentados
por um snapshot local, seis formas, busca por cor, recursão e pixels retidos.
Seletor de estilo e hidden permanecem perdas; sempre PARTIAL. Session real
confirma controles persistidos/reabertos sobre imagens originais; nenhum
algoritmo/código/asset proprietário reutilizado ou equivalência presumida.
Corpus: 132 PARTIAL/12 UNSUPPORTED, 3530 controles/561 chaves; objetivo universal
continua pendente.
[Instalação, evidência e limites](docs/geometric-extension.md).


## Pixel Encoder — 0.32.0

16 controles de um snapshot real recebem renderer original aproximado
API 2: dez padrões, glifos de segmentos, cores e caos. Sliders brutos,
menus/ARGB comprovados; calibração e fidelidade são perdas. Session real
comprova controle persistido/reaberto sobre pixels próprios. Sem material
proprietário reutilizado. Corpus: 132 PARTIAL/12 UNSUPPORTED, 3546 controles/
561 chaves. Objetivo universal permanece aberto.
[Instalação, evidência e limites](docs/pixelencoder-extension.md).


## S_Hotspots — 0.33.0

Nove controles de processamento reais recebem renderer original aproximado
API 2 e uma máscara substituta explícita, fixada ao hash/índice/ID. None
não é inferido de dados opacos. Mocha/path/combinação/calibração permanecem
perdas; strict sem saída parcial. Sem vínculos manuais o corpus mantém
132 PARTIAL/12 UNSUPPORTED, 3546 controles/561 chaves. Suporte universal
continua pendente.
[Evidência, uso e limites](docs/hotspots-extension.md).


## HitFilm Hotspots — 0.34.0

Dois snapshots reais comprovam cinco controles visíveis; renderer original
API 2 separa fill de cor abaixo do limiar de extração Sapphire. Dez valores
reais persistidos/reabertos sobre pixels próprios; sliders brutos, hidden e
calibração continuam perdas. Sempre PARTIAL; strict não publica parcial.
Sem parser ou pacote privado alterado, sem código/SDK/assets proprietários.
[Evidência, uso e limites](docs/hfhotspots-extension.md).


## Godrays — 0.36.0

`craft-bridge extensions install godrays` instala o mapa aproximado de 25
controles reais de PEGR. Carregue o WASM no host experimental API 2;
Buffer Expansion não neutro e separador Quality são recusados. Dez casos
na Session, valores persistidos/reabertos e pixels próprios full/half.
Calibração/unidades continuam perdas; strict não publica parcial.
[Evidência, instalação e limites](docs/godrays-extension.md).

O [diagnóstico agregado](docs/compatibility-diagnosis.md) explica efeitos
sem mapa, parâmetros opacos e aproximações sem exportar presets privados.

## OLM Directional Blur — 0.35.0

14 controles reais e uma entrada de transporte recebem renderer anisotrópico
original API 2. Manual OLM comprova Noise Layer somente no modo Layer;
Smooth/Block estático íntegro autoriza entrada inativa, preservando vínculo
opaco e avisos. Layer continua exigindo escolha manual. Fades/tails/grupos/
ruído/calibração próprios, sempre PARTIAL; strict não publica parcial.
Manual consultado de pacote público licenciado, sem código-fonte disponível;
plugins compilados não executados/distribuídos, parser e presets intactos.
[Evidência, uso e limites](docs/olmdirectional-extension.md).
