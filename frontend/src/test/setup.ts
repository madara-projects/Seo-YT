import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => cleanup());

// Lazy routes pull in sizeable chart modules. Give async DOM queries enough
// room on loaded CI machines without weakening individual assertions.
configure({ asyncUtilTimeout: 5_000 });

// jsdom implements neither of these, and Radix/the shell both need them.
if (!window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    addListener: vi.fn(),
    removeListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

if (!window.ResizeObserver) {
  window.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}

// jsdom throws "Not implemented" for scrollTo, which the shell calls on every
// navigation. Stubbing it keeps real failures visible in the output.
window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
