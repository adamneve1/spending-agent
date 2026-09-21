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
- Rekap rentang tanggal: `rekap pengeluaran 1 sampai 15 September 2026`
- Cek budget: `cek budget kategori bulan ini`
- Bandingkan: `bandingkan Februari vs Januari` atau `bandingkan Februari vs Januari 2026`
- Ubah: `ubah 260826-01 jadi 30 ribu`
- Hapus: `hapus 260826-01`
- Hapus beberapa sekaligus: `hapus 260826-01 260826-02 260826-03`

Secara default ID disimpan di kolom **A**, sementara kolom transaksi yang
sudah ada tetap digunakan: tanggal C, deskripsi D, kategori F, dan nominal G.
Jika sheet memakai kolom lain, atur `EXPENSE_*_COLUMN` di `.env`.
Transaksi lama tanpa ID tetap dapat ditemukan lewat pencarian, tetapi perlu ID
untuk diubah atau dihapus.

## Budget kategori

Budget dibaca langsung dari tabel **Expenses List / Allocation / Realization** di
tab `Report`. Bot memakai Allocation sebagai batas dan Realization sebagai
pemakaian. Atur `BUDGET_TABLE_RANGE` di `.env` jika tabel ada di luar
`Report!B11:G32`. Kategori tanpa Allocation tidak ditampilkan.

Rumus Realization memakai tahun di `Report!K2` dan nama bulan di `Report!K3`.
Bot membaca keduanya melalui `BUDGET_PERIOD_RANGE=Report!K2:K3` dan hanya
memberi peringatan jika periode Report sama dengan bulan transaksi berjalan.
Jika berbeda, bot menyatakan bahwa budget belum dicek.

Setelah transaksi bulan berjalan ditambah atau diubah, bot menampilkan
peringatan jika Realization kategori mencapai 80% Allocation atau melewati
batas. Peringatan mengikuti angka yang dihitung oleh sheet.

Untuk rekap tanggal bebas, kirim dua tanggal, misalnya
`rekap pengeluaran 1 sampai 15 September 2026`. Rentang mencakup kedua tanggal
dan dibatasi maksimal 367 hari.

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

Untuk clone atau pindah akun:

1. Salin `.env.example` ke `.env`. Isi token Telegram, API key Gemini, ID spreadsheet, dan Telegram user ID yang diizinkan.
2. Letakkan JSON service account di lokasi `GOOGLE_CREDENTIALS_FILE` pada host Docker. Bagikan spreadsheet tujuan ke email service account dengan akses editor.
3. Sesuaikan `WORKSHEET_NAME`, nomor kolom `EXPENSE_*_COLUMN`, dan `REPORT_DASHBOARD_RANGE` jika layout spreadsheet berbeda. Nomor kolom dimulai dari 1 dan tidak boleh sama; baris data pertama minimal 2.
4. Jalankan perintah di bawah. Untuk penggunaan Python langsung, `GOOGLE_CREDENTIALS_PATH` menentukan lokasi JSON relatif terhadap direktori project (atau path absolut). Di Docker, biarkan nilainya `credentials.json` karena file host dipasang ke `/app/credentials.json`.

Konfigurasi tiap instalasi tersimpan di `.env`; rahasia dan JSON kredensial tidak ikut Git. Jika mengganti akun Google, pastikan spreadsheet baru sudah dibagikan ke service account yang dipakai.

```bash
docker compose up -d --build
```

## Keamanan

- API keys, Spreadsheet ID, dan Telegram user ID disimpan di `.env`.
- Hanya Telegram user ID dalam `ALLOWED_TELEGRAM_USER_IDS` yang dapat memakai bot.
- Hapus transaksi membutuhkan dua pesan. Beberapa ID dapat dikirim sekaligus,
  misalnya `hapus 260826-01 260826-02`, lalu konfirmasikan perintah yang
  diberikan bot dalam waktu lima menit. Maksimal 20 transaksi per batch.

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
