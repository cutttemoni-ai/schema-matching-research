"""One-time version separation; preserve frozen legacy comparison bytes."""
from pathlib import Path
import ast,sys
root=Path(__file__).resolve().parents[1]
if (root/'schema_match/comparison_vertex_v1.py').exists():raise RuntimeError('One-time separation already completed; do not overwrite either version')
p=root/'schema_match/comparison.py'
text=p.read_text(encoding='utf-8');tree=ast.parse(text)
imports=text[:text.index('METHODS=')]
body='\n\n'.join(ast.get_source_segment(text,n) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('prepare_comparison','execute_comparison'))
out=imports+'from .comparison import summarize_method\n\n'+body
out=out.replace("'comparison-v0'","'vertex-service-comparison-v1'")
(root/'schema_match/comparison_vertex_v1.py').write_text(out+'\n',encoding='utf-8')
p.write_bytes((root/'research-artifacts/gcp-v1/prior-smoke/schema_match/comparison.py').read_bytes())
t=root/'tests/test_ui.py'
t.write_text(t.read_text(encoding='utf-8').replace('schema_match.matching.run_match','schema_match.provider_routing.run_match'),encoding='utf-8')
print('Frozen legacy comparison restored byte-for-byte; Vertex service comparison isolated.')
