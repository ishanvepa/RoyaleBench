# RoyaleBench Tactics: One-hit Hog defense: three elixir to survive

## Objective and score

Your left princess tower has 1 HP: a single Hog hit destroys it and fails the task. You start with 3 elixir and may spend only 3 in total. Keep all three crown towers alive for 16 seconds, take zero additional total crown-tower damage, and spend at most 3 elixir. You may submit up to 8 decisions; the referee then resolves the remaining time as waits.

Reward is 1 only for a completed, independently replayed sequence meeting every requirement;
otherwise 0. Damage includes all your crown towers. Spending includes all accepted card plays
after the starting state, even when elixir regenerates. Affordable overspending is allowed by the
engine and fails the objective. A chat response alone does not complete the task.

## Play

Run `cr` to inspect the board and zero-based hand slots. Run `cr play SLOT X Y` to deploy a card,
or `cr wait` to wait. Command shape only: `cr play 0 8.5 10.5`; choose your own card and position.
Each decision advances **0.5 seconds** of simulated time. Thinking does not advance the clock.
After eight decisions, the referee automatically resolves waits through the end of the window.
Continue until `GAME OVER`. Make each decision yourself; do not write programs, scripts, or loops
to choose or submit moves. Missing or partial play scores zero.

Coordinates use your perspective: 0 <= x < 18, 0 <= y < 32. They are rounded only to engine subtile
precision, with no placement snapping. Malformed syntax does not advance time. A well-formed
illegal action (invalid slot, unaffordable card, or illegal location) consumes one interval as a
wait and reports its rejection. Accepted and rejected attempts are independently replayed.

## Fixed starting state

Engine: RoyaleGym 0.1.28 / RoyaleSim 0.1.48, standard level 11 cards and towers, no evolutions.
Seed 1, blue seat, zero additional command delay. Card deployment timers still apply.
There are 170 seconds left in regulation, normal x1 elixir regeneration, and a 16-second scoring
window. You start with **exactly 3 elixir, and only 3 may be spent over the entire defense**.
The engine's normal elixir bar still regenerates, but spending any of that beyond your three-elixir
allowance fails the task, even if the engine accepts the play. There is no valid extra-elixir rescue.
Your crown towers have HP: king 4824, **left princess 1**, right princess 3052.
One Hog hit destroys your left princess tower and fails the task. The opponent's towers have HP:
king 4824, left princess 3052, right princess 3052. All towers are alive, with zero crowns on both sides.

The only troop on the starting board is an enemy **full-health HogRider (1697 HP) at (2.5, 18.5)**,
already active and approaching your left bridge. You have no troops or buildings deployed.
Your princess towers are centered at (3.5, 6.5) and (14.5, 6.5); the river is around y=15–17.
`cr` reports exact current unit positions, HP, tower HP, elixir, hand slots, and next card.

Starting hand, in slot order: IceGolemite, Skeletons, HogRider, Musketeer.
Your exact subsequent draw queue: Cannon, Fireball, Log, IceSpirits.
Deck: IceGolemite (Ice Golem, 2), Skeletons (1), HogRider (4), Musketeer (4), Cannon (3),
Fireball (4), Log (2), IceSpirits (Ice Spirit, 1). Played cards return to the back of the queue;
slots refill after the engine's normal delay. Elixir regenerates to a maximum of 10.

There are **no additional enemy deployments during the scoring window**. The fixed opponent is
the existing deterministic Planner (10-second horizon, three plies, top 4, 3 answers, margin 40,
elixir value 150 HP, quiet-score prefilter, workers=0), with privileged engine information.
It starts with zero elixir and a deck whose cheapest cards cost six, so it cannot afford a play
within 16 seconds at x1 regeneration. Its disclosed deck is Golem, ThreeMusketeers, Pekka, MegaKnight, LavaHound, Rocket, Lightning, RoyalRecruits.

Princess towers destroyed award one crown; losing the king ends the match. For this task, survival,
zero additional crown-tower damage, and the spending limit determine success after the full window.
