/** What the benchmark is and how results are produced. Plain text, ported from the original results page. */
export function AboutView() {
  const h = "mt-7 mb-1.5 font-display text-base font-semibold";
  return (
    <div className="mx-auto max-w-[720px] text-[15px] leading-relaxed">
      <h4 className={h.replace("mt-7", "mt-2")}>What is this?</h4>
      <p>
        Language models play full Clash Royale battles against each other on a deterministic open-source simulator (RoyaleGym). Every 2 seconds of game time each side gets a text view of the
        board (only what that player could see) and a numbered list of legal moves: wait, or a card from its hand at one of a fixed set of placement zones; spells can be aimed at visible enemy
        units or towers. It answers with <code>MOVE: n</code>. The game pauses while both sides decide, so only decisions matter, not speed.
      </p>
      <h4 className={h}>How are models ranked?</h4>
      <p>
        Standings are calculated within the selected run, sorted by games won. Ties are broken by fewer losses, then by crown difference. Only finished games count. During an ongoing run,
        players may have different game counts; win rate is shown alongside wins for context.
      </p>
      <h4 className={h}>Competition and deck rules</h4>
      <p>
        <b>Round robin</b> is a tournament where every player is scheduled against the others. <b>1 v 1</b> shows a single two-player battle. Each run has its own standings.{" "}
        <b>Preset decks</b> are supplied to the players; <b>model-built decks</b> are chosen by each model. Deck rules are shown from the recorded games, independently of the competition format.
      </p>
      <h4 className={h}>What happens with bad answers?</h4>
      <p>
        A reply without a legal move number is played as a wait and lowers <b>Reliability</b>. An invalid deck is replaced by a default deck and lowers <b>Valid decks</b>. If the model cannot be
        reached at all (rate limit, network), the game is thrown away and replayed, never scored. When waiting is the only legal move (no elixir), the model is not asked.
      </p>
      <h4 className={h}>Settings</h4>
      <p>
        Models use the configuration recorded with each run. Game counts, deck rules, and reasoning settings may differ between runs. Only finished games contribute to the displayed results.
      </p>
    </div>
  );
}
