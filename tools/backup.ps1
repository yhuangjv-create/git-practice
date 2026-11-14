<#
版本快照备份脚本

作用：把当前源码复制到备份目录，文件夹名格式为
      v<版本号>_<改动说明>_<时间戳>

用法：
  .\tools\backup.ps1 -Desc "改了什么"    # 手动备份并指定说明
  .\tools\backup.ps1                     # 自动使用最近一次提交的说明

由 .git/hooks/post-commit 钩子自动调用，每次 commit 后生成一份快照。
#>
param(
    [string]$Desc = "",
    [string]$Dest = "D:\桌面\Clara版本备份"
)

$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

# ---- 1. 读取版本号（唯一真源：mkr/__init__.py） ----
$version = "unknown"
$init = Join-Path $repo "mkr\__init__.py"
if (Test-Path $init) {
    $m = Select-String -Path $init -Pattern '__version__\s*=\s*"([^"]+)"'
    if ($m) { $version = $m.Matches[0].Groups[1].Value }
}

# ---- 2. 确定改动说明 ----
if (-not $Desc) {
    $Desc = (git log -1 --pretty=%s 2>$null)
    if (-not $Desc) { $Desc = "手动备份" }
}
# 去掉文件夹名非法字符
$safeDesc = (($Desc -replace '[\\/:*?"<>|\r\n\t]', ' ') -replace '\s+', ' ').Trim()
if ($safeDesc.Length -gt 40) { $safeDesc = $safeDesc.Substring(0, 40) }

# ---- 3. 生成目标文件夹 ----
$stamp = Get-Date -Format "yyyyMMdd-HHmm"
$name = "v{0}_{1}_{2}" -f $version, $safeDesc, $stamp
$target = Join-Path $Dest $name

if (Test-Path $target) { $target = "$target-2" }
New-Item -ItemType Directory -Path $target -Force | Out-Null

# ---- 4. 复制源码（排除 .git、构建产物、缓存、录制数据） ----
robocopy $repo $target /E /XD ".git" "dist" "build" "__pycache__" ".venv" "venv" "recordings" ".pytest_cache" ".ruff_cache" /XF "*.pyc" /NFL /NDL /NJH /NJS /NP | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy 复制失败，退出码 $LASTEXITCODE" }

# ---- 5. 写入备份说明 ----
$commit = ""
if (Test-Path (Join-Path $repo ".git")) {
    $commit = (git log -1 --pretty="%h %ad %s" --date=short 2>$null)
}
$info = @"
版本号     : v$version
备份时间   : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
改动说明   : $Desc
对应提交   : $commit
备份来源   : $repo
"@
$info | Set-Content -Path (Join-Path $target "_备份说明.txt") -Encoding UTF8

Write-Host "已备份到: $target"
