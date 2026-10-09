# ADR 015 — Registros estruturais Mesh Warp

## Evidência e escopo

O perfil é sustentado pelo único snapshot autorizado `ADBE MESH WARP`, com
um payload de definição e um de instância. A associação segue a documentação
`aRbs`/`aRbp` de py-aep no commit de references.json: o blob após o tdbs pertence
à propriedade; o blob parT é default. Não se reutilizou código ou fixture privada.
A observação anterior do [ADR 005](005-curves-lut-transfer.md) passa a ter leitor
estrutural e roundtrip verificável, sem se tornar mapa geométrico certificado.

Ambos os blobs têm 2580 bytes: cinco palavras big-endian u32
`8,8,0,0,0x0d0d`, seguidas por 64 registros de dez float32 big-endian.
Somente este cabeçalho e tamanho observados são aceitos. As palavras do cabeçalho
não recebem nomes semânticos/versionamento inventados. Os dez floats de cada
registro são preservados na ordem original, sem converter unidades nem descartar
pares. Não se infere normalização ou significado de tangentes pelos valores.
Na comparação real, quatro registros da instância diferem do default.

## Implementação e garantias

`mesh.py` valida o payload inteiro, recusa NaN/Inf, conserva sinais de zero e
registra 64 unidades no orçamento compartilhado, checando o prazo por registro.
O serializer diagnóstico exige a representação completa e valores float32
exatos; não é chamado pelo exportador e não edita o FFX de origem.

O parser aceita somente uma folha aRbp de instância, kind 11, dimensions 1,
stream_flags 7, static, sem chaves ou avisos inesperados. Animação, associação
ambígua, cabeçalho/tamanho desconhecido e dados inválidos permanecem opacos.
A propriedade permanece unknown, não administrativa, com dados estruturais em
metadata e aviso `MESH_RENDER_UNSUPPORTED`. Não há parâmetros derivados nem mapa.
Strict continua sem publicar um preset incompleto.

O destino EffectCraft, commit e38a92e792c07f1c57c5dcfcab37d91932b9e2b8,
`distort2.rs:mesh_warp`, recebe offsets de vértices e interpolação bilinear.
Copiar um dos cinco pares e abandonar os restantes alteraria o resultado.
A evidência atual não certifica uma tradução das tangentes ou da superfície.
Esses pontos continuam trabalho necessário para suporte visual Mesh Warp.

## Validação

28 testes sintéticos originais verificam roundtrip JSON/bytes, sinais de zero,
campos finais, limites/prazo, cabeçalhos, NaN/Inf, truncamento/trailing bytes,
float32 não exato, propriedade estática/animada, defaults diferentes e ausência
de exportação falsa. O teste real opt-in lê os dois blobs e confirma os 1280
campos float32 e byte roundtrip exato, sem redistribuir dados.
A cobertura de conversão continua 119 PARTIAL/25 UNSUPPORTED com extensões,
zero SUCCESS; este incremento amplia leitura estrutural, não certificação visual.

## OLM Directional Blur: pesquisa separada

A [página oficial OLM](https://www.olm.co.jp/post/olm-directional-blur), consultada
em 08/10/2026, e seu pacote oficial foram conferidos. O ZIP contém 41 entradas:
binários AEX, dois manuais PDF e LICENSE-2.0.txt; não contém código-fonte.
O pacote identifica Apache 2.0. Nenhum AEX foi executado, instalado, incorporado
ou redistribuído. Download e extração do manual para consulta ficam em artifacts,
fora dos pacotes de distribuição.

O manual descreve comportamento anisotrópico, grupos de pixels opacos e tratamento
de transparência, distintos do Directional Blur nativo comum. Essa evidência
impede usar um mapa nominal como reprodução do efeito. Não foi criado mapa OLM.
