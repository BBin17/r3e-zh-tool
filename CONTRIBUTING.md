# 参与 R3E 汉化工具维护

这个工具由我在业余时间维护。欢迎帮忙报漏翻、建议译文、修复菜单适配或复测问题。

## 反馈和复测

- [翻译反馈](https://github.com/BBin17/r3e-zh-tool/issues/new?template=translation.md)请附游戏菜单路径、漏翻位置或截图，知道合适译法也可以一起写。
- [故障反馈](https://github.com/BBin17/r3e-zh-tool/issues/new?template=bug.md)请附工具版本、游戏版本、复现步骤和相关操作日志。
- 如果你在复测某个 Issue，请在同一条 Issue 里回复使用的版本、复测步骤和结果。

## 提交源码或译文

从 GitHub fork 本仓库，在自己的分支修改后提交 Pull Request。说明改动涉及哪个页面、原先的问题及复测结果。有对应的 Issue 时请链接到它。

网页菜单译文在 `rr_menu/assets/`。涉及多个译文时，尽量按页面拆分提交。基础文本的反馈可以直接写在 Issue 里；如果知道对应的键，也可以附两列的 `key,zh` 示例。项目收录有权公开的改动。

## 在 Windows 运行源码

安装 Python 3.11 或更新版本，在仓库目录运行：

```powershell
python -m pip install -r requirements-build.txt
python app.py
```

可以通过「游戏与文件 → 更换译文表」选择 [示例 CSV](examples/zh-translations.csv) 来验证基础文本安装流程。示例只有一条译文，正式安装包带有完整基础译文。网页菜单和赛中 HUD 的适配源码在仓库中。

运行自动化测试：

```powershell
python -m unittest test_installer test_updater
```

## 构建本地测试安装包

安装 Visual Studio Build Tools 的 C++ 构建工具。使用自己生成的测试私钥，放在仓库目录外：

```powershell
python release_signing.py --key ../r3e-local-test.pem init-key
python release_signing.py --key ../r3e-local-test.pem pack examples/zh-translations.csv release
python build_release.py --local-test
```

第一次生成私钥后，后续复用同一把测试私钥。产物位于 `dist/local-test`，测试版使用独立安装目录。测试需要更多基础译文时，可以改用自己准备的 `key,zh` CSV。项目的正式版本由维护者验证和签名后发布。
