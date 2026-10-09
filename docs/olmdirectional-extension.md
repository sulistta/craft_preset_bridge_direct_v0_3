# OLM Directional Blur original aproximado — 0.35.0

A extensão `olmdirectional` traduz 14 controles de processamento comprovados
por um parT/tdb4 e a entrada de transporte Noise Layer. Angle=106 graus,
Front Blur Strength=140, Back=0, Gain=1 e Noise Type=Smooth são os valores
reais observados. Demais sliders permanecem brutos; a escala interna dos
kind 2 versus percentuais da interface não é certificada.

```sh
craft-bridge extensions install olmdirectional
craft-bridge convert preset.ffx --out plano.json
craft-bridge apply plano.json --layer 'Minha camada' --dry-run
craft-bridge apply plano.json --layer 'Minha camada' --yes
```

Carregue `bridge_olmdirectional.wasm` por `effect.plugins.load` numa cópia do
[host experimental API 2](experimental-multi-input-host.md). O upstream
oficial exige essa preparação separada. Reconstrua com `uv run python
scripts/build_olmdirectional.py`, Rust 1.98.1 fixado, std somente.
O manifesto possui 16 parâmetros (14 controles, Layer e seu modo Source),
17 valores f64 achatados e duas entradas de imagem.

## Noise Layer e prova de inatividade

O manual oficial do [pacote OLM](https://www.olm.co.jp/post/olm-directional-blur)
especifica Noise Layer somente para o modo Layer. O menu real é
Smooth/Block/Layer, nessa ordem. O mapa declara:

```json
"inactive_when": {"OLM Directional Blur-0016": [1, 2]}
```

Smooth/Block deve ser um enum estático único, obrigatório, sem chaves,
expressão ou perdas de leitura. Apenas nessas condições, e sem substituição
manual, a entrada recebe null de transporte. Não é None decodificado nem
remoção do vínculo original: `SOURCE_LAYER_INACTIVE` e `UNDECODED_VALUE`
permanecem perdas. A entrada opaca também precisa estar presente e estática;
expressões/animação no recurso continuam recusadas.

Layer exige [vínculo manual fixado ao hash/índice/ID](mathops-extension.md),
inclusive para escolher null explicitamente. `parameter` é
`OLM Directional Blur-0017`. Use --source-layers na conversão e --bind-layer
'noise=Nome da camada' na aplicação. O recurso deve ter as mesmas dimensões,
scale e offset da fonte; composições/transforms/effects exigem preparação
explícita. Um vínculo fornecido pelo usuário tem precedência sobre a condição
inativa. Seletor incerto jamais autoriza null automático. Strict não publica
um resultado parcial, inclusive quando a inatividade é comprovada.

## Evidência pública e modelo original

Pacote oficial consultado em 09/10/2026: ZIP de 11811644 bytes, SHA-256
`6ba3d12c5d7e72dd2ae357777126c5ee58dd5afb2e12398ecb4d733840b9c099`.
Contém manual EN 2017–2022, licença Apache 2.0 e plugins compilados; nenhum
código-fonte. Só o manual foi extraído. Nenhum .aex foi executado ou distribuído;
o ZIP/manual de pesquisa ficam fora da distribuição. O kernel abaixo é
original MIT, não implementação OLM obtida do pacote.

O manual descreve blur anisotrópico que ignora pixels totalmente transparentes,
grupos opacos, blur até 4000 pixels, variações de tamanho/ruído, fades, caudas
e ruído Smooth/Block/Layer. A figura usa Alpha Fade; o texto usa Edge Fade.
A versão de origem não é inferida desse manual. Não há comparação visual
Adobe/OLM, nem certificação das fórmulas/unidades internas.

| Controle | Modelo original Bridge |
| --- | --- |
| Angle | Vetor (cos,sin) em coordenadas de imagem, com graus comprovados; limite ±360000. |
| Front / Back | Busca de fonte no sentido oposto/igual ao vetor para cada lado, até 64 amostras bilineares por lado; raw 0..4000, escalado pelo buffer. |
| Brightness Gain | RGB final multiplicado por raw 0..64; alpha conservado. |
| Size Variation | Componentes 8-conectados em alpha>0. Normaliza sqrt(area) entre menor/maior grupo; factor=1−raw/100+raw/100×normalized. Se todos iguais, normalized=0. |
| Alpha Fade | Alpha/RGB premultiplicados do candidato multiplicados por 1−raw/100×distância/comprimento; raw 0..100. Não certifica Edge Fade nas bordas do algoritmo OLM. |
| Sharp Tail | Limita fontes pelo eixo perpendicular central do bounding box do grupo, estreitando pela distância relativa; raw 0..100. |
| Noise Variation | Multiplica o comprimento por 1−raw/100+raw/100×noise; raw 0..100. |
| Noise Type | Smooth: hash de células perpendicular à direção, com smoothstep. Block: célula constante. Layer: luma própria clamp 0..1 da entrada substituta; null explícito fornece zero. |
| Seed / Offset / Thickness | Hash original dos bits f64 do seed (±1e9). Offset em graus desloca a fase por raw/360, não avança com tempo implícito. Thickness (1..100) é o tamanho de célula do modelo. |

O candidato de maior alpha vence, sem diluir RGB pela quantidade de pixels
transparentes. Ties preservam a origem ou o candidato mais próximo encontrado
(front antes de back). Pixels totalmente opacos preservam seus detalhes;
RGB oculto em alpha zero não vaza. Comprimentos extensos usam amostragem
esparsa e podem perder traços estreitos. Canvas fixo; até 2097152 pixels/
imagem; parâmetros/imagens finitos, transporte validado e saída completa
antes de publicar. Espaço de cor, HDR, premultiplicação, antialias, topologia,
fades, kernel e calibração continuam perdas, sempre PARTIAL.

## Verificação

Nove testes Rust cobrem direções/escala, alpha/intensidade, ruído de camada,
seed/fase, grupos/tamanho/caudas, RGB oculto e bounds. Testes Python cobrem
inatividade Smooth/Block, recurso ativo, ambiguidade/expressão/animação,
bounds de controles/mapa e strict. Amostra privada é opt-in e não distribuída.
Doze casos na Session real usam um emissor de impulso original API 1, imagens
originais e guias nativas para ruído: full/half, front/back/vertical/fade,
Layer white/black/gray, size variation, dois ruídos, ordem temporal,
reabertura e 14 valores reais sobre fonte própria uniforme. Não são pixels
renderizados pela origem Adobe.

Workload Full HD inteiramente opaco e uniforme, Front=140/Angle=106/Smooth,
levou ~1,8 s no loader WASM nativo; saída analítica conferida em todos os
pixels. A regra de preservação de detalhe opaco evita a busca de raios nesse
workload. Não mede cenas transparentes complexas nem desempenho geral.
