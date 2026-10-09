# Glint aproximado

Bridge 0.17 inclui **Bridge Glint (Approximate)**, uma extensão opcional original
para o perfil S_Glint observado no corpus. Transfere 25 controles de brilho,
cores, threshold, tamanho, blur e transparência. Usa um algoritmo próprio de
raios exponenciais em quatro eixos; não há comparação visual com Sapphire/Adobe.

```sh
craft-bridge extensions install glint
```

Carregue o caminho `module` mostrado em **Effect → Load Effect Plug-in…** no
EffectCraft, ou pelo comando oficial `effect.plugins.load`. Reinicie a GUI do
Bridge e reconverta para uma pasta nova. Instalar o mapa não carrega o módulo;
a aplicação verifica o manifesto antes de alterar as propriedades.

Coeficientes numéricos são conservados sem inferir unidades de Size/Blur/Threshold.
O renderer tem sua própria calibração: Size × multiplicador do eixo × multiplicador
RGB × scale define o decaimento; os blurs usam caixas com bordas zero. Cores passam
de ARGB255 para RGBA0..1. Opacity usa o menu comprovado All Opaque/Normal/As Premult,
convertido de 1..3 para 0..2; opções desconhecidas são recusadas.

Limites próprios: Brightness/ganhos/Affect Alpha 0..64, Hue Shift -1..1,
Size/blurs 0..4096, multiplicadores de tamanho 0..8, threshold 0..1000000,
controles de mistura 0..1. O cálculo RGB limita a entrada direta a 0..1000000,
usa somente RGB dos controles de cor e uma rotação HSV própria sem ajuste de gama.
Não há clamp silencioso de controles numéricos fora do perfil na conversão.

Background, Matte from Layer/Path e Mocha permanecem opacos. O renderer usa a
imagem de entrada como base, sem afirmar que a referência original esteja vazia.
Controles de máscara e Expand Borders não são traduzidos. O quadro tem tamanho
fixo; não gera pixels fora dos limites da imagem. Widgets também não são
reproduzidos. Essas dependências e diferenças de algoritmo/alpha/HDR/gama são
perdas explícitas. Todos os resultados ficam **PARTIAL**; strict não publica o
plano. [ADR 019](decisions/019-approximate-glint-renderer.md).

Dois snapshots reais exportam 50 propriedades e 12 chaves Linear, incluindo
uma chave de cor. A Session oficial confirmou controles/chaves após salvar e
reabrir; 15 valores intermediários escalares foram comparados com cálculo
independente. O loader WASM passou em 27 casos sintéticos, dois conjuntos reais
de controles sobre pixels originais de teste e Full HD (~23,2 s nesta máquina).
São verificações do Bridge, sem certificação da aparência original.
[Validação](validation.md).

Com Glow, Shake, biblioteca Flare local, Stretch, Diffusion, Modulation e Glint:
121 PARTIAL/23 UNSUPPORTED, 3179 propriedades/504 chaves, nenhum SUCCESS.
Para remover o mapa, remova explicitamente bridge-glint-1.json da pasta mappings
de CRAFT_BRIDGE_CONFIG (padrão ~/.config/craft-bridge/mappings) e reinicie o Bridge.
Suporte universal e fidelidade visual continuam em andamento.
