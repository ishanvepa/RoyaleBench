"""Repair a downloaded Valkyrie codex-v1.0.0 bundle before uploading it.

Usage: uv run python tools/repair_codex_harness.py PATH_TO_BUNDLE
"""

import argparse
import ast
import re
from pathlib import Path


def repair(bundle: Path) -> None:
    contract = bundle / "contract.yaml"
    wrapper = bundle / "collect_outputs.py"
    contract_text = contract.read_text(encoding="utf-8")
    wrapper_text = wrapper.read_text(encoding="utf-8")
    # The upstream contract's obsolete enum rejects newer and provider-prefixed IDs.
    contract_text = re.sub(
        r"(?m)^    choices:\n(?:      - [^\n]+\n)+", "", contract_text
    )
    original = "stream_codex(command, dict(os.environ))"
    replacement = (
        'stream_codex(command, {**os.environ, "CODEX_API_KEY": os.environ["OPENAI_API_KEY"]})'
    )
    if original not in wrapper_text and replacement not in wrapper_text:
        raise ValueError("Unrecognized Codex wrapper; inspect its authentication before patching")
    wrapper_text = wrapper_text.replace(original, replacement)
    ast.parse(wrapper_text)
    # Byte writes prevent Windows from restoring CRLF in Linux shell scripts.
    for script in bundle.rglob("*.sh"):
        script.write_bytes(script.read_bytes().replace(b"\r\n", b"\n"))
    contract.write_bytes(contract_text.encode("utf-8"))
    wrapper.write_bytes(wrapper_text.encode("utf-8"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    repair(parser.parse_args().bundle)
    print("Repaired model choices, shell line endings, and Codex exec authentication.")
