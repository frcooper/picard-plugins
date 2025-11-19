param(
    [Parameter(Mandatory = $true)][string]$PluginName,
    [Parameter(Mandatory = $true)][string]$Version
)

if ($Version -notmatch '^[0-9]+\.[0-9]+\.[0-9]+$') {
    Write-Error "Version must be MAJOR.MINOR.PATCH"
    exit 1
}

if (-not (Test-Path $PluginName -PathType Container)) {
    Write-Error "Plugin directory '$PluginName' not found"
    exit 1
}

switch ($PluginName) {
    'featured-artists-standardizer' { $file = "$PluginName/featured-artists-standardizer.py" }
    'file-collision-protection' { $file = "$PluginName/file-collision-protection.py" }
    'asciifier' { $file = "$PluginName/asciifier.py" }
    default {
        Write-Error "Unknown plugin '$PluginName'"
        exit 1
    }
}

if (-not (Test-Path $file -PathType Leaf)) {
    Write-Error "Plugin file '$file' not found"
    exit 1
}

# Update PLUGIN_VERSION line (simple pattern, no capture groups)
(Get-Content $file) |
    ForEach-Object {
        if ($_ -match '^PLUGIN_VERSION\s*=') {
            "PLUGIN_VERSION = '$Version'"
        } else {
            $_
        }
    } | Set-Content $file

& git diff -- $file

Write-Host "About to commit and tag $PluginName at version $Version" -ForegroundColor Cyan

& git add $file
& git commit -m "chore($PluginName): release v$Version"

$tag = "$PluginName-v$Version"
& git tag $tag

& git push origin HEAD
& git push origin $tag
