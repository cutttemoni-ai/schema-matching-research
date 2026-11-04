"""Append usage without importing authoring validator or traversing holdout data."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from synthetic_campaign import DATA,ART,ROOT,read,write,journal,git_head
from infra.remote_executor_v3 import locked


def record(phase):
    path=DATA/'usage/history.json'
    with locked(DATA/'usage/history.lock'):
        history=read(path);eid='synthetic-b2b-v1-'+phase
        if any(e.get('event_id')==eid for e in history['events']):return
        evaluation=phase=='evaluation'
        if evaluation and not (ART/'evaluation-predictions-seal.json').exists():raise ValueError('Predictions not sealed')
        ids=[f'{"E" if evaluation else "D"}{i:02d}_{kind}' for i in (range(9,13) if evaluation else range(1,9)) for kind in ('products','orders')]
        history['events'].append(dict(event_id=eid,recorded_at_utc=journal.now_iso(),actor='Codex B2B campaign',
            purpose='frozen_predictions_then_separate_scoring' if evaluation else 'development_comparison_and_one_general_revision',
            task_ids=ids,access='truth_after_predictions',used_for_engine_improvement=not evaluation,
            commit=git_head(),prior_dataset_authoring_exposure=True))
        write(path,history)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['development','evaluation']);record(p.parse_args().phase)
