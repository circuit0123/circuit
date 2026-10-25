// Stands in for "msw/browser" when Next bundles the server side of a page: that entry has no Node version, and the server never starts the mock worker.
export const setupWorker = () => { throw new Error("The mock worker only runs in the browser."); };
