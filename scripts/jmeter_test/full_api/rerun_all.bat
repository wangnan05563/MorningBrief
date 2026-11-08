@echo off
cd /d "%~dp0"
set PY=%~dp0..\..\..\backend\.venv\Scripts\python.exe
set LOG=runtime\rerun_all.log
if not exist runtime mkdir runtime
del runtime\all.done 2>nul
echo [%DATE% %TIME%] all start>>"%LOG%"

"%PY%" sandbox.py stop >>"%LOG%" 2>&1
del /q results\STOP 2>nul
del /q results\phases.csv 2>nul
del /q results\probes.json 2>nul
del /q results\report_data.json 2>nul
del /q results\stage_a_snapshot.json 2>nul
del /q results\tables.md 2>nul
del /q results\per_endpoint.csv 2>nul
del /q results\appendix_endpoints.md 2>nul
del /q results\baseline_*.jtl 2>nul
del /q results\baseline_*.log 2>nul
del /q results\stress_*.jtl 2>nul
del /q results\stress_*.log 2>nul
del /q results\soak_*.jtl 2>nul
del /q results\soak_*.log 2>nul
del /q results\monitor_*.csv 2>nul

"%PY%" sandbox.py prepare --force >>"%LOG%" 2>&1
if errorlevel 1 goto fail
"%PY%" sandbox.py start >>"%LOG%" 2>&1
if errorlevel 1 goto fail
"%PY%" seed_auth.py >>"%LOG%" 2>&1
if errorlevel 1 goto fail
"%PY%" probe_all.py >>"%LOG%" 2>&1
if errorlevel 1 goto fail
"%PY%" run_suite.py --baseline >>"%LOG%" 2>&1
if errorlevel 1 goto fail
"%PY%" run_suite.py --stress >>"%LOG%" 2>&1
if errorlevel 1 goto fail
"%PY%" analyze.py >>"%LOG%" 2>&1
copy /y results\report_data.json results\stage_a_snapshot.json >>"%LOG%" 2>&1
echo [%DATE% %TIME%] stage_a done, soak next>>"%LOG%"

"%PY%" run_suite.py --soak >>"%LOG%" 2>&1
if errorlevel 1 goto fail
"%PY%" analyze.py >>"%LOG%" 2>&1
if errorlevel 1 goto fail
"%PY%" make_report.py results\report_data.json >>"%LOG%" 2>&1
if errorlevel 1 goto fail
"%PY%" sandbox.py stop >>"%LOG%" 2>&1

echo OK all>runtime\all.done
echo [%DATE% %TIME%] all OK>>"%LOG%"
exit /b 0

:fail
echo FAIL all exit=%errorlevel%>runtime\all.done
echo [%DATE% %TIME%] all FAIL>>"%LOG%"
exit /b 1
