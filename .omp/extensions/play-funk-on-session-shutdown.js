import { spawn } from "node:child_process";
import { appendFileSync, existsSync } from "node:fs";

const FUNK_SOUND_PATH = "/System/Library/Sounds/Funk.aiff";
const LOG_PATH = "/tmp/omp-funk-hook.log";
const COMPLETION_EVENTS = ["agent_end"];

let lastPlayedAt = 0;

/** Registers a completion sound hook for the final agent response only. */
export default function playFunkOnSessionShutdown(pi) {
  pi.setLabel("Play Funk on final response");
  logHookEvent("loaded");

  for (const eventName of COMPLETION_EVENTS) {
    pi.on(eventName, async () => {
      await playFunkSound(eventName);
    });
  }
}

/** Plays the macOS Funk sound once after the final response. */
function playFunkSound(eventName) {
  logHookEvent(eventName);
  if (!shouldPlayNow()) return Promise.resolve();
  if (!existsSync(FUNK_SOUND_PATH)) {
    logHookEvent("missing-sound");
    return Promise.resolve();
  }

  return new Promise((resolve) => {
    const player = spawn("/usr/bin/afplay", [FUNK_SOUND_PATH], {
      stdio: "ignore",
    });

    logHookEvent(`afplay-spawn:${player.pid ?? "unknown"}`);

    player.on("error", (error) => {
      logHookEvent(`spawn-error:${error.message}`);
      resolve();
    });
    player.on("close", (code) => {
      logHookEvent(`afplay-exit:${code ?? "signal"}`);
      resolve();
    });
  });
}

/** Returns true when enough time passed since the last sound. */
function shouldPlayNow() {
  const now = Date.now();
  if (now - lastPlayedAt < 1500) return false;
  lastPlayedAt = now;
  return true;
}

/** Appends low-noise diagnostics for hook loading and firing. */
function logHookEvent(eventName) {
  appendFileSync(LOG_PATH, `${new Date().toISOString()} ${eventName}\n`);
}
