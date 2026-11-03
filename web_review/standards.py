"""Versioned B2B catalog/order presets; legacy default remains API compatible."""
import json
from schema_match.config import ROOT

PRESETS=('product_catalog_v1','order_lines_v1')

def presets():
    return [json.loads((ROOT/'schemas'/f'{name}.json').read_bytes()) for name in PRESETS]
