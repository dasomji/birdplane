/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import * as React from "react";
import type { ISvgIcons } from "../type";

// Keep the exported name compatible with existing consumers of the fork.
export function PlaneWordmark({
  width = "253",
  height = "53",
  className,
  color = "currentColor",
  ...props
}: ISvgIcons) {
  return (
    <svg
      width={width}
      height={height}
      viewBox="0 0 253 53"
      fill={color}
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role="img"
      aria-label="Birdplane"
      {...props}
    >
      <text
        x="0"
        y="42"
        fontFamily="Inter, Arial, sans-serif"
        fontSize="44"
        fontWeight="600"
        textLength="253"
        lengthAdjust="spacingAndGlyphs"
      >
        Birdplane
      </text>
    </svg>
  );
}
