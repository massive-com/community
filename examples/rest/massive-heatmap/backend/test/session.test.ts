import { describe, it, expect } from "vitest";
import { sessionPhase } from "../src/session.js";

const et = (h: number, m = 0) => Date.parse(`2026-06-23T${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}:00-04:00`);

describe("sessionPhase", () => {
  it("crypto is always open24", () => { expect(sessionPhase("crypto", et(3, 0))).toBe("open24"); });
  it("stocks pre-market at 05:00 ET", () => { expect(sessionPhase("stocks", et(5, 0))).toBe("premarket"); });
  it("stocks regular at 10:00 ET", () => { expect(sessionPhase("stocks", et(10, 0))).toBe("regular"); });
  it("stocks after-hours at 17:00 ET", () => { expect(sessionPhase("stocks", et(17, 0))).toBe("afterhours"); });
  it("stocks closed at 22:00 ET", () => { expect(sessionPhase("stocks", et(22, 0))).toBe("closed"); });
  it("stocks closed on weekend", () => { const sunday = Date.parse("2026-06-21T10:00:00-04:00"); expect(sessionPhase("stocks", sunday)).toBe("closed"); });
});
