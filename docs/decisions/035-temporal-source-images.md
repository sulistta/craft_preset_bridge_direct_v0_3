# ADR 035 — imagens da origem em outros instantes

Data: 2026-10-09. Estado: implementado em host experimental isolado.

## Contexto

API 3 fornece limites temporais, mas entrega imagens auxiliares no instante
corrente. Alterar um relógio ou a seed não fornece pixels de frames anteriores.
A função nativa `EffectHost::self_at` já renderiza o prefixo anterior da camada
em outro tempo. A documentação pública do [Geometric Filter](https://aescripts.com/geometric-filter/)
descreve redução de frame rate, mas não certifica fórmula nem unidade de seus
controles binários. Nenhum mapa Satori foi introduzido.

## Decisão

Criar API 4/revisão 3 com pedidos declarativos limitados, descritores originais
e preflight anterior à mutação. Reutilizar o callback upstream; manter APIs
anteriores e fingerprints sem campos opcionais nulos. Proibir expressões,
metadados desconhecidos, consultas sem fonte e publicação de pixels parciais.
Compartilhar orçamento por árvore síncrona, propagando falha de descendentes.
O limite de 64 consultas e profundidade 16 contém crescimento multiplicativo.

## Consequências

A interface permite renderers temporais futuros sem assumir que são equivalentes
a plugins Adobe. Requer cópia experimental e instalação separada. Os mapas,
módulos e contadores atuais não ganham suporte por existir essa interface.
Testes e evidência da Session: [contrato completo](../temporal-input-host.md).
A licença do upstream permanece MIT OR Apache-2.0; alterações e exemplo são
originais MIT. Fontes privadas e `.research` não são modificadas/distribuídas.
