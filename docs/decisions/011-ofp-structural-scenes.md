# ADR 011 — Leitura estrutural OFP v3, sem renderer

## Evidência e autoria

A pesquisa pública de formato em
[LensFlare.cs, NuajFramework, commit 3ae072166486e5df6a575062bd0da1afeb50a471](https://github.com/Patapom/NuajFramework/blob/3ae072166486e5df6a575062bd0da1afeb50a471/Packages/Cirrus.Utility/Helpers/LensFlare.cs)
foi consultada em 08/10/2026. Não foi identificada licença explícita que autorize
reutilização desse código. O decoder/encoder Python do Bridge é original;
nenhum código, preset ou asset do NuajFramework foi incorporado à distribuição.
Os dados de interoperabilidade foram conferidos independentemente nos 38 blocos
reais autorizados. A referência externa não certifica semântica visual.

O envelope observado começa com OFP e byte de versão 3. Átomos usam tag/tamanho
u16 little-endian. Os marcadores são 3000 (início), 4000 (fim de globais),
1000 (fim de objeto) e 2000 (fim de campo), com payload de um byte zero.
Cada campo contém ID (tag 50/u32), kind (51/u32) e dados (52/32 bytes).
Kinds 0–6 representam float, vetor com flag auxiliar, RGBA8 com flag auxiliar,
inteiro, booleano, enum/rótulo e separador. Objetos têm tipo u32, nome de
64 bytes e flags hidden/solo. Tipos de objeto desconhecidos são preservados.

## Decisão

Separar leitura estrutural de associação e de suporte no destino.
O leitor preserva campos como lista ordenada, inclusive IDs repetidos;
não infere unidades nem interpreta IDs como controles de renderização.
Nomes/rótulos são bytes hexadecimais, não caminhos a abrir. Flags auxiliares
não canônicas e padding dos campos permanecem no raw_hex.

Somente Options kind 11, dimensões 1, stream flags 7, estático, sem chaves ou
avisos adicionais e seguido de exatamente um aRbp pode receber a cena em
metadata.decoded_arbitrary. Essa condição foi comprovada em nove snapshots.
Não há propriedades derivadas nem mapeamento EffectCraft nesta etapa.
Options conserva valor desconhecido e um aviso de perda explícito.

Os 29 blocos restantes têm apenas diagnóstico com offset/hash e cena/erro.
Nove dos 20 contêineres sem associação contêm mais de um payload;
o primeiro não é automaticamente o estado atual. Também não se atribui uma
cena pelo nome do arquivo ou por semelhança dos parâmetros globais.
Esses blocos continuam contabilizados como não convertidos.

O parser verifica limites por bloco (2 MiB/20000 campos/1024 objetos) e seu
prazo cooperativo; campos OFP entram no limite total de parâmetros do arquivo.
A lista de cenas sem associação obedece max_diagnostics;
o total de candidatos fica registrado separadamente. O encoder valida as
contagens e comprimentos antes de decodificar hex/alocar saída, e confere
igualdade de toda a estrutura com a decodificação dos bytes reconstruídos.

## Verificação e pendências

Fixtures sintéticas originais verificam tipos, campos repetidos, bytes auxiliares,
roundtrip, truncamento, tags/tamanhos inválidos, não finitos, prazo e limites,
associação estática, recusa de estado múltiplo e diagnósticos limitados.
O teste real opt-in compara os bytes dos **38 blocos** e as estruturas que
`inspect_file` preserva: **602 objetos/39665 campos**, nove associados e 29 sem
associação. Presets privados/valores/imagens não entram no pacote.

```sh
uv run --extra dev pytest -q tests/unit/test_optical_flares.py
CRAFT_REAL_FIXTURES=1 uv run --extra dev pytest -q \
  tests/integration/test_real_fixtures.py -k ofp
```

O snapshot de 2648 tipos escalares de origem não foi alterado para promover
arbitrários selecionados sem perfil comprovado. Um renderer de objetos,
texturas, composição e transporte de cena ainda precisa ser implementado.
A documentação oficial do fabricante sobre
[objetos e sprites fotográficos](https://video-copilot.gitbook.io/opticalflaresnuke/using-optical-flares-for-nuke/creating-a-lens-flare-from-scratch)
confirma que leitura de controles globais não substitui a cena.
Não houve comparação visual Adobe nem aplicação de Optical Flares na engine.
O objetivo de suportar todos os efeitos permanece ativo.
