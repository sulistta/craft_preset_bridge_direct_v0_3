# ADR 020 — Ordenação original de pixels, S_PixelSort parcial

## Evidência e decisão

Em 08/10/2026 foi consultada a [documentação oficial Boris FX](https://borisfx.com/documentation/sapphire/ae/pixelsort/).
Ela descreve padrões Linear/Radial/Circular, critérios de cor, threshold,
reinícios e seleção por Matte/Mocha. Não fornece código, PRNG ou calibração
que certifiquem os cálculos. Nenhum código, binário, SDK ou asset proprietário
foi obtido ou reutilizado. A extensão MIT do Bridge é independente e aproximada.

Um snapshot local Linear comprova 24 controles parT/tdb4. IDs:
0045 (kind 7) padrão; 0050 (kind 2) Sort Angle; 0051/0059 (kind 6) centros
normalizados; 0052..0058/0060..0063/0067..0070 (kind 2) coeficientes;
0064/0066/0071/0075 (kind 7) menus; 0065 (kind 4) Reverse.
Menus exatos preservados no manifesto: três padrões, dois lados do threshold,
dez métricas, cinco visualizações, três modos de opacity. Origem 1-based para
Choice 0-based; opções fora dos menus são recusadas. Seed é fracionário,
0,2729949951171875 neste perfil. Não há keyframes reais PixelSort no corpus.

Centros [0,5;0,5] normalizados tornam-se [960;540] em camada 1920×1080, pela
regra de pontos já comprovada no Bridge. O ABI oficial point usa pixels de frame
após offset/scale, portanto o renderer não multiplica os centros por scale de
novo. Radius/Ray Length/Thickness/Soften não declaram unidade de origem e
permanecem coeficientes brutos, com interpretação própria abaixo.

Matte from Layer 0001, Matte from Path 0235 e Mocha 0520 continuam opacos.
Matte Use/Blur/Invert, controles Mocha e Soft Borders não são mapeados. Nenhum
estado vazio de máscara é inferido de bytes zero. Combined Mask omite essas
entradas e registra a diferença. Não há equivalência visual comprovada.

## Geometria e algoritmo próprios

Cada pixel recebe grupo, ordem e elegibilidade sem reamostrar a imagem.
Linear projeta [x,y] no eixo de Sort Angle e na perpendicular. round(projeção
perpendicular) define o grupo; projeção longitudinal define a ordem. Radial
usa polar em torno do centro, com bins angulares em max(width,height) × 2*pi.
Ordem é distância ao centro; elegibilidade limita ângulo, Inner Radius e Ray
Length. Vary Radius desloca o início por ruído determinístico por grupo, até
±0,5 × rawVary × rawLength × scale, limitado inferiormente a zero.

Circular usa floor(distância) para agrupar anéis; ordem é ângulo relativo ao
início. Elegibilidade limita Degrees Sorted, Inner Radius e Thickness.
Vary Start desloca o início em ±0,5 × 360 × rawVary por grupo. Distâncias usam
raw × scale, decisões de calibração próprias. Centro e borda angular têm
regras explícitas; nenhum canvas externo, wrap de imagem ou máscara privada.
Pixels em empates geométricos seguem índice original. Wrap de ângulo é
normalizado a [0,360), inclusive quando rem_euclid arredonda uma diferença
negativa muito pequena para 360. Seleção completa conserva essa fronteira.

Métricas próprias: Rec.709, média RGB, mínimo, máximo, canais R/G/B, hue HSV,
saturação HSV e brightness=max(RGB). RGB de análise é limitado a 0..1000000;
Normal divide premultiplicado por alpha quando positivo, As Premult usa
valores armazenados, All Opaque ignora alpha. Pixels de alpha zero fornecem
métrica zero nos dois modos transparentes. Pixels RGB negativos/HDR continuam
preservados como RGBA quando movidos; apenas a métrica usa os limites próprios.

O threshold usa comparação estrita > ou <. Soften aplica caixa separável com
raio round(raw × scale), bordas zero e denominador constante. A seleção inclui
pesos ≥0,5 e geometria elegível. Grupos, pixels excluídos e reinícios interrompem
runs. Cada run é classificado pela métrica, com desempate estável na ordem do
caminho; Reverse inverte a métrica sem inverter empates. Move-se o RGBA inteiro,
sem interpolação espacial ou classificação independente de canais.

Reinícios usam misturador inteiro determinístico original com todos os bits
f64 do seed. Frequência raw/1000, independente de time; 1000 divide todos os
runs em pixels isolados. A fórmula não reproduz o PRNG Sapphire.
Mistura = mask × (1-Mix With Source). Interpola RGBA original e ordenado;
All Opaque força alpha 1. Visualizações são grayscale premultiplicado de
métrica, threshold, reinícios ou seleção geométrica/threshold. Combined Mask
não representa Matte/Mocha. Mix=1 com Show Result nos modos transparentes
é identidade exata, incluindo HDR/alpha. Sem gamma automático.

## Limites e segurança

Limites próprios: ângulos ±36000, arcs 0..360, centros com módulo até 1000000,
radii/length/thickness 0..65536, variação/mix 0..1, threshold ±1000000,
reinícios 0..1000, soften 0..4096, seed 0..1000000. Não são limites/unidades
de origem inferidos. Menus são inteiros exatos, Bool é 0/1, controles finitos.
Até 8.388.608 pixels, lados 65.536, scale [1/65536,16], canais finitos com
módulo até 1000000, alpha 0..1. Sem imports, expressão, camada ou arquivo.

ABI v1 com 24 propriedades/26 doubles. Buffers de saída, entradas de
ordenação, máscaras e índices usam alocações verificadas; sort_unstable não
aloca e desempates explícitos mantêm estabilidade. Trabalho O(N log N), sem
custo proporcional ao raio de blur. No WASM, scratch ocupa até aproximadamente
60 bytes/pixel além do buffer original. O frame só é alterado após todos os
cálculos e alocações; falhas preservam a entrada.

Quatro limitações permanentes cobrem algoritmo/geometria, dependências,
cor/seed/calibração e canvas/máscaras. Sempre PARTIAL; strict não publica.
O objetivo universal ainda não está concluído.

## Validação

Treze testes Rust verificam ordenação estável contra resultado independente,
permutação RGBA nos três padrões, intervalos, métricas, seed fracionário,
alpha, mistura, blur contra soma direta e rejeição sem mutação.
Rust 1.98.1/Clippy passaram; rebuild foi byte idêntico. Loader oficial WASM
passou em 48 casos: 46 sintéticos, um conjunto real de controles sobre pixels
originais e Full HD a 37° (~41,4 s). O perfil real é somente Linear;
Radial/Circular/animação continuam evidência exclusivamente sintética.
Session oficial preservou um componente/24 propriedades estáticas após
salvar/reabrir, com centros em pixels e seed fracionário exato.
Nenhum fixture privado é distribuído; sem render comparativo Adobe.
