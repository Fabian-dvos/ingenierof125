param(
  [switch]$Reverse
)

$raw = Get-Clipboard -Raw
$raw = $raw -replace "`r", ""
$lines = $raw -split "`n"

$match = $lines | Select-String -Pattern '^diff --git ' | Select-Object -First 1
if (-not $match) {
  throw "No encontré 'diff --git' en el portapapeles. Copiá el patch completo (desde 'diff --git ...')."
}

$start = $match.LineNumber - 1
$clean = $lines[$start..($lines.Length-1)] | Where-Object { $_ -notmatch '^\s*```' }
$patch = ($clean -join "`n") + "`n"

if ($Reverse) {
  $patch | git apply -R --whitespace=fix
} else {
  $patch | git apply --whitespace=fix
}

Write-Host "OK: patch aplicado." -ForegroundColor Green
