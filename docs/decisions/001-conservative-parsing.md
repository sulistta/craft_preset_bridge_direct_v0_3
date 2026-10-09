# ADR 001 — Parse local e exportação conservadora

Escolha: Python, sem Rust no runtime. O volume local (144 arquivos, 27 MB incluindo
outros assets) não justifica extensão nativa. A leitura estruturada e limitada é suficiente.
Não se usa py-aep diretamente como parser FFX: seu escopo é AEP e há divergências
nas estruturas publicadas. Reaproveitam-se evidências, preservando avisos e versões.
Efeitos e parâmetros sem mapa explícito são perdas, nunca defaults inventados.
O plano EffectCraft restringe comandos e dados para não se tornar executor arbitrário.
Projetos ecproj só são salvos pela engine conectada; não há escrita direta desse formato.
