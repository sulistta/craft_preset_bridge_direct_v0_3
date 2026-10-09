# ADR 002 — Cobertura integral e contrato de unidades explícito

O objetivo do projeto passou a ser suporte a todos os efeitos. A implementação continua
incremental, sem tratar mapas parciais ou um catálogo amplo como conclusão desse objetivo.
O inventário inclui todos os 77 IDs do corpus e mantém as lacunas de plugins proprietários,
propriedades selecionadas e engines. Não se substitui renderização por renomear um efeito.

O catálogo EffectCraft era artificialmente restrito a seis efeitos. Agora se extrai ParamSpec
da biblioteca nativa, incluindo IDs, tipos, limites, menus e defaults. O snapshot de 306 efeitos
é versionado e não depende de executar Rust na instalação do produto. Um mapa novo ainda
precisa de identificação da origem e teste de equivalência por propriedade.

Foi corrigido o envio de pontos Geometry2 normalizados para uma API que espera pixels.
Os planos EffectCraft passam à versão 2 e planos v1 são recusados, exigindo reconversão.
Isso evita executar silenciosamente artefatos com o contrato de unidades antigo.
FFX exige tamanho explícito da camada de destino para pontos; o produto não assume dimensões.

Menus não são tratados como índices consecutivos universais: separadores e opções distintas
exigem tabela declarativa enum_map. Cores são reordenadas de ARGB 0–255 para RGBA 0–1.
Bezier 2D por componente continua recusado onde a engine oferece easing espacial único.

Índices com lacunas só são associados após conferir ordem crescente, contagem de snapshots
e namespaces de parâmetros. Caminhos de propriedades selecionadas em presets mistos não
consomem snapshots de efeitos inteiros. Dados sem associação comprovada permanecem perdas.
