function readField(raw, keys) {
  for (const key of keys) {
    if (raw[key] !== undefined && raw[key] !== null && String(raw[key]).trim() !== "") {
      return raw[key];
    }
  }
  return null;
}

function toList(value) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item).trim()).filter(Boolean);
  }
  return String(value || "")
    .split("\n")
    .map((item) => item.replace(/^\d+\.\s*/, "").replace(/^[-*]\s*/, "").trim())
    .filter(Boolean);
}

function normalizeStoryHints(raw = {}) {
  return {
    path: readField(raw, ["path", "story_path", "storyPath"]) || null,
    expected_text: readField(raw, ["expected_text", "expectedText", "expected_result", "expectedResult"]) || null,
    expected_selector: readField(raw, ["expected_selector", "expectedSelector"]) || null,
    api_path: readField(raw, ["api_path", "apiPath"]) || null,
    method: readField(raw, ["method", "http_method", "httpMethod"]) || "GET",
    expected_status: Number(readField(raw, ["expected_status", "expectedStatus"]) || 200),
  };
}

function normalizeQaTestCase(raw, index) {
  const testCaseId = readField(raw, ["test_case_id", "testCaseId", "Test Case ID"]) || `TC_IMPORTED_${index + 1}`;
  const title = readField(raw, ["title", "Title"]) || `Imported Test Case ${index + 1}`;
  const preconditions = readField(raw, ["preconditions", "Preconditions"]) || "";
  const testSteps = readField(raw, ["test_steps", "testSteps", "Test Steps"]) || "";
  const testData = readField(raw, ["test_data", "testData", "Test Data"]) || "";
  const expectedResult = readField(raw, ["expected_result", "expectedResult", "Expected Result"]) || "";
  const priority = readField(raw, ["priority", "Priority"]) || "";
  const actualResult = readField(raw, ["actual_result", "actualResult", "Actual Result"]) || "";
  const status = readField(raw, ["status", "Status"]) || "";

  const descriptionParts = [
    preconditions ? `Preconditions: ${preconditions}` : "",
    testData ? `Test data: ${testData}` : "",
    actualResult ? `Actual result: ${actualResult}` : "",
    status ? `Status: ${status}` : "",
  ].filter(Boolean);

  const acceptance = [
    ...toList(testSteps),
    expectedResult ? `Expected result: ${expectedResult}` : "",
  ].filter(Boolean);

  return {
    story_id: readField(raw, ["story_id", "storyId"]) || undefined,
    title: `${testCaseId} - ${title}`,
    description: descriptionParts.join("\n") || title,
    acceptance_criteria: acceptance,
    tags: ["qa-testcase", priority ? String(priority).toLowerCase() : "", status ? String(status).toLowerCase() : ""].filter(Boolean),
    hints: normalizeStoryHints({
      ...raw,
      expected_result: expectedResult,
    }),
  };
}

function normalizeStory(raw, index) {
  const looksLikeQaCase = Boolean(
    readField(raw, ["Test Case ID", "test_case_id", "testCaseId", "Test Steps", "test_steps", "Expected Result", "expected_result"])
  );

  if (looksLikeQaCase) {
    return normalizeQaTestCase(raw, index);
  }

  return {
    story_id: raw.story_id || raw.storyId || undefined,
    title: raw.title || raw.Title || `Imported Story ${index + 1}`,
    description: raw.description || raw.Description || "",
    acceptance_criteria: Array.isArray(raw.acceptance_criteria)
      ? raw.acceptance_criteria
      : toList(raw.acceptance_criteria || raw.acceptanceCriteria || raw["Acceptance Criteria"] || raw.expected_result || raw["Expected Result"] || ""),
    tags: Array.isArray(raw.tags)
      ? raw.tags
      : String(raw.tags || raw.Tags || "")
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
    hints: normalizeStoryHints(raw.hints || raw),
  };
}

function parseStructuredTextBlock(block, index) {
  const lines = block.split("\n").map((item) => item.trim()).filter(Boolean);
  const pairs = {};
  let currentKey = null;

  for (const line of lines) {
    const match = line.match(/^([A-Za-z][A-Za-z0-9 _/-]+)\s*:\s*(.*)$/);
    if (match) {
      currentKey = match[1].trim();
      pairs[currentKey] = match[2].trim();
      continue;
    }
    if (currentKey) {
      pairs[currentKey] = `${pairs[currentKey]}\n${line}`.trim();
    }
  }

  if (Object.keys(pairs).length) {
    return normalizeStory(pairs, index);
  }

  const title = lines[0] || `Imported Story ${index + 1}`;
  const description = lines[1] || title;
  const acceptance = lines
    .slice(2)
    .map((line) => line.replace(/^\d+\.\s*/, "").replace(/^[-*]\s*/, "").trim())
    .filter(Boolean);

  return normalizeStory({
    title,
    description,
    acceptance_criteria: acceptance,
    tags: ["bulk-import"],
  }, index);
}

export function parseBulkStories(text) {
  const source = String(text || "").trim();
  if (!source) {
    throw new Error("Paste user stories or test cases first.");
  }

  try {
    const parsed = JSON.parse(source);
    const items = Array.isArray(parsed) ? parsed : parsed.stories || parsed.testcases || parsed.test_cases;
    if (!Array.isArray(items) || !items.length) {
      throw new Error("JSON must be an array of stories/test cases or an object with a stories array.");
    }
    return items.map(normalizeStory);
  } catch (jsonError) {
    const blocks = source.split(/\n-{3,}\n/g).map((item) => item.trim()).filter(Boolean);
    if (!blocks.length) {
      throw jsonError;
    }
    return blocks.map(parseStructuredTextBlock);
  }
}

export function parseBulkLogs(text) {
  const source = String(text || "").trim();
  if (!source) {
    throw new Error("Paste logs first.");
  }

  try {
    const parsed = JSON.parse(source);
    const items = Array.isArray(parsed) ? parsed : parsed.entries;
    if (!Array.isArray(items) || !items.length) {
      throw new Error("JSON must be an array of log entries or an object with an entries array.");
    }
    return items.map((entry) => ({
      level: String(entry.level || "INFO").toUpperCase(),
      source: entry.source || "application",
      message: entry.message || "",
      context: entry.context || {},
    }));
  } catch {
    return source
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        const match = line.match(/^\[?(INFO|WARNING|ERROR)\]?\s*([^:]+)?:?\s*(.*)$/i);
        if (!match) {
          return {
            level: "INFO",
            source: "application",
            message: line,
            context: {},
          };
        }

        const [, level, sourceLabel, message] = match;
        return {
          level: String(level || "INFO").toUpperCase(),
          source: (sourceLabel || "application").trim(),
          message: (message || line).trim(),
          context: {},
        };
      });
  }
}
