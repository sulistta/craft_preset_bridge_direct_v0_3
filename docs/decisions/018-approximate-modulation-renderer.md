# ADR 018 — Modulação e demodulação originais, perfil Modulation parcial

## Evidência e decisão

Em 08/10/2026 foi consultada a [página oficial Modulation/aescripts](https://aescripts.com/modulation/).
Ela descreve modulação/demodulação de brilho e controles de frequência, fase,
distorção, filtros e direção. O perfil mais recente acrescenta modos de cor e
um quarto filtro. A descrição funcional não comprova fórmulas ou calibração.
Não foram obtidos nem reutilizados código, binários, SDK ou assets do plugin.
A implementação MIT do Bridge é original e aproximada.

Dois snapshots privados comprovam IDs, descriptors parT/tdb4 e menus do perfil
de 12 controles: ADBE Checkout-0001/0002/0003/0009 são números kind 10;
0004/0005/0006/0008/0010/0012 são Bool kind 4; 0007/0011 são Choice kind 7.
Os nomes são, na ordem: Omega, Phase, Distortion, Lowpass 1, Lowpass 2,
Lowpass 3, Direction, Invert, Opacity, Ignore alpha, Orientation, Hide white line.
Menus exatos Forward/Backward e Vertical/Horizontal usam origem 1..2, destino
0..1. O valor bruto Opacity é 255 nas duas instâncias. Isso não constitui prova
de uma unidade física ou limite de origem. Um snapshot traz três chaves Linear
em Omega e três em Phase, em 1,35/1,40/1,45 s. Não há lados Bezier reais neste caso.

## Algoritmo e limites próprios

Entrada RGBA premultiplicada é convertida para luminância Rec.709 direta limitada
a 0..1. Pixels de alpha zero possuem luminância zero. Para scale s, a portadora
usa c = pi*0,75*omega/(1+omega)/s e desvio d = pi*0,2*phase/(1+phase)/s.
A fase inicial é 2*pi*phase módulo 2*pi. Cada pixel incrementa theta por c+d*luma;
a distorção acrescenta distortion/100*sin(theta). IQ é cos/sin dessa fase, com
amplitude alpha ou 1 quando Ignore alpha está ativo.

Os três estágios causais opcionais têm coeficientes próprios 0,5/0,25/0,125,
ajustados por scale como 1-(1-a)^(1/s). Inicializam com a portadora inicial.
A diferença de fase entre amostras consecutivas usa atan2(cross,dot), ramo mais
próximo da portadora; a luminância demodulada é (delta-c)/d limitada a 0..1.
Desvio/norma próximos de zero usam a luminância de entrada. Vertical percorre
linhas, Horizontal percorre colunas; Backward inverte a ordem. A primeira
amostra pode tornar-se branca; Invert ocorre antes da mistura. Alpha é
preservado, e Opacity/255 mistura o RGB premultiplicado original com cinza.
Opacity zero preserva exatamente o buffer, incluindo HDR. Estas fórmulas e a
geometria da orientação são decisões próprias, sem equivalência certificada.

Limites próprios: Omega/Phase 0..4, Distortion -4096..4096, Opacity 0..255;
8.388.608 pixels, lados até 65.536, scale [1/65536,16], canais finitos com módulo até
1.000.000, alpha 0..1. O piso de scale evita overflow de frequências
e fase; escalas menores são recusadas antes de escrever pixels. Bool/Choice exigem 0 ou 1 exatos. Chamadas inválidas
preservam o buffer. ABI v1 com 12 doubles, sem imports, arquivos, camadas ou
expressões. Processamento O(N), sem buffers auxiliares de imagem.

Quatro limitações permanentes do mapa cobrem algoritmos/cores/HDR/gama,
coeficientes/calibração, filtros/ordem e opacity/alpha/linha branca. O resultado
é sempre PARTIAL; strict não publica um preset parcial. Controles de outros
perfis, máscaras, dependências e animações não decodificadas continuam perdas.

## Validação

Dez testes Rust verificam invariantes, canais, alpha, controles, direção,
transposição, mistura e rejeição sem mutação. Loader WASM oficial passou em
19 casos sintéticos independentes, dois conjuntos reais de controles com pixels
originais e Full HD (~14,6 s). Na Session oficial fixada, dois componentes
preservaram 24 controles/seis chaves após reabrir projeto; 12 samples Linear
foram comparados com cálculo independente. Comparação visual com a origem
permanece ausente. Corpus e resultados privados são opt-in e não distribuídos.
