# Imagens temporais — host experimental API 4

O Bridge 0.30.0 aceita manifestos API 4/revisão 3 e planos v4 que solicitam
imagens da própria camada em outros instantes. A cópia experimental do
EffectCraft usa `EffectHost::self_at` com o prefixo de efeitos anterior ao
plugin. Isso inclui animação dos efeitos anteriores e exclui o efeito atual.
É infraestrutura para renderers futuros; nenhum mapa Adobe foi acrescentado.

O EffectCraft oficial não recebe essa extensão automaticamente. Prepare uma
cópia isolada com `uv run python scripts/prepare_effectcraft_multi_input.py
--out artifacts/effectcraft-temporal-host`. O script exporta o commit
`e38a92e792c07f1c57c5dcfcab37d91932b9e2b8`, verifica o patch e registra seu hash;
não altera `.research`, os presets ou uma instalação do usuário. O nome
histórico `host-api2.patch` agora contém as revisões experimentais 1 a 3.

## Contrato declarativo

O manifesto exige `api: 4`, `bridge_host_revision: 3` e `temporal_inputs` não
vazio. Cada entrada possui `id`, `mode`, `parameter`, `multiple` e `edge`.
O parâmetro deve referenciar um slider existente. IDs são ASCII alfanumérico
ou underscore, únicos, até 128 caracteres. Campos desconhecidos são recusados.

| mode | Unidade do contrato original | Limites do slider | Comportamento |
| --- | --- | --- | --- |
| frame_hold | Quantidade inteira de frames pulados | 0 a 1024 | Retém o frame por skip+1 passos; multiple=1 |
| seconds_offset | Segundos locais da camada | −1000 a 1000 | tempo atual + valor × multiple |
| frames_offset | Passos locais de frame | −10000 a 10000 | tempo atual + valor × multiple × passo |

`multiple` é inteiro de 1 a 16, sem booleanos. Os offsets aceitam frações;
frame_hold exige default/valores/chaves inteiros e animação Hold. Esses limites
pertencem ao contrato do Bridge, não a unidades inferidas dos presets Adobe.

A retenção ancora no menor dos tempos locais visíveis. Skip=0 solicita o tempo
atual. O passo local positivo considera FPS e stretch da camada. `edge` aceita
clamp (default), wrap ou mirror. Wrap usa período intervalo+um passo e retém
o último frame na fração final do período; mirror reflete no intervalo.
Uma janela de um frame retorna sempre seu único instante. Pedidos não finitos
ou com magnitude acima de 1e9 segundos são recusados.

## ABI e preflight

`ec_render_v4` possui a assinatura de dez argumentos da API 3, com outro nome
de export. As APIs 1/2/3 conservam suas assinaturas. A tabela mantém descritores
de 80 bytes: entrada principal flag 1, Layer flag 2 e temporal flag 4.
A declaração temporal ocupa o ordinal com bit alto 0x80000000, UID zero e
reserved em +28 zero. Em +72 existe f64 little-endian com o **tempo local
solicitado**; os demais descritores mantêm esses oito bytes zerados. O renderer
nativo pode quantizar o pedido para sua base de ticks.

O contexto temporal de 32 bytes da API 3 permanece: FPS, primeiro e último
tempos locais visíveis e passo local positivo. A geometria dos pixels mantém
o contrato API 2. As entradas auxiliares Layer e temporais compartilham limite
quatro; temporal_inputs contém de uma a quatro declarações.

Antes de modificar uma Session, o Bridge exige capabilities API 4, revisão 3,
layer_timing/temporal_sampling verdadeiros, limite temporal exatamente quatro
e declarações do plugin carregado iguais às do manifesto instalado. O exemplo
[plugin-temporal-package.json](examples/plugin-temporal-package.json) e o
[WAT original](examples/plugin-temporal-probe.wat) testam transporte de pixels.
Não representam um efeito Adobe.

## Falhas e recursos

A chamada temporal exige EffectHost e imagem disponível. Adjustment layer,
fonte ausente ou inválida não recebem uma imagem fabricada. O host mantém
limites de 8.388.608 pixels por imagem, 33.554.432 no total, lado até 65536,
memória WASM até 1 GiB e combustível limitado. A árvore síncrona por thread
compartilha orçamento de 64 consultas auxiliares e profundidade temporal 16.
Falha em chamada temporal aninhada invalida a árvore mesmo quando um callback
retorna uma imagem substituta. O próximo render independente recebe orçamento
novo. Pixels só são publicados após validação da saída completa e finita.

## Evidência e limites

36 testes Rust passaram, incluindo recusa de filhos com falha, recuperação,
limites e regressões API 1/2/3. Na Session real, 23 verificações com imagens
originais e BrightnessContrast animado comprovaram pixels do prefixo em outros
tempos: full/half, pedidos fora de ordem, trim, stretch reverso, chaves Hold e
salvamento/reabertura. Não há comparação visual Adobe ou novo preset real
certificado por esse experimento. O lote continua 131 PARTIAL/13 UNSUPPORTED;
as perdas e a recusa strict permanecem. [ADR 035](decisions/035-temporal-source-images.md).
