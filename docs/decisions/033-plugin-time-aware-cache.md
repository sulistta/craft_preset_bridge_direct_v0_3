# ADR 033 — Tempo de plugins no cache experimental

Status: correção verificada na cópia opt-in, 0.28.0, 2026-10-09.

Uma Session real com Flicker API 1, parâmetros estáticos e onda de frequência
1 devolvia o mesmo vermelho em t=0, 0,25 e 0,5. O kernel original deveria
produzir ganhos 1/1,2/1. O cache legado via somente valores de propriedades,
sem reconhecer plugins que leem o tempo diretamente; o transporte WASM era
válido e o renderer não chegou a ser chamado de novo.

A cópia experimental passa a tratar todo plugin registrado como dependente
de tempo. O hash nativo já inclui tempo local/start/stretch nesses efeitos.
Sem contrato declarativo de dependências, a decisão é conservadora: plugins
estáticos podem custar mais em frames distintos, mas frames iguais continuam
reutilizáveis. APIs 2/3 continuam sem cache de pixels que desconhece imagens
auxiliares/limites temporais. Assinaturas ABI, manifestos e módulos não mudam.

`scripts/validate_legacy_temporal_host.py` verifica 15 amostras originais de
picos/vales, full/half, ordem arbitrária, reabertura e reversão do tempo local.
Os 27 testes do host e a prova de API 2/reabertura/12 módulos legados passaram.
O EffectCraft oficial e `.research` não foram modificados; a correção requer
o host opt-in. Sem render comparativo Adobe ou promessa de suporte universal.
