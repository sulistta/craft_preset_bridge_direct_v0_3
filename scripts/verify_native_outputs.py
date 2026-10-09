"""Verificação opt-in de saídas já convertidas contra o harness oficial em localhost."""

import argparse
import json
from pathlib import Path

from craft_bridge.integrations.control import ControlClient
from craft_bridge.integrations.effectcraft import apply_plan, load_plan

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("plan", type=Path)
parser.add_argument("--port", type=int, default=19877)
parser.add_argument("--layer", default="#1")
parser.add_argument("--yes", action="store_true", help="Confirmar mutações no harness de teste")
args = parser.parse_args()
result = apply_plan(load_plan(args.plan), layer=args.layer, port=args.port, confirmed=args.yes)
with ControlClient(args.port) as client:
    properties = []
    plan = load_plan(args.plan)
    for effect in plan.effects:
        prefix = result["bindings"][effect.ref]["path"]
        for prop in effect.properties:
            properties.append(
                client.execute("prop.get", {"layer": args.layer, "path": prefix + "/" + prop.id})
            )
print(json.dumps({"application": result, "properties": properties}, indent=2))
