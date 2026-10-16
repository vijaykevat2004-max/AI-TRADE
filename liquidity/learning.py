"""Offline one-step contextual Q research. Never changes the active strategy."""
from .kernel import digest

def research(records, minimum_train=100, minimum_test=30):
    # Collapse reruns before splitting. Features must exist at signal discovery.
    unique={r['id']:r for r in records if r.get('status')=='CLOSED' and isinstance(r.get('net_r'),(float,int))}
    rows=sorted(unique.values(),key=lambda r:(r['signal']['earliest_actionable_time'],r['id']))
    split=int(len(rows)*.7);train=rows[:split];test=rows[split:]
    result=dict(method='OFFLINE_ONE_STEP_CONTEXTUAL_Q_TAKE_OR_SKIP',status='INSUFFICIENT_DATA',dataset_hash=digest(rows),unique_closed=len(rows),training=len(train),holdout=len(test),active_policy_changed=False,production_ready=False,limitations=['Not deep reinforcement learning','Revised provider history is not point-in-time certified','No automatic rule promotion'])
    if len(train)<minimum_train or len(test)<minimum_test:return result
    q={};counts={}
    def context(r):
        s=r['signal'];return '|'.join([s['decision'],s.get('confirmation_type','UNKNOWN'),s.get('daily_bias','UNKNOWN')])
    for r in train:
        key=context(r);counts[key]=counts.get(key,0)+1
        q[key]=q.get(key,0)+(r['net_r']-q.get(key,0))/counts[key]
    # Frozen candidate: unseen or sparse contexts abstain. No holdout updates.
    chosen=[r for r in test if counts.get(context(r),0)>=20 and q.get(context(r),0)>0]
    result.update(status='SHADOW_EVALUATED_NOT_APPROVED',q_take=q,context_samples=counts,holdout_baseline_net_r=sum(r['net_r'] for r in test),holdout_candidate_net_r=sum(r['net_r'] for r in chosen),holdout_selected=len(chosen),promotion='BLOCKED_SOURCE_PARITY_AND_INDEPENDENT_VALIDATION')
    return result
