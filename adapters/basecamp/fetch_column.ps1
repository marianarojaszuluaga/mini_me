# Basecamp API - Fetch Cards from Column 7484926006
# This script handles OAuth authentication and retrieves cards from the specified column

param(
    [string]$AuthCode = "",
    [string]$AccessToken = ""
)

# Configuration
$ACCOUNT_ID = "5172885"
 $BUCKET_ID = "44382327"
$COLUMN_ID = "9175270358"
$CLIENT_ID = "c91ea9e7bc5363ac457e0520a8a662fff00d76e8"
$CLIENT_SECRET = "6f92f67545ae0654e0bbb7c8c13de1aa800eb64d"  # ⚠️  Replace with your actual secret
$REDIRECT_URI = "http://localhost"

# Function to get authorization code
function Get-AuthCode {
    $authUrl = "https://launchpad.37signals.com/authorization/new?type=web_server&client_id=$CLIENT_ID&redirect_uri=$REDIRECT_URI&response_type=code"
    Write-Host "Opening authorization URL in browser..."
    Write-Host $authUrl
    Start-Process $authUrl
    
    Write-Host ""
    Write-Host "After authorizing, copy the code from the redirect URL and paste it below:"
    $code = Read-Host "Enter the authorization code"
    return $code
}

# Function to exchange code for access token
function Get-AccessToken {
    param([string]$Code)
    
    Write-Host "Exchanging code for access token..."
    
    $body = @{
        type          = "web_server"
        client_id     = $CLIENT_ID
        client_secret = $CLIENT_SECRET
        redirect_uri  = $REDIRECT_URI
        code          = $Code
    } | ConvertTo-Json
    
    try {
        $response = Invoke-WebRequest `
            -Uri "https://launchpad.37signals.com/authorization/token" `
            -Method POST `
            -ContentType "application/json" `
            -Body $body `
            -ErrorAction Stop
        
        $tokenData = $response.Content | ConvertFrom-Json
        return $tokenData.access_token
    }
    catch {
        Write-Host "Error exchanging code for token: $_"
        return $null
    }
}

# Function to fetch cards from column
function Get-ColumnCards {
    param([string]$Token)
    
    Write-Host "Fetching cards from column $COLUMN_ID..."
    
    $headers = @{
        "Authorization" = "Bearer $Token"
    }
    
    $apiUrl = "https://3.basecampapi.com/$ACCOUNT_ID/buckets/$BUCKET_ID/card_tables/lists/$COLUMN_ID/cards.json"
    
    try {
        $response = Invoke-WebRequest `
            -Uri $apiUrl `
            -Headers $headers `
            -Method GET `
            -ErrorAction Stop
        
        $cards = $response.Content | ConvertFrom-Json
        return $cards
    }
    catch {
        Write-Host "Error fetching cards: $_"
        return $null
    }
}

# Function to display cards
function Show-Cards {
    param($Cards)
    
    if ($null -eq $Cards) {
        Write-Host "No cards found."
        return
    }
    
    Write-Host ""
    Write-Host "=== Cards in Column $COLUMN_ID ==="
    Write-Host ""
    
    foreach ($card in $Cards) {
        Write-Host "Card ID: $($card.id)"
        Write-Host "Title: $($card.title)"
        Write-Host "Description: $($card.description)"
        Write-Host "URL: $($card.url)"
        Write-Host "---"
    }
    
    Write-Host ""
    Write-Host "Total cards: $($Cards.Count)"
}

# Main execution
Write-Host "Basecamp API - Column Card Fetcher"
Write-Host "===================================="
Write-Host ""

# Get token
if ($AccessToken) {
    Write-Host "Using provided access token..."
    $token = $AccessToken
} elseif ($AuthCode) {
    $token = Get-AccessToken -Code $AuthCode
} else {
    $code = Get-AuthCode
    if ($code) {
        $token = Get-AccessToken -Code $code
    } else {
        Write-Host "No authorization code provided. Exiting."
        exit 1
    }
}

if ($null -eq $token) {
    Write-Host "Failed to obtain access token. Exiting."
    exit 1
}

Write-Host "Access token obtained successfully!"
Write-Host ""

# Fetch and display cards
$cards = Get-ColumnCards -Token $token
Show-Cards -Cards $cards

# Save to JSON file
if ($cards) {
    $timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
    $outputFile = "column_cards_$timestamp.json"
    $cards | ConvertTo-Json -Depth 10 | Out-File -FilePath $outputFile -Encoding UTF8
    Write-Host "Cards saved to: $outputFile"

    # Save format for G-magine
    $gmagineFile = "gmagine_batch_input_$timestamp.md"
    "# G-magine Batch Input`nGenerated: $timestamp`n`n" | Out-File -FilePath $gmagineFile -Encoding UTF8
    foreach ($card in $cards) {
        # Extract Title and Description (Notes), basic HTML cleaning for readability
        "## INPUT FROM CARD: $($card.title)`n> $($card.description -replace '<br\s*/?>',"`n" -replace '</p>',"`n" -replace '<[^>]+>','')`n`n---`n" | Out-File -FilePath $gmagineFile -Append -Encoding UTF8
    }
    Write-Host "G-magine input file generated: $gmagineFile"
}
