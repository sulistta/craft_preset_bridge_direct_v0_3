# ADR 003 — Estado de cor em aRbp

Hue/Saturation, Levels e Curves guardam seus ajustes em LIST:aRbs/aRbp imediatamente
após o tdbs da propriedade. Os valores de parT são defaults e não substituem esse estado.
O layout está documentado em py-aep/docs/file_format.md no commit fixado em references.json
e foi conferido contra os blobs de instâncias do corpus privado.

Hue/Saturation usa 45 inteiros big-endian: três ajustes Master e seis faixas com quatro
limites de janela e três ajustes. A conversão preserva as janelas circulares; Reds pode
começar em 345° e terminar em 15°. Os falloffs são as distâncias circulares entre os
limites externos e internos. Janelas ambíguas/sobrepostas fora do perfil são recusadas.

Levels usa magic 0x000F10A7, versão 1 e 25 floats big-endian: cinco ajustes de cada um
dos cinco canais. Input/Output usam unidades normalizadas e Gamma mantém o valor direto.
Os campos temporários da UI podem estar zerados ou apontar para outro canal; o corpus
contém casos concretos. Após decodificar o blob inteiro, esses campos são marcados como
sombras da UI. Se estiverem animados ou desconhecidos, o efeito é recusado para evitar
aplicar uma captura estática como animação. Blobs animados, múltiplos, com expressões,
versões/tamanhos/flags desconhecidos permanecem perdas e não são achatados.

Os switches de clipping Levels são globais na origem e separados por canal no destino;
seus valores são duplicados explicitamente para os cinco canais. A tabela de menus
é origem 1 (On) → destino 1, origem 2 (Off) → destino 0. A opção origem 3 (Off for 32bpc)
é recusada: a engine atual trata o índice 2 como On, e o FFX não comprova a profundidade
do projeto original. Não se altera essa opção silenciosamente.

Curves tem cinco LUTs de 256 bytes e cinco registros de até 16 pontos. Ambos são
preservados no modelo intermediário após validar tamanho, versão e contagens. A engine
possui uma curva monotônica cúbica própria e uma LUT de resolução diferente. Não se
exportam só os pontos afirmando que isso preserva a curva Adobe: ainda falta validar
uma tradução da LUT/interpolação. CURVES_INTERPOLATION identifica essa limitação.

Cada valor derivado carrega o ID da propriedade original e o offset/hash do aRbp.
Somente blobs de instância integralmente reconhecidos saem da contagem de chunks opacos.
Dados de terceiros e defaults não reconhecidos continuam nos diagnósticos limitados.
O produto continua offline e não executa expressões nem conteúdo dos blobs.
