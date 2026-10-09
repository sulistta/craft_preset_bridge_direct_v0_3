# Pixel Encoder original aproximado — 0.32.0

A extensão opcional `pixelencoder` converte 16 controles do perfil local
ADBE PixelEncoder - AEPlugins para padrões matemáticos originais. O lote
mantém 132 PARTIAL/12 UNSUPPORTED porque esse arquivo já continha outro
componente convertido; os controles exportados aumentam de 3530 para 3546.
As 561 chaves e os 1341 avisos relevantes permanecem preservados.

```sh
craft-bridge extensions install pixelencoder
craft-bridge convert preset.ffx --out plano.json
craft-bridge apply plano.json --layer 'Minha camada' --dry-run
craft-bridge apply plano.json --layer 'Minha camada' --yes
```

Carregue `bridge_pixelencoder.wasm` com `effect.plugins.load` em uma cópia
isolada do [host API 2](experimental-multi-input-host.md), revisão 1 ou
compatível posterior. O EffectCraft oficial não aceita essa extensão de ABI.
Reconstrução: `uv run python scripts/build_pixelencoder.py`, Rust 1.98.1.

## Evidência e perdas

Um parT/tdb4 real comprova oito sliders kind 10, quatro Bool, duas cores ARGB
255 e dois menus, total 16 controles (22 valores no ABI). Os dez padrões
seguem a ordem do arquivo: High Detail, Numbers & Letters, Horizontal Lines,
Dots, Vertical Lines, Extra Grunge, Rings, Solid, Diagonal Left e Right.
Chaos Behavior tem Increase Size, Decrease Size e Increase & Decrease Size.
Sliders permanecem brutos, sem unidade Adobe inferida. ARGB→RGBA tem unidade
comprovada no descriptor de cor. Criação exige todos os 16 controles.

A [descrição oficial](https://aescripts.com/pixel-encoder/) explica padrões
em tiles, ajuste de cor e caos, mas não certifica algoritmo ou calibração.
O perfil real não possui controles Advanced/Tone Detection das versões
mais recentes. Nada foi adicionado por assumir os IDs dessas versões.
Nenhum SDK, binário, asset, fonte, código ou preset proprietário copiado.

Renderer original aproximado, sempre PARTIAL. Tom, glifos, padrões, PRNG,
calibração, gamma/HDR, alpha e antialias permanecem diferenças. Máscaras e
expressões não são reproduzidas; strict não publica uma saída parcial.
Animação de sliders e estilos além do salvo são testes originais, não
fixtures Adobe adicionais. Arquivos de origem não são alterados.

## Modelo original

Todas as fórmulas/unidades internas são escolhas do renderer Bridge.

| Controle | Modelo e limites originais |
| --- | --- |
| Brightness / Contrast | Tom = clamp((Y−0,5)×contrast/100+0,5+brightness/100), Y=(R+2G+B)/4. Brightness ±100, contrast 0..1000. |
| Size / Detail X/Y | Largura da célula size×100/max(detailX,0,1); altura análoga. Size 0,1..1024, detail 0..1000. Lock usa a largura também na altura. |
| Cor amostrada | Vizinho mais próximo do centro da célula, borda clamp; não é média/integral de área. Grid segue offset/scale do buffer. |
| Patterns | High Detail usa limiar permutado 4×4; glifos próprios de sete segmentos; linhas, discos, grunge por hash, anéis, quadrados e duas diagonais. Cobertura binária no centro do pixel. |
| Pixel/Background Color | Cores RGBA declaradas; Use Original Color usa o centro da célula. Alpha da cor ×alpha do pixel original. Transparência produz zero RGBA fora da cobertura. |
| Chaos / Intensity / Behavior | Hash por célula e floor(tempo×speed); desloca o tamanho dentro da célula. Increase: 1+ruído; Decrease: 1−ruído; combinado: 1+2ruído−intensity/100, mínimo 0,01. Ruído é hash×intensity/100. |
| Speed / Seed | Speed ±10000, seed fracionário ±1e9; todos os bits do seed participam. Tempo só altera ruído quando Chaos está ativo; speed zero congela. |

O renderer mantém canvas fixo e até 2097152 pixels, sem ampliar budgets do
host. Células de preview podem aliasar e mudar cobertura; ausência de
antialias/filtro de redução é perda explícita. Glifos são matemáticos
originais, não o atlas proprietário e não um arquivo de fonte copiado.

## Validação

Seis testes Rust e Clippy all-targets passaram. Oito testes Python cobrem
conversão, cores, limites e strict. Um teste real opt-in separado verifica
os 16 valores e menus. Treze casos na Session real comprovam os dez padrões
full/half, cor original/transparência, caos fora de ordem/reabertura e 16
controles reais persistidos/reabertos sobre imagens próprias. Não há
comparação visual Adobe. [ADR 037](decisions/037-approximate-pixelencoder-renderer.md).

Um workload original Full HD (1920×1080, glifos de segmentos, fonte uniforme,
brightness/contrast neutros e marcadores red/blue) passou em ~3,5 s no loader
WASM nativo. Não é benchmark geral ou certificação visual. O exemplo
`pixelencoder_hd` do harness permite reproduzir após preparar o host.
