# ADR 041 — Godrays bruto e transporte Point

Status: implementado, aproximado; suporte universal aberto.

## Evidência

Um snapshot real PEGR comprova 25 controles estáticos, Position kind 6 sem
unidade, Spin Amount kind 3 em graus, Quality com separador e expansão neutra.
Não comprova unidades de sliders, posição normalizada ou kernel/calibração.

O host usa `effects::plugin::flatten → Buf::to_px(q)`, inclusive na API 2.
A primeira prova nativa half revelou dupla aplicação de escala quando o f64
recebido era interpretado como valor bruto. A inversão `(flat-offset)/scale`
recupera o valor armazenado; testes Rust incluem padding e Session full/half
confere pixels analíticos. Não foi necessário alterar o host ou mapas anteriores.

## Decisão e consequências

Renderer original MIT API 2 radial/spin com 25 controles, identidade para
sliders/Point, tabelas de menus comprovadas e modelo matemático próprio
explicitamente declarado. Sempre registrar perda de fidelidade/calibração.
Quality=5 e Buffer Expansion não neutro recusados; controles obrigatórios não
recebem defaults por suposição. Expansão de canvas e equivalência continuam
requisitos pendentes. Expressões e plugins Adobe nunca executados.

Matemática sintética, transporte real opt-in e render de pixels próprios são
provas separadas. HD uniforme usa identidade de amostragem constante; não
prova desempenho geral. Strict sem publicação parcial, sem promoção automática
de um preset inteiro após adicionar um efeito.
