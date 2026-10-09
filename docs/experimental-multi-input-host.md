# Host experimental para múltiplas imagens

Esta extensão de desenvolvimento altera uma **cópia** do EffectCraft fixado em
`e38a92e792c07f1c57c5dcfcab37d91932b9e2b8`. Não é a ABI oficial do upstream,
não modifica `.research`, não instala nada no aplicativo do usuário e não
acrescenta um mapa Adobe. O Bridge 0.25.0 aceita manifestos API 2 com
`bridge_host_revision:1` e planos v4 com vínculos Layer explícitos. A aplicação
exige comprovação dessa capacidade no host; o EffectCraft oficial API 1 é recusado.

O obstáculo concreto é que a ABI oficial API 1 transporta uma única imagem.
O `EffectHost` nativo já pode fornecer camadas, mas o wrapper de plugins perde
esse contexto. A extensão oferece um método adicional com contexto, preserva
o método legado e transmite até quatro imagens auxiliares. A resolução usa
`EffectCtx::layer_param`, incluindo o seletor nativo Source / Masks /
Effects & Masks e a recusa do host para referências ausentes ou recursivas.

## Preparar e verificar

Requisitos: checkout Git da referência fixada, Python 3.12 ou posterior com
extra `dev`, Rust **1.98.1** instalado e dependências Cargo disponíveis.
Execute na raiz do Bridge:

```sh
uv run --extra dev python scripts/prepare_effectcraft_multi_input.py
cargo +1.98.1 test --locked --manifest-path artifacts/effectcraft-multi-input/Cargo.toml -p effectcraft-plugin --features wasm --target-dir artifacts/native-target --config profile.dev.package.wasmi.opt-level=3
cargo +1.98.1 run --locked --manifest-path scripts/effectcraft-multi-input/probe/Cargo.toml --target-dir artifacts/native-target -- artifacts/multi-input-engine-proof
uv run --extra dev python scripts/validate_multi_input_plan.py artifacts/multi-input-plan-proof
```

Os diretórios de saída devem ser novos. O preparador exporta o objeto Git fixado,
aplica o patch após `git apply --check` e registra commit/hash do patch em
`bridge-host-provenance.json`. Ele publica a cópia somente após a preparação
completa e recusa sobrescrita ou saída dentro da pesquisa.

Se a cópia já estiver preparada, use os comandos Cargo sem repetir o preparador.
O probe usa a localização padrão `artifacts/effectcraft-multi-input`.

O probe gera um efeito de teste original, uma camada vermelha e outra verde;
compara os pixels antes/depois, verifica previews full/half, consulta o UID
Layer, salva/reabre pela engine e carrega as doze extensões API 1 distribuídas.
O resultado é um projeto sintético e `summary.json`, sem fixtures privadas.

O teste de plano adicional inicia seu próprio host descartável em porta local
efêmera e usa a CLI/API do Bridge: mistura estática, duas chaves Linear, seis
samples full/half, save/reopen e desvinculação explícita de uma instância
existente sem alterar a animação não selecionada. O projeto usa 32 bpc para
verificar os pixels exatos; o destino quantiza 0,5 para 128/255 em 8 bpc.
O helper `bridge.probe.render` só existe no probe de desenvolvimento e chama
Session::render; não é apresentado como comando oficial de renderização.

O [pacote de exemplo](examples/plugin-layer-package.json) e o
[plano estático](examples/plugin-layer-plan.json) usam um renderer original de
teste. Instalar o manifesto não carrega o módulo: o script gera/carrega o WAT
na sua Session descartável. Eles não declaram equivalência com um efeito Adobe.

Na criação, cada Layer declarado deve aparecer no plano, com referência simbólica
ou `{"layer_ref":null}` explícito. Null é preservado na instalação do pacote.
Instâncias existentes permitem alterar só os controles selecionados. Animação
de Layer continua recusada; a animação dos controles numéricos usa o adaptador
existente. Manifestos API 1/fingerprints legados permanecem compatíveis.

## Contrato API 2, revisão 1 (preservado)

Manifesto e `ec_api_version()` devem concordar em `2`. Manifestos API 1 continuam
usando `ec_render` e não podem declarar `type: "layer"`. API 2 exige
`ec_render_v2`; Layer tem default `null` e ocupa dois `f64` na declaração:
metade baixa e metade alta do UID, cada uma um inteiro exato `u32`. `(0,0)`
representa desvinculação explícita. Um valor desconhecido de FFX não constitui
essa evidência. UID positivo ligado mas indisponível retorna erro antes do WASM.

```text
ec_render_v2(pixels:i32, width:i32, height:i32,
             params:i32, nparams:i32, time:f64, scale:f64,
             table:i32, entries:i32) -> i32
```

O host faz uma única alocação alinhada a oito bytes. Ela contém parâmetros,
tabela e pixels: primeiro a imagem principal, depois as imagens auxiliares
ligadas. Pixels são RGBA `f32` premultiplicado, row-major, little-endian, no
mesmo espaço de trabalho entregue pelo host. As imagens podem ter dimensões,
offsets e escalas diferentes; o transporte não reamostra nem transforma cores.
A entrada zero da tabela descreve a imagem principal, seguida de cada parâmetro
Layer na ordem de declaração, inclusive os explicitamente desvinculados.

Cada descritor tem **80 bytes**, alinhamento oito, little-endian:

| Offset | Tipo | Campo |
|---|---|---|
| 0 | u32 | Índice do parâmetro no manifesto; `0xffffffff` para a imagem principal |
| 4, 8 | u32, u32 | Metades baixa/alta do UID; zero na imagem principal ou desvinculada |
| 12 | u32 | Flag: 1 principal, 2 auxiliar ligada, 0 desvinculada |
| 16 | u32 | Ponteiro de pixels; zero se desvinculada |
| 20, 24 | u32, u32 | Largura/altura do buffer |
| 28 | u32 | Reservado, zero |
| 32, 40 | f64, f64 | Offset em pixels de buffer, como em `Buf::to_px` |
| 48 | f64 | Pixels de buffer por pixel de camada |
| 56, 64 | f64, f64 | Tamanho original da camada em pixels |
| 72 | u64 | Reservado, zero |

Campos geométricos da entrada desvinculada são zero. Buffers ligados devem ter
dimensões positivas até 65536 por eixo, no máximo 8.388.608 pixels por imagem
e 33.554.432 pixels somados. Offset/time devem ser finitos até magnitude 1e9;
tamanho de camada deve ser positivo/finito até 1e9; escala entre 1/65536 e 16.
IDs tipados e metades achatadas devem concordar. Buffers e resultados devem ser
finitos. Erro, trap, limite de instruções, memória inválida ou resultado não
finito preservam integralmente a imagem do chamador.

A geometria segue exatamente `p_buffer = p_layer * scale + offset`; o offset
não é reinterpretado como uma distância em pixels de camada.

Memória WASM permanece limitada a 1 GiB, sem imports. O combustível mantém
50 milhões de instruções base mais 20 mil por pixel transportado. Isso limita
o processamento; não estabelece desempenho interativo.

`effect.plugins.list` preserva `api:1` legado e adiciona `apis:[1,2]`,
`bridge_host:{revision:1,layer_inputs:4}` e o `api` individual dos plugins.
`effect.plugins.load` retorna a versão real do manifesto. Um consumidor futuro
deve verificar essa capacidade experimental explicitamente, sem inferi-la da
versão de lançamento ou do catálogo nativo.

## Limites de compatibilidade

Os testes comprovam transporte, aplicação e execução de imagens próprias. Não implementam
S_DissolveShake ou S_MathOps, não decodifica suas referências FFX, não certifica
fórmulas, animações ou equivalência visual Adobe e não altera os contadores do
corpus. Permanecem necessários vínculos comprovados de origem e renderers
dos efeitos com limites/evidência. A partir de 0.26.0, Rule Layer aceita somente substituição explícita de recurso,
fixada ao arquivo e registrada como perda; FFX opaco não vira None e a
instalação de um manifesto não cria um decoder de origem.
Não foi publicado um aplicativo EffectCraft com esta alteração.

O patch e probe são originais; alterações do Bridge sob MIT. Os arquivos
afetados do EffectCraft conservam a licença upstream MIT OR Apache-2.0.
Nenhum código, binário, SDK ou asset proprietário foi usado.

A extensão MathOps 0.26.0 usa esse transporte experimental com duas entradas
auxiliares e processamento original aproximado; veja [uso e limites](mathops-extension.md).
A validação de transporte acima continua distinta da fidelidade do renderer.


## API 3 e revisão 2 — 0.27.0

A mesma cópia preparada agora anuncia `apis:[1,2,3]`,
`bridge_host:{revision:2,revisions:[1,2],layer_inputs:4,layer_timing:true}`.
API 2 continua com manifesto revisão 1 e seu layout intacto. API 3 exige
manifesto `bridge_host_revision:2`, export API 3 e `ec_render_v3` com os
nove argumentos API 2 mais um último `i32 timing_ptr`.

O bloco de 32 bytes contém quatro f64 LE: FPS real da composição, primeiro
frame visível em tempo local da camada, último frame visível em tempo local,
passo local positivo. Out é exclusivo: o último frame é `out-frame_duration`,
limitado ao in. Start/trim/stretch/reverso usam Layer::layer_time. A ordem
dos limites pode ser reversa ou igual. Sem contexto válido, o host recusa.
FPS 0,001..1 milhão; limites finitos ±1 bilhão de segundos; passo 1e-9..1e9.
O bloco vem após a tabela de descritores, antes dos pixels. Descritores de
80 bytes e seus bytes reservados não mudam; API 2 não recebe bloco temporal.

Um prefixo de efeitos com plugin API 2/3 não usa cache de pixels processados,
pois o hash legado não acompanha os recursos auxiliares ou os tempos visíveis.
Isso evita imagem temporal congelada e Background desatualizado; pode aumentar
o custo de renderização. Entradas anteriores ao plugin ainda podem usar cache.
A host API 1 oficial e sua assinatura permanecem preservadas.

Seis testes API 3 somam-se aos 21 existentes; a prova de Session
[do dissolve](dissolveshake-extension.md) verifica os tempos reais e cache
com full/half e reprodução reversa. Essa ABI continua experimental do Bridge.


## Cache temporal de API 1 — correção 0.28.0

Plugins recebem tempo mesmo quando todos os seus controles são estáticos. A
cópia agora os reconhece como dependentes de tempo para o hash do cache nativo,
que inclui tempo local/start/stretch. Isso evita congelar waves/PRNG sem
keyframes; assinaturas ABI e fingerprints permanecem. Plugins estáticos podem
recalcular em frames distintos; API 2/3 continua sem cache de pixels processados
que desconhece seus recursos. O upstream oficial não foi modificado.

`uv run python scripts/validate_legacy_temporal_host.py DIRETORIO_NOVO` verifica
15 samples originais, full/half, picos/vales, reabertura e reprodução reversa.
[Diagnóstico e decisão](decisions/033-plugin-time-aware-cache.md).
