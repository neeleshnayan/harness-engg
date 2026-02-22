/**
 * Circle Transaction States
 *
 * This file mirrors the Circle transaction states from:
 * Krypton_Web3/app/constants/circle_states.py
 *
 * Keep in sync with the backend when Circle adds new states.
 */

// All Circle transaction states (lowercase to match backend normalization)
export enum CircleTransactionState {
  CREATED = 'created',
  CANCELLED = 'cancelled',
  CONFIRMED = 'confirmed',
  COMPLETE = 'complete',
  DENIED = 'denied',
  FAILED = 'failed',
  INITIATED = 'initiated',
  CLEARED = 'cleared',
  QUEUED = 'queued',
  SENT = 'sent',
  STUCK = 'stuck',
  SUCCESS = 'success',
  SUBMITTED = 'submitted',
  UNKNOWN = 'unknown',
}

/**
 * Terminal states - transaction processing has ended (success or failure)
 * These states indicate no further status changes will occur.
 */
export const TERMINAL_STATES = new Set<string>([
  CircleTransactionState.CANCELLED,
  CircleTransactionState.CONFIRMED,
  CircleTransactionState.COMPLETE,
  CircleTransactionState.DENIED,
  CircleTransactionState.FAILED,
  CircleTransactionState.SUCCESS,
]);

/**
 * Success states - transaction completed successfully
 */
export const SUCCESS_STATES = new Set<string>([
  CircleTransactionState.CONFIRMED,
  CircleTransactionState.COMPLETE,
  CircleTransactionState.SUCCESS,
]);

/**
 * Error states - transaction failed or was rejected
 */
export const ERROR_STATES = new Set<string>([
  CircleTransactionState.FAILED,
  CircleTransactionState.DENIED,
  CircleTransactionState.CANCELLED,
]);

/**
 * Ongoing states - transaction is still being processed
 * These are non-terminal states where the transaction is in progress.
 */
export const ONGOING_STATES = new Set<string>([
  CircleTransactionState.CREATED,
  CircleTransactionState.INITIATED,
  CircleTransactionState.QUEUED,
  CircleTransactionState.SENT,
  CircleTransactionState.STUCK,
  CircleTransactionState.SUBMITTED,
  CircleTransactionState.UNKNOWN,
]);

export const PROGRESS_STEP_STATES = [
  // Step 0: Queued (in our local pending queue)
  ['local_queued'],

  // Step 1: Submitted (sent to Circle but pending confirmation)
  [
    CircleTransactionState.CREATED,
    CircleTransactionState.INITIATED,
    CircleTransactionState.QUEUED,
    CircleTransactionState.SENT,
    CircleTransactionState.STUCK,
    CircleTransactionState.SUBMITTED,
    CircleTransactionState.UNKNOWN,
  ],

  // Step 2: Confirmed, Complete, or Failed (Final visible state)
  [
    CircleTransactionState.CONFIRMED,
    CircleTransactionState.CLEARED,
    CircleTransactionState.COMPLETE,
    CircleTransactionState.SUCCESS,
    CircleTransactionState.FAILED,
    CircleTransactionState.DENIED,
    CircleTransactionState.CANCELLED,
  ],
];

/**
 * State category for UI display purposes
 */
export type StateCategory = 'ongoing' | 'success' | 'error' | 'terminal';

/**
 * Get the category of a transaction state for UI display.
 * Only these four categories should be shown in the UI to keep it minimal.
 *
 * @param state - The transaction state (case-insensitive)
 * @returns The state category
 */
export function getStateCategory(state: string): StateCategory {
  const normalizedState = state.toLowerCase();

  if (SUCCESS_STATES.has(normalizedState)) {
    return 'success';
  }

  if (ERROR_STATES.has(normalizedState)) {
    return 'error';
  }

  if (ONGOING_STATES.has(normalizedState) || normalizedState === 'local_queued') {
    return 'ongoing';
  }

  // Default to terminal for unknown states
  if (TERMINAL_STATES.has(normalizedState)) {
    return 'terminal';
  }

  // Unknown states default to ongoing (still processing)
  return 'ongoing';
}

/**
 * Check if a transaction is in a terminal state
 */
export function isTerminalState(state: string): boolean {
  return TERMINAL_STATES.has(state.toLowerCase());
}

/**
 * Check if a transaction is in a success state
 */
export function isSuccessState(state: string): boolean {
  return SUCCESS_STATES.has(state.toLowerCase());
}

/**
 * Check if a transaction is in an error state
 */
export function isErrorState(state: string): boolean {
  return ERROR_STATES.has(state.toLowerCase());
}

/**
 * Check if a transaction is in an ongoing state
 */
export function isOngoingState(state: string): boolean {
  return ONGOING_STATES.has(state.toLowerCase());
}

/**
 * Get a human-readable label for a state category
 */
export function getStateCategoryLabel(category: StateCategory): string {
  switch (category) {
    case 'success':
      return 'Complete';
    case 'error':
      return 'Failed';
    case 'ongoing':
      return 'Processing';
    case 'terminal':
      return 'Ended';
    default:
      return 'Unknown';
  }
}

/**
 * Get a human-readable label for a transaction state
 */
export function getStateLabel(state: string): string {
  const normalizedState = state.toLowerCase();

  switch (normalizedState) {
    case CircleTransactionState.CREATED:
      return 'Created';
    case CircleTransactionState.CANCELLED:
      return 'Cancelled';
    case CircleTransactionState.CONFIRMED:
      return 'Confirmed';
    case CircleTransactionState.COMPLETE:
      return 'Complete';
    case CircleTransactionState.DENIED:
      return 'Denied';
    case CircleTransactionState.FAILED:
      return 'Failed';
    case CircleTransactionState.INITIATED:
      return 'Initiated';
    case CircleTransactionState.CLEARED:
      return 'Cleared';
    case 'local_queued':
      return 'Queued';
    case CircleTransactionState.QUEUED:
      return 'Submitted'; // Circle's queued state = Submitted to Circle
    case CircleTransactionState.SENT:
      return 'Sent';
    case CircleTransactionState.STUCK:
      return 'Stuck';
    case CircleTransactionState.SUCCESS:
      return 'Success';
    case CircleTransactionState.SUBMITTED:
      return 'Submitted';
    case CircleTransactionState.UNKNOWN:
    default:
      return 'Processing';
  }
}

/**
 * Progress tracker steps for UI display
 * Steps: Queued (0) → Confirmed (1) → Complete/Failed (2)
 */
export type ProgressStep = 'queued' | 'confirmed' | 'complete';

/**
 * Get the progress step index (0-2) for a transaction state
 * Uses PROGRESS_STEP_STATES array to determine which step a state belongs to:
 * 0 = Queued (created, initiated, queued, sent, stuck, submitted, unknown)
 * 1 = Confirmed (confirmed, cleared)
 * 2 = Complete (complete, success, failed, denied, cancelled)
 */
export function getProgressStepIndex(state: string): number {
  const normalizedState = state.toLowerCase();

  // Find which step contains this state
  for (let stepIndex = 0; stepIndex < PROGRESS_STEP_STATES.length; stepIndex++) {
    const statesInStep = PROGRESS_STEP_STATES[stepIndex];
    if (statesInStep.includes(normalizedState as CircleTransactionState)) {
      return stepIndex;
    }
  }

  // Default to step 0 if state not found
  return 0;
}

/**
 * Get the progress step labels for the tracker
 */
export function getProgressStepLabel(step: number): string {
  switch (step) {
    case 0:
      return 'Queued';
    case 1:
      return 'Submitted';
    case 2:
      return 'Confirmed';
    default:
      return '';
  }
}

