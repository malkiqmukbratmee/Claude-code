# youtube-cloud

YouTube фабриката без Mac и без CapCut: сваляне, рязане, монтаж и качване от облачна сесия на Claude Code.

| Файл | Какво прави |
|---|---|
| `render_long.py` | дългото видео: снимки на 80% върху бял фон, карти със заглавия, бутон „абонирай се“ (махнато зелено, без звук), войсът |
| `render_short.py` | шортове 9:16: видеото x1.25, червено заглавие (Slide Down / Fade Out) до половината, „АБОНИРАЙ СЕ / ЗА КАНАЛА“ последните 4 s, субтитри ГЛАВНИ на един ред; реже в най-тихото място |
| `yt_upload.py` | вход в каналите с код (google.com/device), качване private или насрочено, тъмбнейл, проверка, квота → `.pending.json` |
| `setup.sh` | подготвя средата: шрифт, yt-dlp, python пакети, моделът за whisper |
| `check_description.py` | проверява описанието по правилата (без тирета, глави от 0:00, ред за абониране, 4–5 хаштага; шорт: 2–3 изречения и #shorts); `yt_upload.py` я пуска сам |
| `notion_when.py` | чете датата и часа под „Качване:“ в Notion; без конкретна дата И час връща „НЯМА“ |
| `fonts.py` | намира шрифтовете |

Рязането на войса и whisper са в skill-а `youtube-factory` (`pipeline/voice-cut`, работи и на Linux с faster-whisper).

## Какво трябва на средата

- **Мрежа:** Full. Свалят се войсове от Google Drive, моделът от huggingface.co и снимки от много сайтове.
- **Ключът за Serper:** network secret за `google.serper.dev` (хедър `X-API-KEY`), заявките вървят без ключ в кода.
- **Променлива:** `YT_CLIENT_SECRET_JSON` (OAuth клиент от тип „TVs and Limited Input devices“).
- **Токените на каналите:** в `YT_TOKENS_FILE` (по подразбиране `~/.config/youtube-cloud/tokens.json`). Контейнерът се трие, затова файлът се пази извън него.

## Команди

```bash
uv run --with pillow python render_long.py plan.json
```

```bash
uv run --with pillow --with numpy python render_short.py shorts.json
```

```bash
uv run --with google-api-python-client --with google-auth python yt_upload.py auth
```

```bash
uv run --with google-api-python-client --with google-auth python yt_upload.py upload plan.json --dry-run
```

## Закон за качване

Видеото и шортовете се обработват веднага, но се качват и насрочват **само** когато в Notion има И конкретна дата и час под „Качване:“, И тъмбнейл под „Тъмб:“ (`notion_tumb`, свален като `thumbnail`). `yt_upload.py` изчислява часа сам от суровия текст (`notion_kacvane`, за шорт и `slot` като `D+1 12:00`) и отказва всичко без дата и час. Първо се качва дългото видео, а шортовете след него (`D+1` до `D+3`, никога в същия ден или преди дългото); ако дългото не мине, шортовете не тръгват. Готовото чака и при всяка проверка се гледа дали датата се е появила.
