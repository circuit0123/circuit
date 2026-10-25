// The data layer's public surface. Screens import from "@/data" and nothing else reaches the backend.
export * from "./appearance";
export * from "./auth";
export * from "./errors";
export * from "./features";
export * from "./gate";
export * from "./home";
export * from "./join";
export * from "./me";
export * from "./notifications";
export * from "./onboarding";
export { DataProvider } from "./provider";
export { useSession } from "./session";
export { MOCK, SCENARIOS, currentScenario, switchScenario, type Scenario } from "./mocks/config";
