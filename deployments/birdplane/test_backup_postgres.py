"""Regression checks for complete Coolify backup transfers."""

import base64
import hashlib
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "backup_postgres", Path(__file__).with_name("backup-postgres.py")
)
backup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backup)


class BackupTransferTests(unittest.TestCase):
    def test_read_command_propagates_missing_dump_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.dump"
            result = subprocess.run(
                ["sh", "-c", backup.chunk_command(str(path), 0)],
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(result.stdout, b"")

    def test_read_command_returns_complete_chunk_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.dump"
            source = b"PGDMP" + b"x" * (backup.CHUNK_BYTES + 15)
            path.write_bytes(source)
            result = subprocess.run(
                ["sh", "-c", backup.chunk_command(str(path), 1)],
                capture_output=True,
                check=True,
            )
            expected = source[backup.CHUNK_BYTES :]
            self.assertEqual(
                backup.decode_chunk(result.stdout.decode(), len(expected)), expected
            )
            self.assertFalse(Path(str(path) + ".chunk").exists())
            self.assertLessEqual(
                len(backup.chunk_command("/tmp/bp-0123456789ab.dump", 999)), 255
            )

    def test_rejects_coolify_truncation_even_when_base64_prefix_is_valid(self):
        output = base64.b64encode(b"PGDMP" + b"x" * 40).decode()
        with self.assertRaises(ValueError):
            backup.decode_chunk(
                output + "\n[... Output truncated at 5MB limit ...]", 45
            )

    def test_rejects_silently_short_chunk(self):
        with self.assertRaises(ValueError):
            backup.decode_chunk(base64.b64encode(b"PGDMP").decode(), 100)

    def test_accepts_wrapped_base64(self):
        data = b"PGDMP" + b"x" * 512
        self.assertEqual(
            backup.decode_chunk(base64.encodebytes(data).decode(), len(data)), data
        )

    def test_does_not_publish_partial_or_corrupt_backup(self):
        source = b"PGDMP" + bytes(range(256)) * 5
        for bad_chunk in [b"short", b"z" * backup.CHUNK_BYTES]:
            with (
                self.subTest(bad_chunk=len(bad_chunk)),
                tempfile.TemporaryDirectory() as directory,
            ):
                path = Path(directory) / "database.dump"
                with self.assertRaises(ValueError):
                    backup.transfer(
                        path,
                        len(source),
                        hashlib.sha256(source).hexdigest(),
                        lambda index, expected, data=bad_chunk: base64.b64encode(
                            data[:expected]
                        ).decode(),
                    )
                self.assertFalse(path.exists())

    def test_complete_transfer_checks_hash_before_publishing(self):
        source = b"PGDMP" + bytes(range(256)) * 4097
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "database.dump"
            calls = []

            def read(index, expected):
                start = index * backup.CHUNK_BYTES
                calls.append((index, expected))
                return base64.encodebytes(source[start : start + expected]).decode()

            backup.transfer(path, len(source), hashlib.sha256(source).hexdigest(), read)
            self.assertEqual(path.read_bytes(), source)
            self.assertEqual(len(calls), 3)
            self.assertEqual(calls[-1][1], len(source) % backup.CHUNK_BYTES)
            self.assertFalse(path.with_suffix(".dump.part").exists())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_manifest_must_describe_exact_remote_file(self):
        digest = "a" * 64
        self.assertEqual(
            backup.parse_manifest(
                f"{digest}  /tmp/backup.dump\n12345\n", "/tmp/backup.dump"
            ),
            (12345, digest),
        )
        for output in [
            f"{digest}  /tmp/other.dump\n12345",
            f"{digest}  /tmp/backup.dump\n0",
        ]:
            with self.assertRaises(ValueError):
                backup.parse_manifest(output, "/tmp/backup.dump")

    def test_cannot_overwrite_an_existing_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "database.dump"
            path.write_bytes(b"existing")
            with self.assertRaises(FileExistsError):
                backup.transfer(path, 5, "a" * 64, lambda *_: "")
            self.assertEqual(path.read_bytes(), b"existing")

    def test_cannot_remove_an_existing_partial_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "database.dump"
            partial = path.with_suffix(".dump.part")
            partial.write_bytes(b"existing partial")
            with self.assertRaises(FileExistsError):
                backup.transfer(path, 5, "a" * 64, lambda *_: "")
            self.assertEqual(partial.read_bytes(), b"existing partial")

    def test_failed_execution_keeps_history_without_retrying(self):
        with tempfile.TemporaryDirectory() as directory:
            client = backup.Coolify(
                "https://coolify.example",
                "test",
                "applications",
                "app",
                "plane-db",
                Path(directory),
                "Manual backup",
            )
            with (
                patch.object(
                    client,
                    "request",
                    side_effect=[
                        {"uuid": "task", "enabled": False, "container": "plane-db"},
                        {},
                        [{"status": "failed"}],
                    ],
                ) as request,
                self.assertRaises(RuntimeError),
            ):
                client.run("capture", "pg_dump -w")
            self.assertEqual(
                [call.args[0] for call in request.call_args_list],
                ["POST", "POST", "GET"],
            )
            self.assertEqual(client.receipts[0]["status"], "failed")

    def test_task_is_disabled_and_cleanup_waits_for_success(self):
        with tempfile.TemporaryDirectory() as directory:
            client = backup.Coolify(
                "https://coolify.example",
                "test",
                "applications",
                "app",
                "plane-db",
                Path(directory),
                "Manual backup",
            )
            with (
                patch.object(
                    client,
                    "request",
                    side_effect=[
                        {"uuid": "task", "enabled": False, "container": "plane-db"},
                        {},
                        [{"status": "running"}],
                        [{"status": "success", "message": "complete"}],
                        {},
                    ],
                ) as request,
                patch.object(backup.time, "sleep"),
            ):
                self.assertEqual(client.run("capture", "pg_dump -w"), "complete")
            self.assertFalse(request.call_args_list[0].args[2]["enabled"])
            self.assertEqual(
                [call.args[0] for call in request.call_args_list],
                ["POST", "POST", "GET", "GET", "DELETE"],
            )


if __name__ == "__main__":
    unittest.main()
