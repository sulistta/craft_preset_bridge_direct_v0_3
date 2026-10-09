# ADR 021 — Flicker temporal original, S_Flicker parcial

## Evidência e decisão

Em 08/10/2026 foi consultada a [documentação oficial Boris FX](https://borisfx.com/documentation/sapphire/ae/flicker/).
A descrição funcional informa modulação temporal de brilho/canais, ruído suave,
onda periódica e seed repetível. Não fornece PRNG, curvas ou calibração capazes
de certificar equivalência. Nenhum código, SDK, binário ou asset proprietário foi
obtido/reutilizado. A extensão MIT é independente, sem dependências Rust externas.

Um snapshot completo parT/tdb4 comprova 14 IDs escalares kind 2 consecutivos:
S_Flicker-0050 Amplitude; 0051 Rand Luma Amp; 0052 Rand Color Amp; 0053 Rand Freq;
0054 Wave Amp; 0055 Wave Freq; 0056/0057/0058 Wave R/G/B Phase;
0059/0060/0061 Red/Green/Blue Amp; 0062 Brightness; 0063 Seed.
Todos são coeficientes brutos. Não se deduz unidade pelo nome. Seed fracionário
0,12298583984375 é conservado exatamente. O snapshot é estático. Um grupo
selecionado separado contém 0050/0051/0053 com uma chave Linear em zero cada;
21504 é a base temporal desse stream, não uma constante do parser.

Load/Save/Help e grupos UI usam classificação administrativa existente.
ADBE Effect Mask Opacity=100 estático conserva o tratamento neutro comprovado.
Não se adicionou nenhuma leitura especulativa nem mapeamento por similaridade.

## Fórmulas próprias

O tempo chega pelo ABI oficial do frame. Noise usa quatro streams de ruído de
valor em lattice inteiro: um compartilhado (luma) e um por canal. O hash inteiro
usa todos os bits f64 do seed, incluindo a parte fracionária. Valores em [-1,1]
são interpolados por quintic 6u^5-15u^4+10u^3, contínua até segunda derivada.
Não há estado persistente, integração temporal nem dependência da ordem de frames.
Tempos negativos e subframes usam floor/time-fraction. Rand Freq multiplica time;
zero fornece ruído constante, sem ignorar os controles de amplitude.

Cada canal c recebe:

```text
randomTime = time * rawRandFreq
luma = rawLumaAmp * noise(randomTime, seed, 0)
color[c] = rawColorAmp * noise(randomTime, seed, c+1)
wave[c] = rawWaveAmp * sin(2*pi * frac(time*rawWaveFreq + rawPhase[c]))
gain[c] = max(0, brightness * (1 + amplitude*channelAmp[c]*(luma+color[c]+wave[c])))
out.rgb[c] = input.rgb[c] * gain[c]
out.alpha = input.alpha
```

Frequências como ciclos/segundo e fase como ciclos são interpretações do
renderer próprio; não são unidades de origem certificadas. Valores não são
convertidos, arredondados nem limitados pelo exportador para imitar o original.
Ganho negativo vira zero por decisão própria; não existe clamp SDR dos pixels.
HDR/valores RGB negativos e alpha recebido são conservados no domínio válido.
Ganho 1 preserva inclusive signed zero. Brightness=1/Amplitude=0 é identidade
exata; Brightness=0 gera RGB zero mantendo alpha. Scale não muda o resultado,
pois o efeito não tem geometria espacial. Sem conversão gamma automática.

## Limites, perdas e segurança

Domínio próprio: amplitudes/brightness 0..1000, frequências 0..10000,
phases ±1000000, seed 0..1000000000, |time| até 1000000000.
Até 8.388.608 pixels, lados 65.536; scale [1/65536,16]; canais RGB finitos
com módulo até 1000000, alpha 0..1. A multiplicação no domínio não ultrapassa
float32. O ABI valida tamanho, alinhamento e referências à própria alocação,
sem imports, arquivos, camadas externas ou expressões. Validação de todos os
pixels precede as escritas; entradas inválidas não alteram o frame.

Trabalho O(N), ganho calculado uma vez por frame, sem scratch adicional por
pixel. A tabela do manifesto tem 14 propriedades/14 doubles. As mesmas regras
permitem valores estáticos e curvas escalares tipadas já suportadas no Bridge.
Grupos selecionados exigem instância existente do módulo, com fingerprint
verificado; não criam cópias nem preenchem controles não selecionados.

Quatro perdas permanentes cobrem PRNG/fórmulas, unidades/calibração, alpha/cor
e evidência real limitada de animação. Sempre PARTIAL; strict não publica plano.
Não existe prova de equivalência visual com Sapphire. O objetivo universal
permanece em andamento.

## Verificação

Nove testes Rust/Clippy: identidade/HDR/alpha, seno contra valores independentes,
seed fracionário, ordem/tempos negativos, continuidade, streams de cor, frequência
zero, scale, limites e ABI inválido sem mutação. Rebuild Rust 1.98.1 byte idêntico.
Loader WASM oficial: 31 casos, com 26 sintéticos pequenos, quatro execuções com
dois conjuntos reais de controles sobre pixels próprios e Full HD (~2,2 s).
O conjunto selecionado usa defaults próprios para controles ausentes no teste
de pixels; isso não representa os valores não salvos no preset da origem.

A Session oficial confirmou um componente criado/14 valores estáticos e um
grupo existente/três propriedades/três chaves isoladas; file.saveAs/file.open
preservaram tudo. Grupo selecionado conservou UID/posição/enabled, propriedade
não selecionada com sentinel não default e composição inativa de destino.
Não há segmento animado real com múltiplas chaves para samples intermediários;
Bezier tem teste sintético separado. Nenhuma fixture privada é distribuída.
