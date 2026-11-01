import json
m=json.load(open('/opt/agentos/config/agents/reporter.json'))
m['identity_token']=m['identity_token'][:24]+'...[truncated]'
print(json.dumps(m, indent=2))
