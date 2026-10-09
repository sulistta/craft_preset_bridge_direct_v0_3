# Adicionar mapas

Mapas não alteram os parsers. `src/craft_bridge/mappings/builtin.json` contém um pacote
`craftbridge.mappings`, versão 1, validado por Pydantic e pelo catálogo fixado.

Um mapa define source, source_format, target, effect, params, evidence, validation e
target_commit. Cada parâmetro tem target, kind (Float/Bool/Choice/Vec2/Color/Text) e operation:
identity, normalized_to_pixels, minus_one, times_100, times_255, argb255_to_rgba ou enum_map.
times_255 converte o limiar Camera Lens Blur de 0–1 para 0–255, incluindo velocidades Bezier.
enum_map exige uma tabela choices de índices da origem para índices de destino; separadores
e opções sem equivalente são recusados. Cores AE são ARGB 0–255 e cores destino RGBA 0–1.
Não há expressões Python/YAML
executável. Tipos e intervalos são verificados; valores não são clampados silenciosamente.
Não há defaults arbitrários: parâmetros não fornecidos usam os defaults da engine nativa.
Em planos de propriedades selecionadas, os parâmetros não fornecidos mantêm seus valores
na instância existente, conferida antes da aplicação.

Text aceita apenas strings UTF-8 estáticas de até 65536 bytes sem NUL. Strings nunca são
avaliadas pelo Bridge; seguem prop.set oficial. Hidden somente recebe tipo Text quando o
default nativo é Value::Str, não por nome nem aparência. Defaults Hidden numéricos/enums
continuam Opaque. As curvas ec.color.curves exigem 2..256 pares x,y finitos em 0..1, x
estritamente crescente de 0 a 1, com números ASCII e separação por espaços. Entradas
que a engine descartaria silenciosamente, como underscores ou algarismos Unicode,
são recusadas; pontos que a engine deduplicaria também são recusados.
Animação textual ainda não é suportada. Planos com Text exigem adaptador Bridge 0.6+;
adaptadores anteriores recusam esse tipo. Conversões atuais geram v3; v2 segue aceito para efeitos builtin. V4 permite
vínculos Layer nativos explícitos, [documentados separadamente](layer-resources.md).
Rule continua sem Layer: dados opacos de FFX não são promovidos a referências.

Uma regra pode declarar requires, um objeto de IDs de origem → valor booleano/numérico.
Cada condição exige exatamente um parâmetro estático, sem avisos de perda, com tipo e
valor correspondentes; condições ausentes, duplicadas ou animadas recusam a regra.
Lumetri usa isso para os grupos ativos e a intensidade Creative. Não são expressões
avaliadas, scripts nem comparações por nome da interface.

O snapshot parsers/ffx/parameter-types.json contém 2648 IDs/tipos de origem comprovados
por parT/tdb4 reais, coletados independentemente dos mapas instalados. make_ffx_profiles.py
o regenera sobre o corpus local e exclui conflitos, dimensões incompatíveis e IDs derivados
pelo Bridge. Isso permite decodificar propriedades, mas não adiciona renderers nem equivalências. Só IDs com tipo comprovado podem promover propriedades selecionadas; o
tipo de destino nunca é usado como evidência do tipo de origem.

Procedimento:

1. Fixar uma fixture real legalmente utilizável ou registrar a falta de evidência.
2. Identificar match names, parâmetros e unidades no conteúdo estruturado.
3. Confirmar ID, tipo, limites, unidade e semântica no código do destino, no commit registrado.
4. Adicionar regras e testes com valores não neutros, enums, limites e animação quando pertinente.
5. Atualizar docs/compatibility.md, THIRD_PARTY_NOTICES e referências.
6. Regenerar o JSON e testar exportação/aplicação.

`scripts/make_builtin_catalog.py` é a fonte auditada dos mapas e do catálogo de destino.
A ausência de fixture real deve ficar como `synthetic-only`; o runtime gera aviso de perda
MAPPING_UNVERIFIED e strict rejeita a conversão. Nunca renomeie esse status sem evidência.

Pacotes comunitários:

```sh
craft-bridge mappings install pacote.json
```

São instalados em `~/.config/craft-bridge/mappings` (ou CRAFT_BRIDGE_CONFIG/mappings),
sem downloads e sem execução de código. Apenas podem mapear novas origens para efeitos e
parâmetros existentes no catálogo auditado ou declarados por manifesto de plugin nativo
em pacote v2, com commit igual. Não podem substituir mapas
existentes nem adicionar IDs de destino não verificados. Para remover um pacote, remova
seu JSON dessa pasta; reinicie a aplicação. Diretórios de configuração são locais ao usuário.
O catálogo EffectCraft completo é extraído de ParamSpec nativo em docs/catalogs/effectcraft.json;
catálogo não equivale a mapa nem certifica equivalência visual. Veja docs/effect-expansion.md.
O catálogo FilmCraft completo em docs/catalogs/filmcraft.json é extraído de effect_defs():
303 efeitos/1426 parâmetros. Preserva limites, opções e animatable; parâmetros que não
aceitam animação recusam keyframes na conversão e na validação do JSON nativo. Defaults
Vec2 com null no snapshot são sentinelas nativos de posição automática serializados por
serde, não coordenadas conhecidas; não são usados como valores de conversão.

## Plugins nativos em pacotes v2

Declare `version: 2` e um array `plugins` com o manifesto da API EffectCraft v1.
Os campos e seis tipos API 1 seguem docs/plugins.md do destino. API 2 é um
contrato experimental separado e exige `bridge_host_revision:1`; oferece
Layer com default null explícito e até quatro entradas. As regras `mappings`
apontam ao ID reverso do manifesto. Nunca use `ec.`
para um renderer externo. Instale pelo mesmo comando `mappings install`.

O renderer precisa estar registrado no EffectCraft (Load Effect Plug-in ou mecanismo
oficial equivalente). O Bridge não carrega módulos ao converter/instalar. Reinstale
o mesmo pacote no computador que aplica o plano. Mudança no manifesto exige reconversão.
O plano v3 contém fingerprint de metadados; limites são os declarados no manifesto,
pois a API consultada não publica UI/limites completos nem hash do código. Um plugin
carregado e um mapa instalado não comprovam equivalência visual com Adobe.
Para evidência, limites e auditoria nativa, veja [ADR 007](decisions/007-native-plugin-catalogs.md).

API 2 exige planos v4 e capacidade `apis:[1,2]`/`bridge_host` comprovada, além
da API 2 individual do plugin carregado, sua versão, parâmetros e defaults.
Campos de versão/capacidade devem ser inteiros exatos. Layer deve constar
explicitamente em cada criação; `{"layer_ref":null}` desvincula e referências
simbólicas são resolvidas por `--bind-layer`. Animação de Layer é recusada.
Uma conversão escalar API 2 emite v4; um plano v4 pode combinar API 1/API 2.
Não existem regras Layer de origem: nada transforma dados desconhecidos em
referências. [Contrato e exemplos](experimental-multi-input-host.md).

## Limitações declaradas de renderers aproximados

Um mapa pode declarar `limitations`, até 32 mensagens de 1..2048 caracteres. Cada
mensagem é uma perda MAPPING_APPROXIMATION, inclusive quando todas as propriedades
são transferidas. Assim a aceitação de controles não gera SUCCESS nem saída strict.
A extensão opcional [Glow](glow-extension.md) utiliza esse contrato; seus fontes,
manifesto e WASM estão em src/craft_bridge/extensions/glow/.

A extensão [Shake](shake-extension.md) usa o mesmo contrato de plugins v2/planos v3
com 43 controles comprovados de origem e renderer original aproximado. Seus
fontes/manifesto/WASM são distribuídos em src/craft_bridge/extensions/shake/.

## Referências de origem opacas — 0.26.0

Rule `kind=Layer` exige `operation=explicit_layer_binding`, destino Layer
EffectCraft, origem FFX, evidência, limitações e recurso obrigatório na criação.
A operação não transforma bytes em Layer: exige um `SourceLayerBindings`
fixado ao hash, índice de preset/efeito e parâmetro único. Null é uma substituição
manual explícita. Recursos estáticos devem ter animated=False comprovado;
animação/expressão são recusadas. O IR permanece desconhecido e o relatório
acrescenta SOURCE_LAYER_REPLACED sem apagar avisos. [Uso](mathops-extension.md).


API 3 exige `bridge_host_revision:2` e plano v4, com preflight dos tempos reais
oferecidos pelo host. API 2 permanece revisão 1 e o host revisão 2 anuncia
compatibilidade explícita com ambas. `required_on_create` aceita até 256 IDs,
alinhado ao limite declarativo de parâmetros; Dissolve Shake exige 41. Não
se criam propriedades parciais usando defaults presumidos da origem.
[Contrato](experimental-multi-input-host.md) e [mapa](dissolveshake-extension.md).
