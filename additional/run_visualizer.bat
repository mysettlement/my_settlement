REM Добавляем Graphviz в PATH
set PATH=%PATH%;C:\Program Files\Graphviz\bin

REM Переходим в директорию со скриптом
cd /d "%~dp0"

REM Запускаем визуализатор
python visualizer.py
