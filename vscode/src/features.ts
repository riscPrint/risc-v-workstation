import type { Feature } from './api';
import spinalblocks from '../features/spinalblocks/src/feature';

import regress from '../features/regress/src/feature';
import coverage from '../features/coverage/src/feature';
import perf from '../features/perf/src/feature';

// Every feature under features/ must be listed here. `npm run manifest:check` fails otherwise.
export const features: Feature[] = [
  spinalblocks,
  regress,
  coverage,
  perf,
];
