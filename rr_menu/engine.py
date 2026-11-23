"""Load the local RaceRoom menu translations in a running -webdev session."""
from contextlib import closing, contextmanager
import csv
import ctypes
from ctypes import wintypes
import io
import json
import locale
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

ASSETS = Path(__file__).resolve().parent / 'assets'
ASSET_NAMES = ('home-zh.js', 'home-zh.json', 'section-zh.json', 'achievements-zh.json',
               'toolbar-zh.json', 'legacy-zh.json', 'car-setup-zh.json', 'drive-zh.json', 'ranked-zh.json')
ORIGIN = 'https://game.raceroomracing.com'
PORT = 8080
MENU_ROUTES = {'/game/menu/main', '/game/menu/game_modes', '/leaderboard', '/my-lap-times',
               '/leaderboard-rankings', '/multiplayer-rankings', '/competitions', '/store',
               '/store/cars', '/store/tracks', '/store/packs', '/store/recommended',
               '/store/discounted', '/store/promotions', '/store/starter-pass', '/store/complete',
               '/news', '/user-settings'}
PROFILE_ROUTE = re.compile(r'/users/[^/]+(?:/(?:races|statistics|achievements|leaderboards|follows))?')
DRIVE_ROUTE = re.compile(r'/game/menu/launcher/(?:single-race|championship|track-day|leaderboard-challenge|test-cars|competition)(?:/[A-Za-z0-9_-]+){0,2}')
RANKED_ROUTE = re.compile(r'/ranked(?:/[^/]+){0,3}|/game/menu/launcher/multiplayer')
LEGACY_ROUTES = re.compile(r'/game-menu/(?:garage(?:/pitstopPreset)?|car-setup|replays|replay-hud|options(?:/[A-Za-z0-9_-]+){0,2})')
GAME_BRIDGE = f"location.origin === '{ORIGIN}' && typeof window.gameClient === 'function'"
WATCH_EVENT = r'Local\RaceRoomHomeZhStop'


def supports_translation(path):
    return (path in MENU_ROUTES or PROFILE_ROUTE.fullmatch(path) is not None
            or LEGACY_ROUTES.fullmatch(path) is not None or DRIVE_ROUTE.fullmatch(path) is not None
            or RANKED_ROUTE.fullmatch(path) is not None)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class MenuPortInUse(RuntimeError):
    pass


def windows_processes(image=None):
    args = ['tasklist', '/fo', 'csv', '/nh']
    if image:
        args += ['/fi', f'IMAGENAME eq {image}']
    listing = subprocess.check_output(args, timeout=10, creationflags=subprocess.CREATE_NO_WINDOW)
    rows = csv.reader(io.StringIO(listing.decode(locale.getpreferredencoding(False), errors='replace')))
    return {row[1]: row[0] for row in rows
            if len(row) >= 2 and row[1].isascii() and row[1].isdigit()
            and (not image or row[0].casefold() == image.casefold())}


def game_listens_locally():
    listing = subprocess.check_output(['netstat', '-ano', '-p', 'tcp'], timeout=10,
                                      creationflags=subprocess.CREATE_NO_WINDOW).decode(errors='replace')
    listeners = [row for line in listing.splitlines() if len(row := line.split()) >= 5
                 and row[1].endswith(f':{PORT}') and row[3] == 'LISTENING']
    if not listeners:
        return False
    processes = windows_processes()
    owners = {processes.get(row[-1], '') for row in listeners}
    other_owners = {name for name in owners if name.lower() != 'rrre64.exe'}
    if other_owners:
        names = sorted({name if re.fullmatch(r'[\w .()\-]{1,64}\.exe', name, re.IGNORECASE) else '未知进程'
                        for name in other_owners}, key=str.lower)
        raise MenuPortInUse(f'网页菜单端口 {PORT} 被占用（{"、".join(names[:5])}）')
    if any(row[1] not in {f'127.0.0.1:{PORT}', f'[::1]:{PORT}'} for row in listeners):
        raise RuntimeError('调试端口监听的地址超出本机回环范围，已停止。')
    return any(row[1] == f'127.0.0.1:{PORT}' for row in listeners)


def find_pages():
    if not game_listens_locally():
        return None
    opener = build_opener(ProxyHandler({}), NoRedirect())
    with opener.open(f'http://127.0.0.1:{PORT}/json/list', timeout=3) as response:
        targets = json.load(response)
    candidates = []
    for target in targets:
        url = urlsplit(target.get('url', ''))
        if target.get('type') != 'page' or f'{url.scheme}://{url.netloc}' != ORIGIN:
            continue
        endpoint = urlsplit(target.get('webSocketDebuggerUrl', ''))
        if (endpoint.scheme != 'ws' or endpoint.netloc not in {f'127.0.0.1:{PORT}', f'localhost:{PORT}'}
                or not re.fullmatch(r'/devtools/page/[A-Za-z0-9_-]+', endpoint.path)):
            continue
        if endpoint.query or endpoint.fragment:
            continue
        candidates.append((url.path.rstrip('/'), f'ws://127.0.0.1:{PORT}{endpoint.path}'))
    return candidates


class DebugPage:
    def __init__(self, socket):
        self.socket = socket
        self.sequence = 0

    def call(self, method, **params):
        self.sequence += 1
        self.socket.send(json.dumps({'id': self.sequence, 'method': method, 'params': params}))
        while True:
            reply = json.loads(self.socket.recv())
            if reply.get('id') == self.sequence:
                break
        if 'error' in reply:
            raise RuntimeError(f'游戏调试接口未能完成 {method}。')
        return reply['result']

    def evaluate(self, expression, context=None):
        params = {'expression': expression, 'returnByValue': True, 'silent': True}
        if context is not None:
            params['contextId'] = context
        result = self.call('Runtime.evaluate', **params)
        if 'exceptionDetails' in result:
            raise RuntimeError('游戏页面未能执行界面译文脚本。')
        return result['result'].get('value')

    def frame(self):
        return self.call('Page.getFrameTree')['frameTree']['frame']

    def world(self, frame_id=None):
        return self.call('Page.createIsolatedWorld', frameId=frame_id or self.frame()['id'],
                         worldName='r3e-home-zh')['executionContextId']


def load_translation(directory=ASSETS, *, charts=False):
    """Build the in-memory overlay script from the packaged catalogues."""
    directory = Path(directory)

    def load(name):
        return json.loads((directory / f'{name}-zh.json').read_text(encoding='utf-8'))

    legacy = load('legacy')
    chart_text = legacy['gameOptions'].pop('canvasText')
    if charts:
        config = chart_text
    else:
        home = load('home')
        config = load('section')
        config['nav'] = home['nav']
        config['home'] = {'selectors': '.坯', 'text': home['text']}
        config['profile']['text'] = config['leaderboards']['text'] | config['profile']['text']
        config['profile']['achievements'] = load('achievements')
        config['toolbar'] = load('toolbar')
        config.update(legacy)
        config['carSetup'] = load('car-setup')
        config['drive'] = load('drive')
        config['ranked'] = load('ranked')
    script = (directory / 'home-zh.js').read_text(encoding='utf-8')
    marker = '/* TRANSLATIONS */'
    if script.count(marker) != 1:
        raise ValueError('菜单译文脚本无效。')
    return script.replace(marker, json.dumps(config, ensure_ascii=True), 1) + f'({json.dumps(charts)})'


class WatchEvent:
    """Coordinate the single local watcher and its stop signal on Windows."""

    def __init__(self):
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        for name, inputs, result in (
            ('CreateEventW', (wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR), wintypes.HANDLE),
            ('OpenEventW', (wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR), wintypes.HANDLE),
            ('SetEvent', (wintypes.HANDLE,), wintypes.BOOL),
            ('CloseHandle', (wintypes.HANDLE,), wintypes.BOOL),
            ('WaitForSingleObject', (wintypes.HANDLE, wintypes.DWORD), wintypes.DWORD),
        ):
            fn = getattr(self.api, name)
            fn.argtypes, fn.restype = inputs, result

    @contextmanager
    def own(self):
        handle = self.api.CreateEventW(None, True, False, WATCH_EVENT)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        existing = ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS
        try:
            if existing:
                raise RuntimeError('游戏汉化已经在运行。')
            yield handle
        finally:
            self.api.CloseHandle(handle)

    def wait(self, handle, milliseconds):
        result = self.api.WaitForSingleObject(handle, milliseconds)
        if result not in (0, 258):  # WAIT_OBJECT_0 / WAIT_TIMEOUT
            raise ctypes.WinError(ctypes.get_last_error())
        return result == 0

    def stop(self):
        deadline = time.monotonic() + 12
        while True:
            handle = self.api.OpenEventW(0x0002, False, WATCH_EVENT)  # EVENT_MODIFY_STATE
            if not handle:
                if ctypes.get_last_error() == 2:  # ERROR_FILE_NOT_FOUND
                    return
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                if not self.api.SetEvent(handle):
                    raise ctypes.WinError(ctypes.get_last_error())
            finally:
                self.api.CloseHandle(handle)
            if time.monotonic() >= deadline:
                raise RuntimeError('汉化监视程序尚未退出，请稍后重试。')
            time.sleep(0.15)


def open_page(websocket, endpoint):
    return closing(websocket.create_connection(endpoint, timeout=3, suppress_origin=True,
                                               http_no_proxy=['127.0.0.1'], redirect_limit=0))


def restore_pages(websocket):
    restored = 0
    errors = []
    for path, endpoint in find_pages() or ():
        try:
            with open_page(websocket, endpoint) as socket:
                page = DebugPage(socket)
                if not page.evaluate(GAME_BRIDGE):
                    continue
                chart = page.evaluate("Boolean(globalThis.__r3eFfbChartZh?.stop)")
                if chart:
                    page.evaluate("globalThis.__r3eFfbChartZh.stop()")
                overlay = page.evaluate(
                    "(() => { const overlay = globalThis.__r3eHomeZh; if (!overlay) return false; overlay.stop(); return true; })()",
                    page.world(),
                )
                if chart or overlay:
                    restored += 1
        except (websocket.WebSocketException, OSError, RuntimeError) as exc:
            errors.append(f'{path}: {exc}')
    if errors:
        raise RuntimeError('部分游戏页面未能检查：' + '；'.join(errors))
    return restored


def apply_pages(websocket, script, wait_seconds, should_stop, watch, *, report=print, on_pages=None):
    chart_script = load_translation(charts=True)
    deadline = time.monotonic() + wait_seconds
    installed = {}
    reported = {}
    applied = False
    game_seen = False
    missing_since = None
    last_paths = ()
    while not should_stop(0):
        try:
            targets = find_pages()
        except OSError:
            targets = []  # The debugger can disappear between netstat and discovery.
        if targets is None and applied:
            return
        if not applied:
            # Steam may take a while to create the process, or briefly restart it.
            game_running = bool(targets) or bool(windows_processes('RRRE64.exe'))
            now = time.monotonic()
            if game_running:
                game_seen = True
                missing_since = None
            elif game_seen:
                if missing_since is None:
                    missing_since = now
                elif now - missing_since >= 3:
                    raise RuntimeError('RaceRoom 在网页菜单就绪前已退出。')
            if now >= deadline and not game_running:
                if game_seen:
                    raise RuntimeError('RaceRoom 在网页菜单就绪前已退出。')
                raise RuntimeError('等待 Steam 启动 RaceRoom 超时，未检测到游戏进程。')
        paths = tuple(dict.fromkeys(path for path, _ in targets or ()))
        if paths and paths != last_paths:
            last_paths = paths
            if on_pages is not None:
                on_pages(tuple((path, supports_translation(path)) for path in paths))
        endpoints = {endpoint for _, endpoint in targets or ()}
        installed = {endpoint: key for endpoint, key in installed.items() if endpoint in endpoints}
        reported = {endpoint: error for endpoint, error in reported.items() if endpoint in endpoints}
        for path, endpoint in targets or ():
            if should_stop(0):
                return
            if not supports_translation(path):
                continue
            try:
                with open_page(websocket, endpoint) as socket:
                    page = DebugPage(socket)
                    frame = page.frame()
                    document = (frame['id'], frame.get('loaderId'))
                    if document[1] and installed.get(endpoint) == document:
                        continue
                    if not page.evaluate(GAME_BRIDGE):
                        continue
                    # Canvas drawings run in the game's world. Install before
                    # opening a settings panel that draws on a canvas.
                    page.evaluate(chart_script)
                    result = page.evaluate(script, page.world(frame['id']))
                    if not result or not result['active'] or not result['labels']:
                        continue
                    installed[endpoint] = document
                    reported.pop(endpoint, None)
                    applied = True
                    report(f"已汉化 {path}（{len(result['labels'])} 项）")
            except (websocket.WebSocketException, OSError, RuntimeError) as exc:
                if reported.get(endpoint) != str(exc):
                    reported[endpoint] = str(exc)
                    report(f'暂时无法汉化 {path}：{exc}')
        if applied and not watch:
            return
        if not applied and time.monotonic() >= deadline:
            raise RuntimeError('未找到可汉化的游戏页面。请确认已使用 -webdev 启动 RaceRoom 并打开游戏菜单。')
        should_stop(850)
