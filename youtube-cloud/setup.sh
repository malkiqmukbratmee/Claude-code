#!/bin/bash
# Подготовка на облачната среда за YouTube фабриката. Сложи го като Setup script на средата
# (менюто на средата → Edit → Setup script): bash youtube-cloud/setup.sh
# Не спира при грешка в незадължителна стъпка (например моделът, ако HuggingFace е блокиран).
set -u
log() { echo "[youtube-cloud] $*"; }

# 1. Шрифтове: Montserrat Black (субтитри, заглавия)
FD="$HOME/.local/share/fonts"; mkdir -p "$FD"
[ -f "$FD/Montserrat-Black.ttf" ] || curl -sfL -o "$FD/Montserrat-Black.ttf" \
  https://raw.githubusercontent.com/JulietaUla/Montserrat/master/fonts/ttf/Montserrat-Black.ttf \
  && log "шрифт: ок" || log "шрифт: НЕ се свали"
command -v fc-cache >/dev/null && fc-cache -f >/dev/null 2>&1

# 2. Програми
command -v ffmpeg >/dev/null || { apt-get update -qq && apt-get install -y -qq ffmpeg; }
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
uv tool install -q yt-dlp >/dev/null 2>&1 && log "yt-dlp: ок" || log "yt-dlp: НЕ се инсталира"

# 3. Python пакетите в кеша на uv (за да не се свалят при всяко видео)
uv run --quiet --with faster-whisper --with numpy --with pillow --with imagehash \
  --with google-api-python-client --with google-auth python -c "import faster_whisper, googleapiclient, PIL" \
  && log "python пакети: ок" || log "python пакети: НЕ"

# 4. Моделът за whisper (~1.6 GB), ако HuggingFace е позволен в мрежата
uv run --quiet --with faster-whisper python -c "from faster_whisper import WhisperModel; WhisperModel('large-v3-turbo', device='cpu', compute_type='int8')" \
  >/dev/null 2>&1 && log "whisper модел: ок" || log "whisper модел: НЕ (huggingface.co блокиран?)"
exit 0
