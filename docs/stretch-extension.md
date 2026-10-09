# Stretch aproximado para pixel_stretch

Bridge 0.13 inclui **Bridge Stretch (Approximate)**, uma extensão original opcional.
São 20 controles de estiramento cumulativo por brilho, reconstrução subpixel,
direção, curva/fase, distribuição, canais, shading e bordas. A aparência continua
aproximada, sem comparação visual Adobe.

## Instalação e uso

```sh
craft-bridge extensions install stretch
```

Carregue o caminho `module` mostrado em **Effect → Load Effect Plug-in…** no
EffectCraft, ou com `effect.plugins.load` e seu caminho absoluto. Reinicie a GUI
do Bridge e reconverta para uma saída nova. Instalar o mapa não carrega o módulo
nem altera projetos; o preflight verifica o manifesto antes da aplicação.

Direction usa os quatro menus de origem; Channels possui os oito menus comprovados
no perfil mais recente. Perfis antigos não possuem Channels/Intensity/Smoothness:
o módulo usa Luma, intensidade 100 e smoothness zero para os controles ausentes.
Os valores são conservados sem clamp de parâmetros. Valores fora dos limites do
manifesto e opções desconhecidas são perdas explícitas. As fases, em graus,
são sliders limitados a ±10⁶ para que a exportação detecte limites de runtime.

## Limites

Intensity Source continua opaco no FFX e a API v1 fornece somente a imagem atual.
A dependência de outra camada não é reproduzida. Não são transferidos máscaras,
assets externos, Curve Graph e campos de UI/versão não documentados. Kernel,
gamma/espaço de cor, exponenciais/smoothness, fase, distribuição, shading, alpha
e feathering são calibrações próprias. Esses limites aparecem no relatório.

Todos os resultados são **PARTIAL**, mesmo quando os 20 controles são transferidos.
Strict publica relatórios sem publicar preset. O renderer conserva o tamanho do
buffer, com até 8.388.608 pixels e lado máximo 65.536. A entrada deve ser finita,
com RGB até ±10⁶ e alpha 0..1; a saída HDR tem limite ±10⁶. O desempenho CPU/WASM
é limitado para uso interativo: Full HD com RGBA separado/compressão/smoothing
levou ~72 segundos neste ambiente. [Validação](validation.md).

Keyframes exigem tempos que caibam na grade da composição. Grupos selecionados
atualizam uma instância existente no índice original e preservam enabled e os
controles restantes. A evidência de animação Stretch é exclusivamente sintética.

## Evidência

O corpus privado contém oito snapshots estáticos em dois perfis de versão:
três exportam 20 propriedades e cinco exportam 17. As 145 propriedades passaram
na Session oficial e na reabertura do projeto. Com Glow, Shake, biblioteca Flare
e Stretch: 117 PARTIAL/27 UNSUPPORTED, 3036 propriedades/484 chaves, nenhum SUCCESS.

Não se distribuem presets do usuário nem código/binários de plugins proprietários.
Para remover o mapa, remova explicitamente bridge-stretch.json em mappings de
CRAFT_BRIDGE_CONFIG (padrão ~/.config/craft-bridge/mappings) e reinicie o Bridge.
O módulo carregado no EffectCraft é independente desse mapa.

[Fórmulas, limites e pesquisa](decisions/013-approximate-stretch-renderer.md).
