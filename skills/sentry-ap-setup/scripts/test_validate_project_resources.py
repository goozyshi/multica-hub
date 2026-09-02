#!/usr/bin/env python3
"""Small regression check for the project Repo creation gate."""

import json
import tempfile
from pathlib import Path

from validate_autopilot_description import Validation, validate_project_resources


PROJECT_ID = "47c28309-66c3-4da0-a82a-4b1d93c491f5"
REPO_URL = "https://gitlab-vywrajy.micoworld.net/micocenter/mico-portal/omigo/h5.git"


def run() -> None:
    with tempfile.TemporaryDirectory() as directory:
        resources_file = Path(directory) / "resources.json"
        resources_file.write_text(
            json.dumps(
                [
                    {
                        "project_id": PROJECT_ID,
                        "resource_type": "github_repo",
                        "resource_ref": {"url": REPO_URL},
                    }
                ]
            ),
            encoding="utf-8",
        )

        valid = Validation()
        validate_project_resources(
            str(resources_file), PROJECT_ID, [REPO_URL], valid
        )
        assert not valid.errors

        resources_file.write_text("[]", encoding="utf-8")
        missing = Validation()
        validate_project_resources(
            str(resources_file), PROJECT_ID, [REPO_URL], missing
        )
        assert any(
            error["code"] == "missing_project_repo" for error in missing.errors
        )


if __name__ == "__main__":
    run()
    print("project resource validator self-check passed")
