from setuptools import setup, find_packages
import os

# Baca deskripsi dari README untuk halaman GitHub/PyPI
with open("readme.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="geoclim",
    version="1.0.0",
    author="Peneliti / Engineer",
    author_email="email@domain.com",
    description="A powerful Python library for spatial and climate data extraction and interpolation.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/username/geoclim", # Ganti dengan URL repo GitHub Anda nanti
    packages=find_packages(),
    py_modules=["geoclim", "logger"],
    install_requires=[
        "numpy",
        "pandas",
        "xarray",
        "rasterio",
        "h5py",
        "scipy",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: GIS",
        "Topic :: Scientific/Engineering :: Atmospheric Science",
    ],
    python_requires=">=3.7",
)
