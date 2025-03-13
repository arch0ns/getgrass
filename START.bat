@echo off
title Grass by Arch0ns
color 0A

:MENU
cls
echo =================================================================
echo                      Grass by Arch0ns
echo =================================================================
echo.
echo 1. Install Module
echo 2. Run Bot
echo 3. Exit
echo.
set /p choice="Enter your choice (1-3): "

if "%choice%"=="1" goto INSTALL
if "%choice%"=="2" goto RUN
if "%choice%"=="3" goto EXIT

:INSTALL
cls
echo Checking modules ...
pip3 install -r requirements.txt
echo installation completed!
pause
goto MENU


:RUN
cls
echo Starting the bot...
python main.py
pause
goto MENU

:EXIT
exit