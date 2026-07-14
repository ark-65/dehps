import json

from typer.testing import CliRunner

from dehps.cli import app
from pattern_fixtures import HISTORY


def test_pattern_discover_cli_is_dry_run_by_default(tmp_path) -> None:
    input_file = tmp_path / "draws.json"
    input_file.write_text(json.dumps({"draws": [{"issue": issue, "red_numbers": numbers} for issue, numbers in HISTORY]}))

    result = CliRunner().invoke(
        app,
        [
            "pattern",
            "discover",
            "--input",
            str(input_file),
            "--families",
            "2",
            "--patterns-per-family",
            "2",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["dry_run"] is True
    assert payload["writes"] == []
    assert payload["patterns"]
