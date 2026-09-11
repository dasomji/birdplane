// Copyright (c) 2023-present Plane Software, Inc. and contributors
// SPDX-License-Identifier: AGPL-3.0-only
import { CORE_OPERATORS, FILTER_FIELD_TYPE } from "@plane/types";
import type { TFilterConfig, TFilterProperty } from "@plane/types";

/** Extend work-item filters without changing other consumers of rich filters. */
export const createFilterConfig = <P extends TFilterProperty>(config: TFilterConfig<P>): TFilterConfig<P> => {
  const operators = new Map(config.supportedOperatorConfigsMap);
  const inclusion = operators.get(CORE_OPERATORS.IN);
  const exact = operators.get(CORE_OPERATORS.EXACT);
  if (inclusion?.type === FILTER_FIELD_TYPE.MULTI_SELECT) {
    operators.set(CORE_OPERATORS.NOT_IN, { ...inclusion, singleValueOperator: CORE_OPERATORS.NOT_EXACT });
  }
  if (exact) operators.set(CORE_OPERATORS.NOT_EXACT, { ...exact });
  // Required properties cannot be empty. Priority's explicit "none" is empty.
  if (!["project_id", "state_id", "state_group", "created_at", "updated_at"].includes(String(config.id))) {
    operators.set(CORE_OPERATORS.IS_EMPTY, {
      type: FILTER_FIELD_TYPE.EMPTY,
      defaultValue: true,
      isOperatorEnabled: true,
    });
  }
  return { ...config, supportedOperatorConfigsMap: operators };
};
