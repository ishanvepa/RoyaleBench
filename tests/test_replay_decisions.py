"""Replay annotations must follow exact game observations, not wall-clock guesses."""

import json
import tempfile
import unittest
from pathlib import Path

from rb_evals.replay_decisions import read_decisions


class ReplayDecisionTests(unittest.TestCase):
    observations = [{"tick": 3600, "team": 0, "text": "DECISION 1\nThe first board."},
                    {"tick": 3640, "team": 0, "text": "DECISION 2\nThe second board."}]

    def parse(self, messages, *, mini=False, observations=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            if mini:
                (root / "trajectory.json").write_text(json.dumps({
                    "trajectory_format": "mini-swe-agent-1.1", "messages": messages}), encoding="utf-8")
            else:
                (root / "trajectory.jsonl").write_text("\n".join(json.dumps(m) for m in messages), encoding="utf-8")
            return read_decisions(root, self.observations if observations is None else observations)

    def test_mini_links_reasoning_and_commands_to_exact_board_and_skips_setup(self):
        messages = [
            {"role": "assistant", "content": "Setup, before seeing any board"},
            {"role": "tool", "content": json.dumps({"output": self.observations[0]["text"] + "\n"})},
            {"role": "assistant", "content": "Defend the left tower.", "reasoning_content": "The left tower is threatened.",
             "tool_calls": [{"function": {"name": "bash", "arguments": json.dumps({"command": "cr play 0 3 12"})}}]},
            {"role": "tool", "content": json.dumps({"output": self.observations[1]["text"]})},
            {"role": "assistant", "content": "Now save elixir.",
             "tool_calls": [{"function": {"name": "bash", "arguments": '{"command":"cr wait"}'}}]},
        ]
        decisions = self.parse(messages, mini=True)
        self.assertEqual([d["tick"] for d in decisions], [3600, 3640])
        self.assertEqual([s["kind"] for s in decisions[0]["steps"]], ["thinking", "text", "tool_use"])
        self.assertEqual(decisions[0]["steps"][-1]["text"], "cr play 0 3 12")
        self.assertNotIn("Setup", json.dumps(decisions))
        self.assertNotIn("Now save", json.dumps(decisions[0]))

    def test_claude_tool_results_and_stream_duplicates(self):
        observation = {"type": "user", "message": {"content": [{"type": "tool_result", "content": [
            {"type": "text", "text": self.observations[0]["text"]}]}]}}
        answer = {"type": "assistant", "message": {"id": "message-1", "content": [
            {"type": "text", "text": "Use Fireball."},
            {"type": "tool_use", "id": "tool-1", "name": "Bash", "input": {"command": "cr act 5"}}]}}
        decisions = self.parse([observation, answer, answer])
        self.assertEqual(len(decisions), 1)
        self.assertEqual([s["text"] for s in decisions[0]["steps"]], ["Use Fireball.", "cr act 5"])

    def test_ambiguous_or_unknown_boards_are_not_guessed_from_decision_number(self):
        observations = [*self.observations, {**self.observations[0], "tick": 4000}]
        messages = [{"role": "tool", "content": self.observations[0]["text"]},
                    {"role": "assistant", "content": "Ambiguous attempt"},
                    {"role": "tool", "content": "DECISION 2\nA different board."},
                    {"role": "assistant", "content": "Unknown attempt"}]
        self.assertEqual(self.parse(messages, mini=True, observations=observations), [])

    def test_unknown_board_and_game_over_clear_previous_decision(self):
        messages = [{"role": "tool", "content": self.observations[0]["text"]},
                    {"role": "assistant", "content": "A synchronized decision"},
                    {"role": "tool", "content": "GAME OVER\nWon"},
                    {"role": "assistant", "content": "Postgame commentary"}]
        decisions = self.parse(messages, mini=True)
        self.assertEqual(len(decisions), 1)
        self.assertEqual(len(decisions[0]["steps"]), 1)

    def test_unrecorded_reasoning_is_not_invented(self):
        messages = [{"role": "tool", "content": self.observations[0]["text"]},
                    {"role": "assistant", "content": "", "tool_calls": [{"function": {
                        "name": "bash", "arguments": {"command": "cr wait"}}}]}]
        self.assertEqual([s["kind"] for s in self.parse(messages, mini=True)[0]["steps"]], ["tool_use"])


if __name__ == "__main__":
    unittest.main()
