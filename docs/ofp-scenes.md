# Leitura de cenas Optical Flares

Na versão 0.11.1, `inspect` lê a estrutura OFP v3 embutida nos chunks aRbp de
presets FFX. A cena contém campos globais e uma lista ordenada de objetos, com
tipos, nomes em bytes, estados hidden/solo e campos tipados. Os IDs dos campos
continuam IDs de origem: ainda não têm tradução comprovada para um renderer.

```sh
craft-bridge inspect ARQUIVO_LOCAL.ffx --json > inspecao.json
```

Nos snapshots estáticos comprovados, a cena está em
`inspection.presets[].effects[].parameters[].metadata.decoded_arbitrary`,
no parâmetro `VIDEOCOPILOT OpticalFlares-0024` (Options).
O valor dessa propriedade continua desconhecido e a perda
`OFP_RENDER_UNSUPPORTED` permanece no modelo.

Blocos sem associação comprovada estão em
`inspection.diagnostics.unassociated_ofp_scenes`, com resumo de origem/offset,
`associated: false` e a cena ou o erro de leitura.
`unassociated_ofp_count` conta todos os candidatos, mesmo quando o limite de
diagnósticos reduz a lista. Não se escolhe o primeiro bloco como estado atual.
Esses dados não entram no plano EffectCraft como comandos de aplicação.

No corpus autorizado há **38 blocos, 602 objetos e 39665 campos**. Todos os
blocos podem ser reconstruídos byte a byte. **Nove cenas** têm associação
estática comprovada; as outras **29** permanecem sem associação em 20 contêineres.
Há tipos de objetos cuja semântica ainda não foi verificada.

O decoder conserva a ordem, IDs repetidos, todos os 32 bytes de cada campo e os
64 bytes do nome de cada objeto. Flags auxiliares de vetores/cores são bytes
brutos; rótulos de enums permanecem bytes. Não se assume charset, unidade,
significado do objeto ou nome de textura. `render_semantics_verified` é false.
O encoder de manutenção verifica igualdade dos dados reconstruídos e recusa
edições inconsistentes; não é um editor certificado de presets OFP.

Limites por bloco: 2 MiB, 20000 campos e 1024 objetos. A leitura também observa
o prazo e a contagem total de parâmetros do parser (incluindo campos OFP).
Tags/tamanhos/marcadores, versão, flags de
objeto e valores finitos são verificados. Arquivos truncados ou layouts
desconhecidos produzem erro controlado. O parser não abre caminhos de textura,
carrega plugins nem executa conteúdo embutido.

Ainda faltam a associação dos estados múltiplos/selecionados, a semântica dos
controles/objetos e um renderer próprio com transporte de cenas ao destino.
Animação, texturas e comportamento visual precisam de validação específica.
O lote não ganha conversões nesta etapa: **101 PARTIAL/43 UNSUPPORTED** com Glow
e Shake, ou **75/69** com builtin. Nenhum preset completo.

Formato, evidência e testes: [ADR 011](decisions/011-ofp-structural-scenes.md).

## Evolução 0.12

O leitor estrutural permanece independente da conversão. A biblioteca Flare
opcional agora usa somente as nove associações estáticas para gerar um renderer
original aproximado; os 29 blocos sem associação continuam diagnóstico. Os dados
OFP são preservados integralmente, sem garantir equivalência visual. Veja
[uso/perdas](flare-library.md) e [ADR 012](decisions/012-local-flare-library.md).
