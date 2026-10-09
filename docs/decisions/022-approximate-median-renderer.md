# ADR 022 — Mediana retangular original, BCC3Median parcial

## Evidência e decisão

Em 08/10/2026 foi consultada a [documentação oficial Boris FX](https://borisfx.com/documentation/continuum/bcc-median/).
A descrição funcional informa redução de ruído por vizinhança, seleção por
canal e janela orientada. Não fornece o algoritmo ou a calibração necessários
para certificar equivalência. Não foram obtidos ou reutilizados código, SDK,
binários ou assets proprietários. A extensão MIT é original, sem dependências
Rust externas. O filtro quadrado nativo não representa a janela anisotrópica
e orientada encontrada nos arquivos, portanto não foi usado como mapa direto.

Três instâncias completas parT/tdb4, em dois arquivos locais, comprovam:

| ID BCC3Median | Controle | Kind de origem | Transferência |
|---|---|---|---|
| 0852 | Mode | 7 | Choice, índice menos um |
| 0851 | Channel | 7 | Choice, índice menos um |
| 0803 | Preserve Alpha | 4 | Bool exato |
| 0801 | Median Length | 2 | Float bruto |
| 0806 | Median Width | 2 | Float bruto |
| 0805 | Median Angle | 3 | Float, graus |
| 0804 | Enable Fractional Radius | 4 | Bool exato |
| 0802 | Median Level | 2 | Float bruto |
| 0807 | Softness | 2 | Float bruto |
| 0520 | Mix with Original | 2 | Float bruto |

Mode segue a ordem parT: Selected Channel Only, Pixel Selected by Channel,
A R G B Separately, Most Common Pixel. Channel: Luminance, Lightness,
Brightness, Hue, Saturation, Alpha, Red, Green, Blue. Não se substitui essa
ordem pelo menu de uma versão atual da documentação. Os três casos reais são
estáticos, com Length=100, Width=3 e ângulos 138°, 108° e 45°.
Não se inferem unidades dos sliders nem se altera o parser por similaridade.

Compare Mode, Compositing e referências opacas de máscara/camada não têm
equivalência comprovada. Nem valores zero nem blobs ausentes certificam uma
máscara vazia. O botão 0001 e controles não mapeados continuam no relatório.
ADBE Effect Mask Opacity=100 estático usa somente o tratamento neutro já
comprovado. Compositing=None não foi interpretado como um blend nativo.

## Algoritmo próprio

Raios são `length*scale/2` e `width*scale/2`. Sem Fractional, usa-se floor;
com Fractional, interpolam-se os quatro pares floor/ceil pelo produto dos pesos.
Cada grade tem eixos ímpares, centro e extremos, e é rotacionada em graus com
arredondamento das coordenadas. Bordas são replicadas. Coordenadas repetidas
mantêm multiplicidade; empates preferem a amostra mais próxima do centro.

O teto de 36 taps por pixel é dividido entre as janelas ativas. Grades densas
são usadas quando cabem; grades maiores são esparsas. Uma janela inteira pode
ter no máximo 35 amostras; quatro janelas fracionárias têm até nove cada.
O caso 100/3 usa 11×3=33 taps sobre os mesmos extremos da grade 101×3.
O teto foi reduzido após testes com pixels variados esgotarem o orçamento
oficial de 50 milhões +20 mil unidades de fuel por pixel. As proteções da
engine não foram alteradas. Amostragem esparsa é uma perda permanente.

Medianas escalares são exatas para as amostras escolhidas, sem quantização SDR.
Redes de comparação Batcher ascendentes são geradas recursivamente; variantes
de 33/35 entradas retêm somente comparações que alimentam a posição mediana.
O gerador original reproduz networks.rs byte a byte. Uma rede pequena de nove
entradas e insertion sort para conjuntos menores evitam trabalho desnecessário.

O renderer converte RGB premultiplicado para RGB direto, limitado a ±1000000;
alpha zero usa RGB direto zero. Luminance usa Rec.709; Lightness usa (min+max)/2;
Brightness usa max; Hue/Saturation usam HSV dos canais RGB não negativos.
Selected Channel Only ajusta a métrica do pixel original. Pixel Selected by
Channel conserva o RGBA da amostra escolhida; a métrica é calculada uma vez
por frame. A R G B Separately usa medianas por componente. Most Common Pixel
agrupa RGBA SDR em quatro bits por canal, mas retorna o pixel original escolhido,
sem substituir suas cores pela quantização. Empates preferem o centro.

Preserve Alpha mantém o alpha recebido. A mistura própria usa:

```text
amount = rawLevel/100 * (1-rawMix/100)
contrast = abs(filteredMetric-originalMetric)/(1+abs(originalMetric))
blend = amount/(1+rawSoftness/100*contrast)
out.rgb = lerp(inputPremultipliedRGB, filteredStraightRGB*chosenAlpha, blend)
```

Softness zero evita avaliar contrast. Alpha é interpolado quando Preserve
Alpha está desativado. Level zero, Mix=100, raios zero e frames uniformes são
identidades exatas. Não há correção gamma automática nem execução de expressões.
Essas fórmulas, limites HDR, geometria, métricas e alpha são decisões próprias.

## Limites e segurança

Length/Width 0..512; Angle ±36000 graus; Level/Softness/Mix 0..100; Mode 0..3,
Channel 0..8 inteiros e Bool exato. Até 8.388.608 pixels, lados 65.536;
scale [1/65536,16]; canais finitos com módulo até 1000000, alpha 0..1.
ABI valida referências à própria alocação, alinhamento, dimensões e dez doubles.
Todos os pixels são validados antes do filtro; a saída é calculada separadamente
e só é copiada após validar finitude. Entradas inválidas não alteram o frame.

O trabalho é limitado por N×36 amostras. Dois buffers RGBA adicionais e, nos
modos de seleção de canal, um plano escalar exigem até cerca de 436 MB no
limite de pixels, incluindo o frame recebido. Não se reduz o limite de memória
ou fuel do host. Não há imports, arquivos, camadas externas ou estado temporal.

Quatro perdas permanentes cobrem algoritmo/amostragem, calibração sem unidades
certificadas, cor/alpha e controles/dependências não traduzidos. Sempre PARTIAL;
strict não publica plano. O objetivo universal permanece em andamento.

## Verificação

15 testes Rust e Clippy passaram: referência independente da mediana densa,
rotação/largura, quatro modos/nove métricas, alpha/HDR/identidade, mistura,
fractional, limites/ABI e preservação dos extremos. As redes foram comparadas
com ordenação independente em 512 conjuntos por tamanho, entradas repetidas,
HDR e subnormais; nove entradas têm teste com todas as 362880 permutações,
e quinze entradas com todas as 32768 sequências binárias.

Loader WASM oficial: 41 casos, com 37 verificações sintéticas, três conjuntos
reais de controles sobre pixels próprios e Full HD uniforme com um impulso.
Quatro modos passaram com raios máximos fracionários e alpha variável em
320×180. Full HD não certifica desempenho geral de imagens complexas.
Rebuild Rust 1.98.1 e geração das redes byte idênticos.

Uma Session oficial descartável carregou o módulo final e conferiu três
componentes/30 valores estáticos, inclusive após file.saveAs/file.open.
Os outros modos/canais e a animação têm evidência apenas sintética.
Nenhuma renderização Adobe ou comparação visual foi realizada. Fixtures
privadas permanecem locais, fora dos pacotes distribuídos.
