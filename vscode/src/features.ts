import cosim from '../features/cosim/src/feature';
import project from '../features/project/src/feature';
import navigation from '../features/navigation/src/feature';
import lsp from '../features/lsp/src/feature';
import type { Feature } from './api';
import spinalblocks from '../features/spinalblocks/src/feature';

import regress from '../features/regress/src/feature';
import coverage from '../features/coverage/src/feature';
import debug from '../features/debug/src/feature';
import perf from '../features/perf/src/feature';
import wave from '../features/wave/src/feature';
import lint from '../features/lint/src/feature';

// Every feature under features/ must be listed here. `npm run manifest:check` fails otherwise.
export const features: Feature[] = [
  navigation,
  project,
  cosim,
  spinalblocks,
  lsp,
  regress,
  coverage,
  perf,
  debug,
  wave,
  lint,
];
