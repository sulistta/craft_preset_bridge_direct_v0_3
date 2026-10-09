# HitFilm Hotspots original aproximado — 0.34.0

A extensão `hfhotspots` converte cinco controles visíveis de
`com.FXHOME.HitFilm.Hotspots` para um renderer original. Dois snapshots
parT/tdb4 comprovam Threshold kind 10 (0,75 / ~0,3), Threshold Add Color
kind 5 ARGB255, Saturation/Brightness kind 10 (=1) e Smooth Source visível
kind 10 (=0). Não há Layer de processamento declarado nesses snapshots.
O grupo administrativo -0000 não é interpretado como uma máscara.

```sh
craft-bridge extensions install hfhotspots
craft-bridge convert preset.ffx --out plano.json
craft-bridge apply plano.json --layer 'Minha camada' --dry-run
craft-bridge apply plano.json --layer 'Minha camada' --yes
```

Carregue `bridge_hfhotspots.wasm` por `effect.plugins.load` numa cópia do
[host experimental API 2](experimental-multi-input-host.md). O upstream
oficial exige essa preparação separada. Reconstrução:
`uv run python scripts/build_hfhotspots.py`, Rust 1.98.1 fixado, std somente.
A extensão contém cinco parâmetros, oito valores f64 achatados, uma imagem.
Nenhum recurso externo, fonte ou SDK proprietário foi incorporado.

## Modelo e perdas

O [manual oficial HitFilm 2017](https://s3.amazonaws.com/media.hitfilm.com/reference-manual/hitfilm-pro-2017/HitFilm-Pro-2017-User-Guide.pdf)
descreve preenchimento por Threshold Add Color nas áreas abaixo do limiar,
controle de saturação/brilho nos highlights e suavização prévia da fonte.
O [manual legado público](https://fxhome-old-reference-manuals.s3.amazonaws.com/hitfilm-4-pro/color.htm)
confirma a finalidade de isolar regiões claras. O PDF retornou 403 na abertura
direta; sua seção textual foi acessível no índice de pesquisa público.
Não se atribui acesso ao documento integral nem calibração certificada.

A implementação é separada de S_Hotspots: a cor é preenchimento, enquanto
Sapphire usa ajuste cromático do limiar. Os modelos abaixo pertencem ao Bridge;
sliders de origem permanecem brutos, sem inferir unidades kind 10.

| Controle | Modelo original e limites |
| --- | --- |
| Smooth Source | Box fracionário separável em RGBA premultiplicado, borda clamp; radius=raw×buffer scale, raw 0..8192. |
| Threshold | Gate hard em max(0,R,G,B) straight depois da suavização; abaixo usa fill, igual/acima conserva os highlights; raw 0..64. |
| Threshold Add Color | ARGB255→RGBA; abaixo, alpha=source alpha×fill alpha e RGB=fill RGB×alpha. |
| Saturation | Y=(R+2G+B)/4; Y+(RGB−Y)×raw, raw ±64; aplica só aos highlights. |
| Brightness | Multiplica RGB dos highlights por raw 0..64 e repremultiplica por alpha; conserva source alpha. |

Alpha zero não deixa vazar RGB oculto. Buffer limitado a 2097152 pixels,
lados até 65536, valores finitos e bounds conferidos antes de publicar toda
a saída. Canvas fixo. Kernel/threshold/cor/HDR/gama/alpha/calibração são
aproximações, sempre perdas: PARTIAL e strict sem publicação parcial.

O menu hidden -1985 contém apenas Preset; -0005 também se chama Smooth
Source, mas é kind 1 hidden, distinto do controle visível -0006. Permanecem
avisos de parâmetros sem mapa; não se presume que alterar o hidden é inócuo.
A ausência de um dos cinco controles exigidos ou valores fora dos limites
recusa a criação completa, inclusive quando -0005 está presente.

## Verificação

Seis testes Rust cobrem gate/color/alpha/saturação/brilho, impulso suavizado,
escala e bounds. Sete testes Python verificam transporte, perdas, strict e
recusa sem -0006. Amostras privadas são opt-in e não distribuídas. Nove casos
na Session nativa confirmam full/half, fill com alpha, brilho, suavização,
reabertura e os cinco valores de cada preset real sobre pixels próprios.
Não existe render comparativo Adobe/HitFilm para certificar equivalência.

Workload Full HD uniforme, Smooth Source=12 e preto abaixo do limiar: ~7,6 s
no loader WASM nativo, todos os pixels conferidos analiticamente. Não é
benchmark geral. Corpus automático: 3556 controles/561 chaves, 132 PARTIAL/
12 UNSUPPORTED. Os dez novos controles pertencem a arquivos já parciais.
