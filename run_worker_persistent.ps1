Set-Location 'd:\datos jt7\proyectos\agentes_autonomos\trade bot\multi agente orquestado'
& '.\.venv\Scripts\Activate.ps1'
$env:MAOQ_KILO_BIN = 'C:\Users\javier\.vscode\extensions\kilocode.kilo-code-7.4.21-win32-x64\bin\kilo.exe'
$env:MAOQ_KILO_MODEL = 'kilo/cohere/north-mini-code:free'
$env:MAOQ_CLINE_BIN = 'C:\Users\javier\AppData\Roaming\npm\cline.cmd'
while ($true) {
  Get-Date -Format o | Out-File 'worker.log' -Append
  maoq worker --once *>> 'worker.log'
  Start-Sleep -Seconds 2
}
