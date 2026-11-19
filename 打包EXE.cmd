@echo off
cd /d "%~dp0"
python build_release.py %* || goto :err
echo.
echo 默认输出目录: dist\release
pause
exit /b 0
:err
echo 打包失败，请查看上方错误信息。
pause
exit /b 1
