"""Transport details that need no bridge: the request file, the version check, startup cleanup."""
import json
import os
import shutil
import tempfile
import time
import unittest

from davinci_mcp import __version__
from davinci_mcp.transport import REQUEST_KEY, STALE_REQUEST_S, BridgeClient, BridgeNotRunning, request_script


class TransportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cmcp-transport-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.profiles = os.path.join(self.tmp, "Profiles")
        os.makedirs(os.path.join(self.profiles, "Default"))
        self.client = BridgeClient(state_dir=os.path.join(self.tmp, "state"), profiles_dir=self.profiles,
                                   log=lambda line: None)
        self.client.ensure_dirs()   # the server does this at startup

    def write_session(self, bridge_version):
        session = json.dumps({"v": 1, "state": "running", "bridge": bridge_version}).encode().hex()
        with open(os.path.join(self.profiles, "Default", "Fusion.prefs"), "w") as fh:
            fh.write('{ CMCP_Session = "%s", CMCP_Beat = "%d", }\n' % (session, int(time.time())))

    def test_request_script_carries_id_and_hex(self):
        script = request_script("abc123", b'{ v = 1, op = "ping" }')
        self.assertEqual(script, 'fu:SetPrefs("%s", "abc123:%s")\n' % (REQUEST_KEY, b'{ v = 1, op = "ping" }'.hex()))

    def test_request_file_is_replaced_and_removed(self):
        self.client._write_request("first1", b"{}")
        self.client._write_request("second", b"{}")
        with open(self.client.request_file) as fh:
            self.assertIn("second:", fh.read())
        self.client._cleanup("second")
        self.assertEqual(os.listdir(self.client.inbox), [])

    def test_bridge_from_another_release_is_refused(self):
        self.write_session("0.2.0")
        live = self.client.liveness()
        self.assertFalse(live["running"])
        self.assertTrue(live["outdated"])
        with self.assertRaises(BridgeNotRunning) as cm:
            self.client.run("return 1", timeout=1)
        self.assertIn("install.py", str(cm.exception))

    def test_matching_bridge_is_running(self):
        self.write_session(__version__)
        self.assertTrue(self.client.liveness()["running"])

    def test_startup_cleanup_removes_only_stale_entries(self):
        old_folder = os.path.join(self.client.inbox, "oldreq1")
        os.makedirs(os.path.join(old_folder, "0000-ab"))
        with open(self.client.request_file, "w") as fh:
            fh.write("-- fresh\n")
        stale = time.time() - STALE_REQUEST_S - 10
        os.utime(old_folder, (stale, stale))
        self.assertEqual(self.client.startup_cleanup(), 1)
        self.assertEqual(os.listdir(self.client.inbox), ["request.lua"])


if __name__ == "__main__":
    unittest.main()
