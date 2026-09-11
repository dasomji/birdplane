import test from "node:test";
import assert from "node:assert/strict";
import { FilterInstance, workItemFiltersAdapter } from "./dist/index.js";
import { getLabelFilterConfig, getTargetDateFilterConfig } from "@plane/utils";
import { CORE_OPERATORS } from "@plane/types";

function setup() {
  const changes = [];
  const filter = new FilterInstance({
    adapter: workItemFiltersAdapter,
    onExpressionChange: (value) => changes.push(value),
  });
  const params = { isEnabled: true, allowedOperators: new Set(Object.values(CORE_OPERATORS)), labels: [] };
  filter.configManager.registerAll([
    getLabelFilterConfig("label_id")(params),
    getTargetDateFilterConfig("target_date")(params),
  ]);
  return { filter, changes };
}

test("operators preserve selections and empty applies immediately without a value picker", () => {
  const { filter, changes } = setup();
  filter.addCondition("and", { property: "label_id", operator: "in", value: ["blog", "other"] }, false);
  const id = filter.allConditions[0].id;
  filter.updateConditionOperator(id, "not_in", false);
  assert.deepEqual(changes.at(-1), { label_id__not_in: "blog,other" });
  const config = filter.configManager.getConfigByProperty("label_id");
  assert.deepEqual(
    config.getAllDisplayOperatorOptionsByValue(["blog"]).map((o) => o.label),
    ["is", "is not", "is empty"]
  );
  filter.updateConditionOperator(id, "is_empty", false);
  assert.equal(filter.allConditions[0].value, true);
  assert.deepEqual(changes.at(-1), { label_id__is_empty: true });
  assert.equal(config.getOperatorConfig("is_empty").type, "empty");
  filter.updateConditionOperator(id, "in", false);
  assert.equal(filter.allConditions[0].value, undefined);
  filter.updateConditionOperator(id, "is_empty", false);
  assert.deepEqual(changes.at(-1), { label_id__is_empty: true });
});

test("saved filters round-trip negative lists, empty, and dates", () => {
  const expression = {
    and: [
      { label_id__not_in: "blog,other" },
      { assignee_id__is_empty: true },
      { target_date__not_exact: "2026-09-20" },
    ],
  };
  assert.deepEqual(workItemFiltersAdapter.toExternal(workItemFiltersAdapter.toInternal(expression)), expression);
  const { filter, changes } = setup();
  filter.addCondition("and", { property: "target_date", operator: "is_empty" }, false);
  assert.deepEqual(changes.at(-1), { target_date__is_empty: true });
  filter.updateConditionOperator(filter.allConditions[0].id, "not_exact", false);
  assert.equal(filter.allConditions[0].value, undefined);
});
