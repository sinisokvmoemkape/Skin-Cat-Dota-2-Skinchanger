# Skin Cat

Free, independent, open-source project for a local Dota 2 cosmetic catalog, one personal selection, and a future user-side visual customization workflow. It is not affiliated with Valve or Overplus and does not copy proprietary code or assets.

## Русский

**Цель проекта:** бесплатный независимый open-source инструмент с минимальным окном ожидания запуска Dota 2 и всеми основными функциями в оверлее. Косметика сохраняется в одной локальной подборке без системы именованных профилей. Проект не связан с Valve или Overplus и не копирует чужой закрытый код или ассеты. Локальность сама по себе не означает, что изменение клиента разрешено или безопасно для сетевой игры.

**Текущий статус:** первая версия ориентирована на Linux. Минимальное окно ожидания, внешний оверлей, единая локальная подборка и ручной поиск публичной исторической статистики через OpenDota реализованы; Linux offscreen-проверки проходят. Windows остаётся целью будущей совместимости, но не блокирует Linux-first выпуск. Косметический каталог пока содержит помеченные образцы. Файлы игры не изменяются. Цель для будущего применения косметики — замена соответствующих VPK-файлов, но она `BLOCKED`: официальное разрешение и поддерживаемый способ не подтверждены, текущая политика безопасности запрещает запись в игру, а Dota2PornFx не разрешил интеграцию Skin Cat в перечне одобренных проектов. До отдельного review правил, совместимости, обратимости и письменного разрешения на контент загрузчик и writer не реализуются; обход защиты и античита исключён.

### Запуск из исходников

Целевая версия Python — 3.12–3.14. Локальная проверка выполнена на Linux/Python 3.14.7; CI настроен для проверки Python 3.12 на Windows и Ubuntu и Python 3.14 на Ubuntu. На Linux с Fish:

```fish
python -m venv .venv
source .venv/bin/activate.fish
python -m pip install -e '.[dev]'
python scripts/compile_translations.py
python -m skin_studio
# or, after installing the package:
skin-cat
```

На Linux с Bash/Zsh команда активации: `source .venv/bin/activate`. Если Qt не может открыть платформенное окно, установите системные библиотеки Qt platform plugin для вашего окружения рабочего стола.

В Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
python scripts/compile_translations.py
python -m skin_studio
# or:
skin-cat
```

Если PowerShell запрещает запуск локального скрипта активации, окружение можно использовать без активации: `.\.venv\Scripts\python.exe -m pip install -e '.[dev]'`, затем запускать тем же `python.exe`.

### Данные и ограничения

- Русский и английский языки переключаются в настройках и сохраняются локально.
- Каталог героев содержит только пример названий, без игровых изображений.
- Каталог косметики содержит демонстрационные категории (предметы героев, курьеры, варды, погода, ландшафт, музыка, HUD, дикторы и др.), поиск, фильтр и избранное. Записи явно помечены как образцы и не содержат игровых ассетов.
- В оверлее каталог и единая локальная подборка: можно искать, фильтровать, добавлять и удалять записи. Это локальный список для preview; он не меняет игру.
- При обновлении один прежний профиль автоматически переносится в подборку. Если их было несколько, старые таблицы сохраняются без изменений, а новая подборка начинается пустой, чтобы приложение не выбирало один из наборов за пользователя.
- В Настройки → «Резервное копирование и восстановление данных» можно экспортировать SQLite snapshot Skin Cat и предварительно проверить архив перед восстановлением. Архив содержит manifest и SHA-256; перед применением показывается состав и требуется подтверждение. Включена только база приложения (до 512 MiB), настройки/журналы и Steam/Dota файлы не включаются. Восстановление поддерживает только текущую версию схемы.
- Главное окно показывает логотип Skin Cat и состояние ожидания/обнаружения Dota 2. Во время ожидания котик моргает и плавно поднимает обе передние лапки: первый жест примерно через секунду, затем примерно раз в пять секунд; фон надписей прозрачен. Каталог и другие основные функции открываются в отдельном OS-окне оверлея.
- Компактная кнопка-котик появляется при обнаружении процесса Dota 2, пока главное окно Skin Cat открыто, с небольшим отступом от левого и верхнего края экрана под курсором. Если Skin Cat свернуть в трей, кнопка скрывается и не появляется до восстановления Skin Cat. Нажатие раскрывает отдельную OS-панель строго по центру этого экрана. В KDE/Wayland глобальная комбинация по умолчанию `Ctrl+Shift+O` регистрируется через системный портал; её можно переназначить через Настройки → Настроить клавишу. Портал попросит подтвердить глобальную клавишу. На Wayland кнопка привязана к экрану, а не к геометрии окна игры: ОС не предоставляет приложению универсальное управление чужими окнами. Exclusive fullscreen требует отдельной проверки.
- Желаемая цель — визуально связанная с Dota панель, если будет найден подходящий способ интеграции. Внутрипроцессный вариант пока заблокирован для отдельной технической и policy-оценки; текущая версия остаётся внешним OS-окном и не изменяет игровой процесс.
- Пока Dota 2 закрыта, кнопка «Публичная история игрока» открывает ручной поиск по Steam32 ID или SteamID64 через OpenDota API. Показываются публичные имя/ранг и общие победы/поражения; видны источник и время запроса. ID передаётся только после нажатия кнопки и не сохраняется. Окно закрывается при обнаружении Dota 2; оверлей не показывает статистику игроков. Данные могут быть неполными или устаревшими; приватные данные и состав матча не запрашиваются.
- Поиск Steam только читает известные пути и `libraryfolders.vdf`.
- Единственный сетевой запрос — инициированный пользователем запрос к OpenDota для публичной исторической статистики; каталог, подборка и остальные функции работают offline. Записи в игровые ресурсы, чтение памяти процесса, инъекция и обход защиты отсутствуют. Обнаружение процесса проверяет только его имя через список процессов ОС.
- Данные приложения находятся в пользовательских каталогах XDG на Linux и AppData на Windows.

### Разработка

```shell
python scripts/compile_translations.py
ruff check .
QT_QPA_PLATFORM=offscreen pytest
```

На Windows используйте `python -m pytest`; Qt тесты запускаются с offscreen backend через конфигурацию тестов. CI запускает проверки на Windows и Ubuntu. Подробности см. в `docs/`.

## English

**Project goal:** a free, independent, open-source tool with a minimal Dota 2 waiting screen, desktop overlay, and one local cosmetic selection without named profiles. The project is not affiliated with Valve or Overplus and does not copy proprietary code or assets. Local-only operation alone does not establish that changing the client is permitted or safe for online play.

**Current status:** the first release targets Linux. The minimal waiting screen, desktop overlay, single local selection, and manual OpenDota public-history lookup are implemented; Linux offscreen checks pass. Windows remains a future compatibility target and does not block the Linux-first release. The catalog currently contains clearly marked sample data. The app does not modify game files. The target for future cosmetic application is replacing the corresponding VPK files, but this remains `BLOCKED`: no official permission or supported method is confirmed, the current security policy prohibits writing to the game, and Dota2PornFx has not approved Skin Cat as an integration project. No downloader or writer will be implemented before a separate review of rules, compatibility, reversibility, and written content permission; security or anti-cheat bypass is out of scope.

### Run from source

Target Python versions are 3.12–3.14. Local checks ran on Linux/Python 3.14.7; CI is configured for Python 3.12 on Windows and Ubuntu and Python 3.14 on Ubuntu. On Linux:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python scripts/compile_translations.py
python -m skin_studio
```

On Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e '.[dev]'
python scripts/compile_translations.py
python -m skin_studio
```

### Data and limitations

- Switch between Russian and English in Settings; the choice is saved locally.
- The hero catalog contains sample names only and no game artwork.
- The cosmetic catalog has sample categories (hero items, couriers, wards, weather, terrain, music, HUD, announcers, and others), search, category filters, and favorites. Entries are labelled as samples and contain no game assets.
- The overlay provides the catalog and one personal local selection where entries can be searched, filtered, added, and removed. This list is only for local preview; it does not change the game.
- On upgrade, the contents of one previous profile are copied into the selection. If there were multiple profiles, their legacy database rows remain unchanged and the new selection starts empty so the app does not choose one on the user's behalf.
- Settings → “Back up or restore application data” exports a consistent SQLite snapshot and validates a selected archive before restore. The ZIP contains a manifest and SHA-256 checksum; a preview shows the database contents and restore requires confirmation. Only the app database (up to 512 MiB) is included; settings, logs, Steam, and Dota 2 files are excluded. Restore accepts only the current schema version.
- The main window shows the Skin Cat logo and whether Dota 2 is waiting or detected. While waiting, the cat blinks and smoothly raises both front paws: the first gesture starts after about a second, then repeats about every five seconds; text backgrounds stay transparent. The catalog and other main features open in a separate OS overlay window.
- A compact translucent cat button appears when the Dota 2 process is detected while the Skin Cat main window is open, inset from the top and left edges of the screen under the cursor. Hiding Skin Cat to the tray hides the button until Skin Cat is restored. Clicking it opens a separate OS panel centered on that screen. On KDE/Wayland, `Ctrl+Shift+O` is registered through the desktop portal and can be reassigned through Settings → Configure shortcut. The portal asks for approval. On Wayland the button follows the screen, not the game's window geometry; the OS does not provide a universal way to control another app's window. Exclusive fullscreen needs separate review.
- The long-term UI goal is a panel visually associated with Dota if a suitable integration method is established. An in-process variant is blocked pending separate technical and policy review; the current version remains an external OS window and does not alter the game process.
- Steam discovery only reads known paths and `libraryfolders.vdf`.
- The only network requests are user-initiated OpenDota lookups for public historical profile aggregates; the catalog and local selection work offline. The app does not write game resources, read process memory, inject code, or bypass security. Process presence detection checks only the executable name through the operating system.
- While Dota 2 is closed, the main window offers a manual Steam32 ID/SteamID64 lookup through the OpenDota API. It displays public profile/rank data and aggregate wins/losses with the source and retrieval time. The ID is sent only after submission and is not saved. The lookup closes when Dota 2 is detected; player stats are not shown in the overlay. Provider data may be incomplete or delayed.
- No OpenDota request is made automatically. A lookup sends the numeric account ID to `api.opendota.com`; OpenDota terms and availability apply. The displayed retrieval time is not a guarantee of how recently the underlying match data was updated.
- Application data uses user XDG directories on Linux and AppData on Windows.

See `docs/` for architecture, feature status, source provenance, feasibility notes, and the Milestone 1 plan. The project code is MIT licensed; this does not grant rights to Valve game assets or other third-party materials.
