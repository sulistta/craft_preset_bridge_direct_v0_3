# ADR 012 — Biblioteca privada de cenas e renderer original aproximado

## Evidência e identidade

A ADR 011 estabelece o envelope OFP v3 e o roundtrip exato de 38 blocos privados.
Nove snapshots têm associação estática comprovada a Options e contêm seis cenas
distintas. Outros 29 blocos permanecem sem associação. parT/tdb4 e menus reais
comprovam os dez controles globais mapeados; não se inferem IDs por nomes.

O renderer em extensions/flare é implementação original MIT, sem dependências
Cargo externas. Não reutiliza código/presets/imagens do NuajFramework ou de plugins
Adobe. A referência Nuaj descrita na ADR 011 não entra em runtime/distribuição.
Os números de campos OFP sustentam a estrutura; as fórmulas descritas abaixo são
calibrações do Bridge, sem certificação da semântica visual do fabricante.

## Transporte e criação

O loader oficial aceita apenas parâmetros tipados limitados, sem payload arbitrário
por frame. Uma biblioteca local associa SHA-256 de cenas ao parâmetro Choice scene.
`CBFLIB01` contém tamanho total, contagem e pares offset/tamanho contíguos, seguidos
dos bytes OFP integrais; máximo 2 MiB/256 cenas. A ordenação é pelo hash, com dedup.
O ID próprio org.craftbridge.flare.lib_* depende do hash da biblioteca. A versão
incorpora hashes do template e biblioteca, e o plano v3 fixa o manifesto.

O build Rust 1.98.1 gera um template sem cenas privadas. O builder Python confere
seu SHA e encontra dois slots com tags/fill únicos dentro de segmentos ativos WASM.
Substitui exclusivamente seus dados de capacidade fixa, sem mudar instruções,
exports, tabelas, offsets ou comprimentos. Slots: 2 MiB de cenas e 16 KiB de
manifesto. Nenhuma expressão extraída é executada; não há imports, acesso a assets,
compilador, registro de mapa ou carregamento de módulo automático.

O mapa usa ofp_scene_lookup somente em Options estático OFP-v3-structural, com
metadados coerentes, bytes reencodados e hash igual ao aRbp original e à biblioteca.
Options é obrigatório na criação. Ausência/duplicata/ambiguidade/cena estrangeira
recusa o componente inteiro e zera suas contagens convertidas. A validação de
planos impede retirar scene para criar com defaults. Controles selecionados não
exigem nem modificam a cena de uma instância existente.

## Calibração aproximada

- Hidden/solo filtram objetos; Texture é omitido, jamais substituído por círculo.
  Brightness é percentual e respeita Ignore Global Brightness. Scale combina
  percentuais externo/global/objeto; raio base é metade da menor dimensão do buffer.
  Stretch/aspect e offsets percentuais definem elipses e posições. Distância usa
  o eixo luz→centro e seu perpendicular. Translation/AutoRotate usam modos do
  perfil implementado; outros valores são recusados.
- Cor global/custom é RGB dos dados, sem interpretar o byte alpha auxiliar como
  premultiplicação. Spectrum usa distribuição própria e Advanced Gradient usa
  Color1, com perda. Tint multiplica luminância própria pela cor externa; Multiply
  multiplica canais. Add limita HDR a 10⁶; Screen limita canais de entrada a 0..1.
- MultiIris distribui réplicas pelo eixo. LensOrbs usa ângulo uniforme e raio
  sqrt(uniforme), com hash u64 próprio do seed f64; não usa PRNG Adobe. Evolution
  fornece fase em graus; animação habilitada adiciona tempo×velocidade própria.
- Kernels originais: glow exp(-r^(2/gamma)), streak exponencial separável,
  iris circular/poligonal com borda suave, famílias de raios por cos elevado a
  24/32, anéis gaussianos, hoop modulado e caustic com raio senoidal. Completion
  limita setores. Gamma mínimo 0,01, espessura mínima 0,005, lados 3..64 e detail
  mínimo 1 são estabilizações próprias. Extensões finitas usam até oito raios;
  controles adicionais não implementados permanecem perdas.
- On Black força alpha 1; Transparent usa cobertura pelo maior canal; Over Input
  soma RGB e compõe alpha. Cor externa alpha multiplica contribuição/cobertura.
  Não se certifica blending/composição equivalente de Optical Flares.

## Limites e validação

O builder recusa objetos/perfis desconhecidos, campos duplicados/tipos inconsistentes,
enums fora do perfil, números além de ±10⁶, mais de 128 réplicas por objeto ou
4096 primitivas. Runtime limita 8.388.608 pixels, tempo ±10⁹ s, scale (0,16],
ABI/alocação e controles pelo manifesto. Erros retornam antes de editar pixels;
o host ainda pode recusar o módulo por limites de memória/fuel. Fuel oficial não
foi aumentado. Não se presume que toda cena permitida pelo limite seja rápida.

Cinco testes Rust verificam famílias, visibilidade/solo, determinismo, cor, modos,
HDR e recusas sem alteração de entrada. Testes Python verificam envelope, integridade
de template/código, associação exata, exigência de scene e strict. Testes reais são
opt-in e não redistribuem fixtures. As seis cenas reais passaram em 65×65 no
loader WASM oficial, com traps expostas em vez de aceitar frame inalterado do wrapper.
Uma cena em 1920×1080 passou em ~83 segundos; desempenho interativo continua limitado.
Reprodução: `python scripts/build_flare.py` usa Cargo.lock/Rust 1.98.1. Um build em
target independente reproduziu exatamente o SHA-256
68a71a00638e525e1b397437b37a6758b20dc914cf0af471ac0147ffb513520b.
`python scripts/validate_flare_renderer.py BIBLIOTECA NOVA_SAIDA --hd` expõe traps
no loader oficial e verifica as cenas mais três modos com alpha externo zero.
Nove componentes criados preservaram 83 controles/50 chaves em projeto reaberto.
A auditoria selecionada verifica controles remanescentes e scene não default,
UID/índice/enabled, alvo inicialmente inativo, curvas e projeto reaberto.
Os 21 grupos selecionados preservaram 136 controles/91 chaves, com 22 lados Bezier
e 75 samples intermediários verificados após reabertura. Um grupo exige grade
mínima de 21 fps, calculada por frações exatas ticks/base; não se arredondam suas
chaves para encaixar em 24/30 fps. A taxa da composição do usuário não é alterada.
Não houve comparação visual Adobe. A meta de suporte a todos os efeitos permanece ativa.
