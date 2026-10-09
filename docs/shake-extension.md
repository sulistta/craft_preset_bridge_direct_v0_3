# Shake aproximado para S_Shake

Bridge 0.11 inclui **Bridge Shake (Approximate)**, um renderer original opcional.
Os 43 controles transferidos incluem eixos, frequência/fase, seed, ondas, estilos,
canais, wrapping e blur. A trajetória e o resultado visual são uma aproximação.

1. Execute `craft-bridge extensions install shake` no ambiente instalado.
2. Carregue o caminho `module` mostrado em **Effect → Load Effect Plug-in…** no
   EffectCraft, ou `effect.plugins.load {"path":"CAMINHO_ABSOLUTO"}` pela API.
3. Reinicie a GUI do Bridge e analise/converta novamente, em uma saída nova.
4. Confira o relatório, os controles e o preview antes de aplicar.

Instalar o mapa não carrega o módulo nem altera um projeto. O preflight verifica
o registro e o contrato do plugin. Grupos selecionados exigem esse efeito no mesmo
índice de origem, começando em zero; enabled e controles não selecionados são
preservados. Propriedades de destino já animadas/com expressão são recusadas.

O blur aproxima movimento com oito transformações do mesmo frame e janela
Mo Blur Length/30 segundos. A API v1 não fornece FPS/shutter nem outros frames.
A calibração X/Y/Z, ruído, fase, estilos e composição por canal são próprias.
Máscaras/Mocha/crop/pixel aspect e expansão de bordas não são transferidos.
Normal e As Premult usam o mesmo buffer premultiplicado fornecido pela API;
All Opaque força alpha 1. Não se certifica a normalização de unidades Sapphire.

Todos os resultados são PARTIAL, mesmo quando todos os 43 controles são
transferidos. Strict recusa a aproximação. Keyframes precisam caber na grade da
composição de destino, que será ativada para editar as chaves. Um dos 19 snapshots
reais foi recusado na aplicação porque seus tempos não cabem na grade nativa.

Com Glow e Shake, o corpus privado gerou 101 resultados parciais/43 sem conversão,
contra 75/69 builtin. Nenhum preset completo foi comprovado.
O renderer CPU/WASM é lento: Full HD com blur e RGB separado levou cerca de
132 segundos neste ambiente. Fonte, fórmula e evidências: [ADR 010](decisions/010-approximate-shake-renderer.md).

Para remover o mapa, remova somente bridge-shake.json da pasta mappings de
CRAFT_BRIDGE_CONFIG (por padrão ~/.config/craft-bridge/mappings) e reinicie a GUI.
O módulo registrado no EffectCraft permanece independente desse mapa.
