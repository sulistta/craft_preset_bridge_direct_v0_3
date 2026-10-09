# ADR 031 — Dissolve Shake e contexto temporal experimental

Status: aceito como aproximação opt-in em 0.27.0, 2026-10-09.

Quatro snapshots e cinco grupos selecionados comprovam IDs e menus de
S_DissolveShake. Background é opaco. Auto Trans depende dos frames efetivos
da camada; a API 2 não transportava esse contexto. A decisão acrescenta
API 3, revisão 2, com assinatura separada e bloco temporal de 32 bytes,
preservando o layout API 2 e API 1. Os limites temporais vêm da engine,
sem FPS ou duração fictícios. Cache de pixels que inclua plugins API 2/3
é desativado porque suas dependências de imagens/tempo não estão no hash.

Renderer Rust MIT original recebe 40 controles brutos e substituição manual
de Background. Envelope, PRNG, geometria, RGB, blur e transparência são
modelos próprios, sempre PARTIAL. Criação exige 41 propriedades; grupos
selecionados preservam o restante; strict não publica. Fonte, evidências,
limites e comandos em [dissolveshake-extension.md](../dissolveshake-extension.md).

Alternativas rejeitadas: presumir None, fabricar limites da camada, executar
expressões, tratar unidade/calibração própria como Adobe, reutilizar cache
sem dependências ou declarar equivalência pelo sucesso da API. Nenhum
parser FFX foi alterado. Testes reais são opt-in sem fixtures redistribuídas.
