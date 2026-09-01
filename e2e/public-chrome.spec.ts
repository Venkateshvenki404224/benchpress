import { test, expect } from "@playwright/test";

// The header and the footer are one include each across all six public routes, so a width that
// breaks one breaks every page at once. 320px is the floor: below the last breakpoint, nothing
// shrinks further.
const ROUTES = ["/", "/landing", "/signup", "/login", "/about", "/contact"];
const WIDTHS = [320, 360, 390, 480, 560, 768, 900, 1024, 1100, 1140, 1280];

async function settle(page: import("@playwright/test").Page) {
  await page.evaluate(async () => {
    await document.fonts.ready;
    for (const face of ["400 14px Poppins", "500 13.5px Poppins", "600 12.5px Poppins"]) {
      try {
        await document.fonts.load(face);
      } catch (error) {
        void error;
      }
    }
    await document.fonts.ready;
  });
}

function overflowIn(sel: string) {
  const root = document.querySelector<HTMLElement>(sel);
  if (!root) return `no ${sel} on page`;
  const vw = window.innerWidth;
  if (document.documentElement.scrollWidth - vw > 1)
    return `page overflows: scrollWidth=${document.documentElement.scrollWidth} vw=${vw}`;
  for (const el of root.querySelectorAll<HTMLElement>("*")) {
    if (getComputedStyle(el).display === "none") continue;
    const box = el.getBoundingClientRect();
    if (box.width === 0 && box.height === 0) continue;
    if (box.right > vw + 1 || box.left < -1)
      return `${el.className || el.tagName} sits outside the viewport: left=${box.left.toFixed(1)} right=${box.right.toFixed(1)} vw=${vw}`;
  }
  return "";
}

test.describe("Public chrome", () => {
  for (const route of ROUTES) {
    test(`${route} keeps its header and footer inside the viewport at every width`, async ({
      page,
    }) => {
      for (const width of WIDTHS) {
        await page.setViewportSize({ width, height: 900 });
        await page.goto(route, { waitUntil: "load" });
        await settle(page);

        for (const selector of [".bp-header", ".bp-footer"]) {
          const overflow = await page.evaluate(overflowIn, selector);
          expect(overflow, `${route} ${selector} at ${width}px`).toBe("");
        }
      }
    });
  }

  test("every route offers the same footer columns", async ({ page }) => {
    const columns: Record<string, string[]> = {};
    for (const route of ROUTES) {
      await page.setViewportSize({ width: 1280, height: 900 });
      await page.goto(route, { waitUntil: "load" });
      columns[route] = await page
        .locator(".bp-footer__col .bp-footer__heading")
        .allInnerTexts();
    }

    for (const route of ROUTES) {
      expect(columns[route], `footer columns on ${route}`).toEqual(columns["/"]);
      expect(columns[route].length).toBeGreaterThan(0);
    }
  });

  // The header is fixed, so a page whose first section forgets the clearance loses its heading
  // under the dock.
  test("no page starts underneath the fixed header", async ({ page }) => {
    for (const route of ROUTES) {
      for (const width of [320, 390, 768, 1280]) {
        await page.setViewportSize({ width, height: 900 });
        await page.goto(route, { waitUntil: "load" });
        await settle(page);

        const gap = await page.evaluate(() => {
          const header = document.querySelector<HTMLElement>(".bp-header__inner")!;
          // `/login` ships five sections and shows one, so the first visible heading is the page's.
          const heading = [...document.querySelectorAll<HTMLElement>("#bp-content h1")].find(
            (candidate) => candidate.getBoundingClientRect().height > 0,
          )!;
          return heading.getBoundingClientRect().top - header.getBoundingClientRect().bottom;
        });

        expect(gap, `${route} at ${width}px`).toBeGreaterThan(0);
      }
    }
  });

  test("the menu button is reachable wherever the nav collapses", async ({ page }) => {
    for (const width of [320, 390, 560, 1024, 1100]) {
      await page.setViewportSize({ width, height: 900 });
      await page.goto("/about", { waitUntil: "load" });
      await settle(page);

      const menu = page.locator(".bp-menu");
      await expect(menu, `menu button at ${width}px`).toBeVisible();
      await expect(page.locator(".bp-nav"), `nav closed at ${width}px`).toBeHidden();

      await menu.click();
      await expect(page.locator(".bp-nav"), `nav opens at ${width}px`).toBeVisible();
    }
  });

  // The wordmark shrinks through two breakpoints, in the header and again in the footer. Both
  // header rules once lost to a more specific per-variant base rule, which a media query cannot
  // outweigh.
  test("the wordmark shrinks the same way on every route", async ({ page }) => {
    const heights: Record<string, string[]> = {};
    for (const route of ["/", "/about"]) {
      heights[route] = [];
      for (const width of [320, 480, 700]) {
        await page.setViewportSize({ width, height: 900 });
        await page.goto(route, { waitUntil: "load" });
        await settle(page);
        heights[route].push(
          await page.evaluate(() => {
            const img = [...document.querySelectorAll<HTMLImageElement>(".bp-brand img")].find(
              (candidate) => getComputedStyle(candidate).display !== "none",
            );
            return getComputedStyle(img!).height;
          }),
        );
      }
    }

    expect(heights["/"]).toEqual(["22px", "24px", "30px"]);
    expect(heights["/about"]).toEqual(heights["/"]);
  });

  test("the theme toggle survives moving into the disclosure", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 900 });
    await page.goto("/about", { waitUntil: "load" });
    await settle(page);

    const toggle = page.locator(".bp-toggle");
    await expect(toggle).toBeHidden();

    await page.locator(".bp-menu").click();
    await expect(toggle).toBeVisible();

    const before = await page.evaluate(() => document.querySelector<HTMLElement>(".bp")!.dataset.mode);
    await toggle.click();
    await expect
      .poll(() => page.evaluate(() => document.querySelector<HTMLElement>(".bp")!.dataset.mode))
      .not.toBe(before);
    expect(await page.evaluate(() => localStorage.getItem("bp-mode"))).toBe(
      await page.evaluate(() => document.querySelector<HTMLElement>(".bp")!.dataset.mode),
    );
  });
});
