# Vínculos Layer nativos — 0.23.0

Planos próprios **v4** podem referenciar outra camada da composição por um
nome simbólico. O adaptador resolve o nome em um seletor escolhido pelo usuário,
consulta a engine e envia o UID verificado. O plano não transporta um número
de camada da aplicação de origem como se fosse um UID de destino.

O [exemplo original](examples/native-layer-plan.json) aplica Add do efeito
nativo Compound Arithmetic, usando a camada destino como imagem A e outra
camada como imagem B. Não é um preset salvo pela Adobe nem uma conversão S_MathOps.
Crie duas camadas na composição e escolha os nomes reais nos argumentos:

```sh
craft-bridge apply docs/examples/native-layer-plan.json \
  --comp "Minha composição" --layer "Imagem A" \
  --bind-layer background="Imagem B" --dry-run

craft-bridge apply docs/examples/native-layer-plan.json \
  --comp "Minha composição" --layer "Imagem A" \
  --bind-layer background="Imagem B" --yes
```

Dry-run mostra seletores e comandos, mas não se conecta nem confirma que as
camadas existem. Na aplicação, todos os vínculos são conferidos antes da criação
de efeitos. Repetir `--bind-layer` permite recursos distintos. Referências faltantes,
extras, duplicadas, vazias, fora da composição e à própria camada são recusadas.
Os seletores são nomes ou seletores oficiais, por exemplo `#2`; não são expressões.

Uma propriedade nativa Layer tem esta forma:

```json
{"id": "secondSource", "kind": "Layer", "value": {"layer_ref": "background"}, "keyframes": []}
```

Para remover explicitamente um vínculo existente, use `{"layer_ref": null}`.
Esse objeto expressa uma decisão no plano. Um `null` desconhecido do modelo
FFX não vira ausência de camada. UID bruto, índice Adobe, texto `#2` no valor
da propriedade, Bool ou Float são recusados. O adaptador confere tipo estático
Layer na engine e compara exatamente o UID lido após escrever, inclusive acima
de 2⁵³. Isso evita a coerção nativa permissiva que transforma strings inválidas
em Layer(None). A composição/camada destino são fixadas pelos UIDs consultados.

O catálogo fixado contém **71 parâmetros Layer em 42 efeitos nativos**. Todos
receberam um vínculo original sintético, conferido após salvar/reabrir o projeto.
Também foram verificados unbind em efeito existente, UID preservado e contexto
em composição inativa. Três testes de pixels usam a biblioteca/EffectHost oficial
com duas imagens próprias: Copy, Add e Multiply pediram o UID correto e produziram
os pixels esperados. Esse teste de host não usa o renderer completo do aplicativo.

A integração é estática e disponível pela CLI/API. Mapas FFX ainda precisam de
evidência para decodificar cada referência. Os parsers e mapas não passaram a
presumir layer vazio nem associar camadas por nomes de parâmetros. Máscaras,
áudio e a semântica de cada efeito continuam exigindo validação específica.
WASM API v1 continua oferecendo uma imagem e não ganha Layer com esta mudança;
S_DissolveShake e S_MathOps ainda exigem renderer/host e leitura de origem adequados.
Ciclos indiretos existentes não são certificados; o host nativo tem suas proteções
contra recursão. Não há transação de projeto: erros posteriores à criação de um
efeito são informados e podem deixar alterações parciais.

Planos comuns v2/v3 continuam aceitos e as conversões atuais continuam gerando
v3. O catálogo, fingerprints e comandos canônicos são verificados. Dados de origem
desconhecidos e as perdas já existentes continuam nos relatórios; strict não publica
planos parciais. [Decisão](decisions/025-native-layer-bindings.md).
