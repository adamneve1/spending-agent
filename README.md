# Spending Agent

Telegram bot untuk mencatat pengeluaran ke Google Sheets menggunakan Gemini dan MCP.

> Contoh: `tadi isi bensin 69 ribu`

## Stack

Python · Telegram · Gemini · MCP · Google Sheets · Docker · GitHub Actions · Linux VM

## Architecture

```text
Telegram
   ↓
Gemini
   ↓
MCP
   ↓
Google Sheets
```

## Run

```bash
docker compose up -d --build
```

## CI/CD

```text
git push
   ↓
Test
   ↓
Docker Build
   ↓
Deploy ke VM
```
