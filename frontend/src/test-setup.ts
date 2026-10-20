import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'
// Each test starts a new user journey; history now persists navigation state.
beforeEach(() => window.history.replaceState(null, '', '/'))
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals() })
Object.defineProperty(window, 'matchMedia', { value: () => ({ matches: false, addEventListener() {}, removeEventListener() {} }) })
