# Modulation aproximado

Bridge 0.16 inclui **Bridge Modulation (Approximate)**, uma extensão opcional
original para o perfil de 12 controles cujo match name é `ADBE Checkout` e cujo
nome de exibição é Modulation. O prefixo ADBE não comprova um efeito nativo Adobe.
Algoritmo, filtros e calibração são próprios; não há comparação visual com a origem.

```sh
craft-bridge extensions install modulation
```

Carregue o caminho `module` mostrado em **Effect → Load Effect Plug-in…** no
EffectCraft, ou pelo comando oficial `effect.plugins.load`. Reinicie a GUI do
Bridge e reconverta para uma pasta nova. Instalar o mapa não carrega o módulo;
a aplicação verifica o manifesto antes de alterar as propriedades.

Os 12 controles são Omega, Phase, Distortion, três Lowpass, Direction, Invert,
Opacity, Ignore alpha, Orientation e Hide white line. Os menus comprovados
Forward/Backward e Vertical/Horizontal passam de 1..2 para 0..1. Os coeficientes
numéricos brutos são preservados. Omega/Phase 0..4, Distortion -4096..4096 e
Opacity 0..255 são limites próprios; não são unidades ou limites certificados
do plugin original. Valores externos são recusados, sem clamp de controles.

O renderer próprio modula luminância em uma portadora complexa e demodula por
quadratura, com três filtros causais opcionais. Usa Opacity/255 para mistura,
preserva alpha e oferece inversão, orientação e primeira linha branca próprias.
Não reproduz os novos controles de cor/quarto filtro de Modulation 2. HDR/gama,
frequências, ordem de filtros e comportamento de alpha permanecem diferenças
registradas no relatório. Todos os resultados ficam **PARTIAL**; strict não
publica o plano. [ADR 018](decisions/018-approximate-modulation-renderer.md).

Dois snapshots reais exportam 24 propriedades e seis chaves escalares Linear.
Na Session oficial, os controles e chaves foram conferidos após salvar/reabrir;
12 valores intermediários foram comparados com cálculo independente. O WASM
passou em 19 casos sintéticos, dois conjuntos reais de controles sobre pixels
originais de teste e um Full HD (~14,6 s nesta máquina). São verificações do
Bridge, sem certificação da aparência do plugin original. [Validação](validation.md).

Com Glow, Shake, biblioteca Flare local, Stretch, Diffusion e Modulation:
120 PARTIAL/24 UNSUPPORTED, 3129 propriedades/492 chaves; nenhum SUCCESS.
Para remover o mapa, remova explicitamente bridge-modulation-1.json da pasta
mappings de CRAFT_BRIDGE_CONFIG (padrão ~/.config/craft-bridge/mappings) e
reinicie o Bridge. O suporte universal continua em andamento.
