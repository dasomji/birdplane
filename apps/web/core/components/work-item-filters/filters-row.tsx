/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import type { IWorkItemFilterInstance } from "@plane/shared-state";
import type { TWorkItemFilterExpression, TWorkItemFilterProperty } from "@plane/types";
// components
import type { TFiltersRowProps } from "@/components/rich-filters/filters-row";
import { FiltersRow } from "@/components/rich-filters/filters-row";
import { PQLEditor } from "./pql-editor";

type TWorkItemFiltersRowProps = TFiltersRowProps<TWorkItemFilterProperty, TWorkItemFilterExpression> & {
  filter: IWorkItemFilterInstance;
};

export const WorkItemFiltersRow = observer(function WorkItemFiltersRow(props: TWorkItemFiltersRowProps) {
  const hasPQLCondition = props.filter.allConditionsForDisplay.some((condition) => condition.property === "pql");

  return (
    <FiltersRow
      {...props}
      renderCondition={(condition, defaultCondition, isDisabled) =>
        condition.property === "pql" ? (
          <PQLEditor condition={condition} filter={props.filter} isDisabled={isDisabled} />
        ) : (
          defaultCondition
        )
      }
      additionalControls={(isDisabled) =>
        !hasPQLCondition && <PQLEditor filter={props.filter} isDisabled={isDisabled} />
      }
    />
  );
});
