<#
.SYNOPSIS
  Lists Azure OpenAI chat/embedding models you can actually deploy, per region.

.DESCRIPTION
  A model is deployable only if all three gates pass:
    1. offered in the region and deployment type (Standard / DataZoneStandard / GlobalStandard)
    2. not deprecated for THAT deployment type (skus[].deprecationDate is in the future)
    3. your subscription has quota > 0 for it
  Read-only: it only calls 'az cognitiveservices model list' and 'usage list'. Requires 'az login'.

.EXAMPLE
  .\scripts\find_deployable_models.ps1
  .\scripts\find_deployable_models.ps1 -Regions swedencentral,francecentral
#>
param(
    [string[]]$Regions = @('swedencentral', 'francecentral', 'germanywestcentral'),
    [string]$Include = 'gpt|embedding',
    [string]$Exclude = 'image|audio|realtime|transcribe|tts|whisper|codex|sora|live|chat-latest'
)

$now = Get-Date
$wanted = 'Standard', 'DataZoneStandard', 'GlobalStandard'
$rows = New-Object System.Collections.Generic.List[object]

foreach ($region in $Regions) {
    Write-Host "Checking $region ..."

    # Parentheses force PowerShell 5.1 to enumerate the parsed JSON array item by item.
    $usage = @{}
    foreach ($u in (az cognitiveservices usage list --location $region -o json | ConvertFrom-Json)) {
        $usage[$u.name.value] = [double]$u.limit
    }

    $models = (az cognitiveservices model list --location $region -o json | ConvertFrom-Json) |
        Where-Object { $_.kind -eq 'OpenAI' -and $_.model.name -match $Include -and $_.model.name -notmatch $Exclude }

    foreach ($m in $models) {
        foreach ($sku in $m.model.skus) {
            if ($wanted -notcontains $sku.name) { continue }
            if ($sku.usageName -match 'finetune') { continue }               # fine-tuned model quota, not base inference

            $deprecates = $null
            if ($sku.deprecationDate) { $deprecates = [datetime]$sku.deprecationDate }
            if ($deprecates -and $deprecates -lt $now) { continue }          # gate 2

            $quota = $usage[$sku.usageName]
            if (-not $quota -or $quota -le 0) { continue }                   # gate 3

            $rows.Add([pscustomobject]@{
                Region       = $region
                Model        = $m.model.name
                Version      = $m.model.version
                Type         = $sku.name
                Quota        = $quota
                DeprecatesOn = $(if ($deprecates) { $deprecates.ToString('yyyy-MM-dd') } else { 'none listed' })
            })
        }
    }
}

if ($rows.Count -eq 0) {
    Write-Host 'No deployable chat or embedding models found with quota > 0 in these regions.'
} else {
    $rows | Sort-Object Region, Model, Version, Type | Format-Table -AutoSize
}
