# ADR 029 — Planos Layer para o host experimental API 2

Data: 09/10/2026. Estado: implementado em 0.25.0, contrato de host opt-in.

A infraestrutura ADR 028 recebia recursos, mas o Bridge recusava manifestos
API 2 e vínculos Layer de plugins. A integração agora aceita API 2 somente
com `bridge_host_revision:1`, plano v4 e fingerprint do manifesto instalado.
Preserva o default null de Layer ao serializar/instalar; exige todos os Layer
explícitos na criação. Não converte FFX desconhecido nem acrescenta Rule Layer.

Antes de criar um efeito, o preflight verifica APIs disponíveis, revisão 1,
quatro entradas, WASM habilitado, API individual 2 do plugin, versão, parâmetros
e defaults presentes. Os campos de capacidade não aceitam bool/float como
inteiro. Depois aplica o resolvedor de camadas existente, confere composição,
proíbe self, transporta UID inteiro exato e consulta o tipo/valor da propriedade.
Animação de recursos permanece recusada; animação escalar mantém o caminho
nativo. Planos v4 podem combinar plugins API 1 e API 2.

O fingerprint API 1 foi conferido contra o wheel headless 0.24.0. Testes de
TCP recusam metadados/capacidades ausentes ou divergentes antes de mutação e
não aceitam UID vizinho acima de 2^63. O teste nativo aplica mistura original
estática e animada em 32 bpc: endpoints/meio em full/half, save/reopen e unbind
de instância existente preservando as chaves não selecionadas.

Isto não implementa S_DissolveShake ou S_MathOps nem certifica renderers Adobe.
Referências de origem continuam opacas e o corpus não muda de status.
[Contrato e reprodução](../experimental-multi-input-host.md).
