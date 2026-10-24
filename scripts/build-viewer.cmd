@echo off
rem Rebuilds the web viewer into logiclayer/viewer/index.html.
rem
rem Only needed when the visualization itself changes. The built file is
rem committed so the tool works without Node installed.
pushd "%~dp0..\web"
call npm install --no-fund --no-audit
call npm run build
popd
