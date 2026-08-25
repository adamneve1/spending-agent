# Spending Agent

Telegram bot untuk mencatat pengeluaran ke Google Sheets menggunakan Gemini dan MCP.

> Contoh: `tadi isi bensin 69 ribu`

## V1: kelola transaksi

Setiap transaksi baru sekarang mendapatkan Transaction ID, misalnya
`EXP-20260805-A1B2C3D4`. Simpan ID tersebut untuk operasi berikut.

- Tambah: `tadi makan siang 25 ribu`
- Lihat: `cek EXP-20260805-A1B2C3D4`
- Cari: `cari pengeluaran food tanggal 05 Aug 2026`
- Ubah: `ubah EXP-20260805-A1B2C3D4 jadi 30 ribu`
- Hapus: `hapus EXP-20260805-A1B2C3D4`

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
