# Por que os presets ficam parciais ou não suportados

Um arquivo FFX guarda configurações e referências; ele não contém a implementação
do plugin que produziu o efeito. Ler seus números não instala Sapphire, BCC,
Dehancer ou outros plugins no EffectCraft. A conversão precisa de um mapa
verificado e de uma implementação correspondente no destino.

No corpus local de 144 arquivos, a validação 0.23.0 com todas as onze extensões
opcionais e a biblioteca local de flares encontrou 124 PARTIAL e 20 UNSUPPORTED,
com 3301 propriedades e 507 chaves transferidas. São resultados de transferência
de dados, sem certificação de equivalência visual. A instalação básica possui
menos mapas. A correção 0.23.1 melhora os diagnósticos, sem adicionar efeitos:
recupera 353 avisos de parâmetros que antes eram omitidos em 65 instâncias
sem mapa, incluindo seis expressões, duas animações com layout desconhecido
e os dados estruturais Mesh Warp. Os 144 arquivos originais continuam intactos.

- **NO_MAPPING:** falta uma correspondência verificada para o efeito ou recurso.
- **UNDECODED_VALUE / COMPLEX_PARAMETER:** o valor, referência ou bloco privado
  ainda não pode ser interpretado. `null` nesse diagnóstico não prova ausência
  de camada, máscara ou projeto Mocha.
- **PARAMETER_UNSUPPORTED / PARAMETER_REJECTED:** um efeito tem mapa, mas algum
  controle não possui destino ou não atende aos tipos, limites ou condições.
- **MAPPING_APPROXIMATION:** a implementação original preserva controles, mas
  tem diferenças declaradas de algoritmo, amostragem, cor ou composição.
- **EXPRESSION / KEYFRAME_LAYOUT:** há comportamento ou animação que não pode
  ser transferido com evidência suficiente. Expressões nunca são executadas.

Os avisos de origem de cada parâmetro aparecem mesmo em efeitos sem mapa e
recusas antecipadas. O relatório JSON mantém `code`, `path` e `loss`; a mensagem
identifica nome e ID do parâmetro. A GUI, `inspect` e o HTML usam esses mesmos
avisos. O modelo intermediário e os bytes de origem não são alterados para
produzir o relatório. Um aviso sem perda não muda sozinho o status para PARTIAL.

## Exemplo: S_MathOps

As quatro instâncias locais possuem SourceB, Mask from Layer, Mask from Path e
Mocha ainda opacos. Também usam A Darks não neutro. O efeito nativo Compound
Arithmetic recebe duas imagens, mas não fornece diretamente os ajustes de
lights/darks/saturation de cada entrada e saída. A documentação pública do
[S_MathOps](https://borisfx.com/documentation/sapphire/ae/mathops/) descreve esses
controles; não especifica seus bytes FFX nem comprova que uma referência local
desconhecida está vazia. Mapear somente Add descartaria configurações relevantes.

Os [bindings Layer nativos](layer-resources.md) permitem escolher uma camada
em um plano próprio v4. Essa capacidade ainda não decodifica SourceB, não cria
um mapa S_MathOps e não fornece uma segunda imagem aos plugins WASM API v1.
S_DissolveShake também depende de outra imagem. Recursos de origem, controles,
renderer e integração precisam avançar juntos.

**PARTIAL** permite uma saída com perdas declaradas; **UNSUPPORTED** não publica
um preset. Com `--strict`, uma conversão parcial é recusada e publica apenas
os relatórios. O objetivo de suportar todos os efeitos continua pendente.
