# Directional Blur aproximado

Bridge 0.21 inclui **Bridge Directional Blur (Approximate)**, extensão original
opcional para 12 controles BCC3Directional Blur. A linha rotacionável possui
Thin, Spread, limiares, deslocamento, nove seleções de canais e 27 modos de
mistura. Kernels, calibração e cor são próprios; sem equivalência visual
certificada com Boris Continuum.

```sh
craft-bridge extensions install directional
```

Carregue o caminho `module` mostrado em **Effect → Load Effect Plug-in…** no
EffectCraft, ou por `effect.plugins.load`. Reinicie a GUI do Bridge e reconverta
para uma pasta nova. Instalar o mapa não carrega o módulo executável. O Bridge
verifica o manifesto da instância antes de aplicar controles.

Amount, Angle, Thin, Spread, Blur Threshold, Maximum Deviation, Avoid Clipping,
Displace Pixels, Apply Mode, Apply Mix, Channels e Mix with Original são
transferidos. Menus seguem o parT real; apenas Angle tem unidade comprovada,
graus. Sliders mantêm os coeficientes brutos. A linha usa até 31 amostras
bilineares, com perda de amostragem em comprimentos maiores.

**Avoid Clipping tem uma limitação:** a amostragem fora da imagem usa pixels
transparentes, mas o ABI mantém o canvas. O módulo não publica pixels além
do frame nem amplia os limites da camada. Essa diferença aparece no relatório.
Compare, Mocha/PixelChooser, tracking e Beat Reactor/audio também permanecem
perdas. Sempre **PARTIAL**; strict não publica plano parcial.

Três instâncias reais transferiram **36 valores estáticos**, conferidos na
Session oficial após salvar/reabrir. Usam Normal/RGBA, comprimentos 31, 67 e 72
e ângulos 0°/90°. Outras opções, misturas e animações têm apenas evidência
sintética. Nenhuma comparação visual com a origem foi realizada.
[Algoritmo e limites](decisions/023-approximate-directional-renderer.md),
[validação](validation.md).

Para remover o mapa, remova explicitamente bridge-directional-1.json de
mappings em CRAFT_BRIDGE_CONFIG (padrão ~/.config/craft-bridge/mappings)
e reinicie o Bridge.

O loader oficial passou em 86 casos sobre pixels próprios, incluindo controles
reais e 27 misturas com alpha variável. Full HD com checker não uniforme,
Angle=137,3° e 31 taps passou em cerca de 96 s nesta máquina. CPU/WASM ainda
é lento para preview; isso não certifica desempenho de outros conteúdos/máquinas.

Com todas as extensões e Flare local: 124 PARTIAL/20 UNSUPPORTED,
3286 propriedades/507 chaves, nenhum SUCCESS. Suporte universal permanece
em andamento; segundas imagens e expansão do canvas precisam de integração.
