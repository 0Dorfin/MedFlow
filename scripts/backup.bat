@echo off
setlocal enabledelayedexpansion

set "PROJECT_PREFIX=proyecto_triage_6"
set "VOLUMES=postgres_data minio_data n8n_data"

for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set "DT=%%I"
set "TS=%DT:~0,8%_%DT:~8,6%"

if "%~1"=="" (
  set "DEST=backups\%TS%"
) else (
  set "DEST=%~1"
)

if not exist .env (
  echo ERROR: .env no encontrado
  exit /b 1
)

if not exist "%DEST%" mkdir "%DEST%"

echo ==^> backup destino: %DEST%

echo ==^> parando containers
docker compose stop >nul

echo ==^> backup volumes
for %%v in (%VOLUMES%) do (
  docker volume inspect "%PROJECT_PREFIX%_%%v" >nul 2>&1
  if !errorlevel! == 0 (
    echo   - %PROJECT_PREFIX%_%%v -^> %%v.tar.gz
    docker run --rm ^
      -v "%PROJECT_PREFIX%_%%v:/src:ro" ^
      -v "%cd%\%DEST%:/dest" ^
      alpine sh -c "cd /src && tar czf /dest/%%v.tar.gz ."
  ) else (
    echo   - %PROJECT_PREFIX%_%%v no existe, skip
  )
)

echo ==^> copiando .env
copy /Y .env "%DEST%\.env" >nul

echo ==^> backup airflow\secrets
if exist airflow\secrets (
  tar czf "%DEST%\airflow_secrets.tar.gz" airflow\secrets
)

echo ==^> levantando containers
docker compose up -d >nul

(
  echo TriageIA backup
  echo timestamp: %TS%
  echo host: %COMPUTERNAME%
  echo project_prefix: %PROJECT_PREFIX%
  echo volumes: %VOLUMES%
) > "%DEST%\MANIFEST.txt"

echo.
echo ==^> done. archivos en %DEST%:
dir /B "%DEST%"

endlocal
