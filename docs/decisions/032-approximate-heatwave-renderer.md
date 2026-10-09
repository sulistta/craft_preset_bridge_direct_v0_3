# ADR 032 — Heatwave original aproximado com máscara explícita

Status: aceito opt-in em 0.28.0, 2026-10-09.

Um FFX completo sustenta 24 controles, pontos normalizados, tipos e menus
Universe_Distort_Heatwave. Mask Layer é opaco. A documentação pública Maxon
informa funções, mas a lista de Shape no snapshot inclui None; não se
substitui a ordem comprovada por descrições de outra versão.

A decisão é um renderer MIT original API 2 com ruído, displacement, blur,
máscaras geométricas/de camada e diagnósticos próprios. Todos os controles
e o recurso são obrigatórios na criação, com `--size` para pontos. A
substituição fixada ao hash/índice/ID deve ser explícita inclusive para Shape
None; não se infere None nem se relaxa a proteção de referências opacas.
Grupos selecionados preservam o restante. Source Mode Source é escolha do
manifesto do destino. Reaproveita somente helpers originais de transporte.

A conversão é sempre PARTIAL; strict não publica. Os testes reais permanecem
opt-in, sem fixtures redistribuídas, e os avisos de origem são mantidos. Noise,
calibração, blur, alpha/cor/diagnósticos e canvas não são equivalentes certificados.
Não houve alteração de parser, execução de expressão ou obtenção de material
proprietário. Evidência, limites e comandos em [heatwave-extension.md](../heatwave-extension.md).
