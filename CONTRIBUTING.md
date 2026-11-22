# 参与 R3E 汉化工具维护

这个工具由我在业余时间维护。欢迎帮忙报漏翻、建议译文、修复菜单适配或复测问题。

## 反馈和复测

- [翻译反馈](https://github.com/BBin17/r3e-zh-tool/issues/new?template=translation.md)请附游戏菜单路径、漏翻位置或截图，知道合适译法也可以一起写。
- [故障反馈](https://github.com/BBin17/r3e-zh-tool/issues/new?template=bug.md)请附复现步骤，并粘贴「操作日志 → 复制诊断」得到的信息。旧版可以手动写工具版本和游戏版本。
- 如果你在复测某个 Issue，请在同一条 Issue 里回复使用的版本、复测步骤和结果。

## 提交源码或译文

从 GitHub fork 本仓库，在自己的分支修改后提交 Pull Request。说明改动涉及哪个页面、原先的问题及复测结果。有对应的 Issue 时请链接到它。

基础译文在 [`translations/zh-translations.csv`](translations/zh-translations.csv)，包含 `key,zh` 两列。请保留已有的键并编辑 `zh` 列。网页菜单译文在 `rr_menu/assets/`。涉及多个译文时，尽量按页面拆分提交。项目收录有权公开的改动。

## 在 Windows 运行源码

安装 Python 3.11 或更新版本，在仓库目录运行：

```powershell
python -m pip install -r requirements-build.txt
python app.py
```

从干净仓库运行时，软件默认使用仓库里的基础译文表。也可以通过「游戏与文件 → 更换译文表」选择自己的 `key,zh` CSV，或用[单条译文示例](examples/zh-translations.csv)验证安装流程。

运行自动化测试：

```powershell
python -m unittest test_diagnostics test_installer test_updater
```

## 版本编号与发布

每一轮测试和发布都沿用同一套编号。每次提供新的本地测试包，都从上一个已出包的版本号继续递增，将 `setup_tool.py` 中 `APP_VERSION` 的第三段加 1，并按版本号分目录保留测试包。

测试包验收通过后，从同一份源码用相同版本号构建正式安装包并发布。其余测试包留在本地，已经用于出包的版本号以后也不再分配给其他构建。

例如从 `0.3.30` 开始，先后测试 `0.3.31`、`0.3.32`、`0.3.33`。如果 `0.3.33` 通过验收，就直接发布 `v0.3.33`，下一轮从 `0.3.34` 继续。

维护者正式签名时使用 `release_signing.py manifest ... --official`。从 v0.3.30 之后数五次 GitHub 公开正式发布，前五次继续附上 7 字节的兼容 CSV，第六次起省略。草稿、预览版和本地测试包都不计数。退役时在发布说明中请 v0.3.27 及以前的用户覆盖安装一次。

## 构建本地测试安装包

使用自己生成的测试私钥，放在仓库目录外：

```powershell
python release_signing.py --key ../r3e-local-test.pem init-key
python release_signing.py --key ../r3e-local-test.pem pack translations/zh-translations.csv release
python build_release.py --local-test
```

第一次生成私钥后，后续复用同一把测试私钥。产物位于 `dist/local-test`，测试版使用独立安装目录。也可以传入自己的 `key,zh` CSV 来构建。项目的正式版本由维护者验证和签名后发布。
