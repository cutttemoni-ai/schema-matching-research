"""Execution-only v2: stop propagation of an uncertain remote API operation."""
def serial_attempts(jobs,invoke,persist,max_calls):
    count=0
    for job in jobs:
        if count>=max_calls:break
        result=invoke(job)
        persist(job,result)
        count+=1
        if result.get('status')=='failed' and result.get('failure_phase')=='api':
            return {'attempts':count,'stopped_remote_uncertainty':True}
    return {'attempts':count,'stopped_remote_uncertainty':False}
