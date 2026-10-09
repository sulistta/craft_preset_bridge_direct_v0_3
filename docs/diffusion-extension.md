# Difusão aproximada para omino_diffusion

Bridge 0.14 inclui **Bridge Diffusion (Approximate)**, uma extensão opcional
original. Transfere 17 controles: error across/aside, initial phase, direção,
contagem, seis cores e seis larguras. O algoritmo de paleta/difusão é próprio;
não há comparação visual com Omino/Adobe.

```sh
craft-bridge extensions install diffusion
```

Carregue o caminho `module` mostrado em **Effect → Load Effect Plug-in…** no
EffectCraft, ou pelo comando oficial `effect.plugins.load`. Reinicie a GUI do
Bridge e reconverta para uma pasta nova. Instalar o mapa não carrega o módulo;
a aplicação verifica o manifesto antes de alterar as propriedades.

A direção usa o menu comprovado right/left/down/up. Color Count 1..6 é convertido
para Choice 0..5; valores fracionários e opções desconhecidas são recusados.
Cores ARGB255 tornam-se RGBA0..1. Os coeficientes brutos e widths são conservados
com limites próprios -4..4 e 1..4096; não são unidades/limites certificados da origem.
Stamps/debug, máscaras, expressões e dependências continuam perdas no relatório.

O renderer usa distância RGB, erro limitado a ±1024, quantização de 8 bits e
larguras arredondadas por scale. HDR/gama e alpha/fase não são reproduções
certificadas. São decisões próprias documentadas no [ADR 014](decisions/014-approximate-diffusion-renderer.md).
Todos os resultados permanecem **PARTIAL**; strict não publica o plano.

Quatro snapshots reais exportam 68 propriedades estáticas. Elas foram conferidas
na Session oficial e após reabrir o projeto. A renderização WASM passou em 17
casos sintéticos independentes, quatro conjuntos de controles reais com pixels
de teste e um caso Full HD (~7,3 segundos nesta máquina). Nenhuma animação Omino
real está presente nesse corpus. [Validação](validation.md).

Com Glow, Shake, biblioteca Flare, Stretch e Diffusion: 119 PARTIAL/25 UNSUPPORTED,
3104 propriedades/484 chaves, nenhum SUCCESS. Para remover o mapa, remova
explicitamente bridge-diffusion.json da pasta mappings de CRAFT_BRIDGE_CONFIG
(padrão ~/.config/craft-bridge/mappings) e reinicie o Bridge.
