# PowerShell 转义字符兼容性测试套件
# 用于测试 PowerShell 中特殊字符的正确处理

param(
    [switch]$Verbose
)

# 设置输出编码为 UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PowerShell 转义字符兼容性测试" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$testResults = @()
$passedCount = 0
$failedCount = 0

function Test-EscapeCharacter {
    param(
        [string]$TestName,
        [object]$TestValue,
        [object]$ExpectedResult
    )
    
    try {
        # 使用 Trim() 移除可能的空白字符后进行对比
        $passed = $TestValue.Trim() -eq $ExpectedResult.Trim()
        
        if ($passed) {
            $status = "✓ 通过"
            $color = "Green"
            $script:passedCount++
        } else {
            $status = "✗ 失败"
            $color = "Red"
            $script:failedCount++
        }
        
        $testResults += [PSCustomObject]@{
            TestName = $TestName
            Status = $status
            Expected = $ExpectedResult
            Actual = $TestValue
        }
        
        Write-Host "[$status] $TestName" -ForegroundColor $color
        if ($Verbose -or -not $passed) {
            Write-Host "  期望：'$ExpectedResult'" -ForegroundColor Gray
            Write-Host "  实际：'$TestValue'" -ForegroundColor Gray
        }
        Write-Host ""
    }
    catch {
        $script:failedCount++
        Write-Host "[✗ 异常] $TestName" -ForegroundColor Red
        Write-Host "  错误：$($_.Exception.Message)" -ForegroundColor Red
        Write-Host ""
    }
}

Write-Host "1. 反引号 (`) 转义测试" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Gray

# 测试反引号转义特殊字符
$escapedDoubleQuote = "`""
$escapedSingleQuote = "`'"
$escapedBacktick = "``"
$escapedDollar = "`$"
$escapedQuestion = "`?"

Test-EscapeCharacter "反引号转义双引号" $escapedDoubleQuote '"'
Test-EscapeCharacter "反引号转义单引号" $escapedSingleQuote "'"
Test-EscapeCharacter "反引号转义反引号" $escapedBacktick '`'
Test-EscapeCharacter "反引号转义美元符号" $escapedDollar '$'
Test-EscapeCharacter "反引号转义问号" $escapedQuestion '?'

Write-Host "2. 变量扩展测试" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Gray

$testVar = "Hello"
Test-EscapeCharacter "双引号内变量扩展" "$testVar World" 'Hello World'
Test-EscapeCharacter "单引号内变量不扩展" '$testVar World' '$testVar World'
Test-EscapeCharacter "花括号变量边界" "${testVar}World" 'HelloWorld'

Write-Host "3. 特殊字符测试" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Gray

Test-EscapeCharacter "换行符" "Line1`nLine2" "Line1`nLine2"
Test-EscapeCharacter "制表符" "Col1`tCol2" "Col1`tCol2"
Test-EscapeCharacter "回车符" "Line1`rLine2" "Line1`rLine2"

Write-Host "4. 路径和反斜杠测试" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Gray

Test-EscapeCharacter "单引号路径" 'C:\Users\test' 'C:\Users\test'
Test-EscapeCharacter "双引号路径转义" "C:\Users`\test" 'C:\Users\test'
Test-EscapeCharacter "Here-String 路径" @"
C:\Users\test
"@ 'C:\Users\test'

Write-Host "5. 中文和 Unicode 测试" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Gray

Test-EscapeCharacter "中文字符串" "中文测试" '中文测试'
Test-EscapeCharacter "混合字符" "Hello 世界 123" 'Hello 世界 123'

Write-Host "6. 命令和参数测试" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Gray

# 测试命令中的特殊字符
$testPath = "C:\test dir"
Test-EscapeCharacter "带空格路径的参数" $testPath $testPath

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "测试结果汇总" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "总测试数：$($testResults.Count)" -ForegroundColor White
Write-Host "通过：$passedCount" -ForegroundColor Green
Write-Host "失败：$failedCount" -ForegroundColor $(if ($failedCount -eq 0) { "Green" } else { "Red" })
Write-Host ""

# 导出测试结果
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$resultFile = ".\test_results_powershell_$timestamp.json"
$testResults | Export-Csv -Path ".\test_results_powershell_$timestamp.csv" -Encoding UTF8 -NoTypeInformation

Write-Host "测试结果已导出到：$resultFile" -ForegroundColor Cyan

if ($failedCount -gt 0) {
    Write-Warning "发现 $failedCount 个测试失败，请检查上述输出详情"
    exit 1
} else {
    Write-Host "所有测试通过！" -ForegroundColor Green
    exit 0
}
