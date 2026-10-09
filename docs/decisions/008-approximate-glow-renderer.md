# ADR 008 — Renderer próprio e parcial para PEDG

## Evidência de origem

PEDG é o match name encontrado no corpus privado. Seus 23 snapshots completos
contêm os descriptors parT que comprovam os 13 IDs/tipos do mapa opcional.
As outras 50 ocorrências são caminhos selecionados ou estruturas sem esse perfil
de tipos; continuam sem conversão nesta etapa. Não são contadas como 73 instâncias
completas. Valores, nomes de arquivos e presets privados não entram no pacote.

O [arquivo oficial Deep Glow v1.5.7](https://www.plugineverything.com/s/Deep-Glow-v157.zip),
listado em [Previous Versions](https://www.plugineverything.com/previous-versions),
contém o manual **v1.4.6**. Foi lido somente o manual; nenhum binário proprietário
foi executado, reutilizado ou distribuído. O manual documenta Exposure como
multiplicador posterior ao threshold; Threshold 100% corresponde a luminância 1,
com HDR acima disso; Screen limitado a 1/Add HDR; Aspect 0/1/2 vertical/isotrópico/
horizontal; tint; View; Source Opacity e Unmult. Também registra Spread depreciado
na 1.2.3 e Smooth Blending sempre ligado desde 1.3. Portanto os controles antigos
do corpus não determinam a versão do algoritmo proprietário.

## Implementação original

`src/craft_bridge/extensions/glow/` contém um crate Rust MIT sem dependências, seu
manifesto, mapa e módulo WebAssembly reproduzível. ID **org.craftbridge.glow**, nome
**Bridge Glow (Approximate)**, API oficial v1. Não usa nome/ID nativo ec.stylize.glow
nem se apresenta como o renderer Deep Glow.

Os 13 controles são Radius, Exposure, Threshold, Threshold Smooth, Blend, Aspect,
Tint Enabled/Color/Mode/Mix, View, Source Opacity e Unmult. Menus da origem são
1-based e usam tabelas explícitas. Cores ARGB/255 viram RGBA. Escala, valores e
keyframes permitidos pelo Bridge são transferidos; o renderer implementa a fórmula
abaixo, cuja equivalência Adobe **não foi comprovada**.

- Luminância de entrada em RGB desmultiplicado, pesos 0.2126/0.7152/0.0722.
  Pixel com alpha zero não emite luz. Limiar T=Threshold/100 e joelho K=T×Smooth/100:
  smoothstep entre T−K e T+K; K=0 é binário; T=0 admite luminância positiva.
  O fator de Exposure multiplica RGB premultiplicado **depois** dessa seleção.
- Seis escalas independentes com pesos 0.32/0.24/0.18/0.12/0.08/0.06. Cada escala
  usa o raio nominal Radius×scale×2^i/96, ponderado por Aspect e 2−Aspect.
  Uma pirâmide reduz cada eixo por potências de dois enquanto seu raio excede 4
  samples; usa filtro tent centrado (1/4,1/2,1/4), três boxes separáveis com raio
  arredondado nessa resolução e reconstrução bilinear. Eixo com raio zero não é
  reduzido. Padding é preto. Somas f64 e janelas deslizantes mantêm custo
  O(pixels), sem loops proporcionais a Radius. Esta calibração espacial é própria;
  o controle de origem não é declarado uma distância equivalente em pixels.
- Glow Input devolve a fonte selecionada, antes de blur/tint/composição. Final usa
  Screen ou Add e Source Opacity; tint Standard multiplica e Overlay/Soft Light
  usam fórmulas [W3C](https://www.w3.org/TR/compositing-1/#blending).
  Os modos W3C limitam seus operandos a SDR; Standard/Add preservam HDR.
- Unmult false produz alpha 1 (fundo preto); true gera alpha pelo maior componente
  absoluto de RGB, limitado a 0..1. Isso é uma escolha do Bridge, não engenharia
  reversa do alpha proprietário. O alpha do seletor Tint não controla o glow.

A API v1 só transmite pixels, tempo e scale: não há informação do espaço de cor
para reproduzir Auto Detect Gamma. Gamma, Spread/Smooth Blending, aberração,
qualidade/downsample/steps/iterations, dither, máscaras e expansão/recorte de bordas
continuam perdas. O buffer não cresce. Sua dimensão máxima é 8388608 pixels;
scale deve estar em (0,16], alpha em 0..1 e componentes de entrada finitos com
magnitude até 1e6. Controles possuem limites declarados no manifesto; erros, valores
não finitos e menus inválidos são recusados antes de alterar pixels. O loader
oficial conserva o frame se houver erro/trap/fuel; a auditoria exige sucesso explícito.

## Uso e relatório

Extensão **opcional**: `craft-bridge extensions install glow` instala somente o mapa
no diretório de configuração. A saída mostra o path absoluto do WASM, que deve ser
carregado no EffectCraft por Load Effect Plug-in ou effect.plugins.load. Não há
instalação Adobe, download ou execução durante parsing/instalação de mapas.
`extensions list` é somente leitura. Após instalar, reinicie a GUI para reanalisar.

`Mapping.limitations` gera avisos de perda MAPPING_APPROXIMATION em **toda** conversão,
inclusive com todos os 13 controles transferidos. Assim nunca retorna SUCCESS por
aceitação de parâmetros, e strict recusa saída parcial. Planos v3 fixam o manifesto;
o preflight exige esse renderer registrado. Os 32 mapas builtin continuam independentes.

Build reproduzível:

```sh
rustup target add wasm32-unknown-unknown --toolchain 1.98.1
.venv/bin/python scripts/build_glow.py
CARGO_TARGET_DIR=artifacts/glow-target cargo +1.98.1 test --locked \
  --manifest-path src/craft_bridge/extensions/glow/Cargo.toml
.venv/bin/python scripts/validate_glow_renderer.py artifacts/nova-validacao-glow --hd
```

A distribuição inclui o módulo compilado e seu código original. Usuários não precisam
instalar Rust. O harness nativo otimiza o interpretador wasmi para medir a execução
com custo representativo de builds de produção; as demais bibliotecas permanecem
no perfil de desenvolvimento. Não há garantia de desempenho em hardware diferente.

## Validação

Oito testes Rust verificam blur contra convolução ingênua, impulso/energia/simetria,
HDR/threshold/exposure, premultiplicação, aspect, composição/tint/alpha, erro sem
mutação e scale. Auditoria WASM usa pixels sintéticos originais e o loader oficial,
com erro de render explícito, não fallback de frame inalterado. Isso não é fixture
Adobe nem comparação visual contra o plugin.

23 componentes reais preservaram **299 controles**, todos conferidos por prop.get
após salvar/reabrir .ecproj. Não têm chaves exportáveis nesta seleção; animação de
Radius é testada separadamente em fixture sintética. As 144 entradas mantêm seus
hashes. Com extensão instalada e referência 1920×1080: **80 PARTIAL/64 UNSUPPORTED**,
1669 parâmetros/17 chaves, zero SUCCESS. Sem a extensão: 75/69, 1370/17.
Evidência privada final em artifacts/glow-native-final-v0.9/, nunca redistribuída.

Nove casos WASM passaram, incluindo um frame Full HD de 2073600 pixels com Radius
2000 e sucesso explícito do renderer. Tempo observado no harness otimizado: cerca
de 21–23 segundos/frame neste ambiente; o módulo é CPU/WASM, sem GPU, e ainda lento
para preview em tempo real. Os ensaios anteriores excederam 60 segundos e motivaram
a pirâmide adaptativa. Esse benchmark é sintético; não mede um preset Adobe nem
prova equivalência visual. Artefatos: artifacts/glow-render-final-v0.9/.

O WASM inclui biblioteca padrão/compiler builtins da toolchain Rust 1.98.1; seus
avisos e textos de licença são distribuídos junto ao módulo em licenses/.
