#!/usr/bin/env python3
"""Exercise the live server's Mudlet negotiation without creating a player."""

from __future__ import annotations

import argparse
import socket
import time

IAC = 255
DO = 253
WILL = 251
SB = 250
SE = 240
GMCP = 201


def gmcp_packet(message: str) -> bytes:
    return bytes((IAC, SB, GMCP)) + message.encode("ascii") + bytes((IAC, SE))


def receive_until(sock: socket.socket, predicate, timeout: float = 5.0) -> bytes:
    deadline = time.monotonic() + timeout
    data = bytearray()
    while time.monotonic() < deadline:
        try:
            chunk = sock.recv(8192)
        except socket.timeout:
            continue
        if not chunk:
            break
        data.extend(chunk)
        if predicate(bytes(data)):
            break
    return bytes(data)


def extract_gmcp(data: bytes) -> list[str]:
    messages: list[str] = []
    marker = bytes((IAC, SB, GMCP))
    ending = bytes((IAC, SE))
    cursor = 0
    while True:
        start = data.find(marker, cursor)
        if start < 0:
            break
        end = data.find(ending, start + len(marker))
        if end < 0:
            break
        messages.append(data[start + len(marker) : end].decode("ascii"))
        cursor = end + len(ending)
    return messages


def run(host: str, port: int) -> None:
    with socket.create_connection((host, port), timeout=3.0) as sock:
        sock.settimeout(0.25)
        greeting = receive_until(sock, lambda data: b"Name:" in data)
        assert bytes((IAC, WILL, GMCP)) in greeting, "server did not offer GMCP"
        assert b"By what name art thou known?" in greeting, "login greeting missing"
        assert bytes((IAC, 249)) in greeting, "login prompt was not framed with IAC GA"

        negotiation = bytes((IAC, DO, GMCP))
        hello = gmcp_packet('Core.Hello {"client":"Mudlet","version":"test"}')
        supports = gmcp_packet(
            'Core.Supports.Add ["Char.Vitals 1","Char.Status 1","Room.Info 1"]'
        )

        # Deliberately split the Telnet sequences to verify state survives reads.
        sock.sendall(negotiation[:2])
        sock.sendall(negotiation[2:] + hello[:7])
        sock.sendall(hello[7:] + supports)

        protocol_data = receive_until(
            sock,
            lambda data: any(
                message.startswith("Client.GUI ") for message in extract_gmcp(data)
            ),
        )
        messages = extract_gmcp(protocol_data)
        assert any(message.startswith("Client.Map ") for message in messages), messages
        assert any(message.startswith("Client.GUI ") for message in messages), messages

        sock.sendall(gmcp_packet("Core.Ping 42"))
        ping_data = receive_until(sock, lambda data: "Core.Ping 42" in extract_gmcp(data))
        assert "Core.Ping 42" in extract_gmcp(ping_data), "Core.Ping response missing"

        # GMCP payload text must not leak into the next login name.
        sock.sendall(b"Mudlettest\r\n")
        login_reply = receive_until(
            sock,
            lambda data: b"Did I get that right" in data or b"Illegal name" in data,
        )
        assert b"Did I get that right, Mudlettest" in login_reply, login_reply
        assert b"Illegal name" not in login_reply, login_reply

    print(
        "Mudlet handshake passed: GMCP offer, map/GUI advertisement, ping, "
        "and clean login input."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("host", nargs="?", default="127.0.0.1")
    parser.add_argument("port", nargs="?", type=int, default=9000)
    args = parser.parse_args()
    run(args.host, args.port)


if __name__ == "__main__":
    main()
