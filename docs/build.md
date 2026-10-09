# Builds e solução de problemas

## Fonte e wheel

`uv sync --frozen --extra dev --extra gui`, depois `uv run --extra dev python -m build`.
O wheel contém craft_bridge, schemas, mapas e renderers/templates WASM originais.
Presets privados, bibliotecas Flare geradas e clones não entram.
O sdist exclui explicitamente artefatos, clones e o pacote privado. `uv.lock` fixa dependências.

## Desktop Windows, macOS e Linux

Execute `uv sync --frozen --extra gui --extra build` e
`uv run --extra gui --extra build python scripts/build_desktop.py` **no sistema de destino**.
PyInstaller gera um diretório em dist; não é um cross-compiler. Bibliotecas Qt permanecem
dinâmicas; os avisos e metadados de licenças acompanham o bundle. Sem assinatura, notarização,
MSI, DMG ou AppImage nesta entrega. A CI fornece builds manuais por workflow_dispatch.

Linux precisa de uma sessão gráfica e das bibliotecas de plataforma do Qt, como libxcb-cursor
para X11. Em CI use `QT_QPA_PLATFORM=offscreen`. `craft-bridge doctor --json` informa se
PySide6 está instalado. Se Qt falhar ao carregar xcb, instale os pacotes Qt/XCB da distribuição
ou execute em uma sessão Wayland compatível; não reinstale Adobe.

## Validação nativa opcional

Clone os commits exatos em docs/references.json para `.research/filmcraft` e
`.research/effectcraft`. Não é necessário para instalar ou executar o Bridge.

```sh
CARGO_PROFILE_DEV_DEBUG=0 CARGO_INCREMENTAL=0 CARGO_TARGET_DIR=artifacts/native-target \
  cargo +1.98.1 build --locked --manifest-path scripts/native-validation/Cargo.toml -j 4
artifacts/native-target/debug/craft-bridge-native-validation filmcraft preset.filmcraft.json
artifacts/native-target/debug/craft-bridge-native-validation effectcraft 19877
```

O harness usa Session real das engines e oferece um transporte de teste JSON/TCP, não a UI
desktop. Cria apenas uma composição/camada em memória, consulta a engine e salva projetos pela
API. Os clones não são modificados. O Cargo.lock do harness fixa os transitivos; reserve espaço
livre para compilação. `DEBUG=0` evita caches de debug de vários GB. Runtimes Python não usam Rust.

## Problemas comuns

- `PARTIAL`/`UNSUPPORTED`: abra o relatório. Plugins sem mapa não são falhas do parser.
- Coordenadas não convertidas: informe --size, não assuma a resolução do vídeo.
- Strict falhou: há perda relevante; a saída de preset foi suprimida e o relatório explica.
- Saída já existe: use outro nome ou diretório. Não há sobrescrita implícita.
- Porta recusada: abra EffectCraft/FilmCraft com --control; o CLI Bridge só usa localhost.
- Keyframe seria deslocado: use uma composição/frame rate compatível; o adaptador recusa snapping silencioso.
- Limite excedido: ajuste Limits/--max-mib/--timeout conscientemente; arquivos malformados permanecem recusados.
- Fechar a GUI durante trabalho: aguarda o arquivo em andamento; cancelamento ocorre entre arquivos.

Próximos passos: fixtures rotuladas para Motion/Opacity e modos de retiming Premiere,
curvas espaciais/cor Bezier do FFX, mapas Glow e recursos de cor restantes com unidades verificadas, comparação de
renders por efeito e transações/rollback de aplicação. Builds assinados exigem infraestrutura externa.
