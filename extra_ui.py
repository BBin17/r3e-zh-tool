"""Coordinate the one-click RaceRoom localization and Steam launch."""
from pathlib import Path
import subprocess
import threading
from tkinter import messagebox

import websocket

from diagnostics import Stage, Status, issue_for
from rr_hud import bundle as hud_bundle
from rr_hud import recipe as hud_recipe
from rr_menu import engine as home_zh


def probe() -> None:
    script = home_zh.load_translation()
    if not script or '/* TRANSLATIONS */' in script:
        raise ValueError('菜单译文未正确打包。')
    hud_recipe.probe_font()


def restore_base_text(installer):
    if installer is None:
        raise RuntimeError('无法读取基础文本状态，请重新检测游戏。')
    info = installer.inspect()
    if not info['exists']:
        raise RuntimeError('未找到 Localization.jca，请通过 Steam 验证游戏文件。')
    if not info['patched']:
        return '未检测到已安装的基础文本汉化'
    return f'已恢复备份 {installer.restore()}'


def restore_game_files(game, installer, log, report=None):
    results = []
    failed = False
    for component, action in ((Stage.HUD, lambda: hud_bundle.restore(game)),
                              (Stage.BASE, lambda: restore_base_text(installer))):
        error = None
        try:
            result = action()
        except Exception as exc:
            error = str(exc)
            result = f'未完成。{error}'
            failed = True
        if report is not None:
            report(component, error)
        message = f'{component}：{result}'
        log(message)
        results.append(message)
    return results, failed


class ExtraControls:
    def __init__(self, app, launch, restore, steam_libraries, game_running, *, status_color):
        self.app = app
        self.steam_libraries = steam_libraries
        self.game_running = game_running
        self.cancel_menu = threading.Event()
        self.menu_active = False
        self.preparing = False
        self.stopping = False

        self.start_game = app._button(launch, '一键汉化并启动', self.launch_game, 'primary', small=False)
        self.start_game.pack(side='right')
        description = app._row(launch)
        description.pack(side='left', fill='x', expand=True, padx=(0, app.S(14)))
        self.game_status = app._label(description, '正在检测 RaceRoom…', size=14, bold=True, color=status_color)
        self.game_status.pack(anchor='w')
        self.menu_status = app._label(description, '基础文本、网页菜单和赛中 HUD', size=12, color=status_color,
                                      justify='left', wraplength=app.S(410))
        self.menu_status.pack(fill='x', pady=(app.S(3), 0))
        app.wrap_to_width(self.menu_status)

        self.restore_game = app._button(restore, '恢复原版', self.restore_original, 'secondary')
        self.restore_game.pack(side='right')

    def post(self, callback, *args):
        self.app.events.put(('extras', (callback, args)))

    def sync_actions(self):
        ready = not (self.app.busy or self.app.detecting or self.stopping)
        game_ready = ready and self.app.game_dir is not None
        self.start_game.set_enabled(game_ready and not self.menu_active)
        self.restore_game.set_enabled(game_ready)

    def _show_stage(self, message, progress=None):
        self.menu_status.configure(text=message)
        self.app.status.configure(text=message)
        if progress is not None:
            self.app.set_progress(progress)

    def launch_game(self):
        game = self.app.game_dir
        if game is None or self.app.busy or self.app.detecting or self.menu_active or self.stopping:
            return
        translations = self.app.translations
        if (self.app.can_install and not self.app.basic_patched and translations.is_file()
                and not messagebox.askyesno(
                    '安装汉化并启动',
                    '将先备份原文件，再应用基础文本和赛中 HUD 汉化，然后通过 Steam 启动 RaceRoom。\n\n继续吗？',
                    parent=self.app.root)):
            return

        self.menu_active = self.preparing = True
        self.cancel_menu.clear()
        self.app.diagnostics.set_menu_pages(())
        self.app._start('正在检查游戏…')
        self.menu_status.configure(text='正在检查游戏…')
        self._start_launch(game, self.app.installer, translations, include_text=True)

    def _start_launch(self, game, installer, translations, *, include_text, include_menu=True):
        threading.Thread(target=self._launch, args=(game, installer, translations, include_text, include_menu),
                         daemon=True).start()

    def _launch(self, game, installer, translations, include_text, include_menu=True):
        stage = Stage.START
        try:
            steam = self._steam_for_game(game)
            event = home_zh.WatchEvent()
            with event.own() as handle:
                def stopped(milliseconds):
                    return self.cancel_menu.is_set() or event.wait(handle, milliseconds)

                if stopped(0):
                    raise RuntimeError('启动已取消。')
                if include_menu:
                    stage = Stage.MENU
                    try:
                        home_zh.game_listens_locally()
                    except home_zh.MenuPortInUse as exc:
                        self.post(self._offer_launch_without_menu, game, installer, translations, include_text, str(exc))
                        return
                    script = home_zh.load_translation()
                stage = Stage.START
                self.app.record_localized_game(game)
                if include_text:
                    stage = Stage.BASE
                    self.post(self.app.set_component_status, Stage.BASE, Status.PREPARING)
                    self.post(self._show_stage, '正在检查基础文本…', 10)
                    if installer is None:
                        raise RuntimeError('无法读取当前安装的基础文本，请在「游戏与文件」中检查游戏目录。')
                    result = installer.install(translations, progress=lambda pct: self.app.progress(10 + pct * .55))
                    self.post(self._basic_ready, result)

                stage = Stage.HUD
                self.post(self.app.set_component_status, Stage.HUD, Status.PREPARING)
                self.post(self._show_stage, '正在准备赛中 HUD…', 65)
                self._prepare_hud(game, stopped)
                self.post(self.app.set_component_status, Stage.HUD, Status.READY)
                stage = Stage.STEAM
                self.post(self._show_stage, '正在通过 Steam 启动 RaceRoom…', 80)
                self._start_steam(steam, stopped, include_menu=include_menu)
                if not include_menu:
                    self.post(self._finish_without_menu)
                    return
                stage = Stage.MENU
                self.post(self.app.set_component_status, Stage.MENU, Status.WAITING)
                self.post(self._show_stage, '赛中 HUD 已就绪，正在等待网页菜单…', 90)
                home_zh.apply_pages(websocket, script, 120, stopped, True,
                                    report=lambda text: self._report_menu(text, include_text),
                                    on_pages=lambda pages: self.post(self.app.diagnostics.set_menu_pages, pages))
        except Exception as exc:
            if stage == Stage.BASE:
                self.post(self._offer_menu_hud_only, game, str(exc), include_menu)
                return
            self.post(self._menu_finished, stage, str(exc))
        else:
            self.post(self._menu_finished, Stage.MENU, None)

    def _steam_for_game(self, game: Path) -> Path:
        if self.game_running():
            raise RuntimeError('请先退出 RaceRoom，再点「一键汉化并启动」。')
        libraries = self.steam_libraries()
        steam = next((root / 'steam.exe' for root in libraries if (root / 'steam.exe').is_file()), None)
        if steam is None:
            raise RuntimeError('未找到 Steam，请先确认 Steam 已安装。')
        registered = {path.resolve() for root in libraries
                      if (root / 'steamapps' / 'appmanifest_211500.acf').is_file()
                      and (path := root / 'steamapps' / 'common' / 'raceroom racing experience').is_dir()}
        if registered != {game.resolve()}:
            raise RuntimeError('请选择 Steam 当前安装的 RaceRoom 目录，再重试。')
        return steam

    def _prepare_hud(self, game, stopped):
        if stopped(0):
            raise RuntimeError('启动已取消。')
        self.app.log(hud_bundle.prepare_launch(game, running=False))

    def _start_steam(self, steam, stopped, *, include_menu=True):
        if stopped(0):
            raise RuntimeError('启动已取消。')
        if self.game_running():
            raise RuntimeError('RaceRoom 已在准备期间启动。请退出游戏后重试。')
        args = [str(steam), '-applaunch', '211500']
        if include_menu:
            args.append('-webdev')
        subprocess.Popen(args, cwd=steam.parent)

    def _basic_ready(self, result):
        applied = result['applied']
        self.app.basic_patched = True
        self.app.set_component_status(Stage.BASE, Status.APPLIED)
        self.app.basic_state.configure(text='已匹配')
        if result.get('cached'):
            summary = '基础文本未变更，已跳过逐条比对'
        else:
            summary = f'已更新 {applied:,} 条基础文本' if applied else '基础文本与译文表一致'
        self.app.basic_summary.configure(text=summary)

    def _offer_menu_hud_only(self, game, error, include_menu=True):
        self.app.set_component_status(Stage.BASE, Status.FAILED)
        notice = self.app.report_issue(Stage.BASE, error)
        self.app.basic_state.configure(text='未完成')
        self._show_stage(notice)
        components = '菜单与 HUD' if include_menu else '赛中 HUD'
        if messagebox.askyesno('基础文本未完成',
                               f'{notice}\n\n详细原因：{error}\n\n是否保留当前基础文本，仅启用{components}并启动？',
                               default=messagebox.NO, parent=self.app.root):
            self._start_launch(game, None, None, include_text=False, include_menu=include_menu)
        else:
            self.menu_active = self.preparing = False
            self.app._set_busy(False)
            self._show_stage(notice, 0)

    def _offer_launch_without_menu(self, game, installer, translations, include_text, error):
        if self.stopping or self.cancel_menu.is_set():
            return
        self.app.set_component_status(Stage.MENU, Status.DISCONNECTED)
        notice = self.app.report_issue(Stage.MENU, error)
        self._show_stage(notice)
        components = '基础文本和赛中 HUD' if include_text else '赛中 HUD'
        if messagebox.askyesno('网页菜单端口被占用',
                               f'{notice}\n\n本次是否跳过网页菜单，只启用{components}并启动？',
                               default=messagebox.NO, parent=self.app.root):
            self.app.set_component_status(Stage.MENU, Status.SKIPPED)
            self._start_launch(game, installer, translations, include_text=include_text, include_menu=False)
        else:
            self.menu_active = self.preparing = False
            self.app._set_busy(False)
            self._show_stage(notice, 0)

    def _finish_without_menu(self):
        self.menu_active = self.preparing = False
        message = '已请 Steam 启动 RaceRoom，本次跳过网页菜单汉化。'
        self._show_stage(message)
        self.app._finish(message)

    def _report_menu(self, text, include_text):
        self.app.log(text)
        if text.startswith('已汉化 '):
            self.post(self._menu_ready, include_text)
        elif text.startswith('暂时无法汉化 '):
            self.post(self.app.diagnostics.record, Stage.MENU, text)

    def _menu_ready(self, include_text):
        if self.stopping or self.cancel_menu.is_set() or not self.preparing:
            return
        self.preparing = False
        self.app.set_component_status(Stage.MENU, Status.ENABLED)
        self._show_stage(
            '中文菜单和赛中 HUD 已启用。游玩时请保持工具开启。' if include_text else
            '已启用菜单与 HUD，未更新基础文本。游玩时请保持工具开启。', 100)
        self.app._set_busy(False)
        self.app.auto_detect(silent=True)

    def _menu_finished(self, stage: Stage, error: str | None):
        was_preparing = self.preparing
        self.menu_active = self.preparing = False
        if self.stopping or self.cancel_menu.is_set():
            self.sync_actions()
            return
        if stage == Stage.HUD:
            self.app.set_component_status(Stage.HUD, Status.FAILED)
        elif stage == Stage.MENU:
            status = Status.DISCONNECTED if error is not None or was_preparing else Status.INACTIVE
            self.app.set_component_status(Stage.MENU, status)
        prefix = '基础文本已汉化。' if self.app.basic_patched and stage in (Stage.HUD, Stage.STEAM, Stage.MENU) else ''
        if was_preparing:
            notice = self.app._fail(stage, error or '菜单汉化在就绪前停止。', prefix=prefix)
            self.menu_status.configure(text=notice)
            self.app.auto_detect(silent=True)
        else:
            notice = self.app.report_issue(stage, error, prefix=prefix) if error else '网页菜单汉化已停止，可再次一键启动。'
            if self.app.busy:
                self.menu_status.configure(text=notice)
            else:
                self._show_stage(notice, 0)
            self.sync_actions()

    def restore_original(self):
        game = self.app.game_dir
        if game is None or self.app.busy or self.app.detecting or self.stopping:
            return
        if not messagebox.askyesno('恢复原版', '退出 RaceRoom 后，可停用网页菜单汉化，并尝试还原赛中 HUD 和基础文本。\n\n继续吗？',
                                   parent=self.app.root):
            return

        installer = self.app.installer
        self.stopping = True
        self.app._start('正在恢复原版…')
        self.menu_status.configure(text='正在恢复原版…')

        def work():
            try:
                results, failed = self._restore_game_files(game, installer)
            except Exception as exc:
                self.post(self._restore_failed, str(exc))
            else:
                self.post(self._restore_finished, results, failed)

        threading.Thread(target=work, daemon=True).start()

    def _stop_menu(self):
        self.cancel_menu.set()
        home_zh.WatchEvent().stop()
        return '已停用汉化'

    def _restore_game_files(self, game, installer):
        if self.game_running():
            raise RuntimeError('请先退出 RaceRoom，再恢复原版。')
        error = None
        try:
            menu = f'网页菜单：{self._stop_menu()}'
        except Exception as exc:
            error = str(exc)
            menu = f'网页菜单：未完成。{error}'
        self.app.log(menu)

        def report(component, reason):
            self.post(self.app.record_restore_result, component, reason)

        report(Stage.MENU, error)
        results, failed = restore_game_files(game, installer, self.app.log, report=report)
        return '\n\n'.join([menu, *results]), error is not None or failed

    def _restore_failed(self, error):
        self.stopping = False
        notice = self.app._fail(Stage.RESTORE, error)
        self.menu_status.configure(text=notice)

    def _restore_finished(self, results, failed):
        self.stopping = False
        if failed:
            issues = self.app.diagnostics.issues
            issue = issues[-1] if issues and issues[-1].stage == Stage.RESTORE else issue_for(Stage.RESTORE, '')
            summary = f'部分项目未能恢复。{issue.action}'
            self.app._set_busy(False)
            self._show_stage(summary, 0)
            self.app.auto_detect(silent=True)
            messagebox.showwarning('恢复原版', f'{summary}\n\n{results}', parent=self.app.root)
        else:
            summary = '恢复原版已完成。'
            self.menu_status.configure(text=summary)
            self.app._finish(summary)
            messagebox.showinfo('恢复原版', results, parent=self.app.root)
