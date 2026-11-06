param(
    [Parameter(Mandatory=$true)][string]$Model,
    [Parameter(Mandatory=$true)][string]$CredentialFile,
    [string]$WebUI = 'http://127.0.0.1:8080'
)
$ErrorActionPreference = 'Stop'
$logDir = Join-Path $PSScriptRoot 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$credential = Import-Clixml -LiteralPath $CredentialFile
$signin = @{email=$credential.UserName; password=$credential.GetNetworkCredential().Password} | ConvertTo-Json
$session = Invoke-RestMethod "$WebUI/api/v1/auths/signin" -Method Post -ContentType 'application/json' -Body $signin
$credential=$null; $signin=$null
$headers = @{Authorization="Bearer $($session.token)"}
$checks = @(
    @{name='wikivoyage'; domain='en.wikivoyage.org'; prompt='Use offline_knowledge_search_knowledge with source_id wikivoyage_en and query London, then read_document on the first result. In 2 sentences explain what the City of London is. Cite the returned URL and archive snapshot date.'},
    @{name='ifixit'; domain='www.ifixit.com'; prompt='Use offline_knowledge_search_knowledge with source_id ifixit_en and query battery replacement, then read_document on the first result. Report only the guide title, author and listed number of steps. Cite the returned URL and archive snapshot date.'},
    @{name='gutenberg'; domain='www.gutenberg.org'; prompt='Use offline_knowledge_search_knowledge with source_id gutenberg_en_literature and query poetry, then read_document on the first result. Report the book title and author from the text. Cite the returned URL and archive snapshot date.'}
)
$report = @()
try {
    $inventory = Invoke-RestMethod "$WebUI/api/models?refresh=true" -Headers $headers -TimeoutSec 60

    $modelInfo = $inventory.data | Where-Object id -eq $model
    if (-not $modelInfo -or 'server:mcp:offline_knowledge' -notin @($modelInfo.info.meta.toolIds)) { throw "Shared knowledge tool is missing for $model" }
    foreach ($check in $checks) {
        $userId = [guid]::NewGuid().ToString()
        $assistantId = [guid]::NewGuid().ToString()
        $timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        $history = @{}
        $history[$userId] = @{id=$userId;role='user';content=$check.prompt;parentId=$null;childrenIds=@($assistantId);timestamp=$timestamp;models=@($model)}
        $history[$assistantId] = @{id=$assistantId;role='assistant';content='';parentId=$userId;childrenIds=@();timestamp=($timestamp+1);model=$model;modelName=$model;modelIdx=0;done=$false}
        $chatBody = @{chat=@{title=('Shared knowledge check - ' + $model + ' - ' + $check.name);models=@($model);history=@{currentId=$assistantId;messages=$history};messages=@($history[$userId],$history[$assistantId])}} | ConvertTo-Json -Depth 12
        $chat = Invoke-RestMethod "$WebUI/api/v1/chats/new" -Headers $headers -Method Post -ContentType 'application/json' -Body $chatBody
        $body = @{model=$model; messages=@(@{role='user';content=$check.prompt}); stream=$true; chat_id=$chat.id; id=$assistantId; tool_ids=@($modelInfo.info.meta.toolIds); background_tasks=@{title_generation=$false;tags_generation=$false;follow_up_generation=$false};params=@{function_calling='native'; temperature=0; num_ctx=32768; num_predict=768; think=$false; keep_alive='1m'}} | ConvertTo-Json -Depth 10
        $timer = [Diagnostics.Stopwatch]::StartNew()
        $null = Invoke-RestMethod "$WebUI/api/chat/completions" -Headers $headers -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 300
        $savedChat = Invoke-RestMethod "$WebUI/api/v1/chats/$($chat.id)" -Headers $headers
        $reply = $savedChat.chat.history.messages.$assistantId
        $timer.Stop()
        $report += @{model=$model; name=$check.name; chatId=$chat.id; elapsedSeconds=$timer.Elapsed.TotalSeconds; response=$reply}
        $report | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'logs\extra-collections-grounding.json') -Encoding utf8
        if ([string]::IsNullOrWhiteSpace($reply.content)) { throw "No final answer for $($check.name)" }
        $calledTools = @($reply.output | Where-Object { $_.type -eq 'function_call' -and $_.status -eq 'completed' } | ForEach-Object name)
        $expectedTools = @('offline_knowledge_search_knowledge','offline_knowledge_read_document')
        foreach ($expectedTool in $expectedTools) { if ($expectedTool -notin $calledTools) { throw "Expected tool was not executed: $expectedTool" } }
        if ($reply.content -notmatch 'https://') { throw 'Answer omitted its source URL' }
        if ($reply.content -notmatch [regex]::Escape($check.domain)) { throw 'Answer omitted the expected publisher citation' }
        Write-Output ($model + ' / ' + $check.name + ': ' + $reply.content)
        Write-Output ('Saved chat: ' + $chat.id)
    }
} finally { $session=$null; $headers=$null }
