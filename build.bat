@echo off
chcp 65001 >nul
title 打包批量网址快捷方式工具（含版本号+清理）

:: 生成时间戳作为版本号
for /f %%a in ('powershell -nologo -command "Get-Date -Format yyyyMMdd_HHmm"') do set VERSION=%%a

:: 设置主脚本名和输出名
set NAME=main
set OUTPUT=%NAME%_v%VERSION%

:: 清理旧目录和文件
echo 正在清理旧的打包文件...
rd /s /q build >nul 2>&1
rd /s /q dist >nul 2>&1
rd /s /q __pycache__ >nul 2>&1
del /q %NAME%.spec >nul 2>&1

:: 安装打包依赖模块
echo 正在安装必要的模块...
pip install pyinstaller
pip install tkinterdnd2

:: 执行打包
echo.
echo 正在打包 %NAME%.py 为 dist\%OUTPUT%.exe...
pyinstaller --noconsole --onefile --icon=icon.ico --name=%OUTPUT% %NAME%.py

echo.
echo ✅ 打包完成！输出文件位于：dist\%OUTPUT%.exe
pause
