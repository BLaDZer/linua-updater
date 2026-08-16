@echo off
REM source: https://github.com/nektos/act
REM docs: https://nektosact.com/
REM
REM official GitHub runner for CI build: https://github.com/actions/runner
REM community runner for CI build: https://github.com/ChristopherHX/github-act-runner
setlocal

tools\act -P windows-latest=-self-hosted