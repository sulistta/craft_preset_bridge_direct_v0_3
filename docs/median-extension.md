# Median aproximado

Bridge 0.20 inclui **Bridge Median (Approximate)**, extensão opcional original
para dez controles BCC3Median. A janela é retangular e rotacionável, com quatro
modos de seleção e nove canais. O algoritmo e a calibração são próprios;
não existe equivalência visual certificada com Boris Continuum.

```sh
craft-bridge extensions install median
```

Carregue o caminho `module` mostrado em **Effect → Load Effect Plug-in…** no
EffectCraft, ou por `effect.plugins.load`. Reinicie a GUI do Bridge e reconverta
para uma pasta nova. Instalar o mapa não carrega o módulo executável. O Bridge
confere o manifesto da instância antes de aplicar controles.

São transferidos Mode, Channel, Preserve Alpha, Median Length, Median Width,
Median Angle, Enable Fractional Radius, Median Level, Softness e Mix with
Original. A ordem dos menus segue os descriptors dos arquivos reais. Apenas
Angle tem unidade de origem comprovada, graus; os demais sliders mantêm seus
valores brutos. O renderer usa raios `raw*scale/2`, bordas replicadas e mistura
própria. Fractional interpola até quatro janelas inteiras.

O teto é de **36 amostras por pixel**, compartilhadas pelas janelas fracionárias.
Cada grade mantém o centro e os extremos da janela; janelas maiores têm
amostragem esparsa. O caso real Length=100/Width=3 usa 33 amostras, em vez de
todos os 303 pontos da grade inteira. Essa redução permite cumprir o orçamento
WASM da engine nos casos verificados e constitui uma perda explícita.

Selected Channel Only altera o canal escolhido; Pixel Selected by Channel
escolhe um pixel inteiro; A R G B Separately calcula medianas independentes;
Most Common Pixel agrupa RGBA com quantização própria de quatro bits por canal.
RGB é analisado sem premultiplicação; Preserve Alpha conserva o alpha original.
HDR, HSV, mistura, softness e quantização têm limites e fórmulas próprios.
[Detalhes e limites](decisions/022-approximate-median-renderer.md).

Três instâncias reais transferiram **30 valores estáticos**, incluindo ângulos
45°, 108° e 138°. A Session oficial confirmou os valores após salvar/reabrir.
Todos usam A R G B Separately; os outros modos, canais e animações possuem
evidência exclusivamente sintética. Compare Mode, Compositing, Mocha,
PixelChooser e referências de camada continuam perdas. Sempre **PARTIAL**;
strict não publica um plano parcial.

O loader oficial passou em 41 casos sobre pixels originais de teste, incluindo
os três conjuntos reais de controles, quatro modos com alpha variável e
Full HD uniforme com um impulso. Este último é um teste de correção,
não um benchmark geral de imagens complexas. [Validação](validation.md).

Com todas as extensões e a biblioteca Flare local: 123 PARTIAL/21 UNSUPPORTED,
3250 propriedades/507 chaves, nenhum SUCCESS. Para remover o mapa, remova
explicitamente bridge-median-1.json de mappings em CRAFT_BRIDGE_CONFIG
(padrão ~/.config/craft-bridge/mappings) e reinicie o Bridge.
