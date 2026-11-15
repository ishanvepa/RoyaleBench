"""The new Tactics task must require a real zero-damage defense and retain @3 bytes."""
import json
from pathlib import Path

import pytest
from valkyrie.sdk.task_content import task_digest

from cr_arena.build_tactics import build as historical_build, OUT
from cr_arena.build_tactics_hog import config, instruction, play, SOURCE_DIGESTS, TASK
from cr_arena.royale_task import verify


@pytest.mark.parametrize("name,actions,expected", [
    ("reference", {1: dict(cmd="play",slot=0,x=1.5,y=11.5),
                   2: dict(cmd="play",slot=1,x=3.5,y=13.5)}, 1),
    ("wait", {}, 0),
    ("lower", {1: dict(cmd="play",slot=0,x=1.5,y=11.5),
               2: dict(cmd="play",slot=1,x=3.5,y=12.5)}, 0),
])
def test_hog_reference_and_placement_contrast(tmp_path,name,actions,expected):
    cfg=config(); path=tmp_path/f"{name}.jsonl"
    outcome=play(cfg,path,actions)
    first,second=verify(cfg,path,None),verify(cfg,path,None)
    assert first==second
    assert first['rewards']['reward']==expected
    assert first['rewards']['integrity']==1
    assert not outcome['opponent_plays']
    if expected:
        assert outcome['spent_elixir']==3 and outcome['tower_damage']==0
    else:
        assert outcome['tower_damage']>0
        assert outcome['crowns_against']==1


def test_hog_starts_with_only_full_health_enemy_and_explains_interval():
    cfg=config(); text=instruction(cfg)
    assert cfg['scenario']['units']==[dict(card='HogRider',team=1,x=2.5,y=18.5)]
    assert cfg['scenario']['spend_budget']==3 and cfg['scenario']['damage_limit']==0
    assert cfg['scenario']['protect_slots']==[0,1,2]
    assert cfg['scenario']['elixir']==3
    assert cfg['scenario']['tower_hp'][0]==[4824,1,3052]
    assert cfg['version']=='2.2.0'
    assert cfg['decision_ticks']==10
    assert '0.5 seconds' in text and '1697 HP' in text and 'eight decisions' in text
    assert '1.5, 11.5' not in text  # Reference defense is never disclosed.
    assert 'left princess 1' in text and 'There is no valid extra-elixir rescue' in text


def test_source_tasks_are_byte_identical_to_published_revision():
    for task,expected in SOURCE_DIGESTS.items():
        assert task_digest(OUT/task)==expected
    assert json.loads((OUT/'manifest.json').read_text())['task_count']==10


def test_historical_builder_cannot_remove_new_task(tmp_path):
    with pytest.raises(ValueError,match='build_tactics_hog'):
        historical_build(OUT,tmp_path)


@pytest.mark.parametrize('content',['','garbage\n','{"action": []}\n'])
def test_bad_logs_never_pass(tmp_path,content):
    path=tmp_path/'actions.jsonl'; path.write_text(content)
    assert verify(config(),path,None)['rewards']['reward']==0
