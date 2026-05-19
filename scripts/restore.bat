@echo off
setlocal enabledelayedexpansion

if "%~1"=="" (
  echo uso: %~nx0 ^<ruta_backup_dir^>
  echo ej:  %~nx0 backups\20260519_164016
  exit /b 1
)

set "SRC=%~f1"
set "PROJECT_PREFIX=triaje-urgencias"
set "VOLUMES=postgres_data minio_data n8n_data"

if not exist "%SRC%" (
  echo ERROR: %SRC% no existe
  exit /b 1
)

echo ==^> restore desde: %SRC%

if exist "%SRC%\.env" (
  if exist .env (
    set "TS=%RANDOM%"
    echo ==^> .env existente -^> .env.bak.!TS!
    move /Y .env ".env.bak.!TS!" >nul
  )
  copy /Y "%SRC%\.env" .env >nul
  echo ==^> .env restaurado
) else (
  echo WARN: %SRC%\.env no encontrado
)

if exist "%SRC%\airflow_secrets.tar.gz" (
  echo ==^> airflow\secrets
  tar xzf "%SRC%\airflow_secrets.tar.gz"
)

echo ==^> parando containers
docker compose down >nul

echo ==^> recreando volumes vacios
for %%v in (%VOLUMES%) do (
  docker volume rm "%PROJECT_PREFIX%_%%v" >nul 2>&1
  docker volume create "%PROJECT_PREFIX%_%%v" >nul
)

echo ==^> restaurando volumes
for %%v in (%VOLUMES%) do (
  if exist "%SRC%\%%v.tar.gz" (
    echo   - %%v.tar.gz -^> %PROJECT_PREFIX%_%%v
    docker run --rm ^
      -v "%PROJECT_PREFIX%_%%v:/dest" ^
      -v "%SRC%:/src:ro" ^
      alpine sh -c "cd /dest && tar xzf /src/%%v.tar.gz"
  ) else (
    echo   - %%v.tar.gz no existe, skip
  )
)

echo ==^> levantando stack
docker compose up -d

echo.
echo ==^> done. estado:
docker compose ps --format "table {{.Name}}\t{{.Status}}"

endlocal
