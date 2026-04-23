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
    A specialized library for reading, processing, and interpolating 
    various spatial and climate data file formats.
    """

    @staticmethod
    def read_excel(filepath):
        """Reads .xlsx files (e.g., target station coordinates)."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Excel file not found: {filepath}")
        return pd.read_excel(filepath)

    @staticmethod
    def read_csv(filepath):
        """Reads standard .csv files."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"CSV file not found: {filepath}")
        return pd.read_csv(filepath)

    @staticmethod
    def read_raster_bil(filepath):
        """
        Reads .bil raster format (e.g., CHIRPS).
        Returns arrays of longitudes, latitudes, and the raster data matrix.
        """
        with rasterio.open(filepath) as dataset:
            data = dataset.read(1)
            # Handle NoData (usually -9999, set to NaN for safe computation)
            if dataset.nodata is not None:
                data = np.where(data == dataset.nodata, np.nan, data)
                
            transform = dataset.transform
            nrows, ncols = dataset.height, dataset.width

            lons = np.array([transform[2] + i * transform[0] for i in range(ncols)])
            lats = np.array([transform[5] + j * transform[4] for j in range(nrows)])

            return lons, lats, data

    @staticmethod
    def extract_tar_gz(tar_path, extract_folder, target_extensions=None):
        """
        Extracts .tar.gz files, with an option to filter by specific extensions.
        Returns a list of extracted file paths.
        """
        extracted_files = []
        with tarfile.open(tar_path, "r:gz") as tar:
            for member in tar.getmembers():
                if target_extensions is None or any(member.name.endswith(ext) for ext in target_extensions):
                    member.name = os.path.basename(member.name) # Clean path
                    tar.extract(member, path=extract_folder)
                    extracted_files.append(os.path.join(extract_folder, member.name))
        return extracted_files

    @staticmethod
    def read_hdf5_imerg(filepath):
        """
        Reads .HDF5 format specifically structured for GPM IMERG data.
        Returns arrays of longitudes, latitudes, and the precipitation matrix.
        """
        with h5py.File(filepath, 'r') as f:
            precip = f["Grid"]["precipitation"][0, :, :]
            lats = f["Grid"]["lat"][:]
            lons = f["Grid"]["lon"][:]
        return lons, lats, precip

    @staticmethod
    def read_binary_gz_gsmap(filepath):
        """
        Reads binary float32 (.dat.gz) structured for GSMaP data.
        Returns matrices for rain_rate and valid_pixel_count.
        """
        with gzip.open(filepath, "rb") as f:
            data = np.frombuffer(f.read(), dtype='<f4')
        
        # GSMaP dimension structure (1200 lat x 3600 lon = 4320000 pixels)
        rain_rate = data[:4320000].copy()
        valid_pixel_count = data[4320000:] if len(data) > 4320000 else None
        
        # Missing values (NaN)
        rain_rate[rain_rate == -999.9] = np.nan
        
        lats = np.linspace(59.95, -59.95, 1200)
        lons = np.linspace(-179.95, 179.95, 3600)
        
        return lons, lats, rain_rate, valid_pixel_count

    @staticmethod
    def read_netcdf_era5(file_pattern):
        """
        Reads one or multiple NetCDF (.nc) files using xarray.
        Example pattern: 'path/to/folder/*.nc'
        """
        ds = xr.open_mfdataset(file_pattern, combine="by_coords")
        return ds

    @staticmethod
    def save_to_csv(df, output_path):
        """Utility function to save DataFrame to CSV."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        df.to_csv(output_path, index=False)

    @staticmethod
    def interpolate_points(lons, lats, grid_data, target_points, fallback_nearest=True):
        """
        Extracts data from a spatial grid to specific target points using Bilinear Interpolation.
        If any point yields NaN (e.g., at boundaries), automatically falls back to nearest neighbor.

        Parameters:
        - lons: 1D array of Longitudes (must be strictly ascending or descending)
        - lats: 1D array of Latitudes (must be strictly ascending or descending)
        - grid_data: 2D data array (e.g., rainfall) with shape (len(lats), len(lons))
        - target_points: 2D numpy array with shape (N, 2), containing [[lat1, lon1], [lat2, lon2], ...]
        - fallback_nearest: Boolean, if True finds the nearest valid value for NaN pixels.
        
        Returns:
        - 1D array of interpolated values for each target point.
        """
        from scipy.interpolate import RegularGridInterpolator
        from scipy.spatial.distance import cdist

        # RegularGridInterpolator requires strictly ascending axes.
        if lats[0] > lats[-1]:
            lats = lats[::-1]
            grid_data = grid_data[::-1, :]
        if lons[0] > lons[-1]:
            lons = lons[::-1]
            grid_data = grid_data[:, ::-1]

        # Initialize Bilinear Interpolator
        interpolator = RegularGridInterpolator((lats, lons), grid_data, bounds_error=False, fill_value=np.nan)
        
        # Execute interpolation. Target points must be formatted as (lat, lon)
        interpolated = interpolator(target_points)

        # Fallback to Nearest Neighbor if there are NaNs after interpolation
        if fallback_nearest and np.isnan(interpolated).any():
            nan_mask = np.isnan(interpolated)
            valid_mask = ~np.isnan(grid_data)
            
            # Form grid points from valid mask
            lat_grid, lon_grid = np.meshgrid(lats, lons, indexing='ij')
            valid_points = np.array([lat_grid[valid_mask], lon_grid[valid_mask]]).T
            valid_values = grid_data[valid_mask]

            if len(valid_points) > 0:
                nearest_idx = np.argmin(cdist(target_points[nan_mask], valid_points), axis=1)
                interpolated[nan_mask] = valid_values[nearest_idx]

        return interpolated

    @staticmethod
    def extract_flexible_date(filename):
        """
        Extracts a date from a filename string using patterns like:
        YYYYMM, YYYY.MM, YYYY-MM, YYYY_MM.
        Suitable for CHIRPS dataset.
        """
        match = re.search(r"\d{4}[\._-]?\d{2}", filename)
        if match:
            return match.group(0).replace("_", "-").replace(".", "-")
        return "unknown"

    @staticmethod
    def filter_bounding_box(df, col_lat="lat", col_lon="lon", lat_min=-12.0, lat_max=6.0, lon_min=95.0, lon_max=141.0):
        """
        Filters spatial coordinates based on a Bounding Box.
        Useful for clipping global spatial data (e.g., GSMaP or CHIRPS) to specific regions.
        """
        return df[
            (df[col_lat] >= lat_min) & (df[col_lat] <= lat_max) &
            (df[col_lon] >= lon_min) & (df[col_lon] <= lon_max)
        ].copy()

    @staticmethod
    def format_grid_2d_to_dataframe(lons, lats, data_array, col_name="ch"):
        """
        Converts 1D Lons, 1D Lats, and 2D Data Grid into a tabular DataFrame format
        with columns: lat, lon, and value. Typically used before exporting to CSV.
        """
        lon_grid, lat_grid = np.meshgrid(lons, lats)
        df = pd.DataFrame({
            "lon": lon_grid.flatten(),
            "lat": lat_grid.flatten(),
            col_name: data_array.flatten()
        })
        return df

    @staticmethod
    def pivot_dataframe_to_grid_2d(df, col_lat="lat", col_lon="lon", col_value="ch"):
        """
        Reconstructs a tabular DataFrame back into a 2D Grid Array.
        Returns 1D Lons, 1D Lats, and 2D Data Matrix.
        Crucial preparation step before running `interpolate_points`.
        """
        unique_lats = np.sort(df[col_lat].unique())
        unique_lons = np.sort(df[col_lon].unique())
        
        grid_data = df.pivot(index=col_lat, columns=col_lon, values=col_value).values
        
        return unique_lons, unique_lats, grid_data

    # =========================================================================
    # HIGH-LEVEL AUTOMATED PIPELINE FUNCTIONS
    # =========================================================================

    @staticmethod
    def _read_target_points(coord_file, col_lat, col_lon):
        """Internal helper to read target coordinates into an array."""
        if coord_file.endswith('.xlsx'):
            df_points = GeoClim.read_excel(coord_file)
        else:
            df_points = GeoClim.read_csv(coord_file)
        lats = df_points[col_lat].values
        lons = df_points[col_lon].values
        return df_points, np.array([lats, lons]).T

    @staticmethod
    def interpolate_era5_nc(coord_file, nc_folder, col_lat="Y", col_lon="X", var_names="tp", agg_method="sum", multiplier=1):
        """
        Automated pipeline for bilinear interpolation of ERA5 (.nc) data
        directly from raw coordinate files and a folder of .nc files.
        Allows specifying multiple target variables (var_names as string or list),
        an aggregation method ('sum' or 'mean'), and an optional multiplier.
        """
        import os
        from glob import glob
        
        df_points, target_points = GeoClim._read_target_points(coord_file, col_lat, col_lon)

        file_pattern = os.path.join(nc_folder, "*.nc")
        dataset_era5 = GeoClim.read_netcdf_era5(file_pattern)

        # Convert to list if it's a single string
        if isinstance(var_names, str):
            var_names = [var_names]

        missing_vars = [v for v in var_names if v not in dataset_era5.data_vars]
        if missing_vars:
            raise KeyError(f"Variables {missing_vars} not found. Available: {list(dataset_era5.data_vars.keys())}")
        
        # Check coordinate names
        lat_col = "latitude" if "latitude" in dataset_era5.coords else "lat"
        lon_col = "longitude" if "longitude" in dataset_era5.coords else "lon"
        time_col = "valid_time" if "valid_time" in dataset_era5.coords else "time"
        
        lats = dataset_era5[lat_col].values
        lons = dataset_era5[lon_col].values

        times = pd.to_datetime(dataset_era5[time_col].values)
        dataset_era5 = dataset_era5.assign_coords({time_col: times})
        dataset_era5.coords["year"] = (time_col, dataset_era5[time_col].dt.year.data)
        dataset_era5.coords["month"] = (time_col, dataset_era5[time_col].dt.month.data)

        # Apply aggregation
        dataset_subset = dataset_era5[var_names]
        if agg_method.lower() == "sum":
            data_monthly = dataset_subset.groupby(["year", "month"]).sum(dim=time_col)
        else:
            data_monthly = dataset_subset.groupby(["year", "month"]).mean(dim=time_col)
        
        results = []
        for i in range(data_monthly["year"].size):
            for j in range(data_monthly["month"].size):
                try:
                    data_sel = data_monthly.isel(year=i, month=j)
                    year_val = int(data_sel["year"].values)
                    month_val = int(data_sel["month"].values)

                    df_out = df_points.copy()
                    df_out["year"] = year_val
                    df_out["month"] = month_val

                    # Interpolate each variable
                    for v_name in var_names:
                        data_vals = data_sel[v_name].values
                        interpolated_vals = GeoClim.interpolate_points(lons, lats, data_vals, target_points)
                        df_out[f"{v_name}_interpolated"] = interpolated_vals * multiplier 
                    
                    results.append(df_out)
                except Exception:
                    continue

        if results:
            return pd.concat(results, ignore_index=True)
        return pd.DataFrame()

    @staticmethod
    def interpolate_chirps_tar_gz(coord_file, tar_gz_folder, extract_folder, col_lat="Y", col_lon="X"):
        """Automated pipeline to process CHIRPS from raw tar.gz to interpolated CSV results."""
        from glob import glob
        import shutil
        
        df_points, target_points = GeoClim._read_target_points(coord_file, col_lat, col_lon)
        os.makedirs(extract_folder, exist_ok=True)
        
        tar_files = glob(os.path.join(tar_gz_folder, "*.tar.gz"))
        results = []
        
        for tar_path in tar_files:
            try:
                files_extracted = GeoClim.extract_tar_gz(tar_path, extract_folder, [".bil", ".hdr"])
                
                for file_bil in files_extracted:
                    if not file_bil.endswith(".bil"):
                        continue
                    
                    lons, lats, data_raster = GeoClim.read_raster_bil(file_bil)
                    interpolated_vals = GeoClim.interpolate_points(lons, lats, data_raster, target_points)
                    
                    date_str = GeoClim.extract_flexible_date(os.path.basename(file_bil))
                    
                    df_out = df_points.copy()
                    df_out["ch_interpolated"] = interpolated_vals
                    df_out["date"] = date_str
                    results.append(df_out)
                    
                    os.remove(file_bil)
                    hdr_path = file_bil.replace(".bil", ".hdr")
                    if os.path.exists(hdr_path):
                        os.remove(hdr_path)
            except Exception:
                continue
                
        if results:
            return pd.concat(results, ignore_index=True)
        return pd.DataFrame()

    @staticmethod
    def interpolate_imerg_hdf5(coord_file, hdf5_folder, col_lat="Y", col_lon="X"):
        """Automated pipeline to process IMERG .HDF5 files to interpolated results."""
        from glob import glob
        
        df_points, target_points = GeoClim._read_target_points(coord_file, col_lat, col_lon)
        hdf5_files = glob(os.path.join(hdf5_folder, "**", "*.HDF5"), recursive=True)
        
        results = []
        for file_path in hdf5_files:
            try:
                lons, lats, precip = GeoClim.read_hdf5_imerg(file_path)
                interpolated_vals = GeoClim.interpolate_points(lons, lats, precip, target_points)
                
                filename = os.path.basename(file_path)
                try:
                    date_str = filename.split('.')[4].split('-')[0]
                    date_val = pd.to_datetime(date_str, format="%Y%m%d")
                except Exception:
                    date_val = None
                    
                df_out = df_points.copy()
                df_out["precip_interpolated"] = interpolated_vals
                df_out["date"] = date_val
                results.append(df_out)
            except Exception:
                continue
                
        if results:
            return pd.concat(results, ignore_index=True)
        return pd.DataFrame()

    @staticmethod
    def interpolate_gsmap_dat_gz(coord_file, dat_gz_folder, col_lat="Y", col_lon="X"):
        """Automated pipeline to process GSMaP binary gz files to interpolated results."""
        from glob import glob
        
        df_points, target_points = GeoClim._read_target_points(coord_file, col_lat, col_lon)
        gz_files = glob(os.path.join(dat_gz_folder, "**", "*.dat.gz"), recursive=True)
        
        results = []
        for file_path in gz_files:
            try:
                lons, lats, rain_rate, valid_pixel = GeoClim.read_binary_gz_gsmap(file_path)
                
                total_rain = rain_rate * valid_pixel
                
                basename = os.path.basename(file_path)
                yyyymm = basename.split('.')[1] 
                date_val = pd.to_datetime(yyyymm, format="%Y%m")
                
                interpolated_vals = GeoClim.interpolate_points(lons, lats, total_rain, target_points)
                
                df_out = df_points.copy()
                df_out["rain_interpolated"] = interpolated_vals
                df_out["date"] = date_val
                results.append(df_out)
            except Exception:
                continue
                
        if results:
            return pd.concat(results, ignore_index=True)
        return pd.DataFrame()
