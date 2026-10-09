# ADR 026 — Preservar perdas antes de recusar um mapa

## Problema e evidência

`exporters/common.py:map_effect` anexava `Parameter.warnings` apenas dentro
do loop de parâmetros mapeados. NO_MAPPING, recurso incompatível, EFFECT_DECODE
e ausência de dados obrigatórios retornavam antes desse loop. O modelo
intermediário preservava os avisos, mas o relatório destinado ao usuário omitia
referências, expressões e outros dados não decodificados nesses casos.

O corpus local possui quatro S_MathOps e nove grupos S_DissolveShake sem mapa;
quatro snapshots DissolveShake contêm Background opaco e cinco grupos só
selecionam outras propriedades de instâncias existentes. O código fixado do destino
possui Layer nativo, mas a API WASM v1 não recebe uma segunda imagem. A
[documentação S_MathOps](https://borisfx.com/documentation/sapphire/ae/mathops/)
descreve ajustes próprios de entrada/saída; Compound Arithmetic não expõe esses
mesmos controles. Essa evidência não autoriza uma equivalência automática.

## Decisão

Coletar os avisos dos parâmetros relevantes ao criar EffectResult, antes de
qualquer recusa. Copiar os objetos, preservar código, severidade e caminho
explícito, preencher caminhos vazios com o ID da propriedade e contextualizar
a mensagem com nome/ID. O loop de conversão não os anexa novamente.
Parâmetros administrativos seguem a classificação existente do parser.

Não se alteram parsers, mapas, valores, unidades, defaults ou critérios de
publicação. FFX desconhecido não vira Layer(None). Os relatórios mais completos
não promovem um efeito para compatível nem satisfazem suporte universal.

## Validação

Regressões sintéticas cobrem os retornos antecipados, avisos não duplicados,
objetos independentes, caminho explícito, aviso sem perda, HTML escapado e
publicação apenas dos relatórios em strict. O teste real opt-in confere que
todo aviso relevante de cada efeito sem mapa aparece no relatório, incluindo
as referências de segunda imagem nos quatro MathOps/quatro snapshots DissolveShake.
Os cinco grupos selecionados adicionais não são tratados como snapshots completos. Nenhuma
fixture privada é distribuída.

535 testes gerais, 26 testes reais opt-in e Ruff/Mypy passaram. Auditoria dos
144 arquivos confirma 1341 avisos relevantes de parâmetros preservados e 353
antes omitidos em 65 instâncias sem mapa: 179 UNDECODED_VALUE, 165
COMPLEX_PARAMETER, duas KEYFRAME_LAYOUT, seis EXPRESSION e uma
MESH_RENDER_UNSUPPORTED. Hashes dos originais permanecem iguais ao inventário
inicial; cobertura permanece 124 PARTIAL/20 UNSUPPORTED, 3301 propriedades/507
chaves. Preservar avisos não certifica fidelidade visual nem suporte universal.
