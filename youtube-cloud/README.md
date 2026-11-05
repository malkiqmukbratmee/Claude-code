# youtube-cloud

YouTube фабриката без Mac и без CapCut: сваляне, рязане, монтаж и качване от облачна сесия на Claude Code.

| Файл | Какво прави |
|---|---|
| `render_long.py` | дългото видео: снимки на 80% върху бял фон, карти със заглавия, бутон „абонирай се“ (махнато зелено, без звук), войсът |
| `render_short.py` | шортове 9:16: видеото x1.25, червено заглавие (Slide Down / Fade Out) до половината, „АБОНИРАЙ СЕ / ЗА КАНАЛА“ последните 4 s, субтитри ГЛАВНИ на един ред; реже в най-тихото място |
| `yt_upload.py` | вход в каналите с код (google.com/device), качване private или насрочено, тъмбнейл, проверка, квота → `.pending.json` |
| `setup.sh` | подготвя средата: шрифт, yt-dlp, python пакети, моделът за whisper |
| `fonts.py` | намира шрифтовете |

Рязането на войса и whisper са в skill-а `youtube-factory` (`pipeline/voice-cut`, работи и на Linux с faster-whisper).

## Какво трябва на средата

- **Мрежа:** Full. Свалят се войсове от Google Drive, моделът от huggingface.co и снимки от много сайтове.
- **Променливи:** `SERPER_API_KEY` (снимки от Google Images), `YT_CLIENT_SECRET_JSON` (OAuth клиент от тип „TVs and Limited Input devices“).
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
