# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules, collect_data_files


ROOT = Path.cwd()
SRC = ROOT / "src"
ASSETS = SRC / "assets"

datas = [
    (str(ASSETS / "icons"), "assets/icons"),
    (str(ASSETS / "providers"), "assets/providers"),
    (str(ASSETS / "prompt"), "assets/prompt"),
    (str(ASSETS / "Robin Haunschild"), "assets/Robin Haunschild"),
]

config_path = ASSETS / "config.json"
if config_path.exists():
    datas.append((str(config_path), "assets"))

datas += collect_data_files("metaknowledge")
datas += collect_data_files("plotly")

hiddenimports = (
    collect_submodules("metaknowledge")
    + collect_submodules("markdown")
    + collect_submodules("plotly")
    + collect_submodules("_plotly_utils")
    + collect_submodules("narwhals")
    + [
        "PyQt5.QtWebEngineWidgets",
        "PyQt5.QtWebChannel",
        "PyQt5.QtSvg",
        "fitz",
        "openai",
        "anthropic",
        "httpx",
        "pandas",
    ]
)

excludes = [
    "pydoc",
    "pdb",
    "tkinter",
    "IPython",
    "jupyter",
    "notebook",
    "sphinx",
    "torch",
    "torchvision",
    "torchaudio",
    "tensorflow",
    "tensorflow_intel",
    "keras",
    "transformers",
    "sklearn",
    "scikit_learn",
    "cv2",
    "opencv_python",
    "opencv_contrib_python",
    "scipy._lib.array_api_compat.torch",
    "scipy._lib.array_api_compat.torch._aliases",
    "scipy._lib.array_api_compat.torch.fft",
    "scipy._lib.array_api_compat.torch.linalg",
    "scipy._lib.array_api_compat.cupy",
    "scipy._lib.array_api_compat.dask",
    "cupy",
    "dask",
    "jax",
    "jaxlib",
    "numba",
    "fitz",
    "pdfplumber",
    "llvmlite",
    "polars",
    "_polars_runtime_32",
    "_polars_runtime_64",
    "_polars_runtime_compat",
    "altair",
    "pyarrow",
    "pyarrow_hotfix",
    "PyQt5.QtQml",
    "PyQt5.QtQuick",
    "PyQt5.QtBluetooth",
    "PyQt5.QtNfc",
    "PyQt5.QtPositioning",
    "PyQt5.QtSensors",
    "PyQt5.QtSerialPort",
    "PyQt5.QtSql",
    "PyQt5.QtTest",
]

a = Analysis(
    ["main.py"],
    pathex=[str(SRC)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=["pyi_runtime_stdio.py"],
    excludes=excludes,
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Beamplots",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(ASSETS / "icons" / "IES.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Beamplots",
)
