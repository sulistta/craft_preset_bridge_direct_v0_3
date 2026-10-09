# PROMPT MESTRE — CRAFT PRESET BRIDGE

## 1. Sua missão

Você é um engenheiro de software sênior especializado em engenharia reversa de formatos binários, editores de vídeo, motion graphics, interoperabilidade entre aplicações criativas, Python, Rust e desenvolvimento de aplicativos desktop.

Sua missão é **criar do zero um aplicativo open source chamado Craft Preset Bridge**, capaz de converter presets da Adobe diretamente para os aplicativos open source FilmCraft e EffectCraft, sem exigir qualquer instalação de software Adobe.

**Não quero apenas uma análise, protótipo visual ou planejamento. Quero que você construa o projeto, implemente os componentes funcionais, execute os testes disponíveis, corrija erros e entregue uma aplicação utilizável.**

O repositório será novo. Não há obrigação de aproveitar códigos das versões experimentais anteriores.

O aplicativo deverá ter uma interface gráfica moderna, motor de conversão desacoplado, interface de linha de comando, conversão em lote, relatórios detalhados e arquitetura extensível.

## 2. Objetivo principal

Suportar dois fluxos independentes:

**Fluxo A — Premiere Pro → FilmCraft**

Entrada: `.prfpset`

Saída: arquivo JSON no formato nativo de presets do FilmCraft.

**Fluxo B — After Effects → EffectCraft**

Entrada: `.ffx`

Saída: plano de conversão estruturado que possa ser aplicado ao EffectCraft por meio dos comandos oficiais da aplicação. Quando tecnicamente viável, também oferecer a geração de projeto `.ecproj` usando mecanismos oficiais do EffectCraft.

### Regra absoluta

O programa NÃO poderá depender de:

- Adobe Premiere Pro instalado.
- Adobe After Effects instalado.
- ExtendScript ou scripts JSX executados dentro da Adobe.
- Plugins Adobe proprietários.
- Automação de interfaces dos programas Adobe.
- Serviços externos pagos.
- APIs remotas para interpretar os arquivos.

Toda leitura dos arquivos `.prfpset` e `.ffx` deverá acontecer localmente, por meio de parsers próprios ou bibliotecas open source compatíveis.

Isso não significa prometer suporte universal. Presets desconhecidos devem ser identificados e reportados corretamente.

## 3. Pesquisa obrigatória antes da implementação

Antes de escrever a implementação definitiva, examine cuidadosamente estes projetos e sua documentação atual.

### Aplicativos de destino

**FilmCraft**

https://github.com/storytold/filmcraft

Arquivos relevantes:

- `docs/architecture.md`
- `docs/control-protocol.md`
- `crates/engine/src/presets.rs`
- `crates/project/src/effect.rs`
- Definições de `EffectInstance`, `Param`, `ParamValue`, `Keyframe` e `Mask`.

Investigue o formato de presets, os identificadores reais dos efeitos, a serialização de parâmetros e as APIs de importação.

O FilmCraft documenta atualmente o formato:

`filmcraft.effect-presets`

com versão 1, organizado como um documento JSON contendo a lista de presets.

Existem comandos `presets.import`, `presets.apply` e `presets.list`.

Confirme tudo isso diretamente no código antes de implementar.

**EffectCraft**

https://github.com/storytold/effectcraft

Arquivos relevantes:

- `README.md`
- `docs/architecture.md`
- `docs/control-protocol.md`
- `docs/agents.md`
- Definições do catálogo de efeitos.
- Estrutura de propriedades e keyframes.
- Implementação de `effect.apply`, `prop.set` e comandos de animação.
- Serialização de projetos `.ecproj`.

O EffectCraft possui uma engine independente da interface, sistema de comandos, automação por CLI, MCP e conexão local.

Investigue como adicionar efeitos, definir propriedades estáticas, criar animações, salvar projetos e validar comandos.

Não suponha que o EffectCraft tenha um formato oficial de presets `.ffx` ou de importação de presets externos.

Se não houver, utilize um plano de comandos próprio e documentado, executado pela API oficial.

### Engenharia reversa de `.ffx`

**FFX Compatibility Tool**

https://github.com/marbou92/FFX-Compatibility-Tool

Documentação essencial:

https://github.com/marbou92/FFX-Compatibility-Tool/blob/main/RESEARCH_NOTES.md

Este projeto é uma referência prioritária.

Ele investiga a estrutura RIFX dos presets do After Effects, identifica efeitos, dependências, parâmetros e informações sobre keyframes.

Estude suas implementações e testes, especialmente:

- `RIFX`
- `FaFX`
- `LIST`
- `besc`
- `tdsp`
- `tdmn`
- `tdsn`
- `tdix`
- `sspc`
- `parT`
- `pard`
- `lhd3`
- `ldat`

Não trate essas estruturas como especificação universal: diferencie os campos documentados e testados daqueles que ainda são hipóteses.

A pesquisa identifica uma base temporal de 30.720 ticks por segundo para determinados registros `ldat`. Confirme a unidade em cada estrutura ou versão suportada. Não a aplique indiscriminadamente.

### Projetos `.aep` e parsing binário

**py-aep**

https://github.com/forticheprod/py-aep

**dot-aep**

https://github.com/virtualritz/dot-aep

Estude as implementações RIFX, os modelos de propriedades, os formatos de keyframes e a interpretação de efeitos.

Esses projetos trabalham principalmente com `.aep`, portanto não assuma que interpretam `.ffx` diretamente.

Avalie o que é realmente reutilizável e escolha a melhor implementação para nossa arquitetura.

### Engenharia reversa de `.prfpset`

**Premiere Pro PRFPSET Analysis**

https://github.com/notoow/premiere-pro-prfpset-analysis

Investigue:

- XML dos presets.
- Resolução de referências internas.
- IDs de efeitos Adobe.
- Estrutura de parâmetros.
- Keyframes.
- Máscaras e dados Base64.
- Escalas temporais.

A documentação apresenta a base de 254.016.000.000 ticks por segundo para estruturas analisadas do Premiere.

Confira as representações temporais antes de convertê-las.

### Licenciamento

Verifique as licenças atuais e os requisitos de atribuição de todos os projetos.

Reutilize código somente quando a licença permitir e mantenha os avisos necessários.

Não copie código, assets, presets ou bibliotecas proprietárias da Adobe.

Crie `THIRD_PARTY_NOTICES.md` e registre as fontes utilizadas e suas versões ou commits.

## 4. Arquitetura técnica

Prefira uma implementação principal em **Python 3.11+**, aproveitando a pesquisa e bibliotecas existentes.

Use Rust apenas se oferecer uma vantagem concreta e mensurável, por exemplo para um parser binário altamente exigente ou uma biblioteca já consolidada.

Se Rust for utilizado, crie uma interface Python clara e builds reproduzíveis.

A arquitetura deve ser organizada em módulos independentes:

**Camada 1 — Entrada**

Responsável por identificar arquivos e detectar o formato real a partir do conteúdo, não apenas da extensão.

**Camada 2 — Parsers**

Dois parsers separados:

- `PrfpsetParser`
- `FfxParser`

**Camada 3 — Modelo intermediário**

Uma representação universal e versionada de presets, efeitos, propriedades, keyframes, máscaras e metadados.

**Camada 4 — Compatibility Mapping**

Traduz os identificadores, parâmetros e unidades dos arquivos Adobe para recursos equivalentes do FilmCraft e EffectCraft.

**Camada 5 — Exportadores**

- `FilmCraftExporter`
- `EffectCraftExporter`

**Camada 6 — Integração**

Conexão opcional com os aplicativos de destino por suas APIs oficiais.

**Camada 7 — Aplicação**

- CLI.
- Interface gráfica.
- Conversão em lote.
- Relatórios.
- Configurações.

Nenhum parser deverá depender de PySide, Tkinter ou qualquer módulo visual.

O núcleo de conversão deve funcionar completamente em modo headless.

## 5. Modelo intermediário universal

Projete um modelo independente dos formatos de origem e destino, contendo, no mínimo:

- `Preset`
- `SourceMetadata`
- `Effect`
- `EffectIdentifier`
- `Parameter`
- `ParameterValue`
- `Keyframe`
- `Interpolation`
- `BezierHandles`
- `Mask`
- `ConversionWarning`
- `UnsupportedFeature`
- `ConversionReport`

Cada efeito deverá preservar:

- Nome original.
- Identificador interno original.
- Ordem na pilha.
- Estado habilitado/desabilitado.
- Lista de parâmetros.
- Animações.
- Máscaras quando suportadas.
- Informações relevantes para o diagnóstico.

Cada propriedade deverá conter valor, tipo, unidade, origem e metadados de animação.

Use tipos explícitos para números, booleanos, enums, cores, coordenadas e vetores.

Não transforme valores desconhecidos silenciosamente em zero.

Sempre mantenha os dados originais disponíveis para diagnóstico, respeitando limites de tamanho e segurança.

O modelo deverá ser serializável em JSON e possuir uma versão de schema.

## 6. Parser Premiere `.prfpset`

Crie um parser robusto que interprete diretamente o XML.

Requisitos:

1. Validar o formato antes de processá-lo.
2. Interpretar a hierarquia do XML.
3. Resolver referências internas como `ObjectID` e `ObjectRef`, quando presentes.
4. Identificar corretamente múltiplos efeitos.
5. Preservar a ordem original.
6. Extrair valores constantes.
7. Interpretar keyframes.
8. Converter tempos corretamente.
9. Reconhecer tipos de parâmetros.
10. Identificar dados Base64 e estruturas desconhecidas.
11. Informar parâmetros não suportados.
12. Rejeitar XML malformado de forma controlada.

Priorize mapeamentos comprovados de:

- Motion.
- Opacity.
- Transform.
- Gaussian Blur.
- Directional Blur.
- Sharpen.
- Brightness & Contrast.
- Crop.
- Tint.
- Levels.
- Gamma Correction.
- Transições e outros efeitos conforme houver equivalência verificada.

Não considere efeitos equivalentes apenas porque possuem nomes parecidos.

O sistema deve permitir acrescentar mapeamentos sem alterar o parser.

### FilmCraft Exporter

Gere o formato oficial `filmcraft.effect-presets`, respeitando o schema real.

Preserve:

- Nome do preset.
- Lista de efeitos.
- Parâmetros.
- Keyframes.
- Dimensões de referência.
- Duração de referência.
- Modo de posicionamento dos keyframes.

Investigue e suporte, conforme a implementação oficial:

- Scale.
- AnchorToIn.
- AnchorToOut.

Faça a conversão correta entre valores normalizados e coordenadas em pixels, considerando resolução e regras de cada efeito.

Valide o JSON produzido contra as estruturas do FilmCraft sempre que possível.

Nunca declare um preset "importável" apenas porque o JSON é sintaticamente válido.

## 7. Parser independente de `.ffx`

Este é o módulo mais importante e tecnicamente mais complexo do projeto.

**O parser deve abrir arquivos `.ffx` reais diretamente, sem Adobe After Effects.**

Implemente parsing RIFX correto, incluindo:

- Cabeçalho.
- Big-endian.
- Tamanhos de chunks.
- Alinhamento/padding.
- Chunks aninhados.
- Árvores LIST.
- Identificadores FourCC.
- Referências internas.
- Limites de offsets.
- Proteção contra estruturas malformadas.

Não use busca por strings como substituto para parsing estruturado.

Use inicialmente o FFX Compatibility Tool como referência principal de engenharia reversa.

### Extração de efeitos

Interprete os índices dos efeitos e suas associações aos blocos de parâmetros.

Recupere, quando comprovadamente possível:

- Match name.
- Nome exibido.
- Ordem.
- Grupos de parâmetros.
- Tipos dos parâmetros.
- Valores estáticos.
- Estados de animação.
- Keyframes.
- Metadados de interpolação.

### Keyframes

Implemente a leitura das estruturas `lhd3` e `ldat` conforme a pesquisa verificada.

Considere:

- Quantidade de keyframes.
- Número de dimensões.
- Formato e tamanho do registro.
- Tempo.
- Valor.
- Interpolação.
- Tangentes.
- Influências de entrada e saída.

Preserve separadamente as curvas de componentes multidimensionais.

Converta tempos usando a base apropriada para o arquivo.

Evite erros de interpretação como tratar 30.720 ticks por segundo como 1.024 ticks por segundo.

Se não houver evidência suficiente para decodificar uma estrutura, preserve os bytes relevantes para diagnóstico e marque a propriedade como não suportada.

### Suporte a presets complexos

Considere que `.ffx` pode representar mais do que uma pilha simples de efeitos.

Existem presets de:

- Transformações.
- Texto.
- Animadores de texto.
- Máscaras.
- Shape properties.
- Efeitos.
- Expressões.
- Plugins externos.
- Animações multidimensionais.

Crie uma classificação por recurso.

Implemente primeiro os casos bem documentados e amplie gradualmente.

Não gere conversões falsas para estruturas complexas.

### Segurança

Trate qualquer `.ffx` como entrada não confiável.

Imponha limites configuráveis para:

- Tamanho do arquivo.
- Quantidade de chunks.
- Profundidade máxima.
- Quantidade de efeitos.
- Número de keyframes.
- Tamanho de buffers.
- Tempo de processamento.

Evite leitura fora dos limites, alocações arbitrárias, recursão ilimitada e execução de conteúdo embutido.

O parser não poderá executar expressões extraídas dos arquivos.

## 8. EffectCraft Exporter

O EffectCraft deverá ser tratado como um destino com engine própria, e não como uma implementação binariamente compatível com After Effects.

Estude seu catálogo atual de efeitos.

Crie mapeamentos explícitos usando os identificadores reais da API.

Comece com recursos comprovados como:

- Transform.
- Opacity.
- Gaussian Blur.
- Glow.
- Color Correction.
- Keyframes de propriedades comuns.
- Outros efeitos com parâmetros documentados.

Mapeie cada parâmetro individualmente e estabeleça transformações explícitas de unidade, enum, intervalo e escala.

### Formato de saída

Se o EffectCraft não possuir um formato nativo de presets importável, implemente nosso próprio formato intermediário:

`craftbridge.effectcraft-plan`

Esse plano deverá ser JSON versionado, com comandos, propriedades, keyframes e referências de destino.

Não apresente esse arquivo como um formato oficialmente importável pelo EffectCraft.

### Aplicação direta

Implemente um adaptador para o protocolo oficial do EffectCraft.

A documentação descreve um servidor JSON local, normalmente iniciado por:

`effectcraft --control 9877`

Use descoberta de capacidades e comandos quando possível.

Operações de interesse:

- `effect.apply`
- `prop.set`
- Inserção de keyframes.
- Consulta da árvore de propriedades.
- Consulta dos efeitos disponíveis.
- Salvamento do projeto.

Consulte a documentação e os schemas reais para descobrir os parâmetros corretos.

Não presuma que o caminho `effects/#1` será sempre correto. Utilize a referência retornada pela própria aplicação após criar um efeito.

Permita selecionar a composição e a camada de destino.

Antes de aplicar, apresente uma prévia dos comandos e solicite confirmação.

Suporte um modo de simulação sem alterações.

Se for possível gerar `.ecproj` de maneira segura por meio do EffectCraft CLI e salvar o projeto usando sua engine, implemente essa opção como fluxo adicional.

Não modifique arquivos `.ecproj` diretamente sem validar cuidadosamente o schema.

## 9. Sistema de mapeamentos extensíveis

Separe os mapeamentos da lógica de parsing.

Use arquivos JSON ou YAML validados por schema.

Os mapeamentos deverão definir:

- ID do efeito de origem.
- ID do efeito de destino.
- Parâmetros equivalentes.
- Conversões de valores.
- Valores padrão comprovados.
- Limites e unidades.
- Recursos não suportados.
- Versões de destino compatíveis.

Exemplo conceitual:

Efeito Adobe `ADBE Gaussian Blur` → efeito equivalente do EffectCraft → parâmetros do EffectCraft.

Esse exemplo não autoriza inventar IDs. Consulte os catálogos reais.

Mantenha testes individuais para os mapeamentos implementados.

Adicione uma maneira simples de instalar pacotes comunitários de mapeamento, sem permitir execução arbitrária de código.

## 10. Interface gráfica

Desenvolva uma interface moderna e organizada usando preferencialmente **PySide6**, com suporte a Windows, macOS e Linux.

A interface deve estar em português brasileiro, preparada para internacionalização.

### Tela principal

Apresente dois destinos:

**Premiere → FilmCraft**

**After Effects → EffectCraft**

O usuário poderá:

- Arrastar arquivos para a janela.
- Selecionar um ou vários presets.
- Escolher uma pasta.
- Ver os arquivos identificados.
- Selecionar diretório de saída.
- Iniciar análise.
- Visualizar os efeitos encontrados.
- Conferir compatibilidade.
- Converter.
- Consultar relatórios.
- Aplicar ao aplicativo de destino, quando conectado.

### Análise antes da conversão

Ao selecionar um arquivo, mostre:

- Nome.
- Formato.
- Tamanho.
- Versão detectada, quando verificável.
- Efeitos encontrados.
- Parâmetros extraídos.
- Animações encontradas.
- Recursos compatíveis.
- Recursos não suportados.
- Avisos.

### Status dos efeitos

Utilize classificações claras:

- Compatível.
- Compatível com adaptação.
- Parcialmente compatível.
- Não suportado.
- Não decodificado.

Nunca apresente "100% convertido" quando existirem dados relevantes ignorados.

### Conversão em lote

Permita centenas de arquivos em uma única operação, com:

- Fila.
- Barra de progresso.
- Cancelamento.
- Resultados individuais.
- Exportação de relatório.
- Tratamento isolado de falhas.
- Preservação opcional da estrutura das pastas.

A interface não pode travar durante a análise de arquivos grandes.

### Design

Visual moderno, com:

- Tema escuro e claro.
- Boa hierarquia visual.
- Ícones consistentes.
- Suporte a DPI elevado.
- Layout responsivo dentro da janela.
- Mensagens de erro compreensíveis.
- Área de logs e diagnóstico.

Evite interfaces com dezenas de controles sem função real.

## 11. Interface de linha de comando

Implemente uma CLI própria com comandos equivalentes a:

`craft-bridge inspect arquivo.ffx`

`craft-bridge inspect arquivo.prfpset --json`

`craft-bridge convert preset.prfpset --out preset.json`

`craft-bridge convert preset.ffx --out preset.effectcraft.json`

`craft-bridge batch ./presets --out ./converted`

`craft-bridge doctor`

`craft-bridge mappings list`

`craft-bridge apply plano.effectcraft.json --target effectcraft --layer "#1"`

A sintaxe definitiva pode ser ajustada se houver razões técnicas.

Requisitos:

- Help.
- Mensagens legíveis.
- JSON estruturado.
- Códigos de saída consistentes.
- `--dry-run`.
- `--strict`.
- Logs detalhados opcionais.
- Sem dependência da interface gráfica.

Não aplique modificações em aplicativos externos sem confirmação explícita ou uma opção de CLI inequívoca.

## 12. Relatórios de conversão

Cada arquivo processado deverá gerar resultados rastreáveis.

Crie relatórios JSON e HTML, com possibilidade de CSV para lotes.

Inclua:

- Arquivo original.
- Hash SHA-256.
- Versões dos parsers.
- Versão/commit do catálogo de destino.
- Efeitos encontrados.
- Efeitos convertidos.
- Efeitos ignorados.
- Parâmetros suportados.
- Keyframes preservados.
- Transformações de unidades.
- Avisos.
- Erros.
- Estado final da conversão.

Utilize estados:

`SUCCESS`

`PARTIAL`

`UNSUPPORTED`

`FAILED`

Um parser que encontrou o cabeçalho RIFX, mas não interpretou efeitos, NÃO deve retornar `SUCCESS`.

No modo `--strict`, rejeite qualquer conversão que provoque perda de recursos relevantes.

## 13. Estrutura sugerida do repositório

Organize o projeto aproximadamente assim:

- `src/craft_bridge/core/` — modelos e pipeline.
- `src/craft_bridge/parsers/prfpset/` — parser XML.
- `src/craft_bridge/parsers/ffx/` — parser binário RIFX.
- `src/craft_bridge/mappings/` — mapas e transformações.
- `src/craft_bridge/exporters/filmcraft/` — saída nativa FilmCraft.
- `src/craft_bridge/exporters/effectcraft/` — planos EffectCraft.
- `src/craft_bridge/integrations/` — conexões CLI e protocolos.
- `src/craft_bridge/cli/` — linha de comando.
- `src/craft_bridge/gui/` — interface desktop.
- `tests/unit/`
- `tests/integration/`
- `tests/fixtures/`
- `tests/golden/`
- `docs/`
- `scripts/`
- `.github/workflows/`
- `pyproject.toml`
- `README.md`
- `AGENTS.md`
- `THIRD_PARTY_NOTICES.md`
- `CHANGELOG.md`

A estrutura é uma sugestão, não uma obrigação. Priorize clareza e facilidade de manutenção.

## 14. Estratégia de implementação

Trabalhe em fases, mas não pare após criar a documentação.

### Fase 1 — Pesquisa e fundação

- Examinar os repositórios.
- Registrar versões e commits estudados.
- Verificar licenças.
- Documentar os formatos.
- Criar arquitetura.
- Preparar o ambiente.
- Criar os modelos intermediários.
- Criar testes iniciais.

### Fase 2 — FilmCraft funcional

- Implementar `.prfpset`.
- Resolver efeitos e parâmetros.
- Implementar mapeamentos iniciais.
- Preservar keyframes suportados.
- Gerar presets FilmCraft.
- Criar testes.
- Validar importação quando houver ambiente disponível.

### Fase 3 — FFX funcional

- Implementar RIFX.
- Identificar efeitos e blocos.
- Interpretar parâmetros conhecidos.
- Interpretar keyframes comprovados.
- Utilizar fixtures reais legalmente disponíveis.
- Gerar relatórios precisos.
- Integrar os primeiros efeitos ao EffectCraft.

### Fase 4 — Integração e interface

- Criar CLI completa.
- Criar aplicação gráfica.
- Adicionar conversão em lote.
- Adicionar execução opcional de comandos nos aplicativos.
- Implementar configurações e diagnósticos.

### Fase 5 — Qualidade e distribuição

- Executar testes.
- Corrigir falhas.
- Adicionar lint e type checking.
- Criar CI.
- Configurar empacotamento.
- Documentar uso.
- Criar exemplos.
- Preparar builds para Windows, macOS e Linux.

Implemente em incrementos utilizáveis, evitando uma arquitetura gigantesca sem funcionalidades concluídas.

## 15. Testes obrigatórios

Utilize `pytest` ou alternativa justificada.

Crie testes para:

**PRFPSET**

- XML válido.
- XML inválido.
- Referências internas.
- Efeitos múltiplos.
- Valores estáticos.
- Keyframes.
- Tempo.
- Valores normalizados.
- Efeitos não suportados.

**FFX**

- Cabeçalho RIFX.
- Chunks aninhados.
- Padding.
- Tamanho incorreto.
- Arquivo truncado.
- Estruturas desconhecidas.
- Identificação de efeitos.
- Associação entre índice e parâmetros.
- Keyframes 1D.
- Keyframes multidimensionais.
- Conversão temporal.
- Proteção contra entradas maliciosas.

**Exportadores**

- Schema de saída.
- Identificadores válidos.
- Parâmetros e valores.
- Ordenação de efeitos.
- Preservação de keyframes.
- Relatórios.
- Rejeição de dados incompatíveis.

**Integrações**

- Simulação do protocolo.
- Falhas de conexão.
- Timeouts.
- Erros retornados pela aplicação.
- Aplicação de efeitos.
- Confirmação antes de modificar projetos.

Faça testes com arquivos sintéticos e, separadamente, fixtures reais.

**Nunca apresente testes sintéticos como prova de compatibilidade com presets reais do After Effects.**

Quando não existir uma fixture real para um determinado recurso, registre essa lacuna.

## 16. Padrões de qualidade e segurança

Requisitos obrigatórios:

- Tipagem estática onde apropriado.
- Código modular.
- Sem funções gigantes.
- Sem `except` genérico que esconda erros.
- Sem `eval` ou execução de conteúdo não confiável.
- Sem subprocessos com shell inseguro.
- Sem execução automática de expressões Adobe.
- Sem sobrescrever arquivos de origem.
- Escritas atômicas sempre que necessário.
- Logs de diagnóstico.
- Testes determinísticos.
- Validação de argumentos.
- Documentação de APIs públicas.
- Gerenciamento de dependências reproduzível.

Prefira funcionalidades pequenas que estejam corretas a recursos extensos que apenas aparentem funcionar.

## 17. Documentação

Crie documentação completa em português brasileiro.

Inclua:

- Instalação.
- Execução.
- Interface gráfica.
- Linha de comando.
- Conversão Premiere → FilmCraft.
- Conversão After Effects → EffectCraft.
- Explicação dos formatos.
- Arquitetura.
- Adição de mapeamentos.
- Testes.
- Limitações conhecidas.
- Solução de problemas.
- Licenças.

Crie uma matriz de compatibilidade que diferencie:

- Recursos implementados.
- Recursos testados com fixtures reais.
- Recursos parcialmente implementados.
- Recursos planejados.

Registre decisões importantes de engenharia em `docs/decisions/`.

## 18. Critérios de aceitação

A primeira entrega funcional deverá:

1. Instalar e executar sem software Adobe.
2. Abrir a interface gráfica.
3. Aceitar arquivos `.prfpset` e `.ffx` diretamente.
4. Fazer análise estruturada dos dois formatos.
5. Converter ao menos um conjunto comprovadamente suportado de presets `.prfpset` para o formato nativo FilmCraft.
6. Interpretar corretamente estruturas `.ffx` documentadas e verificadas.
7. Converter propriedades `.ffx` que possuam mapeamento comprovado para um plano executável pelo EffectCraft.
8. Gerar relatórios verdadeiros de compatibilidade.
9. Executar conversões em lote.
10. Rodar os testes automatizados.
11. Fornecer instruções de build.
12. Não depender de Premiere ou After Effects.

Se não houver arquivos `.ffx` reais suficientes para comprovar a conversão ponta a ponta, entregue o parser funcional para os casos sustentados por evidência, os testes estruturais e os relatórios, identificando precisamente o que ainda exige validação.

Não invente resultados para satisfazer artificialmente os critérios.

## 19. Diretrizes para trabalhar de forma autônoma

Você tem autorização para:

- Criar os diretórios e arquivos do projeto.
- Escolher bibliotecas adequadas.
- Instalar dependências no ambiente disponível.
- Consultar documentação pública.
- Executar comandos.
- Criar e executar testes.
- Corrigir erros encontrados.
- Refatorar implementações.
- Criar documentação.
- Preparar scripts de build.

Não modifique repositórios externos.

Não execute comandos destrutivos fora da área do projeto.

Não copie código de terceiros sem verificar licença e atribuição.

Quando houver dúvida sobre um formato, investigue fontes e testes antes de codificar uma suposição.

Se o ambiente não tiver internet ou não permitir clonar os projetos de referência, registre claramente essa limitação e não afirme que examinou código inacessível.

Não interrompa todo o trabalho por um detalhe não essencial: registre a limitação e continue com as partes implementáveis.

## 20. Entrega final esperada

Ao concluir, apresente:

- Resumo do que foi implementado.
- Estrutura do projeto.
- Instruções para executar a GUI.
- Instruções da CLI.
- Exemplos de conversão.
- Testes executados e resultados.
- Tabela de recursos efetivamente suportados.
- Limitações atuais.
- Próximos passos técnicos recomendados.

Informe se houve validação real com FilmCraft e EffectCraft, ou apenas testes com mocks e fixtures.

Não declare funcionalidades prontas quando estiverem incompletas.

**Comece agora.**

Primeiro investigue os repositórios de referência, registre um resumo técnico curto e as decisões arquiteturais. Em seguida, inicialize o projeto e implemente o máximo possível do primeiro incremento funcional, executando testes continuamente.

O objetivo é construir uma ferramenta real, sustentável, extensível e capaz de evoluir até se tornar uma solução confiável de interoperabilidade entre presets Adobe e aplicativos ArtCraft — mantendo a conversão totalmente independente dos softwares Adobe.
