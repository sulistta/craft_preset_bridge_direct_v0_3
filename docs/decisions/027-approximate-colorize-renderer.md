# ADR 027 — Gradiente Colorize original aproximado

## Evidência e decisão

Quatro snapshots locais parT/tdb4 de BCC3Colorize confirmam 23 controles
estáticos, tipos, dimensões e menus. Não são distribuídos. As páginas oficiais
[Colorize](https://borisfx.com/documentation/continuum/bcc-colorize/) e
[Gradient](https://borisfx.com/documentation/continuum/bcc-gradient/), consultadas
em 08/10/2026, descrevem a função de toning, cores opcionais, espaços de cor,
looping e ajustes HSL. O [manual legado público](https://cdn.borisfx.com/borisfx/download_files/bccavx.colorize.pdf)
confirma a organização do gradiente. Descrições públicas não fornecem algoritmo
ou calibração que certifiquem identidade visual. Menus locais têm precedência.

A extensão MIT org.craftbridge.colorize implementa um modelo original, com
mapa declarativo e perdas permanentes. O ID é próprio, definido pelo manifesto;
nenhum ID nativo de destino é inventado. Catálogo fixado:
e38a92e792c07f1c57c5dcfcab37d91932b9e2b8. Nenhum código, binário, SDK ou asset
proprietário é incorporado. Defaults do manifesto são escolhas próprias.

| Sufixo BCC3Colorize- | Controle | Kind | Destino / domínio próprio |
|---|---|---|---|
| 6488072 | Input | 7 | input: 1..8 → 0..7; PixelChooser=9 recusado |
| 6488066 | Color Space | 7 | color_space: RGB/HSL/HSV 1..3 → 0..2 |
| 6492164, 6496260, 6500356, 6504452 | Color 2..5 On | 4 | color2_on..color5_on |
| 6488067, 6492163, 6496259, 6500355, 6504451, 6508547 | Color 1..6 | 5, quatro dimensões | color1..color6: ARGB-255 → RGBA |
| 6488069, 6488070 | Black/White Point | 2 | black_point/white_point: ±1000 |
| 6488071 | Squeeze | 2 | squeeze: ±100 |
| 6488086 | Loop Mode | 7 | Off/Forward/Back & Forth 1..3 → 0..2 |
| 6488079 | Loop Count | 2 | loop_count: 0..1000 |
| 6488080 | Gradient Offset | 2 | gradient_offset: ±1000000 |
| 6488073 | Color Ease | 2 | color_ease: ±100 |
| 6488075 | Hue | 3, graus | hue: ±10⁹ |
| 6488076, 6488077 | Saturation/Lightness | 2 | saturation/lightness: ±100 |
| 0116 | Mix with Original | 2 | mix: 0..100 |

Todos são obrigatórios para criar a instância: propriedade ausente, duplicada,
recusada ou menu PixelChooser impede criar uma substituição com defaults.
Grupos selecionados podem atualizar o plugin existente, mas não há amostra
real de Colorize selecionado; esse fluxo não recebe certificação real.
Hue preserva graus comprovados por kind 3. Demais sliders mantêm coeficientes
brutos; a interpretação numérica abaixo é calibração própria do renderer.

## Modelo e limites

Luma usa 0.2126/0.7152/0.0722 em RGB reto; canais invertidos usam 1-channel.
Black/White são divididos por 100. O coeficiente normalizado é limitado a 0..1;
thresholds iguais produzem step em white, invertidos dão declive reverso.
Loop usa base*count+offset/100: Off limita aos endpoints, Forward retorna
mod 1 fora de 0..1, Back & Forth usa triângulo de período 2. Forward conserva
o endpoint exato em v=1; em v=2 volta ao início. Convenções próprias explícitas.

Squeeze aplica t**2**(-squeeze/25). As cores habilitadas são redistribuídas
igualmente em 0..1. Na fração f entre knots, Ease aplica
f**e/(f**e+(1-f)**e), e=2**(ease/25). RGB é linear por componente; HSL/HSV usam
hue circular pelo caminho curto, com hue emprestado para endpoints acromáticos.
HSL ajusta cores dos knots antes da interpolação: hue+=graus/360, controles
negativos multiplicam saturation/lightness por 1+c/100, positivos aproximam
cada componente de 1 por c/100. HSL/HSV normalizam RGB a 0..1; RGB direto
conserva componentes negativos/HDR limitados ao domínio próprio.

Alpha de cor é cobertura 0..1, multiplicada por alpha original; Mix é uma
combinação premultiplicada por raw/100. Mix=100 conserva bytes float32 de
entrada. RGB invisível é limpo nos outros valores. Fonte RGB ±1000000,
alpha 0..1; knots finitos ±1000000, limites dos controles conforme manifesto,
até 8388608 pixels/lados 65536, |tempo|≤10⁹, scale 1/65536..16. Validação
precede escrita; esse domínio garante saída float32 finita. Alocação limitada
usa try_reserve; ABI exige buffer próprio, alinhamento e regiões disjuntas.
Tempo/scale não mudam o toning. Expressões nunca são executadas.

## Perdas e validação

PixelChooser/Mocha/tracking, Compare, recursos de camada/path e controles
preset/preview permanecem no relatório. Dados desconhecidos não viram None.
Fórmulas, espaços de cor, gamma/HDR/alpha e distribuição dos knots não são
certificados contra BCC. Strict recusa publicação parcial.

11 testes Rust e Clippy passaram. Rebuild Rust 1.98.1 é byte idêntico:
37843 bytes, SHA-256 57490acff49a7922ca18e26dec094b0993aa611725c56034d0b5d36ba1ff0a6e.
60 casos de pixels próprios passaram no loader WASM oficial com render direto
estrito, comparados com referência colorsys independente. Incluem oito
canais/três espaços, cores opcionais, inversões, loops, controles, alpha/HDR,
quatro conjuntos reais de controles e duas dimensões grandes. Full HD não
uniforme ~5,6 s e UHD ~22,2 s, sem mudar fuel/memória do loader.

Uma Session oficial descartável carregou o módulo final e aplicou quatro
instâncias reais, 92 valores estáticos, conferidos após salvar/reabrir. Esse
ensaio verifica parâmetros/persistência; os pixels são verificados separadamente
pelo loader, sem render.frame do aplicativo nem comparação BCC/Adobe.
Suporte universal permanece pendente.
