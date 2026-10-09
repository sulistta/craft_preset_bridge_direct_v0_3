# Godrays original aproximado — 0.36.0

A extensão `godrays` traduz 25 controles estáticos comprovados de `PEGR`,
identificado como Crate’s Godrays na amostra local. Renderer e wrapper WASM
são originais MIT, sem código, SDK, plugin ou asset ProductionCrate/Adobe.
A tradução permanece PARTIAL: transportar controles não comprova equivalência
visual, unidades dos sliders ou calibração. Strict não publica parcial.

```sh
craft-bridge extensions install godrays
craft-bridge convert preset.ffx --out plano.json
craft-bridge apply plano.json --layer 'Minha camada' --dry-run
craft-bridge apply plano.json --layer 'Minha camada' --yes
```

Carregue `bridge_godrays.wasm` por `effect.plugins.load` no
[host experimental API 2](experimental-multi-input-host.md). Instalar o mapa
não carrega o renderer. O upstream oficial requer preparação separada.
Reconstrua com `uv run python scripts/build_godrays.py`, Rust 1.98.1 fixado,
std somente. Manifesto: 25 parâmetros, 26 f64 achatados, uma entrada de imagem.

## Origem e limites

A amostra comprova Mode, Position, Threshold Mode, Threshold, Threshold Smooth,
Length, Spin Amount, Exposure, Decay, Direction, Chromatic Amount, Channels,
Quality, Samples, Noise, Repeat Edges, Buffer Expansion, Input Opacity,
Blend Mode, Unmult, View e quatro trims. IDs vêm de parT/tdb4; controles com
nome Amount são distinguidos pelos IDs reais. Position é Vec2 sem unidade,
preservado bruto; Spin Amount é ângulo em graus, preservado inclusive oculto.
Sliders kind 10 permanecem brutos; flags de exibição não certificam unidades.

Quality contém separador na posição 5: tabela 1/2/3/4/6 → 0/1/2/3/4, recusando 5.
Todos os 25 controles são obrigatórios na criação. Valores inválidos, expressões
ou controles necessários ausentes/opacos recusam o efeito inteiro, sem defaults
presumidos. Buffer Expansion somente zero: o host usa canvas fixo, e expansão
não neutra não é substituída por identidade.

O host fixado transforma Point por `q*scale+offset`. O renderer recupera o
valor armazenado por `(flat-offset)/scale` antes de seu modelo próprio de centro.
Isso evita escalar a posição duas vezes na prévia. Não é inferência de unidade
Adobe; é inversão do contrato verificado de transporte do destino.

## Matemática própria

- Centro `size*(0.5+positionRaw)`. Zoom amostra linha radial com fator
  `1-sign*t*LengthRaw/10000`; Spin usa rotação inversa em graus. Out/In usam
  sinais opostos; In & Out integra ambos com pesos normalizados.
- Qualidade própria: 8/16/32/64 taps ou Custom com Samples arredondado 2..256.
  Noise/100 desloca taps internos por hash espacial estático; endpoints
  preservados, sem evolução temporal implícita.
- Threshold usa luma linear 0.2126/0.7152/0.0722 ou chroma max−min sobre RGB
  straight. Threshold/Smooth /100 definem corte/smoothstep. RGBA premultiplicado
  é multiplicado pelo gate; alpha zero ignora RGB oculto.
- Pesos `exp(-DecayRaw*t)` normalizados, ganho RGB `2^ExposureRaw`.
  Chromatic desloca `t` em ±0.05*AmountRaw/100 no par escolhido; alpha inclui
  o máximo dos samples deslocados. Unmult próprio usa máximo positivo de RGB
  dos raios como alpha, limitado a 0..1.
- View: input processado com opacidade, raios ou composição final.
  Input Opacity/100 escala RGBA de origem. Screen usa `a+b-a*b`, Add soma RGB,
  ambos com alpha over. HDR/gama/gerenciamento de cor não calibrados na origem.
- Bordas bilineares clamp/transparent e trims em pixels lógicos próprios.
  Até 2097152 pixels, lados 65536, escala 1/65536..16. Limites pertencem ao
  renderer, não certificam faixas do plugin de origem.

Esses divisores e coordenadas são escolhas explícitas da aproximação, não
unidades certificadas. Animações não têm fixture real neste perfil. Máscaras,
expressões, versões futuras, expansão não neutra e fidelidade continuam perdas.

## Provas

11 testes Rust verificam impulsos analíticos, Spin, threshold em cor straight,
alpha zero, decay/exposure, bordas, canais, ruído, trims, geometria full/half/
padding e descritores malformados. Clippy passa com warnings como erros.
20 casos Python sintéticos verificam transporte, Quality, limites, controles
obrigatórios e strict. Um teste real opt-in confere os 25 valores contra o IR,
menus/tipos, ausência de mutação e integridade. São provas distintas.

`scripts/validate_godrays_renderer.py` passou dez casos na Session nativa:
radial full/half, luma/chroma, decay, Spin, trim e persistência de ruído/chromatic.
25 valores reais foram conferidos por `prop.get` antes/depois de reabrir,
com render full/half de pixels uniformes próprios. Nenhuma imagem Adobe comparada.

O exemplo `godrays_hd.rs` confere cada pixel de workload uniforme 1920×1080,
Exposure=2, Noise=100, Custom Samples=256. Amostragem clamp de buffer processado
exatamente constante permanece constante; a integral é avaliada algebricamente.
Isso não mede desempenho de raios em imagens arbitrárias.

Corpus com extensões e perfil local de flare: 3596 parâmetros/561 chaves,
132 PARTIAL/12 UNSUPPORTED. Avisos relevantes e hashes de origem preservados;
suporte universal permanece aberto.
