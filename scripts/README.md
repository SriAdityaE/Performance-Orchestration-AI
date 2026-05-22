# Script Shortcuts

## VM Runner

Run continuously:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Start-VmRunner.ps1 \
  -ProjectRoot "L:\MCP\AI\Performance-Orchestration-AI\SDD-project" \
  -PerfSharedRoot "L:\MCP\AI\Performance-Orchestration-AI\SDD-project\shared-root" \
  -JMeterHome "L:\apache-jmeter-5.5_New\apache-jmeter-5.5" \
  -NotificationChannel slack \
  -SlackWebhookUrl "https://hooks.slack.com/services/REPLACE/ME"
```

Run once:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Start-VmRunner.ps1 \
  -ProjectRoot "L:\MCP\AI\Performance-Orchestration-AI\SDD-project" \
  -PerfSharedRoot "L:\MCP\AI\Performance-Orchestration-AI\SDD-project\shared-root" \
  -JMeterHome "L:\apache-jmeter-5.5_New\apache-jmeter-5.5" \
  -NotificationChannel slack \
  -SlackWebhookUrl "https://hooks.slack.com/services/REPLACE/ME" \
  -Once
```

## Local Submit

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\Start-LocalSubmit.ps1 \
  -ProjectRoot "C:\Users\erraguntlaaditya\OneDrive - Nagarro\Documents\Practice\MCPServer\Performance-Orchestration-AI\SDD-project" \
  -PerfSharedRoot "C:\Users\erraguntlaaditya\OneDrive - Nagarro\Documents\Practice\MCPServer\Performance-Orchestration-AI\SDD-project\shared-root" \
  -RequestFile "request.json" \
  -NotificationChannel terminal
```

## Notes

- Both sides must point to the same physical shared-root storage.
- The local submit script sets `JMETER_HOME` to project root by default for local validation.
- Use `terminal` channel locally and `slack` on VM by default.
