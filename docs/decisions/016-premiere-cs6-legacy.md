# ADR 016 — Presets Premiere CS6: parâmetros comprovados, perdas explícitas

Data: 08/10/2026. Status: implementado parcialmente na 0.15.0.

## Evidência de origem

Referência pública do autor [PPCS6-Pack-DM-001](https://github.com/DzenetanMassart/PPCS6-Pack-DM-001/tree/498aa583f45af4316eb4ab54403ddb6b30af3601),
commit 498aa583f45af4316eb4ab54403ddb6b30af3601. README e apresentação descrevem
um pack criado no Premiere CS6; não é XML gerado pelo Bridge. O arquivo
PPCS6 Pack DM 001 Presets.prfpset tem SHA-256
f87d7c0f7422d2f876990a772ccd557a680c837c97b5d31619240f9cb3432367,
10 presets e 21 componentes, com 15 match names distintos. Não há licença
de redistribuição declarada: download apenas em artifacts ignorados, nenhum
preset, título, descrição ou fixture original distribuído. Os testes unitários
usam XML original sintético, com valores independentes.

O grafo ObjectID/ObjectRef é aceito pelo parser existente. Sliders inteiros
ParameterControlType=1 usam StartKeyframe decimal, inclusive forma `1.`;
CurrentValue pode ser uma prévia antiga igual a zero. O leitor agora aceita
somente valores finitos integralmente representados para esse controle,
sem arredondar frações, executar expressões ou alterar unidades. Valores
animados são extraídos mas sua interpolação continua desconhecida/recusada.

## Novos mapas FilmCraft

Destino fixado em a4536bcfedf588cbef9ea24df149c70bf99a037d, catálogos e renderers
lidos diretamente em crates/project/src/effect.rs, effect/vfx.rs e
crates/render/src/vfx/blur.rs, distort.rs. Não foram modificados.

| ID real de origem | Destino | Parâmetros traduzidos | Limites/perdas |
|---|---|---|---|
| AE.ADBE Geometry | transform | 1 anchor, 2 position, 11 uniform_scale, 3 scale_height, 4 scale_width, 5 skew, 6 skew_axis, 7 rotation, 8 opacity | Pontos normalizados exigem resolução explícita; 9/10 obturação permanecem perdas. Perfil legado separado de Geometry2, sem inferir IDs extras. |
| AE.ADBE Channel Blur | channel_blur | 1 red, 2 green, 3 blue, 4 alpha, 5 repeat_edge | Sliders destino 0..1000; valores superiores recusados, sem clamp. ID 6 Dimensions não mapeado: fonte prova faixa 0..2 mas não rótulos/ordem do menu; resultado bidimensional default é perda explícita. Calibração Gaussian não certificada. |
| AE.ADBE Mosaic | mosaic | 1 horizontal, 2 vertical | Fonte/destino contam blocos, 1..4000. ID 3 Sharp Colors não traduzido: renderer FilmCraft não consulta sharp, apenas amostra centro de bloco; distribuição média Adobe não preservada. |

Todos os mapas declaram limitations e permanecem PARTIAL mesmo quando só
há controles traduzidos. Nenhum novo controle oculto é marcado administrativo.
strict não publica JSON parcial. Animar parâmetros não transforma curvas
Premiere desconhecidas em Linear. Cores inteiras empacotadas do pack continuam
opacas: não se deduziu sua ordem nem profundidade por nome do efeito.

Twirl não foi acrescentado: a [referência Adobe CS6](https://helpx.adobe.com/pdf/cs6/after_effects_reference.pdf)
define raio relativo ao maior lado, enquanto o renderer FilmCraft usa o menor;
essa diferença exige conversão explícita dependente de resolução e testes,
além da comparação da deformação. Não se usou identidade por semelhança de nome.

## Verificação

13 casos unitários novos verificam constante salva, inteiros válidos/fração/NaN,
limites, coordenadas, controles não traduzidos, perda de render e recusa strict.
Teste real opt-in com hash fixo, CRAFT_CS6_PRESETS; não baixa automaticamente.
O pack gera quatro presets FilmCraft com cinco componentes e 26 parâmetros
estáticos, zero chaves preservadas. O harness foi reforçado para comparar
EffectPreset completo após presets.import, incluindo valores, enabled, curvas,
ordem, resolução e duração, em uma Session própria sem diretório persistente.
Isso prova importação e retenção dos dados exportados, não aplicação ao clip
nem equivalência visual Adobe. Os 144 FFX privados não receberam mapas novos.
