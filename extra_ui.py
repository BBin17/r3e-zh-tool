"""Coordinate the one-click RaceRoom localization and Steam launch."""
from pathlib import Path
import subprocess
import threading
from tkinter import messagebox

import websocket

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


def restore_game_files(game, installer, log):
    results = []
    failed = False
    for name, action in (('赛中 HUD', lambda: hud_bundle.restore(game)),
                         ('基础文本', lambda: restore_base_text(installer))):
        try:
            result = action()
        except Exception as exc:
            result = f'未完成。{exc}'
            failed = True
        message = f'{name}：{result}'
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
        self.app._start('正在检查游戏…')
        self.menu_status.configure(text='正在检查游戏…')
        self._start_launch(game, self.app.installer, translations, include_text=True)

    def _start_launch(self, game, installer, translations, *, include_text):
        threading.Thread(target=self._launch, args=(game, installer, translations, include_text),
                         daemon=True).start()

    def _launch(self, game, installer, translations, include_text):
        stage = '启动检查'
        try:
            steam = self._steam_for_game(game)
            script = home_zh.load_translation()
            event = home_zh.WatchEvent()
            with event.own() as handle:
                def stopped(milliseconds):
                    return self.cancel_menu.is_set() or event.wait(handle, milliseconds)

                if stopped(0):
                    raise RuntimeError('启动已取消。')
                self.app.record_localized_game(game)
                if include_text:
                    stage = '基础文本'
                    self.post(self._show_stage, '正在检查基础文本…', 10)
                    if installer is None:
                        raise RuntimeError('无法读取当前安装的基础文本，请在「游戏与文件」中检查游戏目录。')
                    result = installer.install(translations, progress=lambda pct: self.app.progress(10 + pct * .55))
                    self.post(self._basic_ready, result)

                stage = '赛中 HUD'
                self.post(self._show_stage, '正在准备赛中 HUD…', 65)
                self._prepare_hud(game, stopped)
                stage = 'Steam 启动'
                self.post(self._show_stage, '正在通过 Steam 启动 RaceRoom…', 80)
                self._start_steam(steam, stopped)
                stage = '网页菜单'
                self.post(self._show_stage, '赛中 HUD 已就绪，正在等待网页菜单…', 90)
                home_zh.apply_pages(websocket, script, 120, stopped, True,
                                    report=lambda text: self._report_menu(text, include_text))
        except Exception as exc:
            if stage == '基础文本':
                self.post(self._offer_menu_hud_only, game, str(exc))
                return
            self.post(self._menu_finished, f'{stage}未完成：{exc}')
        else:
            self.post(self._menu_finished, None)

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

    def _start_steam(self, steam, stopped):
        if stopped(0):
            raise RuntimeError('启动已取消。')
        if self.game_running():
            raise RuntimeError('RaceRoom 已在准备期间启动。请退出游戏后重试。')
        subprocess.Popen([str(steam), '-applaunch', '211500', '-webdev'], cwd=steam.parent)

    def _basic_ready(self, result):
        applied = result['applied']
        self.app.basic_patched = True
        self.app.basic_state.configure(text='已匹配')
        if result.get('cached'):
            summary = '基础文本未变更，已跳过逐条比对'
        else:
            summary = f'已更新 {applied:,} 条基础文本' if applied else '基础文本与译文表一致'
        self.app.basic_summary.configure(text=summary)

    def _offer_menu_hud_only(self, game, error):
        self.app.log(f'基础文本未完成：{error}')
        self.app.basic_state.configure(text='未完成')
        self._show_stage('基础文本未完成')
        if messagebox.askyesno('基础文本未完成',
                               f'{error}\n\n是否保留当前基础文本，仅启用菜单与 HUD 并启动？',
                               default=messagebox.NO, parent=self.app.root):
            self._start_launch(game, None, None, include_text=False)
        else:
            self.menu_active = self.preparing = False
            self.app._set_busy(False)
            self._show_stage('已取消启动，可检查译文表后重试。', 0)

    def _report_menu(self, text, include_text):
        self.app.log(text)
        if text.startswith('已汉化 '):
            self.post(self._menu_ready, include_text)

    def _menu_ready(self, include_text):
        if self.stopping or self.cancel_menu.is_set() or not self.preparing:
            return
        self.preparing = False
        self._show_stage(
            '中文菜单和赛中 HUD 已启用。游玩时请保持工具开启。' if include_text else
            '已启用菜单与 HUD，未更新基础文本。游玩时请保持工具开启。', 100)
        self.app._set_busy(False)
        self.app.auto_detect(silent=True)

    def _menu_finished(self, error):
        was_preparing = self.preparing
        self.menu_active = self.preparing = False
        if self.stopping or self.cancel_menu.is_set():
            self.sync_actions()
            return
        if was_preparing:
            self.menu_status.configure(text='启动流程未完成。')
            self.app._fail(error or '菜单汉化在就绪前停止。')
            self.app.auto_detect(silent=True)
        else:
            self._show_stage(error or '网页菜单汉化已停止，可再次一键启动。', 0)
            if error:
                self.app.log(error)
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
        try:
            menu = f'网页菜单：{self._stop_menu()}'
            menu_failed = False
        except Exception as exc:
            menu = f'网页菜单：未完成。{exc}'
            menu_failed = True
        self.app.log(menu)
        results, failed = restore_game_files(game, installer, self.app.log)
        return '\n\n'.join([menu, *results]), menu_failed or failed

    def _restore_failed(self, error):
        self.stopping = False
        self.menu_status.configure(text='恢复原版未完成。')
        self.app._fail(error)

    def _restore_finished(self, results, failed):
        self.stopping = False
        summary = '部分项目未能恢复。' if failed else '恢复原版已完成。'
        self.menu_status.configure(text=summary)
        self.app._finish(summary)
        show_results = messagebox.showwarning if failed else messagebox.showinfo
        show_results('恢复原版', results, parent=self.app.root)
