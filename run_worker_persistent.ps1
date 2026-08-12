Set-Location 'd:\datos jt7\proyectos\agentes_autonomos\trade bot\multi agente orquestado'
& '.\.venv\Scripts\Activate.ps1'
while ($true) {
  Get-Date -Format o | Out-File 'worker.log' -Append
  maoq worker --once *>> 'worker.log'
  Start-Sleep -Seconds 2
}
