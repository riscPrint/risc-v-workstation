import type { Feature } from './api';
import spinalblocks from '../features/spinalblocks/src/feature';

// Every feature under features/ must be listed here. `npm run manifest:check` fails otherwise.
export const features: Feature[] = [
  spinalblocks,
];
