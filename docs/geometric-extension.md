# Geometric Filter original aproximado — 0.31.0

A extensão opcional `geometric` converte 21 controles de SatoriGeometricFilters
para um renderer original. Um snapshot real antes UNSUPPORTED passa a PARTIAL.
O lote com todas as extensões contém 132 PARTIAL/12 UNSUPPORTED, 3530 controles
e 561 chaves. Suporte universal e equivalência visual permanecem pendentes.

```sh
craft-bridge extensions install geometric
craft-bridge convert preset.ffx --out plano.json
craft-bridge apply plano.json --layer 'Minha camada' --dry-run
craft-bridge apply plano.json --layer 'Minha camada' --yes
```

Carregue `bridge_geometric.wasm` com `effect.plugins.load` em uma cópia isolada
com o [host experimental API 4/revisão 3](temporal-input-host.md). O EffectCraft
oficial não aceita esse contrato. Para reconstruir: `uv run python
scripts/build_geometric.py`; Rust fixado 1.98.1, sem dependências Rust externas.

## Evidência

IDs/tipos/defaults e menus vêm de um parT/tdb4 local: 14 sliders kind 2,
um slider kind 10, dois Bool e quatro menus (21 ao todo).
Todos são preservados sem inferir unidade de origem. Shape contém Line,
Curve, Triangle, Square, Circle, Rectangle; Strategy contém Random, Stable
Random, Grid; Fade contém cinco modos. A ordem vem do arquivo real.
A [descrição oficial aescripts](https://aescripts.com/geometric-filter/)
explica funções de formas, busca por cores e retenção de frames, mas não
publica algoritmo/calibração. Nenhum código, SDK, binário, asset ou fixture
proprietário foi reutilizado/distribuído.

Preset 0001 é seletor de estilo sem ação certificada; 0026 é hidden sem
semântica comprovada. Ambos permanecem perdas. Máscaras, expressões e grupos
não reproduzidos permanecem no relatório. Criação exige todos os 21 controles.
Sempre PARTIAL; strict não publica preset parcial. Valores fora dos limites
são recusados; skip fracionário e chaves sem Hold não são transportados.

## Modelo original

Fórmulas e unidades internas abaixo são escolhas do renderer Bridge.
Sliders de origem continuam brutos, inclusive ângulos kind 2.

| Controle | Modelo original e limites |
| --- | --- |
| Count / Recursion | Floor; até 10000 posições iniciais, 16 passos. Zero desliga desenho. |
| Size / Growth | Comprimento local até 2048 cada; três comprimentos size, size+growth/2, size+growth. |
| Angle / Random / Range | Interpretação própria raw×2π/360; 16 direções no intervalo de busca. |
| Accuracy | Quatro probes por candidato; média da distância absoluta RGB ≤1−raw/100. Alpha zero desqualifica candidato. |
| Shape / Fill / Width | Segmento, curva quadrática com 12 segmentos, triângulo, quadrado, círculo ou retângulo 2.5:1. Width local até 512; amostragem no centro do pixel, sem antialias certificado. |
| Opacity / Fade | raw/100; fade modula pela posição do comprimento no intervalo ou profundidade de recursão. Alpha sobre RGB straight; cor amostrada na posição inicial. |
| Min / Max Luminosity | (R+2G+B)/4×255, intervalo bruto 0..255; intervalo invertido não desenha. |
| Strategy / Grid Random / Seed | Hash de todos os bits do seed; Grid usa aspecto/tamanho local e jitter raw/100. Stable Random ignora tempo; Random usa floor(tempo solicitado/passo local). |
| Skip / Keep Original | Skip inteiro 0..1024 solicita pixels do prefixo no tempo retido via host. Fundo e busca usam a imagem retida, não apenas um relógio congelado. |

A recursão continua do endpoint escolhido, usando sua direção e a cor inicial.
A busca escolhe o menor erro; empate favorece o primeiro candidato. Geometria
usa offset/scale/tamanho local do buffer. Imagem retida com dimensões ou
geometria diferentes do buffer corrente é recusada, sem substituição silenciosa.
Canvas fixo recorta o exterior. Limites: 2097152 pixels/imagem, um milhão de
probes e oito milhões de visitas de rasterização. Exceder orçamento recusa
o resultado completo. Cor/HDR/gama/alpha, PRNG, calibração, antialias e algoritmos
Satori não são certificados, mesmo quando o destino aceita todos os valores.

## Validação

Dez testes Rust e Clippy all-targets passaram. Oito testes Python verificam
mapa, limites, criação incompleta e strict. Um teste real opt-in separado
verifica os 21 valores/menus e perdas com hashes preservados. Na Session real,
13 casos confirmam seis formas full/half, cinco retenções de prefixo animado,
reabertura e 21 controles reais persistidos/reabertos sobre pixels originais.
Nenhum teste é apresentado como comparação visual Adobe.
[ADR 036](decisions/036-approximate-geometric-renderer.md).

Um workload original Full HD (1920×1080, 1000 triângulos, uma recursão, fonte
uniforme, fundo desligado) passou no loader WASM nativo em ~5,1 s; saída
finita com 121066 pixels visíveis e 1952534 transparentes. Esse resultado
não é um benchmark geral. Execute o exemplo `geometric_hd` do harness para
reproduzir, após preparar a cópia experimental.
