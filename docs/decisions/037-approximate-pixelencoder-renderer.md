# ADR 037 — tiles e glifos originais aproximados

Data: 2026-10-09. Estado: implementado, opt-in, sempre PARTIAL.

Um snapshot local comprova 16 controles Pixel Encoder e duas cores ARGB.
A página pública aescripts descreve dez padrões e controles, mas não fornece
algoritmos/atlas/calibração. Defaults públicos de versões futuras não são
considerados evidência de IDs existentes no arquivo.

Implementar seis famílias matemáticas, dez escolhas de menu, glifos de sete
segmentos próprios e caos determinístico por célula. Conservar todos os
controles brutos e dois menus na ordem real. Usar API 2 para offset/scale;
recusar criação incompleta/fora dos limites, não publicar saída parcial em
strict. Máscaras e expressões não são executadas ou reinterpretadas.

O renderer não depende de SDK, binários ou assets proprietários. Evidência
separa descritores reais, matemática original, Session real e fidelidade
não comprovada. O arquivo já era PARTIAL por outros componentes, então não
há promoção de status: 16 novos controles, 132 PARTIAL/12 UNSUPPORTED.
[Instalação e modelo](../pixelencoder-extension.md).
