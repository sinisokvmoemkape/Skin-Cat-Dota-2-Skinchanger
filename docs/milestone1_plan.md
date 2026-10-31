# План Milestone 1

Статус: согласован пользователем; реализация начата. Linux-проверки проходят, Windows CI ещё не запускался.

## Результат этапа

Запускаемое desktop-приложение на Linux и Windows с навигацией, русским/английским языком, настройками, логированием, SQLite, read-only обнаружением Steam и чётко обозначенными sample данными. Интеграции, меняющие файлы игры, отключены.

## Порядок работ

1. **Основа репозитория:** добавлены `pyproject.toml`, `src/` package, `.gitignore`, инструкция запуска и MIT-лицензия кода; прямые зависимости закреплены в `pyproject.toml`, полного transitive lock-файла пока нет.
2. **Конфигурация и журналирование:** XDG/Windows user directories, язык, версионирование настроек, redaction и уровень логирования.
3. **База:** SQLite connection factory, foreign keys, migration runner, первая схема и integrity check.
4. **Домен и интерфейсы:** базовые модели, ошибки, профили/каталог sample data, платформенный Steam detection interface и simulated resource adapter.
5. **UI:** главное окно, sidebar navigation, страницы Overview/Heroes/Profiles/Settings, тёмная QSS-тема, доступность клавиатурой.
6. **Локализация:** package catalogs в `src/skin_studio/i18n/locale/en` и `ru`, runtime loading и смена языка, persist preference, smoke check critical strings.
7. **Steam discovery:** безопасный read-only поиск конфигов/библиотек, ручной override, обработка отсутствующей установки и native/Proton.
8. **Проверка:** pytest unit/integration для миграций, конфигурации, локализации, путей и simulated adapter. Убедиться, что ни один путь game install не открыт на запись.
9. **CI и документация:** Windows/Linux GitHub Actions, lint/type/translation validation, README EN/RU setup/run, support/limitations, packaging smoke step; зафиксировать текущие ограничения.

## Критерии завершения

- Запуск на локальном CachyOS и Windows через CI или проверенную тестовую среду.
- Рабочая навигация, SQLite initialization/migrations, настройки, logs, read-only Steam discovery.
- Runtime смена русского/английского с сохранением выбора.
- Пользовательские данные вне папки установки и без elevated privileges.
- Нет записи игровых файлов; simulated adapter явно маркирован.
- Unit/integration tests пройдены на Linux и Windows. Каждая команда и результат указаны в отчёте.
- CI конфигурация присутствует; README содержит запуск на двух ОС.

## Предлагаемая GitHub Actions матрица

| Job | OS | Python | Действия |
|---|---|---|---|
| `checks` | Ubuntu latest | 3.12 | Установка зависимостей; компиляция Qt переводов; Ruff; pytest |
| `checks` | Windows latest | 3.12 | Те же проверки на Windows с Qt offscreen backend |
| `compatibility` | Ubuntu latest | 3.14 | Дополнительный запуск тестов, включая локальную версию Python |
| `package-smoke` | Ubuntu latest + Windows latest | 3.12 | Wheel build и запуск установленного wheel через `--smoke`; без публикации артефактов |
| `dependency-audit` | Ubuntu latest | 3.12 | `pip-audit` для зависимостей окружения; исключения требуют документированной причины и срока |

Workflow добавлен, но удалённого GitHub remote в репозитории нет, поэтому Actions ещё не запускался. Не загружать сторонние game assets и не требовать Steam/аккаунт в CI. Release artifact generation, подпись и AppImage cross-distro validation выходят за рамки Milestone 1; сначала выбрать и проверить packaging toolchain.

## Предлагаемая политика Python

Python 3.12 — базовая CI/платформенная цель; Python 3.14 — дополнительная проверка совместимости. PySide6 Essentials и dev-инструменты закреплены точными прямыми версиями в `pyproject.toml`; для полной фиксации транзитивных версий понадобится lock-файл.
