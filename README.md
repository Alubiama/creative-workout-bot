# Creative Workout Bot

Персональный Telegram-агент для ежедневной тренировки креативного мышления.

## Стек
- Python 3.10+
- aiogram 3.x
- SQLite + aiosqlite
- Anthropic Claude API

---

## Установка и запуск

### 1. Получить токены

**Telegram:**
1. Открой [@BotFather](https://t.me/BotFather) в Telegram
2. Напиши `/newbot`
3. Дай имя и username
4. Скопируй токен

**Anthropic:**
1. Зарегистрируйся на [console.anthropic.com](https://console.anthropic.com)
2. API Keys → Create Key
3. Скопируй ключ

### 2. Настроить окружение

```bash
cd E:\projects\creative_bot

# Создать .env
copy .env.example .env
```

Открой `.env` и вставь токены:
```
TELEGRAM_BOT_TOKEN=7xxxxxxxxx:AAF...
ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Установить зависимости

```bash
pip install -r requirements.txt
```

### 4. Запустить

```bash
python bot.py
```

Бот запустится в polling-режиме. Пока консоль открыта — бот работает.

---

## Команды

| Команда | Что делает |
|---------|-----------|
| `/start` | Первый запуск — онбординг + baseline |
| `/deep` | Глубокая сессия (дома, 15-20 мин) |
| `/quick` | Быстрая сессия (в дороге) |
| `/incubate` | Задача на фоновое обдумывание |
| `/answer` | Ответить на задачу инкубации |
| `/stats` | Прогресс и статистика |
| `/streak` | Текущий стрик |
| `/help` | Список команд |

---

## Блоки упражнений

| Тип | Описание |
|-----|---------|
| `aut` | Альтернативное применение (Guilford 1967) |
| `rat` | Удалённые ассоциации (Mednick 1962) |
| `forced` | Вынужденные связи |
| `constraints` | Мышление в ограничениях |
| `triz` | ТРИЗ-принципы |
| `pitch` | Вербализация идеи |
| `frames` | Смешение фреймов |
| `quantity` | Дрель количества |

---

## Прогрессия

- 4 уровня по каждому типу упражнений
- Если 3 сессии подряд оцениваешь «Легко» → уровень растёт автоматически
- LLM оценивает оригинальность по шкале 1-5 и даёт конкретный фидбек

---

## Следующий шаг (после MVP)

Перенести на VPS: сервер Ubuntu 22.04, systemd-сервис, ~$5/мес (Hetzner/DigitalOcean).

```bash
# На VPS:
git clone ...
pip install -r requirements.txt
# Настроить systemd unit
systemctl enable creative-bot && systemctl start creative-bot
```
