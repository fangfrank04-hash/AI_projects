@echo off
chcp 65001 >nul
echo ============================================
echo   RAG 评测系统 - 一键安装 (Python 3.12)
echo ============================================
echo.

:: 检查 Python
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [错误] 未找到 Python！请先安装 Python 3.12
    pause
    exit /b 1
)
python --version

:: 创建虚拟环境
echo.
echo [1/2] 创建虚拟环境...
if exist "venv" (
    echo        venv 已存在，跳过创建
) else (
    python -m venv venv
    if %ERRORLEVEL% NEQ 0 (
        echo [错误] 创建 venv 失败
        pause
        exit /b 1
    )
)

:: 激活虚拟环境
echo.
echo       激活虚拟环境...
call venv\Scripts\activate.bat

:: 安装依赖
echo.
echo [2/2] 安装依赖（从本地包，全程不联网）...
pip install --no-index --find-links=offline_packages -r evaluation_deps/requirements.txt

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [警告] 部分依赖安装失败。方案B仍可正常使用。
    echo        可能失败的包：ragas, langchain（需 OpenAI Key）
) else (
    echo.
    echo ============================================
    echo   安装成功！
    echo ============================================
)

:: 验证
echo.
echo 验证环境...
python -c "from evaluation import auto_evaluate; print('  auto_evaluate 导入成功')" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo   方案B（LLM-as-Judge）可用
) else (
    echo   [警告] 方案B 导入失败
)

python -c "from evaluation import RagasEvaluator; print('  RagasEvaluator 导入成功')" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo   方案A（RAGAS）可用
) else (
    echo   方案A（RAGAS）不可用（需 ragas 库 + OpenAI Key）
)

:: 运行测试
echo.
echo 运行基础测试...
python -m pytest tests/test_evaluation.py -v -k "LLMJudge or BaseEvaluator" --tb=line -q 2>nul
if %ERRORLEVEL% EQU 0 (
    echo   基础测试通过
) else (
    echo   [警告] 部分测试未通过
)

echo.
echo ============================================
echo   内网部署完成！
echo ============================================
echo.
echo   激活: venv\Scripts\activate
echo   测试: python -m pytest tests/test_evaluation.py -v
echo   评测: python run_evaluation.py --dataset tests/mock_data/eval_dataset.json
echo ============================================
pause
