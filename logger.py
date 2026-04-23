import sys
from datetime import datetime

def _dapatkan_waktu():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log_info(pesan):
    """Menampilkan pesan informasi biasa."""
    print(f"[{_dapatkan_waktu()}] [INFO] {pesan}")

def log_sukses(pesan):
    """Menampilkan pesan ketika suatu proses berhasil diselesaikan."""
    print(f"[{_dapatkan_waktu()}] [SUKSES] {pesan}")

def log_peringatan(pesan):
    """Menampilkan pesan peringatan."""
    print(f"[{_dapatkan_waktu()}] [PERINGATAN] {pesan}")

def log_error(tujuan_proses, pesan_error):
    """
    Menampilkan pesan error dengan bahasa yang jelas dan mudah dipahami,
    tanpa emoji, agar maksud dan tujuannya tersampaikan dengan baik.
    
    Parameter:
    - tujuan_proses: Deskripsi proses apa yang sedang dijalankan sebelum gagal.
    - pesan_error: Objek error asli dari Python atau pesan khusus.
    """
    pesan = (
        f"\n[{_dapatkan_waktu()}] [GAGAL]\n"
        f"Tujuan Proses : {tujuan_proses}\n"
        f"Detail Masalah: {str(pesan_error)}\n"
        f"Saran         : Mohon periksa kembali input data, struktur file, atau izin akses.\n"
        f"{'-'*50}"
    )
    print(pesan, file=sys.stderr)
