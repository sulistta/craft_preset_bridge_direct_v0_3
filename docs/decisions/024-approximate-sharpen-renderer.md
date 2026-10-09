# ADR 024 — Multiband Sharpen original aproximado

## Evidência de origem e decisão

Um snapshot completo local parT/tdb4 de S_Sharpen comprova 15 controles de
processamento, estáticos, e a ordem de dois menus. O arquivo privado não é
distribuído. A [documentação oficial Boris FX](https://borisfx.com/documentation/sapphire/ae/sharpen/)
foi consultada em 08/10/2026: descreve sharpening, detalhes, rejeição de bordas,
qualidade e cor. Show Small Detail Size controla o widget de edição da origem.
Ela não publica kernels ou calibração que certifiquem equivalência.

| Sufixo S_Sharpen- | Controle | Kind | Destino | Domínio próprio |
|---|---|---|---|---|
| 0001 | Quality | 7 | quality | Best/Fast → 0/1 |
| 0050 | Sharpen Amp | 2 | amplitude | -64..64 |
| 0105 | Edge Threshold | 2 | threshold | 0..1000000 |
| 0106 | Small Detail Size | 2 | detail_size | 0..8192 |
| 0107 | Scale Tiny Details | 2 | tiny | 0..64 |
| 0108 | Scale Small Details | 2 | small | 0..64 |
| 0109 | Scale Medium Details | 2 | medium | 0..64 |
| 0110 | Scale Large Details | 2 | large | 0..64 |
| 0051 | Sharpen Width | 2 | width | 0..8192 |
| 0100 | Sharpen Luma | 2 | luma | 0..64 |
| 0101 | Sharpen Chroma | 2 | chroma | 0..64 |
| 0102 | Sharpen Red | 2 | red | -64..64 |
| 0103 | Sharpen Green | 2 | green | -64..64 |
| 0104 | Sharpen Blue | 2 | blue | -64..64 |
| 0052 | Opacity | 7 | opacity | All Opaque/Normal/As Premult → 0/1/2 |

Sliders mantêm os valores brutos. Não se atribui unidade nova ao IR nem se
substitui um valor desconhecido por um default. Os defaults do manifesto são
escolhas do renderer próprio. IDs org.craftbridge.sharpen são da extensão
original, não IDs inventados para um efeito nativo de destino. O mapa usa o
catálogo EffectCraft fixado em e38a92e792c07f1c57c5dcfcab37d91932b9e2b8.

## Modelo original e limites

B(r) é um box separável com replicação de bordas. Para r=n+f, os taps
inteiros -n..n pesam 1; os taps externos ±(n+1) pesam f; normalização 2r+1.
Somas deslizantes mantêm custo O(pixels), inclusive com r maior que o quadro.
Cada passe acumula float64 e armazena float32. Os raios são raw*preview_scale.

Best usa B(0.5d), B(d), B(2d), B(4d), d=detail_size*scale. As quatro bandas
são Source-B(0.5d), B(0.5d)-B(d), B(d)-B(2d) e B(2d)-B(4d).
A alteração é a soma de (detail_gain-1)*band mais Source-B(width*scale).
Fast usa apenas Source-B(width*scale); detalhes multibanda não atuam nesse modo.
Isso é uma escolha funcional própria, não uma descrição do algoritmo Sapphire.

Best mede a borda por max(abs(Source-B(d))) nos três canais. Fast usa sua
diferença unsharp. O gate é clamp(1-edge/threshold,0,1); threshold=0 é
identidade. Quanto maior o limiar, menos bordas são rejeitadas.
A diferença luminosa usa 0.2126/0.7152/0.0722; chroma é delta-luma.
Cada canal recebe amp*gate*channel_gain*(luma_gain*delta_luma+
chroma_gain*delta_chroma). Não há calibração da resposta de cor da origem.

Normal limpa RGB invisível, limita a cor reta a ±1000000, filtra o RGB
premultiplicado/alpha e normaliza a cor pelo alpha filtrado. A alteração final
é premultiplicada pelo alpha original, que permanece intacto. As Premult usa
RGB armazenado e conserva alpha; All Opaque opera RGB armazenado e força alpha=1.
Amplitude zero, limiar zero ou ganhos de cor nulos conservam RGB bit exato.
Canal com ganho zero também conserva seu valor armazenado.

Entradas: pixels finitos RGB ±1000000, alpha 0..1, até 8388608 pixels,
dimensões 1..65536, scale 1/65536..16 e parâmetros finitos/tipados nos domínios
do manifesto. Tempo finito, sem estado temporal ou execução de expressões.
Alocações usam try_reserve; uma falha retorna erro. A saída inteira é verificada
antes de publicar. ABI valida dimensão, contagem, ponteiros, alinhamento e regiões
disjuntas do buffer próprio; chamadas inválidas não alteram os pixels.

## Perdas e validação

Matte from Layer kind 0, Matte from Path kind 12 e Mocha kind 11 permanecem
opacos. Controles numéricos/bypass locais não provam ausência dessas dependências.
Show Small Detail Size kind 4 é um widget não transferido, registrado como perda
de edição. Nenhum default público de Matte=None prova o estado do preset local.
Quatro perdas permanentes registram algoritmo, calibração, cor e dependências.
Strict recusa a publicação de todos os planos parciais.

11 testes Rust/Clippy passaram: box versus soma direta independente em ambos
os eixos, raios fracionários/maiores que o quadro, bandas, limiar/amplitude,
luma/chroma/canais, alpha/HDR, invisibilidade, preview scale e ABI inválido.
O loader oficial executou 32 casos WASM distintos com referência independente de imagem
pequena, parâmetros reais sobre pixels originais e Best/Fast Full HD não uniforme.
O quadro 3840×2160 não uniforme passou com os limites originais de fuel/memória
da engine, usando todas as amostras do box, sem amostragem esparsa. Uma Session
real aplicou/persistiu/reabriu 15 propriedades estáticas.
Menus alternativos e Bezier/Hold são verificados apenas com dados sintéticos.
Não houve comparação visual com Sapphire/Adobe nem uso de código/binários/assets
proprietários. Renderer e mapas são MIT; avisos Rust 1.98.1 acompanham o WASM.
