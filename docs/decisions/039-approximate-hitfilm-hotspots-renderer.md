# ADR 039 — HitFilm Hotspots separado, original e aproximado

Status: implementado na 0.34.0, sem certificação visual.

## Evidência

Dois parT/tdb4 privados comprovam cinco controles visíveis e dois hidden.
Threshold kind 10 difere (~0,3/0,75), ARGB255 é preto, Saturation/Brightness
são 1, Smooth Source visível -0006 é 0. Hidden -0005 kind 1 e -1985 Preset
não são silenciosamente descartados como sem efeito. Nenhum parser alterado.

O manual oficial HitFilm 2017 apareceu no índice público com a seção
Threshold Add Color/Smooth Source; abertura direta retornou 403. O manual
legado público também confirma isolamento de highlights. Consultados em
09/10/2026; evidência funcional, sem código/binários/SDK/assets reutilizados.
URLs e limites em [hfhotspots-extension.md](../hfhotspots-extension.md).

## Decisão

Criar módulo original independente `org.craftbridge.hfhotspots`, API 2/revisão
1, cinco parâmetros/oito f64/uma imagem. O mapa exige os cinco IDs reais.
Gate por pico RGB, fill subthreshold, saturação/brilho apenas nos highlights,
box fracionário em RGBA antes do gate, modelo premultiplicado próprio.
Faixas e unidades de radius pertencem à implementação Bridge. Nenhuma
inferência de tipo Layer/default None em blobs não decodificados.

Reutilizar apenas wrapper/helpers MIT originais do próprio Bridge. Preservar
fingerprints/WASM/mapas anteriores. Acrescentar NAMES instala um mapa opt-in,
nunca carrega executável implicitamente. Threshold Add Color de S_Hotspots
é bias cromático; compartilhar esse mapa confundiria dois comportamentos.

## Consequências

Dez valores reais recebem tradução, mas calibração e hidden permanecem
perdas relevantes. Strict continua recusando parcial. Validação em pixels
originais e persistência nativa não é comparação visual da origem. O objetivo
universal continua incompleto e exige tratar outros efeitos e dados complexos.
