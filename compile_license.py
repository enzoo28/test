"""
compile_license.py — Compile license_manager.py to .pyd for tamper resistance.

Requires Cython and a C compiler (Visual Studio Build Tools).

Usage:
  pip install cython
  python compile_license.py build_ext --inplace

The resulting license_manager.cp*-win_amd64.pyd replaces license_manager.py.
Delete the .py file after verifying the .pyd works.
"""

try:
    from Cython.Build import cythonize
    from setuptools import setup, Extension
except ImportError:
    print("Missing Cython. Run: pip install cython")
    print("Also need Visual Studio Build Tools or MSVC compiler.")
    sys.exit(1)

import sys

ext = Extension(
    "license_manager",
    ["license_manager.py"],
    py_limited_api=True,
)

setup(
    name="license_manager",
    ext_modules=cythonize([ext], language_level="3"),
    options={"build_ext": {"inplace": True}},
)
