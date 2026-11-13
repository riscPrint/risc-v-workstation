"""Build and run the reusable independent-master pyuvm composition bench."""
import json
import hashlib
from pathlib import Path
from rvw.common.proc import run_group
from rvw.uvm.composed import generate


def run(source, out, classpath, *, build_args=(), idle_inputs=None, timeout=120, expected_map=None):
    out = Path(out).resolve()
    root = Path(__file__).resolve().parents[4]
    report = generate(source,out,out/'rtl/VerificationSoc.v',expected_map=expected_map)
    command = [str(root/'scripts/with-lock.sh'),'sbt-soc','nice','-n','10','sbt',*build_args,
               'set Compile / unmanagedSources += file("'+report['scala']+'")','compile']
    with (out/'compile.log').open('w') as log:
        built = run_group(command,cwd=root/'SpinalSoc',stdout=log,stderr=log,timeout=timeout)
    if built.returncode or built.timed_out:
        return dict(status='inconclusive',generated=True,ran=False,reason='Test-master build failed; see compile.log.')
    with (out/'elaborate.log').open('w') as log:
        rtl = run_group(['nice','-n','10','java','-cp',classpath,'verification.VerificationGenerate',str(out/'rtl')],
                        cwd=out,stdout=log,stderr=log,timeout=timeout)
    if rtl.returncode or rtl.timed_out:
        return dict(status='inconclusive',generated=True,ran=False,reason='Test-master elaboration failed; see elaborate.log.')
    # Spinal emits relative memory filenames. Bind the exact generated images
    # before the cocotb worker changes its working directory.
    images = {}
    rtl_path = out/'rtl/VerificationSoc.v'
    text = rtl_path.read_text()
    for image in sorted((out/'rtl').glob('*.bin')):
        images[image.name] = hashlib.sha256(image.read_bytes()).hexdigest()
        text = text.replace('"'+image.name+'"','"'+str(image)+'"')
    rtl_path.write_text(text)
    path = out/'bindings.json'
    bindings = json.loads(path.read_text())
    bindings['idle_inputs'] = idle_inputs or {}
    path.write_text(json.dumps(bindings,indent=2)+'\n')
    from rvw.sim.cocotb import run as simulate
    simulation = simulate(out/'bench.json',out/'simulation',seed=31,timeout=timeout)
    checks_path = out/'checks.json'
    checks = json.loads(checks_path.read_text()) if checks_path.is_file() else {}
    # Cocotb result rows and independent positive checker counts are required.
    cases = simulation.get('tests',[])
    passed = bool(cases) and all(t['status']=='pass' for t in cases)
    status = 'pass' if passed and checks.get('checks',0)>0 else 'inconclusive'
    if any(t['status']=='fail' for t in cases):
        status = 'fail'
    return dict(status=status,generated=True,ran=True,checks=checks,simulation=simulation,
                scope=report['scope'],memory_images=images)
