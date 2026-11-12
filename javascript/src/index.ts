export { NinetileClient, DEFAULT_BASE_URL } from './client';
export type { NinetileClientOptions } from './client';
export {
  NinetileError,
  AuthenticationError,
  InsufficientCredits,
  RateLimited,
  SolveFailed,
  SolveTimeout,
} from './errors';
export type { SolveResponse, SolveResult, SolveOptions, RecognizeOptions, RecognizeResult, GetSolveOptions } from './types';
