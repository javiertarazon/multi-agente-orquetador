Set-Location 'd:\datos jt7\proyectos\agentes_autonomos\trade bot\multi agente orquestado'
& '.\.venv\Scripts\Activate.ps1'
$env:MAOQ_KILO_BIN = 'C:\Users\javier\AppData\Roaming\npm\kilo.cmd'
$env:MAOQ_CLINE_BIN = 'C:\Users\javier\AppData\Roaming\npm\cline.cmd'
$env:MAOQ_HERMES_BIN = 'C:\Users\javier\.local\bin\hermes.CMD'
while ($true) {
  Get-Date -Format o | Out-File 'worker.log' -Append
  maoq worker --once *>> 'worker.log'
  Start-Sleep -Seconds 2
}
