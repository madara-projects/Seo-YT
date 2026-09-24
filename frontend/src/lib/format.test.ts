import { describe, expect, it } from "vitest";
import {
  engagementRate,
  formatBytes,
  formatCompact,
  formatMinutes,
  formatSeconds,
  formatSignedPercent,
  formatUptime,
  initialOf,
  percentChange,
  relativeTime,
  toFiniteNumber,
} from "./format";

describe("toFiniteNumber", () => {
  it("keeps a measured zero and rejects absent or non-numeric values", () => {
    expect(toFiniteNumber(0)).toBe(0);
    expect(toFiniteNumber("12")).toBe(12);
    for (const value of [null, undefined, "", "abc", Number.NaN, Infinity, true]) {
      expect(toFiniteNumber(value)).toBeNull();
    }
  });
});

describe("formatCompact", () => {
  it("stays exact below ten thousand and compacts above", () => {
    expect(formatCompact(912)).toBe("912");
    expect(formatCompact(9_999)).toBe("9,999");
    expect(formatCompact(18_432)).toBe("18.4K");
    expect(formatCompact(4_829_331)).toBe("4.8M");
  });

  it("says Unavailable instead of inventing a zero", () => {
    expect(formatCompact(undefined)).toBe("Unavailable");
    expect(formatCompact(0)).toBe("0");
  });
});

describe("percentChange", () => {
  it("computes change against the earlier window", () => {
    expect(percentChange(120, 100)).toBeCloseTo(20);
    expect(percentChange(80, 100)).toBeCloseTo(-20);
  });

  it("refuses a comparison it cannot make honestly", () => {
    expect(percentChange(50, 0)).toBeNull();
    expect(percentChange(50, undefined)).toBeNull();
    expect(percentChange(undefined, 50)).toBeNull();
  });
});

describe("formatSignedPercent", () => {
  it("signs the value with a true minus", () => {
    expect(formatSignedPercent(21.99)).toBe("+22.0%");
    expect(formatSignedPercent(-10.53)).toBe("−10.5%");
    expect(formatSignedPercent(0.01)).toBe("0.0%");
  });
});

describe("durations", () => {
  it("formats view duration in seconds as clock time", () => {
    expect(formatSeconds(17)).toBe("0:17");
    expect(formatSeconds(205)).toBe("3:25");
    expect(formatSeconds(3725)).toBe("1:02:05");
    expect(formatSeconds(null)).toBe("Unavailable");
  });

  it("formats watch time from minutes", () => {
    expect(formatMinutes(45)).toBe("45 mins");
    expect(formatMinutes(51_230)).toBe("853.8 hrs");
    expect(formatMinutes(0)).toBe("0 mins");
    expect(formatMinutes(undefined)).toBe("Unavailable");
  });

  it("formats uptime by its largest units", () => {
    expect(formatUptime(42)).toBe("42 s");
    expect(formatUptime(11_520)).toBe("3 h 12 min");
    expect(formatUptime(200_000)).toBe("2 d 7 h");
  });
});

describe("formatBytes", () => {
  it("uses binary units", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(839_680)).toBe("820 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5 MB");
    expect(formatBytes(null)).toBe("Unavailable");
  });
});

describe("relativeTime", () => {
  const now = Date.parse("2026-09-24T12:00:00Z");

  it("describes past and future moments", () => {
    expect(relativeTime("2026-09-24T11:59:40Z", now)).toBe("just now");
    expect(relativeTime("2026-09-24T11:48:00Z", now)).toBe("12 min ago");
    expect(relativeTime("2026-09-24T09:00:00Z", now)).toBe("3 h ago");
    expect(relativeTime("2026-09-21T12:00:00Z", now)).toBe("3 d ago");
    expect(relativeTime("2026-09-24T18:00:00Z", now)).toBe("in 6 h");
  });

  it("says Unavailable for a missing or broken stamp", () => {
    expect(relativeTime(null, now)).toBe("Unavailable");
    expect(relativeTime("not a date", now)).toBe("Unavailable");
  });
});

describe("engagementRate", () => {
  it("is likes plus comments per hundred views", () => {
    expect(engagementRate(90, 10, 1000)).toBeCloseTo(10);
  });

  it("is unavailable without views", () => {
    expect(engagementRate(5, 1, 0)).toBeNull();
    expect(engagementRate(5, 1, undefined)).toBeNull();
  });
});

describe("initialOf", () => {
  it("returns an upper-case first character, tolerating empty names", () => {
    expect(initialOf("studio fixture")).toBe("S");
    expect(initialOf("  ")).toBe("?");
    expect(initialOf(undefined)).toBe("?");
  });
});
