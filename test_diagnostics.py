import unittest

from diagnostics import Diagnostics, Stage, Status


class DiagnosticsTest(unittest.TestCase):
    def test_report_uses_typed_fields_instead_of_raw_paths_and_usernames(self):
        diagnostics = Diagnostics("0.3.30")
        diagnostics.set_game_versions("123456789", "0.9.7.123")
        diagnostics.states.update({Stage.BASE: Status.APPLIED, Stage.MENU: Status.DISCONNECTED,
                                   Stage.HUD: Status.READY})
        diagnostics.record(Stage.MENU, r"未找到可汉化的游戏页面 C:\Users\ExampleUser\RaceRoom files")
        diagnostics.record(Stage.DETECT, r"无法读取 \\PRIVATE-SERVER\ExampleUser\RaceRoom 文件")
        diagnostics.record(Stage.BASE, r"未找到译文表：D:\Work\owned-by-ExampleUser.csv。")
        report = diagnostics.report()
        for visible in ("工具版本：v0.3.30", "Steam Build ID：123456789", "游戏程序版本：0.9.7.123",
                        "基础文本：已汉化", "网页菜单：未连接", "赛中 HUD：已就绪",
                        "网页菜单未连接", "检查或更换译文表"):
            self.assertIn(visible, report)
        for private in ("ExampleUser", "PRIVATE-SERVER", "RaceRoom files", "D:\\"):
            self.assertNotIn(private, report)

    def test_version_values_are_validated_and_repeated_issues_are_bounded(self):
        diagnostics = Diagnostics("ExampleUser 0.3.30", local_build=True)
        diagnostics.set_game_versions("STEAM-ACCOUNT", "0.9.7\nC:\\User")
        for stage in (Stage.START, Stage.STEAM, Stage.BASE, Stage.MENU, Stage.MENU):
            diagnostics.record(stage, "unexpected technical detail")
        report = diagnostics.report()
        self.assertIn("本地测试", report)
        self.assertIn("Steam Build ID：未读取", report)
        self.assertNotIn("STEAM-ACCOUNT", report)
        self.assertNotIn("unexpected technical detail", report)
        self.assertNotIn("ExampleUser", report)
        self.assertEqual(len(diagnostics.issues), 3)
        self.assertEqual([issue.stage for issue in diagnostics.issues], [Stage.STEAM, Stage.BASE, Stage.MENU])

    def test_failure_guidance_matches_recoverable_conditions(self):
        diagnostics = Diagnostics("0.3.30")
        cases = (
            (Stage.HUD, "缺少可用于 HUD 的 Windows 简体中文字体。", "简体中文补充字体"),
            (Stage.RESTORE, "赛中 HUD：HUD 原版备份校验失败。", "验证游戏文件"),
            (Stage.STEAM, "未找到 Steam，请先确认 Steam 已安装。", "打开 Steam"),
            (Stage.UPDATE, "发布签名验证失败", "下载更新"),
            (Stage.MENU, "暂时无法汉化 /leaderboards：CDP 调用失败", "重新打开出问题的菜单"),
        )
        for stage, error, action in cases:
            with self.subTest(stage=stage):
                self.assertIn(action, diagnostics.record(stage, error).action)


if __name__ == "__main__":
    unittest.main()
