# Multiband Sharpen opcional — 0.22.0

O renderer original aproxima **S_Sharpen** usando quatro bandas de detalhes
no modo Best e unsharp no modo Fast. Preserva 15 coeficientes de processamento:
Quality, Sharpen Amp, Edge Threshold, Small Detail Size, quatro Detail Scales,
Sharpen Width, Luma/Chroma, Red/Green/Blue e Opacity.

```sh
craft-bridge extensions install sharpen
craft-bridge extensions list
```

A instalação registra o mapa declarativo; não carrega o módulo executável.
Carregue o arquivo `module` listado no EffectCraft por `effect.plugins.load`,
ou use **Effect → Load Effect Plug-in…** no EffectCraft. Reinicie a GUI do
Bridge e reconverta para uma pasta nova.
Planos verificam manifesto/fingerprint antes da aplicação.

Uma instância real transferiu 15 valores estáticos, conferidos na Session
oficial após salvar/reabrir. Quality=Best e Opacity=Normal são os únicos modos
observados nessa amostra. Outros modos e animações têm testes sintéticos.
Não há comparação de pixels com Sapphire/Adobe nem promessa de equivalência.

Os filtros, raios, limiares, separação de cor e calibração são próprios.
Fast não usa as quatro escalas de detalhes; Best combina essas bandas com
Sharpen Width. O limiar reduz a alteração em bordas fortes; amplitude negativa
permite suavização. Normal filtra cor premultiplicada e normaliza por alpha;
As Premult opera RGB armazenado; All Opaque força alpha=1. Cores retas têm
limite próprio de ±1000000. Essas diferenças permanecem perdas no relatório.

Matte de camada/path e Mocha continuam opacos. Não se presume máscara vazia,
mesmo com controles locais neutros. Show Small Detail Size é o widget de edição
da origem e não é transferido; não desenha um efeito no quadro exportado.
Todos os resultados desta extensão são PARTIAL; strict não publica o plano.

32 casos WASM distintos passaram no loader oficial, incluindo referência independente,
HDR/alpha, cada banda/canal, controles reais sobre pixels próprios e dois
quadros Full HD não uniformes e um quadro 3840×2160. Neste ambiente, Best
levou ~45 s em Full HD e ~233 s em 4K; Fast Full HD levou ~15 s;
CPU/WASM ainda é lento para preview. Detalhes: [validação](validation.md),
[decisão e limites](decisions/024-approximate-sharpen-renderer.md).

Com os 11 opcionais e a biblioteca Flare local: 124 arquivos PARTIAL,
20 UNSUPPORTED, 3301 propriedades/507 chaves; os 144 originais estão intactos.
O suporte universal segue em andamento, incluindo máscaras, múltiplas imagens,
geometria, recursos externos e fidelidade visual.
