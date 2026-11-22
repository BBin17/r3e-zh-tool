((chartsOnly) => {
  const config = /* TRANSLATIONS */;
  const key = '__r3eHomeZh';
  const nav = 'nav a.紴';
  const excluded = 'script, style, noscript, textarea, input, [contenteditable]';
  const homeRoutes = new Set(['/game/menu/main', '/game/menu/game_modes']);
  const rankingRoutes = new Set(['/leaderboard', '/my-lap-times', '/leaderboard-rankings', '/multiplayer-rankings']);
  const translatedText = new Map();
  const translatedAttributes = new Map();
  let lastSection;
  let stopped = false;
  let queued = false;

  // The catalog keys pair FNV-1a and Jenkins one-at-a-time over UTF-16 code
  // units. Their case-sensitive fingerprints are checked for catalog collisions.
  function textKey(text) {
    let fnv = 2166136261;
    let jenkins = 0;
    for (let i = 0; i < text.length; i++) {
      const unit = text.charCodeAt(i);
      fnv = Math.imul(fnv ^ unit, 16777619);
      jenkins += unit;
      jenkins += jenkins << 10;
      jenkins ^= jenkins >>> 6;
    }
    jenkins += jenkins << 3;
    jenkins ^= jenkins >>> 11;
    jenkins += jenkins << 15;
    return (fnv >>> 0).toString(16).padStart(8, '0') + (jenkins >>> 0).toString(16).padStart(8, '0');
  }

  if (chartsOnly) {
    const chartKey = '__r3eFfbChartZh';
    const prototype = globalThis.CanvasRenderingContext2D?.prototype;
    if (!prototype || globalThis[chartKey]) return;

    const originalFill = prototype.fillText;
    const originalMeasure = prototype.measureText;
    const seatCanvas = '.撑 > .飓 > canvas.飞';

    function seatLabel(text) {
      return config.seat[textKey(text)] ?? text;
    }

    function feedbackLabel(text) {
      const label = config.feedback[textKey(text)];
      if (label) return label;
      const floor = /^(?<label>.{6})(?<value>\d+(?:\.\d+)?)%$/.exec(text)?.groups;
      if (floor && textKey(floor.label) === '50b844072597b1b3') {
        return config.feedback['50b844072597b1b3'].replace('{percentage}', floor.value);
      }
      return text;
    }

    function fillText(text, ...args) {
      if (typeof text === 'string') {
        const canvas = this.canvas;
        if (canvas.matches?.(seatCanvas)) text = seatLabel(text);
        else if (canvas.matches?.('[data-ffb-instrument] canvas')) text = feedbackLabel(text);
      }
      return originalFill.call(this, text, ...args);
    }

    function measureText(text) {
      // The seat panel uses the measured hint widths to place the next hint.
      if (typeof text === 'string' && this.canvas.matches?.(seatCanvas)) text = seatLabel(text);
      return originalMeasure.call(this, text);
    }

    prototype.fillText = fillText;
    prototype.measureText = measureText;
    globalThis[chartKey] = {
      stop() {
        if (prototype.fillText === fillText) prototype.fillText = originalFill;
        if (prototype.measureText === measureText) prototype.measureText = originalMeasure;
        delete globalThis[chartKey];
      },
    };
    return;
  }

  // Capture the shape of a dynamic label, then check each fixed fragment by
  // key. The remaining captures preserve the original runtime values.
  function matchLabel(text, shape, fragments) {
    const groups = shape.exec(text)?.groups;
    if (!groups) return null;
    for (const [name, key] of Object.entries(fragments)) {
      const actual = textKey(groups[name]);
      if (Array.isArray(key) ? !key.includes(actual) : key !== actual) return null;
    }
    return groups;
  }

  // A drive count can be embedded in a longer label. The keyed fragments
  // include their spacing, and the outside word boundaries are ASCII.
  function replaceCount(text, before, after, render) {
    let result = '';
    let end = 0;
    for (const match of text.matchAll(/\b(\d+)\b/g)) {
      const countEnd = match.index + match[0].length;
      const start = before ? match.index - before[0] : match.index;
      if (start < end || (start > 0 && /\w/.test(text[start - 1]))) continue;
      if (before && textKey(text.slice(start, match.index)) !== before[1]) continue;
      const suffix = after.find(([length, key]) =>
        countEnd + length <= text.length && !/\w/.test(text[countEnd + length] ?? '') &&
        textKey(text.slice(countEnd, countEnd + length)) === key);
      if (!suffix) continue;
      result += text.slice(end, start) + render(match[1]);
      end = countEnd + suffix[0];
    }
    return result + text.slice(end);
  }

  const driveCounts = [
    [[4, '154b49db5fd0cc04'], [[5, '3cb8d07c4a5d28b9']], count => `最多 ${count} 辆赛车`],
    [null, [[14, '390da2c6f040861c']], count => `每轮 ${count} 分钟`],
    [null, [[4, '34aaa379e981c8a8']], count => `${count} 分钟`],
    [null, [[8, '83449e527d83da98'], [7, '2891a3d59df9ea01']], count => `${count} 位车手`],
    [null, [[7, '459de80a45655aa1'], [6, '9056267d23c7e147']], count => `${count} 轮`],
    [null, [[5, '3cb8d07c4a5d28b9'], [4, '92d72b6794d3ac18']], count => `${count} 辆赛车`],
    [null, [[7, 'd405cf8be5288da4']], count => `${count} 座赛道`],
    [null, [[9, '1435ba7021e40add'], [7, '364410a4a37404e7']], count => `${count} 款涂装`],
    [null, [[9, '4fb155b6c0561b83']], count => `${count} 个版本`],
  ];
  const drivePhases = new Set(['ec65ee9085389428', 'aae2185035b44d12', '0ee9a1b8ca06b173']);
  const setupNumbers = new Set([
    'b11123dc5d31bfeb', 'd889e2378e411f67', '8796e4504119f1cd', '993ce056c75dbfe9', 'd4460b475cf87f4f',
    '807c21f65f2d5bb1', '79bfc757e85e8f3d',
  ]);
  const steeringRanges = new Set(['585e2a05d942fbe4', '3ce7912c7cc058e7', '37a80a2d2e4755e0']);
  const durationUnits = {
    ['abf8d4dd7437b693']: '秒', ['66b6cdea1ed681a8']: '秒', ['38e70f69bad25d99']: '分钟', ['adbcc5eeefe54f14']: '分钟',
    ['b6032c0f5fab3980']: '小时', ['02ff07349714b291']: '小时', ['54607cea3f029fa9']: '圈', ['6ce424dbbcd4f722']: '圈',
  };
  const windDirections = {
    ['cb0c01d191aca343']: '北', ['37e67bfc3abe1d4c']: '东北', ['c00bf080c8cc9186']: '东', ['5c028b2577f29250']: '东南',
    ['d60c1322ca8b9500']: '南', ['6a02a12fb7f19199']: '西南', ['d20c0cd611f523d2']: '西', ['29e665f2acf801b2']: '西北',
  };

  function sectionForPage() {
    if (location.origin !== 'https://game.raceroomracing.com') return null;
    const path = location.pathname.replace(/\/$/, '');
    if (homeRoutes.has(path)) return 'home';
    if (/^\/ranked(?:\/[^/]+){0,3}$/.test(path) || path === '/game/menu/launcher/multiplayer') return 'ranked';
    if (/^\/game\/menu\/launcher\/(?:single-race|championship|track-day|leaderboard-challenge|test-cars|competition)(?:\/[\w-]+){0,2}$/.test(path)) return 'drive';
    if (rankingRoutes.has(path)) return 'leaderboards';
    if (path === '/news') return 'news';
    if (path === '/user-settings') return 'settings';
    if (path === '/game-menu/replays') return 'replays';
    if (path === '/game-menu/replay-hud') return 'replayHud';
    if (path === '/game-menu/garage') return 'garage';
    if (path === '/game-menu/garage/pitstopPreset') return 'pitStopPresets';
    if (path === '/game-menu/car-setup') return 'carSetup';
    if (/^\/game-menu\/options(?:\/[\w-]+){0,2}$/.test(path)) return 'gameOptions';
    if (/^\/users\/[^/]+(?:\/(?:races|statistics|achievements|leaderboards|follows))?$/.test(path)) return 'profile';
    if (path === '/competitions') return 'competitions';
    if (/^\/store(?:\/(?:cars|tracks|packs|recommended|discounted|promotions|starter-pass|complete))?$/.test(path)) return 'store';
    return null;
  }

  function restore() {
    for (const [node, { source, target }] of translatedText) {
      if (node.data === target) node.data = source;
    }
    for (const [element, attributes] of translatedAttributes) {
      for (const [name, { source, target }] of attributes) {
        if (element.getAttribute(name) === target) element.setAttribute(name, source);
      }
    }
    translatedText.clear();
    translatedAttributes.clear();
  }

  function originalText(node) {
    const previous = translatedText.get(node);
    return previous?.target === node.data ? previous.source : node.data;
  }

  function profileTranslations(page) {
    const result = new Map();
    const read = element => {
      const node = element?.firstChild;
      return node?.nodeType === Node.TEXT_NODE ? node : null;
    };
    const path = location.pathname.replace(/\/$/, '');
    if (path.endsWith('/achievements')) {
      for (const card of document.querySelectorAll('.誓 > .麺')) {
        const title = read(card.querySelector('.楲 .嫝'));
        const description = read(card.querySelector('.楢'));
        const status = read(card.querySelector('.楟'));
        if (title) {
          const text = originalText(title).trim();
          const entry = page.achievements[textKey(text)];
          if (entry) {
            result.set(title, entry[0]);
            if (description) result.set(description, entry[1]);
          } else {
            const hidden = matchLabel(text, /^(?<count>\d+)(?<words>.+)$/, {
              words: ['15310c011f6b529d', 'd6d7a912b8b8a329'],
            });
            if (hidden) result.set(title, `还有 ${hidden.count} 项隐藏成就`);
          }
        }
        if (status) {
          const date = matchLabel(originalText(status).trim(),
            /^(?<words>.{7})(?<day>\d{1,2})\.(?<month>\d{1,2})\.(?<year>\d{4})$/,
            { words: 'e4bc9a52e91703b6' });
          if (date) result.set(status, `已获得 · ${date.year}年${Number(date.month)}月${Number(date.day)}日`);
        }
      }
    } else if (/^\/users\/[^/]+$/.test(path)) {
      for (const term of document.querySelectorAll('.謫 dl.麖 > dt')) {
        const label = read(term);
        if (!label || textKey(originalText(label).trim()) !== '04f4fe714dc35af9') continue;
        const value = read(term.nextElementSibling);
        if (!value) continue;
        const country = page.countries[textKey(originalText(value).trim())];
        if (country) result.set(value, country);
      }
    }
    return result;
  }

  function wizardTranslation(parent, text, id, wizard, common) {
    if (!parent.closest(wizard.selectors)) return null;
    if (parent.closest('.奴')) {
      return id === '64cf0efdcadbff8b' ? wizard.text[id] : null;
    }
    if (Object.hasOwn(wizard.text, id)) return wizard.text[id];
    if (Object.hasOwn(common, id)) return common[id];

    const step = matchLabel(text,
      /^(?<start>.{5})(?<step>\d+)(?<middle>.{4})(?<total>\d+)$/,
      { start: '876b129da0ede95c', middle: '8f7412e63d7eed65' });
    if (step) return `第 ${step.step} 步，共 ${step.total} 步`;
    const sweep = matchLabel(text,
      /^(?<start>.{11})(?<min>[-−]?\d+)°(?<middle>.{4})\+(?<max>\d+)°\.$/,
      { start: '0d27cd1e94809239', middle: '1e65b5ce22086e6e' });
    if (sweep) return `检测到的转动范围为 ${sweep.min}° 至 +${sweep.max}°。`;
    const gears = matchLabel(text, /^(?<count>\d+)(?<words>.+)$/, { words: '4106e86245e510c9' });
    if (gears) return `已检测到 ${gears.count} 个挡位。`;
    const devices = matchLabel(text, /^(?<words>.{26})(?<names>.+)$/,
      { words: '26ba399b1169cee3' });
    if (devices) return `此配置适用于 ${devices.names}`;
    const pedals = matchLabel(text, /^(?<names>.+)(?<words>.{149})$/,
      { words: 'ee775517c7a7d229' });
    if (pedals) {
      const names = pedals.names.split(', ').map(name => common[textKey(name)] ?? name);
      return `${names.join('、')}未达到最大行程。请在踏板软件中设置最大行程，或在「方向盘与踏板」中增大上限死区。`;
    }
    return null;
  }

  function driveTranslation(parent, text, dictionary) {
    if (parent.matches('header.铇 .铄')) {
      const [mode, ...rest] = text.split(' · ');
      const translated = dictionary[textKey(mode)];
      if (rest.length && translated !== undefined) return [translated, ...rest].join(' · ');
    }
    if (parent.matches('.熽, .謈 span, .途 .逘, .熌, .熃, .疹 .嫝, .疑, .瓬, .铉, .譋')) {
      for (const [before, after, render] of driveCounts) text = replaceCount(text, before, after, render);
      if (textKey(text.slice(-20)) === '340cb9992d9c0447') {
        text = `${text.slice(0, -20)} · 与我同组`;
      }
      const custom = matchLabel(text, /^(?<word>.{6})(?= · )/, { word: '9525b78e3a2eed8b' });
      if (custom) text = `自定义${text.slice(custom.word.length)}`;
      if (textKey(text) === '3278295943528178') text = '正午 · 随机';
      const phase = /^(.+?)(?= - \d+)/.exec(text);
      if (phase) {
        const id = textKey(phase[1]);
        if (drivePhases.has(id)) text = `${dictionary[id]}${text.slice(phase[1].length)}`;
      }
    }
    return text;
  }

  function carSetupTranslation(parent, text, page) {
    if (parent.matches('.麺.儹 .儅 > p')) {
      // The existing help pack contains only FNV-1a keys over code points.
      // Keep its original whitespace normalization and key algorithm.
      let hash = 2166136261;
      for (const char of text.replace(/\s+/g, ' ')) {
        hash = Math.imul(hash ^ char.codePointAt(0), 16777619);
      }
      return page.help[(hash >>> 0).toString(16)] ?? null;
    }
    if (parent.matches('.洤 .洱 .嫝, .麺.儹 > .儓, .儑')) {
      const gear = matchLabel(text, /^(?<number>\d+)(?<ordinal>.{2})(?<label>.+)$/, {
        ordinal: ['4b522242fe11fb15', '593661cf0e87a0d4', '595476e39ea238bf', '414546916a4bcdcf'], label: '8a8665508dadcbb9',
      });
      if (gear) return `${gear.number} 挡`;
      const setting = /^(.+) (#?\d+)$/.exec(text);
      if (setting) {
        const id = textKey(setting[1]);
        if (setupNumbers.has(id)) return `${page.text[id]} ${setting[2]}`;
      }
    }
    if (parent.matches('.禵 .嫝')) {
      const range = /^(.+?):\s*([\d.]+°)$/.exec(text);
      if (range) {
        const id = textKey(range[1]);
        if (steeringRanges.has(id)) return `${page.text[id]}：${range[2]}`;
      }
    }
    if (parent.closest('.儠')) {
      const current = matchLabel(text, /^(?<words>.{15})"(?<name>.*)"$/, { words: '666e7a39dd527002' });
      if (current) return `当前调校：「${current.name}」`;
      const unsaved = matchLabel(text, /^(?<name>.+)(?<words>.{20})$/,
        { words: '4efc106e14e6226d' });
      if (unsaved) return `「${unsaved.name}」有未保存的改动`;
    }
    if (parent.closest('.鴠')) {
      const lap = matchLabel(text, /^(?<head>.{5})(?<number>\d+) (?<time>\(.+\))(?<tail>.*)$/,
        { head: '9298ae8778bea657' });
      if (lap) {
        const fastest = textKey(lap.tail.slice(-11)) === '33ecc4242bdb78a4';
        const tail = fastest ? `${lap.tail.slice(0, -11)}最快圈速` : lap.tail;
        return `第 ${lap.number} 圈 ${lap.time}${tail}`;
      }
      const pressure = matchLabel(text, /^(?<words>.{10})(?<amount>[\d.]+)$/,
        { words: 'f1dd8f58d5283d81' });
      if (pressure) return `胎压：${pressure.amount}`;
    }
    return null;
  }

  const storeMonths = ['January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'];

  function storeDate(value) {
    const parts = /^(\d{1,2}) ([A-Za-z]+)$/.exec(value);
    if (!parts) return value;
    const month = storeMonths.indexOf(parts[2]) + 1;
    return month ? `${month}月${Number(parts[1])}日` : value;
  }

  function storeTranslation(text, dictionary) {
    const price = matchLabel(text, /^(?<label>.+?) (?<amount>\p{Sc}\s*\d[\d.,\s]*|\d[\d.,\s]*\s*(?:\p{Sc}|[A-Z]{3}))$/u,
      { label: ['c35b0729f2901714', 'a40140721ecc8bcd'] });
    if (price) return textKey(price.label) === 'c35b0729f2901714'
      ? `支付 ${price.amount}` : `以 ${price.amount} 购买通行证`;
    const credits = matchLabel(text, /^(?<label>\S+) (?<amount>\d[\d.,\s]*) (?<unit>\S+)$/,
      { label: '555cbe6879fe4870', unit: 'fd2fa8a38f7f3798' });
    if (credits) return `保留 ${credits.amount} VRP`;
    const days = matchLabel(text, /^(?:(?<label>.+?) )?(?<days>\d+) (?<unit>\S+)$/,
      { unit: ['e44f21fd765dba8c', 'f691d28a64a0eeb7'] });
    if (days) {
      if (!days.label) return `${days.days} 天`;
      if (['7ecf90df29804d63', '2a3c99d352aa39ed'].includes(textKey(days.label))) return `畅玩全部内容 ${days.days} 天`;
    }
    const day = matchLabel(text, /^(?<label>.+?) (?<day>\d+)$/, { label: 'cb0f057a7a89fd35' });
    if (day) return `第 ${day.day} 天`;
    const ends = matchLabel(text, /^(?<label>.+?) (?<days>\d+) (?<unit>\S+) (?<after>.+?) \((?<date>[^()]+)\)$/,
      { label: 'ed4b4ad310d20d56', unit: ['e44f21fd765dba8c', 'f691d28a64a0eeb7'], after: 'ced96df3aff20a4c' });
    if (ends) return `此通行证将在激活 ${ends.days} 天后到期（${storeDate(ends.date)}）`;
    const date = matchLabel(text, /^(?<label>.+?) (?<date>\d{1,2} [A-Za-z]+)$/,
      { label: ['ae5379d507f744fb', '437c2f3c6523c18c'] });
    if (date) return `${textKey(date.label) === 'ae5379d507f744fb' ? '有效期至' : '促销截止'} ${storeDate(date.date)}`;
    const items = matchLabel(text, /^(?<cars>\d+) (?<carWord>\S+) (?<join>\S+) (?<count>\d+) (?<itemWord>\S+)(?: (?<forWord>\S+) (?<days>\d+) (?<unit>\S+))?$/,
      { carWord: ['95276dd65e163909', '047458e169697274'], join: ['41387a9e4d5fa44b', '0f29c2a66beda11e'] });
    if (items) {
      const type = textKey(items.itemWord);
      if (textKey(items.join) === '41387a9e4d5fa44b' && !items.days &&
          ['702da6a79f7632f0', 'ab3e0bffe45c07dd'].includes(type)) return `${items.cars} 辆赛车 · ${items.count} 个组别`;
      if (textKey(items.join) === '0f29c2a66beda11e' && ['50b1805d2f54d981', '7b3d6c3c34355b73'].includes(type)) {
        const content = `${items.cars} 辆赛车和 ${items.count} 条赛道`;
        if (!items.days) return content;
        if (textKey(items.forWord) === 'acf38390c100b3d3' && ['e44f21fd765dba8c', 'f691d28a64a0eeb7'].includes(textKey(items.unit))) {
          return `${content}，畅玩 ${items.days} 天`;
        }
      }
    }
    const owned = matchLabel(text, /^(?<owned>\d+) (?<of>\S+) (?<total>\d+) (?<label>\S+)$/,
      { of: '69343c6802bf0823', label: 'e367307e4b93008b' });
    if (owned) return `已拥有 ${owned.owned} / ${owned.total}`;
    const tab = /^(?<label>\S+) · (?<count>\d+)$/.exec(text)?.groups;
    if (tab && ['15554cf64ec0aeb0', '96c4fa7dcb675feb'].includes(textKey(tab.label))) {
      return `${dictionary[textKey(tab.label)]} · ${tab.count}`;
    }
    return null;
  }

  function refresh() {
    const section = sectionForPage();
    if (section !== lastSection) restore();
    lastSection = section;
    const labels = new Set();
    if (!section || !document.body) return { active: Boolean(section), labels: [] };

    const page = config[section];
    const legacy = section === 'replays' || section === 'gameOptions' || section === 'garage' ||
      section === 'carSetup' || section === 'pitStopPresets' || section === 'replayHud';
    const scopedText = Object.entries(page.scopedText ?? {});
    const wizard = section === 'gameOptions' && /^\/game-menu\/options\/controls\/wizard\/?$/.test(location.pathname)
      ? config.controlWizard : null;
    const profileText = section === 'profile' ? profileTranslations(page) : null;
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const foundText = new Map();
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const source = originalText(node);
      const text = source.trim();
      const parent = node.parentElement;
      if (!parent || parent.closest(excluded)) continue;
      const id = textKey(text);
      let chinese = wizard ? wizardTranslation(parent, text, id, wizard, page.text) : profileText?.get(node);
      for (const [selector, dictionary] of scopedText) {
        if (chinese) break;
        if (Object.hasOwn(dictionary, id) && parent.closest(selector)) chinese = dictionary[id];
      }
      if (!chinese) {
        const dictionary = !legacy && parent.closest(nav) ? config.nav : page.text;
        if ((dictionary === config.nav || (page.selectors && parent.closest(page.selectors))) &&
            Object.hasOwn(dictionary, id)) {
          chinese = dictionary[id];
        } else if (!legacy && Object.hasOwn(config.toolbar.text, id) && parent.closest(config.toolbar.selectors)) {
          chinese = config.toolbar.text[id];
        }
      }
      if (!chinese && section === 'gameOptions') {
        const usable = parent.matches('.淟') && matchLabel(text, /^(?<value>\d+(?:\.\d+)?)%(?<word>.+)$/,
          { word: 'a87032334519dc84' });
        const above = parent.matches('.闕') && matchLabel(text, /^(?<value>\d+(?:\.\d+)?)%(?<word>.+)$/,
          { word: 'f91278a4a3dabd43' });
        const band = parent.matches('.闕') && matchLabel(text, /^(?<min>\d+) - (?<max>\d+)(?<word>.+)$/,
          { word: '0d9ace6464365052' });
        const matches = parent.closest('label.玐') && matchLabel(text, /^(?<count>\d+)(?<word>.+)$/,
          { word: ['e265e348b5b9c21c', '93649fd75d6ea9ee', 'ab674f2c52a6e921'] });
        if (matches) chinese = `${matches.count} 项结果`;
        if (usable) chinese = `可用行程 ${usable.value}%`;
        if (above) chinese = `以上车速为 ${above.value}%`;
        if (band) chinese = `${band.min}–${band.max} 公里/小时`;
      }
      if (!chinese && section === 'garage') {
        const percentile = parent.matches('.鱨') && matchLabel(text,
          /^(?<word>.{4})(?<value>\d+(?:\.\d+)?)%$/, { word: '1bb795b4aa6517ae' });
        if (percentile) chinese = `前 ${percentile.value}%`;
        const duration = parent.matches('.崃 .崛') && /^(?:(.+?)[,，]\s*)?(\d+(?:\.\d+)?)\s+([a-z]+)$/i.exec(text);
        if (duration) {
          const [, prefix, amount, unit] = duration;
          const translated = durationUnits[textKey(unit.toLowerCase())];
          if (translated) chinese = `${prefix ? `${prefix}，` : ''}${amount} ${translated}`;
        }
        const wind = parent.matches('.崅 dl.麖 > dd') && matchLabel(text,
          /^(?<value>\d+(?:\.\d+)?)\s*(?<unit>\S+)\s+(?<direction>\S+)$/, { unit: 'd53c31f29334d415' });
        if (wind) {
          const direction = windDirections[textKey(wind.direction)];
          if (direction) chinese = `${wind.value} 米/秒 · ${direction}`;
        }
      }
      if (!chinese && section === 'carSetup') chinese = carSetupTranslation(parent, text, page);
      if (!chinese && section === 'store' && parent.closest('.焧, .呕, .徹, .徸, .辜')) {
        chinese = storeTranslation(text, page.text);
      }
      if (!chinese && section === 'replayHud' && parent.matches('.蘴 .蘽')) {
        const lap = matchLabel(text, /^(?<word>\S+)\s+(?<count>\d+)$/, { word: 'b6eb148a8b3a1b37' });
        if (lap) chinese = `第 ${lap.count} 圈`;
      }
      if (!chinese && section === 'drive') {
        const translated = driveTranslation(parent, text, page.text);
        if (translated !== text) chinese = translated;
      }
      if (!chinese) continue;
      const target = source.replace(text, () => chinese);
      foundText.set(node, { source, target });
      if (node.data !== target) node.data = target;
      if (parent.getClientRects().length) labels.add(chinese);
    }
    for (const [node, { source, target }] of translatedText) {
      if (!foundText.has(node) && node.data === target) node.data = source;
    }
    translatedText.clear();
    for (const item of foundText) translatedText.set(...item);

    const toolbarAttributes = config.toolbar.attributes ?? {};
    const pageAttributes = page.attributes ?? {};
    for (const name of new Set([...Object.keys(toolbarAttributes), ...Object.keys(pageAttributes)])) {
      for (const element of document.querySelectorAll(`[${name}]`)) {
        const attributes = translatedAttributes.get(element) ?? new Map();
        const current = element.getAttribute(name);
        const previous = attributes.get(name);
        const source = previous?.target === current ? previous.source : current;
        const local = pageAttributes[name] ?? {};
        const shared = toolbarAttributes[name] ?? {};
        const id = textKey(source);
        const target = Object.hasOwn(local, id) ? local[id] :
          element.closest(config.toolbar.selectors) ? shared[id] : null;
        if (!target) {
          if (previous?.target === current) element.setAttribute(name, source);
          attributes.delete(name);
          continue;
        }
        if (current !== target) element.setAttribute(name, target);
        attributes.set(name, { source, target });
        translatedAttributes.set(element, attributes);
      }
    }
    for (const [element, attributes] of translatedAttributes) {
      if (!element.isConnected || !attributes.size) translatedAttributes.delete(element);
    }
    return { active: true, section, labels: [...labels] };
  }

  function schedule() {
    if (queued || stopped) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      if (!stopped) refresh();
    });
  }

  if (!sectionForPage()) return { active: false, labels: [] };
  globalThis[key]?.stop();
  const observer = new MutationObserver(schedule);
  observer.observe(document.documentElement, {
    subtree: true, childList: true, characterData: true, attributes: true,
    attributeFilter: ['placeholder', 'title'],
  });
  globalThis.navigation?.addEventListener('navigatesuccess', schedule);
  globalThis[key] = {
    refresh,
    stop() {
      stopped = true;
      observer.disconnect();
      globalThis.navigation?.removeEventListener('navigatesuccess', schedule);
      restore();
      delete globalThis[key];
    },
  };
  return refresh();
})
