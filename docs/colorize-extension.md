# Colorize opcional — 0.24.0

A extensão original aproxima BCC3Colorize com um gradiente de até seis cores.
Preserva 23 controles: Input, Color Space, seis cores, quatro Color On,
Black/White Point, Squeeze, Loop Mode/Count, Gradient Offset, Color Ease,
Hue, Saturation, Lightness e Mix with Original.

```sh
craft-bridge extensions install colorize
craft-bridge extensions list
```

A instalação registra o mapa declarativo. Carregue o `module` listado no
EffectCraft por `effect.plugins.load` ou **Effect → Load Effect Plug-in…**.
Reinicie a GUI do Bridge e reconverta para uma pasta nova. O plano verifica
manifesto/fingerprint antes de aplicar.

Quatro instâncias reais transferiram 92 valores estáticos, conferidos na
Session oficial após salvar/reabrir. Os perfis observados usam Luma/RGB,
loop desligado e dois controles de cores intermediárias ativos. Outros
menus, looping e animação possuem testes sintéticos. Não há comparação
visual com BCC/Adobe nem certificação de equivalência.

O gradiente redistribui igualmente as cores habilitadas entre os endpoints.
RGB interpola componentes diretamente; HSL/HSV usam o arco curto do hue,
emprestando o hue da cor cromática quando a outra é cinza. Ajustes HSL,
Squeeze/Ease, luma Rec.709 e calibração dos sliders são fórmulas próprias.
Os valores brutos e os avisos de origem permanecem no relatório.

Input PixelChooser é recusado. Máscaras, Mocha, tracking, camadas/path,
Compare e os controles de preset/preview não são transferidos. Referências
opacas não são consideradas vazias. Todos os resultados são PARTIAL;
`--strict` publica apenas relatórios. Na criação, os 23 controles são
obrigatórios: faltar ou recusar um deles impede criar o efeito com defaults.

A entrada é premultiplicada. Alpha das cores é limitado a cobertura 0..1
no renderer e multiplicado pelo alpha da fonte; Mix combina os resultados
premultiplicados. Mix=100 conserva a entrada exata, inclusive RGB invisível;
outros valores limpam RGB em alpha zero. RGB negativo/HDR é preservado no
componente original da mistura e na interpolação RGB; HSL/HSV usam cores
normalizadas. Essas escolhas de cor/alpha são perdas declaradas.

Limites próprios: até 8388608 pixels, lados até 65536, entrada RGB ±1000000,
alpha 0..1 e parâmetros finitos nos domínios do manifesto. Cores possuem
componentes finitos ±1000000; tempo finito |t|≤10⁹ e scale 1/65536..16.
Chamadas fora desse domínio retornam erro antes de alterar pixels. Black e
White coincidentes produzem uma transição dura; invertidos invertem o
mapeamento. Essas são convenções próprias, sem regra BCC inferida.

60 casos no loader WASM oficial verificam pixels originais contra referência
independente com colorsys, incluindo quatro conjuntos reais de controles.
Full HD não uniforme levou ~5,6 s; UHD ~22,2 s na validação CPU local. Ainda
não é um renderer de preview em tempo real. [Decisão e IDs](decisions/027-approximate-colorize-renderer.md).
