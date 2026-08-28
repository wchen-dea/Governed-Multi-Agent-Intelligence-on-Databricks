import { expect, test } from "@playwright/test";

function sse(events: object[]): string {
  return events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join("") + "data: [DONE]\n\n";
}

test.beforeEach(async ({ page }) => {
  await page.route("**/invocations", async (route) => {
    const body = await route.request().postDataJSON();
    const content = body.input.at(-1)?.content ?? "";
    const events = content.includes("blocked")
      ? [{ type: "response.output_text.delta", delta: "Request blocked." }, { response_envelope: { status: "blocked", guardrail_reasons: ["evidence_required"], truncated: false } }]
      : [{ type: "response.output_item.added", item: { type: "tool_call_output_item", name: "query_sales" } }, { type: "response.output_text.delta", delta: "First " }, { type: "response.output_text.delta", delta: "answer." }, { type: "response.governance", response_envelope: { status: "succeeded", truncated: false } }];
    await route.fulfill({ status: 200, contentType: "text/event-stream", body: sse(events) });
  });
});

test("renders incremental answer and run context on desktop", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("textbox", { name: "Message" }).fill("Show sales answer");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("First answer.")).toBeVisible();
  await page.getByText("Run context").click();
  await expect(page.getByText("App identity", { exact: true })).toBeVisible();
});

test("exposes OBO state and blocked responses", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("textbox", { name: "Message" }).fill("blocked");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Request blocked.")).toBeVisible();
  await page.getByRole("combobox", { name: "Persona" }).selectOption("analyst");
  await page.getByRole("textbox", { name: "Message" }).fill("/token secret-token");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Hybrid OBO")).toBeVisible();
});

test("keeps the workspace usable on mobile", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".app-shell")).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Message" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Send" })).toBeVisible();
});

test("shows manager actions for a pending HITL response", async ({ page }) => {
  await page.route("**/approval-decisions", async (route) => {
    const body = route.request().postDataJSON();
    expect(body.decision).toBe("approved");
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "ok",
        approval: {
          request_id: body.request_id,
          agent_name: body.agent_name,
          approver: body.approver,
          decision: body.decision,
          status: "approved",
        },
      }),
    });
  });
  await page.route("**/invocations", async (route) => {
    const events = [
      { type: "response.output_text.delta", delta: "Review packet ready." },
      {
        type: "response.governance",
        response_envelope: {
          status: "succeeded",
          truncated: false,
          approval_state: {
            status: "pending",
            required: true,
            approver: "manager",
            reason: "Manager review is required before dispatch.",
          },
        },
      },
    ];
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: sse(events),
    });
  });

  await page.goto("/");
  await page.getByRole("textbox", { name: "Message" }).fill("Review HITL packet");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByRole("button", { name: "Approve planning" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Request more info" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Reject" })).toBeVisible();
  await page.getByRole("button", { name: "Approve planning" }).click();
  await expect(page.getByText("Review packet ready.")).toBeVisible();
});