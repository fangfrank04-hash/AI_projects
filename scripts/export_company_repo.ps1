# export_company_repo.ps1 —— 把当前项目导出为一个"全新干净仓库"，用于传公司代码库。
#
# 原理：git archive 只导出 git 已跟踪的文件（自动排除 .gitignore 里的东西，
# 比如 AI 工具目录、镜像 tar、.venv 等），导出后重新 git init，历史只有一个干净的初始提交。
#
# 用法（在项目根目录执行）：
#   powershell -ExecutionPolicy Bypass -File scripts/export_company_repo.ps1
#   powershell -ExecutionPolicy Bypass -File scripts/export_company_repo.ps1 -OutputPath "D:\公司库\aiproctor"
#
# 导出完成后，cd 进新目录确认无误，即可推到公司 GitLab/Gitea（问组长要仓库地址）：
#   git remote add origin <公司仓库地址>
#   git push -u origin main

param(
    [string]$OutputPath = "$env:USERPROFILE\Desktop\AiProctor_company_repo"
)

$ErrorActionPreference = "Stop"
$git = "C:\Program Files\Git\cmd\git.exe"

# 1. 前置检查：工作区必须干净（避免导出的内容缺了没提交的改动）
$status = & $git status --porcelain
if ($status) {
    Write-Host "[错误] 当前有未提交的改动，请先提交再导出：" -ForegroundColor Red
    Write-Host $status
    exit 1
}

# 2. 目标目录不能已存在
if (Test-Path $OutputPath) {
    Write-Host "[错误] 目标目录已存在：$OutputPath（请删除或换一个路径）" -ForegroundColor Red
    exit 1
}

Write-Host "[1/4] 导出 git 已跟踪的文件（自动排除 AI 工具目录/镜像 tar/.venv）..."
New-Item -ItemType Directory -Path $OutputPath | Out-Null
$zipPath = Join-Path $env:TEMP "aiproctor_export.zip"
& $git archive --format=zip --output=$zipPath HEAD
if ($LASTEXITCODE -ne 0) { Write-Host "[错误] 导出失败" -ForegroundColor Red; exit 1 }
Expand-Archive -Path $zipPath -DestinationPath $OutputPath -Force
Remove-Item $zipPath

Write-Host "[2/4] 在新目录初始化全新 git 仓库..."
Push-Location $OutputPath
& $git init -b main | Out-Null
& $git add -A

Write-Host "[3/4] 创建初始提交..."
& $git commit -m "init: AiProctor 智能监考服务 v1.2.0" | Out-Null

Write-Host "[4/4] 校验..."
$fileCount = (& $git ls-files | Measure-Object).Count
$hasAiDirs = Test-Path "$OutputPath\.agents"
Write-Host ""
Write-Host "导出完成：$OutputPath" -ForegroundColor Green
Write-Host "  - 文件数：$fileCount"
Write-Host "  - AI 工具目录混入检查：$(if ($hasAiDirs) { '发现 .agents，异常！' } else { '通过（无 AI 工具文件）' })"
Write-Host "  - 基础镜像 tar 混入检查：$(if (Test-Path "$OutputPath\deploy_split\*.tar") { '发现 tar，异常！' } else { '通过（无镜像 tar）' })"
Pop-Location

Write-Host ""
Write-Host "下一步（推到公司库，需要仓库地址）："
Write-Host "  cd `"$OutputPath`""
Write-Host "  git remote add origin <公司仓库地址>"
Write-Host "  git push -u origin main"
