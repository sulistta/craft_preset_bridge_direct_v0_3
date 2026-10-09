# Dissolve Shake aproximado — 0.27.0

`craft-bridge extensions install dissolveshake` instala o mapa e indica o módulo
WASM. Carregue-o com `effect.plugins.load` no [host experimental revisão 2](experimental-multi-input-host.md).
O EffectCraft oficial/API 1 e o host revisão 1 não aceitam API 3. A preparação
usa uma cópia isolada; não modifica o aplicativo do usuário nem `.research`.

## Evidência e aplicação

Quatro snapshots completos e cinco grupos selecionados FFX locais comprovam
40 controles de processamento, IDs/tipos e ordem dos menus. A documentação
pública [Boris FX DissolveShake](https://borisfx.com/documentation/sapphire/ae/dissolveshake/)
informa a função dos controles. Sliders mantêm os valores brutos; as fórmulas
e calibração do renderer são originais aproximadas. Nenhum código, SDK,
binário, asset ou preset proprietário foi obtido ou redistribuído.

Background `S_DissolveShake-0001` permanece kind 0 opaco. Para criar o efeito,
forneça uma substituição explícita fixada ao SHA-256/índice/ID, usando o
[formato de vínculos de origem](mathops-extension.md). Exemplo de entrada:
`{"preset_index":0,"effect_index":0,"parameter":"S_DissolveShake-0001","layer_ref":"background"}`.
O índice é a posição do efeito no IR; confira-o na inspeção. Null é uma escolha
manual de preto transparente, nunca um None inferido do FFX.

```sh
craft-bridge inspect preset.ffx --json
craft-bridge convert preset.ffx --source-layers vinculos.json --out plano.json
craft-bridge apply plano.json --layer 'Minha camada' --bind-layer 'background=Segunda imagem' --dry-run
craft-bridge apply plano.json --layer 'Minha camada' --bind-layer 'background=Segunda imagem' --yes
```

Criação exige as 41 propriedades íntegras. Grupos selecionados atualizam uma
instância existente, preservando Background, controles e animação não
selecionados. Recursos animados/com expressão, menus desconhecidos e valores
fora dos limites são recusados. A conversão permanece PARTIAL, com todos os
avisos de origem e SOURCE_LAYER_REPLACED; strict não publica um preset parcial.

## Modelo e limites

- Manual usa `raw/100`; Speed concentra o dissolve em torno do meio. Direction
  inverte os pesos. O shake usa envelope `4u(1-u)`, ruído determinístico próprio
  e ondas X/Y/Z/Tilt; seed fracionária conserva seus bits.
- Auto Trans usa primeiro/último frame visível em tempo local da camada real
  do destino, inclusive trim, start, stretch e reprodução reversa. Não
  reconstrói cortes/duração Adobe. Uma camada de um frame escolhe o final.
  Os quatro snapshots reais usam Auto Trans No; Yes foi testado só com dados próprios.
- Geometria usa offset/scale por imagem, amostragem bilinear e No/Tile/Reflect.
  Zoom usa `raw/1000` e Tilt uma calibração própria em graus. Essas convenções
  não declaram unidades ou equivalência do slider Sapphire.
- Motion Blur usa oito transformações das imagens do instante atual, com
  intervalo `raw*passo_local_do_frame`. Não amostra filmagem vizinha ou os
  controles animados nos subtempos. RGB e alpha/cor/HDR têm modelos próprios.
- Até 8.388.608 pixels por imagem e lados até 65.536; amplitudes/frequências
  0..10000, Speed 1..10000, fases ±1 milhão, seed 0..1 bilhão, dissolve/blur
  0..100. Limites são próprios e verificados; o host mantém memória/fuel.

## Verificação

`uv run python scripts/build_dissolveshake.py` usa Rust 1.98.1. Onze testes Rust
cobrem transição, envelope, ruído, ondas, zoom, rotação, RGB, blur não uniforme,
alpha, wraps extremos e recusas. `scripts/validate_dissolveshake_renderer.py`
usa Session real descartável com pixels próprios: dissolve/speed/direction,
null, Auto trim/start/stretch/reverso/frame único, full/half, Linear e projeto
reaberto, atualização selecionada, alteração da imagem auxiliar no mesmo tempo e onda sobre gradiente não uniforme.

O teste real opt-in comprova quatro criações com 160 controles decodificados,
quatro substituições manuais e 13 chaves; cinco grupos selecionados com
48 controles/54 chaves. Isso não certifica o aspecto visual Adobe. O corpus
sem vínculos manuais passa a 129 PARTIAL/15 UNSUPPORTED, 3441 controles/561
chaves, com os 144 hashes e 1341 avisos relevantes preservados. Suporte a
todos os efeitos continua em andamento.
