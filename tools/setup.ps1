<#
一次性启用版本备份钩子

作用：把 Git 的钩子目录指向仓库内的 tools/hooks，
      之后钩子随仓库走，不需要再往 .git/hooks 里复制文件。

换新电脑后只需运行一次：
  .\tools\setup.ps1
#>
$ErrorActionPreference = "Stop"

$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo

if (-not (Test-Path "tools\hooks\post-commit")) {
    throw "找不到 tools\hooks\post-commit"
}

git config core.hooksPath tools/hooks
if ($LASTEXITCODE -ne 0) { throw "设置 core.hooksPath 失败" }

Write-Host "已启用：core.hooksPath = $(git config core.hooksPath)"
Write-Host "钩子实际路径：$repo\tools\hooks\post-commit"
Write-Host "验证命令：git hook run post-commit"
