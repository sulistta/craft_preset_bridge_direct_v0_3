# Flicker aproximado

Bridge 0.19 inclui **Bridge Flicker (Approximate)**, extensão opcional original
que transfere 14 controles S_Flicker. Modula RGB no tempo com ruído suave
repetível e ondas independentes por canal. Fórmulas, seed/PRNG, frequência/fase
e calibração são próprios; não há equivalência visual comprovada com Sapphire.

```sh
craft-bridge extensions install flicker
```

Carregue o caminho `module` mostrado em **Effect → Load Effect Plug-in…** no
EffectCraft, ou por `effect.plugins.load`. Reinicie a GUI do Bridge e reconverta
para uma pasta nova. Instalar o mapa não carrega o módulo executável. A aplicação
verifica o manifesto da instância antes de alterar propriedades.

Os 14 coeficientes permanecem brutos, incluindo seed fracionário. No renderer,
Rand Freq/Wave Freq multiplicam segundos e phases são ciclos; essa calibração
não atribui unidades certificadas à origem. Brightness e amplitudes modulam
RGB com ganho não negativo, preservando alpha. HDR/valores negativos não são
limitados a SDR. Frequência zero produz ruído constante; amplitude zero com
Brightness=1 é identidade. Frames fora de ordem, negativos ou subframes são
repetíveis. Não há execução de expressões nem conversão gamma automática.

Um snapshot real transfere 14 valores estáticos. Um grupo selecionado transfere
três controles com três chaves isoladas em zero. Esse grupo exige a instância
Bridge Flicker já presente na posição original; a aplicação preserva os demais
controles e enabled. Salvar/reabrir pela engine confirmou as duas situações.
Ondas/color flicker e curvas com múltiplas chaves possuem testes sintéticos,
sem samples intermediários reais nesse corpus. Sempre **PARTIAL**, com perdas
no relatório; strict não publica plano. [ADR 021](decisions/021-approximate-flicker-renderer.md).

Loader oficial WASM passou em 31 casos, incluindo controles reais sobre pixels
próprios e Full HD (~2,2 s nesta máquina). O conjunto selecionado usa defaults
próprios para controles ausentes somente no teste de pixels; não se presume que
a origem usava esses valores. [Validação](validation.md).

Com todas as extensões e biblioteca Flare local: 122 PARTIAL/22 UNSUPPORTED,
3220 propriedades/507 chaves, nenhum SUCCESS. Os dois arquivos já tinham outros
efeitos convertíveis; Flicker aumenta a cobertura interna, sem alterar os estados.
Para remover o mapa, remova explicitamente bridge-flicker-1.json de mappings em
CRAFT_BRIDGE_CONFIG (padrão ~/.config/craft-bridge/mappings) e reinicie o Bridge.
