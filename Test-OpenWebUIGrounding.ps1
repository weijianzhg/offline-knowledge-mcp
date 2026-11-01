$ErrorActionPreference = 'Stop'
$credential = Import-Clixml -LiteralPath (Join-Path (Split-Path $PSScriptRoot -Parent) 'open-webui-credential.xml')
$signin = @{email=$credential.UserName; password=$credential.GetNetworkCredential().Password} | ConvertTo-Json
$session = Invoke-RestMethod 'http://127.0.0.1:8080/api/v1/auths/signin' -Method Post -ContentType 'application/json' -Body $signin
$credential=$null; $signin=$null
$headers = @{Authorization="Bearer $($session.token)"}
$checks = @(
    @{name='world_bank'; prompt='Use the offline knowledge tool lookup_fact to find Japan (JPN) population in 2024. Give the exact number, unit, observation year, snapshot date, and source URL. Do not answer from memory.'},
    @{name='wikipedia'; prompt='Search the offline Wikipedia collection for solar eclipse, read the matching article with read_document, and explain briefly what causes a solar eclipse. Cite the article URL and the archive snapshot date.'}
)
$report = @()
try {
    $inventory = Invoke-RestMethod 'http://127.0.0.1:8080/api/models?refresh=true' -Headers $headers -TimeoutSec 60
    if ('offline-knowledge-qwen3.8' -notin @($inventory.data.id)) { throw 'Knowledge preset is not visible in Open WebUI model inventory.' }
    foreach ($check in $checks) {
        $userId = [guid]::NewGuid().ToString()
        $assistantId = [guid]::NewGuid().ToString()
        $timestamp = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
        $history = @{}
        $history[$userId] = @{id=$userId;role='user';content=$check.prompt;parentId=$null;childrenIds=@($assistantId);timestamp=$timestamp;models=@('offline-knowledge-qwen3.8')}
        $history[$assistantId] = @{id=$assistantId;role='assistant';content='';parentId=$userId;childrenIds=@();timestamp=($timestamp+1);model='offline-knowledge-qwen3.8';modelName='Offline Knowledge (Qwen3.8)';modelIdx=0;done=$false}
        $chatBody = @{chat=@{title=('Offline knowledge check - ' + $check.name);models=@('offline-knowledge-qwen3.8');history=@{currentId=$assistantId;messages=$history};messages=@($history[$userId],$history[$assistantId])}} | ConvertTo-Json -Depth 12
        $chat = Invoke-RestMethod 'http://127.0.0.1:8080/api/v1/chats/new' -Headers $headers -Method Post -ContentType 'application/json' -Body $chatBody
        $body = @{model='offline-knowledge-qwen3.8'; messages=@(@{role='user';content=$check.prompt}); stream=$true; chat_id=$chat.id; id=$assistantId; tool_ids=@('server:mcp:offline_knowledge'); background_tasks=@{title_generation=$false;tags_generation=$false;follow_up_generation=$false};params=@{function_calling='native'; temperature=0; num_ctx=32768; num_predict=768; think=$false; keep_alive='5m'}} | ConvertTo-Json -Depth 10
        $timer = [Diagnostics.Stopwatch]::StartNew()
        $null = Invoke-RestMethod 'http://127.0.0.1:8080/api/chat/completions' -Headers $headers -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 300
        $savedChat = Invoke-RestMethod "http://127.0.0.1:8080/api/v1/chats/$($chat.id)" -Headers $headers
        $reply = $savedChat.chat.history.messages.$assistantId
        $timer.Stop()
        $report += @{name=$check.name; chatId=$chat.id; elapsedSeconds=$timer.Elapsed.TotalSeconds; response=$reply}
        $report | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'logs\openwebui-grounding.json') -Encoding utf8
        if ([string]::IsNullOrWhiteSpace($reply.content)) { throw "No final answer for $($check.name)" }
        $calledTools = @($reply.output | Where-Object { $_.type -eq 'function_call' -and $_.status -eq 'completed' } | ForEach-Object name)
        $expectedTools = if ($check.name -eq 'world_bank') { @('offline_knowledge_lookup_fact') } else { @('offline_knowledge_search_knowledge','offline_knowledge_read_document') }
        foreach ($expectedTool in $expectedTools) { if ($expectedTool -notin $calledTools) { throw "Expected tool was not executed: $expectedTool" } }
        if ($reply.content -notmatch 'https://') { throw 'Answer omitted its source URL' }
        Write-Output ($check.name + ': ' + $reply.content)
        Write-Output ('Saved chat: ' + $chat.id)
    }
} finally { $session=$null; $headers=$null }
