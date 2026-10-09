# ADR 013 — Renderer original de estiramento cumulativo

## Evidência de origem

Oito snapshots FFX autorizados comprovam parT/tdb4 para pixel_stretch em dois
perfis: três possuem 20 controles mapeados, cinco possuem 17. IDs, kinds e índices
dos menus vêm dos descriptors reais. Opções usam enum_map explícito 1-based→0-based.
Nenhum valor/nome de preset privado é incluído no pacote. Intensity Source (0018)
permanece grupo/dado opaco; não se interpreta None como ausência de dependência.

A [página oficial Satori/aescripts](https://aescripts.com/pixel-stretch/) foi
consultada em 08/10/2026: descreve acúmulo espacial conforme brilho, parâmetros
de tamanho e intensidade, variantes de canais, fonte alternativa, curva/fase,
distribuição, shading e modos de borda. A história confirma novos controles na
versão 1.6. Não especifica o algoritmo binário de reconstrução/calibração. Não
foram baixados/reutilizados SDK, código, plugin, manual empacotado ou assets.

## Implementação original

extensions/stretch contém Rust MIT sem dependências Cargo externas, manifesto e
WASM API v1. ID próprio org.craftbridge.stretch/0.1.0, 20 parâmetros escalares
tipados. Não usa ID ec.* nem declara equivalência Satori. Quatro perdas permanentes
mantêm toda conversão PARTIAL e fazem strict recusar a publicação.

- Scanlines percorrem direita/esquerda/baixo/cima; cada pixel gera um intervalo
  de largura `1 + intensity/100 × distribution × (pixel_size + stretch × curve - 1)`.
  Intervalos positivos contíguos acumulam deslocamento, com tamanho mínimo 0,001.
  A fase de imagem desloca o footprint de saída por phase/360 × comprimento ×
  intensity/100. Sync recalcula a geometria a partir da imagem deslocada com
  interpolação linear e as bordas escolhidas. São definições espaciais do Bridge.
- A cor premultiplicada constante por intervalo tem integrais prefixadas f64.
  Cada pixel de saída integra exatamente seu footprint de uma unidade nesse modelo
  de reconstrução. Busca binária localiza fronteiras; custo não cresce com stretch,
  compressão ou número de repetições. Wrap/Mirror integram períodos completos
  analiticamente, Clamp prolonga cores extremas, Transparent preenche fora com zero.
  Intervalos interiores dispensam aritmética de borda sem mudar a reconstrução.
- Brilho usa cor direta RGB (alpha >10⁻¹²), coeficientes próprios 0,2126/0,7152/0,0722,
  ou o canal escolhido. Alpha gera seu próprio campo quando selecionado. Brilho é
  limitado a 0..1 apenas para a geometria; HDR de cor permanece até o limite de saída.
  RGB separado reconstrói cor direta com o alpha do mesmo footprint e depois usa
  o alpha final escolhido. Luma/RGB no Alpha conservam alpha original. Esse tratamento
  de premultiplicação não é certificado contra o plugin de origem.
- Curvas próprias: t, 1−t, triangular, meia onda cosseno, t² e (1−t)². Phase desloca
  t periodicamente; fase zero mantém os endpoints exatos. Smoothness usa nove taps
  periódicos em janela valor/100. Uma LUT de 1025 posições, interpolada linearmente,
  calcula a geometria. Curvas exponenciais/smoothing originais não são reproduzidos.
- Start Offset usa percentual do scanline. Dentro do range, distribuição é constante
  ou uma rampa. Range 0 não estira; 0..1 limita a extensão por comprimento×range;
  >1 usa todo o restante do scanline. Além dessa extensão a geometria volta à largura
  1. Essa definição finita de distribuição é própria, especialmente com repetições.
- Shading usa padrões seno, triangular, rampas ou pulso de duty 0,1; período
  shade_size×buffer_scale e fase/360. Opacidade × intensidade atenua RGB ou todo
  RGBA para dimming de alpha premultiplicado. Feather aplica uma rampa pela distância
  à borda do domínio transparente, avaliada no centro do footprint. Tamanho de pixel
  e stretch são razões por amostra; não são escalados novamente no preview.

Neutralidade geométrica sem phase/shading e intensidade zero preservam a entrada
byte a byte. Todos os cálculos/alocações usam buffer temporário; erros não publicam
pixels parciais. ABI valida ponteiros/ranges/alinhamento/nparams contra ec_alloc.
Até 8.388.608 pixels/lado 65.536, scale (0,16], RGB de entrada ±10⁶ e alpha 0..1.
Parâmetros e fases têm limites explícitos de manifesto, com recusa na exportação.
Limites oficiais de fuel/memória não foram aumentados; o host pode recusar frames
complexos. Não há acesso a outra camada, arquivos, scripts, expressões ou assets.

## Verificação

Rust 1.98.1/wasm32-unknown-unknown, Cargo.lock, release/LTO; avisos std/compiler-builtins
acompanham o pacote. Sete testes Rust cobrem cobertura subpixel cumulativa e orientações,
bordas/períodos/deslocamentos grandes, todos os canais/curvas/shadings, HDR/alpha,
controles, neutralidade/preview e recusas sem mutação. Clippy é executado com warnings
como erros. Um build independente reproduziu os 76037 bytes do módulo, SHA-256
c9d1e879b65fe0e9d193901302ad7acdb5f675eff7ffe160f202e167d18462dd.

`python scripts/validate_stretch_renderer.py NOVA_SAIDA --corpus PASTA --hd` usa o
loader WASM oficial com traps explícitas. Os pixels de entrada são originais/sintéticos;
os oito conjuntos de controles opcionais vêm dos presets locais, sem comparação Adobe.
Doze cenários têm expectativas de pixels independentes, incluindo footprints cruzando
fronteiras de segmentos, todos os edge modes, quatro direções, HDR e shading.
O teste Full HD exercita RGBA separado, compressão e smoothing, e registra o tempo.
Os 21 casos passaram; os oito conjuntos de parâmetros reais produziram pixels
diferentes da imagem de teste. Full HD levou ~72 segundos. A otimização de bordas
conservou exatamente os 21 resultados comparados com a versão anterior (~78 s).
Isso verifica o renderer próprio; não é prova de fidelidade à implementação Satori.

Na Session oficial fixada, oito componentes reais preservaram 145 propriedades
estáticas após salvar/reabrir. Não há keyframes reais nessas instâncias. Uma fixture
selecionada inteiramente sintética preservou três controles/seis chaves, quatro
lados Bezier e nove amostras intermediárias; UID/índice/enabled, composição inicialmente
inativa e controles não selecionados permaneceram iguais após reabertura.

Com Glow, Shake, biblioteca Flare e Stretch, o corpus gera 117 PARTIAL/27 UNSUPPORTED,
3036 propriedades/484 chaves; zero SUCCESS. Intensity Source, máscaras, UI privada e
diferenças do renderer continuam perdas. Suporte universal/fidelidade permanecem pendentes.
