"""Shareable diagnostics built from safe fields, never from raw logs."""
from collections import deque
from dataclasses import dataclass
from enum import StrEnum
import re


class Stage(StrEnum):
    DETECT = "检测游戏"
    START = "启动检查"
    BASE = "基础文本"
    MENU = "网页菜单"
    HUD = "赛中 HUD"
    STEAM = "Steam 启动"
    RESTORE = "恢复原版"
    UPDATE_CHECK = "检查更新"
    UPDATE = "下载安装更新"


class Status(StrEnum):
    UNKNOWN = "待检测"
    ABSENT = "未安装"
    INACTIVE = "未启用"
    PREPARING = "处理中"
    WAITING = "等待连接"
    SKIPPED = "本次跳过"
    APPLIED = "已汉化"
    ENABLED = "已启用"
    READY = "已就绪"
    FAILED = "未完成"
    DISCONNECTED = "未连接"
    ORIGINAL = "原版"
    CHECK = "待核对"


COMPONENTS = (Stage.BASE, Stage.MENU, Stage.HUD)
RESTART_GAME = "请完全退出 RaceRoom，再点「一键汉化并启动」。"
SELECT_GAME = "展开「游戏与文件」，选择 Steam 里的 RaceRoom 安装目录。"
VERIFY_GAME = "退出游戏后，在 Steam 中验证游戏文件的完整性。"
CHECK_TRANSLATIONS = "展开「游戏与文件」，检查或更换译文表后重试。"
SEND_DIAGNOSTICS = "点「复制诊断」，把信息发给维护者。"
INSTALLER = "从项目的 GitHub 发布页下载 Windows 安装包覆盖安装。"

FALLBACKS = {
    Stage.DETECT: ("游戏状态读取失败", "确认游戏磁盘可访问，在「游戏与文件」中点「重新检测」。"),
    Stage.START: ("启动检查未通过", SELECT_GAME),
    Stage.BASE: ("基础文本未能汉化", CHECK_TRANSLATIONS),
    Stage.MENU: ("网页菜单未连接", RESTART_GAME),
    Stage.HUD: ("赛中 HUD 准备失败", "退出游戏后从工具重试。再次失败时，" + SEND_DIAGNOSTICS),
    Stage.STEAM: ("Steam 未能启动游戏", "打开 Steam 并确认 RaceRoom 可启动，退出游戏后从工具重试。"),
    Stage.RESTORE: ("恢复原版未完成", "查看操作日志确认未恢复的项目。" + SEND_DIAGNOSTICS),
    Stage.UPDATE_CHECK: ("暂时查不到新版", "确认能打开 GitHub 发布页，再点「检查更新」。"),
    Stage.UPDATE: ("更新未能安装", INSTALLER),
}


@dataclass(frozen=True)
class Issue:
    stage: Stage
    summary: str
    action: str

    @property
    def notice(self) -> str:
        return f"{self.summary}。{self.action}"


def issue_for(stage: Stage, details: str) -> Issue:
    # Only copy recognized fields from exception text, which can contain personal paths.
    port = re.fullmatch(r"网页菜单端口 8080 被占用（([^（）]+)）", details)
    if "RaceRoom" in details and any(term in details for term in ("先退出", "先完全退出", "正在运行", "已在准备期间启动")):
        summary = "RaceRoom 仍在运行"
        action = RESTART_GAME if stage != Stage.RESTORE else "完全退出 RaceRoom，再点「恢复原版」。"
    elif stage in (Stage.START, Stage.STEAM) and "未找到 Steam" in details:
        summary, action = "未找到 Steam", "打开 Steam，确认 RaceRoom 已安装后，从工具启动。"
    elif stage == Stage.DETECT and "未检测到 RaceRoom" in details:
        summary, action = "未检测到 RaceRoom", SELECT_GAME
    elif stage in (Stage.DETECT, Stage.START, Stage.BASE) and any(term in details for term in ("未找到 Localization.jca", "无法读取当前安装的基础文本")):
        summary, action = "缺少游戏文本文件", SELECT_GAME + "已选对目录时，请在 Steam 验证游戏文件。"
    elif stage in (Stage.BASE, Stage.RESTORE) and any(term in details for term in ("匹配的备份", "备份文件校验失败", "原版备份", "备份文件缺失", "HUD 备份不匹配")):
        summary, action = "原版备份不可用或不匹配", VERIFY_GAME
    elif stage == Stage.BASE and any(term in details for term in ("没有匹配条目", "无匹配译文", "预期的游戏语言段")):
        summary, action = "基础译文与游戏版本不匹配", "在「游戏与文件」中点「重新检测」。刚更新游戏时，" + SEND_DIAGNOSTICS
    elif stage == Stage.BASE and any(term in details for term in ("译文表", "CSV 缺少", "有效译文", "发布签名")):
        summary, action = "基础译文表缺失或无效", CHECK_TRANSLATIONS
    elif stage in (Stage.DETECT, Stage.BASE, Stage.HUD, Stage.RESTORE) and (
        "[WinError 5]" in details or "拒绝访问" in details or "Permission denied" in details
    ):
        summary, action = "无法访问游戏文件", "退出 RaceRoom，确认游戏目录可读写后重试。"
    elif stage == Stage.HUD and ("中文字体" in details or "字体缺少字符" in details):
        summary, action = "缺少 HUD 使用的中文字体", "给 Windows 安装简体中文补充字体，退出游戏后重试。"
    elif stage == Stage.HUD and any(term in details for term in ("不兼容", "重新适配", "状态表达式已变化")):
        summary, action = "当前游戏版本的 HUD 需要适配", SEND_DIAGNOSTICS
    elif stage == Stage.HUD and ("备份" in details or "恢复原版" in details):
        summary, action = "HUD 文件或备份需要核对", "退出 RaceRoom，点「恢复原版」并查看结果，再尝试启动。"
    elif stage in (Stage.START, Stage.MENU) and port:
        names = [name for name in port[1].split("、")[:5]
                 if re.fullmatch(r"[\w .()\-]{1,64}\.exe|未知进程", name, re.IGNORECASE)]
        summary = f"网页菜单端口 8080 被占用（{'、'.join(names)}）" if names else "网页菜单端口 8080 被占用"
        action = "关闭占用该端口的程序或停用它的调试功能，再重试网页菜单汉化。"
    elif stage == Stage.MENU and details == "RaceRoom 在网页菜单就绪前已退出。":
        summary, action = "RaceRoom 在网页菜单就绪前已退出", "先在 Steam 中确认游戏能进入主菜单，再从工具启动。"
    elif stage == Stage.MENU and details == "等待 Steam 启动 RaceRoom 超时，未检测到游戏进程。":
        summary, action = "等待 Steam 启动 RaceRoom 超时", "检查 Steam 是否在等待启动确认，再重试。"
    elif stage == Stage.MENU and details.startswith("未找到可汉化的游戏页面。"):
        summary, action = "RaceRoom 已启动，网页菜单尚未连接", "等游戏进入主菜单。仍未连接时，" + SEND_DIAGNOSTICS
    elif stage in (Stage.START, Stage.MENU) and ("调试端口" in details or "游戏汉化已经在运行" in details):
        summary, action = "网页菜单连接被占用或不可用", "退出 RaceRoom 和其他汉化工具窗口，再点「一键汉化并启动」。"
    elif stage == Stage.MENU and ("菜单译文脚本无效" in details or "home-zh.js" in details):
        summary, action = "网页菜单译文资源不可用", INSTALLER
    elif stage == Stage.MENU and details.startswith("暂时无法汉化 "):
        summary, action = "部分网页菜单暂未汉化", "重新打开出问题的菜单。仍显示英文时，" + SEND_DIAGNOSTICS
    elif stage == Stage.UPDATE and ("签名" in details or "校验" in details):
        summary, action = "更新文件未通过校验", "重试「下载更新」。再次失败时，" + INSTALLER
    elif stage in (Stage.UPDATE, Stage.UPDATE_CHECK) and ("无法连接" in details or "下载失败" in details):
        summary, action = "无法从 GitHub 获取更新", "确认能打开 GitHub 发布页，检查网络后重试。"
    else:
        summary, action = FALLBACKS[stage]
    return Issue(stage, summary, action)


def numeric_text(value, pattern: str) -> str:
    return value if isinstance(value, str) and re.fullmatch(pattern, value) else "未读取"


def safe_menu_route(path: str) -> str:
    # Page discovery provides a pathname. Only report route names; hide account and other identifiers.
    if not path.startswith("/") or path.startswith("//"):
        return "未识别页面"
    parts = path.split("/")[1:7]
    for i, part in enumerate(parts):
        private = i > 0 and parts[i - 1].lower() in {"users", "user", "players", "player", "accounts", "account"}
        if private or not re.fullmatch(r"[A-Za-z][A-Za-z_-]{0,31}", part):
            parts[i] = "[已隐藏]"
    return "/" + "/".join(parts)


class Diagnostics:
    def __init__(self, version: str, local_build: bool = False):
        self.version = numeric_text(version, r"[0-9]+(?:\.[0-9]+){1,3}")
        self.local_build = local_build
        self.steam_build = "未读取"
        self.game_version = "未读取"
        self.states = {
            Stage.BASE: Status.UNKNOWN,
            Stage.MENU: Status.INACTIVE,
            Stage.HUD: Status.UNKNOWN,
        }
        self.issues: deque[Issue] = deque(maxlen=3)
        self.menu_pages: tuple[tuple[str, bool], ...] = ()

    def set_menu_pages(self, pages):
        self.menu_pages = tuple(dict.fromkeys((safe_menu_route(path), supported)
                                              for path, supported in pages))[:5]

    def set_game_versions(self, build, exe):
        self.steam_build = numeric_text(build, r"[0-9]{1,15}")
        self.game_version = numeric_text(exe, r"[0-9]+(?:\.[0-9]+){1,3}")

    def record(self, stage: Stage, details: str) -> Issue:
        issue = issue_for(stage, details)
        if not self.issues or self.issues[-1] != issue:
            self.issues.append(issue)
        return issue

    def report(self) -> str:
        edition = "（本地测试）" if self.local_build else ""
        lines = [
            "R3E 汉化工具诊断",
            f"工具版本：v{self.version}{edition}",
            f"Steam Build ID：{self.steam_build}",
            f"游戏程序版本：{self.game_version}",
            *(f"{component}：{self.states[component]}" for component in COMPONENTS),
            "",
            "最近错误：",
        ]
        if self.issues:
            lines.extend(f"- {issue.stage}｜{issue.summary}。{issue.action}" for issue in reversed(self.issues))
        else:
            lines.append("暂无记录")
        return "\n".join(lines)

    def translation_feedback(self) -> str:
        edition = "（本地测试）" if self.local_build else ""
        lines = ["R3E 网页菜单漏翻反馈", f"工具版本：v{self.version}{edition}",
                 f"Steam Build ID：{self.steam_build}", f"游戏程序版本：{self.game_version}",
                 f"网页菜单：{self.states[Stage.MENU]}", "最近检测到的游戏页面："]
        if self.menu_pages:
            lines.extend(f"- {path}（{'已列入适配' if supported else '尚未适配'}）"
                         for path, supported in self.menu_pages)
        else:
            lines.append("未检测到。请补充页面位置或截图。")
        lines.append("漏翻文字或操作步骤：")
        return "\n".join(lines)
