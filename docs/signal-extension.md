# Signal aproximado — 0.29.0

`craft-bridge extensions install signal` instala o mapa e indica o módulo
WASM. Carregue-o com `effect.plugins.load` no [host experimental API 2](experimental-multi-input-host.md),
revisão 1 ou 2 compatível. O EffectCraft oficial/API 1 não aceita esse módulo.
A cópia experimental preserva o aplicativo e os presets do usuário.

```sh
craft-bridge extensions install signal
craft-bridge inspect preset.ffx --json
craft-bridge convert preset.ffx --out plano.json
craft-bridge apply plano.json --layer 'Minha camada' --dry-run
craft-bridge apply plano.json --layer 'Minha camada' --yes
```

## Evidência e perdas

Dois snapshots locais completos de `ADBE Signal` comprovam 26 sliders kind 10,
seis checkboxes e dois menus. Os 34 controles exigidos na criação são
preservados, sem atribuir unidades aos sliders. Emulating VHS usa
VHS_SP/VHS_LP/VHS_EP; Low-Pass filter out usa Off/Lite/Strong, na ordem parT.
Os snapshots diferem no switch Luma modulation. Não têm chaves nesses controles.
A [descrição oficial Zaebects/aescripts](https://aescripts.com/signal/) informa
modulação/decodificação de luminância e crominância, ruído e distorção, mas
não as fórmulas ou calibração necessárias para equivalência.

Destruction button (0012) permanece sem tradução. O valor false salvo não
comprova a ação do botão ou quais propriedades seriam modificadas; não foi
inventada uma ação para ele. Grupos, presets, Force CPU/GPU, máscaras e
expressões não são reproduzidos. Avisos de origem e perdas permanentes ficam
no relatório. Criação incompleta ou fora dos limites é recusada; grupos
selecionados atualizam uma instância existente sem substituir seus outros
controles/chaves. Sempre PARTIAL, strict sem saída parcial.

Código Rust MIT original, sem dependências Rust externas, código, SDK,
binário, asset ou preset proprietário. Nenhuma expressão extraída executada,
parser modificado, comparação Adobe ou certificação Zaebects realizada.

## Modelo próprio

Todas as fórmulas a seguir são escolhas do renderer Bridge, **não unidades ou
algoritmos decodificados da origem**. RGB é tratado sem premultiplicação;
alpha original permanece na posição original, inclusive sob distorção.

| Controles | Modelo Bridge |
|---|---|
| Strength / Amplification | Blend raw/100 entre original e processado; amplificação da luminância antes da portadora. Strength zero é identidade exata. |
| Luminância / crominância | Matriz oponente própria: Y=(R+2G+B)/4, I=R−B, Q=G−(R+B)/2; inversa exata. Não é transformação certificada YIQ/NTSC. |
| Luma/Chroma noise / seed | Hash de todos os bits do seed, coordenadas locais e floor(tempo×30); ruído assinado raw/100. Seed fracionário preservado. Relógio de 30 Hz é próprio, não FPS decodificado. |
| Hue Noise / Phase shift / offset | Rotação de I/Q por 2π×(noise×hue + phase_shift + phase_offset×y_normalizado)/360. Divisor 360 é calibração própria; kind 10 não prova graus. |
| Chroma loss / connections | Crominância ×(1−loss)×exp(−connections×0,06); connections também mistura vizinhos de luminância por raw/100. Não reproduz gerações de equipamento certificado. |
| Luma On / Frequency / Phase / Lightness | Y×[1+lightness×sin(2π×(y_normalizado×frequency×8 + tempo×frequency + phase/360))]. |
| Quantize | Zero desliga; demais valores quantizam Y em max(2,256−raw×2,54) níveis. |
| Tape Errors / start / end / probability / fade / gamma | Sorteio determinístico por instante; faixa vertical start..end, borda smoothstep com fade/100 e expoente max(gamma,0,001). Atenua cor/Y e adiciona ruído. Intervalo invertido é vazio. |
| Thick / Fine / distortion speed | Deslocamento horizontal periódico: width/100×[thick×sin(2π×(3y+t)) + fine×sin(2π×(83y+7t))], t=tempo×speed/100. |
| Roll speed | Deslocamento vertical tempo×raw/100×height, com repetição bilinear. Canvas fixo. |
| Cutoff / Low-Pass in / VHS | Mistura dos vizinhos horizontais por (1−cutoff/100)×(1+VHS_index/2), limitada a 0..1; distâncias de 1/2/4 amostras. Não modelos SP/LP/EP certificados. |
| Sharpen / On-Off | High-pass da luminância com coeficiente raw/10 e os vizinhos horizontais. |
| Scanlines blur / Chroma vertical blend | Mistura vertical dos vizinhos com coeficiente scan_blur/100 para Y e 0,5 para I/Q quando ativada. |
| Portadora / S-video / Low-Pass out | Quatro amostras por pixel: Y+Icos+Qsin; S-video separa Y. Receptor FIR triangular de raio 0/1/3, com 25% da amostra direta +75% filtrada; demodulação em quadratura. Composite permite cross-talk. Não simulação física certificada. |

Filtro/amostragem dependem da resolução do buffer: preview reduzido recebe
geometria real, mas não promete identidade com downsample do render completo.
Gamma/HDR/cor/alpha, frequência da portadora, estatísticas de ruído, erros de
fita e calibração visual proprietários são perdas explícitas.

## Limites e verificação

Os limites são do Bridge, não faixas certificadas do plugin de origem:
seed 0..1e9; strength/cutoff/noises/sharpen/quantize/fade/gamma/scanblur 0..100;
amplification 0..64; Hue Noise 0..10000; chroma loss/start/end/probability 0..1;
connections 0..16; lightness/thick/fine ±100; frequency/speeds ±10000;
phase/shift/offset ±1 milhão; menus inteiros 0..2 e checkboxes booleanos.
Até 2.097.152 pixels/imagem, lados 65536, tempo finito ±1e9; host conserva
limites de memória/fuel. Não há benchmark nem promessa de desempenho Full HD.

Dez testes Rust cobrem inversa HDR, identidade, matemática independente,
resposta dos 34 controles, seed fracionário, repetibilidade, geometria/alpha,
menus, tape errors, escala e recusas de descritores. Dez testes Python e um
real opt-in verificam mapa, leitura, limites, grupos e strict. Session real
experimental: 13 casos próprios full/half, modulação/amplificação com valores
analíticos, menus, ruído temporal/reverso, animação Linear e projeto reaberto.
Dois casos opt-in verificam 68 valores reais persistidos sobre imagens
originais, também após reabertura. Nenhum pixel de origem Adobe comparado.
