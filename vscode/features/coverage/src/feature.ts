import {resultsFeature} from '../../../src/results/feature';
import {activateOverlays} from './overlays';
const base=resultsFeature('coverage','Coverage');
export default {...base,activate(context:Parameters<typeof base.activate>[0]){activateOverlays(context);return base.activate(context);}};
