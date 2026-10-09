# Craft Preset Bridge

Leia `docs/research.md` e `docs/compatibility.md` antes de alterar parsers ou mapas.
Não edite `.research` nem o pacote de presets do usuário. Não redistribua fixtures privadas.
Núcleo headless; PySide6 somente em `gui`. Não execute expressões extraídas.
Não invente IDs nem unidades. Mapeamentos novos exigem evidência, limites e teste.
Perdas relevantes devem aparecer no relatório; strict não publica um preset parcial.
Verifique com `uv run --extra dev pytest`, `uv run --extra dev ruff check .` e
`uv run --extra dev mypy`. Amostras reais são testes opt-in separados.

