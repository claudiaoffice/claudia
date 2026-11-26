// Each condition of a rule says, in words a person reads, why an entry does not fit (a notice, the line of an empty
// menu, D1603, D1604) and when it does (Preferences ▸ Shortcuts, D1604). Their style is the owner's (2026-11-25, Q2).
import { describe, expect, it } from "vitest";
import { CONDITIONS } from "~/lib/fits/conditions";

const t = (msgid: string, vars: Record<string, string | number> = {}) =>
  msgid.replace(/\{(\w+)\}/g, (_all, name: string) => String(vars[name]));

describe("the words of the conditions", () => {
  it.each([...CONDITIONS.values()].map((c) => [c.words, c] as const))(
    "%s says why in a sentence and when in a phrase",
    (_words, condition) => {
      expect(condition.why(t)).toMatch(/^[A-Z].*\.$/);
      expect(condition.plain(t)).toMatch(/^[a-z][^.]*[a-z]$/i);
      expect(condition.plain(t)).not.toMatch(/[{}]/);
    },
  );

  it("names the tool a server lacks, in both", () => {
    const latex = CONDITIONS.get("server: has the tool for LaTeX")!;
    expect(latex.why(t)).toBe("This server has no LaTeX set up.");
    expect(latex.plain(t)).toBe("when the server has LaTeX");
  });

  it('says each "when" once: no two conditions read the same in the Shortcuts list', () => {
    const plain = [...CONDITIONS.values()].map((c) => c.plain(t));
    expect(new Set(plain).size).toBe(plain.length);
  });
});
