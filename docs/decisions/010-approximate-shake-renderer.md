# ADR 010 — Renderer original aproximado para S_Shake

## Evidência

19 snapshots reais autorizados comprovam parT/tdb4 para 43 controles S_Shake.
pdnm comprova Style (Normal/Twitchy/Jumpy), Wrap (No/Tile/Reflect) e Opacity
(All Opaque/Normal/As Premult), com índices de origem 1-based. 13 grupos
selecionados usam os tipos exatos empacotados na ADR 009. IDs/kinds/menus são
metadados de software; valores, nomes de presets e arquivos privados não entram
na distribuição.

A [documentação do fabricante](https://borisfx.com/documentation/sapphire/ae/shake/)
e o [manual AE v10](https://cdn.borisfx.com/borisfx/download_files/Sapphire-Users-Guide-AE.pdf)
foram consultados em 08/10/2026. Descrevem eixos de movimento, ruído repetível,
ondas, estilos e tratamento de canais. Não especificam o kernel, PRNG nem a
normalização dos valores binários desta versão. Nenhum runtime/SDK proprietário
foi executado ou reutilizado. Frequências, fases e unidades espaciais não são
certificadas pela semelhança de rótulos.

## Implementação e limites

src/craft_bridge/extensions/shake/ contém código Rust original MIT, sem dependências
Cargo externas, e manifesto/mapa/WASM API v1. ID org.craftbridge.shake, versão 0.1.0.
O mapa conserva os valores brutos e explicita quatro perdas permanentes. Não usa
IDs nativos ec.* nem se apresenta como Sapphire.

- Ruído escalar em lattice inteiro: hash determinístico u64 com mistura própria,
  valores uniformes em [-1,1), interpolação quintic. Seed conserva bits f64,
  inclusive frações. Normal interpola entre knots; Jumpy usa jumps com drift
  linear e uma chance determinística de retornar ao centro. Twitchy aplica uma
  janela sin² após o intervalo de Stillness em cada período Twitch Frequency.
- Cada eixo soma Rand Amp × noise((t+Phase+AxisPhase)×Frequency×RandFreq) e
  Wave Amp × sin(2π(t+Phase+AxisPhase)×Frequency×WaveFreq), multiplicados por
  Amplitude e pela janela de estilo. Frequency animada não é integrada no tempo.
  Canais usam amplitude/fase próprias e streams independentes de RGB Randomness.
- Transformação inversa centrada em ((width−1)/2,(height−1)/2). X/Y brutos são
  offsets multiplicados por scale. Zoom usa ZDist×exp(-Z/1000), com expoente
  limitado a ±ln(10⁶). Tilt usa graus. Essas calibrações são definidas pelo Bridge,
  sem afirmar unidade/normalização equivalente da origem.
- Bilinear RGBA premultiplicado; bordas pretas, periódicas ou refletidas com pixels
  de borda repetidos. Canais separados usam alpha máximo das três coberturas.
  Normal/As Premult recebem o mesmo buffer premultiplicado da API; All Opaque
  força alpha de entrada 1. HDR finito é preservado até |componente|=10⁶.
- Blur usa oito amostras centradas no tempo do frame, ao longo de Length/30 s,
  transformando o mesmo frame. Não é integração de frames vizinhos, shutter ou FPS
  do host. Máscaras/Mocha/crop/pixel aspect/expansão são perdas. Buffer mantém tamanho.
- Limites: até 8.388.608 pixels, scale (0,16], tempo ±10⁹ s e controles nos intervalos
  originais do manifesto Bridge. Valores inválidos retornam erro antes de editar
  pixels. ABI confere allocation, alinhamento, dimensões e contagem de parâmetros.

## Reprodução e validação

`python scripts/build_shake.py` usa Rust 1.98.1/wasm32-unknown-unknown, release/LTO.
Avisos de std/compiler-builtins acompanham o módulo. Testes Rust e Clippy verificam
movimento, wrap, alpha/HDR, seed fracionário, estilos, canais, blur e limites.
`python scripts/validate_shake_renderer.py NOVA_PASTA --hd` usa o loader WASM oficial,
com erros de render explícitos e timeout padrão 300 s por frame. 17 casos passaram;
Full HD com oito amostras/RGB separado levou ~132 s em CPU neste ambiente.
Não houve comparação visual Adobe.

Na Session oficial fixada em e38a92e792c07f1c57c5dcfcab37d91932b9e2b8,
18 componentes criados preservaram 774 controles/56 chaves; 13 selecionados,
137 controles/173 chaves. Foram salvos/reabertos projetos oficiais. Os selecionados
começaram inativos e preservaram UID, índice, enabled e controles restantes; seus
66 lados Bezier e 126 amostras intermediárias passaram antes/depois de reabertura.
Nos criados, mais 82 lados Bezier e 90 amostras intermediárias foram conferidos após
reabertura (148 lados/216 amostras para Shake ao todo).

Um componente criado, com quatro chaves, foi recusado sem alterar propriedades:
ticks 3000 e 11999 com base 23976 exigem grade mínima 23976 fps para preservação
exata. A API aceita até 1000 fps. A auditoria confirma recusa nativa, não arredonda
tempos nem declara esse componente aplicado. No lote, Shake exporta 954 controles/
233 chaves; com Glow, há 101 PARTIAL/43 UNSUPPORTED, 2672 controles/343 chaves.
Essas contagens de exportação não certificam todos os planos como aplicáveis.

scripts/validate_native_components.py e validate_selected_components.py são usados
somente com Sessions descartáveis do mantenedor. Resultados privados ficam em
artifacts/. A meta de suporte universal permanece em andamento.
