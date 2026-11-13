const { runTests, downloadAndUnzipVSCode } = require('@vscode/test-electron');
const fs = require('node:fs/promises');
const path = require('node:path');
const net = require('node:net');

// A small Scala source and a hand-written design with stable source locations, used alongside
// any state machines in the generated BOOM data. The designs are found by the default `designFiles` globs
// (`**/blocks/*.json.gz`, `**/*.spinalblocks.json`).
const FSM_SOURCE = `package demo

import spinal.core._
import spinal.lib._
import spinal.lib.fsm._

object Mode extends SpinalEnum {
  val SLOW, FAST = newElement()
}

class FsmDemo extends Component {
  val io = new Bundle {
    val start = in Bool()
    val rsp = in Bool()
    val done = out Bool()
  }

  val ctrl = new StateMachine {
    val IDLE = new State with EntryPoint
    val FETCH = new State
    val WAIT_RSP = new State
    val DONE = new State

    IDLE.whenIsActive { when(io.start) { goto(FETCH) } }
    FETCH.whenIsActive { goto(WAIT_RSP) }
    WAIT_RSP.whenIsActive { when(io.rsp) { goto(DONE) } } // response back
    DONE.whenIsActive { goto(IDLE) }
  }

  val mode = Reg(Mode()) init(Mode.SLOW)
  when(io.start) { mode := Mode.FAST }

  io.done := ctrl.isActive(ctrl.DONE)
}
`;

function fsmDesign(file) {
  const lines = FSM_SOURCE.split('\n');
  const at = text => {
    const i = lines.findIndex(l => l.includes(text));
    if (i < 0) throw new Error(`fixture line not found: ${text}`);
    return { file, line: i + 1 };
  };
  const port = (name, dir, text) => ({ name, dir, width: 1, type: 'Bool', group: 'io', groups: ['io'], loc: at(text) });
  const signal = (name, width, type, reg, text) => ({ name, width, type, reg, loc: at(text) });
  const t = (from, to, condition, text, comment = null) => ({ from, to, condition, comment, loc: at(text) });
  return {
    format: 'spinalblocks', version: 1, top: 'FsmDemo', generated: 'integration fixture',
    modules: {
      FsmDemo: {
        name: 'FsmDemo', className: 'demo.FsmDemo', loc: at('class FsmDemo'), instanceCount: 1, blackbox: false,
        ports: [port('io_start', 'in', 'val start'), port('io_rsp', 'in', 'val rsp'), port('io_done', 'out', 'val done')],
        instances: [],
        nodes: [
          { id: 'area:ctrl', name: 'ctrl', kind: 'area', parent: null, compound: true, className: null, loc: at('val ctrl ='),
            signals: [], regCount: 1, combCount: 0 },
          { id: 'reg:ctrl_stateReg', name: 'ctrl_stateReg', kind: 'reg', parent: 'area:ctrl', compound: false, className: null,
            loc: at('val ctrl ='), signals: [signal('ctrl_stateReg', 2, 'ctrl_enumDef', true, 'val ctrl =')], regCount: 1, combCount: 0 },
          { id: 'reg:mode', name: 'mode', kind: 'reg', parent: null, compound: false, className: null, loc: at('val mode ='),
            signals: [signal('mode', 1, 'Mode', true, 'val mode =')], regCount: 1, combCount: 0 },
          { id: 'sig:io_done', name: 'io_done', kind: 'comb', parent: null, compound: false, className: null, loc: at('io.done :='),
            signals: [signal('io_done', 1, 'Bool', false, 'io.done :=')], regCount: 0, combCount: 1 },
        ],
        nets: [
          { id: 'n0', name: 'io_start', width: 1, via: [], control: false, clock: false, from: { kind: 'port', port: 'io_start' },
            to: [{ kind: 'node', id: 'reg:ctrl_stateReg' }, { kind: 'node', id: 'reg:mode' }] },
          { id: 'n1', name: 'io_rsp', width: 1, via: [], control: false, clock: false, from: { kind: 'port', port: 'io_rsp' },
            to: [{ kind: 'node', id: 'reg:ctrl_stateReg' }] },
          { id: 'n2', name: 'ctrl_stateReg', width: 2, via: [], control: false, clock: false, from: { kind: 'node', id: 'reg:ctrl_stateReg' },
            to: [{ kind: 'node', id: 'sig:io_done' }] },
          { id: 'n3', name: 'io_done', width: 1, via: [], control: false, clock: false, from: { kind: 'node', id: 'sig:io_done' },
            to: [{ kind: 'port', port: 'io_done' }] },
        ],
        fsms: [
          { id: 'fsm:ctrl', name: 'ctrl', node: 'area:ctrl', register: 'ctrl_stateReg', kind: 'statemachine', loc: at('val ctrl ='),
            states: ['IDLE', 'FETCH', 'WAIT_RSP', 'DONE'].map(name => ({ name, loc: at(`val ${name} =`) })),
            reset: 'IDLE',
            transitions: [
              t('IDLE', 'FETCH', 'io.start', 'IDLE.whenIsActive'),
              t('FETCH', 'WAIT_RSP', null, 'FETCH.whenIsActive'),
              t('WAIT_RSP', 'DONE', 'io.rsp', 'WAIT_RSP.whenIsActive', 'response back'),
              t('DONE', 'IDLE', null, 'DONE.whenIsActive'),
            ] },
          { id: 'fsm:mode', name: 'mode', node: 'reg:mode', register: 'mode', kind: 'enum', loc: at('val mode ='),
            states: [{ name: 'SLOW', loc: at('val SLOW') }, { name: 'FAST', loc: at('val SLOW') }],
            reset: 'SLOW',
            transitions: [t(null, 'FAST', 'io.start', 'mode := Mode.FAST')] },
        ],
      },
    },
  };
}

async function main() {
  // The extension root (vscode/), three levels up from features/spinalblocks/test.
  const root = path.resolve(__dirname, '../../..');
  const workspace = path.join(root, '.vscode-test', 'workspace');
  // Rebuilt each run, so stale fixtures never satisfy design discovery.
  await fs.rm(workspace, {recursive:true, force:true});
  await fs.mkdir(path.join(workspace, 'blocks'), {recursive:true});
  await fs.mkdir(path.join(workspace, 'fsm'), {recursive:true});
  const fixture = path.join(workspace, 'blocks', 'boom-small.json.gz');
  await fs.copyFile(process.env.SPINALBLOCKS_TEST_DESIGN || path.resolve(root, '../../spinal-boom/blocks/boom-small.json.gz'), fixture);
  const fsmSource = path.join(workspace, 'fsm', 'FsmDemo.scala');
  const fsmFixture = path.join(workspace, 'fsm', 'fsm-demo.spinalblocks.json');
  await fs.writeFile(fsmSource, FSM_SOURCE);
  await fs.writeFile(fsmFixture, JSON.stringify(fsmDesign(fsmSource), null, 1));
  const server = net.createServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  await new Promise(resolve => server.close(resolve));
  const runDir = path.join(root,'.vscode-test',Date.now().toString(36));
  await fs.mkdir(path.join(runDir,'u/User'), {recursive:true});
  await fs.writeFile(path.join(runDir,'u/User/settings.json'), JSON.stringify({'workbench.colorTheme':'Default Dark Modern','chat.disableAIFeatures':true,'git.openRepositoryInParentFolders':'never','workbench.startupEditor':'none'}));
  const executable = process.env.VSCODE_EXECUTABLE || await downloadAndUnzipVSCode({version:'stable', cachePath:path.join(root,'.vscode-test')});
  // T3 may itself run inside Electron in Node mode; the test app must start as a GUI.
  delete process.env.ELECTRON_RUN_AS_NODE;
  await runTests({
    vscodeExecutablePath:executable, extensionDevelopmentPath:root, extensionTestsPath:path.join(root,'dist/spinalblocks/test/integration.js'),
    extensionTestsEnv:{SPINALBLOCKS_TEST_DESIGN:fixture, SPINALBLOCKS_TEST_FSM_DESIGN:fsmFixture, SPINALBLOCKS_TEST_FSM_SOURCE:fsmSource, SPINALBLOCKS_CDP_PORT:String(port)},
    launchArgs:[workspace,'--disable-gpu','--disable-extensions','--disable-workspace-trust','--skip-welcome','--skip-release-notes',`--remote-debugging-port=${port}`,`--user-data-dir=${path.join(runDir,'u')}`,`--extensions-dir=${path.join(runDir,'e')}`],
  });
}
main().catch(error => { console.error(error); process.exitCode = 1; });
