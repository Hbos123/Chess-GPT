/**
 * Test setup file
 * Configures Jest and testing environment
 */

import '@testing-library/jest-dom';

// Mock window if needed
if (typeof window === 'undefined') {
  global.window = {} as any;
}

