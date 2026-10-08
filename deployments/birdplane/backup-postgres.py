#!/usr/bin/env python3
"""Transfer a PostgreSQL snapshot through bounded, manual Coolify tasks.

Use direct container access instead when available. A successful transfer still
requires a full isolated restore before it can be treated as a verified backup.
"""

import argparse
import base64
import hashlib
import json
import os
import re
import shlex
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

CHUNK_BYTES = 512 * 1024


def chunk_command(remote_path: str, index: int) -> str:
    chunk_path = remote_path + ".chunk"
    return (
        f"set -eu; dd if={shlex.quote(remote_path)} bs={CHUNK_BYTES} "
        f"skip={index} count=1 of={shlex.quote(chunk_path)} 2>/dev/null; "
        f"base64 {shlex.quote(chunk_path)}; rm -f {shlex.quote(chunk_path)}"
    )


def decode_chunk(output: str, expected_bytes: int) -> bytes:
    data = base64.b64decode("".join(output.split()), validate=True)
    if len(data) != expected_bytes:
        raise ValueError("Backup chunk length mismatch; transfer is incomplete")
    return data


def parse_manifest(output: str, remote_path: str) -> tuple[int, str]:
    lines = output.strip().splitlines()
    if len(lines) != 2:
        raise ValueError("Unexpected server backup manifest")
    digest, path = lines[0].split(maxsplit=1)
    size = int(lines[1].strip())
    if not re.fullmatch(r"[a-f0-9]{64}", digest) or path != remote_path or size <= 0:
        raise ValueError("Invalid server backup manifest")
    return size, digest


def transfer(destination: Path, size: int, digest: str, read_chunk) -> None:
    if destination.exists():
        raise FileExistsError("Refusing to overwrite an existing backup")
    partial = destination.with_suffix(destination.suffix + ".part")
    checksum = hashlib.sha256()
    output = partial.open("xb")
    try:
        with output:
            os.chmod(partial, 0o600)
            for index, offset in enumerate(range(0, size, CHUNK_BYTES)):
                expected = min(CHUNK_BYTES, size - offset)
                data = decode_chunk(read_chunk(index, expected), expected)
                output.write(data)
                checksum.update(data)
            output.flush()
            os.fsync(output.fileno())
        if checksum.hexdigest() != digest:
            raise ValueError("Backup SHA-256 mismatch; transfer is corrupt")
        # Hard-link publication is atomic and cannot replace an existing backup.
        os.link(partial, destination)
    finally:
        partial.unlink(missing_ok=True)


class Coolify:
    def __init__(
        self,
        url: str,
        token: str,
        resource: str,
        resource_uuid: str,
        container: str,
        directory: Path,
        label: str,
    ):
        self.url = url.rstrip("/") + "/api/v1"
        self.token = token
        self.tasks_path = f"/{resource}/{resource_uuid}/scheduled-tasks"
        self.container = container
        self.directory = directory
        self.label = label
        self.receipts = []

    def request(self, method: str, path: str, body=None):
        request = urllib.request.Request(
            self.url + path,
            headers={
                "Authorization": "Bearer " + self.token,
                "Content-Type": "application/json",
            },
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    def save_receipts(self):
        (self.directory / "tasks.json").write_text(
            json.dumps(self.receipts, indent=2) + "\n"
        )

    def run(self, label: str, command: str) -> str:
        if len(command) > 255:
            raise ValueError("Coolify task command exceeds 255 characters")
        task = self.request(
            "POST",
            self.tasks_path,
            {
                "name": self.label + " / " + label,
                "container": self.container,
                "command": command,
                "frequency": "0 0 1 1 *",
                "enabled": False,
                "timeout": 600,
            },
        )
        path = self.tasks_path + "/" + task["uuid"]
        receipt = {"task_uuid": task["uuid"], "label": label, "status": "created"}
        self.receipts.append(receipt)
        self.save_receipts()
        if task.get("enabled") is not False or task.get("container") != self.container:
            raise RuntimeError("Unexpected task configuration; not executing")
        self.request("POST", path + "/execute")
        deadline = time.monotonic() + 660
        while time.monotonic() < deadline:
            rows = self.request("GET", path + "/executions")
            if rows:
                execution = rows[0]
                status = execution["status"]
                if status not in ("running", "pending", "queued"):
                    receipt.update(
                        {
                            key: execution.get(key)
                            for key in (
                                "status",
                                "started_at",
                                "finished_at",
                                "duration",
                            )
                        }
                    )
                    self.save_receipts()
                    if status != "success":
                        # Preserve failed task history, and never automatically retry.
                        raise RuntimeError(
                            f"Task {label} {status}; inspect {task['uuid']}"
                        )
                    output = execution.get("message") or ""
                    self.request("DELETE", path)
                    receipt["removed"] = True
                    self.save_receipts()
                    return output
            time.sleep(1)
        raise TimeoutError(f"Task {label} still unfinished; retained for investigation")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--token-file", required=True, type=Path)
    parser.add_argument(
        "--resource", choices=("applications", "services"), default="applications"
    )
    parser.add_argument("--uuid", required=True)
    parser.add_argument("--container", default="plane-db")
    parser.add_argument("--database", default="plane")
    parser.add_argument("--user", default="plane")
    parser.add_argument(
        "--output", required=True, type=Path, help="New private backup directory"
    )
    parser.add_argument("--label", default="Manual PostgreSQL backup")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", args.uuid):
        parser.error("Invalid resource UUID")
    os.umask(0o077)
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    client = Coolify(
        args.url,
        args.token_file.read_text().strip(),
        args.resource,
        args.uuid,
        args.container,
        args.output,
        args.label,
    )
    remote_path = "/tmp/bp-" + uuid.uuid4().hex[:12] + ".dump"
    captured_at = datetime.now(timezone.utc).isoformat()
    # All PostgreSQL clients use the same socket and cannot prompt for a password.
    command = (
        "set -eu; umask 077; export PGHOST=/var/run/postgresql PGCONNECT_TIMEOUT=5; "
        f"pg_dump -w -U {shlex.quote(args.user)} -d {shlex.quote(args.database)} -Fc -f {remote_path}; "
        f"sha256sum {remote_path}; wc -c <{remote_path}"
    )
    manifest_path = args.output / "manifest.json"
    manifest = {
        "captured_at": captured_at,
        "database": args.database,
        "remote_path": remote_path,
        "resource_uuid": args.uuid,
        "transfer_verified": False,
        "restore_verified": False,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    size, digest = parse_manifest(client.run("capture", command), remote_path)
    manifest.update({"bytes": size, "sha256": digest})
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        f"Captured {size} bytes; transferring in {CHUNK_BYTES}-byte chunks", flush=True
    )

    def read(index, expected):
        output = client.run(
            f"transfer {index + 1}",
            chunk_command(remote_path, index),
        )
        print(f"Transferred chunk {index + 1}", flush=True)
        return output

    transfer(args.output / "database.dump", size, digest, read)
    manifest["transfer_verified"] = True
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    client.run("remove temporary file", f"rm -f {remote_path}")
    manifest["remote_file_removed"] = True
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(
        "Size and SHA-256 match. Verify a full isolated restore before accepting this backup."
    )


if __name__ == "__main__":
    main()
