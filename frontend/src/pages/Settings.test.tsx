import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Settings } from "./Settings";

// Mock the api client so tests don't try to hit the backend.
vi.mock("../api/client", () => ({
  default: {
    patch: vi.fn().mockResolvedValue({ data: { message: "Channels updated." } }),
  },
}));

describe("Settings page", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders all four channel input fields", () => {
    render(<Settings />);
    expect(screen.getByPlaceholderText(/^https:\/\/hooks\.slack\.com/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/you@company\.com/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/123456789/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/\+14155238886/i)).toBeInTheDocument();
  });

  it("submits filled channels to the API on save", async () => {
    const user = userEvent.setup();
    const api = (await import("../api/client")).default as unknown as {
      patch: ReturnType<typeof vi.fn>;
    };

    render(<Settings />);
    await user.type(screen.getByPlaceholderText(/you@company\.com/i), "ops@example.com");
    await user.click(screen.getByRole("button", { name: /save/i }));

    expect(api.patch).toHaveBeenCalledTimes(1);
    const [path, body] = api.patch.mock.calls[0];
    expect(path).toBe("/workspace/channels");
    expect(body.delivery_channels.email).toEqual({ address: "ops@example.com" });
  });

  it("does not include empty channels in the submitted body", async () => {
    const user = userEvent.setup();
    const api = (await import("../api/client")).default as unknown as {
      patch: ReturnType<typeof vi.fn>;
    };

    render(<Settings />);
    await user.type(screen.getByPlaceholderText(/^https:\/\/hooks\.slack\.com/i), "https://hooks.slack.com/services/X");
    await user.click(screen.getByRole("button", { name: /save/i }));

    const [, body] = api.patch.mock.calls[0];
    expect(body.delivery_channels).toEqual({
      slack: { webhook_url: "https://hooks.slack.com/services/X", min_priority: "low" },
    });
    expect(body.delivery_channels.email).toBeUndefined();
    expect(body.delivery_channels.telegram).toBeUndefined();
    expect(body.delivery_channels.whatsapp).toBeUndefined();
  });
});
