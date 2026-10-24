@echo off
rem Runs the Logic Layer command line from this checkout's virtual environment,
rem without activating it first. Only useful when working on Logic Layer itself;
rem an ordinary install puts a `logic` command on the PATH.
rem
rem   scripts\logic.cmd query "quiet(Who)."
rem
rem The knowledge base is logic.jsonl in whatever directory you run this from,
rem or wherever --kb points.
"%~dp0..\.venv\Scripts\python.exe" -m logiclayer.cli %*
