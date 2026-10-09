# ADR 023 — Blur direcional original, BCC3Directional Blur parcial

## Evidência e decisão

Em 08/10/2026 foram consultadas a [descrição funcional Boris FX](https://borisfx.com/documentation/continuum/bcc-directional-blur/)
e a [referência de Apply Modes](https://borisfx.com/documentation/continuum/bcc-apply-modes/).
Essas páginas descrevem direção, distribuição, limiares, seleção de canais e
mistura. Não estabelecem kernels ou calibração suficientes para certificar
equivalência. A implementação MIT é original, sem dependências Rust externas
ou reutilização de código, SDK, binários ou assets proprietários.

Três instâncias completas parT/tdb4 comprovam os seguintes IDs:

| ID BCC3Directional Blur | Controle | Kind | Transferência |
|---|---|---|---|
| 0002 | Blur Amount | 2 | Float bruto |
| 0003 | Angle | 3 | Float, graus |
| 0004 | Thin | 2 | Float bruto |
| 0005 | Spread | 2 | Float bruto |
| 0006 | Blur Threshold | 2 | Float bruto |
| 0015 | Maximum Deviation | 2 | Float bruto |
| 0007 | Avoid Clipping | 4 | Bool exato |
| 0008 | Displace Pixels | 4 | Bool exato |
| 0009 | Apply Mode | 7 | Choice, índice menos um |
| 0010 | Apply Mix | 2 | Float bruto |
| 0011 | Channels | 7 | Choice, índice menos um |
| 0013 | Mix with Original | 2 | Float bruto |

Apply Mix tem flags 32, mas é um controle funcional; não foi descartado como
administrativo. Channels tem nove opções na ordem de origem: RGBA, RGB, Alpha,
Red, Green, Blue, Red and Green, Red and Blue, Green and Blue. Apply Mode tem
27 opções exatas do parT; não se troca a ordem por menus de outra versão.
O campo 0000 sem nome conserva a classificação administrativa existente.
O botão 0001, Compare, Mocha/PixelChooser, referências opacas, tracking e
Beat Reactor/audio continuam perdas. Nenhum zero ou blob ausente foi
interpretado como máscara vazia. ADBE Effect Mask Opacity=100 estático usa
somente o tratamento neutro anteriormente comprovado.

Os casos reais são estáticos: Amount/Angle/Avoid Clipping são 67/0°/false,
31/90°/true e 72/90°/true. Todos usam Normal e RGBA. Outras combinações de
controles e animações têm somente evidência sintética.

## Algoritmo próprio

Uma linha simétrica tem comprimento `rawAmount*scale` e no máximo 31 taps
bilineares. Offsets e pesos bilineares são calculados uma vez por frame;
vizinhos inteiros repetidos são agrupados e os índices de linhas calculados
uma vez por linha de saída. O número de amostras é ímpar, com centro e extremos. Thin reduz
esse número até três; Spread modifica os pesos por
`(1-spread/100)+(spread/100)*t²`, com t em [-1,1], e normaliza sua soma.
Valores grandes usam amostragem esparsa, declarada como perda. Displace
desloca o centro da amostragem por `-rawAmount*scale` na direção Angle; isso
move a imagem para a direção positiva. Ângulos retos são estabilizados para
evitar resíduos de sin/cos e interpolação artificial em um eixo.

Avoid Clipping=false replica as bordas. Quando true, a amostragem fora da
imagem é transparente. **O ABI v1 mantém as dimensões do frame:** a extensão
não pode publicar pixels além do canvas nem alterar offset. Portanto, true
transfere uma aproximação dentro do frame, com perda permanente de expansão
dos limites. Não se anuncia equivalência à opção original de renderizar fora
dos limites da camada.

Blur opera inicialmente em RGBA premultiplicado. Para cada componente:

```text
delta = lineFiltered - original
limited = original + sign(delta)*min(max(abs(delta)-rawThreshold/255,0),rawDeviation/255)
```

Depois, alpha é limitado a [0,1], e a mistura de cores usa RGB direto.
Mix with Original/100 controla a mistura final; Apply Mix/100 interpola
entre o filtro Normal e o Apply Mode escolhido. Normal ignora Apply Mix.
Somente os componentes selecionados por Channels são publicados; os demais
componentes armazenados permanecem bit a bit iguais. Isso inclui o RGB
armazenado quando apenas Alpha é selecionado. Não há correção gamma automática.

As fórmulas de mistura são próprias. Modos aritméticos incluem min/max,
produto, screen, diferença, soma, subtração, overlay e hard light. Soft Light
usa a aproximação polinomial `(1-2b)*a²+2ab`; Scale Multiply/Screen usam
fatores próprios 2 e 1/2. Lighter/Darker escolhem por luminância Rec.709.
Hue/Saturation/Color/Lightness usam HSL sobre RGB limitado a SDR. Boost Expo
usa médias de potências com offsets próprios; Eq Power usa médias quadráticas;
Bias usa contraste proporcional à diferença. Os cinco Boost preservam entradas
iguais exatamente. As fórmulas completas estão no fonte; não são algoritmos
BCC certificados. A escolha do nome do menu não implica identidade visual.

As conversões /100, /255 e o comprimento/deslocamento são calibração do
renderer próprio. O exportador mantém valores brutos e não atribui unidades
não declaradas aos sliders de origem. Apenas Angle usa graus comprovados.

## Limites e segurança

Amount 0..8192; Angle ±36000 graus; Thin/Spread/Apply Mix/Mix 0..100;
Threshold/Deviation 0..255; dois Bool exatos; Mode 0..26 e Channels 0..8,
inteiros. Até 8.388.608 pixels, lados 65.536, scale [1/65536,16].
RGB finito com módulo até 1000000, alpha 0..1. RGB direto e saídas de misturas
têm limite próprio ±1000000; HSL usa SDR, e alpha zero usa RGB direto zero.

O ABI valida a própria alocação, alinhamento, dimensões e 12 doubles.
Todos os pixels são validados antes do filtro. A saída é produzida em um
buffer separado, validada e copiada somente no fim. Entradas inválidas
conservam o frame. Não há imports, arquivos, camadas externas, expressões ou
estado temporal. Trabalho O(N×31), frame recebido + saída até cerca de
268 MB no limite de pixels. Fuel/memória do host não foram alterados.

Quatro perdas permanentes cobrem kernel/amostragem, calibração,
cor/mistura e limites do canvas/dependências. Sempre PARTIAL; strict não
publica um plano parcial. O objetivo universal permanece em andamento.

## Verificação

13 testes Rust/Clippy passaram: convolução independente da linha horizontal,
rotação/scale, amostragem fracionária, Thin/Spread/deslocamento, transparência
de borda, limiares/desvio, nove seleções de canais, 27 misturas em HDR/alpha,
HSL/aritmética com valores independentes, mistura original/apply, normalização
e limites/ABI inválido sem mutação. A otimização de offsets/pesos bilineares
foi comparada ao cálculo direto em 16 combinações de comprimento/ângulo/borda.
Rebuild Rust 1.98.1 byte idêntico.

A Session oficial descartável carregou o módulo, aplicou três componentes e
conferiu 36 valores estáticos, inclusive depois de file.saveAs/file.open.
Nenhum preset privado é distribuído. Testes WASM e Full HD constam da
[validação](../validation.md); não houve renderização ou comparação Adobe.
