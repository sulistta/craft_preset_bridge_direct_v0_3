# ADR 009 — Tipos de origem completos e animação selecionada de Glow

## Evidência e decisão

O coletor anterior filtrava os descriptors pelos mapas instalados. Isso impedia
decodificar streams selecionados de plugins que agora têm uma extensão opcional.
O coletor passa a reunir todos os tipos comprovados em parT/tdb4 reais, sem depender
de Registry. Foram encontrados 2648 IDs, sem conflitos, no corpus privado autorizado.
O snapshot contém somente IDs, kinds, dimensões e indicação de evidência.

Propriedades derivadas pelo Bridge não comprovam um descriptor da origem. Oito IDs
derivados de Levels anteriormente presentes foram removidos. Conflitos de tipo ou
dimensão excluem o ID; shapes não auditados também ficam fora. Os grupos selecionados
continuam exigindo caminhos e índices exatos, associação por posição, tipo conhecido
e um mapa separado. Conhecer tipos de Sapphire/Optical Flares não fornece renderers.

## Aplicação nativa

18 grupos selecionados PEDG converteram 49 controles e 93 keyframes para a extensão
aproximada da ADR 008. Foram preparados efeitos no índice original (1 a 4, zero-based)
em composições descartáveis, com controles não selecionados e enabled preservados.
O preflight continua recusando uma instância ausente, outro efeito naquele índice,
animação/expressão existente no controle de destino e tempos deslocados pelo snapping.
47.952 fps preservou os tempos dessas fixtures sem normalizá-los para a grade NTSC.
O adaptador não muda a taxa de frames do projeto do usuário.

Foi identificado no código oficial fixado do EffectCraft que keys.select e
keys.interpolation consultam active_comp, ignorando um campo comp. Em
crates/engine/src/commands/prop.rs e anim.rs isso afeta a seleção/edição das chaves.
comp.open em commands/comp.rs usa Session.open_comp. Após validar todos os requisitos,
o adaptador abre o destino quando necessário e confirma o ID ativo antes de modificar
efeitos/propriedades. Ausência do comando ou falha de ativação interrompe a aplicação.
CLI/GUI informam a mudança de composição; dry-run expõe context_commands condicionais.
O plano canônico continua v3. Não há transação/rollback da aplicação inteira.

## Verificação e limites

Na Session oficial compilada (commit e38a92e792c07f1c57c5dcfcab37d91932b9e2b8),
todos os 18 destinos começaram inativos, com outra composição aberta. Foram conferidos
49 controles, 93 chaves, 31 lados Bezier persistidos e 150 amostras intermediárias
contra uma inversão cúbica independente. As amostras e curvas passaram por salvamento
e reabertura; a composição de distração não foi alterada. Contagem de efeitos, UIDs,
enabled e controles não selecionados foram preservados.

scripts/validate_selected_components.py reproduz essa auditoria somente num servidor
descartável controlado pelo mantenedor. Resultados privados permanecem em artifacts/.
Os testes públicos cobrem extração independente dos mapas, exclusão de IDs derivados,
conflitos e shapes, vínculo selecionado e ativação/recusa de contexto via protocolo.
Fixtures reais são opt-in e não são distribuídas.

Com a extensão instalada, o lote de 144 arquivos passa a 92 PARTIAL/52 UNSUPPORTED,
1718 controles/110 chaves; builtin permanece 75/69 e 1370/17. O renderer WASM da
0.9 não mudou. Nenhuma comparação visual Adobe foi realizada: a aproximação, os
recursos ausentes e os caminhos complexos continuam perdas. Todos os efeitos ainda
não são suportados.
