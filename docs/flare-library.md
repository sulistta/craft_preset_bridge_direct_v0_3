# Biblioteca local de flares aproximados

Bridge 0.12 gera **Bridge Flare Library (Approximate)** a partir de cenas OFP v3
estáticas associadas com segurança a Options. O renderer Rust/WASM é original,
sem runtime Adobe, assets externos ou compilador necessário ao usuário.
Os dados da cena são preservados por hash; a aparência é uma aproximação.

## Uso

```sh
craft-bridge extensions build-flare ./presets --out ./minha-biblioteca
craft-bridge mappings install ./minha-biblioteca/mapping.json
```

Carregue `bridge_flare_library.wasm` dessa pasta em **Effect → Load Effect Plug-in…**
no EffectCraft, ou por `effect.plugins.load` com seu caminho absoluto. Instalar o
mapa não carrega o módulo nem altera projetos. Reinicie a GUI do Bridge e faça
nova análise/conversão. Informe a resolução para os pontos:

```sh
craft-bridge batch ./presets --out ./convertidos --size 1920x1080 --preserve-folders
```

O builder exige uma pasta de saída nova. Gere uma única biblioteca com o conjunto
de presets desejado; cenas iguais são deduplicadas e seus índices seguem o hash
ordenado. `library.json` registra hashes do módulo, biblioteca e manifesto.
O manifesto incorpora a identidade do renderer e dos dados. O preflight verifica
esse contrato; o fingerprint do manifesto não atesta os bytes do módulo carregado.

A biblioteca gerada contém dados privados derivados dos seus presets. Mantenha-a
local junto dos planos que dependem dela; o aplicativo distribuído contém somente
o template original, sem cenas do usuário. Uma atualização do renderer exige
gerar e instalar a biblioteca correspondente e reconverter os planos. Mapas de
bibliotecas diferentes para a mesma origem conflitam; use configurações separadas
com `CRAFT_BRIDGE_CONFIG` ou remova explicitamente o mapa anterior antes de trocar.

## Controles e limites

Options escolhe a cena por SHA-256 exato. Position/Center usam `--size` para
converter coordenadas normalizadas em pixels. Brightness/Scale, Rotation, Color,
Tint/Multiply, Evolution e Render Mode têm mapa. Esses dez controles não cobrem
todos os recursos do plugin de origem. Os kernels e sua calibração são próprios.

Os tipos de objeto 1, 2, 4, 5, 6, 7, 8, 9, 11, 12, 14 e 15 têm famílias procedurais.
Objetos configurados como Texture são omitidos, com perda permanente no relatório.
Não são carregadas imagens/sprites. Gradientes avançados, triggers, matte box,
aberração/correção, diversos controles de forma, 3D, máscaras, tracking, camadas,
flicker, motion blur e sampling continuam perdas. Evolution não reproduz o
gerador aleatório/animador original.

Se Options estiver ausente, ambíguo, alterado ou fora da biblioteca, o Bridge
recusa criar o componente inteiro. Ele não usa Scene 0 como substituto. Os 29
blocos OFP sem associação no corpus permanecem diagnóstico. Presets de controles
selecionados atualizam um efeito existente no índice original: preservam a cena,
enabled e controles não selecionados. O efeito deve pertencer à mesma biblioteca.

Todos os resultados são **PARTIAL**; strict produz relatórios sem publicar preset.
Keyframes precisam caber na grade da composição de destino. Full HD levou cerca
de 83 segundos por frame na cena testada neste ambiente CPU/WASM; esta extensão
ainda tem desempenho limitado para uso interativo. Não houve comparação Adobe.

## Evidência

No corpus privado de 144 FFX: nove snapshots completos contêm seis cenas distintas,
e 21 grupos selecionados têm controles mapeados. A exportação Flare preserva 219
propriedades/141 chaves. Com Glow, Shake e a biblioteca local, o lote produz
111 PARTIAL/33 UNSUPPORTED, 2891 propriedades/484 chaves, nenhum SUCCESS.
As cenas reais passaram no loader/render oficial; aplicação e projeto reaberto
são verificados separadamente: 30 componentes/219 propriedades/141 chaves, incluindo
preservação de Scene existente, 22 lados Bezier e 75 valores entre chaves.
[Decisão e fórmulas](decisions/012-local-flare-library.md).
