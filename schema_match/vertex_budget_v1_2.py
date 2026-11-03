"""Admission-only amendment; frozen v1.1 calls/config/provider stay unchanged."""
import json
from copy import deepcopy
from .config import ROOT
from .vertex_provider_v1 import VertexProvider


def policy():return json.loads((ROOT/'config/gcp_budget_v1_2.json').read_bytes())


def upgrade_check(check):
    value=deepcopy(check);cfg=policy()
    represented=value.get('schema_representation_tokens',value['counted_input_tokens'])
    estimate=max(value['counted_input_tokens'],represented)+cfg['service_framing_reserve_tokens']
    value.update(budget_version=cfg['version'],previous_admission_input_estimate=value.get('admission_input_upper_estimate'),
        service_framing_reserve_tokens=cfg['service_framing_reserve_tokens'],admission_input_upper_estimate=estimate,
        is_exact_generate_prompt_count=False,is_proven_upper_bound=False,
        passed=estimate+value['output_token_reserve']<=value['context_token_limit'])
    if not value['passed']:raise ValueError('Token estimate plus reserve exceeds unchanged model context; no clipping')
    return value


class CurrentVertexProvider(VertexProvider):
    def preflight(self,*args,**kwargs):return upgrade_check(super().preflight(*args,**kwargs))
