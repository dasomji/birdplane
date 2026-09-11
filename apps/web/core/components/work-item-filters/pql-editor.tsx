/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import React, { Fragment, useId, useState } from "react";
import { Popover, Transition } from "@headlessui/react";
import { Braces, X } from "lucide-react";
import { useParams } from "next/navigation";
import { usePopper } from "react-popper";
// plane imports
import { Button } from "@plane/propel/button";
import { getButtonStyling } from "@plane/propel/button";
import type { IWorkItemFilterInstance } from "@plane/shared-state";
import type { TFilterConditionNodeForDisplay, TFilterValue, TWorkItemFilterProperty } from "@plane/types";
import { LOGICAL_OPERATOR } from "@plane/types";
import { TextArea } from "@plane/ui";
import { cn } from "@plane/utils";
// services
import { PQLService } from "@/services/pql.service";

type TPQLEditorProps = {
  condition?: TFilterConditionNodeForDisplay<TWorkItemFilterProperty, TFilterValue>;
  filter: IWorkItemFilterInstance;
  isDisabled: boolean;
};

const PRESETS = [
  { label: "Today", query: "createdAt = today()" },
  {
    label: "This week",
    query: "createdAt BETWEEN startOfWeek() AND endOfWeek()",
  },
  { label: "Last 7 days", query: "createdAt >= daysAgo(7)" },
  { label: "Last 24 hours", query: "createdAt >= hoursAgo(24)" },
] as const;
const PQL_MAX_LENGTH = 500;

const pqlService = new PQLService();

export function PQLEditor(props: TPQLEditorProps) {
  const savedQuery = typeof props.condition?.value === "string" ? props.condition.value : "";

  return (
    <PQLEditorContent
      key={JSON.stringify([props.condition?.id ?? null, savedQuery])}
      {...props}
      savedQuery={savedQuery}
    />
  );
}

type TPQLEditorContentProps = TPQLEditorProps & {
  savedQuery: string;
};

function PQLEditorContent(props: TPQLEditorContentProps) {
  const { condition, filter, isDisabled, savedQuery } = props;
  const { workspaceSlug } = useParams();
  const queryFieldId = useId();
  const [draft, setDraft] = useState(savedQuery);
  const [error, setError] = useState<string>();
  const [isValidating, setIsValidating] = useState(false);
  const [referenceElement, setReferenceElement] = useState<HTMLButtonElement | null>(null);
  const [popperElement, setPopperElement] = useState<HTMLDivElement | null>(null);
  const { attributes, styles } = usePopper(referenceElement, popperElement, {
    placement: "bottom-start",
    strategy: "fixed",
    modifiers: [
      { name: "offset", options: { offset: [0, 8] } },
      {
        name: "flip",
        options: { fallbackPlacements: ["top-start", "bottom-end", "top-end"] },
      },
      { name: "preventOverflow", options: { padding: 8 } },
    ],
  });

  if (isDisabled && !condition) return null;

  const handleApply = async (close: () => void) => {
    if (isValidating) return;

    const query = draft.trim();
    if (!query) {
      setError("Enter a PQL query.");
      return;
    }
    if (!workspaceSlug) {
      setError("A workspace is required to validate this query.");
      return;
    }

    setIsValidating(true);
    setError(undefined);
    try {
      await pqlService.validate(workspaceSlug.toString(), query);
      if (condition) {
        filter.updateConditionValue(condition.id, query);
      } else {
        filter.addCondition(LOGICAL_OPERATOR.AND, { property: "pql", operator: "exact", value: query }, false);
      }
      close();
    } catch (validationError) {
      setError(getValidationError(validationError));
    } finally {
      setIsValidating(false);
    }
  };

  const handleRemove = (close: () => void) => {
    if (condition) filter.removeCondition(condition.id);
    setDraft("");
    setError(undefined);
    close();
  };

  if (isDisabled) {
    return (
      <div className="flex h-7 max-w-80 items-center gap-1 rounded-md border border-subtle bg-layer-2 px-2 text-11">
        <Braces className="size-3.5 shrink-0 text-secondary" />
        <span className="shrink-0 text-tertiary">PQL</span>
        <span className="font-mono truncate text-secondary">{savedQuery}</span>
      </div>
    );
  }

  return (
    <Popover className="relative">
      {({ close }) => (
        <>
          <Popover.Button
            ref={setReferenceElement}
            type="button"
            className={cn(getButtonStyling("secondary", "lg"), "max-w-80 gap-1 py-[5px]")}
          >
            <Braces className="size-4 shrink-0 text-secondary" />
            <span className="shrink-0">PQL</span>
            {savedQuery && <span className="font-mono truncate text-11 text-tertiary">{savedQuery}</span>}
          </Popover.Button>
          <Transition
            as={Fragment}
            enter="transition ease-out duration-150"
            enterFrom="translate-y-1 opacity-0"
            enterTo="translate-y-0 opacity-100"
            leave="transition ease-in duration-100"
            leaveFrom="translate-y-0 opacity-100"
            leaveTo="translate-y-1 opacity-0"
          >
            <Popover.Panel className="fixed z-30 translate-y-0">
              <div
                ref={setPopperElement}
                style={styles.popper}
                {...attributes.popper}
                className="max-h-[calc(100vh-1rem)] w-[32rem] max-w-[calc(100vw-2rem)] overflow-y-auto rounded-md border border-subtle bg-surface-1 p-3 shadow-raised-100"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-13 font-medium text-primary">Plane Query Language</h3>
                    <p className="mt-0.5 text-11 text-tertiary">
                      Filter work items with dates that update automatically.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => close()}
                    disabled={isValidating}
                    className="text-tertiary hover:text-secondary disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <X className="size-4" />
                    <span className="sr-only">Close PQL editor</span>
                  </button>
                </div>

                <div className="mt-3 flex flex-wrap gap-1.5">
                  {PRESETS.map((preset) => (
                    <Button
                      key={preset.label}
                      type="button"
                      variant="secondary"
                      size="sm"
                      disabled={isValidating}
                      onClick={() => {
                        setDraft(preset.query);
                        setError(undefined);
                      }}
                    >
                      {preset.label}
                    </Button>
                  ))}
                </div>

                <label htmlFor={queryFieldId} className="mt-3 block text-11 font-medium text-secondary">
                  Query
                </label>
                <TextArea
                  id={queryFieldId}
                  value={draft}
                  maxLength={PQL_MAX_LENGTH}
                  disabled={isValidating}
                  onChange={(event) => {
                    setDraft(event.target.value);
                    setError(undefined);
                  }}
                  onKeyDown={(event) => {
                    if (!isValidating && (event.metaKey || event.ctrlKey) && event.key === "Enter") {
                      event.preventDefault();
                      void handleApply(close);
                    }
                  }}
                  className="font-mono mt-1 min-h-20 resize-y text-12"
                  hasError={Boolean(error)}
                  placeholder="createdAt >= daysAgo(7)"
                  spellCheck={false}
                />
                {error && (
                  <p className="mt-1 text-11 text-danger-primary" role="alert" aria-live="polite">
                    {error}
                  </p>
                )}

                <div className="mt-3 rounded-md bg-layer-2 p-2 text-11 text-tertiary">
                  <p>
                    Date fields: <code>createdAt</code>, <code>updatedAt</code>, <code>startDate</code>, and{" "}
                    <code>dueDate</code>.
                  </p>
                  <p className="mt-1">
                    Relative functions: <code>today()</code>, <code>daysAgo(n)</code>, <code>hoursAgo(n)</code>,{" "}
                    <code>startOfWeek()</code>, and <code>endOfWeek()</code>. Combine expressions with <code>AND</code>.
                  </p>
                </div>

                <div className="mt-3 flex items-center justify-between gap-2">
                  <div>
                    {condition && (
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        disabled={isValidating}
                        onClick={() => handleRemove(close)}
                      >
                        Remove
                      </Button>
                    )}
                  </div>
                  <Button
                    type="button"
                    variant="primary"
                    size="sm"
                    loading={isValidating}
                    disabled={!draft.trim() || isValidating}
                    onClick={() => void handleApply(close)}
                  >
                    Apply query
                  </Button>
                </div>
              </div>
            </Popover.Panel>
          </Transition>
        </>
      )}
    </Popover>
  );
}

function getValidationError(error: unknown): string {
  if (typeof error === "string") return error;
  if (!error || typeof error !== "object") return "The query could not be validated.";

  const errorData = error as Record<string, unknown>;
  for (const key of ["detail", "error", "message", "pql", "query"]) {
    const value = errorData[key];
    if (typeof value === "string") return value;
    if (Array.isArray(value) && typeof value[0] === "string") return value[0];
  }

  return "The query could not be validated.";
}
