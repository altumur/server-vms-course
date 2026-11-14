#!/usr/bin/env python3
import base64, json
print(json.dumps({'exit_code':0,'stdout_b64':base64.b64encode(b'""').decode(),'stderr_b64':''}))
