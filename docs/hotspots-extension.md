# Hotspots original aproximado — 0.33.0

A extensão `hotspots` converte nove controles de S_Hotspots e uma substituição
explícita de máscara. O perfil real contém Layer/Path/Mocha opacos: não se
presume None ou um projeto Mocha vazio. A criação exige nove controles e
um vínculo fixado ao SHA-256, índice do efeito no IR e ID S_Hotspots-0001.
Sempre PARTIAL, inclusive após escolher a máscara; strict não publica parcial.

```sh
craft-bridge extensions install hotspots
craft-bridge inspect preset.ffx --json
craft-bridge convert preset.ffx --source-layers vinculos.json --out plano.json
craft-bridge apply plano.json --layer 'Minha camada' --bind-layer 'mask=Minha máscara' --dry-run
craft-bridge apply plano.json --layer 'Minha camada' --bind-layer 'mask=Minha máscara' --yes
```

O JSON de vínculos segue [o contrato de origem](mathops-extension.md). Use o
hash e `effect_index` observados; exemplo deliberadamente incompleto:

```json
{
  "format": "craftbridge.source-layer-bindings",
  "version": 1,
  "source_sha256": "SUBSTITUA_PELO_SHA256_REAL",
  "bindings": [
    {"preset_index": 0, "effect_index": 0, "parameter": "S_Hotspots-0001", "layer_ref": "mask"}
  ]
}
```

`effect_index` é zero-based na lista de efeitos do preset no IR, não UID
nativo ou índice parT. Para remover a entrada, use `layer_ref: null` como
uma escolha explícita e omita --bind-layer. Isso é substituição manual, não
None decodificado. Referência animada, com expressão, de outro hash/efeito,
ou ausente é recusada. Batch não aceita uma escolha vinculada a outro arquivo.

Carregue `bridge_hotspots.wasm` com `effect.plugins.load` numa cópia isolada
do [host experimental API 2](experimental-multi-input-host.md). O EffectCraft
oficial não recebe suporte automaticamente. Reconstrua com `uv run python
scripts/build_hotspots.py`, Rust fixado 1.98.1, sem bibliotecas Rust externas.

## Evidência e perdas

Um parT/tdb4 comprova cinco sliders kind 2 sem unidade, uma cor ARGB255,
dois menus, um Bool e Mask from Layer opaco. Opacity usa All Opaque/Normal/
As Premult; Mask Use usa Luma/Alpha. Blur Mask=12 é preservado bruto.
A [documentação pública Boris FX](https://borisfx.com/documentation/sapphire/ae/hotspots/)
descreve extração de regiões claras e máscara entre resultado/origem, mas
não certifica o kernel ou a calibração. Defaults públicos não provam ausência
de recurso no FFX. Mocha/Path/Combine Masks/tracking e fidelidade continuam
perdas no relatório. Nenhum SDK, código, binário ou asset proprietário obtido.

## Modelo original

Todas as fórmulas/unidades a seguir pertencem ao renderer Bridge, não são
unidades inferidas dos sliders de origem.

| Controle | Modelo original |
| --- | --- |
| Blur Input / Mask | Box fracionário separável, radius=raw×escala de cada buffer, borda clamp; faixa bruta 0..8192. |
| Threshold | Pico M=max(0,R,G,B). Peso RGB=max(0,1−(threshold+bias)/M), ou zero se M=0; threshold 0..64. |
| Threshold Add Color | bias=Σmax(0,canal)/M×addColor[channel]. Alpha da cor é transportado, mas o threshold usa RGB; canais addColor 0..1. |
| Saturation / Brightness | Y=(R+2G+B)/4 depois da extração; (Y+(RGB−Y)×saturation)×brightness. Saturação ±64, brilho 0..64. |
| Opacity | All Opaque usa alpha 1; Normal divide RGB por alpha positivo antes da extração e repremultiplica; As Premult processa RGB diretamente e conserva alpha. |
| Mask Use / Invert | Bilinear em coordenadas locais via offset/scale; luma própria ou alpha, clamp 0..1, inversão opcional. Exterior transparente. Sem máscara, blur/invert não alteram resultado. |
| Mistura | Máscara interpola pixel original com o resultado, inclusive alpha. Não reproduz path/Mocha nem sua combinação. |

Canvas fixo; até 2097152 pixels/imagem. Validar pixels e saída completa antes
de publicar. Espaço de cor, HDR/gama/alpha, blur e equivalência Sapphire não
certificados. A geometria da máscara substituta vem do destino; referência
e transformação da camada Adobe não são reconstruídas.

## Validação

Sete testes Rust e Clippy all-targets passaram; oito testes Python cobrem
mapa, limites, recusa de máscara implícita e strict. Onze casos na Session
real confirmam máscaras branca/preta/cinza/alpha/invertida full/half, três
modos de opacity, reabertura e nove valores reais mais substituição null
persistidos/reabertos em pixels próprios. Não há comparação visual Adobe.
Um workload Full HD uniforme com Blur Input=12 e sem máscara passou no
loader WASM nativo em ~8,9 s, com todos os pixels analíticos conferidos;
não é benchmark geral. Exemplo `hotspots_hd` permite reproduzir.

Sem vínculos manuais, o corpus automático permanece 132 PARTIAL/12 UNSUPPORTED,
3546 controles/561 chaves. Hashes e 1341 avisos relevantes preservados.
O objetivo universal continua pendente. [ADR 038](decisions/038-approximate-hotspots-renderer.md).
