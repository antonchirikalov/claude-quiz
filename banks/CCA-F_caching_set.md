# CCA-F / CCAR-F — промпт-кеширование, тематический дрилл

> 8 вопросов. Каждый разбор со ссылкой на официальную страницу документации и дословной цитатой.
> Это **не** симуляция экзамена: домены здесь не сбалансированы, это узкий дрилл по одной теме.

## Зачем этот набор существует

Exam Guide v1.0 относит промпт-кеширование к **Out-of-Scope** — «beyond critical: beyond knowing it exists».
Но сдававшие сообщают, что вопросы по кешированию на экзамене были. Расхождение реальное, и закрывать
его пробелом в подготовке нельзя.

Отсюда калибровка набора: здесь спрашивается то, что на экзамене осмысленно спросить — **что кеш делает,
когда он уместен, что его ломает и как считается экономика**. Механики глубже этого уровня в наборе нет
намеренно: минимальные размеры префикса по моделям, окно просмотра в 20 блоков, прогрев через
`max_tokens: 0` — всё это существует, но за границей того, что подтверждено отчётами.

## Как этим пользоваться

1. Прочитай не только разбор, но и цитату. Формулировка документации и есть то, из чего лепится верный вариант.
2. Единственный факт, из которого выводится почти всё остальное: **кеш — это совпадение префикса по байтам.**
   Любое изменение раньше в промпте обнуляет всё, что после него.

---

# Часть 1 — вопросы

## Domain 5 · Prompt Caching

**1.** A support agent sends the same 6,000-token system prompt on every request and marks it for caching. Across thousands of requests the cache-read token count stays at zero. The prompt's first line reads `Current time: 2026-08-21 14:02:11`. What is happening?

- A. The marker sits on the wrong block, so the system prompt is never written to the cache
- B. The prefix differs every request, so a later request has nothing it can match against
- C. The prompt is below the length at which an entry is created, so writes are skipped
- D. Entries expire before the next request arrives, so every write is paid for and wasted

**2.** The agent needs the current date and the user's display name available on every turn. The shared instructions ahead of them must keep hitting the cache. Where do the two dynamic values belong?

- A. At the top of the system prompt, ahead of the instruction block being cached
- B. Interpolated into each tool description, which is far smaller than the system prompt
- C. In the messages, after the last breakpoint, so nothing ahead of them ever changes
- D. Nowhere — a request carrying per-request values cannot also benefit from caching

**3.** A classification service receives one unrelated 800-token document per request. Nothing is shared between requests except a two-sentence instruction. Should caching be switched on?

- A. No — with no reusable prefix a marker buys the write premium and never earns it
- B. Yes — each document is cached, so a repeat submission of the same one costs less
- C. Yes — the instruction gets cached, which is small but free once the entry exists
- D. No, unless documents are sorted so that similar ones tend to arrive close together

**4.** A 20,000-token prefix is shared across requests, and you are deciding whether the default lifetime is worth enabling. Roughly how much reuse does it take before caching pays for itself?

- A. One request — a cache write costs the same as an ordinary uncached request does
- B. Ten or more, because the write premium is several times the base input price
- C. It never pays off on the default lifetime; only the one-hour option can break even
- D. About two — the write premium is modest and a read costs a fraction of base input

**5.** Mid-conversation the application adds one new tool to the request. The next request reprocesses the entire conversation history uncached. Why does one added tool cost the whole history?

- A. Because any change to the request body invalidates every level of the cache at once
- B. Because tools are the first prefix level, so a change invalidates every later one
- C. Because the added description pushed the prefix beyond the window that is searched
- D. Because a changed tool list routes the request differently, and entries are per-route

**6.** A batch job reuses a large cached prefix and fires the next request the moment the previous response finishes. Every second request is a cache miss. Responses stream for about four and a half minutes each. What explains it?

- A. The default lifetime is one minute, so any response longer than that loses the entry
- B. Streaming responses do not refresh an entry the way non-streaming responses do
- C. The lifetime runs from the request's start, so generation time counts against it
- D. Each new write replaces the previous entry, so only the newest prefix stays readable

**7.** Twenty requests sharing an identical 30,000-token prefix are dispatched in parallel. Not one of them reports a cache read. What should change?

- A. Send one request, wait for its response to begin, then dispatch the remaining nineteen
- B. Nothing — parallel requests land on different instances, which hold separate caches
- C. Cap concurrency at four, matching the number of breakpoints a request may carry
- D. Nothing is wrong: the reads will appear on the next batch, once an entry has been written

**8.** An agent has been running for hours over a long conversation. The last response reports 4,000 input tokens, which is far smaller than the conversation obviously is. How should that number be read?

- A. As the total prompt size, meaning the history must have been compacted along the way
- B. As the newest turn only, because earlier turns are never counted again once cached
- C. As a value that is capped for long conversations and stops being meaningful past a point
- D. As the uncached remainder — the total is that plus the cache-write and cache-read counts

---

# Часть 2 — ключ и разбор

## Разбор

**1 · B** · PC 1. Кеш — это совпадение префикса по байтам, а метка времени стоит в первой строке. Значит каждый запрос строит новый префикс, и совпасть ему не с чем. Ошибок при этом не возвращается — просто счётчик чтений остаётся нулевым, и это главный диагностический признак.
- A: метка на блоке важна, но при меняющемся содержимом её правильное расположение ничего не спасёт.
- C: 6000 токенов заведомо выше любого из минимумов, при которых запись пропускается.
- D: истечение времени жизни давало бы промахи при редких запросах, а здесь их тысячи, и ноль абсолютный.
Источник: https://platform.claude.com/docs/en/build-with-claude/prompt-caching — «Cache hits require 100% identical prompt segments, including all text and images up to and including the block marked with cache control.»

**2 · C** · PC 2. Стабильное — раньше, изменчивое — позже: динамические значения ставятся после последней точки кеширования, тогда всё, что до неё, продолжает читаться из кеша. Документация приводит это как отдельный анти-паттерн с примером.
- A: верх системного промпта — худшее место; оттуда изменение обнуляет весь префикс (ровно случай вопроса 1).
- B: описания тулов — это самый первый уровень префикса, изменение там дороже всего (см. вопрос 5). Малый размер тут не аргумент.
- D: динамика и кеширование сочетаются штатно, вопрос только в порядке.
Источник: https://platform.claude.com/docs/en/build-with-claude/prompt-caching — «For a prompt with a static prefix and a varying suffix (timestamps, per-request context, the incoming message), place the breakpoint at the end of the static prefix, not on the varying block.»
Источник: https://platform.claude.com/docs/en/build-with-claude/prompt-caching — «Place `cache_control` on the last block whose prefix is identical across the requests you want to share a cache.»

**3 · A** · PC 3. Кеш платит за себя только повторным чтением одного и того же префикса. Общего здесь два предложения — этого не хватит даже на минимальный размер записи, а документ каждый раз новый. Записи будут, чтений не будет, останется только надбавка.
- B: кешируется префикс запроса, а не документы как содержимое; повторная подача того же документа — гипотетический случай, на который систему не строят.
- C: «free once the entry exists» неверно вдвойне: запись платная, и двух предложений на запись не хватит.
- D: сортировка сближает похожие документы, но кеш требует побайтового совпадения, а не похожести.
Источник: https://platform.claude.com/docs/en/build-with-claude/prompt-caching — «Shorter prompts cannot be cached, even if marked with `cache_control`. Any requests to cache fewer than this number of tokens will be processed without caching, and no error is returned.»

**4 · D** · PC 4. Арифметика простая. Запись на времени жизни по умолчанию — 1.25× от базовой цены входа, чтение — 0.1×. Два запроса: 1.25 + 0.1 = 1.35 против 2.0 без кеша. То есть окупается уже на втором обращении.
- A: запись дороже обычного запроса, а не равна ему.
- B: надбавка составляет четверть базовой цены, а не кратность.
- C: на часовом времени жизни запись стоит 2×, и окупаемость наступает позже — примерно с третьего обращения (2.0 + 0.2 = 2.2 против 3.0). Часовой вариант нужен для трафика с провалами, а не для более быстрой окупаемости. Вариант переворачивает соотношение.
Источник: https://platform.claude.com/docs/en/build-with-claude/prompt-caching — «5-minute cache write tokens are 1.25 times the base input tokens price», «1-hour cache write tokens are 2 times the base input tokens price», «Cache read tokens are 0.1 times the base input tokens price».

**5 · B** · PC 5. Префикс собирается в порядке `tools` → `system` → `messages`, и изменение на любом уровне обнуляет этот уровень и все следующие. Тулы — самый первый, поэтому один добавленный тул уносит и системный промпт, и всю историю.
- A: «любое изменение обнуляет всё» — слишком широко и неверно. Переключение `tool_choice` или изменение содержимого сообщений оставляет верхние уровни живыми. Иерархия существует именно для этого.
- C: окно просмотра — отдельный механизм, и оно про число блоков между точками кеширования, а не про добавление тула.
- D: маршрутизации «по набору тулов» не существует.
Источник: https://platform.claude.com/docs/en/build-with-claude/prompt-caching — «Cache prefixes are created in the following order: `tools`, `system`, then `messages`. This order forms a hierarchy where each level builds upon the previous ones.»
Источник: https://platform.claude.com/docs/en/build-with-claude/prompt-caching — «the cache follows the hierarchy: `tools` → `system` → `messages`. Changes at each level invalidate that level and all subsequent levels.»

**6 · C** · PC 6. Время жизни считается от **начала** запроса, а не от конца ответа. Генерация ответа съедает его наравне с простоем: при пятиминутном сроке и ответе, который стримится четыре с половиной минуты, на следующий запрос остаётся около половины минуты.
- A: срок по умолчанию — пять минут, не одна.
- B: обновление записи не зависит от того, стримится ответ или нет; каждое использование продлевает её бесплатно.
- D: новая запись не вытесняет прежнюю — записи по разным префиксам сосуществуют.
Источник: https://platform.claude.com/docs/en/build-with-claude/prompt-caching — «The lifetime is measured from the start of the request that writes or reads the cache entry, not from the end of its response. Time spent generating a response counts against the lifetime: if a response takes 4 minutes to stream, a follow-up request that reuses the same cached prefix must start within about 1 minute of that response completing.»
Источник: https://platform.claude.com/docs/en/build-with-claude/prompt-caching — «By default, the cache has a 5-minute lifetime. The cache is refreshed for no additional cost each time the cached content is used.»

**7 · A** · PC 7. Запись становится читаемой с момента, когда **начался** первый ответ, а не когда он завершился. Двадцать одновременных запросов пишут каждый свою запись и все платят полную цену. Достаточно отправить один, дождаться начала ответа и выпустить остальные.
- B: разные экземпляры с отдельными кешами — правдоподобное, но выдуманное объяснение.
- C: четыре — это лимит точек кеширования в одном запросе, к конкурентности он отношения не имеет. Реальное число не на своём месте.
- D: «ничего не сломано» неверно: на этой партии двадцать полных оплат вместо одной, и это исправляется порядком отправки.
Источник: https://platform.claude.com/docs/en/build-with-claude/prompt-caching — «For concurrent requests, note that a cache entry only becomes available after the first response begins. If you need cache hits for parallel requests, wait for the first response before sending subsequent requests.»

**8 · D** · PC 8. Поле входных токенов показывает только остаток после последней точки кеширования, а не весь промпт. Полный размер — сумма трёх счётчиков: остаток плюс записанное плюс прочитанное из кеша. Маленькое значение при длинной истории — признак того, что кеш работает, а не того, что история потерялась.
- A: принять остаток за полный размер — самая дорогая из ошибок в этом списке: по ней делают ложный вывод, что контекст усох, и начинают искать несуществующую проблему.
- B: «последний ход» близко по духу, но неточно: граница проходит по последней точке кеширования, а не по ходу диалога.
- C: никакого ограничения сверху у этого поля нет.
Источник: https://platform.claude.com/docs/en/build-with-claude/prompt-caching — «The `input_tokens` field represents only the tokens that come **after the last cache breakpoint** in your request - not all the input tokens you sent.»
Источник: https://platform.claude.com/docs/en/build-with-claude/prompt-caching — «total_input_tokens = cache_read_input_tokens + cache_creation_input_tokens + input_tokens».

---

# Часть 3 — подсчёт и диагностика

## Ответы одной строкой

| 1–8 |
|---|
| B C A D B C A D |

## Результат по доменам

| Домен | Номера вопросов | Всего | Твой результат |
|---|---|---|---|
| 5 · Context Management & Reliability | 1, 2, 3, 4, 5, 6, 7, 8 | 8 | |

## Что делать с результатом

| Промах | Куда вернуться |
|---|---|
| 1, 2 | Порядок префикса. Стабильное раньше, изменчивое позже. Метка времени в системном промпте — канонический способ всё обнулить |
| 3, 4 | Экономика. Запись 1.25×, чтение 0.1×, окупаемость со второго обращения. Нет повторного использования — нет смысла в кеше |
| 5 | Иерархия `tools` → `system` → `messages`. Изменение обнуляет свой уровень и все следующие, но не предыдущие |
| 6, 7 | Время жизни от начала запроса; запись читаема с начала первого ответа. Оба факта про моменты времени, и оба контринтуитивны |
| 8 | Учёт токенов. Остаток после последней точки кеширования — не полный размер промпта |
