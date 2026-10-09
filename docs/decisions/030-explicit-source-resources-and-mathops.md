# ADR 030 — Substituições explícitas de recurso e MathOps aproximado

Data: 2026-10-09. Estado: implementado opt-in em 0.26.0.

S_MathOps combina imagens, mas Source B/Mask kind 0 não têm decoder FFX
comprovado. Os quatro snapshots têm controles não neutros: A Darks=-0,04 e
Blur Mask=12. Compound Arithmetic Add sozinho não preserva esse comportamento.

Introduzimos um arquivo declarativo de substituições fixado ao SHA-256, preset,
índice na lista de efeitos e ID do parâmetro. Rule Layer exige a operação
explicit_layer_binding, evidência, limitações e recurso obrigatório na criação.
O parser/IR permanecem desconhecidos; nenhum blob é executado ou inferido None.
Omissão não escolhe defaults; animação/expressão não admite substituição estática.
Reportamos perda SOURCE_LAYER_REPLACED mantendo todos os avisos originais.

Um renderer Rust próprio usa a ABI experimental 2/revisão 1 para imagem atual,
Source B e máscara opcional. Preserva 15 coeficientes/menus além de duas entradas
manuais, com limites e convenções originais de cor/alpha/blur/geometria. Todos
os controles são obrigatórios na criação; grupos selecionados preservam outras
propriedades. Instalação do mapa não executa/carrega WASM automaticamente.

Alternativas recusadas: decodificar kind 0 como None, escolher uma camada pelo
nome do efeito, eliminar A Darks, tratar Blur Mask como neutro sem comprovar
máscara ausente ou promover status baseado apenas na aplicação da API.

Verificação: regressões originais de vínculo/mapa/strict, 12 casos Rust e
23 casos engine full/half com pixels próprios/Linear/projeto reaberto. Quatro
FFX locais são teste opt-in. Não houve reutilização proprietária, edição de
presets nem alteração de .research. Sem comparação Adobe; objetivo universal
continua aberto. Veja [uso e limites](../mathops-extension.md).
