"""MCCP2 output compression, decoded the way a client decodes it.

Audit 2026-10-21, two faults in src/telnet_proto.c:

- telnet_write_compressed stopped once zlib had taken all the input, but
  a full output buffer means the flush is not finished: 8,192
  incompressible bytes decoded to 8,185, the last seven waiting for the
  next write.
- DONT COMPRESS2 destroyed the stream without its end and sent the rest
  in plaintext, which every decoder reads as a corrupt stream.

tests/test_mccp.c runs the real telnet_proto.c with the socket stubbed.
"""
from __future__ import annotations

import os
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CC = os.environ.get("CC", "cc").split()[-1]
IAC, SB, SE = 255, 250, 240
COMPRESS2 = 86


def phases(output: bytes) -> list[bytes]:
    found = []
    while output:
        (length,) = struct.unpack(">I", output[:4])
        found.append(output[4:4 + length])
        output = output[4 + length:]
    return found


@unittest.skipIf(shutil.which(CC) is None, "no C compiler")
class MccpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        binary = Path(cls.tmp.name) / "test_mccp"
        build = subprocess.run(
            [CC, "-std=gnu89", "-fcommon", "-DROM", "-I", str(ROOT / "src"),
             "-o", str(binary), str(ROOT / "tests" / "test_mccp.c"),
             str(ROOT / "src" / "telnet_proto.c"), "-lz"],
            capture_output=True, text=True)
        if build.returncode != 0:
            raise AssertionError("harness did not build:\n" + build.stderr)
        run = subprocess.run([str(binary)], capture_output=True, timeout=60)
        if run.returncode != 0:
            raise AssertionError("harness exited %d" % run.returncode)
        cls.phases = phases(run.stdout)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def test_the_handshake_goes_out_plain(self) -> None:
        self.assertEqual(self.phases[1], bytes([IAC, SB, COMPRESS2, IAC, SE]))

    def test_a_big_write_is_whole_when_the_call_returns(self) -> None:
        stream = zlib.decompressobj()
        self.assertEqual(stream.decompress(self.phases[2]), self.phases[0])
        self.assertEqual(stream.decompress(self.phases[3]), b"hello")

    def test_turning_it_off_ends_the_stream_before_plaintext(self) -> None:
        stream = zlib.decompressobj()
        stream.decompress(self.phases[2] + self.phases[3])
        self.assertFalse(stream.eof)
        tail = stream.decompress(self.phases[4])
        self.assertEqual(tail, b"")
        self.assertTrue(stream.eof, "the client must see the stream end")
        self.assertEqual(stream.unused_data, b"")
        self.assertEqual(self.phases[5], b"plain")

    def test_it_can_be_turned_on_again(self) -> None:
        handshake = bytes([IAC, SB, COMPRESS2, IAC, SE])
        again = self.phases[6]
        self.assertTrue(again.startswith(handshake), again[:8])
        self.assertEqual(zlib.decompressobj().decompress(again[len(handshake):]), b"again")


if __name__ == "__main__":
    unittest.main()
