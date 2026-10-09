# Validação executada nesta entrega

**Estado atual 0.23.0 (builtin):** veja [expansão](effect-expansion.md): lote com
75 resultados parciais/69 não suportados, 1370 parâmetros e 17 keyframes exportados.
Na 0.7, dois Color Neutralizer reais preservaram quatro propriedades; um perfil RGB
inteiramente sintético preservou cinco. Ambos passaram por salvamento/reabertura.
O RGB real permanece recusado porque seus descriptors não declaram unidade percentual.
Detalhes: [ADR 006](decisions/006-neutralizer-rgb-transfer.md).
Na 0.6, 22 componentes Curves tiveram 110 propriedades estáticas conferidas na engine,
inclusive após salvar/reabrir o projeto. Na 0.5 foram oito componentes/47 parâmetros/duas chaves;
na 0.4, 16 componentes/226 parâmetros/11 chaves. Curves continua parcial por perda de precisão/interpolação.
Na 0.6, o renderer nativo de Curves também foi conferido com ramps por canal contra
Curve::eval. Text estático FilmCraft passou por EffectInstance oficial e presets.import
em fixture sintética, sem atribuir essa evidência a um preset Adobe real.
Na 0.8, a extensão de catálogo/API v1 foi validada com um módulo WASM original/sintético:
três propriedades persistidas e 12 amostras renderizadas, sem novo plugin Adobe real.
Detalhes e limites da introspecção: [ADR 007](decisions/007-native-plugin-catalogs.md).
Checks da 0.8: 259 testes passaram (incluindo corpus real), Ruff/Mypy passaram;
wheel/sdist, instalação headless sem Qt e build Linux/smoke Qt verificados.
Os resultados completos de 55 planos/976 parâmetros pertencem à validação anterior 0.3.
A validação a seguir é o histórico da 0.1.0.
Foi descoberto e corrigido um erro de unidades dos pontos Geometry2: a aceitação anterior
pela API não certificava a conversão correta em pixels. Planos EffectCraft v1 exigem reconversão.

Data: **7 de outubro de 2026**, Linux x86_64, Python 3.12.13 / Qt 6.9.3.
Os commits e licenças das fontes estão em references.json. Não havia binários FilmCraft ou
EffectCraft instalados no PATH. Foram compiladas bibliotecas oficiais em um harness isolado,
sem modificar os repositórios de referência. Rust 1.98.1 foi usado apenas para esta validação.

## Níveis de evidência

1. **Sintético:** fixtures criadas pelo Bridge, testes de XML/RIFX, limites, ataques, tipos,
   enum, tempo, 2D/3D, exportadores e protocolo simulado. Não são arquivos Adobe reais.
2. **Real de origem:** três amostras PRFPSET de notoow, sample_1.ffx do FFX Compatibility Tool
   e 144 FFX privados do pacote local do usuário. Nenhum é distribuído pelo Bridge.
3. **Nativo do destino:** tipos/catálogos e engines reais compilados, chamados pelo harness.
   Isso vai além de mocks, mas não testa as janelas desktop nem a renderização comparativa Adobe.

## FilmCraft

O preset Transform obtido da amostra real `변형.prfpset`, com referência 1920×1080, foi
serializado, desserializado como **EffectInstance oficial** e conferido contra o catálogo real.
Depois foi importado com sucesso por **Session.execute("presets.import", ...)** da engine
oficial no commit a4536bcfedf588cbef9ea24df149c70bf99a037d.

Resultado nativo: `{"imported":["변형 사전 설정"]}`. A conversão continua **PARTIAL**, porque
as opções de shutter dependente da composição e sampling da origem não têm equivalência
certificada nesse mapa. A aceitação pela engine não elimina essa perda.

## EffectCraft

A engine oficial no commit e38a92e792c07f1c57c5dcfcab37d91932b9e2b8 foi inicializada
com uma composição 30 fps e um solid de teste em memória. O harness implementa somente o
transporte JSON por linha; as consultas, mutações e serialização são executadas pela Session real.

Do arquivo real **sample_1.ffx**, o efeito `ADBE Brightness & Contrast 2` foi mapeado para
`ec.color.brightnesscontrast`. A aplicação criou uma instância e retornou seu path/UID.
Consultas `prop.get` confirmaram:

| Propriedade | Resultado nativo |
|---|---|
| brightness | 100 em 0 s; 0 em 0,7 s; Bezier in/out |
| contrast | 0, estático |
| useLegacy | false, estático |

`keys.info` confirmou influência de aproximadamente 33,333333% e velocidade 0 nos lados
relevantes das curvas. Os ticks originais são 0 e 21504 com base 30720, portanto 0,7 s,
sem o erro de usar 1024 ticks/s. `file.saveAs` produziu um **.ecproj real** da engine.
Após adicionar conferência automática com prop.get ao adaptador, a aplicação foi repetida
com sucesso em outra instância retornada como `effects/#2`.

Também foram aplicados **seis planos parciais** derivados do pacote privado do usuário;
o adaptador consultou as propriedades retornadas e confirmou seus valores na engine real.
Esses planos contêm **nove efeitos e 45 parâmetros**: Brightness & Contrast (3),
Unsharp Mask (4), Transform (2). Não preservaram keyframes desse pacote, porque seus
streams animados pertencem a efeitos/estruturas não suportados. Sharpen é decodificado
em dois arquivos, mas esses caminhos têm índices fora do perfil certificado e foram recusados.

Os projetos de teste, resultados completos e imagens da GUI estão em `artifacts/`, excluídos
da distribuição por conter resultados de fixtures privadas. O servidor de teste não é o
servidor desktop oficial; utiliza as mesmas engines/comandos reais por trás do transporte.

## Resultado do lote privado

144 arquivos lidos de forma estruturada, **6 PARTIAL e 138 UNSUPPORTED**, zero SUCCESS.
Nenhum é anunciado como conversão completa. Saídas parciais e relatórios individuais estão
em `artifacts/converted-user-presets`. Métricas sem dados privados: corpus-summary.json.
As origens foram mantidas intactas.

## GUI, pacote e qualidade

A GUI foi aberta em Qt offscreen, analisou arquivos reais em worker, exibiu os dois temas e
foi capturada em PNG para inspeção visual. Isso não valida sessões gráficas de Windows/macOS.
A suíte separa testes normais e `real`. A execução final com `CRAFT_REAL_FIXTURES=1 pytest -q`
passou em **73 testes**. Ruff e Mypy (31 arquivos do núcleo/CLI/GUI) passaram.
O wheel foi instalado em um ambiente separado sem PySide6; doctor confirmou oito mapas e
`gui_installed: false`, preservando o funcionamento headless.
Foram construídos wheel/sdist e um bundle
Linux via PyInstaller; builds de outros sistemas estão preparados por workflow, não executados aqui.

## Lacunas explícitas

Não houve Premiere/After Effects, renderização Adobe, comparação visual entre engines,
validação de FFX multidimensional por fixture real rotulada, curvas XML escalares reais,
texto/shape/máscaras completas, plugins proprietários, rollback transacional, instaladores
assinados ou teste desktop end-to-end em três sistemas operacionais.


## Extensão opcional Glow 0.9

270 testes Python passaram, incluindo o corpus real opt-in; Ruff/Mypy passaram.
Oito testes Rust e Clippy passaram para o renderer original. 23 snapshots reais
transferiram 299 controles, verificados após salvar/reabrir projeto nativo. Com
extensão instalada: 80 PARTIAL/64 UNSUPPORTED, 1669 parâmetros/17 chaves. Sem ela,
a cobertura builtin permanece 75/69 e 1370/17. Os 144 hashes originais foram conferidos.
Nove casos de pixels sintéticos passaram pelo loader WASM oficial, com sucesso de
render explícito, incluindo Full HD/Radius 2000 (~23 s neste ambiente). Nenhuma
comparação visual Adobe foi realizada. O módulo é CPU/WASM e lento para preview;
o algoritmo e a gama/qualidade continuam perdas declaradas. [ADR 008](decisions/008-approximate-glow-renderer.md).

Wheel/sdist 0.9 finais foram auditados: módulo coincide com o hash da auditoria
WASM, fonte original/avisos Rust incluídos, sem dados privados. A instalação do
wheel headless sem Qt foi verificada. Build desktop Linux contém o mesmo módulo
auditado e avisos; smoke Qt offscreen de cinco segundos encerrou por timeout
esperado, sem mensagens de erro. Windows/macOS não foram executados neste ambiente.

## Perfis de origem e Glow selecionado 0.10

281 testes Python passaram com corpus real opt-in e Qt offscreen; Ruff e Mypy
passaram. O snapshot de 2648 tipos foi reextraído e conferido contra todos os
descriptors reais, sem conflitos. Os 144 hashes de entrada coincidem com a
auditoria original; sem extensão, o lote continua 75 PARTIAL/69 UNSUPPORTED,
1370 controles/17 chaves. Com Glow: 92/52, 1718 controles/110 chaves.

18 componentes selecionados adicionais preservaram 49 controles/93 chaves,
31 lados Bezier e 150 amostras intermediárias, antes/depois de salvar e reabrir
projeto oficial. Os destinos começaram inativos, com outra composição aberta.
UIDs, contagem, enabled e controles não selecionados foram preservados; a
composição de distração permaneceu intacta. [ADR 009](decisions/009-source-profiles-and-selected-glow.md).

Wheel headless 0.10 foi instalado sem Qt em Python 3.14.0; uma aplicação nativa
selecionada preservou dois controles/seis chaves e passou por reabertura, ativando
a composição correta. Wheel e bundle Linux contêm os 2648 perfis e o mesmo
WASM auditado na 0.9 (SHA-256 468c3abd6fd0940dabcb52d13bb02006eb0a119b749c93df1902eaea9bb4083c).
O renderer não mudou, portanto os oito testes Rust/nove casos nativos de pixels
da 0.9 continuam sendo a evidência desse módulo. Build Linux passou; smoke Qt
offscreen de cinco segundos encerrou por timeout esperado e log vazio. Não
houve comparação visual Adobe nem execução desktop em Windows/macOS.

## Extensão Shake 0.11

290 testes Python passaram, incluindo corpus real opt-in e Qt offscreen; Ruff/Mypy
passaram. Sete testes Rust e Clippy passaram no renderer original. 17 casos de
pixels/tempo sintéticos passaram pelo loader WASM oficial com erro explícito,
incluindo Full HD/RGB/blur (~132 s). SHA-256 do módulo: 
23af5fb6500bc26fafe46a44853c7afd4b096acbe7402e62623b25ae034a3aa8.

18 componentes criados e 13 selecionados preservaram 911 controles/229 chaves
na engine e em projeto reaberto; 148 lados Bezier/216 amostras intermediárias
foram conferidos. Os selecionados preservaram UIDs, índices, enabled e controles
restantes, começando em composições inativas. Um componente criado com quatro
chaves foi recusado antes de alterar propriedades por grade de tempo incompatível.
Com Glow e Shake: 101 PARTIAL/43 UNSUPPORTED, 2672 controles/343 chaves exportadas.
Nenhum preset completo ou equivalência visual Sapphire foi comprovado.
[ADR 010](decisions/010-approximate-shake-renderer.md).

Wheel 0.11 foi instalado sem Qt em Python 3.12.13; o módulo final foi carregado
numa Session nova e um grupo selecionado preservou nove controles/dez chaves,
ativando o destino e passando por salvamento/reabertura. Build desktop Linux
passou; smoke Qt offscreen de cinco segundos terminou por timeout esperado,
com log vazio. Windows/macOS não foram executados. Os 144 hashes originais
foram conferidos; builtin continua 75/69, 1370/17.

## Cenas OFP 0.11.1

313 testes Python passaram com corpus real opt-in e Qt offscreen; Ruff e Mypy
(36 arquivos) passaram. Fixtures sintéticas originais verificam leitura de campos,
roundtrip, truncamento/corrupção, não finitos, flags/limites/prazo, associação
estática e estados múltiplos sem seleção automática. O teste real verifica os
38 blocos byte a byte: 602 objetos/39665 campos, nove cenas associadas a Options
e 29 preservadas sem associação. [ADR 011](decisions/011-ofp-structural-scenes.md).

A auditoria completa conferiu os 144 hashes contra o lote original e repetiu
as três configurações: builtin 75 PARTIAL/69 UNSUPPORTED, 1370/17;
Glow 92/52, 1718/110; Glow e Shake 101/43, 2672/343. Sem SUCCESS.
Leitura OFP não altera essa cobertura; não há renderer ou aplicação nativa de
Optical Flares. Esses números de exportação não certificam planos completos.

Wheel/sdist 0.11.1 incluem o decoder original, com 88/176 entradas;
não incluem arquivos FFX/ecproj, presets privados, pesquisa Nuaj ou assets externos.
Wheel instalado sem Qt em Python 3.12.13 preservou cenas associadas e sem associação,
incluindo serialização/releitura do modelo JSON e hash dos bytes reconstruídos.
Build Linux inclui o decoder e os mesmos módulos Glow/Shake auditados na 0.9/0.11.
Smoke Qt offscreen permaneceu aberto por cinco segundos, com log vazio, e foi
encerrado pelo mantenedor. Windows/macOS e comparação Adobe não foram executados.

Evidência privada, excluída da distribuição: artifacts/ofp-corpus-audit-v0.11.1.json,
distribution-audit-v0.11.1.json e desktop-audit-v0.11.1.json.

## Biblioteca Flare local 0.12

Nove snapshots Options associados contêm seis cenas distintas, preservadas por
hash/binário exato na biblioteca privada. Outros 29 blocos permanecem diagnóstico.
O renderer procedural original é aproximado e omite Texture/assets. Dez controles
globais são mapeados; criação exige Scene por hash, sem fallback para default.

A Session EffectCraft fixada recebeu nove componentes criados (83 controles/50
chaves) e 21 selecionados (136/91): 219 controles/141 chaves persistidos em projetos
salvos/reabertos. Os selecionados preservaram Scene não default, enabled, UID,
índice, controles restantes e composição de distração. Foram conferidos 22 lados
Bezier e 75 valores entre chaves antes/depois de reabertura. Um grupo exige 21 fps;
o harness calcula a grade exata com ticks/base. O adaptador não muda FPS nem chaves.

As seis cenas reais renderizaram em 65×65 no loader WASM oficial, com falhas/traps
expostas; uma passou em 256×256 e Full HD (1920×1080), ~83 s/frame neste ambiente.
Os limites oficiais de fuel/memória não foram alterados. Aceitação nativa não
comprova equivalência visual Adobe; CPU/WASM continua lento. Cinco testes Rust
verificam kernels originais, modos, cor, visibilidade/solo e entrada inválida sem
alteração de pixels. Testes Python/CLI cobrem integridade do código WASM durante
patching, associação, perfil, hashes, recusa de defaults e strict sem preset publicado.

Com Glow, Shake e biblioteca Flare local: 111 PARTIAL/33 UNSUPPORTED, 2891 controles/
484 chaves; nenhum SUCCESS. Sem opcionais: 75/69, 1370/17. As fixtures reais
continuam opt-in e não entram na distribuição. Evidências locais privadas:
artifacts/flare-whole-native-v0.12/, flare-selected-native-exact-v0.12/,
flare-library-optimized/renderer-summary.json e
flare-library-profile-checked/fullhd-completed-summary.json.

[Uso](flare-library.md) e [ADR 012](decisions/012-local-flare-library.md).

Verificação final 0.12: 332 testes passaram com CRAFT_REAL_FIXTURES=1 e Qt offscreen;
o conjunto regular passou 319 testes/13 skips opt-in. Ruff completo e Mypy (38 módulos) passaram; cinco
testes Rust e Clippy passaram. O template foi reproduzido byte a byte em outro
target Cargo. O verificador WASM passou nove casos (seis cenas reais e três modos
com alpha externo zero); Full HD foi verificado separadamente com trap explícito.

Wheel/sdist incluem o template e licenças, sem FFX/ecproj, biblioteca privada, clones
ou referência Nuaj. O wheel instalado em Python 3.14.0 sem Qt reproduziu exatamente
o módulo da biblioteca privada e exportou os mesmos 219 controles/141 chaves Flare.
Desktop Linux inclui esse template, builder e schema, sem cenas privadas. O smoke
Qt offscreen permaneceu aberto por cinco segundos, com log vazio, e foi encerrado
pelo mantenedor. Os 144 arquivos privados originais mantiveram seus hashes.
Windows/macOS e comparação visual Adobe não foram executados.

## Extensão Stretch 0.13

Oito snapshots reais pixel_stretch em dois perfis de versão exportam 145 propriedades
estáticas (3×20 +5×17), sem keyframes reais. Os oito componentes passaram pela
Session oficial e reabertura do projeto. Intensity Source continua opaco: a API v1
fornece uma imagem, e dependências externas são perdas explícitas. Toda conversão
continua PARTIAL; strict não publica o preset aproximado.

Uma fixture selecionada inteiramente sintética preservou três controles/seis chaves,
quatro lados Bezier e nove amostras intermediárias. UID, índice, enabled, controles
restantes e composição de distração foram preservados após reabertura. Não se usa
esse teste como prova de animação real pixel_stretch.

Sete testes Rust e Clippy passaram. O loader WASM oficial passou 21 casos: 12 cenários
com expectativas de pixels calculadas independentemente, oito conjuntos reais de
controles sobre pixels originais de teste e um Full HD com RGBA separado/compressão/
smoothing (~72 s). Traps são expostos, sem aceitar fallback para frame inalterado.
A otimização conservou exatamente os 21 resultados da versão anterior (~78 s Full HD).
O build independente reproduziu os bytes/hash do módulo. Nenhuma comparação Adobe
foi executada. O desempenho CPU/WASM continua limitado para uso interativo.

Com Glow/Shake/Flare/Stretch: 117 PARTIAL/27 UNSUPPORTED, 3036 propriedades/484 chaves;
sem opcionais: 75/69, 1370/17. Os 144 arquivos originais mantiveram seus hashes.
Evidências privadas, fora da distribuição: artifacts/stretch-native-final-v0.13/,
stretch-renderer-final-v0.13/, stretch-synthetic-selected-native-v0.13/,
stretch-build-audit-v0.13.json e coverage-and-integrity-v0.13.json.

[Uso](stretch-extension.md), [ADR 013](decisions/013-approximate-stretch-renderer.md).

Verificação final 0.13: 333 testes/14 skips opt-in no conjunto regular; 347 testes
passaram com CRAFT_REAL_FIXTURES=1 e Qt offscreen. Ruff completo, Mypy (39 módulos),
sete testes Rust e Clippy passaram. Wheel/sdist têm 128/228 entradas e incluem
fontes, módulo original e licenças, sem FFX/ecproj, bibliotecas privadas ou clones.
O wheel instalado em Python 3.12.13 sem Qt reconheceu os dois perfis reais e
aplicou 20 propriedades nativamente, persistidas após salvar/reabrir. Desktop Linux
inclui o módulo/manifesto/schema e a lista de extensões atualizados; smoke Qt
offscreen permaneceu aberto por cinco segundos, com log vazio, e foi encerrado
pelo mantenedor. Windows/macOS e comparação visual Adobe não foram executados.

## Extensão Diffusion 0.14

Quatro snapshots omino_diffusion reais: 17 controles cada, 68 propriedades
estáticas exportadas e conferidas na Session EffectCraft oficial. O projeto foi
salvo e reaberto, conservando os valores. Nenhuma animação Omino real é alegada.

WASM executado via loader oficial com erros/traps expostos, sem fallback silencioso:
17 casos de pixels sintéticos, quatro conjuntos de controles reais em imagem
sintética 65×49 e um caso Full HD (2.073.600 pixels, ~7,26 s), todos concluídos.
Casos incluem propagação ao longo/entre scanlines, fase, quatro direções, faixas,
preview, transparência, HDR limitado e os seis slots de paleta. Rust: seis testes
e Clippy sem warnings. Compilação --locked Rust 1.98.1 em dois targets produziu
bytes idênticos: 26977 bytes, SHA256
5d0edde4e1cc04761a948c8775d74980f2708e55e28fc0cab15851f389702291.

Com todas as extensões: 119 PARTIAL/25 UNSUPPORTED, 3104 propriedades/484 chaves;
zero SUCCESS. Os 144 hashes de origem permanecem iguais ao lote original.
Evidências privadas ignoradas: artifacts/diffusion-native-v0.14/,
diffusion-renderer-v0.14/, diffusion-build-audit-v0.14.json,
coverage-and-integrity-v0.14.json e remaining-gaps-v0.14.json.
Não se afirma equivalência visual Omino nem capacidade universal.
[Uso](diffusion-extension.md), [ADR 014](decisions/014-approximate-diffusion-renderer.md).

Checks finais 0.14: 344 testes/15 skips no conjunto regular; os 15 testes reais
opt-in passaram separadamente (359 testes aprovados no total). Ruff e Mypy
passaram; seis testes Rust e Clippy sem warnings. Wheel/sdist excluem inputs
privados e contêm módulos/manifestos idênticos ao fonte; instalação headless
sem Qt reconheceu quatro componentes/68 controles reais. Build Linux possui
a versão/lista de extensões compiladas corretas e passou no smoke Qt offscreen
de cinco segundos, encerrado pelo mantenedor, sem mensagens no log.
Windows e macOS não foram validados.

## Mesh Warp estrutural 0.14.1

28 novos casos sintéticos verificam preservação exata dos dez floats por registro,
sinais de zero, payload/default distintos, layouts inválidos, orçamento/prazo,
animação e ausência de conversão falsa. O teste real opt-in confirma roundtrip
byte a byte dos dois blobs de 2580 bytes e associação correta à instância,
preservando 1280 campos float32. Geometria, pares/tangentes e unidades permanecem
sem tradução certificada; nenhum controle foi reduzido a offsets bilineares.

372 testes passaram no conjunto regular, com 16 skips; os 16 testes reais
passaram separadamente (388 aprovações no total). Ruff 0.14.0 e Mypy passaram,
com 40 arquivos de núcleo conferidos. Catálogos/renderers e cobertura de
conversão continuam iguais: 119 PARTIAL/25 UNSUPPORTED com todas as extensões,
3104 propriedades/484 chaves; zero SUCCESS. Os hashes dos 144 originais
continuam iguais. A evidência privada fica em
artifacts/coverage-and-integrity-v0.14.1.json. [ADR 015](decisions/015-mesh-structural-records.md).

## Premiere CS6 — 0.15.0

- `uv run --extra dev pytest`: 385 passaram, 17 reais opt-in ignorados.
- `CRAFT_REAL_FIXTURES=1 CRAFT_CS6_PRESETS=... uv run --extra dev pytest -m real`: 17 passaram, separados dos sintéticos.
- `uv run --extra dev ruff check .`: passou. `uv run --extra dev mypy`: 40 arquivos, sem erros.
- Harness nativo FilmCraft recompilado: cinco componentes em quatro presets,
  26 parâmetros estáticos; comparação completa do EffectPreset após importação.
  Zero keyframes reais preservados; curvas continuam recusadas.
- Wheel 0.15.0 em ambiente Python 3.12 separado sem PySide6: 35 mapas e saída
  do preset real conferidos; caminho site-packages confirmado.
- Wheel/sdist/desktop gerados; nenhum FFX/PRFPSET/PRTL/OFP/AEX/ECProj ou pacote
  privado/exterior distribuído. Todos os 144 hashes originais permanecem iguais.
- Build Qt Linux abre no smoke offscreen por cinco segundos, encerrado pelo
  mantenedor; isso não certifica Windows/macOS nem comparação visual Adobe.

Evidências locais ignoradas: artifacts/public-prfpset-research/native-readback.txt,
report.json, artifacts/distribution-audit-v0.15.0.json e wheel-audit-v0.15.0.json.
[ADR 016](decisions/016-premiere-cs6-legacy.md).

## Continuous Bezier — 0.15.1

Preset S_Shake selecionado real: 11 propriedades/12 chaves conferidas na
Session nativa própria, incluindo Amplitude antes recusada. Quatro lados
Bezier e três samples intermediários conferidos; projeto salvo/reaberto,
propriedade não selecionada, UID, índice, enabled e composição ativa
preservados. Engine em 47.952 fps sem arredondar tempos. Sem comparação
visual Adobe, perda de vínculo de edição explícita, strict continua recusado.
[ADR 017](decisions/017-continuous-bezier-endpoints.md).

Checks da 0.15.1: 398 testes regulares passaram, 18 testes reais opt-in passaram
separadamente, Ruff passou e Mypy não encontrou erros em 40 arquivos. Com todas
as extensões, 3105 propriedades/486 chaves, 119 parciais/25 sem conversão completa;
zero SUCCESS. Wheel headless instalado e build/smoke Linux verificados;
artifacts/coverage-and-integrity-v0.15.1.json guarda a integridade dos originais.

## Modulation — 0.16.0

Dois snapshots reais ADBE Checkout/Modulation comprovam 12 controles cada.
A Session oficial carregou o WASM original e preservou 24 propriedades e seis
chaves Linear após salvar/reabrir. Doze valores intermediários foram conferidos
contra cálculo independente; não há lados Bezier nesses dois streams reais.

O loader oficial com strict_render passou em 22 casos: 19 sintéticos, dois
conjuntos reais de controles aplicados a pixels originais de teste e Full HD
1920×1080 (~14,6 s nesta máquina). Dez testes Rust e Clippy passaram. Rebuild
Rust 1.98.1 reproduziu exatamente o módulo de 41345 bytes, SHA-256
90e0ff9f7a636849dff34f9fd363bebbca91ed36250efd9c467264c788398ee8.
Não há comparação visual com Modulation/Adobe; filtros, frequências, alpha,
HDR/gama e algoritmos são perdas permanentes. Strict não publica resultados parciais.

Checks: 409 testes regulares passaram, 19 reais opt-in passaram separadamente;
Ruff e Mypy passaram (41 arquivos). Com todas as extensões: 120 PARTIAL,
24 UNSUPPORTED, 3129 propriedades/492 chaves; zero SUCCESS. Builtin permanece
75/69, 1370/17 e 35 mapas. Os 144 hashes originais foram reconferidos.

Evidências privadas ignoradas: artifacts/modulation-v0.16/native/,
modulation-renderer-v0.16-final/, modulation-build-audit-v0.16.json,
coverage-and-integrity-v0.16.0.json. Nenhum preset privado é distribuído.
[Uso](modulation-extension.md), [ADR 018](decisions/018-approximate-modulation-renderer.md).

## Glint — 0.17.0

Dois snapshots reais S_Glint comprovam 25 controles. A Session oficial carregou
o WASM original e preservou 50 propriedades/12 chaves Linear (uma de cor) após
salvar/reabrir. Quinze valores intermediários escalares foram conferidos com
cálculo independente; nenhum lado Bezier real neste perfil.

O loader oficial strict_render passou em 30 casos: 27 sintéticos, dois conjuntos
reais de controles sobre pixels originais e Full HD 1920×1080 (~23,2 s).
Onze testes Rust e Clippy passaram. Rebuild Rust 1.98.1 produziu módulo de
36475 bytes idêntico, SHA-256
f84aeec072792b26c128e1e6910b5721c981514a053bb42a972826ed6326a674.
Sem comparação visual com Sapphire/Adobe. Background/Matte/Mocha, kernels,
calibração, alpha/HDR/gama e limites do quadro continuam perdas permanentes;
strict não publica o resultado parcial.

Checks: 421 testes regulares passaram, 20 reais opt-in passaram separadamente;
Ruff e Mypy passaram (42 arquivos). Com todas as extensões: 121 PARTIAL,
23 UNSUPPORTED, 3179 propriedades/504 chaves; zero SUCCESS. Builtin permanece
75/69, 1370/17 e 35 mapas. Os 144 hashes originais foram reconferidos.

Evidências privadas ignoradas: artifacts/glint-v0.17/native/, glint-renderer-v0.17/,
glint-build-audit-v0.17.json, coverage-and-integrity-v0.17.0.json.
Nenhum preset privado é distribuído. [Uso](glint-extension.md),
[ADR 019](decisions/019-approximate-glint-renderer.md).

## Pixel Sort — 0.18.0

Um snapshot real S_PixelSort Linear comprova 24 controles estáticos. A Session
oficial carregou o WASM original e preservou todas as propriedades após
salvar/reabrir, incluindo centros [960,540] para camada 1920×1080 e seed
0,2729949951171875 exato. Não há keyframes reais PixelSort. Radial/Circular
e animação têm somente testes sintéticos.

O loader oficial strict_render passou em 48 casos: 46 sintéticos, um conjunto
real de controles sobre pixels originais e Full HD a 37° 1920×1080 (~41,4 s).
Treze testes Rust e Clippy passaram. Rebuild Rust 1.98.1 reproduziu módulo de
65983 bytes, SHA-256
ce3bcff7461ab5dd2e292bfae7a5cb87112e2117affc0a27960b63bb973135b0.
Sem comparação visual com Sapphire/Adobe. Matte/Mocha, geometria/PRNG,
calibração, HDR/gama/alpha e canvas continuam perdas; strict não publica.

Checks: 436 testes regulares passaram, 21 reais opt-in passaram separadamente;
Ruff e Mypy passaram (43 arquivos). Com todas as extensões: 122 PARTIAL,
22 UNSUPPORTED, 3203 propriedades/504 chaves; zero SUCCESS. Builtin permanece
75/69, 1370/17 e 35 mapas. Os 144 hashes originais foram reconferidos.

Evidências privadas ignoradas: artifacts/pixelsort-v0.18/native/,
pixelsort-renderer-v0.18-final/, pixelsort-build-audit-v0.18.json,
coverage-and-integrity-v0.18.0.json. Nenhum preset privado é distribuído.
[Uso](pixelsort-extension.md), [ADR 020](decisions/020-approximate-pixelsort-renderer.md).


## Flicker — 0.19.0

Um snapshot completo S_Flicker fornece 14 controles estáticos. Um grupo
selecionado fornece três propriedades/três chaves isoladas em zero, com base
temporal 21504. Na Session oficial descartável, ambos foram aplicados, salvos
por file.saveAs e conferidos após file.open. O grupo manteve UID/índice/enabled
e um controle não selecionado com sentinel próprio não default; composição
inativa e outra composição intacta também foram verificadas. Não existe
segmento real com múltiplas chaves para samples intermediários nesta evidência.

Nove testes Rust e Clippy passaram. Rebuild Rust 1.98.1 foi byte idêntico:
WASM 29038 bytes, SHA-256
eaef76f15dc77f40ff6884c885eaf60418937bcec175d065c61011048f2759ff.
Loader WASM oficial passou em 31 casos: 26 casos sintéticos pequenos, quatro
execuções de dois conjuntos reais de controles sobre pixels próprios e Full HD
(~2,2 s). Seno, identidade/HDR/alpha, ruído compartilhado/independente, seed
fracionário, tempos negativos/fora de ordem, continuidade e limites foram
verificados. No teste de pixels do grupo selecionado, controles ausentes usam
defaults próprios; isso não prova o estado não salvo do plugin original.

449 testes gerais passaram, 22 reais opt-in separados; Ruff e Mypy passaram
(44 módulos). Corpus com todos os opcionais: 122 PARTIAL/22 UNSUPPORTED,
3220 propriedades/507 chaves, nenhum SUCCESS; 144 hashes originais inalterados.
Nenhuma equivalência visual certificada. Builtin permanece 35 mapas e 75/69.

Evidências privadas ignoradas: artifacts/flicker-v0.19/{native,selected}/,
flicker-renderer-v0.19/, flicker-build-audit-v0.19.json,
coverage-and-integrity-v0.19.0.json. Nenhum preset privado é distribuído.
[Uso](flicker-extension.md), [ADR 021](decisions/021-approximate-flicker-renderer.md).


## Median — 0.20.0

Três snapshots completos BCC3Median forneceram 30 controles estáticos. Uma
Session oficial descartável nova carregou o módulo final e confirmou cada
valor após aplicação e file.saveAs/file.open. Os casos reais usam ARGB separado,
Length=100/Width=3, ângulos 45°/108°/138°; outros modos/canais e animações são
verificados apenas com dados sintéticos. Não houve comparação visual Adobe.

15 testes Rust e Clippy passaram, incluindo redes versus ordenação independente,
362880 permutações de nove entradas, 32768 sequências binárias de quinze,
HDR/subnormais/alpha, janela/rotação/fractional, limites e ABI inválido sem
mutação. Gerador das redes e rebuild Rust 1.98.1 foram byte idênticos:
WASM 79804 bytes, SHA-256
7983570ed85dd4c71fc6f3419e0a305651f03039b4d49c78b28fb451ff553139.

Loader WASM oficial passou em 41 casos: 37 sintéticos, três conjuntos reais
sobre pixels próprios e Full HD uniforme com um impulso (~55.0 s).
Quatro modos passaram com raios máximos fracionários e alpha variável em
320×180. O Full HD é teste de correção de uma imagem quase uniforme, não
benchmark geral. Entradas maiores usam até 36 taps por pixel sem alterar as
proteções de fuel/memória da engine; essa amostragem é uma perda declarada.

462 testes gerais passaram; 23 reais opt-in passaram separadamente. Ruff e
Mypy passaram (45 módulos). Com todas as extensões e Flare local: 123 PARTIAL,
21 UNSUPPORTED, 3250 propriedades/507 chaves; nenhum SUCCESS. Os 144 hashes
originais foram reconferidos. Builtin permanece 35 mapas e 75/69, 1370/17.

Evidências privadas ignoradas: artifacts/median-v0.20/native-release/,
median-renderer-v0.20-final36/, median-build-audit-v0.20.json e
coverage-and-integrity-v0.20.0.json. Nenhum preset privado é distribuído.
[Uso](median-extension.md), [ADR 022](decisions/022-approximate-median-renderer.md).


## Directional Blur — 0.21.0

Três snapshots BCC3Directional Blur transferiram 36 valores estáticos. Uma
Session oficial descartável nova carregou o módulo final otimizado, aplicou
três componentes e confirmou todas as propriedades após file.saveAs/file.open.
Os casos reais usam Normal/RGBA e Amount/Angle/Avoid Clipping 67/0°/false,
31/90°/true e 72/90°/true. Outros modos/canais e animação só têm testes sintéticos.

13 testes Rust/Clippy passaram. Convolução da linha foi comparada a uma
referência independente; offsets/pesos agrupados foram comparados ao cálculo
bilinear direto em 16 combinações. Limiares, alpha/HDR, mistura, Thin/Spread,
scale/rotação, nove canais, 27 modos e ABI inválido sem mutação foram verificados.
Rebuild Rust 1.98.1 byte idêntico: WASM 43712 bytes, SHA-256
7552b1ef82f1195c987d3511bcd426e903edfe98b5eab793049ceb7022ab4f30.

Loader WASM oficial passou em 86 casos: 82 sintéticos, três conjuntos reais
sobre pixels próprios e Full HD com checker original não uniforme (~96.3 s).
O Full HD usa Amount=96,7, Angle=137,3° e 31 taps. As 27 misturas passaram
em 320×180 com textura RGBA variável. O teto de taps e proteções de fuel/memória
foram conservados. CPU/WASM ainda é lento para preview; a medição não certifica
outros conteúdos ou máquinas. Nenhuma renderização/comparação Adobe foi feita.

478 testes gerais passaram; 24 reais opt-in passaram separadamente; Ruff e
Mypy passaram (46 módulos). Os testes de transferência/CLI foram repetidos com
o módulo final otimizado. Com todos os opcionais: 124 PARTIAL/20 UNSUPPORTED,
3286 propriedades/507 chaves, nenhum SUCCESS. Os 144 hashes originais foram
reconferidos. Builtin continua 35 mapas, 75/69 e 1370/17.

Avoid Clipping não expande os limites do canvas neste ABI: essa diferença,
calibração/mistura/amostragem e máscaras/audio continuam perdas no relatório.
Evidências privadas ignoradas: artifacts/directional-v0.21/native-final/,
directional-renderer-v0.21-optimized/, directional-build-audit-v0.21-final.json
e coverage-and-integrity-v0.21.0.json. Fixtures privadas não são distribuídas.
[Uso](directional-extension.md), [ADR 023](decisions/023-approximate-directional-renderer.md).


## S_Sharpen — 0.22.0

Uma instância real preservou 15 valores estáticos, Best/Normal, em uma nova
Session descartável. O módulo final foi carregado por effect.plugins.load e
prop.get confirmou os valores após aplicação e file.saveAs/file.open. Nenhuma
máscara foi presumida vazia. Show Small Detail Size é widget da origem e
permanece perda de edição; menus alternativos/animação são somente sintéticos.

11 testes Rust e Clippy passaram. Box fracionário foi comparado à soma direta
independente em ambos os eixos, inclusive com raio maior que a imagem. Bandas,
threshold/amplitude negativa, luma/chroma/canais, alpha/HDR/invisibilidade,
scale/tempo e chamadas inválidas sem mutação foram verificados. Rebuild
Rust 1.98.1 byte idêntico: WASM 30003 bytes, SHA-256
d193ca442e5dbf08acc33cd584635005b0d82e318212dc13ac70cbc14bf64599.

O loader oficial passou em 32 casos WASM distintos: referência independente
Best/Fast nos três modos Opacity, cada banda/canal, alpha/HDR/limites, controles
reais sobre pixels originais e três quadros não uniformes. Full HD Best ~44,8 s,
Fast ~15,2 s; 3840×2160 Best ~232,7 s. Essas medições locais não certificam
outras máquinas/conteúdos. 4K foi executado com outras verificações simultâneas.
Fuel e memória da engine não foram alterados; o box usa todas as amostras,
sem reduzir o filtro a taps esparsos. CPU/WASM ainda é lento para preview.
Nenhuma renderização/comparação visual Sapphire/Adobe foi realizada.

495 testes gerais passaram (25 reais separados); Ruff e Mypy passaram
(47 módulos). 25 testes reais opt-in passaram com CRAFT_REAL_FIXTURES e
CRAFT_CS6_PRESETS explícitos. Com os 11 opcionais e Flare local: 124 PARTIAL,
20 UNSUPPORTED, 3301 propriedades/507 chaves; nenhum SUCCESS. Os 144 hashes
originais foram reconferidos. Builtin continua 35 mapas, 75/69 e 1370/17.

Evidências privadas ignoradas: artifacts/sharpen-v0.22/native/,
sharpen-renderer-v0.22/, sharpen-renderer-v0.22-uhd/,
sharpen-build-audit-v0.22.json e coverage-and-integrity-v0.22.0.json.
Fixtures privadas não são distribuídas. Suporte universal permanece pendente.
[Uso](sharpen-extension.md), [ADR 024](decisions/024-approximate-sharpen-renderer.md).


## Layer nativo — 0.23.0

527 testes gerais passaram; 25 reais opt-in passaram separadamente com
CRAFT_REAL_FIXTURES/CRAFT_CS6_PRESETS explícitos. Ruff/Mypy passaram (47 módulos).
Os 32 novos casos de protocolo/CLI usam planos originais sintéticos e verificam
v4/tipos, bindings, catálogo, recusas, UIDs grandes sem arredondar e unbind.

Uma Session oficial descartável aplicou 42 efeitos/71 propriedades Layer,
resolveu o UID de uma camada própria, conferiu o tipo e persistiu/reabriu
todos os vínculos. Unbind em instância existente preservou seu UID. Uma
composição inativa foi preservada; self/camada ausente recusaram sem mutação.
O helper layer-render usa a biblioteca de efeitos e um EffectHost próprio
com duas imagens originais. Copy/Add/Multiply pediram o UID exato e os pixels
foram comparados com resultados independentes. Não houve render.frame do
aplicativo nem render/comparação Adobe. Esses resultados não validam os
algoritmos completos dos 42 efeitos.

Os 144 arquivos originais permanecem intactos. Com os opcionais, cobertura
continua 124 PARTIAL/20 UNSUPPORTED, 3301 propriedades/507 chaves. Os blobs
Layer FFX permanecem desconhecidos e o WASM API v1 não ganhou entrada adicional.
Evidências ignoradas: artifacts/layer-resources-v0.23-final/ e
coverage-and-integrity-v0.23.0.json. [Uso](layer-resources.md),
[ADR 025](decisions/025-native-layer-bindings.md).

## 0.23.1 — perdas de origem nos relatórios

535 testes gerais passaram; 26 testes reais opt-in passaram separadamente.
Ruff e Mypy (47 módulos) passaram. Regressões cobrem ausência de mapa, recurso
incompatível, bloco incompleto, dados obrigatórios ausentes/recusados, duplicação,
mutação do IR, caminho explícito, aviso sem perda, HTML escapado e strict.

Auditoria dos 144 arquivos preservou todos os 1341 avisos relevantes de
parâmetros. 353 eram omitidos anteriormente em 65 instâncias sem mapa,
incluindo seis expressões, duas KEYFRAME_LAYOUT e uma MESH_RENDER_UNSUPPORTED.
Os SHA-256 continuam iguais ao inventário inicial. Cobertura com todos os
opcionais permanece 124 PARTIAL/20 UNSUPPORTED, 3301 propriedades/507 chaves.
Sem novo mapa, renderer ou certificação de equivalência visual nesta correção.

## Colorize — 0.24.0

556 testes gerais passaram; 27 reais opt-in passaram separadamente. Ruff e
Mypy passaram (48 módulos). Novos testes de mapa verificam 23 controles,
cores ARGB→RGBA, menus, Input PixelChooser recusado, dados obrigatórios,
perdas, strict e animações sintéticas. O CLI instala o pacote sem carregar
código nem depender de Adobe.

11 testes Rust/Clippy passaram. O módulo final teve rebuild byte idêntico
com Rust 1.98.1. 60 casos WASM no loader oficial com render direto estrito
conferiram pixels próprios contra referência independente colorsys, incluindo
cor quase zero/HSL, alpha/HDR, looping, 24 combinações Input/Color Space,
quatro conjuntos reais de controles e dois quadros grandes não uniformes.
Full HD ~5,6 s; UHD ~22,2 s, sem ampliar fuel ou memória do loader.

Uma Session nativa descartável carregou o módulo final: quatro componentes
BCC3Colorize, 23 controles cada, 92 valores estáticos conferidos após
salvar/reabrir. Não houve render.frame da aplicação nem comparação BCC/Adobe.
Evidência ignorada: artifacts/colorize-v0.24/native-final/,
colorize-renderer-v0.24-final/ e colorize-build-audit-v0.24.json.

Com os 12 opcionais e Flare local: 124 PARTIAL/20 UNSUPPORTED,
3393 propriedades/507 chaves. Os 144 hashes originais foram reconferidos.
Os quatro Colorize pertencem a arquivos já parciais; quantidade de arquivos
não muda. Builtin permanece 75 PARTIAL/69 UNSUPPORTED, 1370/17. Recursos de
máscaras/tracking e fidelidade visual continuam pendentes; strict não publica
planos parciais. [Uso](colorize-extension.md), [ADR 027](decisions/027-approximate-colorize-renderer.md).

## Host multientrada experimental — desenvolvimento, 09/10/2026

21 testes Rust passaram: seis upstream API 1 e 15 novos de transporte/recusa.
Clippy do plugin com `-D warnings` passou. Uma Session com o host alterado
renderizou camada vermelha substituída pela entrada verde em 8×4 e preview
4×2, conferiu tipo/UID Layer e preservou pixels/vínculo após salvar/reabrir.
Os 12 módulos API 1 distribuídos continuaram carregando.

Preparação em exportação nova foi comparada byte a byte nos seis arquivos do
patch. Quatro regressões Python verificam aplicação efetiva dentro/fora de
repositório pai, recusa de saída existente/pesquisa e falha sem publicação.
`uv run --extra dev pytest`: 560 passed/27 skipped; Ruff e Mypy passaram.
Os 144 hashes privados e a pesquisa original foram reconferidos intactos.
Nenhuma amostra Adobe, novo decoder ou mapa foi usado neste teste; amostras
reais continuam opt-in e não foram reexecutadas nesta etapa de infraestrutura.
Contadores permanecem 124 PARTIAL/20 UNSUPPORTED, 3393 propriedades/507 chaves.
Não houve build de lançamento nem publicação do EffectCraft alterado.
Veja [contrato e reprodução](experimental-multi-input-host.md).

## Integração do Bridge com API 2 — 0.25.0

602 testes gerais/27 reais opt-in passaram; Ruff/Mypy (48 arquivos) e Clippy
do probe nativo com `-D warnings` passaram. O host experimental ADR 028 não
foi alterado nesta etapa. API 1/fingerprint foi comparado com o wheel headless
0.24.0. Manifestos/planos/capacidades e UID exato têm regressões independentes;
campos ausentes ou divergentes recusam aplicação antes de criar efeitos.

`scripts/validate_multi_input_plan.py` iniciou apenas seu próprio processo
de engine descartável e aplicou planos reais pelo adaptador Bridge: três
propriedades estáticas, duas chaves Linear, seis samples em full/half,
save/reopen e unbind de instância existente. A animação não selecionada foi
comparada antes/depois integralmente. As imagens, manifesto e WAT são próprios;
o projeto usa 32 bpc e comparação exata de pixels. Não há comparação Adobe.
O único helper de pixels pertence ao probe e chama Session::render.

Os 144 hashes originais foram conferidos intactos; não houve novo mapa de
origem e os contadores permanecem 124 PARTIAL/20 UNSUPPORTED, 3393/507.
O patch de host é opt-in separado; o executável Bridge não instala nem altera
o EffectCraft do usuário. [ADR 029](decisions/029-api2-layer-plan-integration.md).

## MathOps/substituições — 0.26.0

Passaram 627 testes gerais (28 reais separados/skip), 28 reais opt-in, Ruff,
Mypy em 50 módulos, 12 testes Rust e Clippy com warnings como erro. O teste
real comprovou quatro instâncias: 60 valores decodificados e oito substituições
manuais, com A Darks=-0,04/Blur Mask=12 e avisos de path/Mocha preservados.
Isso não comprova a reconstrução dos vínculos originais nem fidelidade visual.

`scripts/validate_mathops_renderer.py` usa somente imagens/IR próprios, inicia
seu probe e aplica planos pelo Bridge/TCP. Comprovou 23 casos/50 samples em
full/half, 17 operações, máscara preta/branca/invertida, Source B null explícito,
animação Linear e projeto reaberto. Testes Rust incluem máscara não uniforme,
blur fracionário, offsets/scale, alpha/HDR e descritores/entradas inválidas.
Não foi medido Full HD; limites não são uma promessa de desempenho.

Auditoria automática dos 144 originais, sem escolhas manuais de recurso:
124 PARTIAL/20 UNSUPPORTED, 3393 controles/507 chaves. Todos os hashes e
1341 avisos de parâmetros relevantes permaneceram. Os 12 fingerprints e
módulos API 1 existentes são idênticos ao wheel 0.25.0; .research não mudou.
A versão traz uma extensão aproximada opt-in, não suporte universal completo.


## 0.27.0 — Dissolve Shake e host temporal experimental

`uv run --extra dev pytest`: 653 passed/29 skipped (amostras reais opt-in).
Ruff e Mypy (51 arquivos) passaram. Testes reais são executados separadamente
com CRAFT_REAL_FIXTURES=1 e CRAFT_CS6_PRESETS para a referência pública local:
29 passed/653 deselected. A prova de Session reúne 17 casos próprios, incluindo
Background alterado no mesmo instante, sem reutilizar imagem antiga.
Onze testes Rust do renderer e 27 do host/API 1/2/3 passaram; Clippy do
renderer, plugin e transporte/engine de render passou sem avisos próprios.

A Session descartável verifica dissolve/direction/speed/null, Auto Trans com
trim/start/stretch/reverso/frame único, Linear e projeto reaberto, controles
selecionados sem alterar recursos/chaves e onda sobre gradiente não uniforme,
full/half. São imagens de teste originais, sem comparação Adobe. O probe
legado API 2 preserva pixels, vínculo/reabertura e carrega 12 módulos API 1.

Auditoria: 144 hashes intactos; 129 PARTIAL/15 UNSUPPORTED sem vínculos manuais,
3441 controles/561 chaves e 1341 avisos relevantes preservados. Nos quatro
snapshots de Dissolve Shake, Background continua opaco: são 160 controles
mais quatro substituições explícitas e 13 chaves; nos cinco grupos, 48/54.
Patch revisão 2 reproduzido em cópia limpa: sete arquivos upstream alterados,
três novos originais e 928 arquivos upstream byte a byte preservados. API 3
é experimental; suporte universal e fidelidade visual seguem não comprovados.


## 0.28.0 — Heatwave original opt-in

`uv run --extra dev pytest`: 667 passed/30 skipped. A execução real separada,
com CRAFT_REAL_FIXTURES=1 e a referência pública CRAFT_CS6_PRESETS, passou em
30 testes. Ruff, Mypy (52 arquivos) e Clippy do renderer passaram; 11 testes
Rust próprios verificam ruído, blur, máscaras, geometria, extremos e recusas.

Session descartável: 18 casos sintéticos full/half, três tipos de ruído,
três qualidades, máscaras None/Ellipse/Rectangle/Layer, luma/alpha, null e
inversão, atualização auxiliar no mesmo instante, Linear e projeto reaberto.
O 19º caso opt-in usa 24 controles reais + uma substituição explícita,
conferidos pela API e após reabertura; a imagem é um gradiente original,
nunca filmagem do usuário. Alpha null é devolvido como null pelo prop.get,
não como UID inteiro zero. Nenhuma comparação Adobe/Universe foi feita.

Os 144 hashes e 1341 avisos relevantes permanecem; corpus sem vínculos
continua 129 PARTIAL/15 UNSUPPORTED, 3441 controles/561 chaves. A nova criação
exige recurso/tamanho/controles íntegros; não se promove cobertura escolhendo
None implicitamente. Host experimental e módulos anteriores são preservados.


Também foi reproduzido e corrigido o cache de API 1 temporal com controles
estáticos: 15 samples Flicker originais full/half, reabertura e time reverse.
Os 27 testes host/API 1/2/3, Clippy e prova nativa de API 2 passaram após a
correção. Patch reproduzido em cópia limpa com 928 arquivos upstream intactos;
14 mapas/módulos e fingerprints instalados permaneceram iguais à 0.27.0.
A correção está no host experimental; o aplicativo oficial não foi modificado.


## 0.29.0 — Signal original opt-in

`uv run --extra dev pytest`: 677 passed/31 skipped. Execução separada com
CRAFT_REAL_FIXTURES=1 e CRAFT_CS6_PRESETS: 31 passed. Ruff, Mypy (53 arquivos)
e Clippy passaram; dez testes Rust e dez testes Python do novo renderer/mapa.
Um teste real opt-in comprova tipos, valores, unidades ausentes e ordem dos
menus em dois snapshots. Destruction button não foi traduzido.

Session experimental descartável: 13 casos próprios em full/half, pixels
neutros contra o gradiente da engine, amplificação/modulação analíticas,
menus, ruído repetível com pedidos fora de ordem, tempo reverso, animação
Linear e grupo selecionado preservando chaves. Dois casos reais adicionais
conferem 68 valores aplicados, persistidos/reabertos e renderizados sobre
imagens originais. Sem imagens Adobe ou comparação visual de origem.

Corpus com todas as extensões opcionais e perfil local flare, sem vínculos
manuais: 131 PARTIAL/13 UNSUPPORTED, 3509 controles/561 chaves. 144 hashes e
1341 avisos relevantes intactos. Os 15 mapas/módulos e fingerprints anteriores
permaneceram byte a byte equivalentes à wheel 0.28.0; patch host inalterado.
Wheel/sdist e desktop Linux conferidos contra os arquivos de origem, sem
presets privados; instalação wheel Python 3.14 headless sem Qt e lançamento
Qt offscreen verificados. Nenhuma promessa de desempenho Full HD ou suporte
universal. [Uso e limites](signal-extension.md).


## 0.30.0 — transporte de imagens temporais

Checks obrigatórios: 702 testes gerais passaram, 31 reais opt-in passaram
separadamente, Ruff passou e Mypy conferiu 53 arquivos. São 25 novos testes
de manifesto/plano/preflight; nenhum deles é tratado como preset Adobe real.
36 testes Rust do plugin passaram; Clippy all-targets passou. A suite opcional
`effectcraft-host --test plugins` não executou offline porque `boa_ast 0.22.0`
não estava no cache; não é contabilizada como validada.

23 verificações na Session real confirmaram imagens originais do prefixo em
outros instantes; 17 casos API 3 de DissolveShake passaram na mesma engine.
A reprodução do patch preservou 927 arquivos upstream, alterou oito e
acrescentou quatro originais. Hash SHA-256 do patch:
`5378bc4a887f96353821742a031365c6713f3e3378009cc2522631792823a7db`.
Os 16 mapas, WASM e fingerprints existentes foram comparados byte a byte
ou semanticamente com o wheel instalado 0.29.0 e permanecem iguais.

A auditoria dos 144 FFX confirmou 131 PARTIAL/13 UNSUPPORTED, 3509 controles,
561 chaves e 1341 avisos relevantes preservados. Hashes de origem intactos.
Não há novo mapa Adobe nem comprovação de equivalência visual.
[Contrato API 4 e limites](temporal-input-host.md).


## 0.31.0 — Geometric Filter original aproximado

710 testes gerais passaram, 32 reais opt-in passaram separadamente; Ruff e
Mypy (54 arquivos) passaram. Dez testes Rust e Clippy all-targets passaram.
Treze casos na Session experimental real confirmaram seis formas full/half,
cinco tempos retidos do prefixo animado, reabertura e 21 valores estáticos
reais persistidos/reabertos em imagem própria. Um workload Full HD de 1000
triângulos, uma recursão, fonte uniforme e fundo desligado levou ~5,1 s no
loader WASM nativo; não é benchmark geral nem comparação Adobe.

Auditoria dos 144 FFX: 132 PARTIAL/12 UNSUPPORTED, 3530 controles/561 chaves,
1341 avisos relevantes e hashes preservados. Um arquivo antes UNSUPPORTED
agora é parcial; estilos/hidden e fidelidade continuam perdas.
[Modelo, instalação e limites](geometric-extension.md).


## 0.32.0 — Pixel Encoder original aproximado

718 testes gerais passaram e 33 reais opt-in passaram separadamente.
Ruff e Mypy (55 arquivos) passaram; seis testes Rust e Clippy all-targets
passaram. Treze casos de Session real confirmam dez padrões full/half, cor/
transparência, tempo fora de ordem/reabertura e 16 valores reais persistidos
sobre pixels próprios. Um workload Full HD de glifos originais sobre fonte
uniforme com marcadores vermelho/azul levou ~3,5 s no loader WASM nativo;
saída finita com 866304 pixels foreground e 1207296 background. Não é
benchmark geral ou comparação visual Adobe.

O lote permanece 132 PARTIAL/12 UNSUPPORTED; agora 3546 controles/561 chaves.
144 hashes e 1341 avisos relevantes preservados. Os estilos são originais
e a fidelidade permanece perda. [Modelo e limites](pixelencoder-extension.md).


## 0.33.0 — Hotspots original aproximado

726 testes gerais passaram e 34 reais opt-in passaram separadamente.
Ruff e Mypy (56 arquivos) passaram; sete testes Rust e Clippy all-targets
passaram. Onze casos na Session real verificaram máscaras branca/preta/cinza,
luma/alpha, inversão, três modos de opacidade, reabertura e nove controles
reais com substituição explícita por sem máscara sobre pixels próprios.
Um workload Full HD uniforme com Blur Input=12 levou ~8,9 s no loader WASM
nativo; todos os pixels foram conferidos contra o resultado analítico.
Não é benchmark geral nem comparação visual Adobe.

O lote automático permanece 132 PARTIAL/12 UNSUPPORTED, 3546 controles e
561 chaves: nenhuma máscara opaca é removida por suposição. Os 144 hashes
e 1341 avisos relevantes foram preservados. [Modelo e limites](hotspots-extension.md).


## 0.34.0 — HitFilm Hotspots original aproximado

733 testes gerais passaram e 35 reais opt-in passaram separadamente.
Ruff e Mypy (57 arquivos) passaram; seis testes Rust e Clippy all-targets
passaram. Nove casos na Session real verificam highlights/fill, cor/alpha,
brilho, suavização, full/half, reabertura e os cinco valores de cada um de
dois presets reais sobre pixels próprios. Um workload Full HD uniforme,
Smooth Source=12, levou ~7,6 s no loader WASM nativo; todos os pixels foram
conferidos analiticamente. Não é benchmark geral nem comparação HitFilm.

Auditoria: 144 FFX, 132 PARTIAL/12 UNSUPPORTED, 3556 controles/561 chaves.
Dez controles adicionais; arquivos já parciais, sem promoção indevida dos
status. Hashes e 1341 avisos relevantes preservados. [Modelo e limites](hfhotspots-extension.md).


## 0.35.0 — OLM anisotrópico e recurso comprovadamente inativo

754 testes gerais passaram; 36 reais opt-in passaram separadamente.
Ruff e Mypy (58 arquivos) passaram; nove testes Rust e Clippy all-targets
passaram. Os 21 casos Python novos incluem recusa de animação/expressão
no seletor e no recurso: inatividade não ignora esses riscos de tradução.
Doze casos na Session real verificam impulso próprio, front/back/vertical,
alpha fade, três recursos de ruído, size variation, dois modos de ruído,
full/half, ordem temporal, reabertura e 14 controles reais persistidos.
O recurso Smooth foi comprovadamente inativo; nenhum vínculo foi decodificado.

Workload Full HD opaco uniforme Front=140/Angle=106 levou ~1,8 s e manteve
todos os pixels analíticos. A regra de preservar detalhe opaco pula os raios
nessa cena; não comprova desempenho em cena transparente nem benchmark geral.
ZIP/manual oficial consultado, sem fonte disponível, nenhum .aex executado
ou distribuído. [Modelo, evidência e limites](olmdirectional-extension.md).

Auditoria de 144 FFX: 132 PARTIAL/12 UNSUPPORTED, 3571 controles/561 chaves;
144 hashes e 1341 avisos de origem relevantes preservados. São 14 controles
e uma entrada Layer de transporte adicionais em um arquivo já parcial.
Calibração/fidelidade e demais efeitos ainda exigem trabalho para o objetivo
universal; nenhuma comparação Adobe/OLM foi certificada.
