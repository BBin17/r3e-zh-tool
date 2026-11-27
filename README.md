# R3E 汉化工具

RaceRoom Racing Experience（R3E）的非官方中文界面汉化工具。

开发者 [BBin17](https://github.com/BBin17)。

QQ 交流群 **1128386065**。

主窗口的「一键汉化并启动」会准备基础文本、网页菜单和赛中 HUD 汉化，并通过 Steam 启动游戏。[查看最新发布说明](https://github.com/BBin17/r3e-zh-tool/releases/latest)

## 下载与安装

1. 在 [Releases](https://github.com/BBin17/r3e-zh-tool/releases/latest) 下载 `R3E-ZH-Tool-Setup.exe`。
2. 运行安装包。程序安装到 `%LOCALAPPDATA%\Programs\R3E-ZH-Tool`，并创建开始菜单和桌面快捷方式。
3. 用安装包覆盖升级时，请先退出正在运行的旧版汉化工具。安装或还原游戏汉化前，请先退出游戏。

### 卸载

退出游戏和汉化工具后，从 Windows「设置 → 应用 → 已安装的应用」或「控制面板 → 程序和功能」卸载 **R3E 汉化工具**。卸载程序会先停用网页菜单汉化并恢复基础文本和赛中 HUD，确认原版状态后再移除工具和快捷方式。恢复失败时会显示原因并保留工具，以便修复后重试。

旧版可先覆盖安装新版，再使用 Windows 的卸载入口。

## 使用

1. 打开工具，它会自动查找 Steam 游戏目录。展开「游戏与文件」可以手动选择目录、重新检测或更换译文表。
2. 退出游戏后点「一键汉化并启动」。已校验的游戏版本、基础文本文件和译文表均未变化时，工具会跳过解密和逐条比对。工具会在游戏目录下的 `zh-patch-backups` 复用或创建适用的原版备份，确认可恢复后只保留这一份已登记的备份。
3. 工具准备赛中 HUD 后会通过 Steam 启动 RaceRoom。游玩时请保持工具开启，让网页菜单自动汉化。如果基础文本准备失败，可以按提示保留当前基础文本，仅启用菜单和 HUD 后启动。
4. 要还原时，先退出游戏，再点「恢复原版」。工具会分别报告网页菜单、HUD 和基础文本的恢复结果。
5. 如果游戏更新后还留有基础文本汉化，工具会尝试用 Steam 本地清单核对旧备份，仅使用与当前官方文件匹配的备份。如果工具提示备份未匹配，请通过 Steam 验证游戏文件，再重新安装汉化。

安装和恢复前，工具会检查游戏是否正在运行。程序版本显示在窗口标题和主界面上方。在「游戏与文件」中点击「创建桌面快捷方式」可创建或刷新快捷方式。

如果网页菜单的 8080 端口被其他程序占用，工具会显示进程名。可选择跳过网页菜单，继续应用基础文本和赛中 HUD 后启动游戏。

遇到网页菜单漏翻时，请停在该界面，返回工具点「复制漏翻反馈」，再补充漏翻的文字或操作步骤。「更换译文表」会记住所选文件，也可以点「恢复内置译文」重置。切换译文表后，请在下次一键汉化时应用。

## 检查更新

工具启动后会自动检查 GitHub Releases，也可以手动点「检查更新」。下载更新时会自动选择更快的线路，并验证发布签名和程序的 SHA256。基础译文随程序一起更新，完成后会刷新快捷方式并重新启动。

v0.3.2 至 v0.3.27 在兼容期内可通过软件内的「检查更新」升级。v0.3、v0.3.1、兼容期结束后仍在使用旧版，或软件内升级失败时，请退出工具，然后下载最新 Windows 安装包覆盖安装一次。

## 汉化范围

- **基础文本**：游戏设置、菜单等界面中的 `Localization.jca` 文本。
- **网页菜单**：主页、驾驶、排行榜、竞赛、商店、个人资料、成就、设置及向导、回放列表及即时回放、车库、进站预设、车辆调教和暂停菜单中的已适配内容。赛道名称保留原文。
- **赛中 HUD**：部分计时、圈速状态、进站限速、排名和多功能显示屏文本。

工具只替换英文（en_GB）和西班牙文（es_ES）两个语言段。这是实测能正常显示中文的组合，替换全部语言段会导致设置页出现 `$KEY` 占位符。

## 注意

本工具是非官方项目。基础文本和 HUD 汉化会在游戏退出后修改本地文件，并保留原版备份。网页菜单通过 RaceRoom 的 `-webdev` 选项启动，译文通过本机回环连接应用。HUD 字形使用 Windows 已安装的中文字体生成。

## 源码与授权

R3E 汉化工具源码已在 [GitHub 公开仓库](https://github.com/BBin17/r3e-zh-tool)提供，工具免费使用，赞助自愿。原版和二次开发版本可免费分发，二次开发时请注明来源。详见[使用与二次开发条款](LICENSE.md)。欢迎按[贡献指南](CONTRIBUTING.md)提交译文、菜单适配和复测反馈。

## 支持项目

我在业余时间开发和维护这个工具。如果它帮到你，欢迎[自愿赞助 ☕](docs/donate.md)，支持后续的汉化、适配和测试。

| 微信支付 | 支付宝 |
| :---: | :---: |
| <img src="docs/images/donate/wechat-card.png" alt="微信支付收款码" width="320"> | <img src="docs/images/donate/alipay-card.png" alt="支付宝收款码" width="320"> |

## 开发者

在 Windows 上使用 Python 3.11 或更新版本。先安装项目依赖。

```bash
python -m pip install -r requirements-build.txt
```

源码运行：

```bash
python app.py
```

构建默认使用仓库里的[基础译文表](translations/zh-translations.csv)，维护者可用 `make_publish_csv.py` 从本地工作表导出 `key,zh` CSV。签名电脑需要 Python 3.11+、`cryptography` 和 `pyinstaller`。第一次使用时在源码目录外生成 Ed25519 私钥并安全备份。后续发布复用同一把私钥，已安装的工具使用内置公钥验签。

```bash
python release_signing.py --key /path/to/release-signing.pem init-key
python release_signing.py --key /path/to/release-signing.pem pack translations/zh-translations.csv release
```

将生成的 `zh-translations.r3ezh` 和 `release-signing.pub` 放入 Windows 工作目录的 `release`。PyInstaller 会生成带内置签名译文包的 EXE。网页菜单继续一次载入各页译文，供游戏切页时直接使用。

```bash
python build_release.py
```

将构建生成的两个 EXE 放到签名电脑的干净目录，再生成签名清单。标签要和程序版本一致。

```bash
python release_signing.py --key /path/to/release-signing.pem manifest dist/release v0.3.31 --official
```

### 发布新版

代码贡献在公开仓库接收。发布前请核对公开仓库包含对应的源码，正式构建使用维护者本地准备的完整译文和发布签名私钥。用户下载与软件内检查更新统一使用 [BBin17/r3e-zh-tool 的 Releases](https://github.com/BBin17/r3e-zh-tool/releases)。

在公开仓库创建 Release 草稿，标签指向公开仓库的 `main`。上传 `R3E-ZH-Tool-Setup.exe`、`R3E-ZH-Tool.exe`、`SHA256SUMS.txt` 和 `SHA256SUMS.sig`。如果签名阶段生成了只有表头的 `zh-translations.csv`，一并上传。GitHub 自动生成的 Source code 压缩包只有公开下载仓库中的内容。

从 v0.3.30 之后数五次公开正式发布，前五次都附兼容 CSV，第六次起省略。`manifest --official` 从 GitHub 核对已发布的正式版本。跳过的版本号、本地测试包、草稿和预览版都不计入。退役时在新版发布说明中提醒 v0.3.27 及以前的用户覆盖安装一次。

公开仓库保留历次正式 Release。自动清理工作流已停用。恢复历史版本时保留原发布附件，不将历史版设为 Latest。
