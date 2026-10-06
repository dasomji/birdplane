/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
// plane imports
import { PROFILE_SETTINGS, PROFILE_SETTINGS_TABS } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import type { TProfileSettingsTabs } from "@plane/types";
// components
import { LogoSpinner } from "@/components/common/logo-spinner";
import { PageHead } from "@/components/core/page-title";
import { ProfileSettingsContent } from "@/components/settings/profile/content";
import { ProfileSettingsSidebarRoot } from "@/components/settings/profile/sidebar";
// hooks
import { useUser } from "@/hooks/store/user";
import { useAppRouter } from "@/hooks/use-app-router";
// local imports
import type { Route } from "../+types/layout";

function ProfileSettingsPage(props: Route.ComponentProps) {
  const { profileTabId } = props.params;
  // router
  const router = useAppRouter();
  // store hooks
  const { data: currentUser } = useUser();
  // translation
  const { t } = useTranslation();
  // derived values
  const isAValidTab = PROFILE_SETTINGS_TABS.includes(profileTabId as TProfileSettingsTabs);

  if (!currentUser || !isAValidTab)
    return (
      <div className="grid size-full place-items-center px-4">
        <LogoSpinner />
      </div>
    );

  return (
    <>
      <PageHead title={`${t("profile.label")} - ${t("general_settings")}`} />
      <div className="relative flex size-full min-h-0 flex-col">
        <nav aria-label="Profile settings" className="shrink-0 border-b border-subtle p-3 lg:hidden">
          <select
            aria-label="Profile settings page"
            value={profileTabId}
            onChange={(event) => router.push(`/settings/profile/${event.target.value}`)}
            className="w-full rounded-md border border-subtle bg-surface-1 px-3 py-2 text-13 text-primary"
          >
            {PROFILE_SETTINGS_TABS.map((tab) => (
              <option key={tab} value={tab}>
                {t(PROFILE_SETTINGS[tab].i18n_label)}
              </option>
            ))}
          </select>
        </nav>
        <div className="flex min-h-0 min-w-0 flex-1">
          <ProfileSettingsSidebarRoot
            activeTab={profileTabId as TProfileSettingsTabs}
            className="hidden w-[250px] lg:block"
            updateActiveTab={(tab) => router.push(`/settings/profile/${tab}`)}
          />
          <ProfileSettingsContent
            activeTab={profileTabId as TProfileSettingsTabs}
            className="mx-auto w-full max-w-225 min-w-0 grow px-3 py-4 lg:px-page-x lg:py-20"
          />
        </div>
      </div>
    </>
  );
}

export default observer(ProfileSettingsPage);
