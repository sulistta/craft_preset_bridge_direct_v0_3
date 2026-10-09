# Pixel Sort aproximado

Bridge 0.18 inclui **Bridge Pixel Sort (Approximate)**, extensão opcional
original. Transfere 24 controles S_PixelSort para ordenação de pixels completos
em linhas projetadas, raios radiais ou anéis circulares. Geometria, métricas,
reinícios e suavização são fórmulas próprias. Não há comparação visual com
Sapphire/Adobe.

```sh
craft-bridge extensions install pixelsort
```

Carregue o caminho `module` mostrado em **Effect → Load Effect Plug-in…** no
EffectCraft, ou pelo comando oficial `effect.plugins.load`. Reinicie a GUI do
Bridge e reconverta para uma pasta nova. Instalar o mapa não carrega o módulo;
a aplicação verifica o manifesto antes de alterar as propriedades.

Informe o tamanho real da camada (`--size WIDTHxHEIGHT` na CLI). Os pontos
normalizados Radial Center/Circular Center passam para pixels de camada; o ABI
oficial os adapta a pixels do frame de preview. Não se convertem pontos sem
resolução explícita. Radius/Length/Thickness/Soften preservam coeficientes
brutos; a interpretação como distâncias do renderer é calibração própria,
sem unidade de origem inferida.

Menus comprovados: Linear/Radial/Circular; acima/abaixo do threshold; dez
critérios de cor; cinco saídas de visualização; All Opaque/Normal/As Premult.
Passam de 1-based para 0-based conforme as opções exatas. Pixels RGBA são
ordenados juntos, com empate estável. Reverse inverte a classificação;
Mix With Source=1 preserva exatamente o input nos modos transparentes.
Seed conserva a parte fracionária. Reinícios usam PRNG determinístico próprio,
com frequência raw/1000. Soften aplica blur de caixa ao threshold, bordas zero.
Não são reproduções certificadas de Sapphire.

Matte from Layer/Path e Mocha permanecem opacos. O renderer seleciona por sua
geometria e threshold, sem presumir que as máscaras originais estejam vazias.
Combined Mask mostra apenas a seleção própria, sem essas dependências.
Matte Use/Blur/Invert e Soft Borders não são traduzidos. ABI de quadro fixo
não expande o canvas. Essas diferenças e cor/HDR/gama/alpha são perdas no
relatório. Todos os resultados ficam **PARTIAL**; strict não publica o plano.
[ADR 020](decisions/020-approximate-pixelsort-renderer.md).

Um snapshot real Linear exporta 24 propriedades estáticas, sem keyframes.
A Session oficial confirmou todos os valores após salvar/reabrir, incluindo
centros [960,540] para camada 1920×1080 e seed fracionário exato. Radial e
Circular possuem somente verificação sintética neste corpus. O loader WASM
passou em 46 casos sintéticos, um conjunto real de controles sobre pixels
originais e Full HD a 37° (~41,4 s nesta máquina). [Validação](validation.md).

Com todas as extensões e biblioteca Flare local: 122 PARTIAL/22 UNSUPPORTED,
3203 propriedades/504 chaves; nenhum SUCCESS. Para remover o mapa, remova
explicitamente bridge-pixelsort-1.json de mappings em CRAFT_BRIDGE_CONFIG
(padrão ~/.config/craft-bridge/mappings) e reinicie o Bridge. Suporte universal
continua em andamento.
