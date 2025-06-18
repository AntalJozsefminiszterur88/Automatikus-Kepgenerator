@echo off
title Automatikus Kepgenerator Build

echo [INFO] Fuggosegek telepitese...
pip install pyinstaller pyinstaller-hooks-contrib

echo [INFO] Build folyamat inditasa...
pyinstaller ^
    --name "AutomatikusKepgenerator" ^
    --windowed ^
    --icon="logo.ico" ^
    --add-data "config;config" ^
    --add-data "gui/assets;gui/assets" ^
    --add-data "logo.ico;." ^
    --hidden-import "PySide6.QtSvg" ^
    --hidden-import "pynput.keyboard._win32" ^
    --hidden-import "pynput.mouse._win32" ^
    --clean ^
    main.py

echo.
echo A build befejezodott. Ellenorizd a fenti uzeneteket az esetleges hibakert.
pause