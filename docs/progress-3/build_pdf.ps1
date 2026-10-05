# สร้าง PDF จาก WTN-A12_Progress3_Report.html ด้วย Microsoft Edge (headless)
# แก้ชื่อกลุ่ม/สมาชิกในไฟล์ HTML ก่อน แล้วรัน:  powershell -ExecutionPolicy Bypass -File docs\progress-3\build_pdf.ps1
$dir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$html = Join-Path $dir "WTN-A12_Progress3_Report.html"
$pdf  = Join-Path $dir "WTN-A12_Progress3_Report.pdf"
$uri  = ([System.Uri]$html).AbsoluteUri
$edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
Start-Process -FilePath $edge -Wait -NoNewWindow -ArgumentList @(
  "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=15000",
  "--user-data-dir=$env:TEMP\edge-pdf-profile", "--print-to-pdf=`"$pdf`"", "`"$uri`""
)
Write-Host "เขียนไฟล์แล้ว: $pdf"
