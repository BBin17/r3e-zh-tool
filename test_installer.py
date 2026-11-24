import hashlib
import json
import os
import struct
import tempfile
import unittest
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import ANY, Mock, call, patch

import app
from r3e_jca import ANCHOR, SECTION_ORDER, JcaFile, Localization, Section


def sample_localization(text: str) -> Localization:
    return Localization(b"sample preamble", [
        Section(lang, [(ANCHOR, "menu"), ("$Sample", text)]) for lang in SECTION_ORDER
    ])


class InstallerTest(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory(prefix="r3e-installer-")
        self.addCleanup(workspace.cleanup)
        self.root = Path(workspace.name)
        self.installer = app.Installer(self.root, Mock(), Mock())
        self.path = self.installer.loc_path
        self.path.parent.mkdir(parents=True)
        JcaFile(2, sample_localization("one").rebuild()).dump(self.path)
        self.original = self.path.read_bytes()
        self.table = self.root / "translations.csv"
        self.table.write_text("key,zh\n$Sample,一\n", encoding="utf-8")
        self.build = "100"
        self.enterContext(patch.object(app, "game_running", return_value=False))
        self.enterContext(patch.object(app, "steam_build_id", side_effect=lambda _: self.build))

    def test_reinstall_preserves_original_backup_and_other_languages(self):
        self.assertEqual(self.installer.install(self.table)["applied"], 2)
        self.table.write_text("key,zh\n$Sample,二\n", encoding="utf-8")
        self.assertEqual(self.installer.install(self.table)["applied"], 2)
        self.assertTrue(self.installer.inspect()["restorable"])
        loc = Localization.load(JcaFile.load(self.path))
        for section in loc.sections:
            text = "二" if section.lang in app.INSTALL_LANGS else "one"
            self.assertEqual(section.pairs, [(ANCHOR, "menu"), ("$Sample", text)])
        self.assertEqual(len(list(self.installer.backup_dir.glob("*.jca"))), 1)
        self.installer.restore()
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertFalse(self.installer.inspect()["restorable"])

    def test_signed_translation_pack_with_tamper_rejection(self):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from release_signing import make_pack
        import translation_pack

        make_pack(Ed25519PrivateKey.generate(), self.table, self.root)
        pack = self.root / translation_pack.PACK_NAME
        original_pack = pack.read_bytes()
        with patch.object(translation_pack, "bundled_path",
                          return_value=self.root / translation_pack.PUBLIC_KEY_NAME):
            pack.write_bytes(original_pack[:-1] + bytes([original_pack[-1] ^ 1]))
            with self.assertRaisesRegex(ValueError, "签名验证失败"):
                self.installer.install(pack)
            self.assertEqual(self.path.read_bytes(), self.original)

            pack.write_bytes(original_pack)
            self.assertEqual(self.installer.install(pack)["applied"], 2)
            self.assertTrue(self.installer.install(pack)["cached"])

    def test_hud_upgrade_preserves_original_messages_for_restore(self):
        from rr_hud import bundle, recipe

        hud = self.path.parent.parent / "Cosmo" / "hud"
        backups = self.path.parent / bundle.BACKUP_DIR
        backups.mkdir()
        originals = {name: f"original {name}".encode() for name in recipe.PANELS}
        old_receipt = {"hud": str(hud.resolve()), "hud_version": 2,
                       "panels": {}, "font": bundle._hash(b"old font")}
        for name, original in originals.items():
            panel = hud / name
            (panel / "fonts").mkdir(parents=True)
            if name == "message_log":
                (panel / "manifest.json").write_bytes(original)
                continue
            localized = f"old {name}".encode()
            (panel / "manifest.json").write_bytes(localized)
            (panel / "fonts" / bundle.CUSTOM_FONT).write_bytes(b"old font")
            (backups / f"{name}.json").write_bytes(original)
            old_receipt["panels"][name] = {"original": bundle._hash(original),
                                           "localized": bundle._hash(localized)}
        (backups / recipe.RECEIPT).write_text(json.dumps(old_receipt), encoding="utf-8")

        def prepare(stage, paths, *, labels):
            self.assertEqual({name: path.read_bytes() for name, path in paths.items()}, originals)
            (stage / bundle.CUSTOM_FONT).write_bytes(b"new font")
            checksums = {}
            for name, original in originals.items():
                localized = f"new {name}".encode()
                (stage / f"{name}.json").write_bytes(localized)
                checksums[name] = {"original": bundle._hash(original), "localized": bundle._hash(localized)}
            return checksums

        with patch.object(recipe, "game_running", return_value=False), \
             patch.object(recipe, "font_available", return_value=True), \
             patch.object(recipe, "prepare", side_effect=prepare) as build, \
             patch.object(recipe, "translate_panel", return_value={"fonts": {}}):
            bundle.prepare_launch(self.root, running=False)
            self.assertEqual(bundle._receipt(hud.resolve(), backups)["hud_version"], bundle.HUD_VERSION)
            self.assertEqual((hud / "message_log" / "manifest.json").read_bytes(), b"new message_log")
            bundle.prepare_launch(self.root, running=False)
            build.assert_called_once()
            bundle.restore(self.root)
        self.assertFalse(backups.exists())
        for name, original in originals.items():
            self.assertEqual((hud / name / "manifest.json").read_bytes(), original)
            self.assertFalse((hud / name / "fonts" / bundle.CUSTOM_FONT).exists())

    def test_uninstall_requires_verified_game_restore_and_allows_retry(self):
        from rr_hud import bundle, recipe

        self.installer.install(self.table)
        general = self.path.parent
        hud = general.parent / "Cosmo" / "hud"
        backups = general / bundle.BACKUP_DIR
        backups.mkdir()
        hud_original = b"original HUD manifest"
        hud_localized = b"localized HUD manifest"
        font = b"localized font"
        original_hash = hashlib.sha256(hud_original).hexdigest()
        localized_hash = hashlib.sha256(hud_localized).hexdigest()
        panels = {}
        for name in recipe.PANELS:
            panel = hud / name
            (panel / "fonts").mkdir(parents=True)
            (panel / "fonts" / bundle.CUSTOM_FONT).write_bytes(font)
            (panel / "manifest.json").write_bytes(hud_localized)
            (backups / f"{name}.json").write_bytes(hud_original)
            panels[name] = {"original": original_hash, "localized": localized_hash}
        (backups / recipe.RECEIPT).write_text(json.dumps({
            "hud": str(hud.resolve()), "hud_version": bundle.HUD_VERSION, "panels": panels,
            "font": hashlib.sha256(font).hexdigest(),
        }), encoding="utf-8")

        first = backups / f"{next(iter(panels))}.json"
        first.write_bytes(b"damaged backup")
        setup = app.setup_tool
        with patch.object(setup, "tool_running", return_value=False), \
             patch.object(recipe, "game_running", return_value=False), \
             patch("rr_menu.engine.WatchEvent") as watch, \
             patch.object(app, "uninstall_game_dirs", return_value=[self.root]), \
             patch.object(setup.messagebox, "askyesno", return_value=True), \
             patch.object(setup.messagebox, "showerror") as error, \
             patch.object(setup.messagebox, "showinfo"), \
             patch.object(setup, "uninstall") as remove:
            watch.return_value.own.return_value = nullcontext()
            self.assertEqual(setup.uninstall_interactive(app.restore_before_uninstall, parent=None), 1)
            remove.assert_not_called()
            self.assertIn("HUD 原版备份校验失败", error.call_args.args[1])
            self.assertEqual(self.path.read_bytes(), self.original)

            first.write_bytes(hud_original)

            def verify_restored():
                self.assertEqual(self.path.read_bytes(), self.original)
                for name in panels:
                    panel = hud / name
                    self.assertEqual((panel / "manifest.json").read_bytes(), hud_original)
                    self.assertFalse((panel / "fonts" / bundle.CUSTOM_FONT).exists())

            remove.side_effect = verify_restored
            self.assertEqual(setup.uninstall_interactive(app.restore_before_uninstall, parent=None), 0)
            remove.assert_called_once()

    def test_uninstall_blocks_while_game_is_running(self):
        setup = app.setup_tool
        with patch.object(app, "game_running", return_value=True), \
             patch.object(setup.messagebox, "askyesno", return_value=True), \
             patch.object(setup.messagebox, "showerror") as error, \
             patch.object(app, "uninstall_game_dirs") as detect, \
             patch.object(setup, "uninstall") as remove:
            self.assertEqual(setup.uninstall_interactive(app.restore_before_uninstall, parent=None), 1)
            self.assertIn("退出 RaceRoom", error.call_args.args[1])
            detect.assert_not_called()
            remove.assert_not_called()

    def test_refuses_restore_over_new_official_file(self):
        self.installer.install(self.table)
        self.build = "200"
        JcaFile(2, sample_localization("new build").rebuild()).dump(self.path)
        updated = self.path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "Steam"):
            self.installer.restore()
        self.assertEqual(self.path.read_bytes(), updated)

    def test_refuses_restore_when_build_changed_without_changing_file(self):
        self.installer.install(self.table)
        after = self.path.read_bytes()
        self.build = "200"
        with self.assertRaisesRegex(RuntimeError, "Steam"):
            self.installer.restore()
        self.assertEqual(self.path.read_bytes(), after)

    def test_preserves_legacy_backups_without_guessing_their_origin(self):
        self.installer.install(self.table)
        after = self.path.read_bytes()
        directory = self.installer.backup_dir
        manifest = directory / "manifest.json"
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["installs"] = [{"output_sha256": hashlib.sha256(after).hexdigest()}]
        manifest.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "Steam"):
            self.installer.restore()
        self.assertEqual(self.path.read_bytes(), after)
        self.assertEqual((directory / data["backups"][0]["file"]).read_bytes(), self.original)

    def test_backup_that_fails_checksum_never_replaces_game_file(self):
        self.installer.install(self.table)
        after = self.path.read_bytes()
        next(self.installer.backup_dir.glob("*.jca")).write_bytes(b"corrupted backup")
        with self.assertRaisesRegex(RuntimeError, "校验失败"):
            self.installer.restore()
        self.assertEqual(self.path.read_bytes(), after)

    def test_rejects_source_only_csv_and_unmatched_keys(self):
        for csv_text, reason in (("key,source\n$Sample,not a translation\n", "译文列"),
                                 ("key,zh\n$Unmatched,中文\n", "没有匹配")):
            with self.subTest(csv_text=csv_text):
                self.table.write_text(csv_text, encoding="utf-8")
                with self.assertRaisesRegex((RuntimeError, ValueError), reason):
                    self.installer.install(self.table)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertFalse((self.installer.backup_dir / "manifest.json").exists())

    def test_identical_translations_skip_write(self):
        self.table.write_text("key,target\n$Sample,one\n", encoding="utf-8")
        with patch.object(app.os, "replace", wraps=os.replace) as replace:
            self.assertEqual(self.installer.install(self.table)["applied"], 0)
        replace.assert_not_called()
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_unchanged_install_skips_decoding_after_restart(self):
        self.installer.install(self.table)
        fresh = app.Installer(self.root, Mock(), Mock())
        with patch.object(JcaFile, "from_bytes", side_effect=AssertionError("decoded unchanged JCA")):
            result = fresh.install(self.table)
            info = fresh.inspect()
        self.assertEqual(result, {"applied": 0, "cached": True})
        self.assertTrue(info["restorable"])
        self.assertEqual((info["pairs"], info["cjk"]), (2, 1))

    def test_legacy_install_is_verified_once_without_rewriting_game_file(self):
        self.installer.install(self.table)
        manifest = self.installer._manifest()
        manifest.pop("localization_match")
        self.installer._save_manifest(manifest)
        mtime = self.path.stat().st_mtime_ns
        with patch.object(JcaFile, "from_bytes", wraps=JcaFile.from_bytes) as decode:
            self.assertEqual(self.installer.install(self.table), {"applied": 0})
            decode.assert_called_once()
        with patch.object(JcaFile, "from_bytes", side_effect=AssertionError("decoded migrated JCA")):
            self.assertTrue(self.installer.install(self.table)["cached"])
        self.assertEqual(self.path.stat().st_mtime_ns, mtime)
        self.assertEqual(len(list(self.installer.backup_dir.glob("*.jca"))), 1)

    def test_changed_build_rechecks_even_when_file_bytes_are_identical(self):
        self.installer.install(self.table)
        self.build = "200"
        with patch.object(JcaFile, "from_bytes", wraps=JcaFile.from_bytes) as decode:
            self.assertEqual(self.installer.install(self.table), {"applied": 0})
            decode.assert_called_once()
        self.assertTrue(self.installer.install(self.table)["cached"])

    def test_restore_then_reinstall_reuses_one_backup(self):
        self.installer.install(self.table)
        backup = next(self.installer.backup_dir.glob("*.jca"))
        backup_mtime = backup.stat().st_mtime_ns
        for build in ("100", "100", "200"):
            self.assertEqual(self.installer.restore(), backup.name)
            self.build = build
            self.assertFalse(self.installer.inspect()["patched"])
            self.assertEqual(self.installer.install(self.table)["applied"], 2)
        self.assertEqual(self.installer.restore(), backup.name)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(list(self.installer.backup_dir.glob("*.jca")), [backup])
        self.assertEqual(backup.stat().st_mtime_ns, backup_mtime)
        self.assertEqual(len(self.installer._manifest()["backups"]), 1)

    def test_changed_original_replaces_old_backup_after_install(self):
        self.installer.install(self.table)
        self.installer.restore()
        self.build = "200"
        JcaFile(2, sample_localization("new original").rebuild()).dump(self.path)
        new_original = self.path.read_bytes()
        self.installer.install(self.table)
        self.assertEqual([path.read_bytes() for path in self.installer.backup_dir.glob("*.jca")], [new_original])
        self.installer.restore()
        self.assertEqual(self.path.read_bytes(), new_original)

    def test_reinstall_and_restore_use_valid_copy_if_duplicate_is_corrupt(self):
        self.installer.install(self.table)
        name = self.installer.restore()
        duplicate = self.installer.backup_dir / "broken-duplicate.jca"
        duplicate.write_bytes(b"corrupt")
        manifest = self.installer._manifest()
        manifest["backups"].append({**manifest["backups"][0], "file": duplicate.name})
        self.installer._save_manifest(manifest)
        self.installer.install(self.table)
        self.assertEqual(self.installer.restore(), name)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(len(list(self.installer.backup_dir.glob("*.jca"))), 2)
        self.assertEqual(duplicate.read_bytes(), b"corrupt")
        self.assertEqual(len(self.installer._manifest()["backups"]), 1)

    def test_cached_launch_keeps_the_latest_valid_registered_copy(self):
        self.installer.install(self.table)
        manifest = self.installer._manifest()
        original = self.installer.backup_dir / manifest["backups"][0]["file"]
        newer = self.installer.backup_dir / "newer-backup.jca"
        newer.write_bytes(self.original)
        unrelated = self.installer.backup_dir / "unregistered.jca"
        unrelated.write_bytes(self.original)
        manifest["backups"].append({**manifest["backups"][0], "file": newer.name})
        self.installer._save_manifest(manifest)

        self.assertTrue(self.installer.install(self.table)["cached"])
        self.assertFalse(original.exists())
        self.assertEqual(self.installer._manifest()["backups"], [manifest["backups"][-1]])
        self.assertEqual(self.installer.restore(), newer.name)
        self.assertTrue(unrelated.exists())

    def test_original_backup_stays_if_replacing_the_game_file_fails(self):
        self.installer.install(self.table)
        old = next(self.installer.backup_dir.glob("*.jca"))
        self.installer.restore()
        self.build = "200"
        JcaFile(2, sample_localization("new original").rebuild()).dump(self.path)
        replace = os.replace

        def fail_game_replace(source, target):
            if target == self.path:
                raise PermissionError("game file locked")
            return replace(source, target)

        with patch.object(app.os, "replace", side_effect=fail_game_replace):
            with self.assertRaisesRegex(PermissionError, "game file locked"):
                self.installer.install(self.table)
        self.assertEqual(old.read_bytes(), self.original)
        self.assertEqual(len(self.installer._manifest()["backups"]), 2)

    def test_install_leaves_file_intact_if_manifest_write_fails(self):
        with patch.object(self.installer, "_save_manifest", side_effect=OSError("write failed")):
            with self.assertRaisesRegex(OSError, "write failed"):
                self.installer.install(self.table)
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])
        saved = list(self.installer.backup_dir.glob("*.jca"))
        self.assertEqual(len(saved), 1)
        self.installer.install(self.table)
        self.assertEqual(list(self.installer.backup_dir.glob("*.jca")), saved)
        self.assertEqual(self.installer.restore(), saved[0].name)

    def test_restore_leaves_file_intact_if_atomic_replace_fails(self):
        self.installer.install(self.table)
        after = self.path.read_bytes()
        with patch.object(app.os, "replace", side_effect=PermissionError("locked")):
            with self.assertRaisesRegex(PermissionError, "locked"):
                self.installer.restore()
        self.assertEqual(self.path.read_bytes(), after)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])


def _varint(value):
    result = bytearray()
    while value >= 128:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def _int_field(number, value):
    return _varint(number << 3) + _varint(value)


def _bytes_field(number, value):
    return _varint((number << 3) | 2) + _varint(len(value)) + value


class SteamRestoreTest(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory(prefix="r3e-steam-restore-")
        self.addCleanup(workspace.cleanup)
        root = Path(workspace.name)
        self.steamapps = root / "library" / "steamapps"
        self.game = self.steamapps / "common" / "RaceRoom test"
        self.steam = root / "steam"
        self.cache = self.steam / "depotcache"
        self.cache.mkdir(parents=True)
        self.acf = self.steamapps / "appmanifest_211500.acf"
        self.installer = app.Installer(self.game, Mock(), Mock())
        self.path = self.installer.loc_path
        self.path.parent.mkdir(parents=True)
        JcaFile(2, sample_localization("original fixture").rebuild()).dump(self.path)
        self.original = self.path.read_bytes()
        table = root / "translations.csv"
        table.write_text("key,zh\n$Sample,一\n", encoding="utf-8")
        self.enterContext(patch.object(app, "game_running", return_value=False))
        self.enterContext(patch.object(app, "steam_libraries", return_value=[self.steam]))
        self.write_acf(build="100")
        self.installer.install(table)
        self.patched = self.path.read_bytes()
        self.write_acf()
        self.depot = self.write_depot()

    def write_acf(self, build="200", depots=(("9001", "123456789123456789"),), flags="4"):
        installed = "\n".join(f'"{depot}" {{ "manifest" "{manifest}" }}' for depot, manifest in depots)
        self.acf.write_text(f'''"AppState" {{
            "appid" "211500"
            "installdir" "{self.game.name}"
            "buildid" "{build}"
            "StateFlags" "{flags}"
            "InstalledDepots" {{ {installed} }}
        }}''', encoding="utf-8")

    def write_depot(self, contents=None, *, depot=9001, manifest=123456789123456789,
                    embedded_id=None, encrypted=0, duplicate=False, name=None):
        contents = self.original if contents is None else contents
        name = str(app.LOC_REL).upper() if name is None else name
        record = (_bytes_field(1, name.encode() + b"\0") + _int_field(2, len(contents)) +
                  _bytes_field(5, hashlib.sha1(contents).digest()))
        payload = _bytes_field(1, record) * (2 if duplicate else 1)
        metadata = (_int_field(1, embedded_id if embedded_id is not None else depot) +
                    _int_field(2, manifest) + _int_field(4, encrypted))
        sections = ((0x71F617D0, payload), (0x1F4812BE, metadata), (0x1B81B817, b""))
        path = self.cache / f"{depot}_{manifest}.manifest"
        path.write_bytes(b"".join(struct.pack("<II", magic, len(data)) + data for magic, data in sections) +
                         struct.pack("<I", 0x32C415AB))
        return path

    def assert_restore_refused(self):
        self.assertFalse(self.installer.inspect()["restorable"])
        before = self.path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, "Steam 验证游戏文件"):
            self.installer.restore()
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_restore_across_builds_with_verified_unchanged_original(self):
        info = self.installer.inspect()
        self.assertTrue(info["restorable"])
        self.assertTrue(info["steam_verified"])
        self.installer.restore()
        self.assertEqual(self.path.read_bytes(), self.original)
        self.assertFalse(self.installer.inspect()["restorable"])

    def test_restore_legacy_install_record_without_build_or_backup_link(self):
        self.write_acf(build="100")
        manifest = self.installer._manifest()
        manifest["installs"] = [{"output_sha256": hashlib.sha256(self.patched).hexdigest()}]
        self.installer._save_manifest(manifest)
        self.assertTrue(self.installer.inspect()["steam_verified"])
        self.installer.restore()
        self.assertEqual(self.path.read_bytes(), self.original)

    def test_refuses_when_official_file_changed_without_changing_size(self):
        self.write_depot(b"!" + self.original[1:])
        self.assert_restore_refused()

    def test_refuses_over_unrecorded_current_game_file(self):
        JcaFile(2, sample_localization("第三方").rebuild()).dump(self.path)
        self.assert_restore_refused()

    def test_refuses_corrupt_backup_even_if_steam_hash_matches(self):
        next(self.installer.backup_dir.glob("*.jca")).write_bytes(self.patched)
        self.write_depot(self.patched)
        # Use a different current file and record its hash, so only the backup's
        # own checksum check prevents the bytes attested by Steam from being used.
        JcaFile(2, sample_localization("另一份汉化").rebuild()).dump(self.path)
        manifest = self.installer._manifest()
        manifest["installs"] = [{"output_sha256": app.sha256_file(self.path)}]
        self.installer._save_manifest(manifest)
        self.assert_restore_refused()

    def test_refuses_wrong_encrypted_ambiguous_and_off_path_entries(self):
        for options in ({"embedded_id": 9002}, {"encrypted": 1}, {"duplicate": True},
                        {"name": "Other/Localization.jca"}):
            with self.subTest(options=options):
                self.write_depot(**options)
                self.assert_restore_refused()

    def test_refuses_missing_current_cache_and_truncated_manifest(self):
        self.depot.write_bytes(self.depot.read_bytes()[:-1])
        self.assert_restore_refused()
        self.write_depot(manifest=100)
        self.depot.unlink()
        self.assert_restore_refused()

    def test_refuses_multiple_depots_with_same_entry(self):
        self.write_depot(depot=9002, manifest=100)
        self.write_acf(depots=(("9001", "123456789123456789"), ("9002", "100")))
        self.assert_restore_refused()

    def test_refuses_while_steam_app_is_updating(self):
        self.write_acf(flags="260")
        self.assert_restore_refused()

    def test_rechecks_depot_when_manifest_changes_after_staging(self):
        stage = app.staged_file

        def change_steam_manifest(target):
            self.write_depot(manifest=100)
            self.write_acf(depots=(("9001", "100"),))
            return stage(target)

        self.assertTrue(self.installer.inspect()["restorable"])
        with patch.object(app, "staged_file", side_effect=change_steam_manifest):
            with self.assertRaisesRegex(RuntimeError, "Steam 安装清单发生变化"):
                self.installer.restore()
        self.assertEqual(self.path.read_bytes(), self.patched)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])


class DetectionTest(unittest.TestCase):
    def test_detection_failure_keeps_folder_actions_available(self):
        ui = app.App.__new__(app.App)
        ui.busy = False
        ui.detecting = True
        ui.extras = None
        ui.installer = Mock()
        ui.game_dir = None
        ui.saved_translation = False
        ui.default_translations = ui.translations = Path("test.csv")
        ui.diagnostics = app.Diagnostics("0.3.30")
        for name in ("build_label", "status", "btn_folder", "btn_detect", "btn_csv", "btn_open", "btn_default_csv",
                     "basic_state", "basic_summary", "component_summary", "set_progress", "_set_state", "_append_log"):
            setattr(ui, name, Mock())
        ui.stat_vars = {"done": Mock()}
        ui._apply_state({"dir": Path("game"), "error": "broken JCA"})
        ui._set_state.assert_called_once_with("状态读取失败", "broken JCA", app.BAD)
        ui.btn_open.set_enabled.assert_called_once_with(False)
        ui.btn_csv.set_enabled.assert_called_once_with(True)
        ui.btn_folder.set_enabled.assert_called_once_with(True)
        ui.btn_detect.set_enabled.assert_called_once_with(True)
        self.assertIsNone(ui.installer)


class OneClickTest(unittest.TestCase):
    def setUp(self):
        from extra_ui import ExtraControls

        root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.game = root / "steamapps" / "common" / "raceroom racing experience"
        self.game.mkdir(parents=True)
        self.steam = root / "steam.exe"
        self.steam.touch()
        (root / "steamapps" / "appmanifest_211500.acf").touch()
        self.translations = root / "zh-translations.csv"
        self.controls = ExtraControls.__new__(ExtraControls)
        self.controls.app = Mock()
        self.controls.post = Mock()
        self.controls.cancel_menu = Mock()
        self.controls.cancel_menu.is_set.return_value = False
        self.controls.game_running = Mock(return_value=False)
        self.controls.steam_libraries = lambda: [root]
        self.watch = self.enterContext(patch("extra_ui.home_zh.WatchEvent")).return_value
        self.watch.own.return_value = nullcontext("watch handle")
        self.watch.wait.return_value = False
        self.enterContext(patch("extra_ui.home_zh.game_listens_locally", return_value=False))
        self.enterContext(patch("extra_ui.home_zh.load_translation", return_value="translations"))
        self.hud = self.enterContext(patch("extra_ui.hud_bundle.prepare_launch"))
        self.steam_start = self.enterContext(patch("extra_ui.subprocess.Popen"))
        self.menu = self.enterContext(patch("extra_ui.home_zh.apply_pages"))
        self.installer = Mock()
        self.installer.install.return_value = {"applied": 2}

    def test_combined_launch_prepares_both_files_before_starting_steam(self):
        order = Mock()
        order.attach_mock(self.installer.install, "base")
        order.attach_mock(self.hud, "hud")
        order.attach_mock(self.steam_start, "steam")
        order.attach_mock(self.menu, "menu")
        self.controls._launch(self.game, self.installer, self.translations, True)
        self.assertEqual(order.mock_calls, [
            call.base(self.translations, progress=ANY),
            call.hud(self.game, running=False),
            call.steam([str(self.steam), "-applaunch", "211500", "-webdev"], cwd=self.steam.parent),
            call.menu(ANY, "translations", 120, ANY, True, report=ANY, on_pages=ANY),
        ])

    def test_base_failure_waits_for_consent_before_launching_with_menu_and_hud(self):
        self.installer.install.side_effect = RuntimeError("无匹配译文")
        self.controls._launch(self.game, self.installer, self.translations, True)
        self.hud.assert_not_called()
        self.steam_start.assert_not_called()
        self.controls.post.assert_called_with(self.controls._offer_menu_hud_only, self.game, "无匹配译文", True)

        with patch("extra_ui.messagebox.askyesno", return_value=True), \
             patch.object(self.controls, "_start_launch", side_effect=self.controls._launch):
            self.controls.menu_status = Mock()
            self.controls._offer_menu_hud_only(self.game, "无匹配译文")
        self.installer.install.assert_called_once()
        self.hud.assert_called_once_with(self.game, running=False)
        self.steam_start.assert_called_once()

    def test_active_game_prevents_launch_and_restore_from_touching_files(self):
        self.controls.game_running.return_value = True
        self.controls._launch(self.game, self.installer, self.translations, True)
        with self.assertRaisesRegex(RuntimeError, "先退出 RaceRoom"):
            self.controls._restore_game_files(self.game, self.installer)
        self.installer.install.assert_not_called()
        self.installer.inspect.assert_not_called()
        self.hud.assert_not_called()
        self.steam_start.assert_not_called()

    def test_unconnected_menu_keeps_the_successful_base_and_hud_status(self):
        self.controls.preparing = True
        self.controls.stopping = False
        self.controls.menu_status = Mock()
        self.controls.app.basic_patched = True
        error = "未找到可汉化的游戏页面。"

        self.controls._menu_finished(app.Stage.MENU, error)

        self.controls.app.set_component_status.assert_called_once_with(app.Stage.MENU, app.Status.DISCONNECTED)
        self.controls.app._fail.assert_called_once_with(app.Stage.MENU, error, prefix="基础文本已汉化。")
        self.controls.app.auto_detect.assert_called_once_with(silent=True)
        self.assertFalse(self.controls.menu_active)

    def test_restore_continues_with_verified_base_backup_if_hud_fails(self):
        self.installer.inspect.return_value = {"exists": True, "patched": True}
        self.installer.restore.return_value = "Localization-backup.jca"
        with patch("extra_ui.hud_bundle.restore", side_effect=ValueError("HUD 备份不匹配")):
            result, failed = self.controls._restore_game_files(self.game, self.installer)
        self.assertTrue(failed)
        self.watch.stop.assert_called_once()
        self.installer.restore.assert_called_once()
        self.assertIn("网页菜单：已停用汉化", result)
        self.assertIn("赛中 HUD：未完成。HUD 备份不匹配", result)
        self.assertIn("基础文本：已恢复备份 Localization-backup.jca", result)
        for component, error in ((app.Stage.MENU, None), (app.Stage.HUD, "HUD 备份不匹配"),
                                 (app.Stage.BASE, None)):
            self.controls.post.assert_any_call(self.controls.app.record_restore_result, component, error)


if __name__ == "__main__":
    unittest.main()
