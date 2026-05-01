import { render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  accountType: "debtor",
  groupsList: vi.fn().mockResolvedValue([]),
  apiRequest: vi.fn(),
}));

vi.mock("../src/contexts/AuthContext", () => ({
  useAuth: () => ({
    user: { id: "u1", email: "u1@example.com", name: "User", phone: "", account_type: mocks.accountType },
    isAuthenticated: true,
    isLoading: false,
    profileLocale: undefined,
    signIn: vi.fn(),
    signUp: vi.fn(),
    signOut: vi.fn(),
  }),
}));

vi.mock("../src/lib/api", () => ({
  apiRequest: mocks.apiRequest,
  errorCode: vi.fn().mockReturnValue(""),
  groups: {
    list: mocks.groupsList,
    create: vi.fn(),
    accept: vi.fn(),
    decline: vi.fn(),
  },
}));

import { GroupsPage } from "../src/pages/GroupsPage";
import { translateNotification } from "../src/lib/i18n";

describe("group role UI", () => {
  it("does not show the create group action for debtor profiles", async () => {
    mocks.accountType = "debtor";
    mocks.apiRequest.mockResolvedValue({ account_type: "debtor" });

    render(
      <MemoryRouter>
        <GroupsPage language="en" />
      </MemoryRouter>,
    );

    await waitFor(() => expect(mocks.groupsList).toHaveBeenCalled());
    expect(screen.queryByText("Create New Group")).not.toBeInTheDocument();
  });
});

describe("notification localization", () => {
  it("renders notification text in the selected language", () => {
    expect(translateNotification("debt_created", "New debt requires confirmation", "raw", "ar")).toEqual({
      title: "دين جديد",
      body: "تم إنشاء دين جديد",
    });
    expect(translateNotification("debt_created", "تم إنشاء دين جديد", "raw", "en")).toEqual({
      title: "New debt created",
      body: "New debt created",
    });
  });
});
