# Glow aproximado para presets Deep Glow

A versão 0.9 inclui um renderer original **Bridge Glow (Approximate)**. É uma
extensão opcional que transfere parte dos controles PEDG. O resultado visual é
uma aproximação; gama automática, controles de qualidade/dither, aberração e
outros recursos continuam perdas. Todos os resultados permanecem PARTIAL.

1. Execute `craft-bridge extensions install glow` no ambiente instalado do Bridge.
2. Copie o campo `module` mostrado na saída. É o caminho absoluto do módulo WASM
   já incluído; Rust e Adobe não são necessários.
3. No EffectCraft, use **Effect → Load Effect Plug-in…** e selecione esse arquivo.
   Pela API oficial, o comando equivalente é
   `effect.plugins.load {"path": "CAMINHO_ABSOLUTO_MOSTRADO"}`.
4. Reinicie a GUI do Bridge e analise/converta os presets novamente. Examine as
   perdas no relatório e a prévia antes de aplicar. Use uma nova saída.

Instalar o mapa não carrega o renderer nem altera um projeto EffectCraft.
O preflight recusa aplicação se o renderer não estiver registrado, ou se seu
manifesto divergir. Em outra máquina, instale o mesmo mapa e carregue o módulo.
`craft-bridge extensions list` apenas mostra os recursos disponíveis.

No pacote privado de 144 arquivos, com referência 1920×1080, a extensão produz
92 resultados parciais/52 não suportados, contra 75/69 sem ela. Foram transferidos
348 controles de 23 snapshots completos e 18 grupos de propriedades selecionadas,
com 93 keyframes PEDG (110 no lote inteiro). Há caminhos PEDG ainda não convertidos. Nenhum preset completo foi comprovado.

O modo `--strict` recusa a aproximação. Para remover o mapa, remova somente
`bridge-glow.json` de CRAFT_BRIDGE_CONFIG/mappings, ou de
`~/.config/craft-bridge/mappings`, e reinicie a GUI. O renderer permanece
independente do mapa no aplicativo de destino.

Para os grupos selecionados, o destino precisa ter Bridge Glow no mesmo índice de
efeito da origem (começando em zero). O Bridge confere essa instância e preserva
o estado enabled e os controles não selecionados. Não preenche posições ausentes.
Animações exigem uma taxa de frames compatível; a composição de destino será ativada
para que a API selecione as chaves corretas. Veja [ADR 009](decisions/009-source-profiles-and-selected-glow.md).

Fonte, algoritmo, limites, reprodução e evidência: [ADR 008](decisions/008-approximate-glow-renderer.md).

O renderer ainda é lento para preview em tempo real: um frame sintético Full HD
com Radius 2000 levou cerca de 23 segundos neste ambiente. Não usa GPU.
