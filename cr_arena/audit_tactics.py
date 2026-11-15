"""Bounded coordinate sweeps; actual Planner replays validate every selected witness.

The grid is a reproducible search for shortcuts, not an exhaustive proof over continuous
placements or multi-action policies. Screening omits future opponent deployments; witnesses
are always replayed against the real Planner before they can affect a release gate.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from royalegym.protocol import DeployCommand, DeployStatus

from .royale_task import make_referee
from .telemetry import atomic_json


def screen(cfg, card, *, delay=0, step=.5, bounds=(0,18,0,32)):
    if step <= 0 or 18 / step % 1 or 32 / step % 1:
        raise ValueError("step must evenly divide the arena dimensions")
    ref = make_referee(cfg)
    while not ref.over and (ref.tick-ref.start_tick)/20 < delay:
        ref.act_action({"cmd": "wait"})
    if ref.over:
        return dict(card=card, delay=delay, step=step, trials=[])
    g = ref.game
    slot = next(i for i, cid in enumerate(g.state.players[0].hand) if g.card_name(cid) == card)
    cost = g.card_by_id[g.state.players[0].hand[slot]].elixir
    before = cfg["scenario"]["tower_hp"][0]
    state = g.engine.save_state()
    ticks = ref.end_tick - ref.tick
    rows = []
    for ix in range(round(bounds[0]/step),round(bounds[1]/step)):
        for iy in range(round(bounds[2]/step),round(bounds[3]/step)):
            x, y = ix*step, iy*step
            g.engine.load_state(state)
            ex, ey = g.engine_point(0, x, y)
            cmd = DeployCommand(0, slot, ex, ey)
            if g.engine.check_deploy(cmd) != DeployStatus.OK:
                continue
            g.engine.step([cmd], ticks)
            s = g.state
            hp = list(s.players[0].tower_hp)
            damage = sum(max(0, a-b) for a,b in zip(before,hp))
            success = (all(hp[i]>0 for i in (1,2)) and damage <= cfg["scenario"]["damage_limit"]
                       if cfg["scenario"]["grading"] == "one_spell" else s.game_over and s.winner == 0)
            success = bool(success and cost <= cfg["scenario"].get("spend_budget",1000))
            rows.append(dict(x=x,y=y,success=success,damage=damage,own_hp=hp,
                             enemy_hp=list(s.players[1].tower_hp)))
    ref.opponent.close()
    return dict(card=card, delay=delay, step=step, bounds=bounds,
                opponent_followups="omitted screening only",trials=rows)


def main():
    from .tactics import catalog
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--task",required=True)
    ap.add_argument("--card",default="Fireball")
    ap.add_argument("--delay",type=int,default=0)
    ap.add_argument("--step",type=float,default=.5)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    cfg=next(c for c in catalog() if c['id']==args.task)
    result=screen(cfg,args.card,delay=args.delay,step=args.step)
    atomic_json(args.out,result)
    rows=result['trials'];wins=[r for r in rows if r['success']]
    print(json.dumps(dict(task=cfg['id'],count=len(rows),wins=len(wins),best=sorted(rows,key=lambda r:r['damage'])[:3])))


if __name__=='__main__':
    main()
