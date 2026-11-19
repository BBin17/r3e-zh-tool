import hashlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import translation_pack
import updater


class UpdateFilesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="更新 %R3E_TEST% ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.exe = self.root / updater.EXE_NAME
        self.new_exe = self.root / ".r3e-update-test.exe"
        self.exe.write_bytes(b"old exe")
        self.new_exe.write_bytes(b"new exe")
        self.checksum = hashlib.sha256(b"new exe").hexdigest()

    def test_replaces_program_in_unicode_percent_path(self):
        updater.replace_update_file(self.exe, self.new_exe, self.checksum)
        self.assertEqual(self.exe.read_bytes(), b"new exe")

    def test_failed_exe_replace_keeps_original_file(self):
        with mock.patch.object(os, "replace", side_effect=PermissionError("locked")):
            with self.assertRaises(PermissionError):
                updater.replace_update_file(self.exe, self.new_exe, self.checksum, timeout=0)
        self.assertEqual(self.exe.read_bytes(), b"old exe")
        self.assertEqual({self.exe, self.new_exe}, set(self.root.iterdir()))

    def test_changed_download_cannot_replace_exe(self):
        self.new_exe.write_bytes(b"changed exe")
        with self.assertRaisesRegex(updater.UpdateError, "已变更"):
            updater.replace_update_file(self.exe, self.new_exe, self.checksum)
        self.assertEqual(self.exe.read_bytes(), b"old exe")

    @unittest.skipUnless(os.name == "nt", "Windows update helper")
    def test_helper_creates_shortcut_after_replacement(self):
        import setup_tool

        process = subprocess.Popen([sys.executable, "-c", "pass"])
        process.wait(timeout=10)
        shortcut = self.root / "desktop.lnk"
        start_menu = self.root / "start.lnk"
        start_menu.touch()
        with mock.patch.object(setup_tool, "desktop_shortcut_path", return_value=shortcut), \
             mock.patch.object(setup_tool, "shortcut_paths", return_value=[start_menu, shortcut]), \
             mock.patch.object(setup_tool, "make_shortcut") as create, \
             mock.patch.object(updater.subprocess, "Popen") as launch:
            result = updater.run_update_helper([str(process.pid), str(self.exe),
                                                str(self.new_exe), self.checksum])
        self.assertEqual(result, 0)
        self.assertEqual(create.call_args_list, [mock.call(shortcut, self.exe), mock.call(start_menu, self.exe)])
        self.assertFalse(self.new_exe.exists())
        launch.assert_called_once()

    @unittest.skipUnless(os.name == "nt", "Windows update helper")
    def test_legacy_helper_preserves_installed_csv_and_installs_the_matching_exe(self):
        import setup_tool

        legacy_exe = self.new_exe.rename(self.root / updater.LEGACY_EXE_DOWNLOAD)
        marker = self.root / updater.LEGACY_CSV_DOWNLOAD
        marker.write_bytes(updater.LEGACY_CSV_CONTENT)
        old_csv = self.root / updater.LEGACY_CSV_NAME
        old_csv.write_bytes(b"previous local translation table")
        helper = self.root / "helper.exe"
        helper.write_bytes(legacy_exe.read_bytes())
        process = subprocess.Popen([sys.executable, "-c", "pass"])
        process.wait(timeout=10)
        with mock.patch.object(updater.sys, "executable", str(helper)), \
             mock.patch.object(setup_tool, "register_installed_app"), \
             mock.patch.object(setup_tool, "desktop_shortcut_path", return_value=self.root / "desktop.lnk"), \
             mock.patch.object(setup_tool, "shortcut_paths", return_value=[]), \
             mock.patch.object(setup_tool, "make_shortcut"), \
             mock.patch.object(updater.subprocess, "Popen") as launch:
            result = updater.run_update_helper([str(process.pid), str(self.exe),
                                                str(legacy_exe), str(marker)])
        self.assertEqual(result, 0)
        self.assertEqual(self.exe.read_bytes(), b"new exe")
        self.assertEqual(old_csv.read_bytes(), b"previous local translation table")
        self.assertFalse(marker.exists())
        self.assertFalse(legacy_exe.exists())
        launch.assert_called_once()


class DownloadUpdateTest(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.root = Path(workspace.name)
        self.info = {"tag": "v0.3.28", "assets": {name: name for name in (
            updater.EXE_NAME, updater.SUMS_NAME, updater.SUMS_SIGNATURE_NAME)}}
        self.exe_contents = b"new exe"
        digest = hashlib.sha256(self.exe_contents).hexdigest()
        self.manifest = (updater.manifest_header(self.info["tag"]) + f"{digest}  {updater.EXE_NAME}\n").encode()
        key = Ed25519PrivateKey.generate()
        self.signature = key.sign(translation_pack.MANIFEST_DOMAIN + self.manifest)
        pub = self.root / translation_pack.PUBLIC_KEY_NAME
        pub.write_bytes(key.public_key().public_bytes_raw())
        self.enterContext(mock.patch.object(translation_pack, "bundled_path", return_value=pub))
        self.enterContext(mock.patch.object(updater, "_read_small", side_effect=self.read_small))
        self.request_mock = self.enterContext(mock.patch.object(updater, "_request", side_effect=self.request))

    def read_small(self, name):
        return {updater.SUMS_NAME: self.manifest, updater.SUMS_SIGNATURE_NAME: self.signature}[name]

    def request(self, name, timeout):
        response = io.BytesIO(self.exe_contents)
        response.headers = {"Content-Length": str(len(self.exe_contents))}
        return response

    def test_download_after_manifest_verification(self):
        downloaded = updater.download_update(self.info, self.root)
        self.assertEqual(downloaded["exe"].read_bytes(), self.exe_contents)
        self.assertEqual(downloaded["sha256"], hashlib.sha256(self.exe_contents).hexdigest())

    def test_missing_signature_is_rejected_before_download(self):
        del self.info["assets"][updater.SUMS_SIGNATURE_NAME]
        with self.assertRaisesRegex(updater.UpdateError, "SHA256SUMS.sig"):
            updater.download_update(self.info, self.root)
        self.request_mock.assert_not_called()

    def test_modified_manifest_is_rejected_before_download(self):
        self.manifest += b"extra data"
        with self.assertRaisesRegex(updater.UpdateError, "签名验证失败"):
            updater.download_update(self.info, self.root)
        self.request_mock.assert_not_called()

    def test_old_signed_manifest_cannot_be_relabelled(self):
        self.info["tag"] = "v9.0.0"
        with self.assertRaisesRegex(updater.UpdateError, "版本不一致"):
            updater.download_update(self.info, self.root)
        self.request_mock.assert_not_called()

    def test_wrong_exe_checksum_removes_download(self):
        self.exe_contents += b"unexpected bytes"
        with self.assertRaisesRegex(updater.UpdateError, "校验失败"):
            updater.download_update(self.info, self.root)
        self.assertEqual(list(self.root.glob("*.exe")), [])


if __name__ == "__main__":
    unittest.main()
