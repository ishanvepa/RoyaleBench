"""Provider routing and request formatting, without network calls or real credentials."""

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from cr_arena.players import build_player


class OpenAIProviders(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "OPENAI_API_KEY": "test-openai", "OPENROUTER_API_KEY": "test-router",
            "CUSTOM_API_KEY": "test-custom",
        }, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        factory = patch("openai.OpenAI")
        self.factory = factory.start()
        self.addCleanup(factory.stop)
        self.client = self.factory.return_value
        self.client.chat.completions.create.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="MOVE: 1", refusal=None))],
            usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20),
        )

    def player(self, provider="openai", **settings):
        return build_player({"name": "test-model", "provider": provider,
                             "model": "test-model-id", **settings})

    def test_direct_openai_uses_own_key_and_endpoint(self):
        self.player(timeout_s=30)
        self.factory.assert_called_once_with(base_url="https://api.openai.com/v1",
                                             api_key="test-openai", timeout=30, max_retries=2)

    def test_direct_request_parameters_and_usage(self):
        player = self.player(effort="low", max_tokens=1234, extra={"store": False})
        raw, usage = player._call("board", system="rules")
        self.assertEqual(raw, "MOVE: 1")
        self.assertEqual(usage, {"in": 100, "out": 20})
        self.client.chat.completions.create.assert_called_once_with(
            model="test-model-id", max_completion_tokens=1234, reasoning_effort="low",
            messages=[{"role": "system", "content": "rules"}, {"role": "user", "content": "board"}],
            store=False,
        )

    def test_openrouter_keeps_existing_key_endpoint_and_parameters(self):
        player = self.player("openai_compat", effort="low", extra={"route": "fallback"})
        self.assertEqual(self.factory.call_args.kwargs["base_url"], "https://openrouter.ai/api/v1")
        self.assertEqual(self.factory.call_args.kwargs["api_key"], "test-router")
        player._call("board", system="rules")
        kwargs = self.client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["max_tokens"], 4000)
        self.assertEqual(kwargs["extra_body"], {"reasoning": {"effort": "low"}, "route": "fallback"})
        self.assertNotIn("max_completion_tokens", kwargs)

    def test_custom_key_and_endpoint_for_both_providers(self):
        for provider in ("openai", "openai_compat"):
            with self.subTest(provider=provider):
                self.player(provider, api_key_env="CUSTOM_API_KEY", base_url="https://example.test/v1")
                self.assertEqual(self.factory.call_args.kwargs["api_key"], "test-custom")
                self.assertEqual(self.factory.call_args.kwargs["base_url"], "https://example.test/v1")

    def test_missing_openai_key_does_not_fall_back_to_openrouter(self):
        del os.environ["OPENAI_API_KEY"]
        with self.assertRaisesRegex(RuntimeError, "OPENAI_API_KEY is not set"):
            self.player()
        self.factory.assert_not_called()

    def test_unset_effort_is_omitted_and_missing_usage_is_supported(self):
        self.client.chat.completions.create.return_value.usage = None
        _, usage = self.player()._call("board", system="rules")
        self.assertEqual(usage, {})
        self.assertNotIn("reasoning_effort", self.client.chat.completions.create.call_args.kwargs)

    def test_refusal_is_not_reclassified_as_infrastructure_failure(self):
        self.client.chat.completions.create.return_value.choices[0].message.refusal = "declined"
        with self.assertRaisesRegex(RuntimeError, "^refusal: declined$") as result:
            self.player()._call("board", system="rules")
        self.assertIs(type(result.exception), RuntimeError)


if __name__ == "__main__":
    unittest.main()
