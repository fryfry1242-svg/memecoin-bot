# Memecoin bot: project rules

These rules always apply in this repo.

## Hard rules

- **Paper money only.** Every trade is pretend. Never add code that sends real transactions, connects a wallet, or spends real funds.
- **No wallet keys.** Never read, ask for, store, or log private keys, seed phrases, or wallet files.
- **No secrets in the repo.** This repo is public. Never put API keys, passwords, or other secrets in any file here. `.env` is git-ignored and must stay that way.
- **Never push without approval.** Do not run `git push` until North says to push in that moment. Approval for one push does not cover later pushes. Committing is fine when asked; show what will be pushed first.

## How to work with North

- North is a beginner coder. Explain every step in plain language, as if they have never coded.
- Explain the plan before editing files.
- Give exact commands to copy and paste, and say what each one does and what they should see.

## Project notes

- Run Python with `venv/bin/python` (the system `python3` has no `requests`).
- The rug filter rules live only in `rules.py`. `scanner.py`, `rug_filter.py` and `ticket_bot.py` import them, and the scanner saves a plain-language copy into `data.json` for the dashboard's Rules tab.
- A GitHub Action commits new `data.json` and `history.json` every 15 minutes, so run `git pull` before making changes and before pushing.
- To test the scanner locally without touching the real `data.json`, run it from a scratch folder.
- `orders/`, `paper_trades.log`, `positions.json` and `seen_tokens.json` are private paper-trading files and are git-ignored.
