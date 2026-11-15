# RoyaleBench v7: Convert a supported-tank defense into a crown

## Objective and score

Win the actual match by destroying an enemy crown tower within the next 36 seconds. The position starts with 60 seconds of overtime remaining. The scoring window ends before the overtime HP tiebreak: survival, an HP lead, and an unfinished match receive zero credit.

Reward is 1 only for a completed, independently replayed sequence meeting the objective; otherwise 0.
A chat response alone does not complete the task. The sole gameplay success condition is an actual match win (engine winner BLUE).
There are no spending, lane, damage, card, or decision-count objectives. An HP lead only counts
if it produces a completed match win. This scoring window ends before the overtime deadline; the HP/seed tiebreak cannot award success here.

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

Planner is unchanged: deterministic 10-second, three-ply search, top 4 candidates, 3 answers,
margin 40, elixir value 150 HP, quiet-score prefilter, no worker processes. It generates its own
coordinate candidates and sees the true engine state, including your hand and elixir. You see
your own hand/elixir, the board, visible events, and next card. Its deck is disclosed below;
its hand, queue and elixir remain hidden unless inferable from history.

Simulator crown damage per cast (measured in the pinned engine): Log: 35 HP; Rocket: 342 HP. Spell travel and effect delays still apply.

## Fixed starting state

Engine: RoyaleGym 0.1.28 / RoyaleSim 0.1.48, standard level 11 cards and towers, no evolutions.
Seed 1703, blue seat, zero command delay. Time remaining: 60 seconds in
overtime; elixir multiplier x3.
The scoring window is at most 36 seconds and ends earlier if the match ends.
Your starting hand: InfernoTower, Knight, GoblinGang, Log. Starting elixir: 10.
`cr` provides exact tower HP, current unit HP/positions, visible events, and your hand.

Your exact draw queue after the starting four cards: Rocket, Princess, IceSpirits, GoblinBarrel.

Coordinates are in tiles from your perspective: x 0-18 from left to right, y 0-32 from your back
edge to the enemy's. The river is near y 15-16; your princess towers are near (3.5, 6.5) and
(14.5, 6.5), the enemy's near y 25.5. 

## Match rules

Princess tower destroyed = one crown; king destroyed = instant win. A regulation crown lead wins
when regulation ends. Tied crowns enter overtime, where the next destroyed tower wins.
At the final overtime deadline a crown tie is broken by total remaining crown-tower HP, then seed
parity. 
Elixir regenerates (maximum 10), faster in the final minute and overtime. Played cards return to the
back of the eight-card queue; a hand slot refills after the engine's normal refill delay.

## Decks

Your deck: log-bait (average 3.25 elixir).
- GoblinBarrel: 3 elixir, spell
- Princess: 3 elixir, troop, 261 hp each
- GoblinGang: 3 elixir, troop x3, 202 hp each
- Knight: 3 elixir, troop, 1766 hp each
- InfernoTower: 5 elixir, building, 1748 hp each
- Rocket: 6 elixir, spell
- Log: 2 elixir, spell
- IceSpirits: 1 elixir, troop, 215 hp each

Opponent deck: giant-beatdown (average 3.38 elixir).
- Giant: 5 elixir, troop, 3968 hp each
- Musketeer: 4 elixir, troop, 721 hp each
- Knight: 3 elixir, troop, 1766 hp each
- Archer: 3 elixir, troop x2, 304 hp each
- Minions: 3 elixir, troop x3, 230 hp each, flying
- Cannon: 3 elixir, building, 824 hp each
- Fireball: 4 elixir, spell
- Zap: 2 elixir, spell
