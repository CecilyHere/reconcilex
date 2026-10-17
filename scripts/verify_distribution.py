"""Install the built wheel offline in a fresh venv and test the installed package."""

import json
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

root = Path(__file__).resolve().parents[1]
wheels = list((root / "dist").glob("*.whl"))
if len(wheels) != 1:
    raise SystemExit("Expected exactly one wheel in dist/")
env = dict(os.environ)
env.pop("PYTHONPATH", None)
with tempfile.TemporaryDirectory() as directory:
    work = Path(directory)
    venv.EnvBuilder(with_pip=True).create(work / "venv")
    python = work / "venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run([str(python), "-m", "pip", "install", "--no-index", "--no-deps", str(wheels[0])], check=True, cwd=work, env=env)
    subprocess.run([str(python), "-m", "pip", "check"], check=True, cwd=work, env=env)
    subprocess.run([str(python), "-m", "unittest", "discover", "-s", str(root / "tests"), "-v"], check=True, cwd=work, env=env)
    command = work / "venv" / ("Scripts/reconcilex.exe" if os.name == "nt" else "bin/reconcilex")
    subprocess.run([str(command), "demo", "--out", str(work / "report")], check=True, cwd=work, env=env)
    result = json.loads((work / "report" / "result.json").read_text(encoding="utf-8"))
    expected = json.loads((root / "examples" / "expected.json").read_text(encoding="utf-8"))
    assert all(result["summary"][key] == value for key, value in expected.items())
print("Fresh wheel installation, dependency check, installed-package tests, console entry point, and demo verified.")
