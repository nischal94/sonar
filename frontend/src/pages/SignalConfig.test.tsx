import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { SignalConfig } from "./SignalConfig";

// Mock the api client so tests don't hit the backend.
vi.mock("../api/client", () => ({
  default: {
    post: vi.fn(),
  },
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <SignalConfig />
    </MemoryRouter>,
  );
}

describe("SignalConfig wizard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders step 1 with the 'What do you sell?' prompt", () => {
    renderPage();
    expect(
      screen.getByRole("heading", { name: /what do you sell\?/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/step 1 of 5/i)).toBeInTheDocument();
  });

  it("disables Next until the textarea has at least 5 characters", async () => {
    const user = userEvent.setup();
    renderPage();
    const next = screen.getByRole("button", { name: /next/i });
    expect(next).toBeDisabled();

    const textarea = screen.getByRole("textbox");
    await user.type(textarea, "abcd");
    expect(next).toBeDisabled();

    await user.type(textarea, "e");
    expect(next).toBeEnabled();
  });

  it("advances to step 2 (ICP) after clicking Next", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.type(screen.getByRole("textbox"), "Fractional CTO services");
    await user.click(screen.getByRole("button", { name: /next/i }));

    expect(
      screen.getByRole("heading", { name: /who's your icp/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/step 2 of 5/i)).toBeInTheDocument();
  });
});
