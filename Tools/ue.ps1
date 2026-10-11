<#
.SYNOPSIS
    Unreal Engine をコマンドラインから操作するヘルパー。
    この PC で Claude Code（Claude デスクトップアプリ、または claude remote-control）を
    動かしているときに、Claude がエディタを起動・生成・撮影するために使う。

.DESCRIPTION
    使い方:  Tools\ue.cmd <command> [options]
      find            UnrealEditor.exe の場所を表示する
      open            エディタでプロジェクトを開く（すぐ戻る）
      build           エディタを起動してロフトシーン (L_Loft) を生成し、終了する
      shots           L_Loft を 6 視点で撮影し Saved\Screenshots\Loft に PNG を書き出す
      run <file.py>   任意の UE Python スクリプトをエディタで実行して終了する
      log             直近のエディタログから [Loft] の行とエラーを表示する

    オプション:
      -Width 1920 -Height 1080   撮影解像度 (shots)
      -Warmup 30                 撮影前にシェーダー待ちする秒数 (shots)
      -KeepOpen                  撮影後もエディタを開いたままにする (shots)

    UE のインストール先は次の順で探す:
      1. 環境変数 UE_ROOT            例: C:\Program Files\Epic Games\UE_5.6
      2. レジストリ HKLM\SOFTWARE\EpicGames\Unreal Engine\<EngineAssociation>
      3. C:\Program Files\Epic Games\UE_5.* の最新
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)] [string] $Command = "help",
    [Parameter(Position = 1)] [string] $Arg = "",
    [int] $Width = 1920,
    [int] $Height = 1080,
    [int] $Warmup = 30,
    [switch] $KeepOpen
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "..")).Path
$Project = Join-Path $Root "My3DSpace.uproject"
$LogFile = Join-Path $Root "Saved\Logs\My3DSpace.log"

function Quote([string] $s) { return '"' + $s + '"' }

function Get-EngineAssociation {
    try { return (Get-Content $Project -Raw | ConvertFrom-Json).EngineAssociation } catch { return "" }
}

function Find-Editor {
    $candidates = @()
    if ($env:UE_ROOT) { $candidates += (Join-Path $env:UE_ROOT "Engine\Binaries\Win64\UnrealEditor.exe") }
    $assoc = Get-EngineAssociation
    if ($assoc) {
        foreach ($hive in @("HKLM:\SOFTWARE\EpicGames\Unreal Engine\$assoc", "HKCU:\SOFTWARE\Epic Games\Unreal Engine\$assoc")) {
            try {
                $dir = (Get-ItemProperty -Path $hive -ErrorAction Stop).InstalledDirectory
                if ($dir) { $candidates += (Join-Path $dir "Engine\Binaries\Win64\UnrealEditor.exe") }
            } catch { }
        }
        try {
            $builds = Get-ItemProperty -Path "HKCU:\SOFTWARE\Epic Games\Unreal Engine\Builds" -ErrorAction Stop
            foreach ($p in $builds.PSObject.Properties) {
                if ($p.Name -eq $assoc) { $candidates += (Join-Path $p.Value "Engine\Binaries\Win64\UnrealEditor.exe") }
            }
        } catch { }
    }
    foreach ($base in @("C:\Program Files\Epic Games", "D:\Program Files\Epic Games", "D:\Epic Games", "C:\Epic Games", "E:\Epic Games")) {
        if (Test-Path $base) {
            $dirs = Get-ChildItem -Path $base -Directory -Filter "UE_*" | Sort-Object -Descending {
                try { [version]($_.Name.Substring(3)) } catch { [version]"0.0" }
            }
            foreach ($d in $dirs) { $candidates += (Join-Path $d.FullName "Engine\Binaries\Win64\UnrealEditor.exe") }
        }
    }
    foreach ($c in $candidates) { if (Test-Path $c) { return $c } }
    throw "UnrealEditor.exe が見つかりません。環境変数 UE_ROOT にインストール先 (例: C:\Program Files\Epic Games\UE_5.6) を設定してください。"
}

function Invoke-Editor([string[]] $EditorArgs, [switch] $Wait) {
    $exe = Find-Editor
    Write-Host "UnrealEditor : $exe"
    Write-Host "args         : $($EditorArgs -join ' ')"
    $p = Start-Process -FilePath $exe -ArgumentList $EditorArgs -PassThru
    if ($Wait) {
        $p.WaitForExit()
        Write-Host "exit code    : $($p.ExitCode)"
        return $p.ExitCode
    }
    return 0
}

function Show-Log {
    if (-not (Test-Path $LogFile)) { Write-Host "ログがまだありません: $LogFile"; return }
    Write-Host "--- $LogFile (抜粋) ---"
    Get-Content $LogFile -Tail 6000 |
        Where-Object { $_ -match "\[Loft|LogPython|Error:" } |
        Select-Object -Last 100
}

switch ($Command.ToLower()) {
    "find" {
        Find-Editor
    }
    "open" {
        Invoke-Editor @((Quote $Project)) | Out-Null
        Write-Host "エディタを起動しました。"
    }
    "build" {
        $script = Join-Path $Root "Content\Python\build_loft.py"
        Invoke-Editor @((Quote $Project), "-ExecutePythonScript=$(Quote $script)", "-unattended", "-NoSplash", "-log") -Wait | Out-Null
        Show-Log
        Write-Host "生成が終わりました。Tools\ue.cmd open でエディタを開くか、Tools\ue.cmd shots で撮影できます。"
    }
    "shots" {
        $env:LOFT_WIDTH = "$Width"
        $env:LOFT_HEIGHT = "$Height"
        $env:LOFT_WARMUP = "$Warmup"
        $env:LOFT_KEEP_OPEN = $(if ($KeepOpen) { "1" } else { "0" })
        Invoke-Editor @((Quote $Project), '-ExecCmds="py import render_shots"', "-unattended", "-NoSplash", "-log") -Wait | Out-Null
        $src = Join-Path $Root "Saved\Screenshots\WindowsEditor"
        $dst = Join-Path $Root "Saved\Screenshots\Loft"
        New-Item -ItemType Directory -Force -Path $dst | Out-Null
        Get-ChildItem -Path $src -Filter "Loft_*.png" -ErrorAction SilentlyContinue | Move-Item -Destination $dst -Force
        $files = Get-ChildItem -Path $dst -Filter "Loft_*.png" -ErrorAction SilentlyContinue
        if ($files) { $files | ForEach-Object { Write-Host $_.FullName } }
        else { Write-Host "スクリーンショットが見つかりません。Tools\ue.cmd log で原因を確認してください。"; Show-Log }
    }
    "run" {
        if (-not $Arg) { throw "使い方: Tools\ue.cmd run <file.py>" }
        $script = (Resolve-Path $Arg).Path
        Invoke-Editor @((Quote $Project), "-ExecutePythonScript=$(Quote $script)", "-unattended", "-NoSplash", "-log") -Wait | Out-Null
        Show-Log
    }
    "log" {
        Show-Log
    }
    default {
        Get-Help $MyInvocation.MyCommand.Path -Detailed
    }
}
