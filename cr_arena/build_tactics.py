"""Package calibrated Tactics using exactly the RoyaleBench v3 coordinate runtime."""
from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import shutil
import tempfile

from .coordinate_benchmark import package_task, packaged_protocol_digest, protocol_digest
from .royale_task import verify
from .tactics import SOURCE, TITLE, VERSION, catalog, source_manifest
from .telemetry import VERSION as CAPTURE_VERSION, atomic_json
from .validate_tactics import OUT as EVIDENCE, problem

OUT=Path('benchmarks/royalebench-tactics')
FOUNDATION=Path(__file__).resolve().parents[1]/'benchmarks/royalebench-v3'
# Pin the published foundation, not whichever v3 snapshot a future checkout contains.
FOUNDATION_PROTOCOL='0a08b4c4dfca848149bae22c9ec898848ae116df469984a5978a34219b8c506c'


def build(out=OUT,evidence=EVIDENCE):
    out,evidence=Path(out).resolve(),Path(evidence).resolve()
    for protected in (SOURCE.resolve(),FOUNDATION.resolve(),FOUNDATION.with_name('royalebench-v1').resolve(),FOUNDATION.with_name('royalebench-coordinates').resolve()):
        if out==protected or protected in out.parents:raise ValueError('Cannot overwrite a frozen or foundation dataset')
    if out.is_symlink():raise ValueError('Cannot replace a symlink')
    if out.exists() and not (out/'manifest.json').is_file():raise ValueError('Refusing to replace an unrecognized dataset directory')
    if out.exists() and json.loads((out/'manifest.json').read_text()).get('version') != VERSION:
        raise ValueError('Use cr_arena.build_tactics_hog to preserve the expanded Tactics dataset; use a separate --out for historical regeneration')
    foundation=json.loads((FOUNDATION/'manifest.json').read_text())
    runtime=protocol_digest()
    if runtime!=FOUNDATION_PROTOCOL or runtime!=foundation['protocol_sha256'] or runtime!=packaged_protocol_digest(FOUNDATION/foundation['runnable_tasks'][0]):
        raise ValueError('Current coordinate runtime differs from the pinned v3 foundation')
    for name,pinned in foundation['dependencies'].items():
        if version(name)!=pinned:raise ValueError(f'{name} must be {pinned}')
    eligible=set(source_manifest()['runnable_tasks'])
    rows=[];passed=[]
    for cfg in catalog():
        path=evidence/cfg['id']/'validation.json'
        row=json.loads(path.read_text()) if path.exists() else None
        reason=problem(cfg,row,evidence) if cfg['id'] in eligible else 'Historical candidate; no coordinate reference and contrasts validated.'
        if not reason:
            report=verify(cfg,evidence/cfg['id']/'reference.jsonl',None)
            if report['rewards']['reward']!=1 or report['outcome']!=row['reference_outcome']:
                raise ValueError(f"Reference changed during packaging: {cfg['id']}")
            passed.append(cfg)
        rows.append(dict(id=cfg['id'],family=cfg['family'],status='gated' if reason else 'local-validated',reason=reason,validation=row))
    if sum(c['family']==3 for c in passed)==1:
        passed=[c for c in passed if c['family']!=3]
        for row in rows:
            if row['family']==3:row.update(status='gated',reason='Both members of the strategic race pair must pass.')
    manifest=dict(benchmark=TITLE,version=VERSION,action_mode='coordinates-v1',foundation_dataset='royalebench/royalebench-v3@2',
        protocol_sha256=runtime,capture_schema_version=CAPTURE_VERSION,source_dataset='royalebench/royalebench-tactics@2',
        dependencies={p:version(p) for p in ('royalegym','royalesim','msgspec')},
        runnable_tasks=[c['id'] for c in passed],tasks=rows,
        aggregation='Primary: equally weighted mean of family means. Report the default flat task mean separately.',
        status='Coordinate reference and bounded contrast validation; model pilots reported separately.')
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.tactics-build-',dir=out.parent) as temp:
        stage=Path(temp)/out.name;stage.mkdir()
        for cfg in passed:
            package_task(cfg,stage,evidence,SOURCE/cfg['id'],task_prefix='tactics-',strip_trailing_whitespace=True)
            if packaged_protocol_digest(stage/cfg['id'])!=runtime:raise ValueError('Packaged runtime changed')
        for cfg in catalog():
            if cfg['id'] not in manifest['runnable_tasks']:atomic_json(stage/'candidates'/f"{cfg['id']}.json",cfg)
        atomic_json(stage/'manifest.json',manifest)
        (stage/'benchmark.toml').write_text('[benchmark]\ntitle = "RoyaleBench Tactics"\nkind = "eval"\ndescription = "Strategic variations on the RoyaleBench v3 coordinate foundation. Binary objectives, direct placement, post-play budgets and replay grading."\n')
        (stage/'README.md').write_text(f'# {TITLE}\n\n{len(passed)} coordinate-action scenarios on the RoyaleBench v3 foundation.\nSee [the guide](../../docs/tactics.md) for validation and historical menu results.\nRegenerate with `python -m cr_arena.build_tactics`.\n')
        if protocol_digest()!=runtime:raise ValueError('Runtime changed during build')
        previous=Path(temp)/'previous'
        if out.exists():os.replace(out,previous)
        try:os.replace(stage,out)
        except BaseException:
            if previous.exists():os.replace(previous,out)
            raise
    print(f'Built {len(passed)} coordinate Tactics tasks; {len(rows)-len(passed)} gated.')
    return manifest


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,default=OUT)
    ap.add_argument('--evidence',type=Path,default=EVIDENCE)
    args=ap.parse_args();build(args.out,args.evidence)


if __name__=='__main__':main()
