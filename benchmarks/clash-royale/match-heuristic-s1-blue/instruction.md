# Win a Clash Royale match

You are playing one complete match of Clash Royale against a fixed, rule-based opponent. You play
every decision yourself through the `cr` command. Your goal is to **win the match**.

## How to play

- Run `cr` to see the current state of the battle and a numbered list of legal moves.
- Run `cr act N` to play move `N` (move `0` is always "wait"). The game then advances
  2.0 seconds of game time and prints the next state and legal moves.
- The game is paused while you think: there is no penalty for taking time on a decision.
- When you have no move except waiting (for example, not enough elixir), the game waits for you
  automatically, so every state you are shown needs a decision.
- Keep playing until `cr` prints `GAME OVER`. A match lasts 3 minutes of game time, plus up to
  2 minutes of overtime if the crowns are tied: at most 150 decisions, usually fewer. If you stop
  early, every decision you did not make counts as waiting for the rest of the match.

Make each decision yourself from the state `cr` shows you. Do not write programs, scripts or loops
that choose or submit moves for you: the benchmark measures your own decisions, and the timing of
each move is recorded. You cannot inspect or change the game itself; only `cr` is available.

## Scoring

Win = 1, loss = 0. There are no draws: if the crowns are still level when overtime ends, the side
with more tower HP left wins (see the rules below). The match is graded by replaying your moves,
so only the moves you submit with `cr act` count.

## Rules in brief

- Each side has a king tower and two princess towers (left and right). Destroying a princess tower = 1 crown, the king tower = 3 crowns (instant win).
- Most crowns when time runs out wins. If tied, overtime starts and the next crown wins. If crowns are still tied when
  overtime ends, the match ends there and the side with more tower HP left, all its towers added up, wins (if even that
  is exactly equal, a fixed coin flip decides). There are no draws. So tower damage matters even when it takes no crown.
- You spend elixir (max 10, regenerates over time; faster in the last minute and overtime) to play cards from a 4-card hand. A played card goes to the back of your 8-card deck queue.
- Troops walk down their lane toward enemy buildings and fight what they meet. Buildings stay put and defend. Spells hit an area once.
- Good play: defend efficiently (spend less elixir than the enemy push costs), counter-attack with surviving troops, don't sit at full elixir (wasted regeneration), punish the lane where the enemy just spent elixir.

## Coordinates

Positions are in tiles from YOUR point of view: x from 0 (left) to 17 (right), y from 0 (your back
edge) to 31 (the enemy's back edge). The river is at y ~15-16. Your princess towers are near y 6.5,
the enemy's near y 25.5.

## Your deck (8 cards)

- Giant: 5 elixir, troop, 3968 hp each
- Musketeer: 4 elixir, troop, 721 hp each
- Knight: 3 elixir, troop, 1766 hp each
- Archer: 3 elixir, troop x2, 304 hp each
- Minions: 3 elixir, troop x3, 230 hp each, flying
- Cannon: 3 elixir, building, 824 hp each
- Fireball: 4 elixir, spell
- Zap: 2 elixir, spell
