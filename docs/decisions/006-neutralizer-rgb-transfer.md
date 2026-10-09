# ADR 006 — Color Neutralizer: controles e limites do perfil RGB

## Evidência

O match name real é `CS Color Neutralizer`, correspondente ao CC Color Neutralizer.
O [manual Cycore FX HD 1.8.9, páginas 12–13](https://cycorefx.com/downloads/cfx_hd_std/CycoreFX%20HD%201.8.9%20Manual.pdf)
descreve três referências tonais, seletores conectados aos sliders RGB, Pinning e
Blend w. Original. Também explica que Black/White Point alteram a definição de
sombras/highlights e que os modos de diagnóstico substituem a imagem final.

Os dois efeitos reais têm seletores kind 5 com pard UI flags 4. O
[SDK PF_ParamDef](https://ae-plugins.docsforadobe.dev/effect-basics/PF_ParamDef/)
define esse bit como PF_PUI_STD_CONTROL_ONLY: controle sem stream próprio de animação.
O manual confirma que os seletores ajustam os sliders, portanto aplicar ambos como
correções independentes duplicaria o ajuste.

py-aep/docs/file_format.md, commit em references.json, documenta o campo display_flags
do float slider kind 10 em pard +0x7E. Bit 0 indica exibição em porcentagem. O parser
agora preserva esse campo; não atribui unidades aos demais sliders por nome ou intervalo.
**Nos nove sliders RGB de cada efeito real esse campo é zero.** Os limites -100..100
não bastam para provar a escala da correção. A leitura das unidades foi conferida antes
de aceitar qualquer derivação. Os seletores/valores RGB originais continuam no diagnóstico.

## Conversão disponível

O mapa transfere Pinning (-0019) e Blend (-0020), com escalas documentadas e limites
nativos 0..100. Ambos exigem View (-0022) estático igual a 1, Black Point (-0023)
estático 0 e White Point (-0024) estático 100. Propriedades ausentes, duplicadas,
animadas ou com avisos de perda impedem a aplicação dessas regras.

Há um perfil **sintético** adicional para os três RGB explicitamente declarados
em porcentagem: kind 10, display_flags exatamente 1, dimensões 1, streams não espaciais
1/7, valores finitos em -100..100, estáticos e sem expressões/perdas. Cada trio precisa
de IDs únicos e de seu seletor UI-only estático comprovado. Combina os valores em
uma Color RGBA do destino: Balance = anchor + RGB/100, alpha 1. As anchors 0/0.5/1
são os defaults Unbalance auditados na biblioteca EffectCraft. Seu renderer calcula
o offset como Balance-Unbalance. Componentes negativos ou acima de 1 são preservados,
não limitados; origens e valores de todos os componentes são retidos.

Somente após derivação válida os sliders e seu seletor ficam administrativos;
perfis sem unidade, incompletos, animados ou contraditórios não produzem cor estática.
Não se dá suporte RGB real aos dois presets examinados: eles não têm a declaração
de unidade exigida. O perfil percentual foi testado com fixture inteiramente sintética.

NEUTRALIZER_ALGORITHM sempre acompanha o efeito. Interpolação tonal, clipping e
pinning do renderer nativo não foram comparados visualmente com Cycore/Adobe.
Strict recusa o resultado parcial. Black/White não default, outros modos View e
animação RGB continuam perdas, mesmo quando o destino aceita as propriedades.

## Validação

Dois componentes reais foram aplicados em uma Session descartável da biblioteca
EffectCraft oficial: **quatro propriedades** verificadas por prop.get, salvas em novo
.ecproj e conferidas após reabertura. Nenhuma chave RGB foi convertida.

Um componente sintético com RGB não neutro, seletores deliberadamente divergentes,
Pinning e Blend teve **cinco propriedades** conferidas e persistidas na engine. Isso
confirma a representação nativa, inclusive cores fora de 0..1; não comprova a imagem Adobe.

Os resultados reais estão em artifacts/neutralizer-native-v0.7/, e os sintéticos em
artifacts/neutralizer-synthetic-native-v0.7/. Valores/arquivos privados não são distribuídos.
O corpus permanece com 75 PARTIAL e 69 UNSUPPORTED: 1370 parâmetros e 17 chaves,
nenhum preset completo. O objetivo de suporte integral continua pendente.
