"""Pacotes declarativos: apenas operações conhecidas, sem import/eval/plugins Python."""

import json
import os
from copy import deepcopy
from importlib.resources import files
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, StrictInt, ValidationError

from craft_bridge.core.models import Model
from craft_bridge.core.safety import BridgeError, Limits, atomic_write, json_text, read_bounded
from craft_bridge.mappings.plugins import PluginManifest


class Rule(Model):
    target: str
    operation: Literal[
        "identity", "normalized_to_pixels", "minus_one", "times_100", "times_255", "argb255_to_rgba", "enum_map", "ofp_scene_lookup", "explicit_layer_binding"
    ] = "identity"
    kind: Literal["Float", "Bool", "Choice", "Vec2", "Color", "Text", "Layer"] = "Float"
    choices: dict[int, int] = Field(default_factory=dict)
    requires: dict[str, bool | float] = Field(default_factory=dict, max_length=32)
    inactive_when: dict[str, Annotated[list[StrictInt], Field(min_length=1, max_length=256)]] = Field(default_factory=dict, max_length=4)
    scenes: dict[Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")], Annotated[StrictInt, Field(ge=0, le=255)]] = Field(default_factory=dict, max_length=256)


class Mapping(Model):
    source: str
    source_format: Literal["prfpset", "ffx"]
    target: Literal["filmcraft", "effectcraft"]
    effect: str
    params: dict[str, Rule]
    evidence: str
    validation: str
    target_commit: str
    limitations: list[Annotated[str, Field(min_length=1, max_length=2048)]] = Field(default_factory=list, max_length=32)
    required_on_create: list[str] = Field(default_factory=list, max_length=256)


class Package(Model):
    format: Literal["craftbridge.mappings"] = "craftbridge.mappings"
    version: Literal[1, 2] = 1
    name: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,80}$")
    mappings: list[Mapping] = Field(max_length=2048)
    plugins: list[PluginManifest] = Field(default_factory=list, max_length=64)


def mapping_dir() -> Path:
    return Path(os.environ.get("CRAFT_BRIDGE_CONFIG", Path.home() / ".config" / "craft-bridge")) / "mappings"


class Registry:
    def __init__(self, packages: list[Path] | None = None):
        self.catalog = json.loads(files("craft_bridge.mappings").joinpath("catalog.json").read_text())
        self.mappings: dict[tuple[str, str, str], Mapping] = {}
        self.plugins: dict[str, PluginManifest] = {}
        builtins = Package.model_validate_json(
            files("craft_bridge.mappings").joinpath("builtin.json").read_text()
        )
        self._add(builtins)
        external = [self.read_package(path) for path in (sorted(mapping_dir().glob("*.json")) if packages is None else packages)]
        # Register shared manifests before resolving maps, independent of filenames.
        for package in external:
            if package.plugins:
                self._add(Package(version=package.version, name=package.name, plugins=package.plugins, mappings=[]))
        for package in external:
            self._add(package)

    def read_package(self, path: Path) -> Package:
        try:
            return Package.model_validate_json(read_bounded(path, Limits(max_file_bytes=2 * 1024 * 1024)))
        except ValidationError as exc:
            raise BridgeError(f"Pacote de mapas inválido: {exc}") from exc

    def _add(self, package: Package) -> None:
        if package.plugins and package.version != 2:
            raise BridgeError("Plugins exigem pacote de mapas v2.")
        next_plugins = self.plugins.copy()
        extensions = {}
        for plugin in package.plugins:
            specs = plugin.specs()
            if plugin.id in extensions:
                raise BridgeError("Plugin duplicado no pacote.")
            if plugin.id in next_plugins:
                if plugin.fingerprint() != next_plugins[plugin.id].fingerprint():
                    raise BridgeError("Manifesto de plugin conflita com pacote instalado.")
            elif plugin.id in self.catalog["effectcraft"]["effects"]:
                raise BridgeError("Plugin não pode substituir efeito do catálogo.")
            extensions[plugin.id] = specs
            next_plugins[plugin.id] = plugin
        if len(next_plugins) > 64:
            raise BridgeError("Catálogo suporta até 64 plugins por processo EffectCraft.")
        next_mappings = self.mappings.copy()
        for mapping in package.mappings:
            if len(set(mapping.required_on_create)) != len(mapping.required_on_create) or any(id not in mapping.params for id in mapping.required_on_create):
                raise BridgeError("Condições de criação exigem IDs únicos presentes no mapa.")
            if mapping.effect in next_plugins and (mapping.target != "effectcraft" or package.version != 2):
                raise BridgeError("Mapas de plugins exigem EffectCraft e pacote v2.")
            defs = extensions.get(mapping.effect) if mapping.target == "effectcraft" else None
            defs = defs if defs is not None else self.catalog[mapping.target]["effects"].get(mapping.effect)
            if defs is None:
                raise BridgeError(f"Efeito fora do catálogo verificado: {mapping.effect}")
            if mapping.target_commit != self.catalog[mapping.target]["commit"]:
                raise BridgeError("Pacote usa uma versão de catálogo não verificada.")
            destinations = set()
            for source_id, rule in mapping.params.items():
                if rule.target not in defs or defs[rule.target]["kind"] != rule.kind:
                    raise BridgeError(f"Parâmetro/tipo fora do catálogo: {rule.target}")
                if rule.target in destinations:
                    raise BridgeError("Dois parâmetros de origem disputam o mesmo destino.")
                destinations.add(rule.target)
                if rule.kind == "Layer" or rule.operation == "explicit_layer_binding":
                    if (mapping.target != "effectcraft" or mapping.source_format != "ffx"
                        or rule.kind != "Layer" or rule.operation != "explicit_layer_binding"
                        or not mapping.evidence.strip() or not mapping.limitations
                        or source_id not in mapping.required_on_create):
                        raise BridgeError("Layer exige vínculo explícito FFX, evidência, perdas e recurso obrigatório na criação.")
                if rule.operation == "enum_map":
                    spec = defs[rule.target]
                    if (
                        rule.kind != "Choice"
                        or not rule.choices
                        or any(not spec["min"] <= v <= spec["max"] for v in rule.choices.values())
                    ):
                        raise BridgeError("Tabela de enum inválida para o parâmetro de destino.")
                elif rule.choices:
                    raise BridgeError("Tabela de enum exige operation=enum_map.")
                if rule.inactive_when:
                    if rule.operation != "explicit_layer_binding":
                        raise BridgeError("Condição de inatividade exige recurso Layer com vínculo explícito.")
                    for selector, values in rule.inactive_when.items():
                        control = mapping.params.get(selector)
                        if (control is None or control.kind != "Choice" or selector not in mapping.required_on_create
                            or control.operation not in ("minus_one", "enum_map") or len(set(values)) != len(values)):
                            raise BridgeError("Inatividade exige seletor Choice obrigatório com tabela comprovada.")
                        spec = defs[control.target]
                        for value in values:
                            translated = value - 1 if control.operation == "minus_one" else control.choices.get(value)
                            if translated is None or not spec["min"] <= translated <= spec["max"]:
                                raise BridgeError("Valor de inatividade fora do menu comprovado.")
                if rule.operation == "ofp_scene_lookup":
                    spec = defs[rule.target]
                    if (mapping.effect not in next_plugins or mapping.target != "effectcraft"
                        or rule.kind != "Choice" or not rule.scenes or not mapping.limitations
                        or len(set(rule.scenes.values())) != len(rule.scenes)
                        or set(rule.scenes.values()) != set(range(len(spec.get("options", []))))):
                        raise BridgeError("Cena OFP exige plugin, menu/hash bijetivo e limites de fidelidade declarados.")
                    from craft_bridge.parsers.ffx.optical_flares import OPTIONS
                    if mapping.params.get(OPTIONS) is not rule or OPTIONS not in mapping.required_on_create:
                        raise BridgeError("Cena OFP deve vincular Options e ser obrigatória na criação.")
                elif rule.scenes:
                    raise BridgeError("Hashes de cenas exigem operation=ofp_scene_lookup.")
            key = (mapping.source_format, mapping.target, mapping.source)
            if key in next_mappings:
                raise BridgeError(f"Mapa duplicado: {mapping.source}")
            next_mappings[key] = mapping
        self.catalog["effectcraft"]["effects"].update(extensions)
        self.plugins, self.mappings = next_plugins, next_mappings

    def find(self, fmt: str, target: str, source: str) -> Mapping | None:
        return self.mappings.get((fmt, target, source))

    def install(self, path: Path) -> Path:
        package = self.read_package(path)
        candidate = object.__new__(Registry)
        candidate.catalog = deepcopy(self.catalog)
        candidate.plugins = self.plugins.copy()
        candidate.mappings = self.mappings.copy()
        candidate._add(package)
        destination = mapping_dir() / (package.name + ".json")
        atomic_write(destination, json_text(package.model_dump(mode="json", exclude_none=True)))
        self.catalog, self.plugins, self.mappings = candidate.catalog, candidate.plugins, candidate.mappings
        return destination
