# RoyaleBench v4: Cycle while defending (two-hit lethal)

## Objective and score

Win before your tower falls and before overtime ends in 18 seconds. The full draw order is disclosed below; Fireball enters your hand after two card plays.

Reward is 1 only for a completed, independently replayed sequence meeting the objective; otherwise 0.
A chat response alone does not complete the task. Damage means additional damage to all your crown
towers after the starting state. Spending includes all accepted plays, even as elixir regenerates.
Spending and lane budgets are checked by the verifier; overspending is possible and fails the objective.
Any stated card restriction or maximum decision count still applies.

## Play

Run `cr` to inspect the board and zero-based hand slots (0, 1, 2, 3).
Run `cr play SLOT X Y` to deploy that slot at tile coordinates, or `cr wait` to wait.
For command shape only: `cr play 0 8.5 10.5`. Choose your own card and position.
Coordinates use your perspective: 0 <= x < 18, 0 <= y < 32. They are rounded only to engine
subtile precision, never snapped to a nearby legal placement. There is no numbered action menu.
Malformed commands do not advance time. A well-formed illegal play (bad slot, empty slot,
unaffordable card, illegal location, or unavailable card) consumes one interval as a wait and
reports its rejection. Accepted commands and rejected attempts are replayed by the verifier.
Both players choose from the same frozen state. Each interval advances up to 2 seconds; thinking
does not advance time. Continue until `GAME OVER`. Submit each decision yourself; do not write
programs, scripts, or loops to choose or submit moves. Missing or partial play scores zero.
After the task's maximum decision count, or its single allowed spell, the referee resolves waits.

Planner is unchanged: deterministic 10-second, three-ply search, top 4 candidates, 3 answers,
margin 40, elixir value 150 HP, quiet-score prefilter, no worker processes. It generates its own
coordinate candidates and sees the true engine state, including your hand and elixir. You see
your own hand/elixir, the board, visible events, and next card. Its deck is disclosed below;
its hand, queue and elixir remain hidden unless inferable from history.

## Fixed starting state

Engine: RoyaleGym 0.1.28 / RoyaleSim 0.1.48, standard level 11 cards and towers, no evolutions.
Seed 108, blue seat, zero command delay. Time remaining: 18 seconds in
overtime; elixir multiplier x3.
The scoring window is at most 18 seconds and ends earlier if the match ends.
Your starting hand: IceSpirits, Skeletons, IceGolemite, Log. Starting elixir: 6.
`cr` provides exact tower HP, current unit HP/positions, visible events, and your hand.

Your exact draw queue after the starting four cards: Cannon, Fireball, HogRider, Musketeer.

A Fireball deals 159 crown-tower damage in this simulator (verified at build time).

Coordinates are in tiles from your perspective: x 0-18 from left to right, y 0-32 from your back
edge to the enemy's. The river is near y 15-16; your princess towers are near (3.5, 6.5) and
(14.5, 6.5), the enemy's near y 25.5. 

## Match rules

Princess tower destroyed = one crown; king destroyed = instant win. A regulation crown lead wins
when regulation ends. Tied crowns enter overtime, where the next destroyed tower wins.
At the final overtime deadline a crown tie is broken by total remaining crown-tower HP, then seed
parity. For fixed defense windows the stated survival/damage objective determines the score.
Elixir regenerates (maximum 10), faster in the final minute and overtime. Played cards return to the
back of the eight-card queue; a hand slot refills after the engine's normal refill delay.

## Decks

Your deck: hog-2.6-cycle (average 2.62 elixir).
- HogRider: 4 elixir, troop, 1697 hp each
- Musketeer: 4 elixir, troop, 721 hp each
- Cannon: 3 elixir, building, 824 hp each
- IceGolemite: 2 elixir, troop, 1228 hp each
- IceSpirits: 1 elixir, troop, 215 hp each
- Skeletons: 1 elixir, troop x3, 81 hp each
- Fireball: 4 elixir, spell
- Log: 2 elixir, spell

Opponent deck: giant-beatdown (average 3.38 elixir).
- Giant: 5 elixir, troop, 3968 hp each
- Musketeer: 4 elixir, troop, 721 hp each
- Knight: 3 elixir, troop, 1766 hp each
- Archer: 3 elixir, troop x2, 304 hp each
- Minions: 3 elixir, troop x3, 230 hp each, flying
- Cannon: 3 elixir, building, 824 hp each
- Fireball: 4 elixir, spell
- Zap: 2 elixir, spell
