# Heatwave aproximado — 0.28.0

`craft-bridge extensions install heatwave` instala o mapa e indica o módulo
WASM. Carregue-o com `effect.plugins.load` no [host experimental API 2](experimental-multi-input-host.md),
revisão 1 ou revisão 2 compatível. O EffectCraft oficial/API 1 não aceita esse
módulo. A preparação usa uma cópia isolada; não modifica o aplicativo do usuário.

## Evidência e aplicação

Um snapshot FFX local completo comprova 24 controles de processamento, IDs,
tipos, pontos normalizados e ordem dos menus. Mask Layer continua kind 0 opaco.
[Documentação oficial Maxon](https://help.maxon.net/rg/en-us/Content/html/Distortions_heatwave.html)
informa a função geral. O FFX salva Shape None/Ellipse/Rectangle/Layer e Mask
Channel Luminance/Alpha; sua ordem prevalece sobre descrições de outras versões.
Nenhum código, SDK, binário, asset ou preset proprietário foi obtido/reutilizado.

Criação exige 25 propriedades: 24 controles e uma substituição manual de
Mask Layer, mesmo quando o Shape escolhido não usa a imagem de máscara. Null
é uma escolha explícita do destino, nunca None decodificado do blob. Os três
pontos exigem `--size` com as dimensões reais da camada de destino. Use o
[arquivo de vínculos de origem](mathops-extension.md), fixado ao SHA-256 e à
posição do efeito no IR, com esta entrada:

```json
{"preset_index":0,"effect_index":0,"parameter":"Universe_Distort_Heatwave-0025","layer_ref":null}
```

Para usar uma máscara de camada, substitua null por um nome simbólico, como
`"mask"`, e forneça `--bind-layer 'mask=Minha máscara'` durante a aplicação.

```sh
craft-bridge inspect preset.ffx --json
craft-bridge convert preset.ffx --size 1920x1080 --source-layers vinculos.json --out plano.json
craft-bridge apply plano.json --layer 'Minha camada' --dry-run
craft-bridge apply plano.json --layer 'Minha camada' --yes
```

1920x1080 é apenas exemplo; informe o tamanho efetivo. Recursos animados ou
com expressão, menus desconhecidos, pontos sem tamanho e coeficientes fora
dos limites são recusados. Grupos selecionados atualizam uma instância
existente, preservando recursos e controles não selecionados.

## Modelo e limites

O renderer Rust MIT é original aproximado. Sliders conservam valores brutos;
as fórmulas abaixo são calibração própria, sem unidade Universe presumida.

- Ruído value/fractal em três oitavas, funções Default/Billowed/Ridged e
  deslocamento X/Y determinístico. Heat Size e Detail Scale definem frequências
  próprias; Flow Direction tem graus comprovados por kind 3. Flow Speed usa
  `raw/100` nas coordenadas do ruído por segundo, sem simular a implementação Maxon.
- Intensidade usa `raw/100*dimensão_mínima*0,25`; Heat Bias regula a força.
  Blur tem campo independente, feather e detalhe próprios, com 4/9/16 taps
  estratificados e bilinear conforme Quality. Zero intensidade/blur ou Bias=100
  preserva a imagem. Não há reprodução certificada de ruído, blur, gama ou HDR.
- Shape None processa o quadro inteiro e ignora Invert. Ellipse/Rectangle usam
  Point A/B e raio `raw/100*dimensão_mínima`; feather assinado expande/puxa a
  borda. Layer usa escala `raw/100`, posição local e Luminance×alpha ou Alpha.
  Null é máscara preta; Invert pode torná-la branca. Exterior é transparente.
- Output tem cinco modos próprios: Final, Distortion, Blur, Mask e Mask Overlay.
  Os diagnósticos e o overlay magenta não reproduzem a UI Universe. Canvas,
  transformações/referências Adobe e modelos de alpha/cor não são reconstruídos.
- Intensity/Blur/Detail 0..100; Size/Detail Scale/Radius/Mask Scale 0..10000;
  Speed e feathers ±10000, direção ±1 milhão de graus, Bias ±100. Pontos
  finitos até ±1 bilhão de pixels; até 8.388.608 pixels/imagem e lados 65.536.
  O host mantém seus limites de memória/fuel; não há promessa de desempenho Full HD.

A conversão permanece PARTIAL. SOURCE_LAYER_REPLACED e os avisos de origem
são preservados; strict não publica um preset parcial. Não foi alterado o
parser FFX nem executada qualquer expressão extraída.

## Verificação

`uv run python scripts/build_heatwave.py` usa Rust 1.98.1. Onze testes Rust
cobrem controles espaciais/temporais, geometria, escala/offset, canais, alpha,
blur não uniforme, modos de saída, extremos e recusas. Testes Python verificam
mapa, limites, tamanho, recursos, menus completos, grupos selecionados e strict.

`scripts/validate_heatwave_renderer.py DIRETORIO_NOVO` usa uma Session própria
com 18 casos de pixels originais full/half, máscaras, atualização de imagem
auxiliar no mesmo instante, animação Linear, estado selecionado e reabertura.
`--real-presets CAMINHO_LOCAL` acrescenta um caso opt-in com os 24 controles
reais e uma substituição manual, usando gradiente original como imagem de teste.
Fixtures privadas não são distribuídas; não há comparação visual Adobe/Universe.

O corpus automático sem vínculos permanece em 129 PARTIAL/15 UNSUPPORTED,
3441 controles/561 chaves. Os 144 hashes e 1341 avisos relevantes permanecem
intactos. A conversão desse snapshot fica disponível mediante escolha manual
de recurso; suporte a todos os efeitos continua em andamento.
