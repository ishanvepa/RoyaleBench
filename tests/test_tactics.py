"""Tactics must use the exact v3 protocol and independently earn coordinate-mode release."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tomllib

import pytest

from cr_arena import tactics
from cr_arena.build_tactics import FOUNDATION, FOUNDATION_PROTOCOL, OUT, build
from cr_arena.build_v1 import MODEL_API_HOSTS
from cr_arena.coordinate_benchmark import (config as v3_config, instruction, package_task,
    packaged_protocol_digest, protocol_digest, RUNTIME)
from cr_arena.coordinate_task import MODE, CoordinateReferee
from cr_arena.royale_task import make_referee, verify
from cr_arena.telemetry import digest
from cr_arena.validate_tactics import card_action, play, problem, reference, validation_digest


@pytest.fixture(scope='module')
def configs():
    return {c['id']:c for c in tactics.catalog()}


def test_frozen_menu_inputs_and_v3_foundation_are_pinned(configs):
    assert len(configs)==8
    assert len(tactics.source_manifest()['runnable_tasks'])==7
    assert FOUNDATION_PROTOCOL==json.loads((FOUNDATION/'manifest.json').read_text())['protocol_sha256']
    for c in configs.values():
        assert c['action_mode']==MODE and c['version']=='2.0.0'
        assert c['foundation_dataset']=='royalebench/royalebench-v3@2'
        assert isinstance(make_referee(c),CoordinateReferee)


def test_free_placement_has_no_numbered_oracle(configs):
    ref=make_referee(configs['01-timed-spell-a'])
    def unavailable(*args):raise AssertionError('coordinate play must not query numbered moves')
    ref.game.legal_moves=unavailable
    text=ref.observation()
    assert 'HAND SLOTS' in text and 'LEGAL MOVES' not in text
    action=card_action(ref,'Fireball',4.25,12.25)
    _,meta=ref.prepare_action(action)
    assert meta['accepted']
    assert ref.game.own_tiles(0,meta['deployment']['x'],meta['deployment']['y'])==(4.25,12.25)
    with pytest.raises(ValueError,match='numbered'):ref.act(1)


def test_illegal_coordinate_is_a_wait_without_snapping(configs,tmp_path):
    cfg=configs['03-tower-race-a']
    ref,idle=make_referee(cfg),make_referee(cfg)
    action=card_action(ref,'Cannon',9,15.5)
    before=ref.tick;entry=ref.entry(action,5.0)
    assert not entry['accepted'] and entry['rejection']=='WATER'
    assert 'rejected' in ref.act_action(action)
    idle.act_action({'cmd':'wait'})
    assert ref.tick==before+40 and digest(ref.game.state)==digest(idle.game.state)
    assert ref.spent==0 and ref.rejected_actions==1


def test_spending_limit_is_checked_after_accepted_play(configs,tmp_path):
    cfg=deepcopy(configs['01-timed-spell-a'])
    cfg['scenario']['spend_budget']=3
    log=tmp_path/'overspend.jsonl'
    ref=play(cfg,log)
    assert ref.spent==4 and ref.outcome()['tower_damage']==0
    entries=[json.loads(line) for line in log.read_text().splitlines()]
    assert any(e['accepted'] and e['action']['cmd']=='play' for e in entries)
    report=verify(cfg,log,None)
    assert report['rewards']['integrity']==report['rewards']['completed']==1
    assert report['rewards']['reward']==0


@pytest.mark.parametrize('variant',['a','b'])
def test_race_requires_different_opening_strategies(configs,tmp_path,variant):
    cfg=configs[f'03-tower-race-{variant}']
    outcomes={}
    for name,card,x,y in [('commit','Fireball',3.5,22),('defend','Cannon',3.5,9.5)]:
        ref=play(cfg,tmp_path/f'{name}.jsonl',lambda r:card_action(r,card,x,y) if r.decision==0 else {'cmd':'wait'})
        outcomes[name]=int(ref.success())
    assert outcomes=={'commit':int(variant=='a'),'defend':int(variant=='b')}


def test_timed_reference_waits_then_casts_and_replays(configs,tmp_path):
    cfg=configs['01-timed-spell-a'];log=tmp_path/'timing.jsonl'
    ref=play(cfg,log)
    assert ref.success() and ref.outcome()['tower_damage']==0
    entries=[json.loads(line) for line in log.read_text().splitlines()]
    assert entries[0]['action']=={'cmd':'wait'} and entries[1]['action']['cmd']=='play'
    assert verify(cfg,log,None)['rewards']['reward']==1


def test_trade_reference_accepts_tower_loss(configs,tmp_path):
    ref=play(configs['04-tower-trade-a'],tmp_path/'trade.jsonl')
    assert ref.success() and ref.game.state.players[0].tower_hp[1]==0
    assert (ref.outcome()['crowns_for'],ref.outcome()['crowns_against'])==(2,1)


@pytest.mark.parametrize('y',[13,6.5])
def test_spending_counter_early_really_clears_opening(configs,y):
    ref=make_referee(configs['02-reserve-counter-a'])
    initial={e.uid for e in ref.game.state.entities if e.team==1 and e.card_id>=0}
    ref.act_action(card_action(ref,'Log',3.5,y))
    assert not any(e.uid in initial and e.hp>0 for e in ref.game.state.entities)
    assert ref.outcome()['tower_damage']==0 and ref.spent==2


def test_old_menu_evidence_cannot_release_coordinates(configs,tmp_path):
    c=configs['03-tower-race-a'];d=tmp_path/c['id'];d.mkdir()
    log=d/'reference.jsonl';log.write_text('fixture\n')
    row=dict(config_sha256=hashlib.sha256(json.dumps(c,sort_keys=True).encode()).hexdigest(),
        protocol_sha256=protocol_digest(),reward=1,integrity=1,deterministic=True,
        negative_rewards=dict(wait=0,empty=0,malformed=0),
        reference_log_sha256=hashlib.sha256(log.read_bytes()).hexdigest(),
        validation_source_sha256=validation_digest())
    assert 'contrast' in problem(c,row,tmp_path).lower()
    row['contrasts']={'rewards':dict(c['validation_requirements'])}
    assert problem(c,row,tmp_path) is None
    row['contrasts']['rewards']['wrong_strategy_screen_wins']=1
    assert problem(c,row,tmp_path) is not None
    row['protocol_sha256']='historical-menu-protocol'
    assert problem(c,row,tmp_path)=='runtime changed'


@pytest.mark.parametrize('protected',[FOUNDATION,tactics.SOURCE])
def test_builder_does_not_overwrite_foundation(protected,tmp_path):
    before=(protected/'manifest.json').read_bytes()
    with pytest.raises(ValueError,match='overwrite'):build(protected,tmp_path)
    assert (protected/'manifest.json').read_bytes()==before


def test_shared_packager_keeps_v3_gameplay_with_current_viewer(tmp_path):
    cfg=v3_config('01-immediate-lethal',title='RoyaleBench v3',version='3.0.0')
    evidence=Path('runs/royalebench-v3')
    package_task(cfg,tmp_path,evidence,Path('data/royalebench-v1-source')/cfg['id'],task_prefix='v3-')
    task=tmp_path/cfg['id']
    # New packages include the current standalone viewer; published packages stay frozen.
    assert packaged_protocol_digest(task)==protocol_digest()
    for source in RUNTIME:
        if source in {'replay.py','replay.html'}:
            continue
        relative=Path('environment/referee')/source
        assert (task/relative).read_bytes()==(FOUNDATION/cfg['id']/relative).read_bytes()
    assert (task/'environment/cr').read_bytes()==(FOUNDATION/cfg['id']/'environment/cr').read_bytes()
    assert (task/'instruction.md').read_bytes()==(FOUNDATION/cfg['id']/'instruction.md').read_bytes()
    assert tomllib.loads((task/'task.toml').read_text())['agent']['allowed_hosts']==list(MODEL_API_HOSTS)


def test_packaged_tactics_match_foundation():
    manifest=json.loads((OUT/'manifest.json').read_text())
    if manifest.get('action_mode')!=MODE:pytest.skip('build the coordinate Tactics release first')
    from rb_evals.benchmarks import load_benchmark,task_problems
    benchmark=load_benchmark(OUT)
    from cr_arena.build_tactics_clips import SOURCE_DIGESTS, TASKS
    assert set(benchmark.tasks)==set(manifest['runnable_tasks'])==set(SOURCE_DIGESTS)|set(TASKS)
    for name,task in benchmark.tasks.items():
        assert not task_problems(task)
        assert packaged_protocol_digest(task.path)==manifest['protocol_sha256']==FOUNDATION_PROTOCOL
        cfg=json.loads((task.path/'tests/task.json').read_text())
        assert cfg==json.loads((task.path/'environment/task.json').read_text())
        assert cfg['action_mode']==MODE
        assert 'cr play SLOT X Y' in task.instruction and 'cr act N' not in task.instruction
        assert task.config['agent']['allowed_hosts']==list(MODEL_API_HOSTS)
        assert task.config['verifier']['environment_mode']=='separate'
        assert task.config['verifier']['network_mode']=='no-network'
