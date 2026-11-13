import hashlib
import json
from pathlib import Path
import sys
source,out=map(Path,sys.argv[1:])
data=json.loads(source.read_text())
keys=['program','variant','measured_delta','predicted_delta','sign_match','absolute_error_pp','relative_error',
      'wrong_delta','status','rtl_base_ipc','rtl_variant_ipc','hashes','base_hashes']
rows=[]
for r in data['rows']:
 row={k:r[k] for k in keys}
 row.update(model_base_ipc=r['model_base']['ipc'],model_variant_ipc=r['model_variant']['ipc'],
            model_base_cycles=r['model_base']['cycles'],model_variant_cycles=r['model_variant']['cycles'])
 rows.append(row)
report=dict(schema='rvw.nax-delta-table/1',source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            calibration_sha256=data['calibration_sha256'],config_sha256=data['config_sha256'],
            engine_sha256=data['rows'][0]['model_base']['engine_sha256'],variants=data['variants'],
            summary=data['summary'],rows=rows,limits=data['limits'])
out.write_text(json.dumps(report,indent=2)+'\n')
