import os
import tarfile
import gzip
import numpy as np
import pandas as pd
import xarray as xr
import h5py
import rasterio
import re

class GeoClim:
    """
    Library khusus untuk membaca dan memproses berbagai jenis 
    format file data iklim/spasial.
    """

    @staticmethod
    def baca_excel(filepath):
        """Membaca file .xlsx (misal: daftar koordinat stasiun)."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File excel tidak ditemukan: {filepath}")
        return pd.read_excel(filepath)

    @staticmethod
    def baca_csv(filepath):
        """Membaca file .csv biasa."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File CSV tidak ditemukan: {filepath}")
        return pd.read_csv(filepath)

    @staticmethod
    def baca_raster_bil(filepath):
        """
        Membaca format raster .bil (contoh: CHIRPS).
        Mengembalikan array longitude, latitude, dan matrix data raster.
        """
        with rasterio.open(filepath) as dataset:
            data = dataset.read(1)
            # Menangani NoData (biasanya -9999, diset ke NaN agar aman dihitung)
            if dataset.nodata is not None:
                data = np.where(data == dataset.nodata, np.nan, data)
                
            transform = dataset.transform
            nrows, ncols = dataset.height, dataset.width

            lons = np.array([transform[2] + i * transform[0] for i in range(ncols)])
            lats = np.array([transform[5] + j * transform[4] for j in range(nrows)])

            return lons, lats, data

    @staticmethod
    def ekstrak_tar_gz(tar_path, extract_folder, ekstensi_target=None):
        """
        Mengekstrak file .tar.gz, dengan opsi filter ekstensi tertentu.
        Mengembalikan daftar nama file yang berhasil diekstrak.
        """
        extracted_files = []
        with tarfile.open(tar_path, "r:gz") as tar:
            for member in tar.getmembers():
                if ekstensi_target is None or any(member.name.endswith(ext) for ext in ekstensi_target):
                    member.name = os.path.basename(member.name) # Bersihkan path
                    tar.extract(member, path=extract_folder)
                    extracted_files.append(os.path.join(extract_folder, member.name))
        return extracted_files

    @staticmethod
    def baca_hdf5_imerg(filepath):
        """
        Membaca data format .HDF5 khusus untuk struktur GPM IMERG.
        Mengembalikan array longitude, latitude, dan matrix presipitasi.
        """
        with h5py.File(filepath, 'r') as f:
            precip = f["Grid"]["precipitation"][0, :, :]
            lat = f["Grid"]["lat"][:]
            lon = f["Grid"]["lon"][:]
        return lon, lat, precip

    @staticmethod
    def baca_binary_gz_gsmap(filepath):
        """
        Membaca data binary float32 (.dat.gz) khusus struktur data GSMaP.
        Mengembalikan matrix data rain_rate dan valid_pixel_count.
        """
        with gzip.open(filepath, "rb") as f:
            data = np.frombuffer(f.read(), dtype='<f4')
        
        # Struktur dimensi GSMaP (1200 lat x 3600 lon = 4320000 pixel)
        rain_rate = data[:4320000].copy()
        valid_pixel_count = data[4320000:] if len(data) > 4320000 else None
        
        # Missing values (NaN)
        rain_rate[rain_rate == -999.9] = np.nan
        
        lat = np.linspace(59.95, -59.95, 1200)
        lon = np.linspace(-179.95, 179.95, 3600)
        
        return lon, lat, rain_rate, valid_pixel_count

    @staticmethod
    def baca_netcdf_era5(file_pattern):
        """
        Membaca satu atau banyak file NetCDF (.nc) sekaligus menggunakan xarray.
        Contoh input pattern: 'path/to/folder/*.nc'
        """
        ds = xr.open_mfdataset(file_pattern, combine="by_coords")
        return ds

    @staticmethod
    def simpan_ke_csv(df, output_path):
        """Utility function untuk menyimpan DataFrame ke CSV."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df.to_csv(output_path, index=False)

    @staticmethod
    def interpolasi_titik(lons, lats, grid_data, titik_target, fallback_nearest=True):
        """
        Mengekstrak data dari grid spasial ke titik-titik tertentu menggunakan interpolasi Bilinear.
        Jika ada titik yang menghasilkan NaN (misal di tepi batas), otomatis menggunakan nearest neighbor fallback.

        Parameter:
        - lons: Array 1D dari Longitude (urutan harus menaik atau menurun secara berurutan)
        - lats: Array 1D dari Latitude (urutan harus menaik atau menurun secara berurutan)
        - grid_data: Array 2D data (misalnya curah hujan) dengan shape (len(lats), len(lons))
        - titik_target: Array 2D numpy dengan shape (N, 2), berisi [[lat1, lon1], [lat2, lon2], ...]
        - fallback_nearest: Boolean, jika True akan mencari nilai terdekat untuk piksel yang NaN.
        
        Mengembalikan:
        - Array 1D berisi nilai hasil interpolasi untuk setiap titik.
        """
        from scipy.interpolate import RegularGridInterpolator
        from scipy.spatial.distance import cdist

        # RegularGridInterpolator membutuhkan sumbu yang urut naik (strictly ascending). 
        # Jika lats atau lons menurun (descending), kita balik array-nya.
        if lats[0] > lats[-1]:
            lats = lats[::-1]
            grid_data = grid_data[::-1, :]
        if lons[0] > lons[-1]:
            lons = lons[::-1]
            grid_data = grid_data[:, ::-1]

        # Inisialisasi Bilinear Interpolator
        interpolator = RegularGridInterpolator((lats, lons), grid_data, bounds_error=False, fill_value=np.nan)
        
        # Eksekusi interpolasi. Hati-hati titik_target harus berformat (lat, lon)
        interpolated = interpolator(titik_target)

        # Fallback ke Nearest Neighbor jika ada nilai yang masih NaN setelah interpolasi
        if fallback_nearest and np.isnan(interpolated).any():
            nan_mask = np.isnan(interpolated)
            valid_mask = ~np.isnan(grid_data)
            
            # Membentuk titik grid dari mask yang valid
            lat_grid, lon_grid = np.meshgrid(lats, lons, indexing='ij')
            valid_points = np.array([lat_grid[valid_mask], lon_grid[valid_mask]]).T
            valid_values = grid_data[valid_mask]

            if len(valid_points) > 0:
                # Menggunakan cdist untuk mencari titik valid dengan jarak terdekat (Nearest Neighbor)
                nearest_idx = np.argmin(cdist(titik_target[nan_mask], valid_points), axis=1)
                interpolated[nan_mask] = valid_values[nearest_idx]

        return interpolated

    @staticmethod
    def ekstrak_tanggal_fleksibel(nama_file):
        """
        Mengekstrak tanggal dari sebuah string/nama file dengan pola seperti:
        YYYYMM, YYYY.MM, YYYY-MM, YYYY_MM.
        Cocok digunakan pada dataset tipe CHIRPS.
        """
        match = re.search(r"\d{4}[\._-]?\d{2}", nama_file)
        if match:
            return match.group(0).replace("_", "-").replace(".", "-")
        return "unknown"

    @staticmethod
    def filter_batas_koordinat(df, col_lat="lat", col_lon="lon", lat_min=-12.0, lat_max=6.0, lon_min=95.0, lon_max=141.0):
        """
        Melakukan filter batas wilayah/koordinat spasial (Bounding Box) pada DataFrame.
        Berguna untuk memotong data spasial global (seperti GSMaP atau CHIRPS asli) 
        hanya untuk cakupan wilayah Indonesia.
        """
        return df[
            (df[col_lat] >= lat_min) & (df[col_lat] <= lat_max) &
            (df[col_lon] >= lon_min) & (df[col_lon] <= lon_max)
        ].copy()

    @staticmethod
    def format_grid_2d_ke_dataframe(lons, lats, data_array, nama_kolom="ch"):
        """
        Mengubah array Lons (1D), Lats (1D), dan Data Grid (2D) menjadi format tabular (DataFrame Pandas)
        dengan kolom: lat, lon, dan nilai. Biasanya dipakai untuk mengekspor ke file CSV.
        """
        lon_grid, lat_grid = np.meshgrid(lons, lats)
        df = pd.DataFrame({
            "lon": lon_grid.flatten(),
            "lat": lat_grid.flatten(),
            nama_kolom: data_array.flatten()
        })
        return df

    @staticmethod
    def pivot_dataframe_ke_grid_2d(df, col_lat="lat", col_lon="lon", col_nilai="ch"):
        """
        Membentuk kembali DataFrame yang berbentuk tabular ke format Grid 2D Array
        dan mengembalikan Lons 1D, Lats 1D, serta Data Matrix 2D-nya.
        Sangat krusial untuk persiapan sebelum melakukan `interpolasi_titik`.
        """
        # Hati-hati dengan urutan
        lats_unik = np.sort(df[col_lat].unique())
        lons_unik = np.sort(df[col_lon].unique())
        
        # Buat pivot
        grid_data = df.pivot(index=col_lat, columns=col_lon, values=col_nilai).values
        
        return lons_unik, lats_unik, grid_data

    @staticmethod
    def interpolasi_era5_nc(file_koordinat, folder_nc, col_lat="Y", col_lon="X"):
        """
        Fungsi Otomatis (High-Level) untuk melakukan interpolasi bilinear data ERA5 (.nc)
        secara langsung dari file koordinat mentah dan folder kumpulan file .nc.
        
        Parameter:
        - file_koordinat: Path menuju file .xlsx atau .csv berisi koordinat stasiun target.
        - folder_nc: Path menuju folder tempat file-file .nc ERA5 tersimpan.
        - col_lat: Nama kolom latitude di file koordinat.
        - col_lon: Nama kolom longitude di file koordinat.
        
        Mengembalikan:
        - DataFrame Pandas lengkap berisi hasil interpolasi bulanan seluruh stasiun.
        """
        from glob import glob
        
        # 1. Baca Otomatis File Titik (Excel atau CSV)
        if file_koordinat.endswith('.xlsx'):
            df_titik = GeoClim.baca_excel(file_koordinat)
        else:
            df_titik = GeoClim.baca_csv(file_koordinat)
            
        lats_target = df_titik[col_lat].values
        lons_target = df_titik[col_lon].values
        titik_target = np.array([lats_target, lons_target]).T

        # 2. Baca seluruh data NC di folder
        file_pattern = os.path.join(folder_nc, "*.nc")
        dataset_era5 = GeoClim.baca_netcdf_era5(file_pattern)

        tp = dataset_era5["tp"]
        lats = dataset_era5["latitude"].values
        lons = dataset_era5["longitude"].values

        # 3. Proses Group Bulanan sesuai algoritma aslinya
        times = pd.to_datetime(dataset_era5["valid_time"].values)
        tp = tp.assign_coords(valid_time=times)
        tp.coords["year"] = ("valid_time", tp["valid_time"].dt.year.data)
        tp.coords["month"] = ("valid_time", tp["valid_time"].dt.month.data)

        tp_bulanan = tp.groupby(["year", "month"]).sum(dim="valid_time")
        
        results = []
        
        # 4. Looping untuk interpolasi setiap bulannya
        for i in range(tp_bulanan["year"].size):
            for j in range(tp_bulanan["month"].size):
                try:
                    tp_sel = tp_bulanan.isel(year=i, month=j)
                    year_val = int(tp_sel["year"].values)
                    month_val = int(tp_sel["month"].values)
                    tp_vals = tp_sel.values

                    # Otomatis panggil helper Bilinear
                    hasil_interpolasi = GeoClim.interpolasi_titik(lons, lats, tp_vals, titik_target)

                    # Bentuk output
                    df_out = df_titik.copy()
                    df_out["tp_interpolated_mm"] = hasil_interpolasi * 1000 # Meter ke mm
                    df_out["tahun"] = year_val
                    df_out["bulan"] = month_val
                    
                    results.append(df_out)
                except Exception:
                    continue

        df_final = pd.concat(results, ignore_index=True)
        return df_final

    # =========================================================================
    # FUNGSI HIGH-LEVEL LAINNYA UNTUK SEKALI JALAN
    # =========================================================================

    @staticmethod
    def _baca_titik_target(file_koordinat, col_lat, col_lon):
        """Helper internal untuk membaca koordinat target menjadi bentuk array."""
        if file_koordinat.endswith('.xlsx'):
            df_titik = GeoClim.baca_excel(file_koordinat)
        else:
            df_titik = GeoClim.baca_csv(file_koordinat)
        lats = df_titik[col_lat].values
        lons = df_titik[col_lon].values
        return df_titik, np.array([lats, lons]).T

    @staticmethod
    def interpolasi_chirps_tar_gz(file_koordinat, folder_tar_gz, extract_folder, col_lat="Y", col_lon="X"):
        """Fungsi High-Level otomatis proses CHIRPS dari tar.gz mentah ke hasil interpolasi csv."""
        from glob import glob
        import shutil
        
        df_titik, titik_target = GeoClim._baca_titik_target(file_koordinat, col_lat, col_lon)
        os.makedirs(extract_folder, exist_ok=True)
        
        tar_files = glob(os.path.join(folder_tar_gz, "*.tar.gz"))
        results = []
        
        for tar_path in tar_files:
            try:
                # 1. Ekstrak
                files_extracted = GeoClim.ekstrak_tar_gz(tar_path, extract_folder, [".bil", ".hdr"])
                
                # 2. Proses tiap .bil
                for file_bil in files_extracted:
                    if not file_bil.endswith(".bil"):
                        continue
                    
                    lons, lats, data_raster = GeoClim.baca_raster_bil(file_bil)
                    
                    # 3. Interpolasi
                    hasil_interpolasi = GeoClim.interpolasi_titik(lons, lats, data_raster, titik_target)
                    
                    # Ekstrak waktu dan gabung output
                    tgl_str = GeoClim.ekstrak_tanggal_fleksibel(os.path.basename(file_bil))
                    
                    df_out = df_titik.copy()
                    df_out["ch_interpolated"] = hasil_interpolasi
                    df_out["tanggal"] = tgl_str
                    results.append(df_out)
                    
                    # Bersihkan file ekstrak sementara
                    os.remove(file_bil)
                    hdr_path = file_bil.replace(".bil", ".hdr")
                    if os.path.exists(hdr_path):
                        os.remove(hdr_path)
            except Exception:
                continue
                
        if len(results) > 0:
            return pd.concat(results, ignore_index=True)
        return pd.DataFrame()

    @staticmethod
    def interpolasi_imerg_hdf5(file_koordinat, folder_hdf5, col_lat="Y", col_lon="X"):
        """Fungsi High-Level otomatis proses kumpulan file IMERG .HDF5 ke hasil interpolasi."""
        from glob import glob
        from datetime import datetime
        
        df_titik, titik_target = GeoClim._baca_titik_target(file_koordinat, col_lat, col_lon)
        hdf5_files = glob(os.path.join(folder_hdf5, "**", "*.HDF5"), recursive=True)
        
        results = []
        for file_path in hdf5_files:
            try:
                lons, lats, precip = GeoClim.baca_hdf5_imerg(file_path)
                hasil_interpolasi = GeoClim.interpolasi_titik(lons, lats, precip, titik_target)
                
                # Ekstrak tanggal dari nama file
                filename = os.path.basename(file_path)
                try:
                    date_str = filename.split('.')[4].split('-')[0]
                    date_val = pd.to_datetime(date_str, format="%Y%m%d")
                except Exception:
                    date_val = None
                    
                df_out = df_titik.copy()
                df_out["precip_interpolated"] = hasil_interpolasi
                df_out["tanggal"] = date_val
                results.append(df_out)
            except Exception:
                continue
                
        if len(results) > 0:
            return pd.concat(results, ignore_index=True)
        return pd.DataFrame()

    @staticmethod
    def interpolasi_gsmap_dat_gz(file_koordinat, folder_dat_gz, col_lat="Y", col_lon="X"):
        """Fungsi High-Level otomatis proses file GSMaP binary gz ke hasil interpolasi."""
        from glob import glob
        
        df_titik, titik_target = GeoClim._baca_titik_target(file_koordinat, col_lat, col_lon)
        gz_files = glob(os.path.join(folder_dat_gz, "**", "*.dat.gz"), recursive=True)
        
        results = []
        for file_path in gz_files:
            try:
                lons, lats, rain_rate, valid_pixel = GeoClim.baca_binary_gz_gsmap(file_path)
                
                # Kalkulasi total hujan bulanan
                total_rain = rain_rate * valid_pixel
                
                # Ekstrak tahun bulan dari nama file (misal: gsmap_gauge.201403.0.1d.daily.00Z-23Z...)
                basename = os.path.basename(file_path)
                yyyymm = basename.split('.')[1] 
                date_val = pd.to_datetime(yyyymm, format="%Y%m")
                
                hasil_interpolasi = GeoClim.interpolasi_titik(lons, lats, total_rain, titik_target)
                
                df_out = df_titik.copy()
                df_out["rain_interpolated"] = hasil_interpolasi
                df_out["tanggal"] = date_val
                results.append(df_out)
            except Exception:
                continue
                
        if len(results) > 0:
            return pd.concat(results, ignore_index=True)
        return pd.DataFrame()

