

# Live Spread Bot for Polymarket

A Python bot that continuously monitors **live Polymarket prediction markets** and sends **Telegram alerts** when meaningful bid-ask spreads appear under configurable liquidity and activity conditions.

This tool is designed for traders and analysts who want to identify **active, liquid markets with exploitable spreads** in real time.

---

## ✨ Features

* 📊 Fetches live market data from Polymarket’s public API
* 🔍 Filters markets by:

  * Minimum volume
  * Spread range
  * Volume delta
  * Price movement
  * Persistence across cycles
* 📈 Scores and ranks markets by activity and spread significance
* 🔔 Sends alerts directly to Telegram
* 💾 Persists market state between cycles to detect “live” changes
* 🧵 Non-blocking Telegram notifications using asyncio + threading
* ⚙️ Fully configurable via environment variables and constants

---

## 🧠 How It Works

1. Fetches all active, open markets from the Polymarket API (paginated)
2. Parses best bid, best ask, volume, and spread
3. Compares current data to previous cycle state
4. Applies filtering criteria:

   * Volume threshold
   * Spread bounds
   * Volume change
   * Price movement
   * Persistence across cycles
5. Scores qualifying markets
6. Sends top alerts to Telegram
7. Saves market state locally and repeats on a fixed interval

---

## 📦 Requirements

* Python **3.9+**
* A Telegram bot token
* A Telegram chat ID

### Python Dependencies

```bash
pip install requests python-dotenv python-telegram-bot
```

---

## 🔐 Environment Variables

Create a `.env` file in the project root:

```env
TELEGRAM_TOKEN=your_telegram_bot_token
CHAT_ID=your_chat_id
```

---

## ⚙️ Configuration

All configuration is centralized in the `Config` dataclass:

| Parameter              | Description                     | Default             |
| ---------------------- | ------------------------------- | ------------------- |
| `CHECK_INTERVAL`       | Seconds between scans           | `180`               |
| `MIN_VOLUME`           | Minimum market volume           | `100_000`           |
| `MIN_SPREAD`           | Minimum spread                  | `0.05`              |
| `MAX_SPREAD`           | Maximum spread                  | `0.5`               |
| `MIN_VOLUME_DELTA`     | Required volume increase        | `0`                 |
| `MIN_PRICE_MOVE`       | Required price movement         | `0`                 |
| `PERSISTENCE_CYCLES`   | Required consecutive cycles     | `1`                 |
| `MAX_ALERTS_PER_CYCLE` | Max alerts sent per cycle       | `6`                 |
| `TELEGRAM_DELAY`       | Delay between Telegram messages | `0.8s`              |
| `DATA_FILE`            | Local state file                | `market_state.json` |

---

## ▶️ Running the Bot

```bash
python bot.py
```

Once started, the bot will:

* Run indefinitely
* Log activity to stdout
* Send Telegram alerts when qualifying markets appear

---

## 📬 Example Telegram Alert

```
🚨 LIVE SPREAD ALERT 🚨

Will BTC exceed $100k by 2025?
Spread: 0.1234 (12.3%)
Volume: $245,000
https://polymarket.com/event/example-slug
```

---

## 🗂 Project Structure

```
.
├── bot.py
├── .env
├── market_state.json
└── README.md
```

---

## 🛠 Design Notes

* Uses a persistent JSON state file to track historical values
* Telegram messaging runs in a background asyncio loop to avoid blocking
* Resilient to API and network errors (logs and continues)
* Stateless API fetch, stateful decision logic

---

## ⚠️ Disclaimer

This bot is **not financial advice**. Prediction markets involve risk. Always evaluate spreads, liquidity, and execution constraints independently before trading.

---

## 📄 License

MIT License — free to use, modify, and distribute.
