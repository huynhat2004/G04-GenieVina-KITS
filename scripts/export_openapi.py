"""Export contracts from runtime models; no database or secrets required."""
import json
import sys
from pathlib import Path

import yaml
from openapi_spec_validator import validate

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.main import app


def main():
    schema = app.openapi()
    validate(schema)
    (ROOT/'API/openapi.json').write_text(json.dumps(schema,ensure_ascii=False,indent=2)+'\n')
    orders = dict(schema)
    orders['paths'] = {p:v for p,v in schema['paths'].items() if p.startswith(('/api/orders','/api/ai-results'))}
    orders['info'] = {**schema['info'],'title':'Genie Vina – Orders and AI Results'}
    validate(orders)
    (ROOT/'API/orders.yaml').write_text(yaml.safe_dump(orders,allow_unicode=True,sort_keys=False))
    print('Validated and exported full OpenAPI and Orders/AI contract.')


if __name__=='__main__':
    main()
