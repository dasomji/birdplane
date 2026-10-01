import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { test } from "node:test";
import {
  PRODUCT_NAME,
  SITE_NAME,
  SITE_TITLE,
  SPACE_SITE_NAME,
  SPACE_SITE_TITLE,
} from "../packages/constants/src/metadata.ts";

const readJson = (path) => JSON.parse(readFileSync(new URL(path, import.meta.url), "utf8"));

test("browser and installable app names identify Birdplane", () => {
  assert.equal(PRODUCT_NAME, "Birdplane");
  assert.equal(SITE_NAME, PRODUCT_NAME);
  assert.ok(SITE_TITLE.startsWith(`${PRODUCT_NAME} |`));
  assert.equal(SPACE_SITE_NAME, `${PRODUCT_NAME} Publish`);
  assert.ok(SPACE_SITE_TITLE.startsWith(`${SPACE_SITE_NAME} |`));

  for (const path of [
    "../apps/web/manifest.json",
    "../apps/web/public/manifest.json",
    "../apps/web/public/site.webmanifest.json",
    "../apps/web/public/favicon/site.webmanifest",
    "../apps/admin/public/site.webmanifest.json",
    "../apps/space/public/site.webmanifest.json",
    "../apps/space/app/assets/favicon/site.webmanifest",
  ]) {
    const manifest = readJson(path);
    assert.ok(manifest.name.startsWith(PRODUCT_NAME), path);
    assert.ok(manifest.short_name.startsWith(PRODUCT_NAME), path);
    assert.ok(manifest.icons.length > 0, path);
    assert.equal(manifest.display, "standalone", path);
  }
});

test("localized product copy retains translation keys and upstream product names", () => {
  const locales = new URL("../packages/i18n/src/locales/", import.meta.url);
  let checked = 0;
  for (const locale of readdirSync(locales, { withFileTypes: true }).filter((entry) => entry.isDirectory())) {
    const auth = readJson(`../packages/i18n/src/locales/${locale.name}/auth.json`);
    assert.equal(typeof auth.auth.common.new_to_plane, "string", locale.name);
    assert.ok(auth.auth.common.new_to_plane.includes(PRODUCT_NAME), locale.name);
    assert.doesNotMatch(auth.auth.common.new_to_plane, /\bPlane\b/u, locale.name);
    const navigation = readJson(`../packages/i18n/src/locales/${locale.name}/navigation.json`);
    assert.equal(typeof navigation.sidebar.plane_pro, "string", locale.name);
    assert.ok(navigation.sidebar.plane_pro.length > 0, locale.name);
    assert.ok(!navigation.sidebar.plane_pro.includes(PRODUCT_NAME), locale.name);
    checked++;
  }
  assert.ok(checked > 1);
  assert.equal(readJson("../packages/i18n/src/locales/en/navigation.json").sidebar.plane_pro, "Plane Pro");
});
