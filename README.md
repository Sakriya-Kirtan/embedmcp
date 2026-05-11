# embedmcp 🔌

> AI-powered search engine for embedded systems developers.  
> One query. Four sources. One answer.

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.3-lightgrey)](https://flask.palletsprojects.com)
[![MCP](https://img.shields.io/badge/MCP-Compatible-green)](https://modelcontextprotocol.io)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)

---

## What is this?

Embedded developers waste hours searching across Stack Overflow, GitHub Issues, Reddit, and vendor forums simultaneously for the same bug. embedmcp fixes that.

Type one query. Get results from all sources at once — with accepted answer content shown inline, a "what to do first" synthesis, and vendor-specific routing (ST, Espressif, Renesas, Nordic, NXP, TI, Arduino, Raspberry Pi).

**Works as:**
- 🌐 **Web app** — search in your browser, no install needed
- 🤖 **MCP server** — plugs into Claude Desktop, Cursor, VS Code Copilot
- 🔌 **API** — call it from your own tools

---

## Demo

```
Query: "STM32 I2C bus hanging"

📊 SUMMARY
SO: 1 | EE: 2 | GitHub: 1 | Reddit: 3 | KB: 2
🏭 Vendor: STMicroelectronics → https://community.st.com

✅ Best answer (accepted, score 6):
   When doing several writes in a row, you must not perform any write
   access to I2C_CR1 before the STOP bit is cleared by hardware...
   → stackoverflow.com/questions/2556794

🐛 Confirmed fix on GitHub (STM32 F4 HAL, closed):
   HAL_I2C_Mem_Read_IT routine causing interrupts to hang processor
   → github.com/STMicroelectronics/STM32CubeF4/issues/63

💬 Active Reddit discussion on r/stm32:
   I2C bus keeps hanging with HAL_Busy (⬆2 upvotes, 4 comments)
   → reddit.com/r/stm32/comments/10jqikz
```

---

## Data Sources

| Source | What it covers | Cost |
|--------|---------------|------|
| Stack Overflow | Firmware, C/C++, RTOS, drivers | Free (10k req/day) |
| EE Stack Exchange | Hardware, PCB, power, analog | Free (same key) |
| GitHub Issues | HAL bugs, SDK issues, RTOS fixes | Free (5k req/hour) |
| Reddit | r/embedded, r/stm32, r/esp32, r/electronics, r/arduino | Free (public API) |
| Vendor Forums | ST, Espressif, Renesas, Nordic, NXP, TI, Arduino, RPi | Direct links |

---

## Vendor Support

Automatically detects and routes to the right vendor community:

| Vendor | Detected keywords | Official forum |
|--------|------------------|----------------|
| STMicroelectronics | stm32, stm8, hal, cube | community.st.com |
| Espressif | esp32, esp8266, esp-idf | esp32.com |
| Arduino | arduino, uno, mega, nano | forum.arduino.cc |
| Raspberry Pi | raspberry-pi, rp2040, pico | forums.raspberrypi.com |
| Renesas | rzg, rzg3e, ra, rx, rl78 | en-support.renesas.com |
| Nordic Semi | nrf52, nrf53, nrf91, ble | devzone.nordicsemi.com |
| NXP | lpc, kinetis, imx, s32 | community.nxp.com |
| Texas Instruments | msp430, tiva-c, cc32xx | e2e.ti.com |

---

## Quick Start

### Web App (hosted)
Just visit your Railway URL — no install needed.

### Run locally

```bash
git clone https://github.com/YOUR_USERNAME/embedmcp
cd embedmcp
python -m venv venv
venv\Scripts\activate       # Windows
source venv/bin/activate    # Linux/Mac
pip install -r requirements.txt
```

Create a `.env` file:
```env
STACK_API_KEY=your_stack_exchange_key
GITHUB_TOKEN=your_github_token
```

Get free API keys:
- Stack Exchange: [stackapps.com/apps/oauth/register](https://stackapps.com/apps/oauth/register)
- GitHub: Settings → Developer settings → Personal access tokens → `public_repo` scope

Run the web app:
```bash
python app.py
# Open http://localhost:5000
```

---

## MCP Server Setup (Claude Desktop / Cursor)

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "embedmcp": {
      "command": "C:\\path\\to\\embedmcp\\venv\\Scripts\\python.exe",
      "args": ["C:\\path\\to\\embedmcp\\server.py"]
    }
  }
}
```

Then ask Claude: *"STM32 I2C bus hanging — search embedded forums"*

Claude will call your server and ground its answer in live community data.

---

## Project Structure

```
embedmcp/
├── app.py              # Flask web app + API
├── server.py           # MCP server (Claude Desktop / Cursor)
├── fetch_stack.py      # Core search orchestrator
├── github_fetch.py     # GitHub Issues fetcher
├── reddit_fetch.py     # Reddit search (public API)
├── renesas_kb.py       # Renesas-specific resources
├── config.py           # Vendor registry + settings
├── requirements.txt    # Python dependencies
└── .env                # API keys (not committed)
```

---

## Architecture

```
User query
    │
    ▼
fetch_stack.py (orchestrator)
    ├── Stack Overflow API    → top questions + accepted answers
    ├── EE Stack Exchange     → hardware/electronics answers
    ├── github_fetch.py       → issues from MCU/RTOS repos
    ├── reddit_fetch.py       → posts from embedded subreddits
    └── vendor detection      → routes to official forum
    │
    ▼
Synthesized results
    ├── server.py     → MCP tool (AI clients)
    └── app.py        → Web UI + REST API
```

---

## Roadmap

- [x] Stack Overflow + EE Stack Exchange search
- [x] GitHub Issues from STM32, ESP-IDF, Zephyr, RP2040 repos
- [x] Reddit integration (r/embedded, r/stm32, r/esp32, etc.)
- [x] Vendor detection + official forum routing
- [x] Accepted answer content fetching
- [x] MCP server for Claude Desktop / Cursor
- [x] Web demo
- [ ] PDF datasheet RAG (RP2040, RISC-V open datasheets)
- [ ] VS Code extension
- [ ] API key system + Pro tier
- [ ] Discourse forum for embedded devs
- [ ] iStart Gujarat / Startup India application

---

## Contributing

PRs welcome. Especially:
- New vendor support (Microchip, Infineon, SiLabs)
- New GitHub repo sources
- Better search ranking
- VS Code extension

---

## Built by

Solo project by a fresh B.Tech grad from Gujarat, India 🇮🇳  
Built in one vibe-coding session — May 2026

---

## License

MIT — free to use, modify, and deploy.
