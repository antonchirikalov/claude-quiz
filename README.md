# Claude Certified Architect — Practice Quiz

Flask + Jinja2 web app для подготовки к экзамену **Claude Certified Architect (CCA-F)**.

## Что внутри

- Вопросы по всем 5 доменам экзамена с объяснениями правильных ответов
- Случайная выборка вопросов при каждом запуске
- Показ результата с разбором ошибок в конце

## Домены

| Домен | Вес |
|-------|-----|
| Agentic Architecture & Claude Code | 27% |
| Claude Code Configuration | 20% |
| Prompt Engineering | 20% |
| Tools & MCP | 18% |
| Context Management | 15% |

## Быстрый старт

```bash
pip install -r requirements.txt
flask --app app run --debug
```

Открыть: http://localhost:5000

## Генерация вопросов

Банк вопросов хранится в `data/questions.json`. Пополнять его можно двумя способами.

### Способ 1 — Prompt-файл в VS Code Agent Chat (рекомендуется)

Требует: расширение **GitHub Copilot** + подключённый **Tavily MCP**.

1. Открыть VS Code → Agent Chat (`Ctrl+Alt+I`)
2. Нажать кнопку **Attach** → **Prompt...** → выбрать `scripts/generate_questions.prompt.md`
3. Агент сам найдёт материалы через Tavily и допишет вопросы в `data/questions.json`

Промпт настроен на параллельный поиск по всем доменам сразу. Количество вопросов на домен задаётся переменной `count` (по умолчанию 10).

#### Подключение Tavily MCP

В файл настроек VS Code (`settings.json`) добавить:

```json
"mcp": {
  "servers": {
    "tavily": {
      "command": "npx",
      "args": ["-y", "tavily-mcp"],
      "env": {
        "TAVILY_API_KEY": "tvly-ваш-ключ"
      }
    }
  }
}
```

Ключ можно получить бесплатно на [app.tavily.com](https://app.tavily.com).

### Способ 2 — CLI-скрипт с Anthropic API

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python scripts/generate_questions.py
```

Требует действующий `ANTHROPIC_API_KEY`.

## Тесты

```bash
PYTHONPATH=. pytest -q
```

## Структура проекта

```
app/
  __init__.py       — фабрика Flask-приложения
  quiz.py           — загрузка и выборка вопросов
  routes.py         — маршруты (/, /question, /answer, /results)
  schema.py         — Pydantic-схема вопроса
  errors.py         — типизированные исключения
data/
  questions.json    — банк вопросов (источник истины)
scripts/
  generate_questions.py          — CLI-генератор (Anthropic API)
  generate_questions.prompt.md   — агентный промпт для VS Code
templates/          — Jinja2-шаблоны
tests/              — pytest-тесты
```
