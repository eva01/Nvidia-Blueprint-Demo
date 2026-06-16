import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "demo"


class DemoScriptTests(unittest.TestCase):
    def test_default_command_runs_voice_demo_script(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            capture = Path(temp_dir) / "voice-args.txt"
            stub = Path(temp_dir) / "run_cloud_demo.sh"
            stub.write_text(
                f"""#!/usr/bin/env bash
for arg in "$@"; do
  printf '%s\\n' "$arg" >> {capture}
done
touch {capture}
""",
                encoding="utf-8",
            )
            stub.chmod(0o755)
            env = {**os.environ, "DEMO_RUN_CLOUD_SCRIPT": str(stub)}

            result = subprocess.run(
                [str(DEMO)],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=5,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(capture.read_text(encoding="utf-8").splitlines(), [])

    def test_smoke_subcommand_runs_go_smoke_cli_with_base_url(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            capture = Path(temp_dir) / "go-args.txt"
            stub = Path(temp_dir) / "go"
            stub.write_text(
                f"""#!/usr/bin/env bash
printf '%s\\n' "$@" > {capture}
""",
                encoding="utf-8",
            )
            stub.chmod(0o755)
            env = {
                **os.environ,
                "PATH": f"{temp_dir}:{os.environ['PATH']}",
                "FACILITY_BACKEND_URL": "http://127.0.0.1:8787",
            }

            result = subprocess.run(
                [str(DEMO), "smoke"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=5,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                capture.read_text(encoding="utf-8").splitlines(),
                ["run", "./cmd/facility-smoke", "--base-url", "http://127.0.0.1:8787"],
            )

    def test_smoke_subcommand_derives_base_url_from_voice_backend_port(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            capture = Path(temp_dir) / "go-args.txt"
            stub = Path(temp_dir) / "go"
            stub.write_text(
                f"""#!/usr/bin/env bash
printf '%s\\n' "$@" > {capture}
""",
                encoding="utf-8",
            )
            stub.chmod(0o755)
            env = {
                **os.environ,
                "PATH": f"{temp_dir}:{os.environ['PATH']}",
                "VOICE_BACKEND_PORT": "8788",
            }
            env.pop("FACILITY_BACKEND_URL", None)

            result = subprocess.run(
                [str(DEMO), "smoke"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
                timeout=5,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                capture.read_text(encoding="utf-8").splitlines(),
                ["run", "./cmd/facility-smoke", "--base-url", "http://127.0.0.1:8788"],
            )

    def test_smoke_subcommand_preserves_explicit_smoke_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            capture = Path(temp_dir) / "go-args.txt"
            stub = Path(temp_dir) / "go"
            stub.write_text(
                f"""#!/usr/bin/env bash
printf '%s\\n' "$@" > {capture}
""",
                encoding="utf-8",
            )
            stub.chmod(0o755)
            env = {
                **os.environ,
                "PATH": f"{temp_dir}:{os.environ['PATH']}",
                "FACILITY_BACKEND_URL": "http://127.0.0.1:8787",
            }

            result = subprocess.run(
                [
                    str(DEMO),
                    "smoke",
                    "--base-url",
                    "http://127.0.0.1:8789",
                    "--timeout",
                    "2s",
                    "--evidence-report",
                    "evidence.json",
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                capture.read_text(encoding="utf-8").splitlines(),
                [
                    "run",
                    "./cmd/facility-smoke",
                    "--base-url",
                    "http://127.0.0.1:8789",
                    "--timeout",
                    "2s",
                    "--evidence-report",
                    "evidence.json",
                ],
            )

    def test_unknown_command_passes_through_to_voice_demo_script(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            capture = Path(temp_dir) / "voice-args.txt"
            stub = Path(temp_dir) / "run_cloud_demo.sh"
            stub.write_text(
                f"""#!/usr/bin/env bash
printf '%s\\n' "$@" > {capture}
""",
                encoding="utf-8",
            )
            stub.chmod(0o755)
            env = {**os.environ, "DEMO_RUN_CLOUD_SCRIPT": str(stub)}

            result = subprocess.run(
                [str(DEMO), "--workers", "1"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(capture.read_text(encoding="utf-8").splitlines(), ["--workers", "1"])

    def test_help_lists_voice_smoke_and_operator_commands(self) -> None:
        result = subprocess.run(
            [str(DEMO), "--help"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("voice", result.stdout)
        self.assertIn("smoke", result.stdout)
        self.assertIn("operator", result.stdout)
        self.assertIn("--base-url", result.stdout)
        self.assertIn("--timeout", result.stdout)
        self.assertIn("--evidence-report", result.stdout)

    def test_operator_dry_run_prints_no_key_local_demo_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env = {**os.environ, "TMPDIR": temp_dir}
            env.pop("NVIDIA_API_KEY", None)

            result = subprocess.run(
                [str(DEMO), "operator", "--dry-run"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Operator backend: http://127.0.0.1:7860", result.stdout)
            self.assertIn("Sovereignty: http://127.0.0.1:7860/facility/sovereignty", result.stdout)
            self.assertIn("Summary: http://127.0.0.1:7860/facility/summary", result.stdout)
            self.assertIn("Tickets: http://127.0.0.1:7860/facility/tickets", result.stdout)
            self.assertIn("Audit: http://127.0.0.1:7860/facility/audit", result.stdout)
            self.assertIn(f"SQLite DB: {temp_dir}", result.stdout)
            self.assertIn("FACILITY_TICKETS_DB_PATH=", result.stdout)
            self.assertIn("ALLOW_CLOUD_NIM=false", result.stdout)
            self.assertIn("uv run python -m src.pipeline --host 127.0.0.1 --port 7860", result.stdout)
            self.assertIn("go run ./cmd/facility-smoke --base-url http://127.0.0.1:7860", result.stdout)
            self.assertNotIn("NVIDIA_API_KEY", result.stdout)

    def test_operator_dry_run_forces_safe_local_governance_defaults(self) -> None:
        env = {
            **os.environ,
            "SOVEREIGN_MODE": "production",
            "DATA_RESIDENCY_REGION": "remote-region",
            "ALLOW_CLOUD_NIM": "true",
            "PII_REDACTION_ENABLED": "false",
            "AUDIT_LOG_ENABLED": "false",
        }

        result = subprocess.run(
            [str(DEMO), "operator", "--dry-run"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("SOVEREIGN_MODE=local-demo", result.stdout)
        self.assertIn("DATA_RESIDENCY_REGION=local-operator", result.stdout)
        self.assertIn("ALLOW_CLOUD_NIM=false", result.stdout)
        self.assertIn("PII_REDACTION_ENABLED=false", result.stdout)
        self.assertIn("AUDIT_LOG_ENABLED=true", result.stdout)
        self.assertNotIn("SOVEREIGN_MODE=production", result.stdout)
        self.assertNotIn("ALLOW_CLOUD_NIM=true", result.stdout)

    def test_operator_dry_run_uses_unique_temp_db_path_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env = {**os.environ, "TMPDIR": temp_dir}

            first = subprocess.run(
                [str(DEMO), "operator", "--dry-run"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            second = subprocess.run(
                [str(DEMO), "operator", "--dry-run"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            first_db = _output_value(first.stdout, "SQLite DB: ")
            second_db = _output_value(second.stdout, "SQLite DB: ")
            self.assertNotEqual(first_db, second_db)
            self.assertTrue(first_db.startswith(temp_dir))
            self.assertTrue(second_db.startswith(temp_dir))

    def test_operator_dry_run_accepts_explicit_port_db_and_evidence_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "operator.db"

            result = subprocess.run(
                [
                    str(DEMO),
                    "operator",
                    "--dry-run",
                    "--port",
                    "8799",
                    "--db-path",
                    str(db_path),
                    "--evidence-report",
                    "evidence/local.json",
                    "--timeout",
                    "2s",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Operator backend: http://127.0.0.1:8799", result.stdout)
            self.assertIn(f"SQLite DB: {db_path}", result.stdout)
            self.assertIn(
                "go run ./cmd/facility-smoke --base-url http://127.0.0.1:8799 "
                "--evidence-report evidence/local.json --timeout 2s",
                result.stdout,
            )

    def test_operator_dry_run_quotes_commands_with_spaced_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "operator db.sqlite"
            evidence_path = Path(temp_dir) / "local evidence.json"

            result = subprocess.run(
                [
                    str(DEMO),
                    "operator",
                    "--dry-run",
                    "--db-path",
                    str(db_path),
                    "--evidence-report",
                    str(evidence_path),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            smoke_line = next(line for line in result.stdout.splitlines() if line.startswith("Smoke command: "))
            self.assertNotIn(str(evidence_path), smoke_line)
            self.assertIn("local\\ evidence.json", smoke_line)

    def test_operator_non_dry_run_cleans_up_without_unbound_variables(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            uv_stub = Path(temp_dir) / "uv"
            go_stub = Path(temp_dir) / "go"
            python_stub = Path(temp_dir) / "python3"
            uv_args = Path(temp_dir) / "uv-args.txt"
            go_args = Path(temp_dir) / "go-args.txt"

            uv_stub.write_text(
                f"""#!/usr/bin/env bash
printf '%s\\n' "$@" > {uv_args}
exec sleep 30
""",
                encoding="utf-8",
            )
            go_stub.write_text(
                f"""#!/usr/bin/env bash
printf '%s\\n' "$@" > {go_args}
""",
                encoding="utf-8",
            )
            python_stub.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            uv_stub.chmod(0o755)
            go_stub.chmod(0o755)
            python_stub.chmod(0o755)
            env = {
                **os.environ,
                "PATH": f"{temp_dir}:{os.environ['PATH']}",
                "TMPDIR": temp_dir,
            }

            result = subprocess.run(
                [str(DEMO), "operator", "--port", "8795", "--timeout", "1s"],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("unbound variable", result.stderr)
            self.assertEqual(
                uv_args.read_text(encoding="utf-8").splitlines(),
                ["run", "python", "-m", "src.pipeline", "--host", "127.0.0.1", "--port", "8795"],
            )
            self.assertEqual(
                go_args.read_text(encoding="utf-8").splitlines(),
                ["run", "./cmd/facility-smoke", "--base-url", "http://127.0.0.1:8795", "--timeout", "1s"],
            )


def _output_value(output: str, prefix: str) -> str:
    for line in output.splitlines():
        if line.startswith(prefix):
            return line.removeprefix(prefix)
    raise AssertionError(f"Missing output line starting with {prefix!r}: {output}")


if __name__ == "__main__":
    unittest.main()
