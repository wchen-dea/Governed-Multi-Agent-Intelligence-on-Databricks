import { expect, test } from "@playwright/test";

function sse(events: object[]): string {
  return (
    events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join("") +
    "data: [DONE]\n\n"
  );
}

test.beforeEach(async ({ page }) => {
  await page.route("**/invocations", async (route) => {
    const body = await route.request().postDataJSON();
    const content = body.input.at(-1)?.content ?? "";
    const events = content.includes("blocked")
      ? [
          { type: "response.output_text.delta", delta: "Request blocked." },
          {
            response_envelope: {
              status: "blocked",
              guardrail_reasons: ["evidence_required"],
              truncated: false,
            },
          },
        ]
      : [
          {
            type: "response.output_item.added",
            item: { type: "tool_call_output_item", name: "query_sales" },
          },
          { type: "response.output_text.delta", delta: "First " },
          { type: "response.output_text.delta", delta: "answer." },
          {
            type: "response.governance",
            response_envelope: { status: "succeeded", truncated: false },
          },
        ];
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: sse(events),
    });
  });
});

test("shows the beginning of the initial chat content", async ({ page }) => {
  await page.goto("/");
  const chatLog = page.locator(".chat-log");
  await expect(chatLog.getByRole("heading", { name: "Available Agents" })).toBeVisible();
  await expect
    .poll(() => chatLog.evaluate((element) => element.scrollTop))
    .toBe(0);
});

test("clear resets only the conversation content", async ({ page }) => {
  const conversationIds: string[] = [];
  await page.route("**/invocations", async (route) => {
    const request = route.request().postDataJSON() as {
      context?: { conversation_id?: string };
    };
    const conversationId = request.context?.conversation_id;
    if (conversationId) conversationIds.push(conversationId);
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: sse([
        { type: "response.output_text.delta", delta: "First answer." },
        { type: "response.completed", response: {} },
      ]),
    });
  });
  await page.goto("/");
  await page.getByRole("combobox", { name: "Persona" }).selectOption("executive");
  await page.getByRole("textbox", { name: "Message" }).fill("Show sales answer");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("First answer.")).toBeVisible();

  await page.getByRole("button", { name: "Clear conversation" }).click();

  await expect(page.getByText("First answer.")).toHaveCount(0);
  await expect(page.getByRole("heading", { name: "Available Agents" })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Persona" })).toHaveValue("executive");
  await expect(page.getByRole("button", { name: "Insights", exact: true })).toBeEnabled();
  await expect
    .poll(() => page.locator(".chat-log").evaluate((element) => element.scrollTop))
    .toBe(0);

  await page.getByRole("textbox", { name: "Message" }).fill("Show fresh sales answer");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("First answer.")).toBeVisible();
  expect(conversationIds).toHaveLength(2);
  expect(conversationIds[1]).not.toBe(conversationIds[0]);
});

test("renders incremental answer and run context on desktop", async ({
  page,
}) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Commands" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "DE", exact: true })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Persona" })).toBeVisible();
  await expect(page.getByRole("button", { name: "DE", exact: true })).toBeDisabled();
  await page.getByRole("combobox", { name: "Persona" }).selectOption("de-support");
  await page.getByRole("button", { name: "DE", exact: true }).click();
  await expect(page.getByText("Flink streaming job has increasing consumer lag.")).toBeVisible();
  await page
    .getByRole("textbox", { name: "Message" })
    .fill("Show sales answer");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("First answer.")).toBeVisible();
  await page.getByText("Run context").click();
  await expect(page.getByText("App identity", { exact: true })).toBeVisible();
});

test("limits starter tabs and queries to the selected persona", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Operations", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Insights", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "HITL", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "DE", exact: true })).toBeDisabled();

  await page.getByRole("combobox", { name: "Persona" }).selectOption("executive");
  await expect(page.getByRole("button", { name: "Insights", exact: true })).toBeEnabled();
  await expect(page.getByRole("button", { name: "HITL", exact: true })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Operations", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "DE", exact: true })).toBeDisabled();
  await expect(
    page.getByText("What are the top 5 stores by appointment count, and are they also in the top 20 stores by sales?"),
  ).toBeVisible();
  await expect(
    page.getByText(/Using the 2025-08-30 to 2026-04-30 time window/),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "HITL", exact: true }).click();
  await expect(
    page.getByText("Find stores with strong revenue but declining CDI scores"),
  ).toBeVisible();
});

test("exposes OBO state and blocked responses", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("textbox", { name: "Message" }).fill("blocked");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Request blocked.")).toBeVisible();
  await page
    .getByRole("combobox", { name: "Persona" })
    .selectOption("executive");
  await page
    .getByRole("textbox", { name: "Message" })
    .fill("/token secret-token");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByText("Hybrid OBO")).toBeVisible();
});

test("keeps the workspace usable on mobile", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".app-shell")).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Message" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Send" })).toBeVisible();
});

test("transcribes speaker input into the message draft", async ({ page }) => {
  await page.addInitScript(() => {
    class MockSpeechRecognition {
      lang = "";
      interimResults = false;
      maxAlternatives = 1;
      onend: (() => void) | null = null;
      onerror: ((event: { error: string }) => void) | null = null;
      onresult: ((event: {
        resultIndex: number;
        results: ArrayLike<{ 0: { transcript: string } }>;
      }) => void) | null = null;

      start() {
        this.onresult?.({
          resultIndex: 0,
          results: [{ 0: { transcript: "What are" } }],
        });
        this.onresult?.({
          resultIndex: 0,
          results: [{ 0: { transcript: "What are the top five stores" } }],
        });
        this.onend?.();
      }

      abort() {}
    }

    Object.defineProperty(window, "SpeechRecognition", {
      configurable: true,
      value: MockSpeechRecognition,
    });
  });

  await page.goto("/");
  await page.getByRole("textbox", { name: "Message" }).fill("Show");
  await page.getByRole("button", { name: "Transcribe" }).click();
  await expect(page.getByRole("textbox", { name: "Message" })).toHaveValue(
    "Show What are the top five stores",
  );
});

test("cancels an active query without reporting a backend error", async ({ page }) => {
  await page.unroute("**/invocations");
  await page.route("**/invocations", async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1_000));
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: sse([{ type: "response.output_text.delta", delta: "Too late." }]),
    });
  });

  await page.goto("/");
  await page.getByRole("textbox", { name: "Message" }).fill("Long-running request");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(page.getByRole("button", { name: "Cancel" })).toBeVisible();
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByText("Query canceled.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Cancel" })).toHaveCount(0);
});

test("shows manager actions for a pending HITL response", async ({ page }) => {
  await page.route("**/approval-decisions", async (route) => {
    const body = route.request().postDataJSON();
    expect(body.decision).toBe("approved");
    expect(body.request_id).toBe("run-hitl-123");
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
        delegation: {
          task_id: "task-approved-123",
          correlation_id: body.request_id,
          source_agent: "approval-api",
          target_agent: "store-intervention-agent",
          intent: "store_intervention_planning",
          status: "pending",
          completed: false,
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
          openai_run: {
            run_id: "run-hitl-123",
            api: "responses",
            model: "databricks-gpt-5-6-luna",
          },
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
  await page
    .getByRole("textbox", { name: "Message" })
    .fill("Review HITL packet");
  await page.getByRole("button", { name: "Send" }).click();
  await expect(
    page.getByRole("button", { name: "Approve planning" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Request more info" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Reject" })).toBeVisible();
  await page.getByRole("button", { name: "Approve planning" }).click();
  await expect(page.getByText("Review packet ready.")).toBeVisible();
  await expect(
    page.getByText(/Follow-up task: task-approved-123/),
  ).toBeVisible();
});
