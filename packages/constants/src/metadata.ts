/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export const PRODUCT_NAME = "Birdplane";
export const SITE_NAME = PRODUCT_NAME;
export const SITE_TITLE = `${PRODUCT_NAME} | Simple, extensible, open-source project management tool.`;
export const SITE_DESCRIPTION =
  "Open-source project management tool to manage work items, cycles, and product roadmaps easily";
export const SITE_KEYWORDS =
  "software development, plan, ship, software, accelerate, code management, release management, project management, work items tracking, agile, scrum, kanban, collaboration";
export const SITE_URL = process.env.VITE_WEB_BASE_URL || "";
export const TWITTER_USER_NAME = PRODUCT_NAME;

// Birdplane Publish metadata
export const SPACE_SITE_NAME = `${PRODUCT_NAME} Publish`;
export const SPACE_SITE_TITLE = `${SPACE_SITE_NAME} | Make your Birdplane boards public with one-click`;
export const SPACE_SITE_DESCRIPTION = "Publish your Birdplane boards and collect customer feedback.";
export const SPACE_SITE_KEYWORDS =
  "software development, customer feedback, software, accelerate, code management, release management, project management, work items tracking, agile, scrum, kanban, collaboration";
export const SPACE_SITE_URL = process.env.VITE_SPACE_BASE_URL || "";
export const SPACE_TWITTER_USER_NAME = "";
