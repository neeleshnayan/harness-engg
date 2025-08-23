// This file configures the initialization of Sentry on the client.
// The added config here will be used whenever a users loads a page in their browser.
// https://docs.sentry.io/platforms/javascript/guides/nextjs/

import { initSentry } from './lib/sentry';

// Initialize Sentry with custom configuration
initSentry();

export const onRouterTransitionStart = (window as any).Sentry?.captureRouterTransitionStart;