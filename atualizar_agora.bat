@echo off
chcp 65001 > nul
title Sincronizador Comercial Mesus
echo ========================================================
echo   SINCRONIZANDO PAINEL EXECUTIVO COMERCIAL (MESUS)
echo ========================================================
echo.
echo Conectando ao Chatwoot, atualizando dados e publicando na Vercel...
echo.
"C:\Users\oluca\AppData\Local\Programs\Python\Python310\python.exe" "C:\Users\oluca\painel-executivo-comercial\sync_daily.py"
echo.
echo ========================================================
echo   SINCRONIZACAO CONCLUIDA COM SUCESSO!
echo ========================================================
echo.
pause
