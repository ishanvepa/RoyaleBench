# Frozen Tactics menu inputs

Historical `royalebench/royalebench-tactics@2` inputs, preserved before the coordinate migration
from local snapshot commit `c244a82`. Each `config.json` is the raw scenario specification;
released tasks additionally retain their task template, pinned Dockerfile, verifier configuration
and protected reference. The gated counter candidate retains its unsuccessful reference separately.

`runtime/` is the common frozen menu runtime and client. `source/` records the menu-era task
generator, calibration, opening audit and guide. `manifest.json` pins input file checksums.
Coordinate Tactics reads these only for provenance/templates; none of these directories or
reference policies is installed in the player environment. Current coordinate runtime files are
supplied by the shared RoyaleBench v3 packager.
