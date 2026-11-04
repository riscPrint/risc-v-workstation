// Shared web UI test. Adds a synthetic block to a captured VexRiscv fixture.
import {chromium} from 'playwright-core';
import {spawn,spawnSync} from 'node:child_process';
import {mkdtempSync,rmSync,readdirSync} from 'node:fs';
import {tmpdir,homedir} from 'node:os';
import {resolve,join} from 'node:path';
import {createInterface} from 'node:readline';
import assert from 'node:assert/strict';
const root=resolve('..'),temp=mkdtempSync(join(tmpdir(),'rvw-debug-browser-'));
const python=join(root,'rvw/.venv/bin/python'),env={...process.env,PYTHONPATH:join(root,'rvw/src')};
const setup=String.raw`
import sqlite3,gzip,json,hashlib,sys
from pathlib import Path
from rvw.wave.index import build
root,temp=map(Path,sys.argv[1:])
source=temp/'Fixture.scala'
source.write_text('val execute_PC = Reg(UInt(32 bits))\n')
with sqlite3.connect(temp/'vex.db') as c:
 c.executescript(gzip.decompress((root/'vscode/features/debug/test/fixtures/vex.sql.gz').read_bytes()).decode())
 c.execute('INSERT INTO files VALUES(9999,?)',(str(source),))
 c.execute("UPDATE signals SET file_id=9999,line=1 WHERE path='execute_PC'")
 c.execute('INSERT INTO input_files VALUES(?,?,?,?,?)',(str(source),str(source),hashlib.sha256(source.read_bytes()).hexdigest(),source.stat().st_size,'{}'))
 loc=dict(file=str(source),line=1)
 blocks=dict(format='spinalblocks',version=1,top='VexTop',modules=dict(VexTop=dict(name='VexTop',className='Fixture',loc=loc,instanceCount=1,blackbox=False,ports=[],instances=[],nodes=[dict(id='sig:execute_PC',name='execute_PC',kind='reg',parent=None,compound=False,className=None,loc=loc,signals=[dict(name='execute_PC',width=32,type='UInt',reg=True,loc=loc)],regCount=1,combCount=0)],nets=[],fsms=[])))
 data=json.dumps(blocks).encode()
 c.execute('INSERT INTO artifacts VALUES(?,?,?,?,?)',('blocks.json','application/json','identity',len(data),data))
vcd=temp/'wave.vcd'
vcd.write_text('$timescale 1ns $end\n$scope module TOP $end\n$scope module VexTop $end\n$var wire 32 ! execute_PC $end\n$upscope $end\n$upscope $end\n$enddefinitions $end\n#0\nb0 !\n#10\nb100 !\n')
build(str(vcd),str(temp/'wave.rvwi'))
`;
let server,browser;
try {
 const setupResult=spawnSync(python,['-c',setup,root,temp],{env,encoding:'utf8'});assert.equal(setupResult.status,0,setupResult.stderr);
 server=spawn(python,['-m','rvw.query.session','--db',join(temp,'vex.db'),'--wave',process.env.RVW_DEBUG_BENCH_INDEX ?? join(temp,'wave.rvwi'),'--web',join(root,'vscode/dist/debug')],{env});
 const url=await new Promise((resolve,reject)=>{createInterface({input:server.stdout}).once('line',resolve);server.once('error',reject);server.once('exit',code=>reject(new Error(`server exited ${code}`)));});
 const cache=join(homedir(),'Library/Caches/ms-playwright');
 const rev=readdirSync(cache).filter(s=>s.startsWith('chromium-')).sort().at(-1);
 const executablePath=process.env.CHROMIUM ?? join(cache,rev,'chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing');
 browser=await chromium.launch({executablePath,headless:true});const page=await browser.newPage();
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const started=performance.now();
 await page.goto(String(url));await page.locator('#diagram .sb-box').waitFor();
 const openedMs=performance.now()-started;
 if(process.env.RVW_DEBUG_BENCH_INDEX) {
   await page.locator('#signal').fill('execute_PC');await page.locator('#time').fill('539999');
   const jumpStart=performance.now();await page.locator('#jump').click();
   await page.waitForFunction(()=>document.querySelector('#wave').textContent.includes('@ 539999 = 0x4'));
   const jumpMs=performance.now()-jumpStart;assert.deepEqual(errors,[]);
   console.log(JSON.stringify({scope:'headless Chromium; dense synthetic indexed wave; warm filesystem cache; synthetic single-block fixture',open_ms:openedMs,jump_ms:jumpMs,under_1s:openedMs<1000&&jumpMs<1000}));
 } else {
 await page.locator('#signal').fill('execute_PC');await page.locator('#jump').click();await page.locator('#wave svg').waitFor();
 assert.match(await page.locator('#source').innerText(),/execute_PC/);
 await page.locator('#wave button').filter({hasText:'10: 0x4'}).click();
 await page.waitForFunction(()=>document.querySelector('#time').value==='10' && document.querySelector('#wave').textContent.includes('@ 10 = 0x4'));
 await page.locator('#source button').first().click();await page.waitForFunction(()=>document.querySelector('#status').textContent.startsWith('resolved'));
 await page.locator('#diagram .sb-box').first().click();
 await page.waitForFunction(()=>document.querySelector('#status').textContent.startsWith('resolved'));
 await page.locator('#trace').click();await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('no pdg.json'));
 assert.deepEqual(errors,[]);
 console.log('PASS: block and wave SVG, source and wave links, missing trace metadata; 0 page errors');
 }
} finally {await browser?.close();server?.kill('SIGTERM');rmSync(temp,{recursive:true,force:true});}
