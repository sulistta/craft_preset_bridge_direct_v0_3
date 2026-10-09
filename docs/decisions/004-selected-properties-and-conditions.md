# ADR 004 — Propriedades selecionadas e condições de aplicação

FFX sem sspc pode conter uma sequência de caminhos tdsp e blocos tdbs correspondentes
por posição, sem parT. Essa estrutura está documentada no PresetInspector de
FFX Compatibility Tool e aparece em cinco arquivos do corpus privado. Um bloco tdbs
não revela sozinho se o número armazenado representa float, checkbox, enum ou cor.

O Bridge inclui um catálogo de 150 IDs/tipos de origem extraídos de parT/tdb4 reais,
com comparação entre instâncias e exclusão de conflitos. O catálogo não contém nomes
de arquivos, valores de presets nem blobs. Pode ser regenerado com make_ffx_profiles.py
sobre o corpus local; o produto lê o snapshot empacotado, sem consultar a pasta privada.
Não se infere tipo pela quantidade de dimensões nem pelo tipo do efeito de destino.

Somente caminhos exatos Effect Parade/efeito/parâmetro, com índices válidos, contagem
correta de blocos e tipo comprovado são promovidos a effect-properties. Propriedades
do mesmo match name e índice de instância são agrupadas. Instâncias distintas ficam
separadas. Formatos mistos e grupos complexos ainda não promovidos permanecem perdas.

O plano aplica esses ajustes a um efeito existente: application=existing e
source_effect_index preservam o índice zero-based da origem. O adaptador confere ID,
índice e UID na layer.tree antes de qualquer mutação; não cria efeitos para preencher
lacunas. Também confere todas as propriedades e recusa substituição de animações ou
expressões existentes, cuja mesclagem ainda não está validada. A aplicação mantém os
parâmetros não selecionados e o estado enabled. bridge.bindExistingEffect é uma
operação interna de vínculo da prévia, nunca um comando enviado à engine.

Lumetri possui controles nativos, mas a engine não expõe os switches de ativação dos
grupos Adobe. Regras declarativas requires exigem um único controle estático, sem perdas,
com valor e tipo exatos. Basic Correction, Creative e Vignette são convertidos apenas
quando seus respectivos switches são True. O Creative nativo escala mais controles
com Intensity; esse grupo exige Intensity=100 para evitar alterar a intensidade dos
outros ajustes. Look e Input LUT só traduzem None; presets de LUT, curvas, wheels e
dados HSL não são adivinhados a partir dos índices. As perdas continuam explícitas.

Keyframes Bool/Choice são tipados e aceitos em Hold. Uma chave isolada Linear tem valor
constante e é normalizada para Hold com transformação registrada; várias chaves Linear
ou Bezier continuam recusadas. Color single-ease de 152 bytes é aceito apenas com
Linear/Hold e tangentes nulas; Bezier de uma dimensão de easing não é tratado como
quatro derivadas independentes. ARGB é reordenado/dividido em valores e chaves.

A engine normaliza taxas próximas a padrões NTSC: 23.976 vira 24000/1001. A tolerância
anterior em frações de frame admitia uma pequena diferença de tempo que só aparecia
no post-check. O preflight agora calcula o tempo após snap e compara em segundos com
tolerância de 1 ns (relativa 1e-12), consistente com o Tick nativo. Não altera o FPS da
composição do usuário. Na validação isolada, 47.952 fps preservou exatamente os tempos
23976/1000 de dois componentes, sem arredondá-los à grade NTSC.
