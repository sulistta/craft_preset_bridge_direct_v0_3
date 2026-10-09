# ADR 025 — Referências Layer portáveis para planos nativos

## Evidência

EffectCraft e38a92e792c07f1c57c5dcfcab37d91932b9e2b8 expõe 71 parâmetros com
ParamUi::Layer/Value::Layer(None), em 42 efeitos. Value::Layer serializa como UID
u64 ou null. Em keyframe/src/value.rs, coerce_json converte por as_u64 e pode
aceitar um JSON inválido como None. engine/commands/query.rs expõe comp.info.layers
e layer.tree.id; commands/prop.rs fornece prop.get.type/value/keys. EffectHost
aceita layer(uid) da mesma composição e recusa self/recursão. O código fixado foi
lido sem alterar .research. Não se deduziu correspondência Adobe a partir de nomes.

## Decisão

Planos v4 permitem PlanProperty.kind=Layer com um objeto tipado LayerReference,
`{"layer_ref":"nome"}`. Null é permitido apenas dentro desse objeto, como unbind
explícito. Valores escalares/UIDs brutos não são válidos para Layer. Até 64 nomes
distintos; nomes ASCII iniciados por letra, até 80 caracteres. Animação Layer e
Layer em plugins API v1 são recusados. O catálogo continua a origem dos IDs/tipos.

Não se alterou Rule nem o IR para inferir referências não decodificadas.
As conversões atuais ainda geram v3 e preservam perdas. V2/v3 continuam aceitos;
plugins exigem fingerprint em v3/v4. V4 apenas autoriza a capacidade declarada;
não converte um plugin de uma imagem em um plugin de múltiplas imagens.

O adaptador recebe layer_bindings explícitos ou CLI --bind-layer REF=SELETOR.
Conjunto de bindings deve igualar as referências do plano; até 64 seletores
UTF-8 não vazios, no máximo 256 bytes, sem NUL. Dry-run não resolve a engine.
bridge.resolveLayer é um comando de prévia interno e não é enviado ao destino.
O plano e sua prévia devem ser canonicamente equivalentes.

Preflight resolve o destino e cada recurso por comandos oficiais, verifica UID
u64 positivo e pertencimento à composição, recusa self e fixa o contexto pelo UID.
Exige comandos de leitura e default nativo None dos parâmetros Layer. Antes de
prop.set, confirma tipo Layer sem chaves/expressão; prop.get posterior exige
campo value presente e igualdade exata de inteiros ou null explícito. Comparação
numérica aproximada não pode aceitar UIDs vizinhos acima de 2⁵³.

## Validação e limites

Testes de transporte verificam tipos inválidos, versões, animação, JSON extra,
bindings faltantes/extras/duplicados, self/fora da composição, catálogo divergente,
UID grande, null, dry-run e CLI. Fake server é evidência de protocolo, não de engine.

Uma Session oficial descartável aplicou 42 componentes/71 parâmetros Layer com
camadas originais sintéticas. Valores foram lidos após salvar/reabrir; unbind em
instância existente preservou UID, composição inativa foi preservada e self/layer
ausente foram recusados sem mutação. O helper original layer-render testa a
biblioteca de efeitos oficial com um EffectHost de duas imagens. Copy/Add/Multiply
conferiram o UID consultado e pixels contra resultados independentes.

Não se usou render.frame do aplicativo, indisponível na Session mínima. Não se
atribui suporte visual a todos os 42 efeitos a partir da aceitação dos parâmetros.
Áudio, máscaras, ciclos indiretos, Layer animado, recursos FFX opacos e integração
WASM multientrada permanecem pendentes. Sem comparação Adobe. Não há transação:
falha de engine após criar efeito pode deixar um componente novo. Essa limitação
é informada pelo adaptador; referências desconhecidas nunca são zeradas para
simular suporte universal.
