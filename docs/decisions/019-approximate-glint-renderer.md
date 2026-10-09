# ADR 019 — Raios Glint originais, suporte S_Glint parcial

## Evidência e decisão

Em 08/10/2026 foi consultada a [documentação oficial Boris FX](https://borisfx.com/documentation/sapphire/ae/glint/).
Ela descreve highlights com raios, ganhos/tamanhos por eixo e canal, threshold,
filtros, hue e composição. Background e Matte podem alterar o resultado;
Mocha fornece máscaras. A descrição funcional não estabelece os kernels nem
a calibração interna. Não foram obtidos ou reutilizados código, binários, SDK
ou assets proprietários. A extensão MIT do Bridge é original e aproximada.

Dois snapshots locais comprovam descriptors parT/tdb4, IDs/tipos e menu Opacity.
25 controles mapeados: S_Glint-0050/0100/0052..0056/0058..0071/0101 são numéricos
kind 2; 0051/0057 são cores kind 5 ARGB255; 0074 é menu kind 7
All Opaque/Normal/As Premult, 1..3 para 0..2. IDs preservados no mapping.json.
Um snapshot possui 12 chaves Linear: Brightness, Threshold, Threshold Blur,
Size e Blur Glint com duas cada; Hue Shift e Threshold Add Color com uma cada.
Tempos 36864/24576 = 1,5 s e 37888/24576 = 1,541666… s. Nenhum lado Bezier
real está presente nesses streams.

Background 0001, Matte from Layer 0002, Matte from Path 0235 e Mocha 0520
continuam opacos. Controles dependentes de máscara não são mapeados, nem
Invert Matte/Matte Type, Expand Borders ou o widget Show Size. A aparência não
é certificada e o estado vazio de dependências não é inferido de bytes zero.

## Algoritmo original e calibração

Normal usa RGB direto (premultiplicado dividido por alpha quando positivo),
As Premult usa os canais armazenados, All Opaque trata alpha como 1. Valores
RGB usados para highlights são limitados a 0..1000000; pixels de alpha zero
não contribuem nos dois modos transparentes. Threshold Blur usa uma caixa
separável com raio round(raw × scale), bordas zero e denominador constante.

Para cada canal, seed é max(RGB - threshold - thresholdAddRGB, 0), multiplicado
por alpha em Normal. Glint From Alpha interpola esse seed com
max(alpha - threshold - thresholdAddRGB, 0). Isso é um modelo próprio, não o
algoritmo comprovado da origem.

Quatro famílias de scanlines seguem X, Y, diagonal top-right/bottom-left e
diagonal top-left/bottom-right. Raio por canal = raw Size × Size eixo × Size RGB
× scale. Kernel bilateral original k[d]=(1-q)/(1+q) × q^abs(d), q=exp(-1/raio);
raio zero usa q=0. Recorrências forward/backward calculam a convolução sem custo
proporcional ao raio, incluindo a amostra central uma vez. Cada eixo recebe
seu ganho Brightness próprio. Diagonais usam distância em passos da grade, sem
correção euclidiana. Zero fora do quadro; nenhum wrap, extensão de canvas ou
recorte por máscara. Blur Glint usa outra caixa separável após somar os raios.

Brightness global e RGB não negativo de Scale Colors multiplicam a saída.
Hue Shift aplica rotação HSV por 6 × raw shift, sem transformação de gama.
Alpha dos controles de cor é conservado nos dados, mas não participa da fórmula
RGB. Entrada negativa para highlights e tint negativo são limitados a zero;
o RGB original da base é preservado na composição. HDR não negativo participa
do cálculo dentro dos limites próprios; isso não certifica gestão de cor Adobe.

Base RGB = inputRGB × Source Opacity × Bg Brightness; base alpha = inputAlpha
× Source Opacity (inputAlpha=1 em All Opaque). O ABI oferece uma imagem, então
essa base própria não representa referências reais de Background/Matte.
Glint alpha = clamp(max(glintRGB) × Affect Alpha,0,1). RGB final soma base e
glint × (1 - Glint Under Source × baseAlpha). Alpha final usa
baseAlpha + glintAlpha × (1-baseAlpha); All Opaque força 1. RGB com alpha final
zero torna-se zero. Brightness zero com mistura/base padrão nos modos
transparentes é identidade exata, mesmo para HDR/pixels transparentes.
Todas essas decisões de transparência são próprias e constam nas perdas.

## Limites, segurança e status

Limites próprios: Brightness/ganhos/Affect Alpha/Bg Brightness 0..64;
Hue Shift -1..1; Size/blurs 0..4096; tamanhos relativos 0..8;
threshold 0..1000000; mistura e alpha de cor 0..1; RGB de cor com módulo
até 1000000. Não são limites de origem inferidos. Fora do perfil, a conversão
recusa o parâmetro. Sem clamp silencioso de controles.

ABI oficial v1, 25 propriedades/31 doubles, sem imports, execução de expressão,
camadas ou arquivos. Até 8.388.608 pixels, lados até 65.536, scale
[1/65536,16], entrada finita com módulo até 1000000 e alpha 0..1.
Quatro buffers RGB usam 48 bytes/pixel além do quadro; todas as alocações são
verificadas antes de escrever saída. Complexidade O(N), independente do raio.
Recusa de parâmetros/dimensões/buffer/scale preserva o quadro. O piso de scale
previne overflow e não representa uma unidade descoberta da origem.

O mapa traz quatro limitações permanentes: algoritmo/calibração, dependências,
cor/transparência e quadro/máscaras/widgets. O resultado é sempre PARTIAL;
strict não publica o preset parcial. Suporte universal permanece pendente.

## Validação

Onze testes Rust verificam raios contra convolução direta independente,
quatro direções/canais, blur contra soma direta, cores, alpha, mistura,
identidade e rejeição sem mutação. Rust 1.98.1/Clippy passaram e rebuild
produziu bytes exatos. O loader WASM oficial passou em 30 casos: 27 sintéticos,
dois conjuntos reais de controles com pixels originais e Full HD (~23,2 s).
A Session oficial preservou dois componentes/50 propriedades/12 chaves após
reabrir; 15 samples escalares foram comparados com cálculo independente.
Corpus é opt-in e não distribuído. Sem comparação visual com Sapphire/Adobe.
