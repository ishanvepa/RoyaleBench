"""Validate Tactics through the shared v3 coordinate referee and independent verifier."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from functools import partial
import hashlib
import json
from pathlib import Path

from .audit_tactics import screen
from .bots.planner import Planner
from .coordinate_benchmark import calibration_problem, protocol_digest
from .royale_task import make_referee, verify
from .tactics import SOURCE, TITLE, VERSION, catalog, source_manifest
from .telemetry import atomic_json

OUT = Path('runs/tactics-coordinates')


def validation_digest():
    return hashlib.sha256(b''.join(Path(__file__).with_name(n).read_bytes().replace(b'\r\n',b'\n')
        for n in ('validate_tactics.py','audit_tactics.py'))).hexdigest()


def card_action(ref, card, x, y):
    slot = next(i for i,cid in enumerate(ref.game.state.players[0].hand) if ref.game.card_name(cid)==card)
    return dict(cmd='play',slot=slot,x=x,y=y)


def reference(ref):
    family, variant = ref.cfg['family'], ref.cfg['id'][-1]
    elapsed=(ref.tick-ref.start_tick)/20
    if family == 1:
        if elapsed >= 2 and not ref.plays:
            e=next(e for e in ref.game.state.entities if e.team==1 and ref.game.card_name(e.card_id)=='Giant')
            return card_action(ref,'Fireball',*ref.game.own_tiles(0,e.x,e.y))
    elif family == 2:
        lane=3.5 if variant=='a' else 14.5
        if ref.decision==0:return card_action(ref,'IceGolemite',9,10.5)
        if ref.decision==1:return card_action(ref,'IceSpirits',lane,10.5)
        if elapsed>=8 and not any(p['card']=='Log' for p in ref.plays):return card_action(ref,'Log',lane,3.5)
    elif family == 3 and ref.decision==0:
        return card_action(ref,'Fireball',3.5,25.5) if variant=='a' else card_action(ref,'Cannon',3.5,9.5)
    elif family == 4 and ref.decision==0:
        return card_action(ref,'Fireball',14.5 if variant=='a' else 3.5,25.5)
    return {'cmd':'wait'}


def play(cfg, path, chooser=reference):
    ref=make_referee(cfg);entries=[]
    try:
        while not ref.over:
            action=chooser(ref)
            entries.append(ref.entry(action,5.0))
            ref.act_action(action)
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(''.join(json.dumps(e)+'\n' for e in entries),encoding='utf-8',newline='\n')
        return ref
    finally:
        ref.opponent.close()


def attempt(cfg,out,name,chooser):
    path=out/cfg['id']/'contrasts'/f'{name}.jsonl'
    ref=play(cfg,path,chooser);report=verify(cfg,path,None)
    if report['rewards']['integrity'] != 1:raise RuntimeError(f'Contrast integrity failed: {name}')
    row=dict(name=name,reward=report['rewards']['reward'],integrity=1,outcome=report['outcome'],
             own_hp=list(ref.game.state.players[0].tower_hp))
    print(json.dumps(dict(task=cfg['id'],contrast=name,reward=row['reward'],damage=row['outcome']['tower_damage'])),flush=True)
    return row


def sweep(cfg,out,card,delay,name,bounds=(0,18,0,32)):
    result=screen(cfg,card,delay=delay,step=.5,bounds=bounds)
    atomic_json(out/cfg['id']/'screens'/f'{name}.json',result)
    # Select distinct best candidates, then validate them with the real adaptive opponent.
    rows=sorted(result['trials'],key=lambda r:(not r['success'],r['damage']))
    trials=[]
    for i,point in enumerate(rows[:4]):
        def choose(ref):
            return card_action(ref,card,point['x'],point['y']) if (ref.tick-ref.start_tick)/20>=delay and not ref.plays else {'cmd':'wait'}
        trials.append(attempt(cfg,out,f'{name}-{i}',choose))
    return dict(card=card,delay=delay,step=.5,tested_points=len(rows),
                screening_wins=sum(r['success'] for r in rows),
                witnesses=trials,scope='one play on a half-tile grid; screening omits future opponent deployments')


def contrasts(cfg,out):
    family,variant=cfg['family'],cfg['id'][-1]
    rows=[];rewards={};screens=[]
    if family==1:
        for name,delay in [('immediate_best',0),('late_best',4)]:
            s=sweep(cfg,out,'Fireball',delay,name);screens.append(s)
            rewards[name]=max(t['reward'] for t in s['witnesses'])
            rewards['screen_'+name]=s['screening_wins']
    elif family==2:
        lane=3.5 if variant=='a' else 14.5
        def opening(ref):
            return card_action(ref,'Log',lane,13)
        def musketeer(ref):
            if ref.decision==0:return opening(ref)
            if (ref.tick-ref.start_tick)/20>=4 and not any(p['card']=='Musketeer' for p in ref.plays):return card_action(ref,'Musketeer',lane,10.5)
            return {'cmd':'wait'}
        rows.append(attempt(cfg,out,'spend_then_musketeer',musketeer))
        planner=None
        try:
            def recover(ref):
                nonlocal planner
                if ref.decision==0:return opening(ref)
                if planner is None:planner=Planner(ref.game.decks,cfg['seed'],0,**cfg['planner'])
                state=ref.game.engine.save_state();planner.e.load_state(state)
                budget=cfg['scenario']['spend_budget']-ref.spent
                p=planner.g.state.players[0]
                plays=[a for a in planner.candidates(0) if planner.g.card_by_id[p.hand[a[1]]].elixir<=budget]
                choice,_=planner.act(state,plays)
                if choice is None:return {'cmd':'wait'}
                _,slot,x,y=choice;x,y=ref.game.own_tiles(0,x,y)
                return dict(cmd='play',slot=slot,x=x,y=y)
            rows.append(attempt(cfg,out,'spend_then_recover',recover))
        finally:
            if planner:planner.close()
    elif family in (3,4):
        lane=3.5 if family==3 or variant=='b' else 14.5
        for name,card,x,y in [('commit','Fireball',lane,25.5),
             ('defend' if family==3 else 'save_tower','Cannon',14.5 if family==4 and variant=='b' else 3.5,9.5)]:
            rows.append(attempt(cfg,out,name,lambda r,c=card,x=x,y=y:card_action(r,c,x,y) if r.decision==0 else {'cmd':'wait'}))
        if family==3:
            choices = [('Fireball',(0,18,0,17)),('Minions',(0,18,0,32)),
                       ('Knight',(0,18,0,32)),('Cannon',(0,18,0,32))] if variant=='a' else [('Fireball',(0,18,17,32))]
            for card,bounds in choices:
                s=sweep(cfg,out,card,0,'wrong-strategy-'+card,bounds);screens.append(s)
            rewards['wrong_strategy_screen_wins']=sum(s['screening_wins'] for s in screens)
            rewards['wrong_strategy_witness_best']=max(t['reward'] for s in screens for t in s['witnesses'])
        else:
            before=cfg['scenario']['tower_hp'][0]
            rewards['reference_loses_princess']=int(rows[0]['reward']==1 and any(before[i]>0 and rows[0]['own_hp'][i]==0 for i in (1,2)))
            s=sweep(cfg,out,'Cannon',0,'defensive-cannon');screens.append(s)
            rewards['defensive_cannon_screen_wins']=s['screening_wins']
            rewards['defensive_cannon_best']=max(t['reward'] for t in s['witnesses'])
    rewards.update((r['name'],r['reward']) for r in rows)
    return dict(trials=rows,screens=screens,rewards=rewards)


def problem(cfg,row,evidence):
    if not row:return 'Coordinate calibration has not run.'
    p=calibration_problem(cfg,row,evidence/cfg['id']/'reference.jsonl')
    if p:return p
    if row.get('validation_source_sha256')!=validation_digest():return 'Validation implementation changed.'
    for key,value in cfg['validation_requirements'].items():
        if row.get('contrasts',{}).get('rewards',{}).get(key)!=value:return f'Coordinate contrast {key} failed or is missing.'
    return None


def validate(cfg,out,reuse=False):
    path=out/cfg['id']/'validation.json'
    if reuse and path.exists():
        row=json.loads(path.read_text())
        if problem(cfg,row,out) is None:
            report=verify(cfg,out/cfg['id']/'reference.jsonl',None)
            if report['outcome']==row['reference_outcome'] and report['rewards']['reward']==1:return row
    ref=play(cfg,out/cfg['id']/'reference.jsonl')
    a=verify(cfg,out/cfg['id']/'reference.jsonl',None);b=verify(cfg,out/cfg['id']/'reference.jsonl',None)
    negative={}
    play(cfg,out/cfg['id']/'wait.jsonl',lambda r:{'cmd':'wait'})
    for name,content in [('empty',''),('malformed','not json\n')]:
        p=out/cfg['id']/f'{name}.jsonl';p.write_text(content)
    for name in ['wait','empty','malformed']:
        negative[name]=verify(cfg,out/cfg['id']/f'{name}.jsonl',None)['rewards']['reward']
    row=dict(task=cfg['id'],reward=a['rewards']['reward'],integrity=a['rewards']['integrity'],
        deterministic=a==b,negative_rewards=negative,reference_outcome=ref.outcome(),
        config_sha256=hashlib.sha256(json.dumps(cfg,sort_keys=True).encode()).hexdigest(),
        protocol_sha256=protocol_digest(),validation_source_sha256=validation_digest(),
        reference_log_sha256=hashlib.sha256((out/cfg['id']/'reference.jsonl').read_bytes()).hexdigest())
    atomic_json(path,row)
    if row['reward']==1 and row['integrity']==1 and row['deterministic'] and not any(negative.values()):
        row['contrasts']=contrasts(cfg,out);atomic_json(path,row)
    print(json.dumps(dict(task=cfg['id'],release_problem=problem(cfg,row,out))),flush=True)
    return row


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--tasks',type=int,nargs='*')
    ap.add_argument('--out',type=Path,default=OUT)
    ap.add_argument('--jobs',type=int,choices=range(1,5),default=1)
    ap.add_argument('--reuse',action='store_true')
    args=ap.parse_args()
    names=set(source_manifest()['runnable_tasks'])
    configs=[c for c in catalog() if c['id'] in names and (not args.tasks or c['family'] in args.tasks)]
    worker=partial(validate,out=args.out,reuse=args.reuse)
    if args.jobs==1:rows=[worker(c) for c in configs]
    else:
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:rows=list(pool.map(worker,configs))
    atomic_json(args.out/'validation.json',dict(benchmark=TITLE,version=VERSION,protocol_sha256=protocol_digest(),tasks=rows))


if __name__=='__main__':main()
