import { describe, expect, it } from "vitest";
import { formatHours } from "../time-format";

describe("formatHours", () => {
  it("handles positive hours correctly", () => {
    expect(formatHours(0.1)).toBe("6m");
    expect(formatHours(2.4)).toBe("2.4h");
    expect(formatHours(39.4)).toBe("1.6d");
  });

  it("handles negative hours", () => {
    expect(formatHours(-1)).toBe("-1.0h");
    expect(formatHours(-0.5)).toBe("-30m");
    expect(formatHours(-2.4)).toBe("-2.4h");
    expect(formatHours(-50)).toBe("-2.1d");
  });

  it("handles null/undefined/NaN values", () => {
    expect(formatHours(null)).toBe("-");
    expect(formatHours(undefined)).toBe("-");
    expect(formatHours(Number.NaN)).toBe("-");
  });

  it("handles zero", () => {
    expect(formatHours(0)).toBe("0m");
  });
});
