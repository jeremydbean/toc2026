#!/usr/bin/env python3
"""Boot a game binary against disposable world data and test its login socket."""

import argparse
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]


def receive_until(connection, expected, process, timeout=20):
    deadline = time.monotonic() + timeout
    received = bytearray()
    connection.settimeout(0.5)
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Game exited before completing the login check")
        try:
            chunk = connection.recv(8192)
        except socket.timeout:
            continue
        if not chunk:
            raise RuntimeError("Game closed the login connection unexpectedly")
        received.extend(chunk)
        if expected.lower() in received.lower():
            return
        if len(received) > 131072:
            raise RuntimeError("Unexpectedly large login response")
    raise TimeoutError(f"Game did not send expected login text: {expected!r}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, default=ROOT / "merc")
    parser.add_argument("--runner", default="", help="Optional emulator command, e.g. qemu-aarch64 -L /usr/aarch64-linux-gnu")
    parser.add_argument("--seconds", type=int, default=25, help="Additional game-loop observation time")
    args = parser.parse_args()
    if not 0 <= args.seconds <= 300:
        parser.error("--seconds must be between 0 and 300")
    binary = args.binary.resolve(strict=True)
    command = [*shlex.split(args.runner), str(binary)]

    with tempfile.TemporaryDirectory(prefix="toc-game-smoke-") as directory:
        fixture = Path(directory)
        for name in ("area", "player", "gods", "heroes", "corpse", "log", "backups"):
            (fixture / name).mkdir()
        # Copy world definitions only, never live accounts, queues, or runtime tables.
        for source in (ROOT / "area").glob("*.are"):
            shutil.copyfile(source, fixture / "area" / source.name)
        shutil.copyfile(ROOT / "area" / "area.lst", fixture / "area" / "area.lst")
        (fixture / "area" / "pkilldata.txt").write_text("$\n", encoding="ascii")
        world = fixture / "area"
        checked = subprocess.run(
            [*command, "--check-area"], cwd=world,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90,
        )
        output = checked.stdout.decode("latin-1")
        if checked.returncode or "Validation OK:" not in output:
            raise RuntimeError(f"Area validation failed:\n{output[-6000:]}")
        print(next(line for line in output.splitlines() if "Validation OK:" in line), flush=True)

        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        # The legacy game binds INADDR_ANY; use an isolated host/network for this check.
        with (fixture / "game.log").open("wb") as log:
            process = subprocess.Popen([*command, str(port)], cwd=world, stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 60
                while True:
                    if process.poll() is not None:
                        raise RuntimeError("Game exited during startup")
                    try:
                        connection = socket.create_connection(("127.0.0.1", port), timeout=1)
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise TimeoutError("Game did not open its login socket")
                        time.sleep(0.1)
                with connection:
                    receive_until(connection, b"name", process)
                    connection.sendall(b"1\r\n")
                    receive_until(connection, b"Illegal name", process)
                    connection.sendall(b"Armprobe\r\n")
                    receive_until(connection, b"Did I get that right", process)
                    connection.sendall(b"n\r\n")
                    receive_until(connection, b"what IS it, then?", process)
                    connection.sendall(b"Armprobe\r\n")
                    receive_until(connection, b"Did I get that right", process)
                    connection.sendall(b"y\r\n")
                    receive_until(connection, b"Give me a password", process)
                    connection.sendall(b"Armtest9\r\n")
                    receive_until(connection, b"Please retype password", process)
                    connection.sendall(b"Wrong123\r\n")
                    receive_until(connection, b"Passwords don't match", process)
                    connection.sendall(b"Armtest9\r\n")
                    receive_until(connection, b"Please retype password", process)
                    connection.sendall(b"Armtest9\r\n")
                    receive_until(connection, b"What is your race", process)
                    print("PASS: login, name validation, and password hashing/confirmation", flush=True)
                    deadline = time.monotonic() + args.seconds
                    while time.monotonic() < deadline:
                        if process.poll() is not None:
                            raise RuntimeError("Game exited during the game-loop check")
                        time.sleep(0.25)
                    print(f"PASS: game loop remained alive for {args.seconds} additional seconds", flush=True)
            except Exception:
                log.flush()
                print((fixture / "game.log").read_text(encoding="latin-1")[-6000:])
                raise
            finally:
                if process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)


if __name__ == "__main__":
    main()
