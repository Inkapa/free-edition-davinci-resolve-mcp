import importlib
import os
import unittest
from unittest import mock

from davinci_mcp import paths


# The paths are built with os.path, so they only come out as Linux paths on a POSIX host.
@unittest.skipIf(os.name == "nt", "Linux paths are checked on a POSIX host")
class LinuxPathsTest(unittest.TestCase):
    def tearDown(self):
        importlib.reload(paths)

    def _reload_as_linux(self, env):
        with mock.patch("sys.platform", "linux"), mock.patch.dict(os.environ, env, clear=False):
            for name in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "RESOLVE_INSTALL_DIR", "DAVINCI_MCP_FUSCRIPT"):
                if name not in env:
                    os.environ.pop(name, None)
            return importlib.reload(paths)

    def test_defaults_follow_opt_resolve_and_xdg(self):
        linux = self._reload_as_linux({"HOME": "/home/someone"})
        self.assertTrue(linux.LINUX)
        self.assertFalse(linux.WINDOWS)
        self.assertEqual(linux.RESOLVE_SUPPORT, "/home/someone/.local/share/DaVinciResolve")
        self.assertEqual(linux.SCRIPTS_UTILITY, "/home/someone/.local/share/DaVinciResolve/Fusion/Scripts/Utility")
        self.assertEqual(linux.STATE_DIR, "/home/someone/.local/share/DaVinciResolve/ClaudeMCP")
        self.assertEqual(linux.DOCS_DIR, "/opt/resolve/Developer/Scripting")
        self.assertEqual(linux.FUSCRIPT, "/opt/resolve/libs/Fusion/fuscript")
        self.assertEqual(linux.RESOLVE_IMAGE, "/opt/resolve/bin/resolve")

    def test_overrides(self):
        linux = self._reload_as_linux({
            "HOME": "/home/someone",
            "XDG_DATA_HOME": "/data",
            "RESOLVE_INSTALL_DIR": "/usr/local/resolve",
        })
        self.assertEqual(linux.RESOLVE_SUPPORT, "/data/DaVinciResolve")
        self.assertEqual(linux.FUSCRIPT, "/usr/local/resolve/libs/Fusion/fuscript")


if __name__ == "__main__":
    unittest.main()
