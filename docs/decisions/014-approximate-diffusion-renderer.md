# ADR 014 — Difusão de paleta original, suporte parcial Omino

## Evidência e decisão

Em 08/10/2026 foram consultadas a [página oficial da suite 2.2 build 13](https://omino.com/store/ominoAeSuite_2_2_13/index.html)
e a [publicação do autor sobre debug](https://omino.com/pixelblog/2008/02/).
A descrição funcional sustenta paleta configurável, quatro direções, faixas e
propagação de erro; não publica fórmulas. O código é disponibilizado mediante
acordo; não foi obtido, copiado ou incorporado. Nenhum binário, SDK ou asset Adobe
é necessário. Esta extensão MIT é uma implementação independente aproximada.

Quatro snapshots privados estáticos comprovam os 17 controles parT/tdb4:
0001/0017 (kind 10) error across/aside; 0002 (kind 5) initial phase;
0003 (kind 7) menu right/left/down/up; 0016 (kind 1) color count;
0004/0006/0008/0010/0012/0014 cores ARGB255 (kind 5);
0005/0007/0009/0011/0013/0015 widths (kind 1).
Os números de contagem 1..6 tornam-se Choice 0..5, com menu numérico próprio.
Não há animação Omino real neste corpus. Stamps/debug continuam perdas explícitas.

## Algoritmo e limites próprios

Scanlines são percorridas na direção selecionada, sem serpentina. A cor direta
de entrada é limitada a 0..1 e quantizada a 8 bits. A menor distância RGB quadrática
seleciona a primeira cor em empates. A cor selecionada permanece por
`max(1, round(width * scale))` pixels; cada pixel acumula o erro de cor direto.
O erro vezes across segue ao próximo pixel; vezes aside segue à mesma posição
da próxima scanline. RGB de Initial Phase inicia o erro de cada scanline.
As bordas descartam erros sem wrap. Erros são limitados a ±1024 para garantir
convergência numérica mesmo com coeficientes negativos ou exagerados.

Alpha da paleta multiplica alpha da entrada; pixels transparentes não propagam
erro nem iniciam faixas. Alpha da fase é ignorado. As cores da paleta são
quantizadas a 8 bits também. Não se afirma que qualquer dessas decisões reproduz
o algoritmo Omino. Coeficientes -4..4 e widths 1..4096 são limites próprios,
não unidades nem limites de origem descobertos. Valores externos são recusados
na exportação; não há clamp silencioso de controles.

O ABI v1 é o contrato oficial de uma imagem premultiplicada e 38 doubles de
parâmetros. Sem imports, execução de expressão ou acesso a camada/arquivo.
Limites: 8.388.608 pixels, lados até 65.536, scale (0,16]; parâmetros/imagem
finitos e alpha 0..1. Chamadas inválidas preservam o buffer original.
O resultado permanece PARTIAL; strict não publica o plano.

## S_DissolveShake investigado separadamente

A [documentação Boris FX](https://borisfx.com/documentation/sapphire/ae/dissolveshake/)
confirma Foreground/Background e Auto Trans dependente dos limites da camada.
Os quatro snapshots completos e cinco grupos selecionados locais contêm Background
opaco, ainda sem referência de camada decodificada. O ABI v1 não fornece segunda
imagem nem limites da camada. Este efeito continua sem mapa; não se assume fundo
preto/transparente nem se substitui uma transição por Shake.

## Validação

Os testes sintéticos usam pixels e arquivos originais de teste. O corpus privado
é opt-in, separado, e não é distribuído. Comparação visual Adobe permanece ausente;
persistência de parâmetros na Session e execução WASM são verificações diferentes.
