"""UI dispatch, preserving the frozen Qwen comparison implementation."""
from . import comparison as legacy
from . import comparison_vertex_v1 as vertex
pending_retry_count=legacy.pending_retry_count


def prepare_comparison(data,targets,settings,source_ids):
    return (vertex if settings.provider=='vertex' else legacy).prepare_comparison(data,targets,settings,source_ids)


def execute_comparison(plan,settings,*args,**kwargs):
    return (vertex if settings.provider=='vertex' else legacy).execute_comparison(plan,settings,*args,**kwargs)
