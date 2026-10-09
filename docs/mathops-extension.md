# MathOps aproximado e vínculos de origem — 0.26.0

`craft-bridge extensions install mathops` instala o mapa de 17 propriedades
S_MathOps: 15 controles decodificados e duas substituições manuais de recurso.
Carregue o caminho do módulo indicado com `effect.plugins.load` em uma engine
preparada com o [host experimental revisão 1](experimental-multi-input-host.md).
API 2 é uma extensão opt-in do Bridge; o EffectCraft oficial/API 1 recusa esse
módulo. O Bridge não altera a instalação do aplicativo.

## Escolher as camadas

As referências Source B e Mask from Layer permanecem opacas no FFX. Crie um
JSON específico do arquivo após conferir o SHA-256 e os índices de efeitos
na inspeção. `effect_index` é a posição **zero-based na lista de efeitos do
preset no IR**, não o UID nativo, source_effect_index nem o índice parT.
Cada `layer_ref` é um nome simbólico próprio; null exige uma decisão explícita
de remover essa entrada. Nunca representa um None decodificado do blob.

```json
{
  "format": "craftbridge.source-layer-bindings",
  "version": 1,
  "source_sha256": "SUBSTITUA_PELO_SHA256_DO_FFX",
  "bindings": [
    {"preset_index": 0, "effect_index": 6, "parameter": "S_MathOps-0001", "layer_ref": "second"},
    {"preset_index": 0, "effect_index": 6, "parameter": "S_MathOps-0003", "layer_ref": null}
  ]
}
```

```sh
craft-bridge inspect preset.ffx --json
craft-bridge inspect preset.ffx --source-layers vinculos.json --json
craft-bridge convert preset.ffx --source-layers vinculos.json --out plano.json
craft-bridge apply plano.json --layer 'Minha camada' --bind-layer 'second=Segunda imagem' --dry-run
craft-bridge apply plano.json --layer 'Minha camada' --bind-layer 'second=Segunda imagem' --yes
```

O primeiro vínculo substitui o recurso de origem por uma referência simbólica
no plano. `--bind-layer` resolve essa referência para uma camada real no
projeto, com checagem de UID/contexto do destino. São duas etapas distintas.
Vínculos ausentes, duplicados, de outro hash/preset/efeito ou de propriedades
sem mapa explícito são recusados. Recursos animados ou com expressão não
podem ser substituídos. A criação exige os 17 parâmetros íntegros; um grupo
selecionado pode atualizar somente seus controles em uma instância existente.
Até 64 vínculos por arquivo; JSON limitado a 64 KiB. Batch não aceita esse
argumento: a configuração pertence a um único arquivo.

## Diferenças e limites

As descrições funcionais e menus vêm da [documentação pública Boris FX](https://borisfx.com/documentation/sapphire/ae/mathops/).
Os IDs/tipos brutos vêm de quatro snapshots locais completos, somente lidos,
sem redistribuição. Nenhum código, SDK, binário ou asset proprietário foi usado.

- As 17 operações têm implementação original. Add/Subtract/Multiply/Divide,
  Screen/Average/Min/Max/Difference usam fórmulas elementares; Overlay, Xor,
  Bounce, quantização bitwise e demais convenções são aproximações explícitas.
- Ajuste original: `RGB*(lights-darks)+darks`, seguido por saturação ao redor
  da luma Rec.709. Nos quatro exemplos, A Darks=-0,04 e Blur Mask=12 são
  preservados. Não há calibração Sapphire nem unidade presumida para sliders.
- Geometria: coordenadas locais da imagem principal são convertidas pelo
  offset/scale de cada buffer; amostragem bilinear e exterior transparente.
  Transformações/referências Adobe não são reconstruídas. Resource mode usa
  Source no manifesto como escolha do destino, registrada nas limitações.
- Máscara de camada usa luma/alpha e box fracionário separável com raio
  `raw*scale`. Path/Mocha/tracking/combinação de máscaras não são traduzidos;
  seus bytes e avisos permanecem no relatório. Não se presume máscara vazia.
- Source B explicitamente null usa preto transparente; máscara explicitamente
  null aplica o processamento ao quadro inteiro. São escolhas do renderer.
- Alpha Normal usa cor reta e união dos alphas; All Opaque força alpha=1;
  As Premult opera nos canais premultiplicados. RGB intermediário limitado a
  ±1 milhão; bitwise usa 8 bits e divisores com módulo abaixo de 1e-12 dão zero.
- Até 8.388.608 pixels por imagem, lados até 65.536, três imagens no módulo.
  Lights/saturation 0..64, darks -64..64, blur bruto 0..8192; valor fora dos
  limites é recusado. O host mantém os seus limites de memória/fuel.

A conversão é sempre PARTIAL e strict não publica o plano. As substituições
produzem SOURCE_LAYER_REPLACED sem apagar os avisos de origem. Quatro instâncias
permitem 60 valores decodificados e oito substituições explícitas; não são
68 referências/controles extraídos integralmente do FFX.

## Validação reproduzível

`python scripts/build_mathops.py` usa Rust 1.98.1. Doze testes Rust cobrem
fórmulas, alpha, blur não uniforme, geometria, entradas inválidas e descritores.
`scripts/validate_mathops_renderer.py DIRETORIO_NOVO` inicia apenas seu probe
experimental descartável e verifica 23 casos de pixels próprios, full/half,
animação Linear e salvamento/reabertura. Testes reais ficam opt-in separados.
Não há comparação visual Adobe, benchmark Full HD ou prova de suporte universal.
