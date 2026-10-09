# ADR 034 — Signal original aproximado sem ação de botão inferida

Status: aceito opt-in em 0.29.0, 2026-10-09.

Dois snapshots completos ADBE Signal comprovam IDs/tipos/menus e valores
estáticos. O parT contém 34 controles de processamento legíveis e um
Destruction button booleano, além de marcadores administrativos. A descrição
pública Zaebects/aescripts explica a função, sem especificar fórmulas ou
unidades. Kind 10 não permite declarar Phase/Hue como graus.

A decisão é um renderer MIT original com matriz oponente inversível,
portadora/decodificação próprias, filtros limitados, ruído e geometria. API 2
revisão 1 experimental oferece geometria de preview e evita congelar efeitos
temporais com controles estáticos. Uma única entrada, sem recurso manual.
A ação do botão não foi inventada nem seu false interpretado como confirmação
de equivalência. Todos os 34 controles são obrigatórios ao criar o efeito;
grupo selecionado atualiza a instância existente.

Limites, matrizes, relógio de 30 Hz, frequência/fase/ruído/cor/filtros são
escolhas próprias documentadas, com perdas permanentes. Sempre PARTIAL;
strict não publica. Testes próprios e fixtures reais opt-in são separados;
projetos/imagens de teste não certificam fidelidade Adobe/Zaebects. Nenhum
parser ou arquivo privado alterado, expressão executada ou código/SDK/binário/
asset proprietário obtido. [Evidência, uso e limites](../signal-extension.md).
