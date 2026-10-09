# Formatos e API headless

## Modelo intermediário

`craftbridge.intermediate`, versão 1; schema em `src/craft_bridge/schemas/intermediate.json`.
SourceMetadata contém caminho, tamanho, SHA-256, parser e versão detectada.
PresetDocument contém presets ordenados e avisos globais. Cada Effect preserva nome,
match name, ordem, enabled, propriedades e máscaras desconhecidas. ParameterValue distingue
number/boolean/enum/color/point/vector/text/unknown; `null` significa desconhecido.
Keyframe guarda ticks inteiros, time_base, valor, interpolações in/out por componente e
velocidades/influências separadas. `.seconds` é calculado somente na fronteira com APIs.

Origin/diagnostics guardam offsets, hashes e amostras Base64 **limitadas**, não uma cópia
completa dos blobs opacos. Estruturas decodificadas têm limites próprios; cenas
OFP preservam campos/bytes tipados para roundtrip, com campos contabilizados
no limite global de parâmetros e blocos sem associação limitados por max_diagnostics.
[Formato OFP](ofp-scenes.md). O original permanece no disco e é referenciado pelo hash. Expressões
são apenas dados; nunca são avaliadas.

```python
from craft_bridge.core.pipeline import inspect_file, preview, convert_file
from craft_bridge.core.safety import Limits

doc = inspect_file("meu.ffx", Limits(max_file_bytes=64*1024*1024))
payload, report = preview(doc)
report = convert_file("meu.prfpset", "novo.json", source_size=(1920,1080), strict=True)
```

A API oferece Limits para arquivo, chunks, profundidade, efeitos, parâmetros, keyframes,
amostras de diagnóstico e deadline cooperativo. O limite de parsing não mata processos;
checks ocorrem entre chunks/elementos/streams. A leitura XML inicial é limitada por bytes e
bloqueia DTD/entidades, mas não é preemptada durante `fromstring`.

## FilmCraft

Formato nativo `filmcraft.effect-presets`, versão 1. O schema local é um subconjunto do
schema serde examinado, sem máscaras. A validação também verifica IDs e tipos contra o
catálogo fixado. ParamValue usa tags externas Float, Bool, Choice, Vec2 e Color;
Vec2 serializa um objeto x/y, não um array. Tempos são ticks a 254016000000 por segundo.

StartKeyframe contém o valor salvo; CurrentValue pode ser um estado de preview diferente.
O sentinel negativo não é um keyframe da animação. Type 0/1/2 tem um mapa de posicionamento
isolado, ainda necessitando fixtures rotuladas de animação. `--keyframe-mode` fornece uma
escolha explícita. Keyframes do modelo intermediário com Linear/Hold podem ser exportados;
o parser Premiere não certifica os códigos de interpolação dos registros textuais.

## EffectCraft

Formato próprio `craftbridge.effectcraft-plan`, versões 2/3/4; schema em schemas/.
Conversões atuais geram V3. V2 segue aceito para builtins; plugins exigem V3/V4 e
fingerprint do manifesto instalado. V4 permite Layer estático simbólico nativo,
resolvido por bindings explícitos; UID bruto não é portátil. [Recursos Layer](layer-resources.md).
Esse fingerprint não é um hash do código do renderer. Veja ADR 007.
Planos v1 exigem reconversão devido à correção de pontos normalizados para pixels.
Pontos usam pixels da camada; cores usam RGBA 0–1; propriedades podem ter grupos `grupo/param`.
Contém effects com ref `fxN`, IDs do catálogo, enabled e propriedades tipadas/keyframes.
Na 0.4, application=create (default) mantém a criação de efeitos. application=existing
exige source_effect_index zero-based e vincula propriedades selecionadas à instância
correspondente, sem alterar enabled nem criar cópias. Planos antigos v2 de criação são
aceitos; os campos de vínculo exigem adaptador 0.4 ou posterior. bridge.bindExistingEffect
é resolvido localmente pela prévia/adaptador e nunca enviado como comando à engine.
A lista commands é uma prévia canônica, validada contra os dados semânticos. Comandos
extras, IDs arbitrários, caminhos injetados, duplicatas e catálogos desconhecidos são recusados.
`$layer`, `$comp`, `$fx0.path` e `$fx0.uid` são referências simbólicas, não código executável.

O adaptador usa apenas métodos oficiais engine.execute no TCP loopback. A porta pode ser
configurada; host remoto não é suportado. Cada resposta verifica id/ok, tamanho e timeout.
Efeitos são criados em ordem; paths retornados pela engine vinculam as propriedades.
prop.addKey recebe tempo da camada, e a engine arredonda para frames da composição.
O preflight recusa tempos que seriam deslocados. keys.select/keys.interpolation/keys.setEase
preservam as curvas aceitas, usando influências em porcentagem na API. Esses comandos
operam na composição ativa: após o preflight, o adaptador usa comp.open quando
o destino é outra composição, e confirma sua ativação antes de alterar propriedades.
O dry-run informa essa etapa condicional em context_commands; ela não altera a
lista canônica commands nem a versão do plano.
O tempo pós-snap é comparado em segundos, incluindo a distinção entre taxas decimais
e racionais NTSC. Nenhuma composição do usuário tem seu FPS alterado pelo adaptador.
Propriedades existentes com chaves/expressões são recusadas antes de mutação até a
mesclagem ser validada. Bool/Choice usam Hold; uma chave Linear isolada é convertida
para Hold com transformação registrada. Color single-ease aceita Linear/Hold;
Bezier e tangentes não nulas permanecem recusados.

## Relatórios

`craftbridge.conversion-report`, versão 1. SUCCESS/PARTIAL/UNSUPPORTED/FAILED são
estados de conversão, não notas percentuais. Cada efeito informa parâmetros/keyframes
extraídos e preservados, transformações, evidência do mapa e avisos. Um cabeçalho válido
sem conteúdo decodificado nunca gera SUCCESS. Strict recusa perdas e publica diagnóstico.
O relatório inclui o commit de destino e não afirma ter contatado a engine em conversões offline.

Pacotes com `Mapping.limitations` exigem Bridge 0.9+. O campo não executa código:
contém mensagens de perdas de conversão. Renderers aproximados declarados por
extensões usam esse campo para permanecer PARTIAL mesmo com controles transferidos.
