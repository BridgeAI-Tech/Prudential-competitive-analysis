# One-command refresh: collect -> classify/normalise -> store -> export -> build dashboard.
# Optional credentials (collectors switch on automatically when set):
#   $env:APIFY_TOKEN       Facebook / Instagram post-level data (licensed Apify actors)
#   $env:YOUTUBE_API_KEY   YouTube Data API v3 (free key)
# Usage:  powershell -ExecutionPolicy Bypass -File .\run_pipeline.ps1 [-EndDate 2026-11-06]
param([string]$EndDate = "")
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$endArg = @()
if ($EndDate) { $endArg = @("--end", $EndDate) }
python pipeline/collect.py @endArg
if ($LASTEXITCODE -ne 0) { throw "collect failed" }
python pipeline/build.py
if ($LASTEXITCODE -ne 0) { throw "build failed" }
Set-Location web
npx next build
