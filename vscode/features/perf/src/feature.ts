import {resultsFeature} from '../../../src/results/feature';
import {activateWindow} from './window';
const base=resultsFeature('perf','Performance');
export default {...base,activate(context:Parameters<typeof base.activate>[0]){activateWindow(context);return base.activate(context);}};
