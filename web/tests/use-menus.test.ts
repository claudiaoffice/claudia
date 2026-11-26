// A workspace's menus, live (D1644): what is true now (`windowFacts`), and the menus assembled from the definition
// with the workspace's handlers (`useMenus`), which says once on the console what the workspace does not do.
import { afterEach, describe, expect, it, vi } from "vitest";
import type { BaseState } from "~/lib/base-session";
import { DEFINITIONS } from "~/lib/menus.generated";
import { useMenus, windowFacts } from "~/lib/menus/use-menus";

function state(over: Record<string, unknown> = {}): BaseState {
  return {
    me: { role: "editor" },
    consent: null,
    containerTypes: [{ type: "latex" }],
    canUndo: true,
    canRedo: false,
    wayBack: null,
    ...over,
  } as unknown as BaseState;
}

describe("what is true now", () => {
  it("takes the role, the server’s tools and what can be undone from the session", () => {
    const facts = windowFacts(state(), { selection: [] });
    expect(facts.role).toBe("editor");
    expect(facts.client).toBe("web");
    expect([...facts.tools]).toEqual(["latex"]);
    expect(facts.document).toEqual({
      undo: true,
      redo: false,
      references: false,
      randomNumbers: false,
      backPlace: false,
      slides: 0,
    });
  });

  it("takes what the app adds: references, random numbers, slides, the desktop app, the way back", () => {
    const facts = windowFacts(state({ wayBack: { at: 1 } }), {
      selection: [],
      references: true,
      randomNumbers: true,
      slides: 3,
      desktop: true,
    });
    expect(facts.client).toBe("desktop");
    expect(facts.document).toMatchObject({
      references: true,
      randomNumbers: true,
      backPlace: true,
      slides: 3,
    });
  });

  it("is looking only while the past is replayed, and for anybody who is neither owner nor editor", () => {
    expect(
      windowFacts(state({ me: { role: "owner" }, replay: {} }), {
        selection: [],
      }).role,
    ).toBe("viewer");
    expect(
      windowFacts(state({ me: { role: "commenter" } }), { selection: [] }).role,
    ).toBe("viewer");
  });

  it("has the ai only where a provider answers that is not the stand-in", () => {
    const answering = (provider: string) =>
      windowFacts(state({ consent: { answering: { provider } } }), {
        selection: [],
      }).ai;
    expect(answering("ollama")).toBe(true);
    expect(answering("stand-in")).toBe(false);
    expect(windowFacts(state(), { selection: [] }).ai).toBe(false);
  });
});

describe("a workspace's menus", () => {
  afterEach(() => vi.restoreAllMocks());

  const facts = () => windowFacts(state(), { selection: [] });

  it("are the definition’s menus with the workspace’s handlers", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const menus = useMenus("composes", {
      handlers: () => ({}),
      facts,
      notice: vi.fn(),
    });
    expect(menus.value.bar.map((m) => m.label)).toEqual(
      DEFINITIONS.composes.menus.map((m) => m.label),
    );
  });

  it("say once on the console which actions have no handler and which handlers no action", () => {
    const error = vi.spyOn(console, "error").mockImplementation(() => {});
    const menus = useMenus("composes", {
      handlers: () => ({ "test.nothing": { run: () => {} } }),
      facts,
      notice: vi.fn(),
    });
    void menus.value;
    expect(error).toHaveBeenCalledTimes(2);
    expect(error.mock.calls[0]![0]).toMatch(
      /^menus of composes: no handler for /,
    );
    expect(error.mock.calls[1]![0]).toBe(
      "menus of composes: a handler for no action: test.nothing",
    );
  });
});
