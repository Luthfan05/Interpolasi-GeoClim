# GeoClim

![Python Version](https://img.shields.io/badge/python-3.7%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-Active-success)

**GeoClim** is a high-level Python library designed to simplify the workflow of extracting, processing, and interpolating various global climate and geospatial grid datasets (e.g., rainfall data) into targeted station coordinates.

By combining Bilinear Interpolation with a robust Nearest Neighbor fallback, GeoClim handles boundary NaNs and complex geospatial data matrices seamlessly.

---

## 🚀 Supported Datasets

- **CHIRPS**: Automatic unpacking of `.tar.gz` and reading of `.bil` rasters via `rasterio`.
- **GPM IMERG**: Hierarchical `.HDF5` dataset parsing using `h5py`.
- **GSMaP**: Decodes raw binary float32 (`.dat.gz`) arrays along with valid pixel counts via `gzip` & `numpy`.
- **ERA5 Copernicus**: Merges multi-dimensional NetCDF (`*.nc`) files effortlessly with `xarray`.

---

## 🛠️ Installation

Clone this repository and install the library via pip:

```bash
git clone https://github.com/yourusername/geoclim.git
cd geoclim
pip install -e .
```

Alternatively, just install the dependencies using `requirements.txt`:
```bash
pip install -r requirements.txt
```

### Google Colab Installation
If you are working on Google Colab, you can install GeoClim directly from GitHub by creating a new code cell and running:

```python
!pip install git+https://github.com/Luthfan05/Interpolasi-GeoClim.git
```

---

## 📖 Quick Start (High-Level API)

You don't need to write hundreds of lines of complex looping or matrix logic. Prepare an Excel/CSV file containing your target coordinates (Latitude and Longitude columns), and run these powerful one-liners:

### 1. Processing ERA5 (`.nc`)
Automatically merges all monthly `.nc` files, interpolates, and converts to Millimeters.
```python
from geoclim import GeoClim
from logger import log_success

result = GeoClim.interpolate_era5_nc(
    coord_file='coordinates.xlsx',
    nc_folder='Data_ERA5',
    col_lat='Y', # Adjust to your excel latitude column
    col_lon='X'  # Adjust to your excel longitude column
)
GeoClim.save_to_csv(result, 'Output_ERA5.csv')
log_success("ERA5 data processed successfully!")
```

### 2. Processing GPM IMERG (`.HDF5`)
```python
from geoclim import GeoClim

result = GeoClim.interpolate_imerg_hdf5(
    coord_file='coordinates.xlsx',
    hdf5_folder='Data_IMERG'
)
GeoClim.save_to_csv(result, 'Output_IMERG.csv')
```

### 3. Processing GSMaP (`.dat.gz`)
Automatically calculates total monthly precipitation based on `rain_rate` x `valid_pixel_count` before interpolating.
```python
from geoclim import GeoClim

result = GeoClim.interpolate_gsmap_dat_gz(
    coord_file='coordinates.xlsx',
    dat_gz_folder='Data_GSMaP'
)
GeoClim.save_to_csv(result, 'Output_GSMaP.csv')
```

### 4. Processing CHIRPS (`.tar.gz`)
Unpacks the raster `.bil` data into a temporary folder, interpolates it, and automatically cleans up the temporary files afterwards to save storage.
```python
from geoclim import GeoClim

result = GeoClim.interpolate_chirps_tar_gz(
    coord_file='coordinates.xlsx',
    tar_gz_folder='Data_CHIRPS',
    extract_folder='Temp_Extract'
)
GeoClim.simpan_ke_csv(result, 'Output_CHIRPS.csv')
```

---

## 🤝 Contributing
Contributions are welcome! Please open an issue or submit a pull request if you want to add support for more satellite formats or improve the interpolation algorithms.

## 📝 License
This project is licensed under the MIT License.
