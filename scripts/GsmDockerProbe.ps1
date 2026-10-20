# Fixed read-only commands only. A broken Desktop pipe must not hang diagnostics.
function Get-GsmDockerProbe {
    param([ValidateSet('info','ps','stats')][string]$Kind='info',[ValidateRange(100,60000)][int]$TimeoutMs=8000)
    $command=Get-Command docker -ErrorAction SilentlyContinue
    if(-not $command){return @{exitCode=-1;timedOut=$false;stdout='';stderr='Docker CLI missing'}}
    $process=[Diagnostics.Process]::new()
    $process.StartInfo.FileName=$command.Source
    $process.StartInfo.Arguments=switch($Kind){
        'info' {'info --format "{{.OSType}}"'}
        'ps' {'ps --format "table {{.Names}}\t{{.Ports}}\t{{.Status}}"'}
        'stats' {'stats --no-stream --format "{{json .}}"'}
    }
    $process.StartInfo.UseShellExecute=$false
    $process.StartInfo.CreateNoWindow=$true
    $process.StartInfo.RedirectStandardOutput=$true
    $process.StartInfo.RedirectStandardError=$true
    try {
        $null=$process.Start()
        $stdout=$process.StandardOutput.ReadToEndAsync()
        $stderr=$process.StandardError.ReadToEndAsync()
        if(-not $process.WaitForExit($TimeoutMs)){
            # This Process object owns only the CLI probe, never Desktop/WSL/container.
            try {$process.Kill();$null=$process.WaitForExit(1000)} catch {}
            return @{exitCode=-1;timedOut=$true;stdout='';stderr="Docker $Kind probe exceeded $TimeoutMs ms; inspect Docker Desktop startup."}
        }
        return @{exitCode=$process.ExitCode;timedOut=$false;stdout=$stdout.GetAwaiter().GetResult();stderr=$stderr.GetAwaiter().GetResult()}
    } finally {$process.Dispose()}
}
