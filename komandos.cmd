@echo off

rem make the executed directory current
pushd %~dp0

rem start - to hide the console after launching the GUI
rem  1>stdout.txt 2>stderr.txt for debugging w console-less launchable app
rem start python\pythonw komandos\komandos.py 1>stdout.txt 2>stderr.txt
start python\pythonw komandos\komandos.py

rem restore the old working directory in case this was called from shell
popd