"""A connection's address, apart from its host name (review, 2026-11-06).

The asynchronous resolver replaces a connection's host string with the PTR
name when one comes back, and bans, the shared-address notice and the staff
views all read that string. So:

- a numeric ban stopped matching once the name arrived, and the banned
  address could log in;
- one address was missed as shared when only one connection had resolved,
  and two addresses with the same PTR name were reported as one;
- an IPv6 ban typed whole never matched the compressed form the web bridge
  sends;
- DNS LIST showed a creator SOCKETS hid, and printed the throttle's folded
  IPv6 key as though it were an IPv4 address.

Each connection now carries its address by family and bytes (src/netaddr.c),
fixed for its life. Synthetic Z characters and a synthetic Killuminati in a
throwaway world; the "other" addresses are the documentation ranges
(203.0.113.0/24, 198.51.100.0/24, 2001:db8::/32), claimed through the PROXY
header exactly as the web bridge sends it.
"""
from __future__ import annotations

import re
import time
import unittest
from pathlib import Path

from live_mud import LiveMud, create_character, login, patch_player_file, skip_reason

ROOT = Path(__file__).resolve().parents[1]
SKIP = skip_reason()
PW = "Zaddrpass1"
TEMPLE = 4207


def make(mud: LiveMud, name: str, **fields) -> None:
    with mud.connect(timeout=120) as client:
        create_character(client, name, PW)
        client.send("quit")
        if not client.wait_closed():
            raise AssertionError(f"{name} did not leave the world")
    if fields:
        patch_player_file(mud, name, **fields)


def reboot_with_bans(mud: LiveMud, *bans: str) -> None:
    """The ban list is read at boot: write it, then boot again."""
    mud._stop()
    (mud.root / "area" / "ban.txt").write_text("".join(f"{ban}~\n" for ban in bans),
                                               encoding="latin-1")
    mud._launch()


def proxied(mud: LiveMud, header: str, timeout: float = 60):
    client = mud.connect(timeout=timeout)
    client.expect("by what name", "name:")
    client.send(header)
    client.expect("Name:", timeout=20)
    return client


class AddressSourceTests(unittest.TestCase):
    def test_bans_and_notices_read_the_address(self) -> None:
        comm = (ROOT / "src" / "comm.c").read_text(encoding="latin-1")
        ban = comm.split("static bool check_ban( DESCRIPTOR_DATA *d, int type )", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("net_addr_equal( &banned, &d->addr )", ban)
        self.assertIn("d->host_resolved", ban, "a host-name ban waits for a name")
        self.assertNotIn("check_ban( d->host", comm)
        same = comm.split("static void wizinfo_same_host( DESCRIPTOR_DATA *d", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("net_addr_equal( &od->addr, &d->addr )", same)
        self.assertNotIn("od->host", same)
        accept = comm.split("DESCRIPTOR_DATA *new_descriptor(int control) {", 1)[1].split("\n}\n", 1)[0]
        self.assertLess(accept.index("desc >= FD_SETSIZE"), accept.index("alloc_perm"),
                        "a descriptor select() cannot hold is refused before it is one")

    def test_staff_listings_share_one_visibility_rule(self) -> None:
        wiz = (ROOT / "src" / "act_wiz.c").read_text(encoding="latin-1")
        dns = wiz.split("void do_dns( CHAR_DATA *ch, char *argument )", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("staff_may_see_descriptor( ch, d )", dns)
        self.assertNotIn("inet_ntop( AF_INET, &address", dns, "no folded key shown as an address")
        sockets = wiz.split("void do_sockets( CHAR_DATA *ch, char *argument )", 1)[1].split("\n}\n", 1)[0]
        self.assertEqual(sockets.count("staff_may_see_descriptor( ch, d )"), 2)


@unittest.skipIf(SKIP is not None, SKIP or "")
class AddressBanLiveTests(unittest.TestCase):
    def test_an_address_ban_holds_whatever_the_resolver_did(self) -> None:
        env = {"TOC_DNS_LOOPBACK": "1", "TOC_DNS_DELAY_MS": "1500"}
        with LiveMud(extra_env=env) as mud:
            make(mud, "Zbanstaff", Levl=70, Room=TEMPLE)
            make(mud, "Zbanned")
            # 127.0.0.1 as it is; an IPv6 address spelled out whole, as
            # staff might type it; a test-net address with no PTR record.
            reboot_with_bans(mud, "127.0.0.1", "2001:0DB8:0000:0000:0000:0000:0000:0042",
                             "203.0.113.9")
            staff = mud.connect(timeout=120)
            try:
                staff.send(f"PROXY TCP4 198.51.100.7 127.0.0.1 50001 {mud.port}")
                login(staff, "Zbanstaff", PW)
                staff.sync("scroll 0")

                # Pending: the name arrives while the lookup it started waits.
                with mud.connect(timeout=30) as pending:
                    pending.expect("by what name", "name:")
                    pending.send("Zbanned")
                    pending.expect("Access denied", timeout=20)

                # Completed: the lookup replaces the host with a name. The
                # ban is asked again then, of the address, and still holds:
                # the connection is closed the moment the name arrives,
                # before a name is typed at all. (Before, the name took the
                # address's place and the same connection logged in.)
                with mud.connect(timeout=60) as done:
                    done.expect("by what name", "name:")
                    done.send("")                     # a line: the lookup starts
                    done.expect("Name:", timeout=20)
                    done.expect("Access denied", timeout=30)
                    self.assertTrue(done.wait_closed(timeout=20))
                log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
                self.assertIn("Banning access to 127.0.0.1 (its name, localhost, came after it "
                              "connected).", log, "the name did come back")

                # Unsuccessful: an address with no name.
                with proxied(mud, f"PROXY TCP4 203.0.113.9 127.0.0.1 50002 {mud.port}") as none:
                    none.send("Zbanned")
                    none.expect("Access denied", timeout=20)

                # IPv6, banned spelled out, arriving compressed.
                with proxied(mud, f"PROXY TCP6 2001:db8::42 ::1 50003 {mud.port}") as six:
                    six.send("Zbanned")
                    six.expect("Access denied", timeout=20)

                # Disabled: no lookup at all.
                staff.must("dns off", "Hostname lookups are now OFF")
                with mud.connect(timeout=30) as off:
                    off.expect("by what name", "name:")
                    off.send("")
                    off.expect("Name:", timeout=20)
                    time.sleep(2.0)
                    off.send("Zbanned")
                    off.expect("Access denied", timeout=20)

                # An address not banned is let through, its PTR name or not.
                with proxied(mud, f"PROXY TCP4 203.0.113.10 127.0.0.1 50004 {mud.port}") as free:
                    free.send("Zbanned")
                    free.expect("Password", timeout=20)
            finally:
                staff.close()

    def test_a_host_name_ban_is_asked_when_the_name_arrives(self) -> None:
        env = {"TOC_DNS_LOOPBACK": "1", "TOC_DNS_DELAY_MS": "2500"}
        with LiveMud(extra_env=env) as mud:
            make(mud, "Zbanname")
            reboot_with_bans(mud, "localhost")
            with mud.connect(timeout=60) as client:
                client.expect("by what name", "name:")
                client.send("Zbanname")
                # The name has not come back: nothing to match yet.
                client.expect("Password", timeout=20)
                client.expect("Access denied", timeout=20)
                self.assertTrue(client.wait_closed(timeout=20))
            log = (mud.root / "log" / "toc.log").read_text(encoding="latin-1")
        self.assertIn("Banning access to 127.0.0.1 (its name, localhost, came after it connected).", log)


@unittest.skipIf(SKIP is not None, SKIP or "")
class AddressStaffLiveTests(unittest.TestCase):
    def test_ban_allow_and_dns_allow_read_any_spelling(self) -> None:
        with LiveMud() as mud:
            for name in ("Killuminati", "Zaddrtarget"):
                make(mud, name, Levl=70 if name == "Killuminati" else 5, Room=TEMPLE)
            with mud.connect(timeout=120) as creator:
                login(creator, "Killuminati", PW)
                creator.sync("scroll 0")
                said = creator.must("ban 2001:0DB8:0000:0000:0000:0000:0000:0043", "banned")
                self.assertIn("2001:db8::43 is now banned (an address", said)
                self.assertIn("already banned", creator.must("ban 2001:db8::43", "banned"))
                with proxied(mud, f"PROXY TCP6 2001:db8::43 ::1 50005 {mud.port}") as six:
                    six.send("Zaddrtarget")
                    six.expect("Access denied", timeout=20)
                self.assertIn("no longer banned", creator.must("allow 2001:db8:0:0::43", "banned"))
                with proxied(mud, f"PROXY TCP6 2001:db8::43 ::1 50006 {mud.port}") as six:
                    six.send("Zaddrtarget")
                    six.expect("Password", timeout=20)

                # DNS ALLOW takes IPv6 and DNS GUARD never shows the folded key.
                self.assertIn("no longer held back",
                              creator.must("dns allow 2001:0db8:0000:0000:0000:0000:0000:0099", "guard"))
                self.assertIn("Syntax", creator.must("dns allow 203.0.113.9x", "Syntax"))
                self.assertIn("Syntax", creator.must("dns allow 203.0.113", "Syntax"))
                guard = creator.must("dns guard", "Connection guard")
                self.assertNotRegex(guard, r"\b24\d\.\d+\.\d+\.\d+")
            trusted = (mud.root / "log" / "player_addresses.tsv").read_text(encoding="latin-1")
        self.assertIn("2001:db8::99\t", trusted, "an IPv6 address is written as itself")
        self.assertNotRegex(trusted, r"(?m)^2[4-5]\d\.")

    def test_dns_list_hides_who_sockets_hides(self) -> None:
        with LiveMud(fixtures=True) as mud:
            for name in ("Killuminati", "Zaddrimpl", "Zaddrsevn"):
                make(mud, name, Levl=70, Room=TEMPLE)
            make(mud, "Zaddrmort", Room=TEMPLE)
            with mud.connect(timeout=120) as creator, \
                    mud.connect(timeout=120) as impl, \
                    mud.connect(timeout=120) as seventy_one, \
                    mud.connect(timeout=120) as mortal:
                login(creator, "Killuminati", PW)
                login(impl, "Zaddrimpl", PW)
                login(seventy_one, "Zaddrsevn", PW)
                login(mortal, "Zaddrmort", PW)
                for client in (creator, impl, seventy_one):
                    client.sync("scroll 0")
                creator.must("trust zaddrsevn 71", "trusted at level 71")

                def views(client) -> str:
                    return client.must("sockets", "[") + client.must("dns list", "Connected descriptors")

                # The creator arrives wizinvis at 72: hidden from 70 and 71.
                for viewer in (impl, seventy_one):
                    seen = views(viewer)
                    self.assertNotIn("Killuminati", seen)
                    self.assertIn("Zaddrmort", seen, "an ordinary player is listed")

                # Wizinvis 71: the 71 sees him in both lists, the 70 in neither.
                creator.must("wizinvis 71", "")
                self.assertEqual(views(seventy_one).count("Killuminati"), 2)
                self.assertNotIn("Killuminati", views(impl))

                # Switched into a mobile the implementor can see: the row is
                # listed by his name, so it stays hidden whole.
                creator.must("wizinvis 72", "")
                creator.must("goto 32700", "")
                creator.must("load mob 32700", "You create")
                creator.must("switch sparring", "Possessed")
                seen = views(impl)
                self.assertNotIn("Killuminati", seen)
                self.assertNotIn("sparring", seen.lower())
                creator.send("return")


@unittest.skipIf(SKIP is not None, SKIP or "")
class SharedAddressLiveTests(unittest.TestCase):
    def test_one_address_is_one_address_whatever_resolved(self) -> None:
        env = {"TOC_DNS_LOOPBACK": "1"}
        with LiveMud(extra_env=env) as mud:
            for name in ("Zaddrstaff", "Zaddrone", "Zaddrtwo"):
                make(mud, name, Levl=70 if name == "Zaddrstaff" else 5, Room=TEMPLE)
            with mud.connect(timeout=120) as staff, \
                    mud.connect(timeout=120) as one, \
                    mud.connect(timeout=120) as two:
                login(staff, "Zaddrstaff", PW)
                staff.sync("scroll 0")
                # One arrives by IPv4-mapped IPv6, the other dotted; one is
                # given time to resolve, the other is not.
                one.expect("by what name", "name:")
                one.send(f"PROXY TCP6 ::ffff:203.0.113.77 ::1 50010 {mud.port}")
                login(one, "Zaddrone", PW)
                one.sync("scroll 0")
                two.expect("by what name", "name:")
                two.send(f"PROXY TCP4 203.0.113.77 127.0.0.1 50011 {mud.port}")
                mark = len(staff.transcript)
                login(two, "Zaddrtwo", PW)
                staff.drain(2.0)
                said = staff.transcript[mark:]
                self.assertIn("Zaddrtwo shares an address with Zaddrone: 2 players on from 203.0.113.77.",
                              said)
                self.assertIn("not proof of one person", said)


if __name__ == "__main__":
    unittest.main()
