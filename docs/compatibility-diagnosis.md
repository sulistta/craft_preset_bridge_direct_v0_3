# Por que os presets ainda ficam parciais

A tradução de um parâmetro não comprova a reprodução do preset inteiro.
Um único efeito sem mapa, recurso externo ausente, expressão ou curva não
suportada pode impedir a conversão completa. Renderers originais aproximados
também registram perda de fidelidade, mesmo quando todos os controles são
transportados. O modo strict recusa a publicação de saídas parciais.

A auditoria local do corpus de 144 FFX, usando os mapas da versão 0.35.0,
as 21 extensões empacotadas, o perfil local de cenas de flare e resolução
explícita 1920×1080, confirmou:

| Observação | Resultado |
| --- | ---: |
| Status PARTIAL / UNSUPPORTED | 132 / 12 |
| Identificadores de efeito encontrados | 77 |
| Identificadores sem mapa / instâncias desses efeitos | 27 / 72 |
| Arquivos com pelo menos um efeito sem mapa | 49 |
| Arquivos com parâmetro de origem desconhecido, excluindo administrativos | 107 |
| Arquivos com aviso de perda na conversão de efeitos | 144 |
| Parâmetros convertidos / chaves preservadas | 3571 / 561 |

As observações se sobrepõem. Somar 49 e 107 não dá uma quantidade de arquivos
incompatíveis. Valores desconhecidos podem ser controles inativos ou conter
dados de um recurso ainda não decodificado; o contador não certifica sua
relevância visual. Ter mapa também não garante a criação do efeito nem a
conversão de todos os seus parâmetros.

Uma segunda execução com **apenas os mapas nativos**, sem extensões nem perfil
de flare, produziu 75 PARTIAL/69 UNSUPPORTED e 1370 parâmetros convertidos.
Nesse cenário, 49 identificadores não têm mapa, afetando 139 arquivos.
Portanto, a configuração de mapas explica parte importante da diferença de
cobertura. A primeira medição inclui extensões opcionais; ela não descreve
uma instalação que ainda não tenha esses mapas e os módulos correspondentes
disponíveis no destino. A auditoria não instala nada automaticamente.

`craft-bridge extensions list` mostra os mapas e módulos empacotados.
`craft-bridge extensions install NOME` instala o mapa escolhido no Bridge;
o carregamento do módulo no EffectCraft segue a documentação daquela extensão.
Efeitos que exigem APIs experimentais continuam dependendo do
[host preparado](experimental-multi-input-host.md). Instalar o mapa por si só
não comprova que o renderer esteja carregado no destino.

Entre os efeitos sem mapa, `MB LookSuite3` aparece em 21 arquivos/28 instâncias;
`FC NITRATE`, em sete; `GG AEPixelSorter2` e
`Magic_Bullet_Suite_Magic_Bullet`, em quatro arquivos cada. São identificadores
extraídos, sem reprodução de presets ou de seus valores privados.

## Reproduzir o diagnóstico

```sh
uv run python scripts/audit_compatibility.py /caminho/Presets \
  /caminho/fora-dos-presets/diagnostico.json --bundled --size 1920 1080
```

O comando inclui os mapas nativos e, com `--bundled`, os mapas das extensões
originais. `--map /caminho/mapa.json` pode ser repetido para perfis locais
adicionais. A configuração altera o resultado: o perfil local de flare usado
na medição acima não é distribuído. Mapas instalados na configuração do usuário
não são carregados implicitamente por esta auditoria. Sem `--size`, o programa
usa a resolução da origem quando disponível, mantendo as recusas normais
quando faltam dimensões comprovadas.

O relatório agrega contagens por formato, destino e identificador de efeito.
Inclui códigos de avisos de perda da origem e da conversão separadamente;
esses contadores não devem ser somados como perdas distintas. Não inclui
nomes de arquivos, caminhos de origem, nomes de presets, valores ou bytes
extraídos. Ignora arquivos de preset que sejam symlinks, como o lote normal.

O script usa os parsers e a prévia headless existentes, verifica o hash de cada
arquivo antes/depois e não publica planos de conversão. Recusa saída dentro
da pasta de origem e arquivos de saída existentes. Entrada inválida ou mudança
do arquivo durante a análise interrompe a auditoria, sem relatório parcial.
Não contacta uma engine: não verifica instalação do WASM, execução nativa nem
equivalência visual. Os hashes comprovam integridade durante a leitura, não
certificam a procedência dos presets.

## Próximo efeito investigado

`PEGR`, apresentado como Crate’s Godrays na amostra local, contém 25 controles
de processamento tipados e estáticos. Isso oferece evidência dos IDs, valores
e menus daquela amostra, mas ainda não comprova as unidades dos sliders ou
da posição, a calibração do algoritmo ou sua equivalência no destino. O efeito
recebe mapa e renderer original aproximado na 0.36.0. Quality contém um
separador recusado, e Buffer Expansion exige tratamento de geometria antes
de se declarar suporte fora do valor neutro.
[Instalação, provas e limites](godrays-extension.md).
