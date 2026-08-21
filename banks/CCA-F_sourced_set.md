# CCA-F / CCAR-F — сет с цитатами из официальной документации

> 12 вопросов, у каждого разбор со ссылкой на конкретный раздел документации и дословной цитатой оттуда.
> Собрано агентом-исследователем 16 августа 2026: официальный Exam Guide v1.0 (July 2026) + `platform.claude.com` / `code.claude.com` / `modelcontextprotocol.io`.
> **Важно про ссылки:** `docs.claude.com` больше не отдаёт эти страницы — API-раздел переехал на `platform.claude.com`, Claude Code и Agent SDK на `code.claude.com`. Старые ссылки в чужих гайдах теперь редиректы.
> Это тематический дрилл, а не симуляция: домены здесь не сбалансированы по весам (D1 — 4 вопроса, D2 — 3, D3 — 4, D4 — 1, D5 — 0).

## Как этим пользоваться

1. Ответил — прочитай не только разбор, но и цитату. Формулировка в документации и есть то, из чего экзамен лепит правильный вариант.
2. Где blueprint и текущая документация разошлись, в разборе стоит явная пометка. **На экзамене отвечай по blueprint.**

---

# Часть 1 — вопросы

## Domain 1 · Agentic Architecture & Orchestration

**1.** Your agentic loop terminates as soon as the model's response contains a text block saying the work is finished. Sometimes it stops before the last tool result comes back. What is the correct control-flow signal?

- A. Continue while the response contains a `tool_use` block and stop when it contains only text
- B. Continue while `stop_reason` is `"tool_use"`; exit on any other stop reason
- C. Stop when `stop_reason` is `"end_turn"` and keep looping for every other value
- D. Cap the loop at a fixed number of iterations and treat the cap as the termination condition

**2.** A coordinator delegates document analysis to a subagent with the prompt "analyze the findings from the previous step". The subagent replies that it has no findings to analyze. Why?

- A. The subagent's `allowedTools` list is missing the tool it needs to read prior results
- B. The coordinator must wait for the previous subagent to finish before spawning the next one
- C. A subagent starts with a fresh, isolated context window and never sees the coordinator's conversation history, so the findings must be included in the prompt itself
- D. Subagent prompts are limited in length and the findings were truncated

**3.** A refund above $500 must never be executed by the agent. Two designs are proposed: a line in the system prompt forbidding it, and a hook that intercepts the tool call. Which is correct, and what is the trap in the hook choice?

- A. The system prompt is sufficient if the rule is stated in capitals and repeated in the tool description
- B. A hook, because it gives deterministic control — but it has to intercept the call *before* execution; a `PostToolUse` hook runs after the tool already succeeded and cannot undo it
- C. A `PostToolUse` hook, because it sees the actual refund amount in the result and can roll the transaction back
- D. Either works: hooks and prompt instructions both enforce the rule, hooks are merely faster

**4.** In the exam blueprint, which mechanism spawns a subagent, and what must the coordinator's configuration contain?

- A. The `Task` tool, and `allowedTools` must include `"Task"`
- B. An `AgentDefinition` entry alone is enough; no tool permission is involved
- C. The `Spawn` tool, with the subagent named in `subagents`
- D. `fork_session`, which creates the subagent as a branch of the current session

---

## Domain 2 · Tool Design & MCP Integration

**5.** A single endpoint receives invoices, delivery notes and contracts; each has its own extraction schema and the document type is unknown before the call. The model sometimes replies in prose instead of calling an extraction tool. Which `tool_choice` setting fixes this, and what does it guarantee?

- A. `"auto"` — the model decides, which is what you want when the type is unknown
- B. `{"type": "tool", "name": "extract_invoice"}` — forces extraction and you retry with the other schemas if it fails
- C. `"any"` — the model must call one of the provided tools but chooses which one
- D. `"none"` — prevents the prose reply by disabling free-form output

**6.** An MCP tool returns `"Operation failed"` for every failure: payment provider timeouts, malformed order IDs, refunds over the policy ceiling, and missing permissions. How should failures be reported instead?

- A. Raise a JSON-RPC protocol error for each case so the client sees a proper error code
- B. Return the result with `isError: true` plus structured metadata — error category and a retryable flag — and a message saying what to try next
- C. Return an empty successful result and let the agent infer the failure from the missing data
- D. Retry internally until the call succeeds so the agent never sees a failure

**7.** An agent must change one line in a config file, but `Edit` refuses the change: the anchor text it matched on occurs three times in the file. How should the change be applied reliably?

- A. Call `Edit` three times in sequence and let the final call determine the resulting content
- B. Load the whole file with `Read`, apply the change, and write the result back with `Write`
- C. Run `Grep` first to count the occurrences, then call `Edit` once per matching line number
- D. Rename the surrounding identifiers so the anchor text becomes unique, then call `Edit` again

---

## Domain 3 · Claude Code & Developer Workflow

**8.** The root `CLAUDE.md` has grown past a thousand lines covering eight packages. You want each package's file to pull in only the standards relevant to it. Which mechanism does that, and what is its limit?

- A. `@path/to/file` imports, expanded into context at launch, recursive up to four hops deep
- B. A `sources:` array in the CLAUDE.md frontmatter listing the files to load
- C. `.claude/config.json` with an `imports` key resolved at startup
- D. Symlinking the shared standards file into each package directory

**9.** Test files sit next to the code they test throughout the repository (`Button.test.tsx` beside `Button.tsx`), and all of them must follow the same conventions. What applies the conventions automatically?

- A. A `CLAUDE.md` in each directory that contains test files
- B. A skill under `.claude/skills/` holding the test conventions, invoked when writing tests
- C. A file in `.claude/rules/` whose YAML frontmatter carries a `paths` glob such as `**/*.test.tsx`
- D. A section in the root `CLAUDE.md` headed "Testing conventions"

**10.** A codebase-analysis skill floods the main conversation with hundreds of lines of intermediate output. Which SKILL.md frontmatter option isolates it, and what is the consequence for that skill?

- A. `context: fork` — the skill runs in a forked subagent and does not get your conversation history
- B. `isolated: true` — the skill runs in a sandbox and returns only its final message
- C. `allowed-tools` — restricting the tools reduces how much output the skill can produce
- D. `background: true` — the skill runs asynchronously and posts a summary when done

**11.** A CI job runs `claude "Review this PR"` and hangs waiting for interactive input. The findings then have to be parsed by a script and posted as inline comments. Which flags solve both problems?

- A. `--batch` for non-interactive mode, then `--format=json`
- B. `CLAUDE_HEADLESS=true` in the environment, then pipe the output through `jq`
- C. `-p` (or `--print`) for non-interactive mode, then `--output-format json` together with `--json-schema` for schema-constrained findings
- D. Redirect stdin from `/dev/null`, then `--structured-output`

---

## Domain 4 · Prompt Engineering & Structured Output

**12.** A nightly batch of 500 extraction requests comes back and your code matches results to documents by their position in the results list. Roughly one result in five is attached to the wrong document. What went wrong?

- A. The batch exceeded the 24-hour window and partial results were returned out of order
- B. Batch results can come back in any order; requests and responses must be correlated by the `custom_id` field
- C. The batch API silently drops failed requests, which shifts every subsequent position
- D. Results are ordered correctly only when every request uses an identical prompt prefix

---

# Часть 2 — ключ и разбор

Запись: номер, верный вариант, task statement, разбор, затем ссылка на документацию с дословной цитатой.

## Разбор

**1 · B** · TS 1.1. Цикл управляется полем `stop_reason`: пока оно `"tool_use"` — выполняешь тулы и продолжаешь, на любом другом значении выходишь.
- A: наличие блока `tool_use` — следствие, а не сигнал; текстовый блок часто приходит вместе с ним, и проверка «только текст» ломается ровно на этом.
- C: перевёрнутая логика — так цикл будет крутиться на `end_turn` и останавливаться на всём остальном.
- D: лимит итераций — страховка от зацикливания, а не механизм завершения; blueprint называет это анти-паттерном дословно.
- Тонкость сверх blueprint: выходов больше двух — документация перечисляет `end_turn`, `max_tokens`, `stop_sequence`, `refusal`. Формулировка «выходим на любом не-`tool_use`» точнее, чем «выходим на `end_turn`».
Источник: https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works#the-agentic-loop-client-tools — «The loop exits on any other stop reason (`end_turn`, `max_tokens`, `stop_sequence`, or `refusal`), which means Claude has either produced a final answer or stopped for another reason that your application should handle.»
Источник: https://platform.claude.com/docs/en/api/handling-stop-reasons — «Claude is calling a tool and expects you to run it.»

**2 · C** · TS 1.2 и TS 1.3. Субагент стартует с чистым контекстом: он не видит ни истории диалога координатора, ни прочитанных файлов. Всё, что ему нужно, кладётся прямо в промпт вызова.
- A: `allowedTools` управляет доступом к тулам, а не видимостью чужого контекста.
- B: последовательность здесь ни при чём — даже дождавшись предыдущего агента, координатор обязан передать результат явно.
- D: длина промпта не ограничивала бы находки до нуля.
- Важная оговорка: изоляция не абсолютна — иерархия `CLAUDE.md` наследуется, а fork, наоборот, наследует родительский диалог. Вариант «субагент не наследует вообще ничего» тоже был бы неверен.
Источник: https://code.claude.com/docs/en/sub-agents#what-loads-at-startup — «Each subagent starts with a fresh, isolated context window. It doesn't see your conversation history, the skills you've already invoked, or the files Claude has already read.»
Источник: https://code.claude.com/docs/en/agent-sdk/subagents#what-subagents-inherit — «The only content you pass from parent to subagent is the Agent tool's prompt string, so include any file paths, error messages, or decisions the subagent needs directly in that prompt.»

**3 · B** · TS 1.5. Хук даёт детерминированный контроль там, где промпт даёт вероятностный. Но перехватывать надо исходящий вызов: `PostToolUse` срабатывает после успешного выполнения тула и отменить его не может.
- A: капслок и дублирование в описании тула не превращают вероятностное соблюдение в гарантию.
- C: откат средствами хука — выдумка; деньги уже ушли.
- D: уравнивать хук и промпт — ровно то различие, которое blueprint проверяет.
Источник: https://code.claude.com/docs/en/hooks-guide — «Hooks are user-defined shell commands. Claude Code runs them at specific points in its lifecycle, which gives you deterministic control: certain actions always happen rather than relying on the LLM to choose to run them.»
Источник: https://code.claude.com/docs/en/memory#claude-md-vs-auto-memory — «To block an action regardless of what Claude decides, use a PreToolUse hook instead.»

**4 · A** · TS 1.3. По blueprint субагенты порождаются тулом `Task`, и в `allowedTools` координатора должен быть `"Task"` — иначе вызовы просто не исполняются.
- B: `AgentDefinition` описывает субагента, но не даёт права его вызвать.
- C: тула `Spawn` не существует.
- D: `fork_session` ветвит сессию для сравнения подходов, а не порождает субагента.
- ⚠️ Расхождение с текущим продуктом: в Claude Code 2.1.63 тул переименован в `Agent`, `Task` оставлен алиасом, а префикс `Task` теперь носят несвязанные тулы списка задач (`TaskCreate`, `TaskStop`). **На экзамене верный ответ — `Task`**, по blueprint; в жизни пишешь `Agent`.
Источник: https://code.claude.com/docs/en/sub-agents#let-subagents-spawn-their-own-subagents — «In version 2.1.63, the Task tool was renamed to Agent. Existing `Task(...)` references in settings and agent definitions still work as aliases.»
Источник: https://code.claude.com/docs/en/agent-sdk/subagents#detect-subagent-invocation — «Claude invokes subagents through the `Agent` tool, so include `Agent` in `allowedTools` to auto-approve subagent invocations without a permission prompt.»

**5 · C** · TS 2.3 и TS 4.3. `"any"` обязывает модель вызвать какой-нибудь тул, оставляя выбор схемы за ней — это и нужно, когда тип документа заранее неизвестен.
- A: `"auto"` разрешает ответить текстом, что и происходит.
- B: форсировать схему счёта на неизвестном типе означает извлекать инвойс из договора; ретраи по остальным схемам — дорогой костыль.
- D: `"none"` запрещает тулы вовсе, то есть гарантирует именно прозу.
- Побочный эффект, который любят проверять: при `"any"` и форсированном туле модель не выдаёт текстового пояснения перед вызовом, даже если попросить.
Источник: https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools#forcing-tool-use — «`any` tells Claude that it must use one of the provided tools, but doesn't force a particular tool.»

**6 · B** · TS 2.2. Ошибка исполнения тула возвращается результатом с `isError: true`, а структурированные метаданные — категория и признак повторяемости — позволяют агенту выбрать поведение вместо угадывания.
- A: протокольные ошибки JSON-RPC — для неизвестных тулов и невалидных аргументов, а не для сбоя бизнес-операции.
- C: пустой успех — молчаливое подавление ошибки, названный анти-паттерн.
- D: бесконечные внутренние ретраи бессмысленны для невалидного ID и отсутствующих прав.
- Ловушка на написание: в протоколе MCP поле называется `isError`, в Messages API — `is_error`.
Источник: https://modelcontextprotocol.io/specification/2025-06-18/server/tools#error-handling — «Tool Execution Errors: Reported in tool results with `isError: true`: API failures / Invalid input data / Business logic errors»
Источник: https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls#handling-errors-with-is_error — «Instead of generic errors like `failed`, include what went wrong and what Claude should try next.»

**7 · B** · TS 2.5. `Edit` работает точным совпадением строки и требует, чтобы якорь встречался ровно один раз. Когда уникального якоря нет, blueprint предписывает откат на полное чтение и запись файла: `Read`, затем `Write`.
- A: повторные вызовы `Edit` упрутся в ту же неуникальность, а «последний победит» — не механика этого тула.
- C: `Grep` посчитает вхождения, но `Edit` не принимает номер строки как якорь, так что применить правку этим не выйдет.
- D: переименовывать код ради того, чтобы инструмент нашёл якорь, — менять предметную область под ограничение инструмента.
- ⚠️ Расхождение с текущим продуктом: документация решает ту же проблему иначе — удлинить якорь до уникального фрагмента или поставить `replace_all: true`. **На экзамене верный ответ — `Read` + `Write`**, по blueprint; в работе используешь `replace_all`.
Источник: https://code.claude.com/docs/en/tools-reference — «Uniqueness: `old_string` must appear exactly once. When it appears more than once, Claude either supplies a longer string with enough surrounding context to pin down one occurrence, or sets `replace_all: true` to replace them all.»

**8 · A** · TS 3.1. Синтаксис `@path` подключает внешний файл, содержимое разворачивается в контекст при запуске; вложенность импортов ограничена четырьмя уровнями.
- B, C, D: ни `sources:` во frontmatter, ни `imports` в `.claude/config.json` не существуют, а симлинки не дают избирательности по пакетам.
Источник: https://code.claude.com/docs/en/memory — «CLAUDE.md files can import additional files using `@path/to/import` syntax. Imported files are expanded and loaded into context at launch alongside the CLAUDE.md that references them.»
Источник: https://code.claude.com/docs/en/memory — «Relative paths resolve relative to the file containing the import, not the working directory. Imported files can recursively import other files, with a maximum depth of four hops.»

**9 · C** · TS 3.3. Правила в `.claude/rules/` c полем `paths` во frontmatter подключаются по glob-паттерну независимо от каталога — ровно случай файлов, разбросанных по всему дереву.
- A: `CLAUDE.md` привязан к каталогу, а тестов десятки каталогов.
- B: скилл загружается по вызову, а требуется автоматика.
- D: раздел в общем файле полагается на то, что модель сама сообразит, к чему он относится.
Источник: https://code.claude.com/docs/en/memory#organize-rules-with-clauderules — «Rules can be scoped to specific files using YAML frontmatter with the `paths` field. These conditional rules only apply when Claude is working with files matching the specified patterns.»

**10 · A** · TS 3.2. `context: fork` запускает скилл в отдельном субагентском контексте, поэтому его вывод не оседает в основном диалоге. Плата за это — скилл не видит историю разговора.
- B и D: `isolated` во frontmatter нет; `background` существует, но работает только вместе с `context: fork` и решает другую задачу.
- C: `allowed-tools` ограничивает права, а не объём вывода.
Источник: https://code.claude.com/docs/en/skills#frontmatter-reference — «context — Set to `fork` to run in a forked subagent context.»
Источник: https://code.claude.com/docs/en/skills — «Add `context: fork` to your frontmatter when you want a skill to run in isolation. The skill content becomes the prompt that drives the subagent. It won't have access to your conversation history.»

**11 · C** · TS 3.6. `-p` (`--print`) исполняет промпт без интерактивного режима и выходит, а `--output-format json` вместе с `--json-schema` даёт машиночитаемый результат под заданную схему.
- A, B, D: `--batch`, `CLAUDE_HEADLESS`, `--structured-output` — выдуманные механизмы; это фирменный стиль дистракторов этого task statement. Перенаправление stdin не отвечает на вопрос о формате вывода.
Источник: https://code.claude.com/docs/en/cli-reference — «`--print`, `-p` — Print response without interactive mode»
Источник: https://code.claude.com/docs/en/headless#get-structured-output — «To get output conforming to a specific schema, use `--output-format json` with `--json-schema` and a JSON Schema definition.»

**12 · B** · TS 4.5. Порядок результатов в батче не гарантирован, сопоставление идёт по `custom_id`. Позиция в списке — не идентификатор.
- A: истечение окна даёт истёкшие запросы, а не перемешанные.
- C: неудачные элементы помечаются в результатах, а не выпадают молча.
- D: общий префикс влияет на кеш, а не на порядок.
- ⚠️ Смежное утверждение blueprint — «батч не поддерживает многоходовой вызов тулов внутри запроса» — **противоречит текущей документации**, где tool use и многоходовые диалоги прямо перечислены как поддерживаемые в батче. На экзамене отвечай по blueprint, но ссылку на доки под это утверждение не подкладывай.
Источник: https://platform.claude.com/docs/en/build-with-claude/batch-processing — «Batch results can be returned in any order, and may not match the ordering of requests when the batch was created. To correctly match results with their corresponding requests, always use the `custom_id` field.»

---

# Часть 3 — подсчёт и диагностика

## Ответы одной строкой

| 1–12 |
|---|
| B C B A C B B A C A C B |

## Результат по доменам

| Домен | Номера вопросов | Всего | Твой результат |
|---|---|---|---|
| 1 · Agentic Architecture & Orchestration | 1, 2, 3, 4 | 4 | |
| 2 · Tool Design & MCP Integration | 5, 6, 7 | 3 | |
| 3 · Claude Code & Developer Workflow | 8, 9, 10, 11 | 4 | |
| 4 · Prompt Engineering & Structured Output | 12 | 1 | |

## Где blueprint расходится с текущей документацией

| Вопрос | Blueprint | Текущая документация |
|---|---|---|
| 4 | тул называется `Task` | переименован в `Agent` в версии 2.1.63, `Task` — алиас |
| 7 | при неуникальном якоре — `Read` + `Write` | удлинить якорь или `replace_all: true` |
| 12 | батч не поддерживает многоходовой вызов тулов | tool use и многоходовые диалоги перечислены как поддерживаемые |
| 1 | выход из цикла по `end_turn` | выход по любому не-`tool_use` значению, их шесть |

На экзамене отвечай по blueprint. Эта таблица — чтобы после сертификации не унести с собой устаревшую картину.
