# ADR 005 — Transferência parcial da LUT Curves

## Problema e evidência

O blob estático ADBE CurvesCustom-0001 v1 tem cinco LUTs de 256 bytes e cinco registros
de até 16 pontos. O layout está documentado em py-aep/docs/file_format.md, commit de
references.json, seção aRbp/Curves. O corpus contém 24 instâncias: 22 estáticas nesse
perfil e duas com estruturas/animação ainda não suportadas. Os registros/pontos e as
flags originais são preservados no modelo, sem presumir a semântica das flags.

EffectCraft ec.color.curves usa strings Hidden Value::Str para rgb/red/green/blue/alpha.
Curve::parse normaliza a lista de pares e interpola por Hermite monotônico
Fritsch–Carlson, com tabela de 1025 entradas e interpolação linear no acesso. Essa
interpolação não é a spline Adobe. Usar somente os pontos originais não é suficiente.

## Decisão

Transferir todos os 256 samples de cada canal como pares x/255,y/255. Não estimar a
spline Adobe pelos seus poucos pontos. O parent mantém pontos, LUTs, flags e origem
aRbp no diagnóstico; cinco parâmetros derivados Text carregam a representação nativa.
O parent se torna administrativo somente após validar integralmente o blob estático.

A perda CURVES_INTERPOLATION pertence ao efeito e sempre acompanha a exportação:
o destino reamostra a LUT, usa outra interpolação, e a tabela de 8 bits não representa
com precisão os cálculos Adobe em 16/32bpc ou HDR. O modo normal publica resultado parcial;
strict o recusa. Isso é um avanço no suporte, não a solução final de equivalência visual.
A seleção do canal de edição na interface (source -0002) ainda não é mapeada. O campo
channel nativo Hidden/Enum continua Opaque, sem adivinhar um popup a partir de seu default.

Blobs animados, múltiplos, ausentes, versões/flags de stream desconhecidas ou expressões
continuam recusados. Nunca se aplica uma curva estática extraída de uma animação sem
preservar seu tempo. O parent mantém o aviso de leitura quando a derivação não é possível.

## Text e validação

Text no plano v2 é uma extensão de tipo que exige Bridge 0.6+. A API prop.set já aceita
Value::Str; o adaptador não avalia os textos. Limite: 65536 bytes UTF-8 sem NUL; somente
estático. Hidden só é classificado Text quando seu default oficial é string. Outros
Hidden permanecem Opaque, evitando dedução de tipos por número ou nome.

O perfil ec.color.curves aceita 2..256 pares x,y finitos em 0..1, x crescente de 0 a 1,
separados por espaço, com números ASCII. A validação impede tokens que Curve::parse ignoraria silenciosamente,
duplicatas que a engine removeria, curvas incompletas e números não finitos. Text com
keyframes é recusado na conversão e na validação de planos importados. FilmCraft Text
estático recebe também o wrapper serde nativo; animação textual permanece recusada.

## Medição executada

O harness chama Curve::parse/eval da biblioteca oficial, sem uma reimplementação Python
do algoritmo. Foram examinados **110 canais** das 22 instâncias estáticas, nas 256
posições x=i/255. Resultados em unidades de 8 bits (erro absoluto normalizado ×255):

| Reconstrução | Erro máximo nos samples | Canais com diferença acima de 1e-7 normalizado |
|---|---:|---:|
| Somente pontos originais | 39,094917 | 24 |
| LUT com 256 pontos | 0,02454235 | 24 |

Isso mede a transferência da LUT armazenada, não o algoritmo Adobe renderizado. Não
é uma garantia para pixels entre os samples, HDR, composição de canais ou outras versões.
O roundtrip nativo verificou as 110 strings após aplicar, salvar .ecproj e reabrir.
Além do avaliador Curve::eval, o harness renderizou ramps de 256 samples pelo render
oficial ec.color.curves, isolando um canal por vez (alpha usa pixels premultiplicados).
Os samples retornados pelo renderer e pelo avaliador foram exatamente iguais nos
220 casos de reconstrução: 110 por modo. Isso verifica o destino, não o renderer Adobe.
Não houve comparação de imagens geradas no Adobe.

Regeneração sobre corpus privado local e saída nova:

```sh
.venv/bin/python scripts/validate_curve_transfer.py CORPUS_LOCAL artifacts/nova-auditoria-curves
.venv/bin/python scripts/validate_native_components.py CORPUS_LOCAL artifacts/novos-componentes-curves \
  --source 'ADBE CurvesCustom'
```

Os datasets de entrada, LUTs, resultados por canal e projetos nativos permanecem em
artifacts/, fora de Git/wheel/sdist. Este ADR contém apenas formato público e medidas agregadas.

## Mesh Warp: pesquisa pendente

O único Mesh Warp do corpus contém um blob de 2580 bytes: cabeçalho de 20 bytes e
64 registros de 40 bytes. Default e instância diferem em quatro registros. O padrão
do default sugere um vértice e quatro controles por registro numa grade 8×8, mas a
semântica das tangentes e sua equivalência ainda não foi validada. O destino meshwarp
usa offsets de vértices e interpolação bilinear; não representa esses controles diretamente.
O Bridge mantém o blob opaco. Essa observação não constitui um mapa nem uma decodificação
certificada; descartar as tangentes silenciosamente não satisfaria suporte integral.

Na 0.14.1, a preservação estrutural dos dez floats por registro e a associação
do blob de instância ganharam leitor e testes de roundtrip. Semântica, unidades
e tradução das tangentes continuam pendentes. [ADR 015](015-mesh-structural-records.md).
