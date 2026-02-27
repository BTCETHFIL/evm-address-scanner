@echo off

:: 设置中文编码
chcp 65001 >nul

echo 正在安装依赖...
pip install -r requirements.txt

if %errorlevel% equ 0 (
    echo 依赖安装成功，正在启动程序...
    python evm_address_scanner.py
) else (
    echo 依赖安装失败，请检查网络连接或Python环境
    pause
)
