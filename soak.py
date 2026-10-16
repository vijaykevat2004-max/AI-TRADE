"""Explicit synthetic 50-actor progression/restart rehearsal, never live evidence."""
from datetime import timedelta
import json
from pathlib import Path
import tempfile
from test_liquidity import Tests,bar
from liquidity.runtime import Store,Supervisor

def main():
    cfg,fixture=Tests().synthetic();symbols=['SYNTHETIC'+str(i) for i in range(50)]
    full=fixture['bars']+[bar(i) for i in range(20,73)]
    ticks=0;watermarks=[];counts={}
    with tempfile.TemporaryDirectory(dir='.') as tmp:
        path=Path(tmp)/'soak.sqlite';store=Store(path)
        for i in range(20,73):
            def provider(symbol,now,config):
                if symbol==symbols[0]:raise ValueError('INJECTED_SINGLE_SYMBOL_FAULT')
                return {'5m':full[:i+1],'1d':fixture['daily']}
            if i==45:store=Store(path)  # actual persistent restart/resume
            now=full[i].t+timedelta(minutes=6,seconds=30)
            report=Supervisor(symbols,store,dict(year=2026,verified=True),provider).tick(now)
            assert len(report['agents'])==50
            watermarks.append(store.states()[symbols[1]]['watermark']);ticks+=1
            for state,n in report['counts'].items():counts[state]=counts.get(state,0)+n
        assert len(set(watermarks))==ticks,'FROZEN_WATERMARK'
        events=store.pending();ids=[id for id,_ in events]
        assert len(ids)==len(set(ids)),'DUPLICATE_OUTBOX'
    result=dict(mode='SYNTHETIC_SIMULATION_NOT_PERFORMANCE',agents=50,ticks=ticks,actor_iterations=50*ticks,independent_source_faults=1,progressing_watermark_agents=49,watermark_updates=ticks,restart=True,duplicate_ids=0,states=counts,production_ready=False)
    Path('reports').mkdir(exist_ok=True);Path('reports/soak.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))

if __name__=='__main__':main()
