# Start Next.js dev server for WhoDados
# A partir de 2026-09 o projeto de producao vive em WhoDados/ (na raiz do repo).
$ErrorActionPreference = "Continue"
$repoRoot = (Resolve-Path "$PSScriptRoot\..").Path
$fePath = Join-Path $repoRoot "WhoDados\frontend"
$outFile = "$env:TEMP\nextjs_dev.log"

if (-not (Test-Path $fePath)) {
    Write-Host "[ERROR] WhoDados frontend nao encontrado em: $fePath"
    exit 1
}

Write-Host "Starting Next.js dev server..."
Write-Host "Working directory: $fePath"

try {
    $proc = Start-Process -FilePath "cmd" -ArgumentList "/c","cd /d `"$fePath`" && npx next dev -p 3000" -WorkingDirectory $fePath -PassThru -NoNewWindow -RedirectStandardOutput $outFile -RedirectStandardError "$env:TEMP\nextjs_err.log" -ErrorAction Stop
    Write-Host "Process started with PID: $($proc.Id)"
    
    Write-Host "Waiting 15s for server to start..."
    Start-Sleep -Seconds 15
    
    if ($proc.HasExited) {
        Write-Host "[ERROR] Process exited with code: $($proc.ExitCode)"
        if (Test-Path $outFile) { Get-Content $outFile }
        if (Test-Path "$env:TEMP\nextjs_err.log") { Get-Content "$env:TEMP\nextjs_err.log" }
    } else {
        Write-Host "[SUCCESS] Server is running!"
        
        # Check if port 3000 is listening
        $tcpCon = Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue
        if ($tcpCon) {
            Write-Host "Port 3000 is listening: $($tcpCon.Count) connection(s)"
            Write-Host "LocalAddress: $($tcpCon[0].LocalAddress)"
        } else {
            Write-Host "Port 3000 not found yet..."
        }
        
        if (Test-Path $outFile) { 
            Write-Host "--- STDOUT ---"
            Get-Content $outFile
        }
    }
} catch {
    Write-Host "[ERROR] $($_.Exception.Message)"
}

Write-Host "Done. Check $outFile for output."
