# Spending Agent

Telegram bot untuk mencatat pengeluaran ke Google Sheets menggunakan Gemini dan MCP.

> Contoh: `tadi isi bensin 69 ribu`

## V1: kelola transaksi

Setiap transaksi baru sekarang mendapatkan Transaction ID, misalnya
`260826-01`. Enam angka pertama adalah tanggal transaksi (`DDMMYY`),
sedangkan dua angka terakhir adalah urutan pengeluaran pada tanggal tersebut.
Simpan ID ini untuk operasi berikut.

- Tambah: `tadi makan siang 25 ribu`
- Lihat: `cek 260826-01`
- Cari: `cari pengeluaran food tanggal 05 Aug 2026`
- Terakhir: `cek 10 pengeluaran terakhir`
- Rekap: `total spending minggu ini`, `total spending bulan ini`, atau `total spending Februari 2026`
- Bandingkan: `bandingkan Februari vs Januari` atau `bandingkan Februari vs Januari 2026`
- Ubah: `ubah 260826-01 jadi 30 ribu`
- Hapus: `hapus 260826-01`

Secara default ID disimpan di kolom **A**, sementara kolom transaksi yang
sudah ada tetap digunakan: tanggal C, deskripsi D, kategori F, dan nominal G.
Jika sheet memakai kolom lain, atur `EXPENSE_ID_COLUMN` di `.env`.
Transaksi lama tanpa ID tetap dapat ditemukan lewat pencarian, tetapi perlu ID
untuk diubah atau dihapus.

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

Create `.env` from `.env.example`, then set `ALLOWED_TELEGRAM_USER_IDS` to
your numeric Telegram user ID. The bot will refuse to start without this
allowlist.

```bash
docker compose up -d --build
```

## Keamanan

- API keys, Spreadsheet ID, dan Telegram user ID disimpan di `.env`.
- Hanya Telegram user ID dalam `ALLOWED_TELEGRAM_USER_IDS` yang dapat memakai bot.
- Hapus transaksi membutuhkan dua pesan: `hapus 260826-01`, lalu
  `konfirmasi hapus 260826-01` dalam waktu lima menit.

## Scheduled financial report

Laporan otomatis dikirim hanya ke chat yang ada di `ALLOWED_TELEGRAM_USER_IDS`.
Secara default seluruh scheduler nonaktif. Konfigurasikan melalui `.env`:

```dotenv
REPORT_TIMEZONE=Asia/Jakarta
DAILY_REPORT_ENABLED=true
DAILY_REPORT_TIME=21:00
WEEKLY_REPORT_ENABLED=false
WEEKLY_REPORT_DAY=monday
WEEKLY_REPORT_TIME=09:00
MONTHLY_REPORT_ENABLED=false
MONTHLY_REPORT_DAY=1
MONTHLY_REPORT_TIME=09:00
```

Opsional, `REPORT_TELEGRAM_CHAT_IDS` dapat membatasi penerima lebih lanjut;
ID di luar allowlist akan diabaikan. State laporan disimpan di Docker volume
agar restart container tidak mengirim ulang laporan pada jadwal yang sama.

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
