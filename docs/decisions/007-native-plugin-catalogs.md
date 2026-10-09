# ADR 007 — Catálogos de plugins nativos EffectCraft

## Necessidade e evidência

O catálogo fixado tem 306 efeitos, mas não renderers para os principais plugins
do corpus. PEDG aparece 73 vezes. Deep Glow é descrito pelo fabricante como glow
com falloff inverso ao quadrado e controles próprios de gama, threshold/HDR e composição
([fonte primária](https://www.plugineverything.com/deep-glow)). O Glow nativo usa outro
contrato; renomear PEDG não preservaria o efeito.

EffectCraft oferece plugins API v1, Rust e WebAssembly, conforme docs/plugins.md e
crates/effects/src/plugin.rs do commit fixado em references.json. Plugins registrados
têm propriedades, animação e comandos oficiais. Antes desta etapa, o Bridge recusava
todos os IDs externos, inclusive renderers corretamente registrados. Esse impedimento
foi removido para permitir implementações open source específicas sem plugins Adobe.

## Contrato

Pacotes craftbridge.mappings **v2** declaram `plugins` com o manifesto da API oficial.
São aceitos slider, angle, checkbox, popup, point e color; defaults/tipos/menus/limites
são validados. Máximo 64 plugins e 256 parâmetros por plugin. IDs `ec.` são reservados;
substituições do catálogo e manifestos conflitantes são recusados. Instalação falha
não deixa o registro em memória parcialmente atualizado nem sobrescreve arquivos.

Os mapas continuam exigindo evidência dos IDs, unidades e semântica. Um manifesto
não cria renderer nem prova correspondência com Adobe. O Bridge não carrega/executa
WASM, Rust ou expressões ao ler presets/instalar mapas. O renderer deve estar
registrado no EffectCraft pelo mecanismo oficial; nenhum path/código entra no plano.

Saídas novas usam **plano v3**. Cada efeito externo recebe plugin_fingerprint, SHA-256
do manifesto normalizado, conferido contra o pacote instalado. V2 segue aceito para
builtins; plugins exigem V3. V1 continua recusado. Manifesto alterado, ausente ou não
instalado invalida o plano antes da aplicação.

O preflight consulta effect.plugins.list/effect.list e confere API, ID único, versão,
lista ordenada de parâmetros e defaults. Divergências recusam aplicação antes de
effect.apply/prop.set. O protocolo atual não publica UI/limites completos nem hash
do módulo: limites vêm do manifesto revisado. O fingerprint identifica **metadados**;
não atesta código binário nem equivalência visual. A introspecção não é apresentada
como prova de informações que ela não fornece.

## Validação

O harness ganhou o loader oficial effectcraft-plugin/wasm, sem alterar os checkouts
de referência. Um módulo WAT original e sintético usa gain, enabled e channel; não
implementa nem representa um efeito Adobe.

- Carregado por effect.plugins.load na Session descartável, API v1.
- Pacote instalado, convertido para v3, manifesto fixado e preflight aceito.
- Três propriedades conferidas por prop.get e após salvar/reabrir .ecproj.
- Renderer oficial de plugins processou três casos (All/Red/Disabled), quatro pixels
  cada: 12 amostras com alpha parcial/zero e RGB HDR. Comparação com a fórmula do
  módulo, tolerância 1e-6; também detecta trap que deixe o frame inalterado.
- Testes de versão/API/defaults/IDs divergentes recusam antes de comandos de mutação.

Artefatos: artifacts/plugin-native-final-v0.8/. Auditoria reproduzível em Session nova:

```sh
.venv/bin/python scripts/validate_plugin_catalog.py artifacts/nova-auditoria-plugin --port 20088
```

O corpus segue **75 PARTIAL/69 UNSUPPORTED, 1370 parâmetros/17 chaves**, nenhum
preset completo. A extensão não adiciona mapas reais para Deep Glow, Optical Flares,
Sapphire ou OLM Directional Blur. Suporte universal permanece pendente; esses efeitos
precisam de renderers e mapas específicos, com evidência própria.
